"""SettingsManager (JSON-backed), every setting's default, and validators for the structured ones."""
import json
import os
import re
import shutil

CONFIG_PATH = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "kitebrowser", "settings.json")

# label, URL template ({} = query). Brave is the default: in testing its results pages loaded in WebKit with no ads and
# no browser-install banner (only footer links), while Mojeek, Startpage, Qwant and Google showed bot checks and DuckDuckGo/Ecosia
# promoted their own browsers.
ENGINES = {
    "brave": ("Brave Search", "https://search.brave.com/search?q={}"),
    "mojeek": ("Mojeek", "https://www.mojeek.com/search?q={}"),
    "startpage": ("Startpage", "https://www.startpage.com/do/search?q={}"),
    "ecosia": ("Ecosia", "https://www.ecosia.org/search?q={}"),
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com/?q={}"),
    "google": ("Google", "https://www.google.com/search?q={}"),
    "custom": ("Custom", None),
}

USER_AGENTS = {
    "default": None,  # WebKit's own
    "firefox": "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0",
    "chrome": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "safari": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) "
              "Version/18.5 Safari/605.1.15",
    "custom": None,
}

ZOOM_LEVELS = (0.3, 0.5, 0.67, 0.8, 0.9, 1.0, 1.1, 1.2, 1.33, 1.5, 1.7, 2.0, 2.4, 3.0)

# name -> (label, setting that shows it). The menu button isn't listed: it always stays, so Settings stays reachable.
TOOLBAR_BUTTONS = {
    "tabs": ("Tab panel toggle", "show_tabs_button"),
    "back": ("Back", "show_nav"),
    "forward": ("Forward", "show_nav"),
    "reload": ("Reload", "show_reload"),
    "home": ("Home", "show_home"),
    "bookmarks": ("Bookmarks", "show_bookmarks"),
    "downloads": ("Downloads (when there are any)", "show_downloads"),
    "memory": ("History and Memory Finder", "show_memory"),
}

DEFAULTS = {
    # General
    "homepage": "kite://start",
    "search_engine": "brave",
    "search_url": "",  # only used when search_engine is "custom"
    "keywords": [  # [keyword, name, URL template]; "w kite" searches Wikipedia for "kite"
        ["w", "Wikipedia", "https://en.wikipedia.org/w/index.php?search={}"],
        ["yt", "YouTube", "https://www.youtube.com/results?search_query={}"],
        ["gh", "GitHub", "https://github.com/search?q={}"],
        ["r", "Reddit", "https://www.reddit.com/search/?q={}"],
        ["maps", "OpenStreetMap", "https://www.openstreetmap.org/search?query={}"],
    ],
    "suggestions": True,
    "restore_session": True,
    "download_dir": "",  # empty = the system Downloads folder
    "new_tab_page": "start",
    "new_tab_position": "end",
    "switch_to_new_tabs": False,
    "last_tab": "close",
    # Look
    "theme": "dark",
    "theme_preset": "dusk",
    "custom_window": "#161a31",  # used by the Custom theme; seeded from the current theme when first picked
    "custom_view": "#1f2442",
    "custom_popover": "#232949",
    "custom_text": "",  # empty = picked automatically for contrast
    "chrome_background": "color",
    "chrome_gradient": "#3b2f6b",
    "chrome_image": "",
    "chrome_dim": 45,  # % of the window color laid over the image, so text stays readable
    "chrome_opacity": 100,
    "card_gap": 8,
    "card_border": 1,
    "card_shadow": True,
    "toolbar_height": 46,
    "active_tab_style": "bar",
    "color_development": "#4fd1c5",
    "color_social": "#f2789f",
    "color_research": "#8fa8ff",
    "color_media": "#b38cff",
    "color_other": "#8a90a8",
    "group_rules": [],  # [group name, "domain.com, other.org"], checked before the built-in groups
    "builtin_groups": True,
    "animations": True,
    "accent": "#f5b83d",  # empty = system accent
    "density": "compact",
    "roundness": 14,
    "ui_font": "",  # Pango description like "Inter 11"; empty = system font
    "tab_layout": "vertical",
    "tab_position": "start",
    "sidebar_width": 250,
    "tab_width": 200,
    "close_buttons": "hover",
    "show_favicons": True,
    "show_brand": True,
    "show_tabs": True,
    "auto_group": True,
    "tab_search": True,
    "toolbar_start": ["tabs", "back", "forward", "reload"],
    "toolbar_end": ["home", "bookmarks", "downloads", "memory"],
    "show_tabs_button": True,
    "show_nav": True,
    "show_reload": True,
    "show_url": True,
    "show_home": True,
    "show_bookmarks": True,
    "show_downloads": True,
    "show_memory": True,
    "show_reader": True,
    # Tabs
    "tab_sleep": True,
    "sleep_on_low_memory": True,
    "sleep_minutes": 15,
    # Start page
    "start_background": "sky",
    "start_color": "#1b2150",
    "start_image": "",
    "start_show_kite": True,
    "start_show_search": True,
    "start_show_bookmarks": True,
    "start_show_recent": True,
    "start_tiles": 8,
    "start_clock": False,
    # Web
    "font_sans": "",
    "font_serif": "",
    "font_mono": "",
    "font_size": 16,
    "font_size_mono": 13,
    "min_font_size": 0,
    "default_zoom": 1.0,
    "user_agent": "default",
    "user_agent_custom": "",
    "block_autoplay": True,
    "javascript": True,
    "spell_check": True,
    "smooth_scrolling": True,
    "devtools": True,
    "use_interface_css": True,
    "use_user_styles": True,
    "use_user_script": True,
    # Privacy
    "block_trackers": True,
    "itp": True,
    "memory_search": True,
    # Tools
    "command_palette": True,
    "split_view": True,
    "site_panel": True,
    "focus_mode": False,
    "screenshot_dir": "",  # empty = the system Pictures folder
    "screenshot_full_page": True,
    # Internal state the UI writes
    "tracker_exceptions": [],  # hosts where tracker blocking is off
    "site_permissions": {},  # host -> {permission kind: allowed}, from "remember my choice"
    "site_zoom": {},  # host -> zoom level
    "shortcuts": {},  # action name -> [accelerators]; only overrides of the defaults
}
CHOICES = {
    "search_engine": tuple(ENGINES),
    "theme": ("dark", "light", "system"),
    "theme_preset": ("dusk", "pine", "plum", "tide", "graphite", "midnight", "custom"),
    "chrome_background": ("color", "gradient", "image"),
    "active_tab_style": ("bar", "fill", "underline", "outline"),
    "density": ("compact", "relaxed"),
    "tab_layout": ("vertical", "horizontal"),
    "tab_position": ("start", "end"),
    "close_buttons": ("hover", "always", "never"),
    "new_tab_page": ("start", "homepage", "blank"),
    "new_tab_position": ("end", "after"),
    "last_tab": ("close", "keep"),
    "start_background": ("sky", "solid", "image"),
    "user_agent": tuple(USER_AGENTS),
    "default_zoom": ZOOM_LEVELS,
}
RANGES = {  # inclusive bounds, enforced on load and import
    "roundness": (0, 28), "sidebar_width": (180, 480), "tab_width": (100, 360), "sleep_minutes": (1, 240),
    "start_tiles": (0, 24), "font_size": (9, 40), "font_size_mono": (8, 40), "min_font_size": (0, 30),
    "chrome_dim": (0, 90), "chrome_opacity": (30, 100), "card_gap": (0, 32), "card_border": (0, 4),
    "toolbar_height": (32, 72),
}


PATH_KEYS = ("download_dir", "start_image", "chrome_image", "screenshot_dir")  # an imported file keeps the user's own paths


def valid(key, value):
    if key not in DEFAULTS:
        return False
    # URLs from an imported file must not smuggle in javascript: or file: pages.
    if key == "homepage" and not (isinstance(value, str) and value.startswith(("https://", "http://", "kite:", "about:blank"))):
        return False
    if key == "search_url" and value and not (isinstance(value, str) and value.startswith(("https://", "http://"))
                                              and "{}" in value):
        return False
    default = DEFAULTS[key]
    if isinstance(value, bool) != isinstance(default, bool) or not isinstance(value, type(default)):
        return False
    if key in RANGES and not RANGES[key][0] <= value <= RANGES[key][1]:
        return False
    return value in CHOICES.get(key, (value,))


def is_hex_color(value):
    return isinstance(value, str) and len(value) == 7 and value[0] == "#" and \
        all(c in "0123456789abcdefABCDEF" for c in value[1:])


def is_font_family(value):
    # Families end up in CSS strings; quotes, braces and semicolons could break out of them.
    return isinstance(value, str) and 0 < len(value) <= 80 and not any(c in value for c in "\"'{};\\<>")


def valid_keywords(rows):
    """Keyword rows that are safe to use: [keyword, name, http(s) URL template with {}]."""
    out = []
    for row in rows if isinstance(rows, list) else []:
        if (isinstance(row, list) and len(row) == 3 and all(isinstance(x, str) for x in row) and row[0]
                and " " not in row[0] and row[2].startswith(("https://", "http://")) and "{}" in row[2]):
            out.append(row)
    return out


GROUP_DOMAIN = re.compile(r"^(localhost|[a-z0-9-]+(\.[a-z0-9-]+)+)$")


def valid_groups(rows):
    """[(name, (domains…))] from the user's group rows; bad rows and bad domains are dropped."""
    out = []
    for row in rows if isinstance(rows, list) else []:
        if not (isinstance(row, list) and len(row) == 2 and all(isinstance(x, str) for x in row)):
            continue
        name = row[0].strip()
        domains = tuple(d for d in re.split(r"[\s,]+", row[1].lower()) if GROUP_DOMAIN.match(d))
        if name and len(name) <= 30 and domains:
            out.append((name, domains))
    return out


PERMISSION_KINDS = ("location", "notifications", "camera", "microphone", "camera and microphone", "screen",
                    "clipboard", "pointer")


def valid_hosts(hosts):
    return [h for h in hosts if isinstance(h, str) and GROUP_DOMAIN.match(h)] if isinstance(hosts, list) else []


def valid_site_permissions(value):
    """{host: {kind: bool}} with unknown hosts, kinds and non-bool answers dropped."""
    out = {}
    for host, kinds in (value.items() if isinstance(value, dict) else ()):
        if isinstance(host, str) and GROUP_DOMAIN.match(host) and isinstance(kinds, dict):
            good = {k: v for k, v in kinds.items() if k in PERMISSION_KINDS and isinstance(v, bool)}
            if good:
                out[host] = good
    return out


def toolbar_layout(s):
    """(start, end) button names: unknown names dropped, duplicates removed, new buttons added to their default side."""
    seen, sides = set(), []
    for key in ("toolbar_start", "toolbar_end"):
        side = []
        for name in s[key]:
            if name in TOOLBAR_BUTTONS and name not in seen:
                seen.add(name)
                side.append(name)
        sides.append(side)
    for i, key in enumerate(("toolbar_start", "toolbar_end")):
        sides[i] += [n for n in DEFAULTS[key] if n not in seen]
    return sides[0], sides[1]


class SettingsManager:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self.data = dict(DEFAULTS)
        self._listeners = []
        self.schedule = None  # the app sets a debounce here so sliders don't write the file on every step
        try:
            with open(path) as f:
                loaded = json.load(f)
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            print(f"settings: unreadable {path} ({e}); moved to .bak, using defaults")
            os.replace(path, path + ".bak")
            return
        if isinstance(loaded, dict):
            self.update_from(loaded)

    def __getitem__(self, key):
        return self.data[key]

    def update_from(self, loaded):
        """Takes every valid key from an untrusted dict; returns the keys it rejected."""
        rejected = []
        for k, v in loaded.items():
            if valid(k, v):
                self.data[k] = v
            else:
                rejected.append(k)
        return rejected

    def set(self, key, value):
        if self.data[key] == value:
            return
        self.data[key] = value
        self.schedule(self.save) if self.schedule else self.save()
        for cb in self._listeners:
            cb(key)

    def replace_all(self, loaded, keep_paths=True):
        """Import (or reset, with {} and keep_paths=False): back up the current file, then defaults plus valid keys.

        An import never changes where downloads go or which local image is read: those stay the user's own.
        """
        backup = self.backup()
        kept = {k: self.data[k] for k in PATH_KEYS} if keep_paths else {}
        self.data = dict(DEFAULTS)
        rejected = self.update_from({k: v for k, v in loaded.items() if k not in PATH_KEYS} if keep_paths else loaded)
        self.data.update(kept)
        self.save()
        for cb in self._listeners:
            cb(None)
        return backup, rejected

    def backup(self):
        if not os.path.exists(self.path):
            return None
        shutil.copyfile(self.path, self.path + ".bak")
        return self.path + ".bak"

    def connect(self, callback):
        self._listeners.append(callback)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.data, f, indent=2)
        os.replace(tmp, self.path)

    def search_engine(self):
        """(label, URL template) for the chosen engine; a custom URL without {} falls back to Brave."""
        label, url = ENGINES[self["search_engine"]]
        if url is None:
            url = self["search_url"] if "{}" in self["search_url"] else ENGINES["brave"][1]
        return label, url

    def user_agent(self):
        if self["user_agent"] == "custom":
            return self["user_agent_custom"].strip() or None
        return USER_AGENTS[self["user_agent"]]
