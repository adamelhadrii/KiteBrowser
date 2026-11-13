"""Every window action with its default shortcuts, plus validation and rebinding of user overrides."""
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, Gtk  # noqa: E402

# (section, action name, title, default accelerators)
ACTIONS = [
    ("Tabs", "new-tab", "New tab", ["<Ctrl>t"]),
    ("Tabs", "close-tab", "Close tab", ["<Ctrl>w", "<Ctrl>F4"]),
    ("Tabs", "reopen-tab", "Reopen closed tab", ["<Ctrl><Shift>t"]),
    ("Tabs", "next-tab", "Next tab", ["<Ctrl>Tab", "<Ctrl>Page_Down"]),
    ("Tabs", "prev-tab", "Previous tab", ["<Ctrl><Shift>Tab", "<Ctrl><Shift>ISO_Left_Tab", "<Ctrl>Page_Up"]),
    ("Tabs", "toggle-tabs", "Show or hide the tab panel", ["<Ctrl>b"]),
    ("Windows", "new-window", "New window", ["<Ctrl>n"]),
    ("Windows", "new-private", "New private window", ["<Ctrl><Shift>p"]),
    ("Windows", "fullscreen", "Full screen", ["F11"]),
    ("Page", "focus-url", "Go to the address bar", ["<Ctrl>l", "F6", "<Alt>d"]),
    ("Page", "back", "Back", ["<Alt>Left"]),
    ("Page", "forward", "Forward", ["<Alt>Right"]),
    ("Page", "reload", "Reload", ["<Ctrl>r", "F5"]),
    ("Page", "hard-reload", "Reload, ignoring the cache", ["<Ctrl><Shift>r", "<Shift>F5"]),
    ("Page", "home", "Home", ["<Alt>Home"]),
    ("Page", "find", "Find in page", ["<Ctrl>f"]),
    ("Page", "find-next", "Next match", ["<Ctrl>g", "F3"]),
    ("Page", "find-prev", "Previous match", ["<Ctrl><Shift>g", "<Shift>F3"]),
    ("Page", "zoom-in", "Zoom in", ["<Ctrl>plus", "<Ctrl>equal", "<Ctrl>KP_Add"]),
    ("Page", "zoom-out", "Zoom out", ["<Ctrl>minus", "<Ctrl>KP_Subtract"]),
    ("Page", "zoom-reset", "Reset zoom", ["<Ctrl>0", "<Ctrl>KP_0"]),
    ("Page", "reader", "Reader view", ["<Ctrl><Alt>r", "F9"]),
    ("Page", "print", "Print", ["<Ctrl>p"]),
    ("Page", "bookmark", "Bookmark this page", ["<Ctrl>d"]),
    ("Kite", "bookmarks", "Bookmarks", ["<Ctrl><Shift>o"]),
    ("Kite", "downloads", "Downloads", ["<Ctrl><Shift>y", "<Ctrl>j"]),
    ("Kite", "memory", "History and Memory Finder", ["<Ctrl><Shift>f", "<Ctrl>h"]),
    ("Kite", "devtools", "Developer tools", ["F12", "<Ctrl><Shift>i"]),
    ("Kite", "palette", "Command palette", ["<Ctrl><Shift>k"]),
    ("Tabs", "split", "Split view with the next tab", ["<Ctrl><Alt>s"]),
    ("Kite", "focus-mode", "Focus mode", ["<Ctrl><Shift>m"]),
    ("Page", "screenshot", "Save a screenshot of the page", ["<Ctrl><Shift>s"]),
    ("Kite", "settings", "Settings", ["<Ctrl>comma"]),
    ("Kite", "shortcuts", "Keyboard shortcuts", ["<Ctrl>question", "<Ctrl>slash"]),
]
DEFAULTS = {name: accels for _s, name, _t, accels in ACTIONS}
TITLES = {name: title for _s, name, title, _a in ACTIONS}
GOTO = [f"<Ctrl>{i}" for i in range(1, 10)] + [f"<Alt>{i}" for i in range(1, 10)]  # fixed: go to tab N
MODIFIERS = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK


def normalize(accel):
    ok, key, mods = Gtk.accelerator_parse(accel)
    return Gtk.accelerator_name(key, mods) if ok and key else None


def is_valid(accel):
    """A bare letter would be swallowed in every text field, so require Ctrl/Alt/Super unless it's an F-key."""
    if not isinstance(accel, str):
        return False
    ok, key, mods = Gtk.accelerator_parse(accel)
    if not ok or not key:
        return False
    return bool(mods & MODIFIERS) or Gdk.KEY_F1 <= key <= Gdk.KEY_F35


def effective(overrides):
    """name -> accelerators in effect: defaults with valid overrides applied ([] means unbound)."""
    result = {name: list(accels) for name, accels in DEFAULTS.items()}
    for name, accels in (overrides if isinstance(overrides, dict) else {}).items():
        if name in result and isinstance(accels, list) and all(is_valid(a) for a in accels):
            result[name] = list(accels)
    return result


def rebind(overrides, name, accel):
    """New overrides with accel bound to name only; returns (overrides, titles of actions it was taken from).

    accel None unbinds name. Raises ValueError for an invalid or reserved accelerator.
    """
    new = dict(overrides if isinstance(overrides, dict) else {})
    if accel is None:
        new[name] = []
        return new, []
    if not is_valid(accel):
        raise ValueError("Use Ctrl, Alt or Super with the key, or an F-key")
    key = normalize(accel)
    if key in {normalize(a) for a in GOTO}:
        raise ValueError("Ctrl or Alt plus a number already switches tabs")
    taken = []
    for other, accels in effective(overrides).items():
        if other != name and key in {normalize(a) for a in accels}:
            new[other] = [a for a in accels if normalize(a) != key]
            taken.append(TITLES[other])
    new[name] = [accel]
    return new, taken
