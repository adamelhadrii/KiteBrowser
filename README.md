# KiteBrowser

A small GTK 4 / libadwaita / WebKitGTK browser where every feature is a toggle in Settings (`Ctrl+,`).
Settings live in `~/.config/kitebrowser/settings.json` and apply instantly.

New tabs open `kite://start`, a local page with a search box, your bookmarks and recently visited pages. It makes no
network requests, and websites can't read it. Searches go to **Brave Search** by default. You can switch to Mojeek,
Startpage, Ecosia, DuckDuckGo, Google or your own URL in Settings → General.

## Features

Everything below has a switch in Settings.

- **Tabs:** vertical or horizontal panel, auto-grouping (Development, Social, Research, Media), a filter box,
  pinned tabs, mute and audio indicator, duplicate, close others, reopen closed tabs, and middle-click to close.
  Right-click a tab for its menu. Ctrl+click or middle-click a link to open it in a background tab.
- **RAM saver:** background tabs sleep after 15 minutes (configurable) and wake when clicked. You can also put a tab
  to sleep from its menu. Restored tabs stay asleep until you open them.
- **Address bar:** suggestions from bookmarks and history, a padlock for HTTPS, and a star to bookmark the page.
- **Bookmarks:** star a page or press Ctrl+D. They appear in the bookmarks menu and on the new-tab page.
- **Downloads:** saved to your Downloads folder (configurable), with progress, cancel, open, and show in folder.
  Server-supplied file names are cleaned so they can't escape the folder or overwrite files.
- **Find in page**, **per-site zoom** (remembered like Firefox), **reader view**, **print**, **full screen** and
  **developer tools** (the WebKit inspector).
- **Private windows** (Ctrl+Shift+P) use a separate, in-memory profile and are never indexed or saved.
- **Session restore:** your windows and tabs come back on the next launch.
- **Privacy:** a built-in blocker for about 70 ad, analytics and social-pixel domains; intelligent tracking
  prevention; autoplay with sound blocked; permission prompts for location, camera, microphone, screen, notifications
  and clipboard; and one button to clear history, cookies and site data.
- **Memory Finder:** search pages you visited by describing them (see below).
- **Command palette** (`Ctrl+Shift+K`): one box that finds open tabs in every window, actions, Settings pages,
  bookmarks and history. Enter runs the top result.
- **Site panel:** click the padlock for the current site's connection, a per-site tracker-blocking switch, its zoom,
  the permissions you told Kite to remember (with Forget), and clearing just that site's cookies and data.
- **Split view** (`Ctrl+Alt+S`, or right-click a tab → Show beside the current tab): two tabs side by side with a
  draggable divider. Click a side to make it current; the address bar, find bar and zoom follow it, and the focused
  side gets an accent line on top. Both sides stay awake. Picking another tab, closing or sleeping either side, or
  pressing the shortcut again closes the split.
- **Focus mode** (`Ctrl+Shift+M`): hides the toolbar and tabs; point at the top edge or press `Ctrl+L` to bring the
  toolbar back.
- **Page screenshots** (`Ctrl+Shift+S`): the whole page (or only what's visible) saved to Pictures, with an Open
  button. Very tall pages fall back to the visible part.
- **Tab sleeping that really frees memory:** a sleeping tab's web process is ended (13 tabs with 12 asleep use about
  410 MB), and when free memory drops below 12% the least recently used background tabs sleep early.
- **Error pages:** a Kite page with Try again instead of a bare error, also when a tab crashes.

## Customize

Settings (`Ctrl+,`) has seven pages and a search box. Most changes apply immediately. The ones that wait for the next
page load or new tab say so.

- **General:** search engine, **search keywords** (type `w kite` to search Wikipedia; add your own with any URL
  containing `{}`), what Ctrl+T opens and where, whether links opened in new tabs take focus, what closing the last
  tab does, session restore, tab sleeping, homepage, download folder, and **export, import or reset** all settings.
- **Colors:** six color themes (Dusk, Pine, Plum, Tide, Graphite, Midnight) or **Custom**, where you pick the
  window, page card, menu and text colors yourself (Kite picks light or dark widgets to match). Accent color.
  **Window background:** the theme color, a two-color gradient, or your own image with an adjustable dim layer,
  plus **window opacity** so your desktop shows through (it adds to Hyprland's own opacity). The dot color of
  each tab group. One button resets this whole page.
- **Look:** corner roundness, space around pages (0 fills the window), page outline and shadow, toolbar height,
  interface font, tab spacing, animations on/off; tab panel layout, side, width, tab width, close-button style,
  site icons, logo, and how the current tab is marked (side bar, fill, underline, outline); **your own tab
  groups** (a name and its domains, matched before the built-in groups, which you can turn off); and the
  **toolbar**: show, hide, reorder and move every button between sides.
- **Start page:** sky, solid color or your own image as background; show or hide the kite, clock, search box,
  bookmarks and recent sites; how many sites per section.
- **Web:** sans, serif and monospace fonts, text sizes, minimum size, default zoom, which browser to identify as,
  autoplay, JavaScript, smooth scrolling, spell check, developer tools.
- **Privacy:** tracker blocking, tracking prevention, Memory Finder, clear data.
- **Shortcuts:** click any action and press a new key combination. Shortcuts need Ctrl, Alt or Super (or an F-key)
  so they don't swallow typing. A combination already in use moves to the new action, and Kite tells you.

### Your own files

In `~/.config/kitebrowser/`, edited from Settings → Web → Your files. Kite reloads them as soon as you save:

| File | What it does |
|---|---|
| `interface.css` | Restyles Kite itself (GTK CSS). Mistakes show up as a message naming the line. |
| `userstyle.css` | CSS added to every web page. |
| `userscript.js` | JavaScript run on every page after it loads (applies on the next page load). |

### Reset

Settings → General → Backup → Reset all settings. Your previous settings are saved to
`~/.config/kitebrowser/settings.json.bak` first, and imports do the same.

Not supported: Firefox extensions (WebKitGTK can't run them), sync, and a password manager. Pages that need Widevine
DRM, such as Netflix, may not play.

## Install as an app

Build scripts live in `packaging/`. Each writes to `packaging/dist/`.

| System | Build | Install |
|---|---|---|
| Arch / Omarchy | `packaging/build-arch.sh` | `sudo pacman -U packaging/dist/kitebrowser-*.pkg.tar.zst` |
| Debian 13+, Ubuntu 25.04+ | `packaging/build-deb.sh` | `sudo apt install ./packaging/dist/kitebrowser_*_all.deb` |
| Any distro (AppImage) | `packaging/build-appimage.sh` (needs `appimagetool`) | run the `.AppImage` |

If you used `./install.sh` before, delete the three files it made when you switch to a package, or your launcher
keeps starting the development folder: `~/.local/share/applications/io.github.KiteBrowser.desktop`,
`~/.local/share/icons/hicolor/scalable/apps/io.github.KiteBrowser.svg` and the `KiteBrowser.desktop` shortcut on your
desktop.

All three install the same thing: the app in `/usr/share/kitebrowser`, a `kitebrowser` command, a launcher entry and
the icon. They use your system's GTK 4, libadwaita 1.6+ and WebKitGTK 6.0 rather than bundling them, so the packages
stay small and get engine security updates from your distro. The AppImage tells you which packages to install if they
are missing. Older Ubuntu releases (24.04 and earlier) ship a libadwaita that is too old. Windows isn't possible: the
WebKitGTK engine has no supported Windows version.

## Install system packages

GTK 4 needs **WebKitGTK 6.0** (`WebKit` namespace, version `6.0`). `libwebkit2gtk-4.1` is the GTK 3 build and
won't load in a GTK 4 app. You also need libadwaita 1.6 or newer.

Arch / Omarchy:

```bash
sudo pacman -S --needed python-gobject gtk4 libadwaita webkitgtk-6.0
```

Debian 13 / Ubuntu 24.10+:

```bash
sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-adw-1 gir1.2-webkit-6.0
```

Fedora:

```bash
sudo dnf install python3-gobject gtk4 libadwaita webkitgtk6.0
```

## Run

Use the system Python (`/usr/bin/python3`). A pyenv/mise/venv Python won't see the distro's `gi` module.

```bash
/usr/bin/python3 main.py
```

You can pass URLs: `/usr/bin/python3 main.py github.com wikipedia.org`. If Kite is already running, they open as tabs
in the existing window.

To add KiteBrowser to your app launcher:

```bash
./install.sh
```

To check the non-GUI logic:

```bash
/usr/bin/python3 selfcheck.py
```

## Files

| File | Purpose |
|---|---|
| `main.py` | Starts the app |
| `app.py` | Shared state: settings, web engine, theme, tracker blocker, `kite://` pages, session restore |
| `browser.py` | Window, toolbar, address bar, tabs, find bar, zoom, permissions, Memory Finder UI |
| `settings.py` | `SettingsManager` (JSON), every default, validators |
| `preferences.py` | The Settings dialog |
| `themes.py` | Color presets, the Custom theme, window backgrounds, and the CSS built from Colors and Look |
| `shortcuts.py` | Actions, default shortcuts, rebinding rules |
| `userfiles.py` | Your CSS and script files, with live reload |
| `bookmarks.py` | Bookmark storage |
| `downloads.py` | Download tracking and safe file names |
| `blocker.py` | The tracker list, as WebKit content-blocker rules |
| `reader.py` | Reader view |
| `palette.py` | Command palette |
| `sitepanel.py` | The site panel behind the padlock |
| `start_page.py` | The `kite://start` new-tab page |
| `history_indexer.py` | SQLite FTS5 page index with plain-English queries |
| `assets/io.github.KiteBrowser.svg` | The logo, used for the app icon, tab panel and start page |
| `install.sh` | Adds a launcher entry and icon |
| `selfcheck.py` | Asserts for grouping, address bar, settings, start page, search, downloads, bookmarks, blocker |

## Shortcuts

Press `Ctrl+?` in Kite for the full list.

| Keys | Action |
|---|---|
| `Ctrl+T` / `Ctrl+W` / `Ctrl+Shift+T` | New tab / close tab / reopen closed tab |
| `Ctrl+Tab`, `Ctrl+Shift+Tab`, `Ctrl+1`…`9` | Next / previous / numbered tab |
| `Ctrl+N` / `Ctrl+Shift+P` | New window / new private window |
| `Ctrl+L` | Focus the address bar |
| `Ctrl+F`, `Ctrl+G` | Find in page, next match |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset |
| `Ctrl+D` / `Ctrl+Shift+O` | Bookmark page / show bookmarks |
| `Ctrl+J` | Downloads |
| `Ctrl+H` or `Ctrl+Shift+F` | History and Memory Finder |
| `Ctrl+Alt+R` | Reader view |
| `Ctrl+P` | Print |
| `F11` | Full screen |
| `F12` | Developer tools |
| `Ctrl+B` | Show/hide the tab panel |
| `Ctrl+Shift+K` | Command palette |
| `Ctrl+Shift+M` | Focus mode |
| `Ctrl+Alt+S` | Split view with the next tab (again to close it) |
| `Ctrl+Shift+S` | Save a screenshot of the page |
| `Ctrl+,` | Settings |

## Memory Finder

When a page finishes loading, its title and visible text (first 20k characters) go into
`~/.local/share/kitebrowser/history.db`. Filler words ("that article I read about…") are dropped, and the
remaining words are matched with stemming and prefixes, ranking title matches higher. `today`, `yesterday`, `week`,
`month` and `year` limit results by time. With an empty query it lists your most recent pages. Turning the toggle
off stops indexing but keeps the existing database. Settings → Privacy → Clear data empties it. Private windows are
never indexed.
