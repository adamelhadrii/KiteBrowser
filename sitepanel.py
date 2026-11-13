"""Site panel, opened from the padlock: connection, tracker blocking, zoom, remembered permissions and site data."""
from urllib.parse import urlparse

from gi.repository import Adw, Gtk, WebKit

from settings import valid_hosts, valid_site_permissions


def build(win):
    pop = Gtk.Popover(position=Gtk.PositionType.BOTTOM)
    pop.add_css_class("site-panel")
    pop.set_parent(win.url)
    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, width_request=360,
                  margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
    pop.set_child(box)
    pop.connect("show", lambda *_: fill(win, box, pop))
    return pop


def connection(tab):
    """(icon, text) describing how the current page was loaded."""
    if tab.url.startswith("http:"):
        return "channel-insecure-symbolic", "This connection isn't secure. Don't enter passwords or card details here."
    ok, _certificate, errors = tab.view.get_tls_info() if tab.view else (False, None, 0)
    if ok and not errors:
        return "channel-secure-symbolic", "The connection is secure and the certificate is valid."
    return "dialog-warning-symbolic", "The connection is encrypted, but its certificate has problems."


def remembered(win, host):
    """{kind: allowed} the user told Kite to remember for host."""
    if win.private:
        return {kind: allowed for (h, kind), allowed in win.permissions.items() if h == host}
    return dict(valid_site_permissions(win.s["site_permissions"]).get(host, {}))


def forget(win, host, kind):
    if win.private:
        win.permissions.pop((host, kind), None)
        return
    perms = valid_site_permissions(win.s["site_permissions"])
    perms.get(host, {}).pop(kind, None)
    win.s.set("site_permissions", {h: k for h, k in perms.items() if k})


def clear_site_data(win, tab, host):
    manager = win.session.get_website_data_manager()

    def removed(m, result):
        m.remove_finish(result)
        win.toast(f"Cleared cookies and data for {host}")
        if tab.view:
            tab.view.reload()

    def fetched(m, result):
        mine = [d for d in m.fetch_finish(result) if host == d.get_name() or host.endswith("." + d.get_name())]
        if not mine:
            win.toast(f"{host} has no saved cookies or data")
            return
        m.remove(WebKit.WebsiteDataTypes.ALL, mine, None, removed)

    manager.fetch(WebKit.WebsiteDataTypes.ALL, None, fetched)


def fill(win, box, pop):
    while child := box.get_first_child():
        box.remove(child)
    tab, s = win.current, win.s
    host = urlparse(tab.url).hostname if tab and tab.url.startswith(("http:", "https:")) else None
    if not host:
        box.append(Gtk.Label(label="This is one of Kite's own pages.", wrap=True, margin_top=6, margin_bottom=6))
        return
    title = Gtk.Label(label=host, xalign=0, wrap=True)
    title.add_css_class("title-4")
    box.append(title)
    icon, text = connection(tab)
    line = Gtk.Box(spacing=10)
    line.append(Gtk.Image(icon_name=icon, valign=Gtk.Align.START))
    status = Gtk.Label(label=text, xalign=0, wrap=True, hexpand=True)
    status.add_css_class("dim-label")
    line.append(status)
    box.append(line)

    rows = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
    rows.add_css_class("boxed-list")
    box.append(rows)

    blocking = Adw.SwitchRow(title="Block trackers on this site", active=host not in s["tracker_exceptions"],
                             sensitive=s["block_trackers"])
    if not s["block_trackers"]:
        blocking.set_subtitle("Tracker blocking is off in Settings → Privacy")

    def toggle_blocking(row, _):
        others = [h for h in valid_hosts(s["tracker_exceptions"]) if h != host]
        s.set("tracker_exceptions", others if row.get_active() else others + [host])
        if tab.view:
            tab.view.reload()  # the new rules apply to the next load

    blocking.connect("notify::active", toggle_blocking)
    rows.append(blocking)

    level = tab.view.get_zoom_level() if tab.view else 1.0
    zoom = Adw.ActionRow(title="Zoom", subtitle=f"{round(level * 100)}%")
    reset = Gtk.Button(label="Reset", valign=Gtk.Align.CENTER, sensitive=abs(level - s["default_zoom"]) > 1e-3)
    reset.add_css_class("flat")
    reset.connect("clicked", lambda *_: (win.zoom(0), zoom.set_subtitle(f"{round(s['default_zoom'] * 100)}%"),
                                         reset.set_sensitive(False)))
    zoom.add_suffix(reset)
    rows.append(zoom)

    for kind, allowed in sorted(remembered(win, host).items()):
        row = Adw.ActionRow(title=kind.capitalize(), subtitle="Allowed" if allowed else "Blocked")
        forget_button = Gtk.Button(label="Forget", valign=Gtk.Align.CENTER,
                                   tooltip_text="Ask again next time the site wants this")
        forget_button.add_css_class("flat")
        forget_button.connect("clicked", lambda _b, k=kind, r=row: (forget(win, host, k), rows.remove(r)))
        row.add_suffix(forget_button)
        rows.append(row)

    clear = Adw.ButtonRow(title="Clear cookies and data for this site")
    clear.add_css_class("destructive-action")

    def confirm(*_):
        pop.popdown()
        alert = Adw.AlertDialog(heading=f"Clear data for {host}?",
                                body="You'll be signed out of this site, and its saved preferences are removed. "
                                     "Other sites aren't affected.")
        alert.add_response("cancel", "Cancel")
        alert.add_response("clear", "Clear")
        alert.set_response_appearance("clear", Adw.ResponseAppearance.DESTRUCTIVE)
        alert.set_close_response("cancel")
        alert.connect("response", lambda _a, r: r == "clear" and clear_site_data(win, tab, host))
        alert.present(win)

    clear.connect("activated", confirm)
    rows.append(clear)
