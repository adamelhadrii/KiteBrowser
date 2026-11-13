"""Downloads: safe file names, progress tracking, and the rows shown in the downloads popover."""
import os
import re

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk, Pango  # noqa: E402


def safe_filename(suggested, folder):
    """The server picks the suggested name, so keep only a plain basename and never overwrite an existing file."""
    name = os.path.basename((suggested or "").replace("\\", "/"))
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip().lstrip(".")[:200] or "download"
    base, ext = os.path.splitext(name)
    path, n = os.path.join(folder, name), 1
    while os.path.exists(path):
        path = os.path.join(folder, f"{base} ({n}){ext}")
        n += 1
    return path


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


class Downloads:
    """Shared by all windows; each window registers a listener to update its button and popover."""

    def __init__(self, settings):
        self.s = settings
        self.items = []
        self.listeners = []
        self._queued = False

    def attach(self, session):
        session.connect("download-started", self.on_started)

    def folder(self):
        return (self.s["download_dir"] or GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
                or os.path.expanduser("~/Downloads"))

    def on_started(self, _session, dl):
        item = {"dl": dl, "name": "Starting…", "path": None, "state": "running"}
        self.items.insert(0, item)
        dl.connect("decide-destination", self.on_decide, item)
        dl.connect("notify::estimated-progress", lambda *_: self.notify())
        dl.connect("failed", self.on_failed, item)
        dl.connect("finished", self.on_finished, item)
        self.emit(started=True)

    def on_decide(self, dl, suggested, item):
        folder = os.path.expanduser(self.folder())
        os.makedirs(folder, exist_ok=True)
        # shortcut: two downloads with the same name starting in the same instant can pick one path; WebKit then fails one
        item["path"] = safe_filename(suggested, folder)
        item["name"] = os.path.basename(item["path"])
        dl.set_destination(item["path"])
        self.emit()
        return True

    def on_failed(self, _dl, _error, item):
        if item["state"] == "running":
            item["state"] = "failed"
        self.emit()

    def on_finished(self, _dl, item):
        if item["state"] == "running":
            item["state"] = "done"
            self.emit(finished=item)
        else:
            self.emit()

    def cancel(self, item):
        item["state"] = "cancelled"
        item["dl"].cancel()

    def clear(self):
        self.items = [i for i in self.items if i["state"] == "running"]
        self.emit()

    def notify(self):
        # Progress fires many times a second; batch it.
        if not self._queued:
            self._queued = True
            GLib.timeout_add(250, self._flush)

    def _flush(self):
        self._queued = False
        self.emit()
        return GLib.SOURCE_REMOVE

    def emit(self, started=False, finished=None):
        for cb in list(self.listeners):
            cb(started, finished)


def download_row(item, window, downloads):
    dl, state = item["dl"], item["state"]
    received = dl.get_received_data_length()
    response = dl.get_response()
    total = response.get_content_length() if response else 0
    if state == "running":
        status = f"{round(dl.get_estimated_progress() * 100)}% of {human_size(total)}" if total else human_size(received)
    else:
        status = {"done": f"Done, {human_size(received)}", "failed": "Failed", "cancelled": "Cancelled"}[state]

    col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3, hexpand=True)
    name = Gtk.Label(label=item["name"], xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=30)
    name.add_css_class("heading")
    info = Gtk.Label(label=status, xalign=0)
    info.add_css_class("dim-label")
    info.add_css_class("caption")
    col.append(name)
    if state == "running":
        col.append(Gtk.ProgressBar(fraction=dl.get_estimated_progress()))
    col.append(info)

    row = Gtk.Box(spacing=8, margin_top=6, margin_bottom=6, margin_start=6, margin_end=6)
    row.append(col)

    def button(icon, tip, cb):
        b = Gtk.Button(icon_name=icon, tooltip_text=tip, valign=Gtk.Align.CENTER)
        b.add_css_class("flat")
        b.add_css_class("circular")
        b.connect("clicked", lambda *_: cb())
        row.append(b)

    if state == "running":
        button("process-stop-symbolic", "Cancel download", lambda: downloads.cancel(item))
    elif state == "done" and item["path"]:
        launcher = Gtk.FileLauncher(file=Gio.File.new_for_path(item["path"]))
        button("document-open-symbolic", "Open file", lambda: launcher.launch(window, None, None))
        button("folder-open-symbolic", "Show in folder", lambda: launcher.open_containing_folder(window, None, None))
    return row
