"""KiteBrowser application: state every window shares (settings, history, web engine, theme, session restore)."""
import json
import os
from urllib.parse import urlparse

from browser import (APP_ID, ASSETS, CACHE_DIR, CSS, DATA_DIR, LOGO, Adw, BrowserWindow, Gdk, Gio, GLib, Gtk,
                     WebKit, accent_fg, to_url)
import blocker
import shortcuts
import start_page
from bookmarks import Bookmarks
from downloads import Downloads
from history_indexer import HistoryIndexer
from settings import CONFIG_PATH, SettingsManager, is_font_family, is_hex_color, valid_hosts, valid_keywords
from themes import chrome_css, clamp, custom_is_dark, interface_css, palette
from userfiles import UserFiles

SESSION_PATH = os.path.join(DATA_DIR, "session.json")
# Settings the kite://start page bakes in, so open start pages reload when they change.
RELOAD_START_KEYS = ("search_engine", "search_url", "accent", "memory_search", "theme_preset", "keywords",
                     "start_background", "start_color", "start_image", "start_show_kite", "start_show_search",
                     "start_show_bookmarks", "start_show_recent", "start_tiles", "start_clock", "theme",
                     "custom_window", "custom_view", "custom_popover", "custom_text", "animations")
USER_FILE_KEYS = ("use_interface_css", "use_user_styles", "use_user_script")
BACKGROUND_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
                    ".gif": "image/gif"}  # no SVG: it can carry script and would run in the kite:// origin


class Kite(Adw.Application):
    def __init__(self, app_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE):
        super().__init__(application_id=app_id, flags=flags)
        self._save_queued = False
        self._settings_timer = 0

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.s = SettingsManager()
        self.s.schedule = self.schedule_settings_save
        self.history = HistoryIndexer()
        self.bookmarks = Bookmarks()
        with open(LOGO) as f:
            self.logo_svg = f.read()

        display = Gdk.Display.get_default()
        Gtk.IconTheme.get_for_display(display).add_search_path(ASSETS)
        Gtk.Window.set_default_icon_name(APP_ID)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        # Above USER priority so a desktop theme's gtk.css can't repaint Kite's chrome.
        Gtk.StyleContext.add_provider_for_display(display, css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.theme_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, self.theme_css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
        # The window background has its own provider: reloading it re-decodes a background image, so it reloads
        # only when its CSS actually changes, not on every unrelated slider step.
        self.chrome_css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(display, self.chrome_css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 2)
        self._css_cache = {}
        self.user_css = Gtk.CssProvider()  # the user's interface.css wins over everything Kite sets
        self.user_css.connect("parsing-error", lambda _p, section, error: self._css_errors.append(
            f"interface.css line {section.get_start_location().lines + 1}: {error.message}"))
        self._css_errors = []
        Gtk.StyleContext.add_provider_for_display(display, self.user_css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 3)

        context = WebKit.WebContext.get_default()
        context.register_uri_scheme("kite", self.serve_kite)  # once per process, before any WebView exists
        # Local: web pages can't load or embed kite:// URLs (the start page lists history).
        context.get_security_manager().register_uri_scheme_as_local("kite")
        lang = (GLib.get_language_names()[0] or "en_US").split(".")[0]
        context.set_spell_checking_languages(["en_US" if lang in ("C", "POSIX") else lang])
        self.session = WebKit.NetworkSession.new(os.path.join(DATA_DIR, "webkit"), CACHE_DIR)
        self.session.get_website_data_manager().set_favicons_enabled(True)
        self.downloads = Downloads(self.s)
        self.downloads.attach(self.session)
        self.web_settings = WebKit.Settings()
        self.content = WebKit.UserContentManager()
        self.filter_store = WebKit.UserContentFilterStore.new(os.path.join(CACHE_DIR, "filters"))
        self.filter_on = None  # the exception hosts the active filter was built for; None = no filter

        self.user_files = UserFiles(os.path.dirname(CONFIG_PATH), self.apply_user_files)
        self.s.connect(self.on_setting)
        Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self.apply_settings())
        self.apply_settings()
        self.apply_shortcuts()
        self.apply_user_files()

    def do_shutdown(self):
        if self._settings_timer:  # a debounced settings save is still waiting
            GLib.source_remove(self._settings_timer)
            self.s.save()
        Adw.Application.do_shutdown(self)

    # ---- windows ------------------------------------------------------------
    def do_command_line(self, cmd):
        # Also runs in the first instance for every later `main.py URL` launch, so links open as tabs.
        self.open_initial(cmd.get_arguments()[1:])
        return 0

    def do_activate(self):
        self.open_initial([])

    def open_initial(self, args):
        win = self.get_active_window()
        if win:
            for a in args:
                win.open_tab(to_url(a, self.s.search_engine()[1], self.s["keywords"]))
            win.present()
            return
        state = self.load_session() if not args and self.s["restore_session"] else []
        for w in state or [None]:
            BrowserWindow(self, urls=args, restore=w).present()

    def new_window(self, private=False):
        BrowserWindow(self, private=private).present()

    def browser_windows(self):
        return [w for w in self.get_windows() if isinstance(w, BrowserWindow)]

    def all_tabs(self):
        return [t for w in self.browser_windows() for t in w.tabs]

    # ---- settings -----------------------------------------------------------
    def on_setting(self, key):
        """key None means everything changed (import or reset)."""
        self.apply_settings()
        if key in (None, "shortcuts"):
            self.apply_shortcuts()
        if key is None or key in USER_FILE_KEYS:
            self.apply_user_files()
        if key is None or key in RELOAD_START_KEYS:
            self.reload_start_pages()

    def schedule_settings_save(self, save):
        # Sliders change a setting many times a second: apply each change live, write the file once it settles.
        if self._settings_timer:
            GLib.source_remove(self._settings_timer)

        def fire():
            self._settings_timer = 0
            save()
            return GLib.SOURCE_REMOVE

        self._settings_timer = GLib.timeout_add(400, fire)

    def apply_shortcuts(self):
        for name, accels in shortcuts.effective(self.s["shortcuts"]).items():
            self.set_accels_for_action("win." + name, accels)
        for i in range(1, 10):
            self.set_accels_for_action(f"win.goto-tab({i})", [f"<Ctrl>{i}", f"<Alt>{i}"])

    def suspend_shortcuts(self, suspended):
        """While a new shortcut is being recorded, no existing one may fire."""
        if not suspended:
            return self.apply_shortcuts()
        for name in shortcuts.DEFAULTS:
            self.set_accels_for_action("win." + name, [])
        for i in range(1, 10):
            self.set_accels_for_action(f"win.goto-tab({i})", [])

    def apply_user_files(self, name=None):
        s, files = self.s, self.user_files
        if name in (None, "interface.css"):
            self._css_errors = []
            self.user_css.load_from_string(files.read("interface.css") if s["use_interface_css"] else "")
            if self._css_errors and (win := self.get_active_window()):
                win.toast(self._css_errors[0])
        if name in (None, "userstyle.css", "userscript.js"):
            self.content.remove_all_style_sheets()  # leaves the tracker filter alone
            self.content.remove_all_scripts()
            frames = WebKit.UserContentInjectedFrames.ALL_FRAMES
            if s["use_user_styles"] and (css := files.read("userstyle.css")).strip():
                self.content.add_style_sheet(WebKit.UserStyleSheet(css, frames, WebKit.UserStyleLevel.USER, None, None))
            if s["use_user_script"] and (js := files.read("userscript.js")).strip():
                self.content.add_script(WebKit.UserScript(js, frames, WebKit.UserScriptInjectionTime.END, None, None))

    def apply_settings(self):
        s = self.s
        style = Adw.StyleManager.get_default()
        theme = s["theme"]
        if s["theme_preset"] == "custom":  # widgets Kite doesn't recolor must match the custom window color
            theme = "dark" if custom_is_dark(s) else "light"
        style.set_color_scheme({"dark": Adw.ColorScheme.FORCE_DARK, "light": Adw.ColorScheme.FORCE_LIGHT}.get(
            theme, Adw.ColorScheme.DEFAULT))
        a, dark = self.accent(), style.get_dark()
        image = s["chrome_image"]
        image_ok = os.path.splitext(image)[1].lower() in BACKGROUND_TYPES and os.path.isfile(image)
        self.load_css(self.theme_css, interface_css(s, dark, a, accent_fg(a)))
        self.load_css(self.chrome_css, chrome_css(s, dark, image_ok))
        Gtk.Settings.get_default().set_property("gtk-enable-animations", s["animations"])

        ws = self.web_settings
        sans = s["font_sans"] if is_font_family(s["font_sans"]) else "sans-serif"
        ws.set_default_font_family(sans)
        ws.set_sans_serif_font_family(sans)
        ws.set_serif_font_family(s["font_serif"] if is_font_family(s["font_serif"]) else "serif")
        ws.set_monospace_font_family(s["font_mono"] if is_font_family(s["font_mono"]) else "monospace")
        ws.set_default_font_size(clamp("font_size", s["font_size"]))
        ws.set_default_monospace_font_size(clamp("font_size_mono", s["font_size_mono"]))
        ws.set_minimum_font_size(clamp("min_font_size", s["min_font_size"]))
        ws.set_user_agent(s.user_agent())  # None restores WebKit's own
        ws.set_enable_developer_extras(s["devtools"])
        ws.set_enable_smooth_scrolling(s["smooth_scrolling"])
        ws.set_enable_javascript(s["javascript"])
        WebKit.WebContext.get_default().set_spell_checking_enabled(s["spell_check"])
        self.session.set_itp_enabled(s["itp"])
        self.apply_blocker()
        for w in self.browser_windows():
            w.apply_settings()

    def load_css(self, provider, css):
        if self._css_cache.get(provider) != css:
            self._css_cache[provider] = css
            provider.load_from_string(css)

    def accent(self):
        a = self.s["accent"]
        if is_hex_color(a):
            return a
        c = Adw.StyleManager.get_default().get_accent_color_rgba()
        return "#%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255))

    def apply_blocker(self):
        """Tracker filter on or off; recompiled when the per-site exceptions change."""
        exceptions = tuple(valid_hosts(self.s["tracker_exceptions"]))
        want = exceptions if self.s["block_trackers"] else None
        if want == self.filter_on:
            return
        self.filter_on = want
        self.content.remove_all_filters()
        if want is not None:
            rules = GLib.Bytes.new(blocker.rules_json(want).encode())
            self.filter_store.save("kite-trackers", rules, None, self._filter_saved, want)

    def _filter_saved(self, store, result, compiled_for):
        try:
            tracker_filter = store.save_finish(result)
        except GLib.Error as e:
            print("tracker blocker:", e.message)
            return
        if self.filter_on == compiled_for:  # a newer change may have arrived while this compiled
            self.content.remove_all_filters()
            self.content.add_filter(tracker_filter)

    def clear_data(self, done):
        self.history.clear()

        def cleared(manager, result):
            try:
                manager.clear_finish(result)
                message = "Browsing data cleared"
            except GLib.Error as e:
                message = f"History cleared, but cookies and site data weren't: {e.message}"
            self.reload_start_pages()
            done(message)

        self.session.get_website_data_manager().clear(WebKit.WebsiteDataTypes.ALL, 0, None, cleared)

    # ---- kite://start -------------------------------------------------------
    def serve_kite(self, request):
        s = self.s
        if urlparse(request.get_uri()).path == "/background":
            return self.serve_background(request)
        view = request.get_web_view()
        private = getattr(view.get_root() if view else None, "private", False)
        recent = [] if private or not (s["memory_search"] and s["start_show_recent"]) else \
            [(u, t) for u, t, *_ in self.history.search("", limit=60)]
        marks = [(b["url"], b.get("title", "")) for b in self.bookmarks.all()] if s["start_show_bookmarks"] else []
        label, url = s.search_engine()
        options = {"preset": s["theme_preset"], "background": s["start_background"], "color": s["start_color"],
                   "kite": s["start_show_kite"], "search": s["start_show_search"], "clock": s["start_clock"],
                   "tiles": s["start_tiles"], "keywords": {k.lower(): u for k, _n, u in valid_keywords(s["keywords"])},
                   "motion": s["animations"], "palettes": (palette(s, True), palette(s, False))}
        page = start_page.render(url, label, self.accent(), recent, self.logo_svg, marks, options)
        data = GLib.Bytes.new(page.encode())
        request.finish(Gio.MemoryInputStream.new_from_bytes(data), data.get_size(), "text/html")

    def error_page(self, uri, message):
        return start_page.error_page(uri, message, self.accent(), self.logo_svg,
                                     (palette(self.s, True), palette(self.s, False)))

    def serve_background(self, request):
        # Only ever the file chosen in Settings, never a path taken from the URL.
        path = self.s["start_image"]
        kind = BACKGROUND_TYPES.get(os.path.splitext(path)[1].lower())
        try:
            if not kind:
                raise OSError("not a supported image")
            with open(path, "rb") as f:
                data = GLib.Bytes.new(f.read())
        except OSError as e:
            request.finish_error(GLib.Error.new_literal(Gio.io_error_quark(), str(e), Gio.IOErrorEnum.NOT_FOUND))
            return
        request.finish(Gio.MemoryInputStream.new_from_bytes(data), data.get_size(), kind)

    def reload_start_pages(self):
        for w in self.browser_windows():
            for t in w.tabs:
                if t.view and t.url.startswith("kite:"):
                    t.view.reload()

    # ---- session restore ----------------------------------------------------
    def schedule_save(self):
        if not self._save_queued:
            self._save_queued = True
            GLib.timeout_add(500, self.save_session)

    def save_session(self, *_):
        self._save_queued = False
        self._settings_timer = 0
        state = [w.session_state() for w in self.browser_windows() if not w.private]
        state = [w for w in state if w["tabs"]]
        # Never overwrite the saved session with nothing: closing the last tab or window keeps it for next launch.
        if state and self.s["restore_session"]:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(SESSION_PATH + ".tmp", "w") as f:
                json.dump(state, f)
            os.replace(SESSION_PATH + ".tmp", SESSION_PATH)
        return GLib.SOURCE_REMOVE

    def window_closing(self, win):
        others = [w for w in self.browser_windows() if w is not win and not w.private and w.tabs]
        if others:
            GLib.idle_add(self.save_session)  # runs after win has left the window list
        else:
            self.save_session()

    def load_session(self):
        try:
            with open(SESSION_PATH) as f:
                state = json.load(f)
            return [w for w in state if isinstance(w, dict) and isinstance(w.get("tabs"), list) and w["tabs"]]
        except (OSError, ValueError, TypeError):
            return []
