#!/bin/sh
# Builds dist/KiteBrowser-<version>-x86_64.AppImage. It runs on any distro that has GTK 4, libadwaita 1.6+ and
# WebKitGTK 6.0 installed; bundling WebKit itself would make it ~200 MB and break with every system update.
# Needs appimagetool on PATH (or APPIMAGETOOL=/path/to/appimagetool).
set -e
here=$(cd "$(dirname "$0")" && pwd)
ver=$(cat "$here/VERSION")
tool=${APPIMAGETOOL:-$(command -v appimagetool || true)}
if [ -z "$tool" ] && [ -z "$APPDIR_ONLY" ]; then
    echo "appimagetool not found. Get it once with:" >&2
    echo "  curl -Lo ~/.local/bin/appimagetool https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage && chmod +x ~/.local/bin/appimagetool" >&2
    exit 1
fi
mkdir -p "$here/dist"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
appdir="$work/KiteBrowser.AppDir"
sh "$here/stage.sh" "$appdir"
install -m755 "$here/AppRun" "$appdir/AppRun"
cp "$here/io.github.KiteBrowser.desktop" "$appdir/"
cp "$here/../assets/io.github.KiteBrowser.svg" "$appdir/io.github.KiteBrowser.svg"
ln -s io.github.KiteBrowser.svg "$appdir/.DirIcon"
if [ -n "$APPDIR_ONLY" ]; then  # for testing the layout without appimagetool
    rm -rf "$APPDIR_ONLY" && cp -a "$appdir" "$APPDIR_ONLY" && echo "AppDir at $APPDIR_ONLY" && exit 0
fi
ARCH=x86_64 "$tool" "$appdir" "$here/dist/KiteBrowser-$ver-x86_64.AppImage"
