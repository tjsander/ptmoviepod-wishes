# Wishes in the Physical Media Universe

Every disc wished for at the end of [Physical Therapy: A Movie Podcast](https://linktr.ee/ptmoviepod), and whether the wish came true.

- **Site:** `docs/` (GitHub Pages serves this folder). `docs/index.html` is a single self-contained page.
- **Table:** [`wishes.md`](wishes.md) has the same data as Markdown.
- **Data:** `data/` is the source of truth; everything else is generated from it.

## How it updates

`tools/update.py` runs daily from a systemd user timer:

1. Checks the podcast feed for a new episode.
2. Fetches the YouTube captions, finds the wish segment and asks Claude (`claude -p`) to transcribe the wishes.
3. About weekly, re-checks Blu-ray.com listings for every wish that hasn't come true.
4. Rebuilds `wishes.md` and the site, commits, pushes, and opens an issue asking for a review.

New wishes are published straight away, marked "unconfirmed". To confirm who made them, open `confirm/index.html`
(audio clips, generated locally), then run `python3 tools/confirm.py` and paste the results.

## Doing things by hand

| To | Run |
|---|---|
| Rebuild everything from `data/` | `python3 tools/update.py --skip-releases --no-publish` |
| Force a Blu-ray.com check | `python3 tools/update.py --releases` |
| See what would happen, changing nothing | `python3 tools/update.py --dry-run` |
| Confirm an episode as transcribed | `python3 tools/confirm.py --ok S3E08` |

Fix a wrong title, format or wisher by editing `data/wishes.json`; fix a release status in `data/outcomes.json`
(set `"manual": true` to stop the checker changing it). The headings and the "About the table" notes in `wishes.md`
are hand-written and preserved; the leader board and tables are regenerated.

Needs `yt-dlp`, `ffmpeg`, `curl`, `gh` and `claude` on the path, and a TMDB API token in `~/.config/mmboxmonkey/tmdb-token`
or the `TMDB_TOKEN` environment variable (used only to look up posters for new films; it is never written to the site or
the repository). Without a token everything still runs, but new films get no poster or Letterboxd link.

An unofficial fan project. This product uses the TMDB API but is not endorsed or certified by TMDB.
