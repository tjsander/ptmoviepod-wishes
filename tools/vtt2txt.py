#!/usr/bin/env python3
"""Convert YouTube auto-caption .vtt files into clean, timestamped text.

Usage: vtt2txt.py <vtt_dir> <out_dir>

YouTube's auto captions repeat each line across rolling cues; this keeps each
spoken line once and groups them into ~30 second paragraphs, each prefixed
with its [h:mm:ss] start time so a search hit can be traced back to the video.
"""
import html
import re
import sys
from pathlib import Path

CUE = re.compile(r"^(\d+):(\d\d):(\d\d)\.\d+ --> ")
TAG = re.compile(r"<[^>]+>")
PARAGRAPH_SECONDS = 30


def lines_with_times(vtt_text):
    start = None
    last = None
    for raw in vtt_text.splitlines():
        m = CUE.match(raw)
        if m:
            h, mi, s = map(int, m.groups())
            start = h * 3600 + mi * 60 + s
            continue
        if start is None:
            continue
        line = html.unescape(TAG.sub("", raw)).strip()
        if not line or line == last:
            continue
        last = line
        yield start, line


def convert(vtt_path):
    out = []
    para_start = None
    words = []
    for start, line in lines_with_times(vtt_path.read_text(encoding="utf-8")):
        if para_start is None:
            para_start = start
        elif start - para_start >= PARAGRAPH_SECONDS:
            out.append(format_paragraph(para_start, words))
            para_start, words = start, []
        words.append(line)
    if words:
        out.append(format_paragraph(para_start, words))
    return "\n".join(out) + "\n"


def format_paragraph(start, words):
    h, rem = divmod(start, 3600)
    m, s = divmod(rem, 60)
    return f"[{h}:{m:02d}:{s:02d}] {' '.join(words)}"


def main():
    vtt_dir, out_dir = Path(sys.argv[1]), Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for vtt in sorted(vtt_dir.glob("*.vtt")):
        name = re.sub(r"\.en(-orig)?$", "", vtt.stem)
        (out_dir / f"{name}.txt").write_text(convert(vtt), encoding="utf-8")
        count += 1
    print(f"converted {count} files into {out_dir}")


if __name__ == "__main__":
    main()
