"""kite://start, the local new-tab page. No network requests; everything is inline."""
import html
import json
import re
from urllib.parse import urlparse

from settings import is_hex_color
from themes import PRESETS

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><title>New tab</title>
<style>
:root { --top:%(dark_top)s; --bottom:%(dark_bottom)s; --ink:%(dark_ink)s; --field:rgba(255,255,255,.07);
  --line:rgba(255,255,255,.13); --accent:%(accent)s; color-scheme:dark; }
@media (prefers-color-scheme: light) {
  :root { --top:%(light_top)s; --bottom:%(light_bottom)s; --ink:%(light_ink)s; --field:rgba(255,255,255,.78);
    --line:rgba(26,31,61,.14); color-scheme:light; } }
:root { --muted:color-mix(in srgb, var(--ink) 62%%, transparent); }
html, body { height:100%%; margin:0; }
body { background:%(background)s; color:var(--ink);
  font:16px/1.5 "Adwaita Sans", Inter, system-ui, sans-serif; overflow:hidden; }
.line { position:fixed; inset:0; width:100%%; height:100%%; pointer-events:none; }
.line path { fill:none; stroke:var(--muted); stroke-width:1.3; opacity:.55; vector-effect:non-scaling-stroke; }
.kite { position:fixed; left:calc(76vw - 60px); top:calc(24vh - 160px); width:120px; height:160px;
  transform-origin:60px 160px; animation:drift 7s ease-in-out infinite alternate; }
@keyframes drift { from { transform:rotate(-5deg); } to { transform:rotate(4deg) translateY(6px); } }
@media (prefers-reduced-motion: reduce) { .kite { animation:none; } }
%(motion)s
main { position:relative; max-width:640px; margin:0 auto; padding:%(top_space)s 24px 0; }
.clock { font-size:64px; font-weight:300; letter-spacing:-.02em; margin:0 0 20px; text-align:center;
  font-variant-numeric:tabular-nums; }
form { position:relative; }
form svg { position:absolute; left:20px; top:50%%; translate:0 -50%%; width:20px; height:20px; color:var(--muted); }
input { box-sizing:border-box; width:100%%; font:inherit; font-size:19px; padding:16px 20px 16px 54px;
  border-radius:18px; border:1px solid var(--line); background:var(--field); color:var(--ink);
  backdrop-filter:blur(14px); outline:none; }
input::placeholder { color:var(--muted); }
input:focus { border-color:var(--accent); box-shadow:0 0 0 4px color-mix(in srgb, var(--accent) 30%%, transparent); }
h2 { font-size:13px; font-weight:600; color:var(--muted); margin:32px 0 8px 4px; }
ul { list-style:none; padding:0; margin:0; display:grid; grid-template-columns:repeat(auto-fill, minmax(190px, 1fr)); gap:4px; }
a { display:flex; gap:10px; align-items:center; padding:8px 10px; border-radius:12px; color:inherit; text-decoration:none; min-width:0; }
a:hover, a:focus-visible { background:var(--field); }
a:focus-visible { outline:2px solid var(--accent); }
.av { flex:none; width:30px; height:30px; border-radius:9px; display:grid; place-items:center; font-weight:700; font-size:13px;
  background:hsl(var(--h) 60%% 60%% / .22); color:hsl(var(--h) 75%% 72%%); }
@media (prefers-color-scheme: light) { .av { color:hsl(var(--h) 55%% 38%%); } }
.t { display:flex; flex-direction:column; min-width:0; }
.t b, .t small { white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
.t b { font-weight:600; font-size:14px; } .t small { color:var(--muted); font-size:12px; }
</style></head>
<body>
%(kite)s
<main>
  %(clock)s
  %(search)s
  %(recent)s
</main>
<script>
const engine = %(engine)s, keywords = %(keywords)s;
const clock = document.getElementById('clock');
const tick = () => { clock.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); };
if (clock) { tick(); setInterval(tick, 5000); }
document.getElementById('f')?.addEventListener('submit', e => {
  e.preventDefault();
  const t = document.getElementById('q').value.trim();
  if (!t) return;
  const [first, ...rest] = t.split(/\\s+/);
  if (rest.length && Object.hasOwn(keywords, first.toLowerCase()))
    location.href = keywords[first.toLowerCase()].split('{}').join(encodeURIComponent(rest.join(' ')));
  else if (/^[a-z][a-z0-9+.-]*:/i.test(t) && !/^[\\w.-]+:\\d/.test(t)) location.href = t;
  else if (!/\\s/.test(t) && (t.includes('.') || t.startsWith('localhost'))) location.href = (t.startsWith('localhost') ? 'http://' : 'https://') + t;
  else location.href = engine.split('{}').join(encodeURIComponent(t));
});
</script>
</body></html>"""


def _kite_shapes(logo_svg):
    """The kite group from the app logo, so the page and the icon share one drawing."""
    m = re.search(r'<g id="kite".*?</g>', logo_svg, re.S)
    return re.sub(r' transform="[^"]*"', "", m.group(0)) if m else ""


def _links(entries, limit):
    """entries: [(url, title)] from history/bookmarks. They come from web pages, so everything is escaped."""
    items, seen = [], set()
    for url, title in entries:
        host = urlparse(url).hostname or url
        if not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        if len(items) == limit:
            break
        name = title or host
        hue = sum(map(ord, host)) % 360
        items.append(f'<li><a href="{html.escape(url)}"><span class="av" style="--h:{hue}">'
                     f'{html.escape(name[:1].upper())}</span><span class="t"><b>{html.escape(name)}</b>'
                     f'<small>{html.escape(host)}</small></span></a></li>')
    return "".join(items)


KITE = """<svg class="line" viewBox="0 0 1000 1000" preserveAspectRatio="none" aria-hidden="true">
  <path d="M -10 1010 C 260 860, 600 760, 760 240"/></svg>
<svg class="kite" viewBox="34 14 60 84" aria-hidden="true">%s</svg>"""
SEARCH = """<form id="f" role="search">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <input id="q" name="q" autofocus autocomplete="off" aria-label="Search or enter an address" placeholder="%s">
  </form>"""
DEFAULT_OPTIONS = {"preset": "dusk", "background": "sky", "color": "#1b2150", "kite": True, "search": True,
                   "clock": False, "tiles": 8, "keywords": {}, "motion": True, "palettes": None}


def render(search_url, engine_label, accent, recent, logo_svg, bookmarks=(), options=None):
    """options: see DEFAULT_OPTIONS. keywords maps keyword -> URL template, already validated.

    palettes, when given, is (dark, light) from themes.palette, which also covers the Custom theme.
    """
    o = {**DEFAULT_OPTIONS, **(options or {})}
    preset = PRESETS.get(o["preset"], PRESETS["dusk"])
    dark, light = o["palettes"] or (preset[True], preset[False])
    background = {"solid": o["color"] if is_hex_color(o["color"]) else "var(--top)",
                  # served by Kite from the path in settings, never from a path in the URL
                  "image": 'url("kite://start/background") center / cover no-repeat, var(--top)'}.get(
        o["background"], "linear-gradient(180deg, var(--top), var(--bottom))")
    # One recent entry per site; bookmarks are listed as saved.
    by_host = {}
    for url, title in recent:
        by_host.setdefault(urlparse(url).hostname or url, (url, title))
    tiles = max(0, min(24, int(o["tiles"])))
    sections = [(heading, links) for heading, links in (("Bookmarks", _links(bookmarks, tiles)),
                                                        ("Recently visited", _links(by_host.values(), tiles)))
                if links]
    return PAGE % {
        "dark_top": dark["sky_top"], "dark_bottom": dark["sky_bottom"], "dark_ink": dark["fg"],
        "light_top": light["sky_top"], "light_bottom": light["sky_bottom"], "light_ink": light["fg"],
        "background": background,
        "motion": "" if o["motion"] else ".kite { animation:none; }",
        "top_space": "34vh" if o["kite"] or not o["clock"] else "26vh",
        "clock": '<p class="clock" id="clock"></p>' if o["clock"] else "",
        "search": SEARCH % html.escape(f"Search with {engine_label} or enter an address") if o["search"] else "",
        "keywords": json.dumps(o["keywords"]).replace("<", "\\u003c"),
        "accent": accent if re.fullmatch(r"#[0-9a-fA-F]{6}", accent) else "#f5b83d",
        "kite": KITE % _kite_shapes(logo_svg) if o["kite"] else "",
        "recent": "".join(f"<h2>{h}</h2><ul>{links}</ul>" for h, links in sections),
        # json.dumps yields a valid JS string; escaping "<" stops a "</script>" inside a custom URL closing the tag.
        "engine": json.dumps(search_url).replace("<", "\\u003c"),
    }


ERROR = """<!doctype html>
<html><head><meta charset="utf-8"><title>%(title)s</title>
<style>
:root { --top:%(dark_top)s; --bottom:%(dark_bottom)s; --ink:%(dark_ink)s; --accent:%(accent)s; --on-accent:%(on_accent)s;
  color-scheme:dark; }
@media (prefers-color-scheme: light) {
  :root { --top:%(light_top)s; --bottom:%(light_bottom)s; --ink:%(light_ink)s; color-scheme:light; } }
html, body { height:100%%; margin:0; }
body { display:grid; place-items:center; background:linear-gradient(180deg, var(--top), var(--bottom)); color:var(--ink);
  font:16px/1.55 "Adwaita Sans", Inter, system-ui, sans-serif; }
main { max-width:34em; padding:24px; text-align:center; }
svg { width:56px; height:78px; transform:rotate(-14deg); margin-bottom:14px; }
h1 { font-size:26px; line-height:1.25; margin:0 0 10px; }
p { margin:0 auto 8px; max-width:30em; color:color-mix(in srgb, var(--ink) 75%%, transparent); }
code { display:block; margin-top:14px; font-size:13px; word-break:break-all;
  color:color-mix(in srgb, var(--ink) 55%%, transparent); }
button { margin-top:24px; font:600 15px/1 inherit; padding:12px 24px; border-radius:999px; border:0;
  background:var(--accent); color:var(--on-accent); cursor:pointer; }
button:focus-visible { outline:2px solid var(--ink); outline-offset:3px; }
</style></head>
<body><main>
<svg viewBox="34 14 60 84" aria-hidden="true">%(kite)s</svg>
<h1>%(heading)s</h1>
<p>%(detail)s</p>
<code>%(uri)s</code>
%(button)s
</main></body></html>"""


def error_page(uri, message, accent, logo_svg, palettes=None):
    """The page shown when a load fails. message None means the site's certificate isn't valid (no way past it)."""
    dark, light = palettes or (PRESETS["dusk"][True], PRESETS["dusk"][False])
    accent = accent if is_hex_color(accent) else "#f5b83d"
    host = urlparse(uri).hostname or uri
    if message is None:
        heading = f"{host} isn't safe to open"
        detail = ("Its security certificate isn't valid, so Kite stopped before sending anything. The site may be "
                  "set up wrongly, or someone may be intercepting the connection.")
        button = ""
    else:
        crashed = message.startswith("This tab")
        heading = message if crashed else f"Can't reach {host}"
        detail = ("Reload to try again. Pages you had open in other tabs aren't affected." if crashed
                  else f"{message}. Check your connection, or try again in a moment.")
        button = '<button onclick="location.reload()" autofocus>Try again</button>'
    from themes import luminance
    return ERROR % {
        "title": html.escape(heading), "heading": html.escape(heading), "detail": html.escape(detail),
        "uri": html.escape(uri), "button": button, "kite": _kite_shapes(logo_svg), "accent": accent,
        "on_accent": "#1a1f3d" if luminance(accent) > 0.55 else "#ffffff",
        "dark_top": dark["sky_top"], "dark_bottom": dark["sky_bottom"], "dark_ink": dark["fg"],
        "light_top": light["sky_top"], "light_bottom": light["sky_bottom"], "light_ink": light["fg"],
    }
