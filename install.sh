#!/bin/sh
# Adds KiteBrowser to your app launcher and puts a shortcut on your desktop. Undo: rm the three files it prints.
set -e
here=$(cd "$(dirname "$0")" && pwd)
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
desktop=$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")
mkdir -p "$apps" "$icons" "$desktop"
cp "$here/assets/io.github.KiteBrowser.svg" "$icons/"
# Absolute /usr/bin/python3: a launcher's PATH may find a pyenv/mise Python without the gi module.
# Absolute Icon= path: desktop-icon widgets don't all search the icon theme.
cat > "$apps/io.github.KiteBrowser.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=KiteBrowser
Comment=A light, fully customizable web browser
Exec=/usr/bin/python3 "$here/main.py" %U
Icon=$icons/io.github.KiteBrowser.svg
Categories=Network;WebBrowser;
MimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;
StartupWMClass=io.github.KiteBrowser
EOF
cp "$apps/io.github.KiteBrowser.desktop" "$desktop/KiteBrowser.desktop"
chmod +x "$desktop/KiteBrowser.desktop"  # file managers treat only executable .desktop files as trusted launchers
echo "Installed $apps/io.github.KiteBrowser.desktop"
echo "Installed $icons/io.github.KiteBrowser.svg"
echo "Installed $desktop/KiteBrowser.desktop"
