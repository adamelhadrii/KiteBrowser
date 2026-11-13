"""Command palette: one search box for open tabs, actions, Settings pages, bookmarks and history."""
from urllib.parse import urlparse

from gi.repository import Adw, Gdk, Gtk, Pango

import shortcuts

KIND_ORDER = {"tab": 0, "action": 1, "setting": 2, "bookmark": 3, "history": 4}
KIND_ICONS = {"tab": "view-paged-symbolic", "action": "system-run-symbolic", "setting": "emblem-system-symbolic",
              "bookmark": "starred-symbolic", "history": "document-open-recent-symbolic"}
KIND_LABELS = {"tab": "Open tab", "action": "Action", "setting": "Settings", "bookmark": "Bookmark",
               "history": "History"}


def score(query, title, subtitle=""):
    """How well an item matches: 4 title starts with it, 3 a title word does, 2 inside the title, 1 elsewhere, 0 no."""
    q, t, sub = query.lower().strip(), title.lower(), subtitle.lower()
    if not q:
        return 1
    if t.startswith(q):
        return 4
    if any(word.startswith(q) for word in t.split()):
        return 3
    if q in t:
        return 2
    if q in sub or all(word in t or word in sub for word in q.split()):
        return 1
    return 0


def rank(query, items, limit=12):
    """items: (kind, title, subtitle, payload). Best match first; ties go tabs, actions, settings, bookmarks, history."""
    scored = [(score(query, item[1], item[2]), i, item) for i, item in enumerate(items)]
    hits = sorted((x for x in scored if x[0]), key=lambda x: (-x[0], KIND_ORDER[x[2][0]], x[1]))
    return [item for _s, _i, item in hits[:limit]]


def open_palette(win):
    from preferences import PAGE_ICONS, open_settings_dialog
    app = win.app
    items = []
    for w in app.browser_windows():
        for t in w.tabs:
            items.append(("tab", t.title or t.url or "New tab", urlparse(t.url).hostname or t.url, (w, t)))
    current = shortcuts.effective(app.s["shortcuts"])
    for _section, name, title, _defaults in shortcuts.ACTIONS:
        action = win.lookup_action(name)
        if name != "palette" and action and action.get_enabled():
            keys = current[name]
            hint = Gtk.accelerator_get_label(*Gtk.accelerator_parse(keys[0])[1:]) if keys else ""
            items.append(("action", title, hint, name))
    items += [("setting", f"Settings: {page}", "", page) for page in PAGE_ICONS]
    items += [("bookmark", b.get("title") or b["url"], b["url"], b["url"]) for b in app.bookmarks.all()]

    entry = Gtk.SearchEntry(placeholder_text="Search tabs, actions, settings, bookmarks and history")
    entry.add_css_class("palette-entry")
    results = Gtk.ListBox(selection_mode=Gtk.SelectionMode.BROWSE, margin_start=8, margin_end=8,
                          margin_top=8, margin_bottom=8)
    empty = Gtk.Label(label="Nothing matches. Try another word.", margin_top=40)
    empty.add_css_class("dim-label")
    results.set_placeholder(empty)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    box.add_css_class("palette")
    box.append(entry)
    box.append(Gtk.Separator())
    box.append(Gtk.ScrolledWindow(child=results, vexpand=True))
    dialog = Adw.Dialog(title="Command palette", content_width=640, content_height=460, child=box)
    shown = []

    def run(item):
        kind, _title, _sub, payload = item
        dialog.close()
        if kind == "tab":
            w, t = payload
            w.present()
            w.select(t)
        elif kind == "action":
            win.activate_action("win." + payload, None)
        elif kind == "setting":
            open_settings_dialog(win, app).set_visible_page_name(payload)
        else:
            win.open_tab(payload)

    def update(*_):
        query = entry.get_text()
        # History is searched only once there's something to search for, and never from a private window.
        extra = [] if win.private or not query.strip() else \
            [("history", t or u, u, u) for u, t in app.history.suggest(query.strip(), 8)]
        shown[:] = rank(query, items + extra)
        results.remove_all()
        for kind, title, sub, _payload in shown:
            row = Gtk.Box(spacing=12)
            row.append(Gtk.Image(icon_name=KIND_ICONS[kind]))
            col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, hexpand=True)
            col.append(Gtk.Label(label=title, xalign=0, ellipsize=Pango.EllipsizeMode.END))
            if sub:
                detail = Gtk.Label(label=sub, xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE)
                detail.add_css_class("meta")
                col.append(detail)
            row.append(col)
            tag = Gtk.Label(label=KIND_LABELS[kind])
            tag.add_css_class("meta")
            row.append(tag)
            results.append(row)
        if shown:
            results.select_row(results.get_row_at_index(0))

    def on_key(_ctl, keyval, _code, _state):
        if keyval in (Gdk.KEY_Down, Gdk.KEY_Up) and shown:
            row = results.get_selected_row()
            i = max(0, min(len(shown) - 1, (row.get_index() if row else -1) + (1 if keyval == Gdk.KEY_Down else -1)))
            results.select_row(results.get_row_at_index(i))
            return True
        return False

    keys = Gtk.EventControllerKey()
    keys.connect("key-pressed", on_key)
    entry.add_controller(keys)
    entry.connect("search-changed", update)
    entry.connect("activate", lambda *_: shown and run(shown[(results.get_selected_row() or
                                                              results.get_row_at_index(0)).get_index()]))
    results.connect("row-activated", lambda _l, row: run(shown[row.get_index()]))
    update()
    dialog.present(win)
    entry.grab_focus()
    return dialog
