"""Release announcements from Disc Connected on Bluesky (public API, no login needed).

Posts look like:  "***ANNOUNCEMENT*** Coming on January 26th on Blu-ray in the US from @criterion.bsky.social: #Chocolat (1988)!"
"""
import datetime
import json
import re
import urllib.parse
import urllib.request

ACTOR = "disc-connected.bsky.social"
API = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december".split(), 1)}
PUBLISHERS = {
    "criterion": "Criterion", "20thcentury": "20th Century Studios", "warnerarchive": "Warner Archive", "shoutstudios": "Shout! Factory",
    "discotek": "Discotek Media", "wellgo": "Well Go USA", "kinolorber.com": "Kino Lorber", "arrowvideo": "Arrow Video", "shoutfactory": "Shout! Factory",
    "scream-factory": "Shout! Factory", "vinegarsyndrome": "Vinegar Syndrome", "severin": "Severin Films", "lionsgate": "Lionsgate",
    "paramount": "Paramount", "warnerbros": "Warner Bros.", "sonypictures": "Sony Pictures", "universal": "Universal",
    "disney": "Disney", "mgm": "MGM", "24": "A24", "a24": "A24", "neon": "Neon", "kls": "Kino Lorber", "synapse": "Synapse Films",
}
LINE = re.compile(
    r"Coming\s+(?P<when>on\s+\w+\s+\d+\w*|at the end of\s+\w+|in\s+\w+|soon|early\s+\w+|mid[- ]\w+|late\s+\w+)\s+on\s+(?P<fmt>.+?)\s+in the\s+(?P<region>[A-Z]{2,3})\s+from\s+(?P<pub>\S+?):\s+(?P<title>.+?)!\s",
    re.S)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("&", "and"))


def publisher(handle):
    h = handle.lstrip("@#").lower().removesuffix(".bsky.social")
    for k, v in PUBLISHERS.items():
        if h.startswith(k):
            return v
    words = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", handle.lstrip("@#").split(".")[0]).split()
    return " ".join(w[0].upper() + w[1:] for w in words)


def release_date(when, posted):
    """Concrete date for 'on January 26th' (the next one after the post); end-of-month for 'at the end of November'; else None."""
    m = re.match(r"on\s+(\w+)\s+(\d+)", when)
    if m and m.group(1).lower() in MONTHS:
        mo, day = MONTHS[m.group(1).lower()], int(m.group(2))
        for y in (posted.year, posted.year + 1):
            try:
                d = datetime.date(y, mo, day)
            except ValueError:
                return None
            if d >= posted - datetime.timedelta(days=7):
                return d.isoformat()
    return None


def parse(post):
    """One announcement dict from a post, or None if it isn't a US 'Coming on …' announcement."""
    text = post["record"]["text"] + " "
    m = LINE.search(text)
    if not m or m.group("region") != "US":
        return None
    posted = datetime.datetime.fromisoformat(post["indexedAt"].replace("Z", "+00:00")).date()
    fmt = m.group("fmt")
    ym = re.search(r"\((\d{4})(?:/\d{4})?\)\s*$", m.group("title").strip())
    uri = post["uri"]
    return dict(
        title=m.group("title").strip(), year=int(ym.group(1)) if ym else None,
        uhd="4K" in fmt, fmt=fmt, pub=publisher(m.group("pub")), iso=release_date(m.group("when"), posted),
        when=m.group("when"), posted=post["indexedAt"],
        url=f"https://bsky.app/profile/{ACTOR}/post/{uri.rsplit('/', 1)[-1]}")


def fetch_since(since_iso, max_pages=10):
    """Announcements posted after `since_iso` (an ISO timestamp), oldest first, plus the newest timestamp seen."""
    out, cursor, newest = [], None, since_iso
    for _ in range(max_pages):
        q = dict(actor=ACTOR, limit=100, filter="posts_no_replies")
        if cursor:
            q["cursor"] = cursor
        with urllib.request.urlopen(f"{API}?{urllib.parse.urlencode(q)}", timeout=30) as r:
            d = json.load(r)
        stop = False
        for item in d["feed"]:
            if "reason" in item:  # reposts
                continue
            p = item["post"]
            if p["indexedAt"] <= since_iso:
                stop = True
                continue
            newest = max(newest, p["indexedAt"])
            a = parse(p)
            if a:
                out.append(a)
        cursor = d.get("cursor")
        if stop or not cursor:
            break
    return sorted(out, key=lambda a: a["posted"]), newest


def matches(announcement, movie):
    """Does this announcement cover the wished-for film 'Title (Year)'?"""
    m = re.match(r"^(.*?)\s*\((\d{4})", movie)
    title, year = (m.group(1), int(m.group(2))) if m else (movie, None)
    t, a = norm(title), norm(re.sub(r"\(\d{4}(/\d{4})?\)", "", announcement["title"]))
    if not t or not (t == a or (len(t) > 8 and t in a)):
        return False
    return not (year and announcement["year"] and abs(announcement["year"] - year) > 1)
