#!/usr/bin/python3
"""Assert-based checks for the non-GUI logic. Run: ./selfcheck.py"""
import json
import os
import tempfile
import time

import start_page
from browser import accent_fg, classify, next_zoom, to_url
import blocker
from bookmarks import Bookmarks
from downloads import safe_filename
from history_indexer import HistoryIndexer
from settings import DEFAULTS, ENGINES, SettingsManager

# Tab grouping
assert classify("https://github.com/x/y") == "Development"
assert classify("https://en.m.wikipedia.org/wiki/Ant") == "Research"
assert classify("https://www.youtube.com/watch?v=1") == "Media"
assert classify("https://x.com/home") == "Social"
assert classify("https://box.com") == "Other"  # no substring false positive for x.com

# Omnibox
S = "https://duckduckgo.com/?q={}"
assert to_url("example.com", S) == "https://example.com"
assert to_url("localhost:8000", S) == "http://localhost:8000"
assert to_url("about:blank", S) == "about:blank"
assert to_url("https://a.b/c", S) == "https://a.b/c"
assert to_url("rust async book", S) == "https://duckduckgo.com/?q=rust+async+book"

# Settings: roundtrip, listener, invalid values ignored, corrupt file backed up
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "sub", "settings.json")
    s = SettingsManager(path)
    seen = []
    s.connect(seen.append)
    s.set("tab_sleep", False)
    s.set("tab_sleep", False)  # no-op, no second event
    assert seen == ["tab_sleep"] and SettingsManager(path)["tab_sleep"] is False
    with open(path, "w") as f:
        json.dump({"theme": "neon", "sleep_minutes": "5", "bogus": 1, "density": "relaxed"}, f)
    s = SettingsManager(path)
    assert s["theme"] == DEFAULTS["theme"] and s["sleep_minutes"] == 15 and s["density"] == "relaxed"
    with open(path, "w") as f:
        f.write("{not json")
    assert SettingsManager(path)["theme"] == "dark" and os.path.exists(path + ".bak")
    # Search engine: default Brave, unknown engine rejected, custom URL used only when it has {}
    s = SettingsManager(path)
    assert s.search_engine() == ENGINES["brave"]
    s.set("search_engine", "custom")
    assert s.search_engine()[1] == ENGINES["brave"][1]  # empty custom URL falls back
    s.set("search_url", "https://example.org/?s={}")
    assert s.search_engine() == ("Custom", "https://example.org/?s={}")
    with open(path, "w") as f:
        json.dump({"search_engine": "bing"}, f)
    assert SettingsManager(path)["search_engine"] == "brave"

# Accent text color
assert accent_fg("#f5b83d") == "#1a1f3d" and accent_fg("#1c3faa") == "#ffffff"

# Start page: page-supplied titles/URLs are escaped, non-http links dropped, engine URL can't break out of <script>
with open(os.path.join(os.path.dirname(__file__), "assets", "io.github.KiteBrowser.svg")) as f:
    logo = f.read()
page = start_page.render("https://x/?q={}</script><script>alert(1)//", "X", "#f5b83d",
                         [("https://a.com/", "<img src=x onerror=alert(1)>"), ("javascript:alert(1)", "evil")], logo)
assert "<img src=x" not in page and "&lt;img" in page and "javascript:alert" not in page
two = start_page.render("u{}", "X", "#000000", [("https://y.com/a", "A"), ("https://y.com/b", "B")], logo,
                        [("https://b.org/", "Saved"), ("javascript:x", "bad")])
assert two.count("y.com</small>") == 1 and "<h2>Bookmarks</h2>" in two and "javascript:x" not in two
assert page.count("</script>") == 1 and '<path d="M64 14' in page

# Memory Finder
h = HistoryIndexer(":memory:")
now = time.time()
h.add("https://blog/rust", "Async Rust explained", "Futures, executors and tokio runtimes in depth", now - 3600)
h.add("https://blog/py", "Python packaging", "pip, wheels and virtual environments", now - 3600)
h.add("https://old/rust", "Rust ownership", "borrow checker and async lifetimes", now - 40 * 86400)
h.add("https://blog/py", "Python packaging guide", "uv, pip and wheels", now)  # re-visit replaces
r = h.search("that article about async rust I read last week")
assert [x[0] for x in r] == ["https://blog/rust"], r  # old page excluded by "last week"
assert h.search("async rust")[0][0] == "https://blog/rust"  # title match ranks first
assert len(h.search("")) == 3 and h.search("")[0][0] == "https://blog/py"  # recent first, url deduped
assert h.search("packag")[0][1] == "Python packaging guide"  # prefix + latest version
assert h.search('" OR ) DROP') == []  # hostile input can't break the MATCH syntax
assert [u for u, _ in h.suggest("blog/r")] == ["https://blog/rust"]  # URL substring, which FTS can't match
assert h.suggest("100%_") == []  # LIKE wildcards in input are literal

# Zoom steps
assert next_zoom(1.0, 1) == 1.1 and next_zoom(1.0, -1) == 0.9 and next_zoom(3.0, 1) == 3.0 and next_zoom(0.3, -1) == 0.3

# Tracker rules: valid JSON, one rule per domain, regexes without alternation (WebKit rejects "|")
rules = json.loads(blocker.rules_json())
assert len(rules) == len(blocker.TRACKERS) == len(set(blocker.TRACKERS)) and all("|" not in r["trigger"]["url-filter"] for r in rules)

with tempfile.TemporaryDirectory() as d:
    # Downloads: server-chosen names can't escape the folder, start with a dot, or overwrite
    assert safe_filename("../../.bashrc", d) == os.path.join(d, "bashrc")
    assert safe_filename("", d) == os.path.join(d, "download")
    open(os.path.join(d, "a.zip"), "w").close()
    assert safe_filename("a.zip", d) == os.path.join(d, "a (1).zip")
    assert safe_filename("C:\\evil\\b.exe", d) == os.path.join(d, "b.exe")
    # Bookmarks persist and toggle
    path = os.path.join(d, "b", "bookmarks.json")
    b = Bookmarks(path)
    assert b.toggle("https://x.org/", "X") is True and Bookmarks(path).has("https://x.org/")
    assert b.search("x.or")[0]["title"] == "X" and b.toggle("https://x.org/", "X") is False and not Bookmarks(path).has("https://x.org/")
# ---- customization ----
import shortcuts
import themes
from settings import CHOICES, RANGES, TOOLBAR_BUTTONS, toolbar_layout, valid

# Every preset has dark and light palettes with every key the CSS and start page use
KEYS = {"window", "view", "fg", "popover", "dialog", "private", "sky_top", "sky_bottom"}
for name in CHOICES["theme_preset"]:
    for dark in (True, False):
        assert set(themes.palette({**DEFAULTS, "theme_preset": name}, dark)) == KEYS
        assert name == "custom" or set(themes.PRESETS[name][dark]) == KEYS

# Custom theme: its window color picks light or dark, and the text color follows unless set
light = {**DEFAULTS, "theme_preset": "custom", "custom_window": "#f4f0e8"}
assert not themes.custom_is_dark(light) and themes.palette(light, True)["fg"] == "#1b1d27"
assert themes.custom_is_dark({**light, "custom_window": "#101010"})
assert themes.palette({**light, "custom_text": "#ff0000"}, False)["fg"] == "#ff0000"
assert themes.palette({**light, "custom_window": "url(x)"}, True)["window"] == DEFAULTS["custom_window"]  # bad hex ignored

# Window background: an image path can't break out of the CSS url(), and a missing image means no image layer
weird = {**DEFAULTS, "chrome_background": "image", "chrome_image": '/tmp/a "b) (c.png'}
css = themes.chrome_css(weird, True, True)
assert '"b' not in css.split('url("')[1].split('")')[0] and css.count('url("') == 1
assert "url(" not in themes.chrome_css(weird, True, False) and "0.50" in themes.chrome_css({**DEFAULTS, "chrome_opacity": 50}, True, False)
assert "chrome_image" in __import__("settings").PATH_KEYS

# Every adjustable layout rule comes from the theme CSS, and full screen wins over the gap
css = themes.interface_css({**DEFAULTS, "card_gap": 20, "active_tab_style": "fill"}, True, "#f5b83d", "#1a1f3d")
assert "margin: 0 20px 20px 20px" in css and css.index("window.fullscreen .webcard") > css.index(".webcard {")
assert ".dot.g-media" in css and ".dot.user-0" in css and "var(--accent-fg-color)" in css

# Your own tab groups: checked first, subdomains match, bad rows ignored, built-ins can be turned off
from settings import valid_groups
mine = valid_groups([["Work", "example.com, jira.corp.io"], ["", "x.com"], ["Bad", "not a domain!"]])
assert mine == [("Work", ("example.com", "jira.corp.io"))]
assert classify("https://docs.example.com/x", mine) == "Work" and classify("https://github.com", mine) == "Development"
assert classify("https://github.com", [("Code", ("github.com",))]) == "Code"  # user groups win over built-ins
assert classify("https://github.com", mine, builtin=False) == "Other"

# Every key survives write -> reload with a non-default value, including floats, lists and dicts
odd = {k: (not v if isinstance(v, bool) else CHOICES[k][-1] if k in CHOICES else RANGES[k][1] if k in RANGES
           else v + ["x"] if isinstance(v, list) and k.startswith("toolbar") else [["k", "K", "https://k.org/?q={}"]] if isinstance(v, list)
           else {"a": 1.5} if isinstance(v, dict) else "#123456" if k in ("accent", "start_color")
           else "https://x.org/?q={}" if k in ("homepage", "search_url")
           else "#abcdef" if k.startswith(("custom_", "color_")) or k == "chrome_gradient" else "x")
       for k, v in DEFAULTS.items()}
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "settings.json")
    m = SettingsManager(path)
    for k, v in odd.items():
        m.set(k, v)
    again = SettingsManager(path)
    assert all(again[k] == v for k, v in odd.items()), [k for k, v in odd.items() if again[k] != v]
    # A garbled import keeps defaults for bad keys, takes good ones, and backs up the old file
    backup, rejected = again.replace_all({"roundness": 999, "font_size": "big", "theme": "light", "keywords": "nope",
                                         "show_nav": 1, "default_zoom": 1.1, "nonsense": True})
    assert again["roundness"] == DEFAULTS["roundness"] and again["theme"] == "light" and again["default_zoom"] == 1.1
    assert again["show_nav"] is True and sorted(rejected) == ["font_size", "keywords", "nonsense", "roundness", "show_nav"]
    assert backup and json.load(open(backup))["roundness"] == RANGES["roundness"][1]
assert not valid("homepage", "javascript:alert(1)") and not valid("homepage", "file:///etc/passwd")
assert valid("homepage", "kite://start") and not valid("search_url", "javascript:{}") and valid("search_url", "")
with tempfile.TemporaryDirectory() as d:
    m = SettingsManager(os.path.join(d, "s.json"))
    m.set("download_dir", "/home/me/dl")
    m.replace_all({"download_dir": os.path.expanduser("~/.config/autostart"), "start_image": "/etc/x.png", "theme": "light"})
    assert m["download_dir"] == "/home/me/dl" and m["start_image"] == "" and m["theme"] == "light"  # import keeps paths
    m.replace_all({}, keep_paths=False)
    assert m["download_dir"] == ""  # reset clears them
assert valid("sleep_minutes", 5) and not valid("sleep_minutes", True) and not valid("default_zoom", 1.05)

# Toolbar layout: unknown and duplicate names dropped, missing buttons come back on their default side
fake = {"toolbar_start": ["reload", "bogus", "reload", "home"], "toolbar_end": ["memory"]}
start, end = toolbar_layout(fake)
assert start == ["reload", "home", "tabs", "back", "forward"] and end == ["memory", "bookmarks", "downloads"]
assert sorted(start + end) == sorted(TOOLBAR_BUTTONS)

# Search keywords
KW = DEFAULTS["keywords"]
assert to_url("w kite flying", S, KW) == "https://en.wikipedia.org/w/index.php?search=kite+flying"
assert to_url("W kite", S, KW).startswith("https://en.wikipedia.org")  # keyword match ignores case
assert to_url("w", S, KW) == S.replace("{}", "w")  # a keyword alone is an ordinary search
assert to_url("zz kite", S, KW) == S.replace("{}", "zz+kite")
assert to_url("x y", S, [["x", "Evil", "javascript:alert({})"]]) == S.replace("{}", "x+y")  # unsafe templates ignored

# Shortcuts: modifiers required (except F-keys), Ctrl/Alt+digit reserved, a taken key moves
assert shortcuts.is_valid("<Ctrl>k") and shortcuts.is_valid("F7") and not shortcuts.is_valid("k")
assert not shortcuts.is_valid("<Shift>k") and not shortcuts.is_valid("<Ctrl>nonsensekey")
new, taken = shortcuts.rebind({}, "print", "<Ctrl>t")
eff = shortcuts.effective(new)
assert eff["print"] == ["<Ctrl>t"] and "<Ctrl>t" not in eff["new-tab"] and taken == ["New tab"]
try:
    shortcuts.rebind({}, "print", "<Ctrl>3")
    raise AssertionError("Ctrl+3 should be reserved")
except ValueError:
    pass
assert shortcuts.effective({"print": ["k"], "nope": ["<Ctrl>q"]})["print"] == ["<Ctrl>p"]  # bad overrides ignored
assert shortcuts.rebind({}, "print", None)[0] == {"print": []}

# Start page options: hidden parts are gone, keyword JSON can't close the script, image comes from the fixed route
opts = {"kite": False, "search": False, "clock": True, "background": "image", "preset": "pine",
        "keywords": {"x": "https://x.org/?q={}</script><script>alert(1)//"}}
page = start_page.render("https://e/?q={}", "E", "#f5b83d", [], logo, [], opts)
assert 'class="kite"' not in page and 'id="q"' not in page and 'id="clock"' in page
assert page.count("</script>") == 1 and 'url("kite://start/background")' in page and themes.PRESETS["pine"][True]["sky_top"] in page
assert "#123456" in start_page.render("u{}", "E", "#f5b83d", [], logo, [], {"background": "solid", "color": "#123456"})
assert "expression" not in start_page.render("u{}", "E", "#f5b83d", [], logo, [], {"background": "solid", "color": "expression(x)"})

# Error pages escape what the network and URL supply; certificate errors get no way past them
err = start_page.error_page('http://x/"><script>alert(1)</script>', "Connection <b>refused</b>", "#f5b83d", logo)
assert "<script>alert" not in err and "&lt;b&gt;refused" in err and "Try again" in err
assert "Try again" not in start_page.error_page("https://bad.example/", None, "#f5b83d", logo)
# Low-memory detection reads /proc/meminfo-style text and fails safe
from browser import low_memory
with tempfile.TemporaryDirectory() as d:
    path = os.path.join(d, "meminfo")
    open(path, "w").write("MemTotal:       8000000 kB\nMemFree:  100 kB\nMemAvailable:    500000 kB\n")
    assert low_memory(path)
    open(path, "w").write("MemTotal:       8000000 kB\nMemAvailable:   4000000 kB\n")
    assert not low_memory(path) and not low_memory(os.path.join(d, "missing"))
# No two default actions share a shortcut (a new action could silently steal one)
seen = {}
for _sec, name, _title, accels in shortcuts.ACTIONS:
    for a in accels:
        key = shortcuts.normalize(a)
        assert key not in seen, f"{a} is bound to both {seen[key]} and {name}"
        seen[key] = name

# Command palette ranking
import palette
items = [("history", "Kite flying", "", 1), ("tab", "GitHub - kite", "github.com", 2), ("action", "Settings", "Ctrl+,", 3),
         ("setting", "Settings: Colors", "", 4), ("bookmark", "MDN", "developer.mozilla.org", 5)]
assert [i[3] for i in palette.rank("settings", items)][:2] == [3, 4]  # title starts with it; action before setting
assert palette.rank("kite", items)[0][3] == 1 and palette.rank("git", items)[0][3] == 2
assert palette.rank("mozilla", items)[0][3] == 5 and palette.rank("zzz", items) == []
assert [i[0] for i in palette.rank("", items)][:2] == ["tab", "action"]  # empty query: tabs first

# Per-site tracker exceptions compile into one trailing ignore rule
rules = json.loads(blocker.rules_json(("example.com",)))
assert rules[-1] == {"trigger": {"url-filter": ".*", "if-domain": ["*example.com"]}, "action": {"type": "ignore-previous-rules"}}
assert all(r["action"]["type"] == "block" for r in json.loads(blocker.rules_json()))

# Remembered permissions: only real hosts, known kinds and true/false answers survive
from settings import valid_site_permissions, valid_hosts
assert valid_site_permissions({"a.com": {"camera": True, "teleport": True, "location": "yes"}, "bad host": {"camera": True},
                               "b.org": {"teleport": False}, 7: {}}) == {"a.com": {"camera": True}}
assert valid_hosts(["a.com", "x y", 3, "localhost"]) == ["a.com", "localhost"]
print("selfcheck OK")
