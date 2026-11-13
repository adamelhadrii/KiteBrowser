"""KiteBrowser window: toolbar and omnibox, tab panel, find bar, zoom, reader view, permissions, Memory Finder."""
import itertools
import os
import re
import time
from urllib.parse import quote_plus, urlparse

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("WebKit", "6.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, Gio, GLib, Graphene, Gtk, Pango, WebKit  # noqa: E402

from downloads import download_row  # noqa: E402
import sitepanel  # noqa: E402
from palette import open_palette  # noqa: E402
from reader import READER_JS  # noqa: E402
import shortcuts  # noqa: E402
from preferences import open_settings_dialog  # noqa: E402
from downloads import safe_filename  # noqa: E402
from settings import (TOOLBAR_BUTTONS, ZOOM_LEVELS, toolbar_layout, valid_groups, valid_keywords,  # noqa: E402
                      valid_site_permissions)
from themes import USER_GROUP_COLORS, clamp  # noqa: E402

APP_ID = "io.github.KiteBrowser"
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO = os.path.join(ASSETS, APP_ID + ".svg")
DATA_DIR = os.path.join(GLib.get_user_data_dir(), "kitebrowser")
CACHE_DIR = os.path.join(GLib.get_user_cache_dir(), "kitebrowser")

GROUPS = {
    "Development": ("github.com", "gitlab.com", "codeberg.org", "stackoverflow.com", "stackexchange.com",
                    "readthedocs.io", "python.org", "pypi.org", "npmjs.com", "crates.io", "docs.rs",
                    "developer.mozilla.org", "localhost", "127.0.0.1"),
    "Social": ("twitter.com", "x.com", "facebook.com", "instagram.com", "reddit.com", "linkedin.com",
               "mastodon.social", "bsky.app", "threads.net", "discord.com", "news.ycombinator.com"),
    "Research": ("wikipedia.org", "arxiv.org", "scholar.google.com", "semanticscholar.org", "pubmed.ncbi.nlm.nih.gov",
                 "researchgate.net", "jstor.org", "nature.com", "sciencedirect.com"),
    "Media": ("youtube.com", "youtu.be", "netflix.com", "spotify.com", "twitch.tv", "vimeo.com",
              "soundcloud.com", "music.apple.com"),
}
GROUP_ORDER = (*GROUPS, "Other")
TOOLBAR_ACTIONS = {"tabs": "toggle-tabs", "back": "back", "forward": "forward", "reload": "reload", "home": "home",
                   "bookmarks": "bookmarks", "downloads": "downloads", "memory": "memory"}
CLOSED_TAB_MEMORY = 25

CSS = """
window.kite headerbar { background: none; box-shadow: none; }
.omnibox { border-radius: 999px; min-height: 34px; padding: 0 14px; border: none; box-shadow: none;
  background-color: alpha(currentColor, .07); }
.omnibox:focus-within { background-color: var(--view-bg-color); box-shadow: 0 0 0 2px var(--accent-bg-color); }
.zoom-badge { border-radius: 999px; padding: 2px 10px; min-height: 0; font-size: .85em; font-weight: 600; }
.private-badge { font-size: .8em; font-weight: 700; padding: 3px 10px; border-radius: 999px;
  background-color: alpha(#b38cff, .25); }
.suggestions contents { padding: 6px; border-radius: 14px; }
.suggestions row { border-radius: 10px; padding: 6px 10px; }
.suggestions .url { font-size: .85em; opacity: .6; }
.webcard { background-color: var(--view-bg-color); }
.findbar { padding: 6px 6px 6px 10px; border-radius: 14px; background-color: var(--popover-bg-color);
  box-shadow: 0 0 0 1px alpha(currentColor, .1), 0 6px 18px rgba(0, 0, 0, .3); }
.brand { padding: 2px 6px 8px; }
.brand label { font-weight: 800; font-size: 1.1em; }
.newtab { border-radius: 10px; padding: 6px 10px; font-weight: 600; }
.tabpanel { padding: 0 8px 8px; }
.tabpanel.tabs-horizontal { padding: 0 8px 6px; }
.tabstrip .tab { border-radius: 10px; transition: background-color 120ms ease-out; }
.tabstrip .tab:hover { background-color: alpha(currentColor, .06); }
.tabstrip .tab > button.pick { padding: 5px 8px; min-height: 0; background: none; box-shadow: none; }
.relaxed .tabstrip .tab > button.pick { padding: 10px 12px; }
.tabstrip .tab .close { opacity: 0; min-width: 22px; min-height: 22px; padding: 0; margin-right: 4px; }
.tabstrip .tab:hover .close, .tabstrip .tab:focus-within .close, .tabstrip .tab.active .close { opacity: .75; }
window.close-always .tabstrip .tab .close { opacity: .75; }
.tabstrip .tab .title { min-width: 0; }
.pins { margin: 2px 2px 8px; }
.split-pane { border-top: 2px solid transparent; }
.split-pane.focused { border-top-color: var(--accent-bg-color); }
.pins flowboxchild { padding: 0; }
.pin-tile { min-height: 34px; min-width: 40px; padding: 0; background-color: alpha(currentColor, .06); }
.pin-tile:hover { background-color: alpha(currentColor, .1); }
.pin-tile.active { background-color: alpha(currentColor, .14); box-shadow: inset 0 0 0 2px var(--accent-bg-color); }
.pin-tile.asleep image { opacity: .5; }
.tabstrip .tab .audio { min-width: 22px; min-height: 22px; padding: 0; }
.tabstrip .tab.asleep .title, .tabstrip .tab.asleep image { opacity: .5; }
.tabstrip .group { margin: 12px 8px 4px; }
.tabs-horizontal .tabstrip .group { margin: 0 4px 0 10px; }
.tabstrip .group label { font-size: .78em; font-weight: 700; opacity: .65; }
.dot { min-width: 7px; min-height: 7px; border-radius: 99px; }
.badge { font-size: .7em; font-weight: 600; padding: 1px 7px; border-radius: 99px; background-color: alpha(currentColor, .12); }
.palette-entry, .palette-entry:focus-within { font-size: 1.2em; min-height: 56px; padding: 0 18px; border-radius: 0;
  background: none; box-shadow: none; outline: none; }
.palette list { background: none; }
.palette row { border-radius: 10px; padding: 8px 10px; }
.palette .meta { font-size: .85em; opacity: .6; }
.palette .snippet { font-size: .9em; opacity: .75; }
"""


def classify(url, user_groups=(), builtin=True):
    """Group name for a tab. user_groups is valid_groups() output and is checked first."""
    host = (urlparse(url).hostname or "").lower()
    for group, domains in [*user_groups, *(GROUPS.items() if builtin else ())]:
        if any(host == d or host.endswith("." + d) for d in domains):
            return group
    return "Other"


def to_url(text, search_url, keywords=()):
    text = text.strip()
    first, _, rest = text.partition(" ")
    for keyword, _name, template in valid_keywords(list(keywords)):
        if first.lower() == keyword.lower() and rest.strip():
            return template.replace("{}", quote_plus(rest.strip()))
    if re.match(r"^[a-z][a-z0-9+.-]*:", text) and not re.match(r"^[\w.-]+:\d", text):
        return text  # has a scheme (https:, about:, kite:) and isn't host:port
    if " " not in text and ("." in text or text.startswith("localhost")):
        return ("http://" if text.startswith(("localhost", "127.")) else "https://") + text
    return search_url.replace("{}", quote_plus(text))


def accent_fg(hex_color):
    """Dark text on light accents (Kite saffron), white on dark ones."""
    r, g, b = (int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return "#1a1f3d" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else "#ffffff"


def ago(ts):
    s = max(0, time.time() - ts)
    if s < 60:
        return "just now"
    if s < 3600:
        return f"{int(s // 60)} min ago"
    if s < 86400:
        return f"{int(s // 3600)} h ago"
    days = int(s // 86400)
    return "yesterday" if days == 1 else f"{days} days ago"


def low_memory(meminfo="/proc/meminfo", threshold=0.12):
    """True when the system has less than threshold of its memory available."""
    try:
        with open(meminfo) as f:
            info = {line.split(":")[0]: int(line.split()[1]) for line in f if line.split()[1:2]}
        return info["MemAvailable"] < info["MemTotal"] * threshold
    except (OSError, KeyError, ValueError, IndexError):
        return False


def next_zoom(level, direction):
    if direction > 0:
        return next((z for z in ZOOM_LEVELS if z > level + 1e-3), ZOOM_LEVELS[-1])
    return next((z for z in reversed(ZOOM_LEVELS) if z < level - 1e-3), ZOOM_LEVELS[0])


def permission_question(request, host):
    """(kind, prompt) for a site permission request, or (None, None) for kinds left to WebKit's default (deny)."""
    W = WebKit
    if isinstance(request, W.GeolocationPermissionRequest):
        return "location", f"Let {host} see your location?"
    if isinstance(request, W.NotificationPermissionRequest):
        return "notifications", f"Let {host} show notifications?"
    if isinstance(request, W.UserMediaPermissionRequest):
        if W.user_media_permission_is_for_display_device(request):
            return "screen", f"Let {host} see your screen?"
        cam = W.user_media_permission_is_for_video_device(request)
        mic = W.user_media_permission_is_for_audio_device(request)
        kind = "camera and microphone" if cam and mic else "camera" if cam else "microphone"
        return kind, f"Let {host} use your {kind}?"
    # getattr: these request types only exist in newer WebKitGTK releases
    if isinstance(request, getattr(W, "ClipboardPermissionRequest", ())):
        return "clipboard", f"Let {host} read your clipboard?"
    if isinstance(request, getattr(W, "PointerLockPermissionRequest", ())):
        return "pointer", f"Let {host} hide and lock your pointer?"
    return None, None


_tab_ids = itertools.count(1)


class Tab:
    def __init__(self, win, url, related=None, lazy=False, title="", pinned=False, muted=False):
        self.id = next(_tab_ids)
        self.win, self.url, self.title, self.view = win, url or "", title, None
        self.favicon, self.loading, self.pinned, self.muted = None, False, pinned, muted
        self.showing_error = self.error_pending = False
        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True, vexpand=True)
        self.last_active = time.monotonic()
        if lazy:
            self.fetch_favicon()  # restored tabs stay unloaded until selected
        else:
            self.wake(related)

    def fetch_favicon(self):
        db = self.win.session.get_website_data_manager().get_favicon_database()
        if not (db and self.url.startswith(("http:", "https:"))):
            return

        def done(db, result):
            try:
                self.favicon = db.get_favicon_finish(result)
            except GLib.Error:
                return
            self.win.render_tabs()

        db.get_favicon(self.url, None, done)

    def wake(self, related=None):
        app, w = self.win.app, self.win
        autoplay = WebKit.AutoplayPolicy.ALLOW_WITHOUT_SOUND if app.s["block_autoplay"] else WebKit.AutoplayPolicy.ALLOW
        kw = {"user_content_manager": app.content, "website_policies": WebKit.WebsitePolicies(autoplay=autoplay)}
        # Tabs opened as popups share their opener's web process; remember which, so sleep never kills a shared one.
        opener = next((t for t in self.win.app.all_tabs() if t.view is related), None) if related else None
        self.process_group = opener.process_group if opener else self.id
        v = WebKit.WebView(related_view=related, **kw) if related else \
            WebKit.WebView(network_session=w.session, **kw)
        v.set_settings(app.web_settings)
        v.set_is_muted(self.muted)
        v.set_vexpand(True)
        # Keep the ids: sleep() disconnects exactly these before ending the page.
        self.handlers = [v.connect(signal, handler) for signal, handler in (
            ("notify::title", self.on_title),
            ("notify::uri", self.on_uri),
            ("notify::favicon", self.on_favicon),
            ("notify::is-loading", self.on_loading),
            ("notify::is-playing-audio", lambda *_: w.render_tabs()),
            ("notify::estimated-load-progress", self.on_progress),
            ("load-changed", self.on_load_changed),
            ("create", lambda v, _action: w.open_tab(None, related=v, index=w.after_current()).view),
            ("close", lambda v: w.close_tab(self)),
            ("decide-policy", w.on_decide_policy),
            ("permission-request", w.on_permission_request),
            ("load-failed", self.on_load_failed),
            ("web-process-terminated", self.on_crashed),
            ("load-failed-with-tls-errors", lambda v, uri, _cert, _errors: w.show_error(self, uri, None)),
        )]
        finder = v.get_find_controller()
        finder.connect("counted-matches", lambda _f, n: self is w.current and w.find_status(
            f"{n} match{'' if n == 1 else 'es'}"))
        finder.connect("failed-to-find-text", lambda _f: self is w.current and w.find_status("No matches"))
        self.view = v
        self.box.append(v)
        if self.url and not related:
            v.load_uri(self.url)

    def sleep(self):
        # WebKit keeps a closed page's process alive for reuse, so dropping the view alone frees little: end the
        # process too, unless an awake tab (a popup or its opener) still runs in it. The favicon stays on the Tab.
        if self.win.split and self in self.win.split:
            self.win.end_split()
        view = self.view
        self.box.remove(view)
        # Stop listening first: a dying page reports a blank URL and title, which would overwrite what we wake to.
        for handler in self.handlers:
            view.disconnect(handler)
        if not any(t is not self and t.view and t.process_group == self.process_group for t in self.win.app.all_tabs()):
            view.terminate_web_process()
        self.view, self.loading, self.handlers = None, False, []
        self.win.render_tabs()

    def on_title(self, v, _):
        self.title = v.get_title() or ""
        if self is self.win.current:
            self.win.update_title()
        self.win.render_tabs()
        self.win.session_changed()

    def on_uri(self, v, _):
        self.url = v.get_uri() or ""
        if self is self.win.current:
            self.win.sync_url()
            self.win.update_nav()
        self.win.render_tabs()
        self.win.session_changed()

    def on_favicon(self, v, _):
        self.favicon = v.get_favicon()
        self.win.render_tabs()

    def on_loading(self, v, _):
        self.loading = v.is_loading()
        if self is self.win.current:
            self.win.update_nav()
        self.win.render_tabs()

    def on_crashed(self, v, reason):
        # Kite ends a sleeping tab's process itself; only a crash of the page on screen needs the error page.
        if v is self.view and reason != WebKit.WebProcessTerminationReason.TERMINATED_BY_API:
            self.win.show_error(self, self.url, "This tab crashed" if reason == WebKit.WebProcessTerminationReason.CRASHED
                                else "This tab ran out of memory and was stopped")

    def on_load_failed(self, v, _event, uri, error):
        # Cancelled loads and loads that turned into downloads aren't failures the user needs to see.
        P, N = WebKit.PolicyError, WebKit.NetworkError
        if (error.domain == "WebKitPolicyError" and error.code == P.FRAME_LOAD_INTERRUPTED_BY_POLICY_CHANGE) or \
                (error.domain == "WebKitNetworkError" and error.code == N.CANCELLED):
            return False
        return self.win.show_error(self, uri, error.message)

    def on_progress(self, v, _):
        if self is self.win.current:
            p = v.get_estimated_load_progress()
            self.win.url.set_progress_fraction(0 if p >= 1 else p)

    def on_load_changed(self, v, event):
        if event == WebKit.LoadEvent.STARTED:
            # The error page's own load starts here too; any other load (like Try again) clears the error.
            self.showing_error, self.error_pending = self.error_pending, False
        elif event == WebKit.LoadEvent.COMMITTED:
            self.win.apply_zoom(self)
        elif event == WebKit.LoadEvent.FINISHED:
            if not self.showing_error:
                self.win.index_page(self)
            if self is self.win.current:
                self.win.update_nav()


class BrowserWindow(Adw.ApplicationWindow):
    def __init__(self, app, urls=(), private=False, restore=None):
        super().__init__(application=app, default_width=1280, default_height=800)
        self.app, self.s, self.history, self.private = app, app.s, app.history, private
        self.tabs, self.current, self.closed, self.order = [], None, [], []
        self.suggestion_urls = []
        self.permissions = {}  # private windows only: (host, kind) -> allowed
        self.add_css_class("kite")
        if private:
            self.add_css_class("private")
            self.session = WebKit.NetworkSession.new_ephemeral()
            app.downloads.attach(self.session)
        else:
            self.session = app.session

        self.build_actions()
        self.build_ui()
        # Tiled side by side (e.g. a private window next to a normal one), drop the extra toolbar buttons so the
        # address bar keeps its room; the main menu still has all of them.
        self.narrow = False
        self.set_size_request(360, 300)
        breakpoint = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 800sp"))
        breakpoint.connect("apply", lambda *_: self.set_narrow(True))
        breakpoint.connect("unapply", lambda *_: self.set_narrow(False))
        self.add_breakpoint(breakpoint)
        self.connect("close-request", self.on_close_request)
        self.connect("notify::fullscreened", lambda *_: self.apply_settings())
        app.downloads.listeners.append(self.refresh_downloads)
        self.apply_settings()
        self.refresh_downloads()
        self.sleep_timer = GLib.timeout_add_seconds(30, self.sleep_idle_tabs)

        if restore:
            for t in restore["tabs"]:
                if isinstance(t, dict) and isinstance(t.get("url"), str):
                    self.open_tab(t["url"], lazy=True, select=False, title=str(t.get("title", "")),
                                  pinned=bool(t.get("pinned")), muted=bool(t.get("muted")))
        if self.tabs:
            sel = restore.get("selected", 0)
            self.select(self.tabs[sel if isinstance(sel, int) and 0 <= sel < len(self.tabs) else 0])
        else:
            for u in urls or [self.s["homepage"]]:
                self.open_tab(to_url(u, self.s.search_engine()[1], self.s["keywords"]))

    # ---- construction -------------------------------------------------------
    def build_actions(self):
        def cur(fn):
            return lambda *_: self.current and self.current.view and fn(self.current.view)

        # Titles and (rebindable) shortcuts live in shortcuts.ACTIONS; the app applies the accelerators.
        callbacks = {
            "new-tab": self.new_tab,
            "close-tab": lambda *_: self.current and self.close_tab(self.current),
            "reopen-tab": self.reopen_tab,
            "next-tab": lambda *_: self.cycle(1),
            "prev-tab": lambda *_: self.cycle(-1),
            "toggle-tabs": lambda *_: self.s.set("show_tabs", not self.s["show_tabs"]),
            "new-window": lambda *_: self.app.new_window(),
            "new-private": lambda *_: self.app.new_window(private=True),
            "fullscreen": lambda *_: self.unfullscreen() if self.is_fullscreen() else self.fullscreen(),
            "focus-url": lambda *_: (self.reveal_toolbar(True), self.url.grab_focus()),
            "palette": lambda *_: open_palette(self),
            "focus-mode": lambda *_: self.s.set("focus_mode", not self.s["focus_mode"]),
            "screenshot": self.screenshot,
            "split": self.toggle_split,
            "back": cur(lambda v: v.go_back()),
            "forward": cur(lambda v: v.go_forward()),
            "reload": cur(lambda v: v.reload()),
            "hard-reload": cur(lambda v: v.reload_bypass_cache()),
            "home": cur(lambda v: v.load_uri(self.s["homepage"])),
            "find": self.find_open,
            "find-next": self.find_next,
            "find-prev": self.find_prev,
            "zoom-in": lambda *_: self.zoom(1),
            "zoom-out": lambda *_: self.zoom(-1),
            "zoom-reset": lambda *_: self.zoom(0),
            "reader": self.toggle_reader,
            "print": cur(lambda v: WebKit.PrintOperation.new(v).run_dialog(self)),
            "bookmark": self.toggle_bookmark,
            "bookmarks": lambda *_: self.b_bookmarks.popup(),
            "downloads": self.show_downloads,
            "memory": self.open_memory_finder,
            "devtools": cur(lambda v: self.s["devtools"] and v.get_inspector().show()),
            "settings": lambda *_: open_settings_dialog(self, self.app),
            "shortcuts": self.show_shortcuts,
        }
        for _section, name, _title, _accels in shortcuts.ACTIONS:
            action = Gio.SimpleAction(name=name)
            action.connect("activate", callbacks[name])
            self.add_action(action)
        stop = Gio.SimpleAction(name="stop")  # what the reload button does while a page loads
        stop.connect("activate", cur(lambda v: v.stop_loading()))
        self.add_action(stop)

        goto = Gio.SimpleAction(name="goto-tab", parameter_type=GLib.VariantType("i"))
        goto.connect("activate", lambda _a, p: self.goto(p.get_int32()))
        self.add_action(goto)

        # Tab context-menu actions take the tab's id, which stays valid while the list reorders.
        for name, fn in [
            ("tab-reload", lambda t: t.view and t.view.reload()),
            ("tab-duplicate", lambda t: self.open_tab(t.url, index=self.tabs.index(t) + 1)),
            ("tab-pin", self.toggle_pin),
            ("tab-mute", self.toggle_mute),
            ("tab-sleep", lambda t: t.view and t is not self.current and not (self.split and t in self.split)
             and t.sleep()),
            ("tab-split", self.start_split),
            ("tab-bookmark", lambda t: self.toggle_bookmark(tab=t)),
            ("tab-close", self.close_tab),
            ("tab-close-others", lambda t: [self.close_tab(o) for o in list(self.tabs) if o is not t and not o.pinned]),
        ]:
            action = Gio.SimpleAction(name=name, parameter_type=GLib.VariantType("i"))
            action.connect("activate", lambda _a, p, fn=fn: (t := self.tab_by_id(p.get_int32())) and fn(t))
            self.add_action(action)

    def build_ui(self):
        def button(icon, tip, action):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip, action_name="win." + action)
            b.add_css_class("flat")
            return b

        header = Adw.HeaderBar()
        self.b_tabs = button("sidebar-show-symbolic", "Toggle tabs (Ctrl+B)", "toggle-tabs")
        self.b_back = button("go-previous-symbolic", "Back (Alt+Left)", "back")
        self.b_fwd = button("go-next-symbolic", "Forward (Alt+Right)", "forward")
        self.b_home = button("go-home-symbolic", "Home", "home")
        self.b_mem = button("document-open-recent-symbolic", "History and Memory Finder (Ctrl+H)", "memory")
        self.b_reload = button("view-refresh-symbolic", "Reload (Ctrl+R)", "reload")

        self.b_menu = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=self.main_menu(), primary=True,
                                     tooltip_text="Menu (F10)")
        self.b_menu.add_css_class("flat")
        self.b_bookmarks = Gtk.MenuButton(icon_name="user-bookmarks-symbolic", tooltip_text="Bookmarks (Ctrl+Shift+O)",
                                          popover=self.build_bookmarks_popover())
        self.b_bookmarks.add_css_class("flat")
        self.b_downloads = Gtk.MenuButton(icon_name="folder-download-symbolic", tooltip_text="Downloads (Ctrl+Shift+Y)",
                                          popover=self.build_downloads_popover())
        self.b_downloads.add_css_class("flat")
        header.pack_end(self.b_menu)
        if self.private:
            badge = Gtk.Label(label="Private", tooltip_text="History, cookies and site data are forgotten "
                                                            "when this window closes", valign=Gtk.Align.CENTER)
            badge.add_css_class("private-badge")
            header.pack_end(badge)
        self.tool_buttons = {"tabs": self.b_tabs, "back": self.b_back, "forward": self.b_fwd, "reload": self.b_reload,
                             "home": self.b_home, "bookmarks": self.b_bookmarks, "downloads": self.b_downloads,
                             "memory": self.b_mem}
        self.tools_start, self.tools_end = Gtk.Box(spacing=2), Gtk.Box(spacing=2)
        header.pack_start(self.tools_start)
        header.pack_end(self.tools_end)

        self.url = Gtk.Entry(hexpand=True)
        self.url.add_css_class("omnibox")
        self.url.connect("activate", self.on_url_activate)
        self.url.connect("changed", self.on_url_changed)
        self.url.connect("icon-press", self.on_url_icon)
        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", self.on_url_key)
        self.url.add_controller(keys)
        focus = Gtk.EventControllerFocus()
        focus.connect("leave", lambda *_: GLib.timeout_add(150, self.hide_suggestions))
        self.url.add_controller(focus)
        self.zoom_badge = Gtk.Button(tooltip_text="Reset zoom (Ctrl+0)", action_name="win.zoom-reset",
                                     valign=Gtk.Align.CENTER, visible=False)
        self.zoom_badge.add_css_class("zoom-badge")
        self.b_reader = button("x-office-document-symbolic", "Reader view (Ctrl+Alt+R)", "reader")
        bar = Gtk.Box(spacing=4)
        for w in (self.url, self.zoom_badge, self.b_reader):
            bar.append(w)
        header.set_title_widget(Adw.Clamp(maximum_size=760, hexpand=True, child=bar))
        self.build_suggestions()
        self.site_popover = sitepanel.build(self)
        self.url.set_icon_tooltip_text(Gtk.EntryIconPosition.PRIMARY, "Site information")
        pointer = Gtk.EventControllerMotion(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        pointer.connect("motion", self.on_pointer)
        self.add_controller(pointer)

        self.brand = Gtk.Box(spacing=8)
        self.brand.add_css_class("brand")
        self.brand.append(Gtk.Image(icon_name=APP_ID, pixel_size=22))
        self.brand.append(Gtk.Label(label="Kite"))
        self.newtab_content = Adw.ButtonContent(icon_name="list-add-symbolic", label="New tab", halign=Gtk.Align.START)
        newtab = Gtk.Button(child=self.newtab_content, action_name="win.new-tab", tooltip_text="New tab (Ctrl+T)")
        newtab.add_css_class("flat")
        newtab.add_css_class("newtab")
        self.tab_search = Gtk.SearchEntry(placeholder_text="Filter tabs")
        self.tab_search.connect("search-changed", lambda *_: self.render_tabs())
        self.tab_box = Gtk.Box(spacing=2)
        self.tab_box.add_css_class("tabstrip")
        self.tab_scroll = Gtk.ScrolledWindow(child=self.tab_box)
        self.tab_panel = Gtk.Box(spacing=6)
        self.tab_panel.add_css_class("tabpanel")
        for w in (self.brand, newtab, self.tab_search, self.tab_scroll):
            self.tab_panel.append(w)
        self.tab_menu = Gtk.PopoverMenu(has_arrow=False)
        self.tab_menu.set_parent(self.tab_panel)  # not a row: rows are rebuilt on every title/spinner change

        self.stack = Gtk.Stack(hexpand=True, vexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE,
                               transition_duration=90)
        overlay = self.overlay = Gtk.Overlay(child=self.stack)
        self.split = None  # (left tab, right tab) while split view is on
        self.paned = Gtk.Paned(wide_handle=True, hexpand=True, vexpand=True)
        overlay.add_overlay(self.build_findbar())
        card = Gtk.Box(hexpand=True, vexpand=True, overflow=Gtk.Overflow.HIDDEN)  # clips the WebView's corners
        card.add_css_class("webcard")
        card.append(overlay)
        self.card = card
        self.body = Gtk.Box()
        self.body.append(self.tab_panel)
        self.body.append(card)
        self.toolbar_view = Adw.ToolbarView(content=self.body, top_bar_style=Adw.ToolbarStyle.FLAT)
        self.toolbar_view.add_top_bar(header)
        self.toasts = Adw.ToastOverlay(child=self.toolbar_view)
        self.set_content(self.toasts)

    def main_menu(self):
        menu = Gio.Menu()
        for section in (
            [("New tab", "new-tab"), ("New window", "new-window"), ("New private window", "new-private")],
            [("Home", "home"), ("Bookmarks", "bookmarks"), ("Downloads", "downloads"),
             ("History and Memory Finder", "memory")],
            [("Find in page", "find"), ("Zoom in", "zoom-in"), ("Zoom out", "zoom-out"), ("Reset zoom", "zoom-reset"),
             ("Reader view", "reader"), ("Print…", "print"), ("Full screen", "fullscreen")],
            [("Command palette", "palette"), ("Split view", "split"), ("Save a screenshot", "screenshot"),
             ("Focus mode", "focus-mode")],
            [("Developer tools", "devtools"), ("Keyboard shortcuts", "shortcuts"), ("Settings", "settings")],
        ):
            part = Gio.Menu()
            for label, action in section:
                part.append(label, "win." + action)
            menu.append_section(None, part)
        return menu

    def apply_settings(self):
        s, H, V = self.s, Gtk.Orientation.HORIZONTAL, Gtk.Orientation.VERTICAL
        fullscreen = self.is_fullscreen()
        for c in ("compact", "relaxed"):
            self.remove_css_class(c)
        self.add_css_class(s["density"])
        (self.add_css_class if fullscreen else self.remove_css_class)("fullscreen")
        self.stack.set_transition_duration(90 if s["animations"] else 0)
        focus = s["focus_mode"]  # like full screen, but the toolbar comes back when you point at the top edge
        self.toolbar_view.set_reveal_top_bars(not (fullscreen or focus))

        vertical = s["tab_layout"] == "vertical"
        self.body.set_orientation(H if vertical else V)
        self.tab_panel.set_orientation(V if vertical else H)
        self.tab_box.set_orientation(V if vertical else H)
        for c in ("tabs-vertical", "tabs-horizontal"):  # GTK already owns .vertical/.horizontal on boxes
            self.tab_panel.remove_css_class(c)
        self.tab_panel.add_css_class("tabs-" + s["tab_layout"])
        (self.add_css_class if vertical else self.remove_css_class)("vertical-layout")
        self.brand.set_visible(vertical and s["show_brand"])
        if s["tab_position"] == "end":
            self.body.reorder_child_after(self.tab_panel, self.card)
        else:
            self.body.reorder_child_after(self.tab_panel, None)
        for c in ("panel-end", "close-always"):
            self.remove_css_class(c)
        if s["tab_position"] == "end":
            self.add_css_class("panel-end")
        if s["close_buttons"] == "always":
            self.add_css_class("close-always")
        self.newtab_content.set_label("New tab" if vertical else "")
        self.tab_panel.set_size_request(clamp("sidebar_width", s["sidebar_width"]) if vertical else -1, -1)
        self.tab_search.set_size_request(-1 if vertical else 180, -1)
        self.tab_scroll.set_policy(Gtk.PolicyType.NEVER if vertical else Gtk.PolicyType.AUTOMATIC,
                                   Gtk.PolicyType.AUTOMATIC if vertical else Gtk.PolicyType.NEVER)
        self.tab_scroll.set_vexpand(vertical)
        self.tab_scroll.set_hexpand(not vertical)
        self.tab_panel.set_visible(s["show_tabs"] and not fullscreen and not focus)
        self.lookup_action("palette").set_enabled(s["command_palette"])
        self.lookup_action("split").set_enabled(s["split_view"])
        if not s["split_view"]:
            self.end_split()
        self.tab_search.set_visible(s["tab_search"])

        self.url.set_visible(s["show_url"])
        self.url.set_placeholder_text(f"Search with {s.search_engine()[0]} or enter an address")
        self.sync_url()
        self.layout_toolbar()
        self.lookup_action("memory").set_enabled(s["memory_search"])
        self.lookup_action("devtools").set_enabled(s["devtools"])
        self.update_title()
        self.render_tabs()

    def layout_toolbar(self):
        """Refill both toolbar boxes in the user's order; hidden or unavailable buttons stay out of sight."""
        s = self.s
        start, end = toolbar_layout(s)
        for box in (self.tools_start, self.tools_end):  # empty both first: a button may be switching sides
            while child := box.get_first_child():
                box.remove(child)
        for box, names in ((self.tools_start, start), (self.tools_end, end)):
            for name in names:
                box.append(self.tool_buttons[name])
        # Tiled side by side, the extras go so the address bar keeps its room; the main menu still has them.
        extras = ("home", "bookmarks", "memory")
        available = {"memory": s["memory_search"], "downloads": bool(self.app.downloads.items)}
        for name, (label, key) in TOOLBAR_BUTTONS.items():
            button = self.tool_buttons[name]
            button.set_visible(s[key] and available.get(name, True) and not (self.narrow and name in extras))
            button.set_tooltip_text(self.tool_tooltip(name))
        self.update_nav()

    def on_url_icon(self, _entry, position):
        if position == Gtk.EntryIconPosition.SECONDARY:
            self.toggle_bookmark()
        elif self.s["site_panel"]:
            area = self.url.get_icon_area(Gtk.EntryIconPosition.PRIMARY)
            self.site_popover.set_pointing_to(area)
            self.site_popover.popup()

    def reveal_toolbar(self, reveal):
        """Focus mode: show the toolbar while it's needed (pointer at the top, typing an address)."""
        if self.s["focus_mode"] and not self.is_fullscreen():
            self.toolbar_view.set_reveal_top_bars(reveal)

    def on_pointer(self, _ctl, _x, y):
        if not self.s["focus_mode"] or self.is_fullscreen():
            return
        shown = self.toolbar_view.get_reveal_top_bars()
        if y < 6 and not shown:
            self.reveal_toolbar(True)
        elif shown and y > self.toolbar_view.get_top_bar_height() + 48 and not self.editing_url() \
                and not self.suggest_pop.get_visible():
            self.reveal_toolbar(False)

    def screenshot(self, *_):
        tab = self.current
        if not (tab and tab.view):
            return
        folder = os.path.expanduser(self.s["screenshot_dir"] or GLib.get_user_special_dir(
            GLib.UserDirectory.DIRECTORY_PICTURES) or "~/Pictures")
        name = f"{urlparse(tab.url).hostname or 'Kite'} {time.strftime('%Y-%m-%d %H.%M.%S')}.png"
        full = self.s["screenshot_full_page"]

        def done(view, result, whole):
            try:
                texture = view.get_snapshot_finish(result)
            except GLib.Error:
                if whole:  # very tall pages can exceed what the GPU can draw at once
                    return view.get_snapshot(WebKit.SnapshotRegion.VISIBLE, WebKit.SnapshotOptions.NONE, None,
                                             done, False)
                return self.toast("Kite couldn't take a screenshot of this page")
            os.makedirs(folder, exist_ok=True)
            path = safe_filename(name, folder)
            texture.save_to_png(path)
            toast = Adw.Toast(title=f"Saved {os.path.basename(path)}" + ("" if whole or not full else
                                                                         " (visible part: the page is too tall)"),
                              button_label="Open", timeout=5)
            toast.connect("button-clicked", lambda *_: Gtk.FileLauncher(
                file=Gio.File.new_for_path(path)).launch(self, None, None))
            self.toasts.add_toast(toast)
            self.last_screenshot = path

        region = WebKit.SnapshotRegion.FULL_DOCUMENT if full else WebKit.SnapshotRegion.VISIBLE
        tab.view.get_snapshot(region, WebKit.SnapshotOptions.NONE, None, done, full)

    def set_narrow(self, narrow):
        self.narrow = narrow
        self.apply_settings()

    def show_shortcuts(self, *_):
        if not hasattr(Adw, "ShortcutsDialog"):  # libadwaita < 1.8 (Debian 13): the Settings page lists them too
            open_settings_dialog(self, self.app).set_visible_page_name("Shortcuts")
            return
        dialog = Adw.ShortcutsDialog()
        sections, current = {}, shortcuts.effective(self.s["shortcuts"])
        for section, name, title, _defaults in shortcuts.ACTIONS:
            if section not in sections:
                sections[section] = Adw.ShortcutsSection(title=section)
                dialog.add(sections[section])
            if current[name]:  # the shortcuts in effect, including the user's own
                sections[section].add(Adw.ShortcutsItem(title=title, accelerator=current[name][0]))
        sections["Tabs"].add(Adw.ShortcutsItem(title="Go to tab 1 to 8 (9 = last tab)", accelerator="<Ctrl>1"))
        dialog.present(self)

    def toast(self, text):
        self.toasts.add_toast(Adw.Toast(title=text, timeout=3))

    def update_title(self):
        title = (self.current.title if self.current else "") or "KiteBrowser"
        self.set_title(f"{title} (Private)" if self.private else title)

    # ---- tabs ---------------------------------------------------------------
    def open_tab(self, url, related=None, select=True, lazy=False, index=None, title="", pinned=False, muted=False):
        tab = Tab(self, url, related, lazy=lazy, title=title, pinned=pinned, muted=muted)
        self.tabs.insert(len(self.tabs) if index is None else index, tab)
        self.stack.add_child(tab.box)
        if select:
            self.select(tab)
        else:
            self.render_tabs()
        self.session_changed()
        return tab

    def after_current(self):
        return self.tabs.index(self.current) + 1 if self.current in self.tabs else None

    def new_tab(self, *_):
        page = {"start": "kite://start", "homepage": self.s["homepage"], "blank": "about:blank"}[self.s["new_tab_page"]]
        self.open_tab(page, index=self.after_current() if self.s["new_tab_position"] == "after" else None)
        self.url.grab_focus()

    def tab_by_id(self, tab_id):
        return next((t for t in self.tabs if t.id == tab_id), None)

    def select(self, tab):
        if self.split and tab not in self.split:
            self.end_split()  # picking another tab leaves split view
        if self.current and self.current is not tab:
            self.current.last_active = time.monotonic()
            self.find_close()
        if tab.view is None:
            tab.wake()
        self.current = tab
        tab.last_active = time.monotonic()
        if self.split:
            for t in self.split:  # the address bar, find bar and zoom follow the focused side
                (t.box.add_css_class if t is tab else t.box.remove_css_class)("focused")
        else:
            self.stack.set_visible_child(tab.box)
        self.update_title()
        self.url.set_progress_fraction(0)
        self.sync_url()
        self.update_zoom_badge()
        self.update_nav()
        self.render_tabs()
        self.session_changed()

    def close_tab(self, tab):
        if tab not in self.tabs:
            return
        if self.split and tab in self.split:
            self.end_split()
        if tab.url:
            self.closed = (self.closed + [{"url": tab.url, "pinned": tab.pinned}])[-CLOSED_TAB_MEMORY:]
        i = self.tabs.index(tab)
        self.tabs.remove(tab)
        self.stack.remove(tab.box)
        if not self.tabs and self.s["last_tab"] == "keep":
            self.new_tab()
        elif not self.tabs:
            self.close()
        elif tab is self.current:
            self.current = None
            self.select(self.tabs[min(i, len(self.tabs) - 1)])
        else:
            self.render_tabs()
            self.session_changed()

    def reopen_tab(self, *_):
        if self.closed:
            last = self.closed.pop()
            self.open_tab(last["url"], pinned=last["pinned"], index=self.after_current())

    def cycle(self, step):
        order = self.order or self.tabs
        if self.current in order:
            self.select(order[(order.index(self.current) + step) % len(order)])

    def goto(self, n):
        order = self.order or self.tabs
        if order:
            self.select(order[-1] if n == 9 else order[min(n, len(order)) - 1])

    def toggle_pin(self, tab):
        tab.pinned = not tab.pinned
        self.render_tabs()
        self.session_changed()

    def toggle_mute(self, tab):
        tab.muted = not tab.muted
        if tab.view:
            tab.view.set_is_muted(tab.muted)
        self.render_tabs()
        self.session_changed()

    def render_tabs(self):
        while child := self.tab_box.get_first_child():
            self.tab_box.remove(child)
        q = self.tab_search.get_text().lower() if self.s["tab_search"] else ""
        tabs = [t for t in self.tabs if q in f"{t.title} {t.url}".lower()]
        # CSS classes by position or fixed name, never from a user's group name (it could be "active" or "tab").
        user_groups = valid_groups(self.s["group_rules"])
        dot_class = {"Pinned": "pinned", **{g: f"g-{g.lower()}" for g in GROUP_ORDER}}
        dot_class.update({name: f"user-{i % len(USER_GROUP_COLORS)}" for i, (name, _d) in enumerate(user_groups)})
        sections = [("Pinned", [t for t in tabs if t.pinned])]
        rest = [t for t in tabs if not t.pinned]
        if self.s["auto_group"]:
            grouped = {}
            for t in rest:
                grouped.setdefault(classify(t.url, user_groups, self.s["builtin_groups"]), []).append(t)
            order = [*dict.fromkeys([name for name, _d in user_groups] + list(GROUP_ORDER))]
            sections += [(g, grouped[g]) for g in order if g in grouped]
        else:
            sections.append((None, rest))
        self.order = []
        vertical = self.s["tab_layout"] == "vertical"
        # A heading only helps when there's more than one group to tell apart.
        headings = len([n for n, m in sections if m and n != "Pinned"]) > 1
        for name, members in sections:
            if not members:
                continue
            if name == "Pinned":  # pinned tabs are compact icon tiles, like a dock
                tiles = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, homogeneous=True, max_children_per_line=8,
                                    column_spacing=4, row_spacing=4) if vertical else Gtk.Box(spacing=4)
                tiles.add_css_class("pins")
                for t in members:
                    tiles.append(self.pin_tile(t))
                    self.order.append(t)
                self.tab_box.append(tiles)
                continue
            if name and headings:
                header = Gtk.Box(spacing=7, valign=Gtk.Align.CENTER)
                header.add_css_class("group")
                dot = Gtk.Box(valign=Gtk.Align.CENTER)
                dot.add_css_class("dot")
                dot.add_css_class(dot_class[name])
                header.append(dot)
                header.append(Gtk.Label(label=name, xalign=0))
                self.tab_box.append(header)
            for t in members:
                self.tab_box.append(self.tab_widget(t))
                self.order.append(t)

    def start_split(self, other):
        """Show other beside the current tab. Both stay awake, and the focused side drives the toolbar."""
        if not self.s["split_view"] or not self.current or other is self.current or other not in self.tabs:
            return
        if self.split:
            self.end_split()
        left = self.current
        if other.view is None:
            other.wake()
        for t in (left, other):
            self.stack.remove(t.box)  # a widget has one parent: out of the stack, into the paned
            t.box.add_css_class("split-pane")
            t.last_active = time.monotonic()
        self.paned.set_start_child(left.box)
        self.paned.set_end_child(other.box)
        self.paned.set_position(max(1, self.overlay.get_width() // 2))
        self.overlay.set_child(self.paned)
        self.split = (left, other)
        left.box.add_css_class("focused")
        for t in (left, other):
            focus = Gtk.EventControllerFocus()
            focus.connect("enter", lambda _c, tab=t: self.split and tab in self.split and tab is not self.current
                          and self.select(tab))
            t.box.add_controller(focus)
            t.split_focus = focus
        self.render_tabs()

    def end_split(self):
        if not self.split:
            return
        tabs, self.split = self.split, None
        self.paned.set_start_child(None)
        self.paned.set_end_child(None)
        for t in tabs:
            t.box.remove_css_class("split-pane")
            t.box.remove_css_class("focused")
            t.box.remove_controller(t.split_focus)
            self.stack.add_child(t.box)
        self.overlay.set_child(self.stack)
        if self.current:
            self.stack.set_visible_child(self.current.box)
        self.render_tabs()

    def toggle_split(self, *_):
        """Split with the next tab in the panel (or the previous one at the end); again to close it."""
        if self.split:
            return self.end_split()
        order = self.order or self.tabs
        if self.current in order and len(order) > 1:
            i = order.index(self.current)
            self.start_split(order[i + 1] if i + 1 < len(order) else order[i - 1])

    def pin_tile(self, tab):
        tile = Gtk.Button(child=self.tab_icon(tab) or Gtk.Image(icon_name="globe-symbolic", pixel_size=16),
                          tooltip_text=tab.title or tab.url)
        tile.add_css_class("pin-tile")
        for cls, on in (("active", tab is self.current or (self.split and tab in self.split)),
                        ("asleep", tab.view is None)):
            if on:
                tile.add_css_class(cls)
        tile.connect("clicked", lambda *_: self.select(tab))
        click = Gtk.GestureClick(button=0)
        click.connect("pressed", lambda g, _n, x, y: self.on_tab_click(g, tab, tile, x, y))
        tile.add_controller(click)
        return tile

    def update_nav(self):
        """Back/forward only when there's somewhere to go; the reload button stops a loading page."""
        v = self.current.view if self.current else None
        self.lookup_action("back").set_enabled(bool(v and v.can_go_back()))
        self.lookup_action("forward").set_enabled(bool(v and v.can_go_forward()))
        loading = bool(v and v.is_loading())
        self.b_reload.set_icon_name("process-stop-symbolic" if loading else "view-refresh-symbolic")
        self.b_reload.set_action_name("win.stop" if loading else "win.reload")
        self.b_reload.set_tooltip_text("Stop loading" if loading else self.tool_tooltip("reload"))

    def tool_tooltip(self, name):
        action = TOOLBAR_ACTIONS[name]
        keys = shortcuts.effective(self.s["shortcuts"])[action]
        hint = Gtk.accelerator_get_label(*Gtk.accelerator_parse(keys[0])[1:]) if keys else ""
        return f"{shortcuts.TITLES[action]} ({hint})" if hint else shortcuts.TITLES[action]

    def show_error(self, tab, uri, message):
        """Kite's own error page instead of WebKit's bare text. message None means a certificate problem."""
        if not tab.view:
            return False
        tab.showing_error, tab.error_pending = True, True  # never index an error page into history
        tab.view.load_alternate_html(self.app.error_page(uri, message), uri, None)
        return True

    def tab_icon(self, tab):
        if tab.loading:
            return Adw.Spinner(width_request=16, height_request=16)
        if not self.s["show_favicons"]:
            return None
        if tab.url.startswith("kite:"):
            return Gtk.Image(icon_name=APP_ID, pixel_size=16)
        if tab.favicon:
            return Gtk.Image(paintable=tab.favicon, pixel_size=16)
        return Gtk.Image(icon_name="globe-symbolic", pixel_size=16)

    def tab_widget(self, tab):
        inner = Gtk.Box(spacing=9)
        if icon := self.tab_icon(tab):
            inner.append(icon)
        title = Gtk.Label(label=tab.title or tab.url or "New tab", xalign=0, hexpand=True,
                          ellipsize=Pango.EllipsizeMode.END, max_width_chars=22)
        title.add_css_class("title")
        inner.append(title)
        if tab.view is None:
            badge = Gtk.Label(label="Sleeping")
            badge.add_css_class("badge")
            inner.append(badge)
        pick = Gtk.Button(child=inner, hexpand=True, tooltip_text=tab.url)
        pick.add_css_class("pick")
        pick.connect("clicked", lambda *_: self.select(tab))
        row = Gtk.Box()
        row.add_css_class("tab")
        if self.s["tab_layout"] == "horizontal":
            row.set_size_request(clamp("tab_width", self.s["tab_width"]), -1)
        row.append(pick)
        if tab.muted or (tab.view and tab.view.is_playing_audio()):
            audio = Gtk.Button(icon_name="audio-volume-muted-symbolic" if tab.muted else "audio-volume-high-symbolic",
                               tooltip_text="Unmute tab" if tab.muted else "Mute tab", valign=Gtk.Align.CENTER)
            audio.add_css_class("flat")
            audio.add_css_class("circular")
            audio.add_css_class("audio")
            audio.connect("clicked", lambda *_: self.toggle_mute(tab))
            row.append(audio)
        if not tab.pinned and self.s["close_buttons"] != "never":
            close = Gtk.Button(icon_name="window-close-symbolic", tooltip_text="Close tab", valign=Gtk.Align.CENTER)
            close.add_css_class("flat")
            close.add_css_class("circular")
            close.add_css_class("close")
            close.connect("clicked", lambda *_: self.close_tab(tab))
            row.append(close)
        for cls, on in (("active", tab is self.current or (self.split and tab in self.split)),
                        ("asleep", tab.view is None)):
            if on:
                row.add_css_class(cls)
        click = Gtk.GestureClick(button=0)
        click.connect("pressed", lambda g, _n, x, y: self.on_tab_click(g, tab, row, x, y))
        row.add_controller(click)
        return row

    def on_tab_click(self, gesture, tab, row, x, y):
        button = gesture.get_current_button()
        if button == Gdk.BUTTON_SECONDARY:
            self.show_tab_menu(tab, row, x, y)
        elif button == Gdk.BUTTON_MIDDLE:
            GLib.idle_add(self.close_tab, tab)  # not mid-event: closing destroys this row
        else:
            return
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)

    def show_tab_menu(self, tab, row, x, y):
        def item(section, label, action):
            entry = Gio.MenuItem.new(label, None)
            entry.set_action_and_target_value("win." + action, GLib.Variant("i", tab.id))
            section.append_item(entry)

        page, close = Gio.Menu(), Gio.Menu()
        item(page, "Reload", "tab-reload")
        item(page, "Duplicate", "tab-duplicate")
        item(page, "Unpin tab" if tab.pinned else "Pin tab", "tab-pin")
        item(page, "Unmute tab" if tab.muted else "Mute tab", "tab-mute")
        if self.split and tab in self.split:
            close_split = Gio.MenuItem.new("Close split view", "win.split")
            page.append_item(close_split)
        elif tab is not self.current and self.s["split_view"]:
            item(page, "Show beside the current tab", "tab-split")
        if tab.view and tab is not self.current and not (self.split and tab in self.split):
            item(page, "Put to sleep", "tab-sleep")
        if tab.url.startswith(("http:", "https:")):
            item(page, "Remove bookmark" if self.app.bookmarks.has(tab.url) else "Bookmark", "tab-bookmark")
        item(close, "Close tab", "tab-close")
        item(close, "Close other tabs", "tab-close-others")
        menu = Gio.Menu()
        menu.append_section(None, page)
        menu.append_section(None, close)
        self.tab_menu.set_menu_model(menu)
        ok, point = row.compute_point(self.tab_panel, Graphene.Point().init(x, y))
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = (int(point.x), int(point.y), 1, 1) if ok else (0, 0, 1, 1)
        self.tab_menu.set_pointing_to(rect)
        self.tab_menu.popup()

    def sleep_idle_tabs(self):
        if not self.s["tab_sleep"]:
            return GLib.SOURCE_CONTINUE
        cutoff = time.monotonic() - self.s["sleep_minutes"] * 60
        visible = self.split or (self.current,)  # both halves of a split view are on screen
        awake = [t for t in self.tabs if t not in visible and t.view and not t.view.is_playing_audio()]
        for t in awake:
            if t.last_active < cutoff:
                t.sleep()
        if self.s["sleep_on_low_memory"] and low_memory():
            # Free the two least recently used background tabs now, rather than after the timeout.
            for t in sorted((t for t in awake if t.view), key=lambda t: t.last_active)[:2]:
                t.sleep()
        return GLib.SOURCE_CONTINUE

    # ---- session ------------------------------------------------------------
    def session_changed(self):
        if not self.private:
            self.app.schedule_save()

    def session_state(self):
        tabs = [t for t in self.tabs if t.url]
        return {"tabs": [{"url": t.url, "title": t.title, "pinned": t.pinned, "muted": t.muted} for t in tabs],
                "selected": tabs.index(self.current) if self.current in tabs else 0}

    def on_close_request(self, *_):
        GLib.source_remove(self.sleep_timer)
        if self.refresh_downloads in self.app.downloads.listeners:
            self.app.downloads.listeners.remove(self.refresh_downloads)
        if not self.private:
            self.app.window_closing(self)
        return False

    # ---- navigation policy and permissions ----------------------------------
    def on_decide_policy(self, view, decision, kind):
        if kind == WebKit.PolicyDecisionType.NAVIGATION_ACTION:
            action = decision.get_navigation_action()
            background = action.get_mouse_button() == 2 or action.get_modifiers() & Gdk.ModifierType.CONTROL_MASK
            if background and action.get_navigation_type() == WebKit.NavigationType.LINK_CLICKED:
                decision.ignore()
                tab = next((t for t in self.tabs if t.view is view), None)
                index = self.tabs.index(tab) + 1 if tab else None
                self.open_tab(action.get_request().get_uri(), select=self.s["switch_to_new_tabs"], index=index)
                return True
        elif kind == WebKit.PolicyDecisionType.RESPONSE and decision.is_main_frame_main_resource():
            headers = decision.get_response().get_http_headers()
            disposition = (headers.get_one("Content-Disposition") or "") if headers else ""
            if not decision.is_mime_type_supported() or disposition.lower().startswith("attachment"):
                decision.download()
                return True
        return False

    def on_permission_request(self, view, request):
        host = urlparse(view.get_uri() or "").hostname or "this page"
        kind, question = permission_question(request, host)
        if kind is None:
            return False
        saved = sitepanel.remembered(self, host)
        if kind in saved:
            request.allow() if saved[kind] else request.deny()
            return True
        remember = Gtk.CheckButton(halign=Gtk.Align.CENTER, label=(
            "Remember until this window closes" if self.private else f"Remember for {host}"))
        alert = Adw.AlertDialog(heading=question, extra_child=remember)
        alert.add_response("deny", "Block")
        alert.add_response("allow", "Allow")
        alert.set_response_appearance("allow", Adw.ResponseAppearance.SUGGESTED)
        alert.set_default_response("deny")
        alert.set_close_response("deny")

        def answered(_alert, response):
            allowed = response == "allow"
            if remember.get_active() and self.private:
                self.permissions[host, kind] = allowed  # forgotten with the window
            elif remember.get_active():  # the site panel lists these and can forget them
                perms = valid_site_permissions(self.s["site_permissions"])
                perms.setdefault(host, {})[kind] = allowed
                self.s.set("site_permissions", perms)
            request.allow() if allowed else request.deny()

        alert.connect("response", answered)
        alert.present(self)
        return True

    # ---- omnibox ------------------------------------------------------------
    def editing_url(self):
        focus = self.get_focus()
        return bool(focus and focus.is_ancestor(self.url))

    def sync_url(self):
        url = self.current.url if self.current else ""
        icon = ("channel-secure-symbolic" if url.startswith("https:") else
                "channel-insecure-symbolic" if url.startswith("http:") else "system-search-symbolic")
        self.url.set_icon_from_icon_name(Gtk.EntryIconPosition.PRIMARY, icon)
        web = url.startswith(("http:", "https:"))
        self.b_reader.set_visible(self.s["show_reader"] and not self.narrow and web)  # useless on Kite's own pages
        marked = web and self.app.bookmarks.has(url)
        self.url.set_icon_from_icon_name(Gtk.EntryIconPosition.SECONDARY,
                                         ("starred-symbolic" if marked else "non-starred-symbolic") if web else None)
        if web:
            self.url.set_icon_tooltip_text(Gtk.EntryIconPosition.SECONDARY,
                                           "Remove bookmark (Ctrl+D)" if marked else "Bookmark this page (Ctrl+D)")
        if not self.editing_url():
            self.url.set_text("" if url.startswith("kite:") else url)
            self.hide_suggestions()

    def on_url_activate(self, entry):
        row = self.suggest_list.get_selected_row()
        target = self.suggestion_urls[row.get_index()] if row else to_url(entry.get_text(), self.s.search_engine()[1], self.s["keywords"])
        self.hide_suggestions()
        if self.current and self.current.view:
            self.current.view.load_uri(target)
            self.current.view.grab_focus()

    def build_suggestions(self):
        self.suggest_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, can_focus=False)
        self.suggest_list.connect("row-activated", lambda _l, row: self.open_suggestion(row.get_index()))
        self.suggest_pop = Gtk.Popover(child=self.suggest_list, autohide=False, has_arrow=False,
                                       position=Gtk.PositionType.BOTTOM, halign=Gtk.Align.START, can_focus=False)
        self.suggest_pop.add_css_class("suggestions")
        self.suggest_pop.set_parent(self.url)

    def on_url_changed(self, entry):
        text = entry.get_text().strip()
        if not (self.s["suggestions"] and text and self.editing_url()):
            self.hide_suggestions()
            return
        rows = [("starred-symbolic", b["url"], b.get("title", "")) for b in self.app.bookmarks.search(text)[:3]]
        if not self.private:
            seen = {u for _i, u, _t in rows}
            rows += [("document-open-recent-symbolic", u, t) for u, t in self.history.suggest(text, 8) if u not in seen]
        rows = rows[:7]
        self.suggest_list.remove_all()
        self.suggestion_urls = [u for _i, u, _t in rows]
        for icon, url, title in rows:
            box = Gtk.Box(spacing=10)
            box.append(Gtk.Image(icon_name=icon))
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            col.append(Gtk.Label(label=title or url, xalign=0, ellipsize=Pango.EllipsizeMode.END))
            link = Gtk.Label(label=url, xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
            link.add_css_class("url")
            col.append(link)
            box.append(col)
            self.suggest_list.append(Gtk.ListBoxRow(child=box, can_focus=False))
        if rows:
            self.suggest_pop.set_size_request(self.url.get_width(), -1)
            self.suggest_pop.popup()
        else:
            self.hide_suggestions()

    def on_url_key(self, _ctl, keyval, _code, _state):
        if keyval == Gdk.KEY_Escape:
            if self.suggest_pop.get_visible():
                self.hide_suggestions()
            else:
                self.sync_url_text()
                self.current and self.current.view and self.current.view.grab_focus()
            return True
        if keyval in (Gdk.KEY_Down, Gdk.KEY_Up) and self.suggest_pop.get_visible():
            row = self.suggest_list.get_selected_row()
            i = (row.get_index() if row else -1) + (1 if keyval == Gdk.KEY_Down else -1)
            target = self.suggest_list.get_row_at_index(i) if i >= 0 else None
            self.suggest_list.select_row(target) if target else self.suggest_list.unselect_all()
            return True
        return False

    def sync_url_text(self):
        url = self.current.url if self.current else ""
        self.url.set_text("" if url.startswith("kite:") else url)

    def open_suggestion(self, index):
        if 0 <= index < len(self.suggestion_urls) and self.current and self.current.view:
            self.current.view.load_uri(self.suggestion_urls[index])
            self.hide_suggestions()
            self.current.view.grab_focus()

    def hide_suggestions(self):
        self.suggest_list.unselect_all()
        self.suggest_pop.popdown()
        return GLib.SOURCE_REMOVE

    # ---- find in page -------------------------------------------------------
    def build_findbar(self):
        self.find_entry = Gtk.SearchEntry(placeholder_text="Find in page", width_chars=20)
        self.find_entry.connect("search-changed", self.find_changed)
        self.find_entry.connect("activate", self.find_next)
        self.find_entry.connect("next-match", self.find_next)
        self.find_entry.connect("previous-match", self.find_prev)
        self.find_entry.connect("stop-search", lambda *_: self.find_close(focus_page=True))
        self.find_label = Gtk.Label(width_chars=10, xalign=0)
        self.find_label.add_css_class("dim-label")
        self.find_label.add_css_class("caption")
        bar = Gtk.Box(spacing=4)
        bar.add_css_class("findbar")
        bar.append(self.find_entry)
        bar.append(self.find_label)
        for icon, tip, cb in (("go-up-symbolic", "Previous match (Ctrl+Shift+G)", self.find_prev),
                              ("go-down-symbolic", "Next match (Ctrl+G)", self.find_next),
                              ("window-close-symbolic", "Close (Esc)", lambda *_: self.find_close(focus_page=True))):
            b = Gtk.Button(icon_name=icon, tooltip_text=tip)
            b.add_css_class("flat")
            b.add_css_class("circular")
            b.connect("clicked", cb)
            bar.append(b)
        self.find_revealer = Gtk.Revealer(child=bar, halign=Gtk.Align.END, valign=Gtk.Align.START, margin_top=10,
                                          margin_end=14, transition_type=Gtk.RevealerTransitionType.CROSSFADE)
        return self.find_revealer

    def finder(self):
        return self.current.view.get_find_controller() if self.current and self.current.view else None

    def find_open(self, *_):
        self.find_revealer.set_reveal_child(True)
        self.find_entry.grab_focus()
        self.find_entry.select_region(0, -1)

    def find_changed(self, entry):
        finder, text = self.finder(), entry.get_text()
        if not finder:
            return
        if not text:
            finder.search_finish()
            self.find_status("")
            return
        options = WebKit.FindOptions.CASE_INSENSITIVE | WebKit.FindOptions.WRAP_AROUND
        finder.search(text, options, 1000)
        finder.count_matches(text, options, 1000)

    def find_next(self, *_):
        if not self.find_revealer.get_reveal_child():
            return self.find_open()
        if (finder := self.finder()) and self.find_entry.get_text():
            finder.search_next()

    def find_prev(self, *_):
        if (finder := self.finder()) and self.find_entry.get_text():
            finder.search_previous()

    def find_status(self, text):
        self.find_label.set_label(text)

    def find_close(self, focus_page=False):
        if not self.find_revealer.get_reveal_child():
            return
        self.find_revealer.set_reveal_child(False)
        if finder := self.finder():
            finder.search_finish()
        if focus_page and self.current and self.current.view:
            self.current.view.grab_focus()

    # ---- zoom, reader, bookmarks --------------------------------------------
    def apply_zoom(self, tab):
        default = self.s["default_zoom"]
        zoom = self.s["site_zoom"].get(urlparse(tab.url).hostname or "", default)
        tab.view.set_zoom_level(zoom if isinstance(zoom, (int, float)) and 0.3 <= zoom <= 3 else default)
        if tab is self.current:
            self.update_zoom_badge()

    def zoom(self, direction):
        tab = self.current
        if not (tab and tab.view):
            return
        default = self.s["default_zoom"]
        level = default if direction == 0 else next_zoom(tab.view.get_zoom_level(), direction)
        tab.view.set_zoom_level(level)
        host = urlparse(tab.url).hostname
        if host:  # remembered per site, like Firefox
            zooms = dict(self.s["site_zoom"])
            if abs(level - default) < 1e-3:
                zooms.pop(host, None)
            else:
                zooms[host] = level
            self.s.set("site_zoom", zooms)
        self.update_zoom_badge()

    def update_zoom_badge(self):
        default = self.s["default_zoom"]
        level = self.current.view.get_zoom_level() if self.current and self.current.view else default
        self.zoom_badge.set_label(f"{round(level * 100)}%")
        self.zoom_badge.set_visible(abs(level - default) > 1e-3)

    def toggle_reader(self, *_):
        tab = self.current
        if not (tab and tab.view and tab.url.startswith(("http:", "https:"))):
            return

        def done(view, result):
            try:
                outcome = view.evaluate_javascript_finish(result).to_string()
            except GLib.Error:
                return
            if outcome == "none":
                self.toast("Kite can't find an article on this page")

        # The "kite" world keeps page scripts from tampering with the builder's globals.
        tab.view.evaluate_javascript(READER_JS, -1, "kite", None, None, done)

    def toggle_bookmark(self, *_, tab=None):
        tab = tab or self.current
        if not (tab and tab.url.startswith(("http:", "https:"))):
            return
        added = self.app.bookmarks.toggle(tab.url, tab.title)
        self.toast("Bookmark added" if added else "Bookmark removed")
        self.sync_url()
        self.app.reload_start_pages()

    def build_bookmarks_popover(self):
        search = Gtk.SearchEntry(placeholder_text="Search bookmarks")
        listing = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        listing.add_css_class("navigation-sidebar")
        empty = Gtk.Label(label="Bookmark pages with Ctrl+D or the star in the address bar.", wrap=True,
                          max_width_chars=34, margin_top=18, margin_bottom=18)
        empty.add_css_class("dim-label")
        listing.set_placeholder(empty)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, width_request=360)
        box.append(search)
        box.append(Gtk.ScrolledWindow(child=listing, max_content_height=420, propagate_natural_height=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER))
        pop = Gtk.Popover(child=box)
        urls = []

        def open_bookmark(url):
            pop.popdown()
            if self.current and self.current.view:
                self.current.view.load_uri(url)
            else:
                self.open_tab(url)

        def remove(url):
            self.app.bookmarks.toggle(url, "")
            fill()
            self.sync_url()
            self.app.reload_start_pages()

        def fill(*_):
            listing.remove_all()
            urls.clear()
            for b in self.app.bookmarks.search(search.get_text().strip()):
                urls.append(b["url"])
                row = Gtk.Box(spacing=8)
                col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
                col.append(Gtk.Label(label=b.get("title") or b["url"], xalign=0, ellipsize=Pango.EllipsizeMode.END))
                host = Gtk.Label(label=urlparse(b["url"]).hostname or b["url"], xalign=0,
                                 ellipsize=Pango.EllipsizeMode.END)
                host.add_css_class("dim-label")
                host.add_css_class("caption")
                col.append(host)
                row.append(col)
                rm = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text="Remove bookmark", valign=Gtk.Align.CENTER)
                rm.add_css_class("flat")
                rm.add_css_class("circular")
                rm.connect("clicked", lambda _b, u=b["url"]: remove(u))
                row.append(rm)
                listing.append(row)

        listing.set_activate_on_single_click(True)
        listing.connect("row-activated", lambda _l, row: open_bookmark(urls[row.get_index()]))
        search.connect("search-changed", fill)
        pop.connect("show", lambda *_: (search.set_text(""), fill(), search.grab_focus()))
        return pop

    # ---- downloads ----------------------------------------------------------
    def build_downloads_popover(self):
        self.dl_list = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.dl_list.add_css_class("navigation-sidebar")
        heading = Gtk.Label(label="Downloads", xalign=0, hexpand=True)
        heading.add_css_class("heading")
        clear = Gtk.Button(label="Clear finished")
        clear.add_css_class("flat")
        clear.connect("clicked", lambda *_: self.app.downloads.clear())
        top = Gtk.Box(spacing=6, margin_start=6)
        top.append(heading)
        top.append(clear)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=380)
        box.append(top)
        box.append(Gtk.ScrolledWindow(child=self.dl_list, max_content_height=400, propagate_natural_height=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER))
        self.dl_popover = Gtk.Popover(child=box)
        self.dl_popover.connect("show", lambda *_: self.fill_downloads())
        return self.dl_popover

    def fill_downloads(self):
        self.dl_list.remove_all()
        for item in self.app.downloads.items:
            self.dl_list.append(download_row(item, self, self.app.downloads))

    def refresh_downloads(self, started=False, finished=None):
        self.layout_toolbar()
        if self.dl_popover.get_visible():
            self.fill_downloads()
        if started and self.is_active():
            self.b_downloads.popup()
        if finished and self.is_active():
            self.toast(f"Downloaded {finished['name']}")

    def show_downloads(self, *_):
        if self.app.downloads.items:
            self.b_downloads.popup()
        else:
            self.toast("No downloads yet")

    # ---- Memory Finder ------------------------------------------------------
    def index_page(self, tab):
        url = tab.url
        if self.private or not (self.s["memory_search"] and url.startswith(("http://", "https://")) and tab.view):
            return

        def done(view, result):
            try:
                text = view.evaluate_javascript_finish(result).to_string()
            except GLib.Error:
                return
            self.history.add(url, tab.title, text or "")

        tab.view.evaluate_javascript("document.body ? document.body.innerText : ''", -1, "kite", None, None, done)

    def open_memory_finder(self, *_):
        entry = Gtk.SearchEntry(placeholder_text="Describe a page you saw, like “rust async article from last week”")
        entry.add_css_class("palette-entry")
        results = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE, margin_start=8, margin_end=8,
                              margin_top=8, margin_bottom=8)
        empty = Gtk.Label(wrap=True, justify=Gtk.Justification.CENTER, margin_top=40)
        empty.add_css_class("dim-label")
        results.set_placeholder(empty)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.add_css_class("palette")
        box.append(entry)
        box.append(Gtk.Separator())
        box.append(Gtk.ScrolledWindow(child=results, vexpand=True))
        dialog = Adw.Dialog(title="Memory Finder", content_width=700, content_height=500, child=box)
        urls = []

        def open_url(url):
            dialog.close()
            self.open_tab(url)

        def update(*_):
            results.remove_all()
            urls.clear()
            q = entry.get_text().strip()
            empty.set_label(f"Nothing you visited matches “{q}”. Try fewer or different words." if q else
                            "Pages you visit show up here once they finish loading.")
            for url, title, snippet, visited in self.history.search(q):
                urls.append(url)
                col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                top = Gtk.Box(spacing=12)
                name = Gtk.Label(label=title or url, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
                name.add_css_class("heading")
                when = Gtk.Label(label=ago(visited))
                when.add_css_class("meta")
                top.append(name)
                top.append(when)
                host = Gtk.Label(label=urlparse(url).hostname or url, xalign=0, ellipsize=Pango.EllipsizeMode.END)
                host.add_css_class("meta")
                text = Gtk.Label(label=" ".join(snippet.split()), xalign=0, wrap=True, lines=2,
                                 ellipsize=Pango.EllipsizeMode.END)
                text.add_css_class("snippet")
                for w in (top, host, text):
                    col.append(w)
                results.append(Gtk.ListBoxRow(child=col))

        def on_key(_ctl, keyval, _code, _state):
            if keyval == Gdk.KEY_Down and (row := results.get_row_at_index(0)):
                row.grab_focus()
                return True
            return False

        keys = Gtk.EventControllerKey()
        keys.connect("key-pressed", on_key)
        entry.add_controller(keys)
        entry.connect("search-changed", update)
        entry.connect("activate", lambda *_: urls and open_url(urls[0]))
        results.connect("row-activated", lambda _l, row: open_url(urls[row.get_index()]))
        update()
        dialog.present(self)
        entry.grab_focus()
