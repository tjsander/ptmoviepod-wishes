"""Shared logic for the wish list: load the data, judge each wish, and write the outputs.

Source of truth (all in data/):
  episodes.json   one entry per podcast episode (number, date, title, YouTube id, wish-segment start)
  wishes.json     one entry per wish (episode, film, format, who, repeat, notes, confirmed)
  outcomes.json   release status per film, keyed by a prefix of the film string
  tmdb.json       TMDB id and poster per film string

Outputs:
  wishes.md        the leader board table and bullets, the main table and the repeat-wish table
                   (everything else in that file is left as written by hand)
  docs/data.json   what the website reads
"""
import collections
import datetime
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PEOPLE = ["Kurt", "Sam", "Bobby", "Kimberly", "Guests"]
LABELS = [("Arrow", "Arrow"), ("Kino", "Kino Lorber"), ("Criterion", "Criterion"), ("Shout", "Shout Factory"), ("Scream Factory", "Shout Factory"),
          ("Second Sight", "Second Sight"), ("Paramount Presents", "Paramount"), ("BFI", "BFI"), ("Sony", "Sony Pictures"), ("A24", "A24")]
BOUTIQUE = {"Arrow", "Criterion", "Kino Lorber", "Shout Factory", "Vinegar Syndrome", "Synapse Films", "Radiance Films", "Second Sight"}
NO_FILM_LINK = {"Godzilla Heisei-era films (box set)", "Original Heisei-era poster art included in that Godzilla set"}
RANK = {"no": 0, "partly": 1, "listed": 2, "announced": 3, "yes": 4}


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def ep_code(e):
    return f"S{e['season']}E{e['episode']:02d}"


def short_title(movie):
    return movie.rsplit(" (", 1)[0]


def outcome_key(movie, outcomes):
    return next((k for k in sorted(outcomes, key=len, reverse=True) if movie.startswith(k)), None)


def wanted_labels(fmt):
    if "Columbia Classics" in fmt:
        return []
    out = []
    for token, name in LABELS:
        if token in fmt and name not in out:
            out.append(name)
    return out


def judge(wish, outcomes):
    """Return the outcome of one wish: status, texts for the tables, publisher match."""
    key = outcome_key(wish["movie"], outcomes)
    o = outcomes.get(key) if key else None
    if not o or o["status"] == "no":
        detail = o["detail"] if o else ""
        return dict(status="no", detail=detail, pub=None, urls=[], released=None, label=None,
                    came=f"No ({detail})" if detail else "No", lab="—")
    status, detail, pub = o["status"], o["detail"], o["pub"]
    came = f"Not yet ({detail} listed with no date)" if status == "listed" else f"{status.capitalize()} ({detail})"
    wanted = wanted_labels(wish["fmt"])
    if "boutique" in wish["fmt"]:
        label, lab = ("yes", f"Yes ({pub})") if pub in BOUTIQUE else ("no", f"No ({pub})")
    elif not wanted:
        label, lab = "n/a", f"n/a ({pub})"
    elif pub in wanted:
        label, lab = "yes", f"Yes ({pub})"
    else:
        label, lab = "no", f"No ({pub}, not {' or '.join(wanted)})"
    return dict(status=status, detail=detail, pub=pub, urls=o.get("urls", []), released=o.get("released"), label=label, came=came, lab=lab)


def rows():
    """Every wish joined with its episode and outcome, in episode order."""
    eps = {e["n"]: e for e in load("episodes.json")}
    outcomes = load("outcomes.json")
    out = []
    for i, w in enumerate(load("wishes.json")):
        e = eps[w["ep"]]
        r = dict(w, i=i, e=e, code=ep_code(e), **judge(w, outcomes))
        r["wait"] = None
        if r["status"] == "yes" and r["released"]:
            r["wait"] = (datetime.date.fromisoformat(r["released"]) - datetime.date.fromisoformat(e["date"])).days
        out.append(r)
    out.sort(key=lambda r: (r["ep"], r["i"]))
    for r in out:
        if r["repeat"]:
            r["first"] = next((x for x in out if x["movie"] == r["movie"] and not x["repeat"]), None)
    return out


# ---------------------------------------------------------------- markdown

def _esc(s):
    return s.replace("|", "\\|")


def _who(r):
    return r["who"] + (" (guest)" if r["guest"] else "") + ("" if r.get("confirmed", True) else " (unconfirmed)")


def main_table(R):
    lines = ["| Movie | Format wished for | Format came true? | Wished-for publisher? | Ep. | Episode | Date | Wished by | Notes |", "|---|---|---|---|---|---|---|---|---|"]
    for r in R:
        if not r["repeat"]:
            lines.append(f"| {_esc(r['movie'])} | {_esc(r['fmt'])} | {_esc(r['came'])} | {_esc(r['lab'])} | {r['code']} | {_esc(r['e']['title'])} | {r['e']['date']} | {_who(r)} | {_esc('; '.join(r['notes']))} |")
    return lines


def repeat_table(R):
    lines = ["| Movie | Repeated by | Ep. | Date | Asked for this time | First wished by | First asked for | Format came true? |", "|---|---|---|---|---|---|---|---|"]
    for r in R:
        if r["repeat"] and r.get("first"):
            f = r["first"]
            lines.append(f"| {_esc(r['movie'])} | {_who(r)} | {r['code']} | {r['e']['date']} | {_esc(r['fmt'])} | {_who(f)}, {f['code']} ({f['e']['date']}) | {_esc(f['fmt'])} | {_esc(r['came'])} |")
    return lines


def leaderboard(R):
    counted = [r for r in R if not r["repeat"]]
    reps = [r for r in R if r["repeat"]]
    mine = lambda r, name: r["guest"] if name == "Guests" else (r["who"] == name and not r["guest"])
    labels = ["Wishes made", "Repeat wishes 🔔 (shame, not counted)", "Came true (wished format released in the US)", "Announced with a release date",
              "Listed with no date yet", "Partly came true", "Will come true (announced + listed + half for partly)", "Fastest wish granted",
              "Longest wait for a granted wish", "Average wait for a granted wish", "Granted (came true + will come true)"]
    cols, scores, shame = [], [], []
    for name in PEOPLE:
        W = [r for r in counted if mine(r, name)]
        yes = [r for r in W if r["status"] == "yes"]
        timed = [r for r in yes if r["wait"] is not None]
        n = lambda s: sum(r["status"] == s for r in W)
        will = n("announced") + n("listed") + n("partly") / 2
        pct = lambda x: round(100 * x / len(W)) if W else 0
        fast = min(timed, key=lambda r: r["wait"]) if timed else None
        slow = max(timed, key=lambda r: r["wait"]) if timed else None
        shame.append(sum(mine(r, name) for r in reps))
        scores.append(len(yes) + will)
        cols.append([str(len(W)), "", f"{len(yes)} ({pct(len(yes))}%)", str(n("announced")), str(n("listed")), str(n("partly")), f"{will:g}",
                     f"{short_title(fast['movie'])}, {fast['wait']} days" if fast else "—", f"{short_title(slow['movie'])}, {slow['wait']} days" if slow else "—",
                     f"{round(sum(r['wait'] for r in timed) / len(timed))} days" if timed else "—", f"{len(yes) + will:g} ({pct(len(yes) + will)}%)"])
    worst = max(shame)
    for c, k in zip(cols, shame):
        c[1] = "😇 0" if k == 0 else ("🤡 " if k == worst else "🙈 ") + str(k)
    for medal, k in zip("🥇🥈🥉", sorted(range(len(cols)), key=lambda k: -scores[k])[:3]):
        cols[k][-1] = medal + " " + cols[k][-1]
    lines = ["| | " + " | ".join(PEOPLE) + " |", "|---" * (len(PEOPLE) + 1) + "|"]
    lines += [f"| {label} | " + " | ".join(c[i] for c in cols) + " |" for i, label in enumerate(labels)]

    bullets = []
    kim = [r for r in counted if mine(r, "Kimberly")]
    if kim and not any(r["status"] == "yes" for r in kim):
        near = next((r for r in kim if r["status"] in ("announced", "listed")), None)
        tail = f" The closest is {short_title(near['movie'])}, which Blu-ray.com lists from {near['pub']}" + (" with no date." if near["status"] == "listed" else ".") if near else ""
        bullets.append("- **Kimberly:** no wish granted yet." + tail)
    G = [r for r in counted if r["guest"]]
    if G:
        made = collections.Counter(r["who"] for r in G)
        top = made.most_common(1)[0][0]
        won = [short_title(r["movie"]) for r in G if r["who"] == top and r["status"] == "yes"]
        bullets.append(f"- **Guests:** {len(made)} guests made {len(G)} wishes between them. {top} made the most ({made[top]})"
                       + (f" and has had {len(won)} granted: {' and '.join(won)}." if won else "."))
    times = collections.Counter(r["movie"] for r in R)
    movie, k = times.most_common(1)[0]
    if k > 1:
        whos = sorted({r["who"] for r in R if r["movie"] == movie})
        st = next(r for r in R if r["movie"] == movie)
        bullets.append(f"- **Most-wished film:** {short_title(movie)}, wished {['', 'once', 'twice', 'three times', 'four times', 'five times'][min(k, 5)]} by {' and '.join(whos)}"
                       + (" and still not on 4K." if st["status"] == "no" and "4K" in st["fmt"] else "."))
    bullets.append(f"- **Everyone:** {sum(r['status'] == 'yes' for r in counted)} of {len(counted)} wishes have come true, counting guests.")
    bullets.append(f"- **Repeat wishes:** wishing for something already wished for on the show earns a Repeat 🔔 tag and no credit in these numbers. {len(reps)} so far.")
    bullets.append("- **Counting:** repeat wishes are left out of every number above. Waits run from the episode date to the US release date.")
    unconfirmed = [r for r in R if not r.get("confirmed", True)]
    if unconfirmed:
        bullets.append(f"- **Unconfirmed:** {len(unconfirmed)} recent wishes were transcribed automatically and are waiting for a human check of who made them.")
    return lines, bullets


def write_markdown(R, checked=None):
    """Refresh the generated parts of wishes.md, leaving hand-written headings and notes alone."""
    path = ROOT / "wishes.md"
    md = path.read_text(encoding="utf-8")
    table, bullets = leaderboard(R)
    a = md.index("| | Kurt | Sam |")
    b = md.index("| Movie | Format wished for")
    c = md.find("\n## ", b)
    rest = "" if c < 0 else md[c + 1:]
    if rest.startswith("## Repeat wishes"):
        k = rest.find("\n## ", 1)
        rest = "" if k < 0 else rest[k + 1:]
    head = md[:a]
    if checked:
        head = re.sub(r"Release status checked [^.\n]+\.", f"Release status checked {checked}.", head)
    body = ("\n".join(table) + "\n\n" + "\n".join(bullets) + "\n\n" + "\n".join(main_table(R)) + "\n\n## Repeat wishes 🔔\n\n"
            "Shame! Each of these had already been wished for on the show.\n\n" + "\n".join(repeat_table(R)) + "\n\n" + rest)
    path.write_text(head + body, encoding="utf-8")


# ---------------------------------------------------------------- site data

def write_site_data(R, checked):
    tmdb = load("tmdb.json")
    out = []
    for r in R:
        movie = r["movie"]
        films = [] if movie in NO_FILM_LINK else [f for f in tmdb.get(movie, []) if f.get("id")]
        segs, pos = [], 0
        if len(films) > 1:      # link each film inside a multi-film wish separately
            for i, f in enumerate(films):
                j = movie.find(f["q"], pos)
                if j < 0:
                    segs = []
                    break
                k = j + len(f["q"])
                m = re.match(r" \(\d{4}\)", movie[k:])
                if m:
                    k += m.end()
                if j > pos:
                    segs.append([movie[pos:j], None])
                segs.append([movie[j:k], i])
                pos = k
            if segs and pos < len(movie):
                segs.append([movie[pos:], None])
        if not segs:
            segs = [[movie, 0 if films else None]]
        d = dict(repeat=r["repeat"], ep=r["code"], epn=r["ep"], epTitle=r["e"]["title"], date=r["e"]["date"], vid=r["e"]["vid"], t=r["e"].get("t", 0),
                 who=r["who"], guest=r["guest"], confirmed=r.get("confirmed", True), movie=movie, segs=segs,
                 films=[dict(title=f["title"], year=f["year"], kind=f["kind"], id=f["id"], poster=f.get("poster")) for f in films],
                 fmt=r["fmt"], status=r["status"], detail=r["detail"] if r["status"] != "listed" else r["detail"],
                 pub=r["pub"], label=r["label"] or "none", labelText="" if r["lab"] == "—" else r["lab"], urls=r["urls"],
                 released=r["released"] if r["status"] in ("yes", "announced", "partly") else None, notes="; ".join(r["notes"]))
        if r["repeat"] and r.get("first"):
            f = r["first"]
            d["first"] = dict(who=f["who"], ep=f["code"], date=f["e"]["date"], vid=f["e"]["vid"], t=f["e"].get("t", 0), fmt=f["fmt"])
        out.append(d)
    (ROOT / "docs" / "data.json").write_text(json.dumps(dict(checked=checked, rows=out), indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def build_all(checked=None):
    """Regenerate wishes.md, docs/data.json and docs/index.html from data/."""
    import subprocess
    import sys
    state = load("state.json") if (DATA / "state.json").exists() else {}
    checked = checked or state.get("checked") or datetime.date.today().isoformat()
    R = rows()
    pretty = datetime.date.fromisoformat(checked).strftime("%-d %b %Y")
    write_markdown(R, pretty)
    write_site_data(R, checked)
    subprocess.run([sys.executable, str(ROOT / "tools" / "build_site.py")], check=True)
    return R
