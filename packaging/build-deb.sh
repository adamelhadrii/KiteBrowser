#!/bin/sh
# Builds dist/kitebrowser_<version>_all.deb for Debian 13+ and Ubuntu 25.04+ (they ship libadwaita 1.6 or newer).
# Install it with: sudo apt install ./dist/kitebrowser_*_all.deb
set -e
here=$(cd "$(dirname "$0")" && pwd)
ver=$(cat "$here/VERSION")
mkdir -p "$here/dist"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
sh "$here/stage.sh" "$work/root"
mkdir "$work/control"
(cd "$work/root" && find usr -type f -exec md5sum {} + > "$work/control/md5sums")
cat > "$work/control/control" <<CONTROL
Package: kitebrowser
Version: $ver
Architecture: all
Maintainer: KiteBrowser <kitebrowser@localhost>
Installed-Size: $(du -sk "$work/root" | cut -f1)
Depends: python3 (>= 3.11), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1 (>= 1.6), gir1.2-webkit-6.0
Recommends: hunspell-en-us
Section: web
Priority: optional
Description: Light, fully customizable GTK 4 web browser
 KiteBrowser is a WebKitGTK browser where every feature, color and shortcut
 can be changed in Settings, with tab sleeping, natural-language history
 search, tracker blocking and session restore.
CONTROL
echo 2.0 > "$work/debian-binary"
tar --owner=0 --group=0 --numeric-owner -cJf "$work/control.tar.xz" -C "$work/control" ./control ./md5sums
tar --owner=0 --group=0 --numeric-owner -cJf "$work/data.tar.xz" -C "$work/root" ./usr
rm -f "$here/dist/kitebrowser_${ver}_all.deb"
# dpkg requires this member order.
(cd "$work" && ar rcD "$here/dist/kitebrowser_${ver}_all.deb" debian-binary control.tar.xz data.tar.xz)
echo "Built $here/dist/kitebrowser_${ver}_all.deb"
