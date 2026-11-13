"""Bookmarks stored as a JSON list in the data dir."""
import json
import os
import time

PATH = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "kitebrowser", "bookmarks.json")


class Bookmarks:
    def __init__(self, path=PATH):
        self.path = path
        try:
            with open(path) as f:
                items = json.load(f)
            self.items = [b for b in items if isinstance(b, dict) and isinstance(b.get("url"), str)]
        except FileNotFoundError:
            self.items = []
        except (OSError, ValueError) as e:
            print(f"bookmarks: unreadable {path} ({e}); moved to .bak")
            os.replace(path, path + ".bak")
            self.items = []

    def all(self):
        return sorted(self.items, key=lambda b: b.get("added", 0), reverse=True)

    def has(self, url):
        return any(b["url"] == url for b in self.items)

    def toggle(self, url, title):
        """Adds or removes url; returns True when it is now bookmarked."""
        if self.has(url):
            self.items = [b for b in self.items if b["url"] != url]
        else:
            self.items.append({"url": url, "title": title or url, "added": time.time()})
        self.save()
        return self.has(url)

    def search(self, text):
        t = text.lower()
        return [b for b in self.all() if t in b["url"].lower() or t in b.get("title", "").lower()]

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.items, f, indent=1)
        os.replace(tmp, self.path)
