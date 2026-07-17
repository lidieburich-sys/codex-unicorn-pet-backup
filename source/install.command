#!/bin/zsh
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET_DIR="$HOME/.codex/pets/codex-unicorn"

mkdir -p "$TARGET_DIR"
cp "$SOURCE_DIR/pet.json" "$SOURCE_DIR/spritesheet.webp" "$TARGET_DIR/"

echo "Codex Unicorn installed."
echo "Target: $TARGET_DIR"
echo "Restart Codex or reselect the pet if it is already open."
read -r "?Press Enter to close..."
