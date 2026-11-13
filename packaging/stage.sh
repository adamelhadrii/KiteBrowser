#!/bin/sh
# Lays Kite out under $1 the way every package installs it (/usr/bin, /usr/share/...). Used by all three builders.
set -e
dest=$1
src=$(cd "$(dirname "$0")/.." && pwd)
app="$dest/usr/share/kitebrowser"
mkdir -p "$app/assets" "$dest/usr/bin" "$dest/usr/share/applications" \
         "$dest/usr/share/icons/hicolor/scalable/apps" "$dest/usr/share/doc/kitebrowser"
for f in "$src"/*.py; do
    [ "$(basename "$f")" = selfcheck.py ] || install -m644 "$f" "$app/"
done
install -m644 "$src/assets/io.github.KiteBrowser.svg" "$app/assets/"
install -m644 "$src/assets/io.github.KiteBrowser.svg" "$dest/usr/share/icons/hicolor/scalable/apps/"
install -m755 "$src/packaging/kitebrowser" "$dest/usr/bin/kitebrowser"
install -m644 "$src/packaging/io.github.KiteBrowser.desktop" "$dest/usr/share/applications/"
install -m644 "$src/README.md" "$dest/usr/share/doc/kitebrowser/"
