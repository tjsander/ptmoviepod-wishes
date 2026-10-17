#!/usr/bin/env python3
"""Confirm (or correct) who made recently transcribed wishes, then rebuild and publish.

Paste the results box from confirm/index.html on standard input, one wish per line:

    S3E08 | Film Title (2001) | Sam

or confirm everything from an episode as transcribed:

    python3 tools/confirm.py --ok S3E08
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import update  # noqa: E402
import wishlib  # noqa: E402
from wishlib import load, save  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--ok", metavar="EPISODE", help="confirm every wish in this episode as transcribed, e.g. S3E08")
ap.add_argument("--no-publish", action="store_true")
a = ap.parse_args()

codes = {wishlib.ep_code(e): e["n"] for e in load("episodes.json")}
wishes = load("wishes.json")
regulars = {"Kurt", "Sam", "Bobby", "Kimberly"}
changed = 0
if a.ok:
    for w in wishes:
        if w["ep"] == codes[a.ok] and not w.get("confirmed", True):
            w["confirmed"] = True
            changed += 1
else:
    for line in sys.stdin:
        parts = [x.strip() for x in line.split(" | ")]
        if len(parts) != 3:
            continue
        code, movie, who = parts
        hits = [w for w in wishes if w["ep"] == codes.get(code) and w["movie"] == movie]
        if not hits:
            print("no such wish:", line.strip())
            continue
        if who.lower() == "not sure":
            continue
        for w in hits:
            if w["who"] != who:
                print(f"{code} {movie}: {w['who']} → {who}")
            w["who"], w["guest"], w["confirmed"] = who, who not in regulars, True
            changed += 1
print(changed, "wishes confirmed")
if changed:
    save("wishes.json", wishes)
    wishlib.build_all()
    if not a.no_publish:
        update.publish([], [])
        # close the review issue for any episode whose wishes are now all confirmed
        for code, n in codes.items():
            if any(w["ep"] == n for w in wishes) and all(w.get("confirmed", True) for w in wishes if w["ep"] == n):
                for num in update.run(["gh", "issue", "list", "--state", "open", "--search", f'"Review: new wishes from {code}" in:title',
                                       "--json", "number", "--jq", ".[].number"], cwd=wishlib.ROOT).stdout.split():
                    update.run(["gh", "issue", "close", num, "--comment", f"All {code} wishes confirmed."], cwd=wishlib.ROOT)
                    print(f"closed issue #{num}")
