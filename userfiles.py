"""The user's own CSS and JavaScript files, created from templates on demand and reloaded when saved."""
import os

from gi.repository import Gio

TEMPLATES = {
    "interface.css": """/* Kite interface CSS: restyles Kite itself. Saved changes apply right away.
   Turn it off in Settings → Web → Your files.

   Examples:
   .omnibox { border-radius: 4px; }                 square address bar
   .tabstrip .tab.active { font-weight: bold; }     bold current tab
   window.kite headerbar { min-height: 38px; }      slimmer toolbar
*/
""",
    "userstyle.css": """/* CSS added to every web page. Saved changes apply to open pages right away.

   Examples:
   ::selection { background: #f5b83d; color: #1a1f3d; }
   img { border-radius: 6px; }
*/
""",
    "userscript.js": """// JavaScript run on every web page once it has loaded. Saved changes apply on the next page load.
//
// Example: show the page's host in the console
// console.log("Kite userscript on", location.host);
""",
}


class UserFiles:
    def __init__(self, folder, on_change):
        self.folder = folder
        self.on_change = on_change
        os.makedirs(folder, exist_ok=True)
        # Watch the folder, not the files: editors save by writing a temp file and renaming it over the original.
        self.monitor = Gio.File.new_for_path(folder).monitor_directory(Gio.FileMonitorFlags.WATCH_MOVES, None)
        self.monitor.connect("changed", self._changed)

    def path(self, name):
        return os.path.join(self.folder, name)

    def read(self, name):
        try:
            with open(self.path(name), encoding="utf-8", errors="replace") as f:
                return f.read()
        except FileNotFoundError:
            return ""

    def ensure(self, name):
        path = self.path(name)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(TEMPLATES[name])
        return path

    def _changed(self, _monitor, file, other, event):
        E = Gio.FileMonitorEvent
        if event not in (E.CHANGES_DONE_HINT, E.CREATED, E.DELETED, E.MOVED_IN, E.MOVED_OUT, E.RENAMED):
            return
        for f in (file, other):
            if f and f.get_basename() in TEMPLATES:
                self.on_change(f.get_basename())
