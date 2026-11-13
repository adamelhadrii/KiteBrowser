#!/bin/sh
# Builds dist/kitebrowser-<version>-1-any.pkg.tar.zst. Install it with: sudo pacman -U dist/kitebrowser-*.pkg.tar.zst
set -e
here=$(cd "$(dirname "$0")" && pwd)
root=$(dirname "$here")
ver=$(cat "$here/VERSION")
mkdir -p "$here/dist"
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
tar -czf "$work/kitebrowser-$ver.tar.gz" -C "$(dirname "$root")" --exclude=__pycache__ --exclude=dist \
    --transform "s,^$(basename "$root"),kitebrowser-$ver," "$(basename "$root")"
sed "s/^pkgver=.*/pkgver=$ver/" "$here/arch/PKGBUILD" > "$work/PKGBUILD"
cd "$work" && PKGDEST="$here/dist" makepkg --force --nodeps --noconfirm
