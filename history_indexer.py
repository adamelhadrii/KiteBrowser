"""Memory Finder backend: page titles + text in SQLite FTS5, queried with plain English."""
import os
import re
import sqlite3
import time

DB_PATH = os.path.join(
    os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")), "kitebrowser", "history.db")

# Filler words people use when describing a page ("that article I read about ...").
STOPWORDS = set("""a an the and or of to in on at for with about from by that this these those was were is are be
it its i me my we you page pages site website article post something some saw seen read looked visited remember
find thing stuff last ago past earlier recent recently""".split())
TIME_HINTS = {"today": 1, "yesterday": 2, "week": 7, "weeks": 14, "month": 31, "months": 92, "year": 365}
MAX_BODY = 20000


class HistoryIndexer:
    def __init__(self, path=DB_PATH):
        if path != ":memory:":
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS pages USING fts5("
                        "url UNINDEXED, title, body, visited UNINDEXED, tokenize='porter unicode61')")

    def add(self, url, title, body, visited=None):
        with self.db:
            # shortcut: url is UNINDEXED so this DELETE scans the table; add a url->rowid table past ~50k pages
            self.db.execute("DELETE FROM pages WHERE url = ?", (url,))
            self.db.execute("INSERT INTO pages VALUES (?, ?, ?, ?)",
                            (url, title, body[:MAX_BODY], visited or time.time()))

    def search(self, query, limit=20):
        """Returns [(url, title, snippet, visited)], best match first; empty query = most recent."""
        words = re.findall(r"\w+", query.lower())
        days = max((TIME_HINTS[w] for w in words if w in TIME_HINTS), default=None)
        since = time.time() - days * 86400 if days else 0
        terms = [w for w in words if w not in STOPWORDS and w not in TIME_HINTS]
        if not terms:
            return self.db.execute(
                "SELECT url, title, substr(body, 1, 160), visited FROM pages WHERE visited >= ? "
                "ORDER BY visited DESC LIMIT ?", (since, limit)).fetchall()
        # \w+ tokens can't contain quotes, so quoting each one makes the MATCH string injection-safe.
        match = " OR ".join(f'"{t}"*' for t in terms)
        return self.db.execute(
            "SELECT url, title, snippet(pages, 2, '', '', '…', 16), visited FROM pages "
            "WHERE pages MATCH ? AND visited >= ? ORDER BY bm25(pages, 0, 5, 1, 0) LIMIT ?",
            (match, since, limit)).fetchall()

    def suggest(self, text, limit=8):
        """Address-bar suggestions: substring match on URL or title, most recent first."""
        # url is UNINDEXED in the FTS table, so FTS MATCH can't find "git" in github.com; LIKE scans instead.
        # shortcut: full scan per keystroke, fine for personal history; add a url table with an index past ~100k pages
        like = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        return self.db.execute(
            "SELECT url, title FROM pages WHERE url LIKE ? ESCAPE '\\' OR title LIKE ? ESCAPE '\\' "
            "ORDER BY visited DESC LIMIT ?", (like, like, limit)).fetchall()

    def clear(self):
        with self.db:
            self.db.execute("DELETE FROM pages")
