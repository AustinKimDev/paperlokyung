#!/bin/sh
# Download the upstream Paperlogy 1.001 release and verify its checksum.
set -eu

URL="https://github.com/Freesentation/paperlogy/raw/main/Paperlogy-1.001.zip"
SHA256="6ffa5c8fc7539c61f419dcd2c4dd714556412f2455d26399e83792968c7b23d6"
DEST="${1:-build/upstream}"

mkdir -p "$DEST"
curl -sSL -o "$DEST/Paperlogy-1.001.zip" "$URL"
echo "$SHA256  $DEST/Paperlogy-1.001.zip" | shasum -a 256 -c -
unzip -o -q "$DEST/Paperlogy-1.001.zip" -d "$DEST"
ls "$DEST"/Paperlogy-*.ttf
