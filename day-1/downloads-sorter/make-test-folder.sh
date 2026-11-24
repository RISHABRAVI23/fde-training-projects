#!/usr/bin/env bash
# Creates (or resets) a messy fake downloads folder for testing the sorter.
# Usage: ./make-test-folder.sh [folder]   (default: ./test-downloads)
set -euo pipefail

dir="${1:-./test-downloads}"

rm -rf "$dir"
mkdir -p "$dir/already-a-folder"

touch \
  "$dir/holiday photo.jpg" \
  "$dir/SCREENSHOT.PNG" \
  "$dir/diagram.svg" \
  "$dir/report final.pdf" \
  "$dir/notes.txt" \
  "$dir/budget.xlsx" \
  "$dir/letter.docx" \
  "$dir/song.mp3" \
  "$dir/clip.MP4" \
  "$dir/backup.zip" \
  "$dir/archive.tar.gz" \
  "$dir/installer.exe" \
  "$dir/script.py" \
  "$dir/README" \
  "$dir/.hidden-config" \
  "$dir/weird.unknownext" \
  "$dir/already-a-folder/inside.txt"

# A pre-existing sorted file, to test name clashes.
mkdir -p "$dir/Images"
touch "$dir/Images/holiday photo.jpg"

echo "Created test folder: $dir"
find "$dir" | sort
