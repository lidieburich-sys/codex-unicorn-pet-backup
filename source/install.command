#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
TARGET_DIR="$HOME/.codex/pets/codex-current-backup"

mkdir -p "$TARGET_DIR"
cp "$REPO_DIR/installed/pet.json" "$REPO_DIR/installed/spritesheet.webp" "$TARGET_DIR/"

echo "Codex (Backup) installed."
echo "Target: $TARGET_DIR"
echo "Refresh the Pets settings, then select Codex (Backup)."
