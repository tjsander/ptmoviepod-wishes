#!/usr/bin/env python3
"""Build docs/index.html (a single self-contained page for GitHub Pages).

Usage: python3 tools/build_site.py

Reads docs/data.json (the wish list with outcomes, release links and TMDB ids)
and the "Leader board" section of wishes.md, and writes docs/index.html.
No network access or API key is needed; posters are loaded by the browser
from TMDB's image CDN when a title is hovered.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
data = json.loads((ROOT / "docs" / "data.json").read_text(encoding="utf-8"))
md = (ROOT / "wishes.md").read_text(encoding="utf-8").split("\n")


def inline(text):
    """Escape text and turn **bold** into <strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html.escape(text, quote=False))


def leaderboard():
    start = next(i for i, line in enumerate(md) if line.strip().lower().startswith("## leader"))
    end = next(i for i, line in enumerate(md) if line.startswith("| Movie | Format wished for"))
    table, bullets = [], []
    for line in md[start + 1:end]:
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if not all(re.fullmatch(r"-+", c) for c in cells):
                table.append(cells)
        elif line.startswith("- "):
            bullets.append(line[2:])
    head, body = table[0], table[1:]
    out = ['<div class="scroll"><table class="board"><thead><tr>']
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        egg = ' class="egg" tabindex="0"' if row[0].lower().startswith("longest wait") else ""
        out.append("<tr>" + f'<th scope="row"{egg}>{inline(row[0])}</th>' + "".join(f"<td>{inline(c)}</td>" for c in row[1:]) + "</tr>")
    out.append("</tbody></table></div>")
    if bullets:
        out.append('<ul class="facts">' + "".join(f"<li>{inline(b)}</li>" for b in bullets) + "</ul>")
    return "\n".join(out)


title = next((line[2:].strip() for line in md if line.startswith("# ")), "Wishes into the Physical Media Universe")
payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ · Physical Therapy: A Movie Podcast wish list</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__URL__">
<meta property="og:type" content="website">
<meta property="og:site_name" content="__TITLE__">
<meta property="og:title" content="__TITLE__ · Physical Therapy: A Movie Podcast">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__URL__">
<meta property="og:image" content="__URL__card.png">
<meta name="twitter:card" content="summary_large_image">
<script type="application/ld+json">__JSONLD__</script>
<style>
:root {
  --bg: #f4f1ea; --card: #fffdf8; --ink: #1c1b19; --mute: #6b665c; --line: #ddd6c8; --accent: #9a3b1f; --head: #ebe5d8;
  --yes: #1f7a4d; --yes-bg: #dff1e6; --ann: #1d5fa8; --ann-bg: #dfeaf8; --lst: #8a5a00; --lst-bg: #f8ecc9; --par: #6a3fa0; --par-bg: #ece2f7; --no: #6b665c; --no-bg: #e9e5db;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15161a; --card: #1d1f24; --ink: #ecebe7; --mute: #9d9a92; --line: #33363d; --accent: #f0a37f; --head: #24272d;
    --yes: #7fd6a4; --yes-bg: #173526; --ann: #8fbcf2; --ann-bg: #162b45; --lst: #e8c36a; --lst-bg: #3a2e10; --par: #c6a6ee; --par-bg: #2c2040; --no: #9d9a92; --no-bg: #2a2c31;
  }
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--accent); text-underline-offset: 2px; }
main { max-width: 1180px; margin: 0 auto; padding: 32px 16px 64px; }
header h1 { font: 700 clamp(1.7rem, 4.5vw, 2.6rem)/1.15 Georgia, "Times New Roman", serif; margin: 0 0 6px; letter-spacing: -0.01em; }
header p { margin: 0; color: var(--mute); }
h2 { font: 700 1.25rem/1.2 Georgia, serif; margin: 0; display: inline; }
details.sec { margin-top: 32px; }
details.sec > summary { cursor: pointer; padding: 6px 0 10px; list-style-position: outside; margin-left: 1.1em; color: var(--mute); }
details.sec > summary h2 { color: var(--ink); }
details.sec > summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
details.sec:not([open]) { border-bottom: 1px solid var(--line); }
.scroll { overflow-x: auto; border: 1px solid var(--line); border-radius: 10px; background: var(--card); }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; vertical-align: top; padding: 9px 12px; border-bottom: 1px solid var(--line); }
tbody tr:last-child > * { border-bottom: 0; }
thead th { background: var(--head); font-size: .8rem; text-transform: uppercase; letter-spacing: .05em; color: var(--mute); white-space: nowrap; }
.board th[scope=row] { font-weight: 600; min-width: 190px; }
.board td { font-variant-numeric: tabular-nums; min-width: 110px; }
.facts { color: var(--mute); padding-left: 20px; margin: 14px 0 0; font-size: .95rem; }
.facts strong { color: var(--ink); }
.controls { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 0 0 12px; }
.controls input[type=search], .controls select { font: inherit; color: var(--ink); background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; }
.controls input[type=search] { flex: 1 1 220px; min-width: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font: inherit; font-size: .88rem; cursor: pointer; border: 1px solid var(--line); background: var(--card); color: var(--ink); border-radius: 999px; padding: 5px 12px; }
.chip[aria-pressed=true] { background: var(--ink); color: var(--bg); border-color: var(--ink); }
.count { color: var(--mute); font-size: .9rem; margin: 0 0 8px; }
#wishes thead th button { all: unset; cursor: pointer; }
#wishes thead th button:focus-visible, .chip:focus-visible, a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
#wishes thead th[aria-sort=ascending] button::after { content: " ▲"; }
#wishes thead th[aria-sort=descending] button::after { content: " ▼"; }
.movie { font-weight: 600; }
.movie a { color: inherit; text-decoration-color: var(--line); }
.movie a:hover { color: var(--accent); text-decoration-color: currentColor; }
.note, .sub { display: block; color: var(--mute); font-size: .85rem; font-weight: 400; }
.pill { display: inline-block; font-size: .78rem; font-weight: 700; letter-spacing: .03em; text-transform: uppercase; border-radius: 999px; padding: 2px 9px; white-space: nowrap; }
.s-yes { color: var(--yes); background: var(--yes-bg); } .s-announced { color: var(--ann); background: var(--ann-bg); }
.s-listed { color: var(--lst); background: var(--lst-bg); } .s-partly { color: var(--par); background: var(--par-bg); } .s-no { color: var(--no); background: var(--no-bg); }
.ep { white-space: nowrap; font-variant-numeric: tabular-nums; }
#poster { position: fixed; z-index: 10; width: 190px; pointer-events: none; display: none; border-radius: 8px; overflow: hidden; background: var(--head); box-shadow: 0 10px 30px rgba(0, 0, 0, .35); border: 1px solid var(--line); }
#poster img { display: block; width: 100%; aspect-ratio: 2 / 3; object-fit: cover; }
.egg { cursor: default; }
#egg { position: fixed; z-index: 11; width: 260px; pointer-events: none; display: none; border-radius: 8px; overflow: hidden; background: var(--head); box-shadow: 0 10px 30px rgba(0, 0, 0, .35); border: 1px solid var(--line); }
#egg img { display: block; width: 100%; aspect-ratio: 1; object-fit: cover; }
#egg span { display: block; padding: 3px 8px; font-size: .7rem; color: var(--mute); text-align: right; }
.about p { margin: 0 0 10px; max-width: 78ch; }
.listen a { font-weight: 600; }
footer { margin-top: 40px; color: var(--mute); font-size: .88rem; }
footer p { margin: 0 0 8px; }
.tmdb img { height: 24px; width: auto; vertical-align: middle; margin-right: 10px; }
@media (max-width: 760px) {
  .cards thead { display: none; }
  .cards, .cards tbody, .cards tr, .cards td { display: block; width: 100%; }
  .cards tr { padding: 10px 12px; border-bottom: 1px solid var(--line); }
  .cards tbody tr:last-child { border-bottom: 0; }
  .cards td { padding: 2px 0; border: 0; }
  .cards td[data-l]::before { content: attr(data-l) ": "; color: var(--mute); font-size: .82rem; }
}
</style>
</head>
<body>
<main>
<header>
  <h1>__TITLE__</h1>
  <p>Every disc wished for at the end of <a href="https://linktr.ee/ptmoviepod" target="_blank" rel="noopener"><em>Physical Therapy: A Movie Podcast</em></a>, the show about physical media, film preservation and why owning movies matters, hosted by Kurt and Sam, and whether each wish came true. Release status checked <span id="checked">__CHECKED__</span>.</p>
</header>

<details class="sec" id="sec-wishes" open>
  <summary><h2 id="h-wishes">All wishes</h2></summary>
  <div class="controls">
    <input type="search" id="q" placeholder="Already wished for? Search…" aria-label="Search wishes">
    <select id="who" aria-label="Wished by"><option value="">Everyone</option></select>
    <div class="chips" id="chips" role="group" aria-label="Outcome"></div>
  </div>
  <p class="count" id="count" aria-live="polite"></p>
  <div class="scroll">
    <table id="wishes" class="cards">
      <thead><tr>
        <th data-k="movie"><button type="button">Film</button></th>
        <th data-k="fmt"><button type="button">Wished for</button></th>
        <th data-k="status"><button type="button">Came true?</button></th>
        <th data-k="epn" aria-sort="ascending"><button type="button">Episode</button></th>
        <th data-k="who"><button type="button">Wished by</button></th>
      </tr></thead>
      <tbody id="rows">__ROWS__</tbody>
    </table>
  </div>
</details>

<details class="sec" id="sec-board" open>
  <summary><h2 id="h-board">Leader board</h2></summary>
  __LEADERBOARD__
</details>

<details class="sec" id="sec-repeats" open>
  <summary><h2 id="h-repeats">Repeat wishes 🔔</h2></summary>
  <p class="count">Shame! Each of these had already been wished for on the show, so they are left off the leader board.</p>
  <div class="scroll">
    <table id="repeats" class="cards">
      <thead><tr><th>Film</th><th>Repeated by</th><th>First wished by</th><th>Came true?</th></tr></thead>
      <tbody id="reprows">__REPROWS__</tbody>
    </table>
  </div>
</details>

<details class="sec about" id="sec-about" open>
  <summary><h2 id="h-about">About the show</h2></summary>
  <p><strong>Physical Therapy: A Movie Podcast</strong> (PT Movie Pod) is, in the show's own words, &ldquo;a movie podcast dedicated to physical media, film preservation and why owning movies matters.&rdquo; Hosts Kurt and Sam, with producer Kimberly and regular guests, talk through new 4K UHD and Blu-ray releases, boutique labels such as Arrow Video, Criterion, Kino Lorber and Shout Factory, and the films on their shelves.</p>
  <p>Every episode ends with the hosts &ldquo;putting wishes out into the physical media universe&rdquo;: each names a film they want released on a format it isn't on yet. This page tracks all __NWISHES__ wishes across __NEPS__ episodes, and the __NYES__ that have come true so far.</p>
  <p class="listen">Listen: <a href="https://podcasts.apple.com/us/podcast/physical-therapy-a-movie-podcast/id1736079773" target="_blank" rel="noopener">Apple Podcasts</a> · <a href="https://www.youtube.com/@ptmoviepod" target="_blank" rel="noopener">YouTube</a> · <a href="https://linktr.ee/ptmoviepod" target="_blank" rel="noopener">all links</a> · <a href="https://boxd.it/lR6On" target="_blank" rel="noopener">Letterboxd</a></p>
</details>

<footer>
  <p>Film titles link to Letterboxd; hover a title for its poster. Outcomes link to the release page on Blu-ray.com where one was found. Episode links open YouTube at the wish segment.</p>
  <p>Wishes were collected from YouTube auto-captions, and who made each wish is inferred from the conversation, so some attributions may be wrong. New episodes are transcribed automatically and marked "unconfirmed" until checked by ear. "No" means no US release in the wished format was found on Blu-ray.com.</p>
  <p>Listen to and follow the show: <a href="https://linktr.ee/ptmoviepod" target="_blank" rel="noopener">linktr.ee/ptmoviepod</a>.</p>
  <p>Made by <a href="https://github.com/tjsander" target="_blank" rel="noopener">Travis J. Sanders</a>. An unofficial fan project.</p>
  <p class="tmdb">__TMDB_LOGO__This product uses the TMDB API but is not endorsed or certified by TMDB.</p>
</footer>
</main>
<div id="poster" aria-hidden="true"><img alt=""></div>
<div id="egg" aria-hidden="true"><img alt=""><span>via GIPHY</span></div>
<script id="data" type="application/json">__DATA__</script>
<script>
(function () {
  var D = JSON.parse(document.getElementById('data').textContent), reps = D.rows.filter(function (r) { return r.repeat; }), rows = D.rows.filter(function (r) { return !r.repeat; });
  var LABEL = { yes: 'Yes', announced: 'Announced', listed: 'Not yet', partly: 'Partly', no: 'No' };
  var ORDER = { yes: 0, announced: 1, partly: 2, listed: 3, no: 4 };
  var state = { q: '', who: '', status: '', key: 'epn', dir: 1 };
  var $ = function (id) { return document.getElementById(id); };
  function squash(s) { return s.toLowerCase().replace(/[^a-z0-9]/g, ''); }

  // collapsible sections remember whether they were left open or closed
  var shut = [];
  try { shut = JSON.parse(localStorage.getItem('ptw-collapsed') || '[]'); } catch (e) {}
  [].forEach.call(document.querySelectorAll('details.sec'), function (d) {
    if (shut.indexOf(d.id) >= 0) d.open = false;
    d.addEventListener('toggle', function () {
      var now = [].filter.call(document.querySelectorAll('details.sec'), function (x) { return !x.open; }).map(function (x) { return x.id; });
      try { localStorage.setItem('ptw-collapsed', JSON.stringify(now)); } catch (e) {}
    });
  });
  // "/" jumps to the search box
  document.addEventListener('keydown', function (e) {
    if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey || /^(INPUT|TEXTAREA|SELECT)$/.test(e.target.tagName)) return;
    e.preventDefault(); $('sec-wishes').open = true; $('q').focus();
  });
  function el(tag, attrs, kids) {
    var n = document.createElement(tag), k;
    for (k in attrs || {}) { if (k === 'text') n.textContent = attrs[k]; else if (attrs[k] != null) n.setAttribute(k, attrs[k]); }
    (kids || []).forEach(function (c) { n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); });
    return n;
  }
  function fmtDate(iso) { var d = new Date(iso + 'T00:00:00Z'); return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' }); }
  $('checked').textContent = fmtDate(D.checked);

  // filters
  var people = [], seen = {};
  rows.forEach(function (r) { var w = r.guest ? 'Guests' : r.who; if (!seen[w]) { seen[w] = 1; people.push(w); } });
  ['Kurt', 'Sam', 'Bobby', 'Kimberly', 'Guests'].filter(function (p) { return seen[p]; }).forEach(function (p) { $('who').appendChild(el('option', { value: p, text: p })); });
  [['', 'All'], ['yes', 'Came true'], ['announced', 'Announced'], ['partly', 'Partly'], ['listed', 'Listed, no date'], ['no', 'No']].forEach(function (c) {
    var n = c[0] ? rows.filter(function (r) { return r.status === c[0]; }).length : rows.length;
    var b = el('button', { type: 'button', class: 'chip', 'aria-pressed': c[0] === '' ? 'true' : 'false', 'data-s': c[0], text: c[1] + ' (' + n + ')' });
    b.addEventListener('click', function () { state.status = c[0]; [].forEach.call($('chips').children, function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); }); render(); });
    $('chips').appendChild(b);
  });
  $('q').addEventListener('input', function (e) { state.q = e.target.value.toLowerCase().trim(); render(); });
  $('who').addEventListener('change', function (e) { state.who = e.target.value; render(); });
  [].forEach.call(document.querySelectorAll('#wishes thead th'), function (th) {
    th.querySelector('button').addEventListener('click', function () {
      var k = th.getAttribute('data-k');
      state.dir = state.key === k ? -state.dir : 1; state.key = k;
      [].forEach.call(document.querySelectorAll('#wishes thead th'), function (x) { x.removeAttribute('aria-sort'); });
      th.setAttribute('aria-sort', state.dir === 1 ? 'ascending' : 'descending');
      render();
    });
  });

  // poster popover
  var pop = $('poster'), img = pop.querySelector('img'), wanted = null;
  function showPoster(a, ev) {
    var p = a.getAttribute('data-poster'); if (!p) return;
    var url = 'https://image.tmdb.org/t/p/w342' + p;
    if (wanted !== url) {
      // blank the old poster first so it never shows under the new title
      wanted = url; img.style.visibility = 'hidden'; img.removeAttribute('src');
      var next = new Image();
      next.onload = function () { if (wanted === url) { img.src = url; img.style.visibility = 'visible'; } };
      next.src = url;
    }
    pop.style.display = 'block'; movePoster(a, ev);
  }
  function movePoster(a, ev) {
    var w = 190, h = 285, x, y, r;
    if (ev && ev.clientX != null && ev.type !== 'focus') { x = ev.clientX + 18; y = ev.clientY - h / 2; }
    else { r = a.getBoundingClientRect(); x = r.right + 12; y = r.top - h / 2 + r.height / 2; }
    if (x + w > window.innerWidth - 8) x = Math.max(8, (ev && ev.clientX != null && ev.type !== 'focus' ? ev.clientX : a.getBoundingClientRect().left) - w - 18);
    y = Math.max(8, Math.min(y, window.innerHeight - h - 8));
    pop.style.left = x + 'px'; pop.style.top = y + 'px';
  }
  function hidePoster() { pop.style.display = 'none'; wanted = null; img.style.visibility = 'hidden'; img.removeAttribute('src'); }
  function filmLink(text, f) {
    var href = f.kind === 'movie' ? 'https://letterboxd.com/tmdb/' + f.id + '/' : 'https://www.themoviedb.org/tv/' + f.id;
    var a = el('a', { href: href, target: '_blank', rel: 'noopener', 'data-poster': f.poster, title: f.kind === 'movie' ? 'Open on Letterboxd' : 'Open on TMDB (TV series)', text: text });
    a.addEventListener('mouseenter', function (e) { showPoster(a, e); });
    a.addEventListener('mousemove', function (e) { movePoster(a, e); });
    a.addEventListener('mouseleave', hidePoster);
    a.addEventListener('focus', function (e) { showPoster(a, e); });
    a.addEventListener('blur', hidePoster);
    return a;
  }
  window.addEventListener('scroll', hidePoster, { passive: true });

  // easter egg: a GIF on the "Longest wait" row of the leader board
  var egg = $('egg'), eggImg = egg.querySelector('img');
  function showEgg(th, ev) {
    if (!eggImg.getAttribute('src')) eggImg.src = 'https://media.giphy.com/media/FoH28ucxZFJZu/giphy.gif';
    egg.style.display = 'block';
    var w = 260, h = 285, r = th.getBoundingClientRect();
    var x = ev && ev.clientX != null && ev.type !== 'focus' ? ev.clientX + 18 : r.left + 24;
    var y = ev && ev.clientY != null && ev.type !== 'focus' ? ev.clientY - h - 12 : r.top - h - 8;
    if (x + w > window.innerWidth - 8) x = window.innerWidth - w - 8;
    if (y < 8) y = Math.min(window.innerHeight - h - 8, r.bottom + 8);
    egg.style.left = Math.max(8, x) + 'px'; egg.style.top = y + 'px';
  }
  function hideEgg() { egg.style.display = 'none'; }
  [].forEach.call(document.querySelectorAll('.egg'), function (th) {
    th.addEventListener('mouseenter', function (e) { showEgg(th, e); });
    th.addEventListener('mousemove', function (e) { showEgg(th, e); });
    th.addEventListener('mouseleave', hideEgg);
    th.addEventListener('focus', function (e) { showEgg(th, e); });
    th.addEventListener('blur', hideEgg);
  });
  window.addEventListener('scroll', hideEgg, { passive: true });

  function movieCell(r) {
    var movie = el('td', { class: 'movie' });
    r.segs.forEach(function (s) { movie.appendChild(s[1] == null || !r.films[s[1]] ? document.createTextNode(s[0]) : filmLink(s[0], r.films[s[1]])); });
    if (r.notes) movie.appendChild(el('span', { class: 'note', text: r.notes }));
    return movie;
  }
  function epLink(x) { return el('a', { class: 'ep', href: 'https://www.youtube.com/watch?v=' + x.vid + (x.t ? '&t=' + x.t + 's' : ''), target: '_blank', rel: 'noopener', text: x.ep }); }
  function outcomeCell(r) {
    var out = el('td', { 'data-l': 'Came true' }, [el('span', { class: 'pill s-' + r.status, text: LABEL[r.status] })]);
    var bits = [];
    if (r.status === 'listed') bits.push((r.detail || '').replace(' listed with no date', '') + ' listed with no date');
    else if (r.detail) bits.push(r.detail);
    if (r.pub) bits.push(r.pub);
    if (bits.length) {
      var d = el('span', { class: 'sub' });
      if (r.urls.length) {
        d.appendChild(el('a', { href: r.urls[0], target: '_blank', rel: 'noopener', text: bits.join(' · ') }));
        r.urls.slice(1).forEach(function (u, i) { d.appendChild(document.createTextNode(' ')); d.appendChild(el('a', { href: u, target: '_blank', rel: 'noopener', text: '[' + (i + 2) + ']' })); });
      } else d.textContent = bits.join(' · ');
      out.appendChild(d);
    }
    if (r.label === 'yes') out.appendChild(el('span', { class: 'sub', text: 'From the label they asked for' }));
    if (r.label === 'no') out.appendChild(el('span', { class: 'sub', text: 'Not the label they asked for' }));
    return out;
  }
  function rowNode(r) {
    var ep = el('td', { 'data-l': 'Episode' }, [epLink(r), el('span', { class: 'sub', text: r.epTitle + ' · ' + fmtDate(r.date) })]);
    return el('tr', {}, [movieCell(r), el('td', { 'data-l': 'Wished for', text: r.fmt }), outcomeCell(r), ep, el('td', { 'data-l': 'Wished by' }, [r.who + (r.guest ? ' (guest)' : '')].concat(r.confirmed === false ? [el('span', { class: 'sub', text: 'unconfirmed' })] : []))]);
  }
  function repNode(r) {
    var again = el('td', { 'data-l': 'Repeated by' }, [r.who + ' · ', epLink(r), el('span', { class: 'sub', text: fmtDate(r.date) + ' · asked for: ' + r.fmt })]);
    var first = el('td', { 'data-l': 'First wished by' }, [r.first.who + ' · ', epLink(r.first), el('span', { class: 'sub', text: fmtDate(r.first.date) + ' · asked for: ' + r.first.fmt })]);
    return el('tr', {}, [movieCell(r), again, first, outcomeCell(r)]);
  }
  $('reprows').textContent = '';
  reps.forEach(function (r) { $('reprows').appendChild(repNode(r)); });
  function sortVal(r, k) {
    if (k === 'status') return ORDER[r.status];
    if (k === 'movie') return r.movie.replace(/^(the|a|an) /i, '').toLowerCase();
    if (k === 'epn') return r.epn;
    return String(r[k]).toLowerCase();
  }
  function render() {
    var list = rows.filter(function (r) {
      if (state.status && r.status !== state.status) return false;
      if (state.who && (r.guest ? 'Guests' : r.who) !== state.who) return false;
      if (state.q) {
        var hay = [r.movie, r.fmt, r.who, r.ep, r.epTitle, r.detail, r.pub || '', r.notes].join(' ').toLowerCase();
        if (hay.indexOf(state.q) < 0 && (!squash(state.q) || squash(hay).indexOf(squash(state.q)) < 0)) return false;
      }
      return true;
    });
    list.sort(function (a, b) {
      var x = sortVal(a, state.key), y = sortVal(b, state.key);
      if (x < y) return -state.dir; if (x > y) return state.dir;
      return rows.indexOf(a) - rows.indexOf(b);
    });
    var tb = $('rows'), frag = document.createDocumentFragment();
    list.forEach(function (r) { frag.appendChild(rowNode(r)); });
    tb.textContent = ''; tb.appendChild(frag);
    $('count').textContent = list.length === rows.length ? rows.length + ' wishes'
      : list.length ? list.length + ' of ' + rows.length + ' wishes'
      : state.q ? 'No wish matches “' + $('q').value.trim() + '”. Nobody has wished for that yet.' : 'No wishes match these filters.';
  }
  render();
})();
</script>
</body>
</html>
"""

# TMDB's terms ask for their logo next to the notice. Save an approved logo from
# https://www.themoviedb.org/about/logos-attribution as tools/tmdb-logo-short.svg (or tools/tmdb-logo.svg) and it is inlined here, unaltered.
logo_file = next((f for f in (ROOT / "tools" / "tmdb-logo-short.svg", ROOT / "tools" / "tmdb-logo.svg") if f.exists()), None)
if logo_file:
    import base64
    logo = ('<a href="https://www.themoviedb.org/" target="_blank" rel="noopener"><img alt="TMDB" src="data:image/svg+xml;base64,'
            + base64.b64encode(logo_file.read_bytes()).decode() + '"></a>')
else:
    logo = ""
    print("note: no TMDB logo file found in tools/, so the footer has the TMDB notice but no logo")
SITE_URL = "https://tjsander.github.io/ptmoviepod-wishes/"
LABEL = {"yes": "Yes", "announced": "Announced", "listed": "Not yet", "partly": "Partly", "no": "No"}
esc = lambda s: html.escape(str(s), quote=True)


def pretty(iso):
    import datetime
    return datetime.date.fromisoformat(iso).strftime("%-d %b %Y")


def yt(x):
    return f'https://www.youtube.com/watch?v={x["vid"]}' + (f'&amp;t={x["t"]}s' if x.get("t") else "")


def film_cell(r):
    out = []
    for text, i in r["segs"]:
        f = r["films"][i] if i is not None and i < len(r["films"]) else None
        if f:
            href = f'https://letterboxd.com/tmdb/{f["id"]}/' if f["kind"] == "movie" else f'https://www.themoviedb.org/tv/{f["id"]}'
            out.append(f'<a href="{href}">{esc(text)}</a>')
        else:
            out.append(esc(text))
    note = f'<span class="note">{esc(r["notes"])}</span>' if r["notes"] else ""
    return f'<td class="movie">{"".join(out)}{note}</td>'


def outcome_cell(r):
    bits = []
    if r["status"] == "listed":
        bits.append(r["detail"] + " listed with no date")
    elif r["detail"]:
        bits.append(r["detail"])
    if r["pub"]:
        bits.append(r["pub"])
    sub = " · ".join(bits)
    if sub and r["urls"]:
        sub = f'<a href="{esc(r["urls"][0])}">{esc(sub)}</a>'
    else:
        sub = esc(sub)
    return f'<td data-l="Came true"><span class="pill s-{r["status"]}">{LABEL[r["status"]]}</span>' + (f'<span class="sub">{sub}</span>' if sub else "") + "</td>"


def who_text(r):
    return esc(r["who"]) + (" (guest)" if r["guest"] else "")


def row_html(r):
    return (f'<tr>{film_cell(r)}<td data-l="Wished for">{esc(r["fmt"])}</td>{outcome_cell(r)}'
            f'<td data-l="Episode"><a class="ep" href="{yt(r)}">{r["ep"]}</a><span class="sub">{esc(r["epTitle"])} · {pretty(r["date"])}</span></td>'
            f'<td data-l="Wished by">{who_text(r)}</td></tr>')


def repeat_html(r):
    f = r["first"]
    return (f'<tr>{film_cell(r)}<td data-l="Repeated by">{who_text(r)} · <a class="ep" href="{yt(r)}">{r["ep"]}</a><span class="sub">{pretty(r["date"])} · asked for: {esc(r["fmt"])}</span></td>'
            f'<td data-l="First wished by">{esc(f["who"])} · <a class="ep" href="{yt(f)}">{f["ep"]}</a><span class="sub">{pretty(f["date"])} · asked for: {esc(f["fmt"])}</span></td>{outcome_cell(r)}</tr>')


main_rows = [r for r in data["rows"] if not r["repeat"]]
repeat_rows = [r for r in data["rows"] if r["repeat"] and r.get("first")]
n_yes = sum(r["status"] == "yes" for r in main_rows)
desc = (f"Every 4K and Blu-ray release wished for on Physical Therapy: A Movie Podcast, the physical media podcast hosted by Kurt and Sam: "
        f"{len(main_rows)} wishes, {n_yes} granted so far, with links to each release.")
jsonld = json.dumps({"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "@id": SITE_URL + "#site", "url": SITE_URL, "name": title, "description": desc, "inLanguage": "en",
     "author": {"@type": "Person", "name": "Travis J. Sanders", "url": "https://github.com/tjsander"}, "about": {"@id": SITE_URL + "#podcast"}},
    {"@type": "PodcastSeries", "@id": SITE_URL + "#podcast", "name": "Physical Therapy: A Movie Podcast", "alternateName": ["PT Movie Pod", "ptmoviepod"],
     "description": "A movie podcast dedicated to physical media, film preservation and why owning movies matters.",
     "url": "https://linktr.ee/ptmoviepod", "webFeed": "https://feed.podbean.com/ptmoviepod/feed.xml", "genre": ["Film", "Physical media", "Blu-ray", "4K UHD"],
     "sameAs": ["https://podcasts.apple.com/us/podcast/physical-therapy-a-movie-podcast/id1736079773", "https://www.youtube.com/@ptmoviepod", "https://boxd.it/lR6On"]}]},
    ensure_ascii=False).replace("</", "<\\/")

PAGE = (PAGE.replace("__ROWS__", "".join(row_html(r) for r in main_rows)).replace("__REPROWS__", "".join(repeat_html(r) for r in repeat_rows))
        .replace("__DESC__", esc(desc)).replace("__URL__", SITE_URL).replace("__JSONLD__", jsonld).replace("__CHECKED__", pretty(data["checked"]))
        .replace("__NWISHES__", str(len(main_rows))).replace("__NEPS__", str(len({r["ep"] for r in data["rows"]}))).replace("__NYES__", str(n_yes)))
(ROOT / "docs" / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
(ROOT / "docs" / "sitemap.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                           f'  <url><loc>{SITE_URL}</loc><lastmod>{data["checked"]}</lastmod></url>\n</urlset>\n', encoding="utf-8")
(ROOT / "docs" / "llms.txt").write_text(
    f"# {title}\n\n> A fan-made tracker of every physical media wish made on Physical Therapy: A Movie Podcast (PT Movie Pod), and whether each has come true.\n\n"
    "Physical Therapy: A Movie Podcast is a movie podcast dedicated to physical media, film preservation and why owning movies matters. "
    "It is hosted by Kurt and Sam, produced by Kimberly, and covers 4K UHD and Blu-ray releases and boutique labels such as Arrow Video, Criterion, Kino Lorber and Shout Factory. "
    "Each episode ends with the hosts wishing for a film to be released on a format it is not yet available on.\n\n"
    f"This site lists {len(main_rows)} wishes from {len({r['ep'] for r in data['rows']})} episodes; {n_yes} have come true. Release status was last checked on {data['checked']}.\n\n"
    "## Links\n\n"
    f"- [The wish list]({SITE_URL}): the full table with outcomes and release links\n"
    f"- [Data as JSON]({SITE_URL}data.json): every wish with film, format, wisher, episode and release status\n"
    "- [Listen to the podcast](https://linktr.ee/ptmoviepod): all platforms\n"
    "- [Apple Podcasts](https://podcasts.apple.com/us/podcast/physical-therapy-a-movie-podcast/id1736079773)\n"
    "- [YouTube](https://www.youtube.com/@ptmoviepod)\n", encoding="utf-8")
page = PAGE.replace("__TMDB_LOGO__", logo).replace("__TITLE__", html.escape(title)).replace("__LEADERBOARD__", leaderboard()).replace("__DATA__", payload)
(ROOT / "docs" / "index.html").write_text(page, encoding="utf-8")
(ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")
print(f"wrote docs/index.html ({len(page) // 1024} KB, {len(data['rows'])} wishes)")
