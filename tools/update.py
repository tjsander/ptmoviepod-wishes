#!/usr/bin/env python3
"""Keep the wish list up to date. Meant to be run daily by a timer.

  1. Look at the podcast feed for episodes we don't have yet.
  2. For each new one: fetch the YouTube captions, find the wish segment, ask Claude to
     transcribe the wishes, look the films up on TMDB, and build a page of audio clips
     for checking who made each wish.
  3. About once a week (or whenever there is a new episode): re-check Blu-ray.com for
     every wish that hasn't come true.
  4. Rebuild wishes.md and the site, commit, push, and open a GitHub issue asking for a review.

Useful flags:
  --dry-run          do the lookups but change nothing on disk and publish nothing
  --no-publish       write files but don't commit, push or open an issue
  --releases         force the Blu-ray.com check now
  --skip-releases    never do the Blu-ray.com check on this run
  --baseline         record every current Blu-ray.com listing as already known, change no outcomes
  --draft N          print what Claude extracts for existing episode number N (a test; saves nothing)
"""
import argparse
import base64
import datetime
import difflib
import email.utils
import html
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bsky  # noqa: E402
import vtt2txt  # noqa: E402
import wishlib  # noqa: E402
from wishlib import DATA, ROOT, load, save  # noqa: E402

FEED = "https://feed.podbean.com/ptmoviepod/feed.xml"
CHANNEL = "https://www.youtube.com/@ptmoviepod/videos"
TMDB_TOKEN = Path.home() / ".config" / "mmboxmonkey" / "tmdb-token"
UA = "Mozilla/5.0 (X11; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
CHANT = re.compile(r"i wish,? i wish|we wish(ed)?,? we wish|wishes (out )?(in)?to the|time to (make|put) (some )?wish|wishing for movies", re.I)
OUTRO = re.compile(r"that('s| is|’s) (it|our show|going to do it)|thank you (all |so much |again )?for (listening|being here|checking|returning|joining)|that does it for", re.I)
REPACK = re.compile(r"Slipcover|Exclusive|Iconic Moments|Double Feature|Film Favorites|Collection|Pack\b|Trilogy|Mondo", re.I)
PUBLISHERS = {"Paramount Pictures": "Paramount", "Disney / Buena Vista": "Disney", "Lionsgate Films": "Lionsgate", "Raven Banner Releasing": "Raven Banner"}
TODAY = datetime.date.today()
norm = lambda s: re.sub(r"[^a-z0-9]", "", html.unescape(s).lower())
log = lambda *a: print(*a, flush=True)


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **kw)


# ---------------------------------------------------------------- new episodes

def feed_episodes():
    ns = {"itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd"}
    xml = urllib.request.urlopen(urllib.request.Request(FEED, headers={"User-Agent": UA}), timeout=30).read()
    out = []
    for it in ET.fromstring(xml).find("channel").findall("item"):
        ep = it.findtext("itunes:episode", namespaces=ns)
        if not ep:
            continue
        out.append(dict(season=int(it.findtext("itunes:season", namespaces=ns) or 1), episode=int(ep), title=it.findtext("title").strip(),
                        date=email.utils.parsedate_to_datetime(it.findtext("pubDate")).strftime("%Y-%m-%d")))
    return sorted(out, key=lambda e: e["date"])


def youtube_videos():
    r = run(["yt-dlp", "--flat-playlist", "--no-warnings", "--print", "%(id)s\t%(title)s", CHANNEL])
    return [line.split("\t", 1) for line in r.stdout.splitlines() if "\t" in line]


def fetch_captions(vid):
    """Download auto-captions for one video; return (vtt_path, txt_path) or None if not available yet."""
    vdir, tdir = ROOT / "transcripts" / "vtt", ROOT / "transcripts" / "txt"
    vdir.mkdir(parents=True, exist_ok=True)
    tdir.mkdir(parents=True, exist_ok=True)
    run(["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en", "--sub-format", "vtt", "--restrict-filenames", "--no-warnings",
         "-o", str(vdir / "%(upload_date)s_%(title).80s_%(id)s.%(ext)s"), "--", vid])
    hits = sorted(vdir.glob(f"*_{vid}.en.vtt"))
    if not hits:
        return None
    txt = tdir / (re.sub(r"\.en$", "", hits[0].stem) + ".txt")
    txt.write_text(vtt2txt.convert(hits[0]), encoding="utf-8")
    return hits[0], txt


def seconds(par):
    h, m, s = map(int, re.match(r"\[(\d+):(\d\d):(\d\d)\]", par).groups())
    return h * 3600 + m * 60 + s


def wish_segment(txt_path):
    """Return (start seconds, end seconds, text) of the end-of-episode wish segment."""
    P = Path(txt_path).read_text(encoding="utf-8").splitlines()
    hits = [i for i, p in enumerate(P) if CHANT.search(p) and i >= len(P) * 0.5]
    start = hits[0] if hits else max(0, len(P) - 25)
    end = next((i for i in range(start + 1, len(P)) if OUTRO.search(P[i])), len(P) - 1)
    end = min(end, start + 45)
    return max(0, seconds(P[start]) - 5), seconds(P[end]) + 32, "\n".join(P[max(0, start - 1):end + 1]), bool(hits)


PROMPT = """You are transcribing the end-of-episode "wishes" segment of Physical Therapy: A Movie Podcast.
In this segment each person chants "I wish, I wish" and then wishes for one film (occasionally more) to be released on a
physical media format it is not yet available on. They then discuss each wish, which usually reveals who wished for what.

Regular voices: Kurt (the host, also called "Marty"), Sam (co-host), Kimberly or "Kim"/"Kimmy" (producer, wishes only
occasionally), and Bobby (a recurring co-host in some episodes). The episode title names any guest.
The text is YouTube auto-captions: no speaker names (newer episodes mark a change of speaker with ">>"), and film titles
and names are often misspelled. Correct titles to the real film and add the release year.

Episode title: {title}

Return ONLY a JSON array, one object per wish, in the order wished:
  "movie":  "Correct Title (Year)"
  "fmt":    the format and label asked for, in a few words, such as "4K", "Blu-ray", "4K from Arrow Video",
            "Criterion Blu-ray or 4K", "4K, probably Kino", or "Not stated" if none was named
  "who":    "Kurt", "Sam", "Kimberly", "Bobby", or the guest's full name
  "guest":  true if the wisher is a guest, otherwise false
  "sure":   true only if the conversation makes the wisher unambiguous
  "note":   "" or one short sentence if the wisher changed their wish or said they had wished for it before
If someone changes their wish, return only the final wish and mention the first in "note".
If the segment contains no wishes, return [].

Segment:
{segment}
"""


def draft_wishes(title, segment):
    r = run(["claude", "-p", PROMPT.format(title=title, segment=segment)], timeout=600)
    m = re.search(r"\[.*\]", r.stdout, re.S)
    if not m:
        raise RuntimeError("Claude returned no JSON: " + (r.stdout or r.stderr)[:300])
    out = []
    for w in json.loads(m.group(0)):
        if isinstance(w, dict) and w.get("movie"):
            out.append(dict(movie=w["movie"].strip(), fmt=(w.get("fmt") or "Not stated").strip(), who=(w.get("who") or "Unknown").strip(),
                            guest=bool(w.get("guest")), sure=bool(w.get("sure")), note=(w.get("note") or "").strip()))
    return out


def tmdb_lookup(movie):
    """Find a film on TMDB, preferring the well-known one when several share a title."""
    tok = os.environ.get("TMDB_TOKEN") or (TMDB_TOKEN.read_text().strip() if TMDB_TOKEN.exists() else "")
    if not tok:
        log("  no TMDB token (set TMDB_TOKEN or create", TMDB_TOKEN, "): no poster or Letterboxd link for", movie)
        return []
    m = re.match(r"^(.*?)\s*\((\d{4})", movie)
    title, year = (m.group(1), int(m.group(2))) if m else (movie, None)

    def api(kind, only_year=None):
        q = {"query": title, "include_adult": "true"}
        if only_year:
            q["primary_release_year"] = only_year
        headers = {"Accept": "application/json"}
        if len(tok) > 60:
            headers["Authorization"] = "Bearer " + tok
        else:
            q["api_key"] = tok
        req = urllib.request.Request(f"https://api.themoviedb.org/3/search/{kind}?" + urllib.parse.urlencode(q), headers=headers)
        return json.load(urllib.request.urlopen(req, timeout=20)).get("results", [])

    # Every result with a plausible title and year is a candidate. When several qualify (two films
    # sharing a title, or a short title inside a longer one) the most popular wins, measured by TMDB
    # vote count and then its popularity score, which on its own swings with what is trending.
    for kind in ("movie", "tv"):
        candidates = []
        for r in api(kind):
            name = r.get("title") or r.get("name") or ""
            original = r.get("original_title") or r.get("original_name") or ""
            date = (r.get("release_date") or r.get("first_air_date") or "")[:4]
            if year and (not date or abs(int(date) - year) > 1):
                continue
            q = norm(title)
            sim = max(difflib.SequenceMatcher(None, norm(n), q).ratio() for n in (name, original))
            contains = len(q) >= 5 and any(norm(n).startswith(q) for n in (name, original))
            if sim >= 0.75 or contains:
                candidates.append((r.get("vote_count", 0), r.get("popularity", 0), dict(q=title, kind=kind, id=r["id"], title=name, year=date, poster=r.get("poster_path"))))
        if candidates:
            return [max(candidates, key=lambda c: c[:2])[2]]
    # nothing looked right by title (e.g. "9 to 5" is listed as "Nine to Five"): trust TMDB's own top hit for that year
    if year:
        hits = api("movie", year)
        if hits:
            r = max(hits[:3], key=lambda r: r.get("vote_count", 0))
            return [dict(q=title, kind="movie", id=r["id"], title=r.get("title") or "", year=(r.get("release_date") or "")[:4], poster=r.get("poster_path"))]
    return []


def cut_clip(vid, start, end):
    """Cache the episode audio and return an mp3 clip of the wish segment as bytes (or None)."""
    adir = ROOT / "audio"
    adir.mkdir(exist_ok=True)
    if not list(adir.glob(f"*_{vid}.*")):
        run(["yt-dlp", "--no-warnings", "--no-progress", "-f", "bestaudio", "--restrict-filenames", "-o", str(adir / "%(upload_date)s_%(title).80s_%(id)s.%(ext)s"), "--", vid])
    src = next(iter(sorted(adir.glob(f"*_{vid}.*"))), None)
    if not src:
        return None
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(start), "-to", str(end), "-i", str(src), "-ac", "1", "-b:a", "48k", "-f", "mp3", "-"], capture_output=True)
    return r.stdout or None


def confirm_page(items):
    """Write confirm/index.html: one audio clip per new episode with a wisher dropdown per wish."""
    cards = []
    for e, wishes, clip in items:
        names = ["Kurt", "Sam", "Bobby", "Kimberly"] + sorted({w["who"] for w in wishes if w["guest"]}) + ["Not sure"]
        rows = []
        for w in wishes:
            opts = "".join(f'<option{" selected" if n == w["who"] else ""}>{html.escape(n)}</option>' for n in dict.fromkeys(names + [w["who"]]))
            rows.append(f'<div class="wish" data-ep="{wishlib.ep_code(e)}" data-movie="{html.escape(w["movie"])}"><span class="movie">{html.escape(w["movie"])}'
                        f'<small>{html.escape(w["fmt"])}{"" if w.get("sure", True) else " · unsure"}</small></span>'
                        f'<label>Wished by <select>{opts}</select></label><input type="text" placeholder="or type a name"></div>')
        audio = f'<audio controls preload="metadata" src="data:audio/mpeg;base64,{base64.b64encode(clip).decode()}"></audio>' if clip else "<p class=meta>No audio clip available.</p>"
        cards.append(f'<section><h2>{wishlib.ep_code(e)} · {html.escape(e["title"])}</h2><p class="meta">{e["date"]} · '
                     f'<a href="https://www.youtube.com/watch?v={e["vid"]}&t={e["t"]}s">open on YouTube</a></p>{audio}{"".join(rows)}</section>')
    page = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Confirm wishers</title><style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1d1f;--mute:#666;--line:#d9d6cf;--accent:#2f5d50}
@media (prefers-color-scheme:dark){:root{--bg:#17181a;--card:#212327;--ink:#ececec;--mute:#a0a0a0;--line:#3a3d42;--accent:#7fc4ad}}
body{background:var(--bg);color:var(--ink);font:16px/1.45 system-ui,sans-serif;margin:0;padding:24px 16px 80px}main{max-width:760px;margin:0 auto}
h1{font-size:1.5rem;margin:0 0 4px}h2{font-size:1.05rem;margin:0}.meta,.intro,small{color:var(--mute);font-size:.9rem}small{display:block;font-weight:400}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin:16px 0}audio{width:100%;margin:10px 0}
.wish{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:center;padding:8px 0;border-top:1px solid var(--line)}.movie{font-weight:600;flex:1 1 220px}
select,input,textarea,button{font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:6px 8px}input{flex:1 1 160px;min-width:0}
textarea{width:100%;box-sizing:border-box;height:160px;font:13px/1.4 ui-monospace,monospace}button{background:var(--accent);color:var(--bg);border:0;padding:8px 16px;cursor:pointer;font-weight:600}
</style></head><body><main><h1>Confirm who made each wish</h1>
<p class="intro">Each dropdown starts on the automatic guess. Play the clip, correct anything wrong, then copy the results and run <code>python3 tools/confirm.py</code> and paste them (finish with Ctrl-D).</p>
__CARDS__<section><h2>Results</h2><textarea id="out" readonly></textarea><p><button id="copy">Copy results</button> <span id="msg" class="meta"></span></p></section></main><script>
var out=document.getElementById('out');function build(){out.value=[].map.call(document.querySelectorAll('.wish'),function(w){var t=w.querySelector('input').value.trim();
return w.dataset.ep+' | '+w.dataset.movie+' | '+(t||w.querySelector('select').value)}).join('\\n')}document.addEventListener('input',build);build();
document.getElementById('copy').onclick=function(){navigator.clipboard.writeText(out.value).then(function(){document.getElementById('msg').textContent='Copied.'},function(){out.select()})};
</script></body></html>""".replace("__CARDS__", "".join(cards))
    (ROOT / "confirm").mkdir(exist_ok=True)
    (ROOT / "confirm" / "index.html").write_text(page, encoding="utf-8")


def same_film(movie, known):
    """Return the already-wished film string that is the same film as `movie`, or None."""
    split = lambda s: (norm(re.sub(r"^(the|a|an) ", "", re.sub(r"\s*\(.*$", "", s).lower())), int(m.group(1)) if (m := re.search(r"\((\d{4})", s)) else None)
    title, year = split(movie)
    for k in known:
        t2, y2 = split(k)
        if t2 == title and (year is None or y2 is None or abs(year - y2) <= 1):
            return k
    return None


def ingest_new_episodes(dry):
    episodes, wishes, tmdb = load("episodes.json"), load("wishes.json"), load("tmdb.json")
    have = {(e["season"], e["episode"]) for e in episodes} | {norm(e["title"]) for e in episodes}
    new = [f for f in feed_episodes() if (f["season"], f["episode"]) not in have and norm(f["title"]) not in have]
    if not new:
        log("feed: no new episodes")
        return []
    used = {e["vid"] for e in episodes}
    videos = [v for v in youtube_videos() if v[0] not in used]
    added, pages = [], []
    for f in new:
        log(f"new episode: S{f['season']}E{f['episode']:02d} {f['title']} ({f['date']})")
        match = max(videos, key=lambda v: difflib.SequenceMatcher(None, norm(v[1]), norm(f["title"])).ratio(), default=None)
        if not match or difflib.SequenceMatcher(None, norm(match[1]), norm(f["title"])).ratio() < 0.6:
            log("  not on YouTube yet; will try again next run")
            continue
        caps = fetch_captions(match[0])
        if not caps:
            log("  captions not ready yet; will try again next run")
            continue
        start, end, segment, found = wish_segment(caps[1])
        try:
            drafted = draft_wishes(f["title"], segment)
        except Exception as err:
            log("  could not draft wishes:", err)
            continue
        e = dict(n=max(x["n"] for x in episodes) + 1, season=f["season"], episode=f["episode"], date=f["date"], title=f["title"], vid=match[0], file=caps[1].name, t=start if found else 0)
        episodes.append(e)
        videos.remove(match)
        mine = []
        for d in drafted:
            # a repeat is the same film as an earlier wish, however the title was written; reuse the earlier spelling
            earlier = same_film(d["movie"], [w["movie"] for w in wishes])
            if earlier:
                d["movie"] = earlier
            w = dict(ep=e["n"], movie=d["movie"], fmt=d["fmt"], who=d["who"], guest=d["guest"], repeat=bool(earlier), notes=[d["note"]] if d["note"] else [], confirmed=False)
            wishes.append(w)
            mine.append(dict(w, sure=d["sure"]))
            if d["movie"] not in tmdb:
                tmdb[d["movie"]] = tmdb_lookup(d["movie"])
            log(f"  wish: {d['movie']} | {d['fmt']} | {d['who']}{'' if d['sure'] else ' (unsure)'}{' | REPEAT' if w['repeat'] else ''}")
        added.append((e, mine))
        if not dry:
            pages.append((e, mine, cut_clip(e["vid"], start, end)))
    if added and not dry:
        save("episodes.json", episodes)
        save("wishes.json", wishes)
        save("tmdb.json", tmdb)
        confirm_page(pages)
    return added


# ---------------------------------------------------------------- Blu-ray.com

def curl(url):
    return run(["curl", "-s", "-m", "30", "-A", UA, "-H", "Accept: text/html,application/xhtml+xml", "-H", "Accept-Language: en-US,en;q=0.9",
                "-e", "https://www.blu-ray.com/", "--compressed", url]).stdout


def search_bluray(keyword):
    page = curl("https://www.blu-ray.com/movies/search.php?keyword=" + urllib.parse.quote_plus(keyword) + "&submit=Search&action=search")
    time.sleep(1)
    out = {}
    for url, name in re.findall(r'href="(https://www\.blu-ray\.com/movies/[^"]+-Blu-ray/\d+/)"[^>]*title="([^"]*)"', page):
        out.setdefault(url, html.unescape(name))
    # the quick-search box sometimes knows short or common titles that the full search buries
    quick = run(["curl", "-s", "-m", "30", "-A", UA, "-e", "https://www.blu-ray.com/", "--compressed", "https://www.blu-ray.com/search/quicksearch.php",
                 "--data-urlencode", "section=bluraymovies", "--data-urlencode", "userid=-1", "--data-urlencode", "country=US", "--data-urlencode", "keyword=" + keyword]).stdout
    time.sleep(1)
    names = [html.unescape(n) for n in re.findall(r'flags/\w+\.png"[^>]*>&nbsp;(.*?)</li>', quick)]
    m = re.search(r"var urls = new Array\((.*?)\);", quick)
    for url, name in zip(re.findall(r"'([^']*)'", m.group(1)) if m else [], names):
        out.setdefault(url, name)
    return out


def release_page(url):
    """Return (publisher, ISO date or None) from a Blu-ray.com release page."""
    page = curl(url)
    time.sleep(1)
    i = page.find("subheading grey")
    if i < 0:
        return None, None
    parts = [x.strip() for x in re.sub(r"<[^>]+>", "|", page[i + 17:i + 900]).split("|") if x.strip()]
    pub = html.unescape(parts[0]) if parts else None
    if pub and re.fullmatch(r"\d{4}", pub):
        pub = None
    date = None
    for p in parts[1:8]:
        for fmt in ("%b %d, %Y", "%b %Y"):
            try:
                date = datetime.datetime.strptime(p, fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return PUBLISHERS.get(pub, pub), date


def title_matches(name, keyword, year):
    ym = re.search(r"\((\d{4})\)\s*$", name)
    base = re.sub(r"\s+4K\b.*$", "", re.sub(r"\s*\([^)]*\)?", "", name).replace("…", ""))
    ok = norm(base) == norm(keyword) or (len(norm(keyword)) > 8 and norm(keyword) in norm(base))
    return ok and not (year and ym and abs(int(ym.group(1)) - year) > 1)


def month(iso):
    return datetime.date.fromisoformat(iso).strftime("%b %Y")


def check_releases(dry, baseline=False):
    """Look for new Blu-ray.com listings for every wish that hasn't come true; return a list of report lines."""
    outcomes, wishes = load("outcomes.json"), load("wishes.json")
    seen = load("seen_releases.json") if (DATA / "seen_releases.json").exists() else {}
    overrides = load("search_overrides.json")
    fmts = {}
    for w in wishes:
        fmts.setdefault(w["movie"], []).append(w["fmt"])
    report = []
    for movie in fmts:
        key = wishlib.outcome_key(movie, outcomes)
        o = outcomes.get(key) if key else None
        status = o["status"] if o else "no"
        if status == "yes":
            continue
        # an announced date arriving, or a date appearing on an undated listing
        if o and status in ("listed", "announced") and o.get("urls") and "blu-ray.com" in o["urls"][0] and not baseline:
            before = o.get("released")
            pub, iso = release_page(o["urls"][0])
            if iso and iso != o.get("released"):
                o["released"] = iso
            if o.get("released"):
                kind = o["detail"].split(" ")[0].rstrip(",")
                released = datetime.date.fromisoformat(o["released"]) <= TODAY
                new_status = "yes" if released else "announced"
                new_detail = f"{kind}, {month(o['released'])}" if released else f"{kind} due {month(o['released'])}"
                if new_status != status or o["released"] != before:
                    report.append(f"**{movie}**: {status} → {new_status} ({new_detail}, {o['pub']}) {o['urls'][0]}")
                    o["status"], o["detail"], status = new_status, new_detail, new_status
            if status == "yes":
                continue
        m = re.match(r"^(.*?)\s*\((\d{4})", movie)
        keys = overrides.get(movie) or [[re.sub(r"[!?]", "", m.group(1)) if m else movie, int(m.group(2)) if m else None]]
        known = seen.setdefault(movie, {})
        fresh = []
        for keyword, year in keys:
            for url, name in search_bluray(keyword).items():
                if url in known or not title_matches(name, keyword, year):
                    continue
                entry = dict(name=name, uhd=bool(re.search(r"\b4K\b", name)), seen=TODAY.isoformat())
                if not baseline:
                    entry["pub"], entry["iso"] = release_page(url)
                    fresh.append(dict(entry, url=url))
                known[url] = entry
        if baseline or not fresh:
            continue
        for e in fresh:
            report.append(f"New listing for **{movie}**: {e['name']} ({e.get('pub') or 'publisher unknown'}, {e.get('iso') or 'no date'}) {e['url']}")
        if o and o.get("manual"):
            report.append(f"  ↳ {movie} is judged by hand (edition-specific wish), so its status was left as “{status}”.")
            continue
        want4k = any("4K" in f for f in fmts[movie])
        loose = any(("Blu-ray" in f and "4K" not in f) or f.startswith("Any") or "Not stated" in f for f in fmts[movie])
        labels = {l for f in fmts[movie] for l in wishlib.wanted_labels(f)}
        good = []
        for e in fresh:
            if not e.get("pub") or REPACK.search(e["name"]):
                continue
            if (want4k and e["uhd"]) or (loose and not want4k) or (not want4k and not loose and e["pub"] in labels):
                good.append(e)
        if not good:
            continue
        best = min(good, key=lambda e: (e["iso"] is None, e["iso"] or "", not e["uhd"]))
        kind = "4K" if best["uhd"] else "Blu-ray"
        if best["iso"] and datetime.date.fromisoformat(best["iso"]) <= TODAY:
            new = dict(status="yes", detail=f"{kind}, {month(best['iso'])}")
        elif best["iso"]:
            new = dict(status="announced", detail=f"{kind} due {month(best['iso'])}")
        else:
            new = dict(status="listed", detail=kind)
        if wishlib.RANK[new["status"]] > wishlib.RANK[status]:
            outcomes[key or movie] = dict(new, pub=best["pub"], urls=[best["url"]], released=best["iso"], manual=False)
            report.append(f"  ↳ **{movie}**: {status} → {new['status']} ({new['detail']}, {best['pub']})")
    if not dry:
        save("seen_releases.json", seen)
        if not baseline:
            save("outcomes.json", outcomes)
    return report


def check_bsky(dry, state):
    """Apply release announcements Disc Connected posted on Bluesky since the last look; return report lines."""
    since = state.get("last_bsky") or (state.get("last_release_check", TODAY.isoformat()) + "T00:00:00Z")
    try:
        found, newest = bsky.fetch_since(since)
    except Exception as e:  # network or API trouble shouldn't stop the rest of the update
        log("bluesky check failed:", e)
        return []
    outcomes, wishes = load("outcomes.json"), load("wishes.json")
    fmts = {}
    for w in wishes:
        fmts.setdefault(w["movie"], []).append(w["fmt"])
    report = []
    for movie in fmts:
        key = wishlib.outcome_key(movie, outcomes)
        o = outcomes.get(key) if key else None
        status = o["status"] if o else "no"
        if status == "yes":
            continue
        hits = [a for a in found if bsky.matches(a, movie)]
        if not hits:
            continue
        for a in hits:
            report.append(f"Announcement for **{movie}**: {a['title']}, {a['fmt']}, {a['pub']}, {a['iso'] or a['when']} {a['url']}")
        if o and o.get("manual"):
            report.append(f"  ↳ {movie} is judged by hand (edition-specific wish), so its status was left as “{status}”.")
            continue
        want4k = any("4K" in f for f in fmts[movie])
        loose = any(("Blu-ray" in f and "4K" not in f) or f.startswith("Any") or "Not stated" in f for f in fmts[movie])
        labels = {l for f in fmts[movie] for l in wishlib.wanted_labels(f)}
        good = [a for a in hits if not REPACK.search(a["title"] + " " + a["fmt"])
                and ((want4k and a["uhd"]) or (loose and not want4k) or (not want4k and not loose and a["pub"] in labels))]
        if not good:
            continue
        best = min(good, key=lambda a: (a["iso"] is None, a["iso"] or "", not a["uhd"]))
        kind = "4K" if best["uhd"] else "Blu-ray"
        if best["iso"] and datetime.date.fromisoformat(best["iso"]) <= TODAY:
            new = dict(status="yes", detail=f"{kind}, {month(best['iso'])}")
        elif best["iso"]:
            new = dict(status="announced", detail=f"{kind} due {month(best['iso'])}")
        else:
            new = dict(status="listed", detail=kind)
        if wishlib.RANK[new["status"]] > wishlib.RANK[status]:
            outcomes[key or movie] = dict(new, pub=best["pub"], urls=[best["url"]], released=best["iso"], manual=False)
            report.append(f"  ↳ **{movie}**: {status} → {new['status']} ({new['detail']}, {best['pub']})")
    if not dry:
        save("outcomes.json", outcomes)
        state["last_bsky"] = newest
        save("state.json", state)
    return report


# ---------------------------------------------------------------- publish

def publish(added, report):
    git = lambda *a: run(["git", "-C", str(ROOT), *a])
    if git("rev-parse", "--is-inside-work-tree").returncode:
        log("not a git repository; nothing published")
        return
    git("add", "-A")
    if not git("diff", "--cached", "--quiet").returncode:
        log("nothing changed")
        return
    bits = [f"{len(w)} wishes from {wishlib.ep_code(e)}" for e, w in added] + ([f"{len(report)} release updates"] if report else [])
    git("commit", "-m", "Update wish list: " + (", ".join(bits) or "refresh"))
    if git("remote").stdout.strip():
        p = git("push")
        log("pushed" if not p.returncode else "push failed: " + p.stderr[-300:])
    if not (added or report):
        return
    body = []
    for e, wishes in added:
        body += [f"### New episode: {wishlib.ep_code(e)} · {e['title']}", "",
                 f"Wishes were transcribed automatically and are live, marked unconfirmed. [Listen to the segment](https://www.youtube.com/watch?v={e['vid']}&t={e['t']}s).", "",
                 "| Film | Format | Wished by | Sure? |", "|---|---|---|---|"]
        body += [f"| {w['movie']} | {w['fmt']} | {w['who']} | {'yes' if w.get('sure') else '**no**'} |" for w in wishes]
        body += ["", "To confirm: open `confirm/index.html` on the machine that ran the update, check each wisher, then run `python3 tools/confirm.py` and paste the results. "
                 "If a title or format is wrong, edit `data/wishes.json` and run `python3 tools/update.py --skip-releases`.", ""]
    if report:
        body += ["### Release changes found (Blu-ray.com and Disc Connected on Bluesky)", "", "These were applied automatically from title matches, so please check them.", ""] + [f"- {line}" if not line.startswith("  ") else line for line in report]
    title = "Review: " + (", ".join(f"new wishes from {wishlib.ep_code(e)}" for e, _ in added) or "release status changes")
    issue = run(["gh", "issue", "create", "--title", title, "--body", "\n".join(body)], cwd=ROOT)
    log("review issue:", issue.stdout.strip() or issue.stderr.strip()[-200:])
    run(["notify-send", "Physical Therapy wish list updated", title + ". Please review."])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for flag in ("--dry-run", "--no-publish", "--releases", "--skip-releases", "--baseline"):
        ap.add_argument(flag, action="store_true")
    ap.add_argument("--draft", type=int, metavar="N")
    a = ap.parse_args()
    if a.draft:
        e = next(x for x in load("episodes.json") if x["n"] == a.draft)
        _, _, segment, _ = wish_segment(ROOT / "transcripts" / "txt" / e["file"])
        for w in draft_wishes(e["title"], segment):
            log(w)
        return
    state = load("state.json") if (DATA / "state.json").exists() else {}
    if a.baseline:
        check_releases(a.dry_run, baseline=True)
        log("baseline recorded")
        return
    added = ingest_new_episodes(a.dry_run)
    last = state.get("last_release_check")
    due = not last or (TODAY - datetime.date.fromisoformat(last)).days >= 7
    report = []
    if not a.skip_releases and (a.releases or due or added):
        log("checking Blu-ray.com…")
        report = check_releases(a.dry_run)
        for line in report:
            log(" ", line)
        if not a.dry_run:
            state["last_release_check"] = state["checked"] = TODAY.isoformat()
            save("state.json", state)
    if not a.skip_releases:
        log("checking Disc Connected on Bluesky…")
        extra = check_bsky(a.dry_run, state)
        for line in extra:
            log(" ", line)
        report += extra
    if a.dry_run:
        log("dry run: nothing written")
        return
    wishlib.build_all()
    if not a.no_publish:
        publish(added, report)


if __name__ == "__main__":
    main()
