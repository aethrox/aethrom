#!/usr/bin/env bash
# Desktop launcher for Linux: a .desktop entry that opens the vault in Obsidian.
# Usage: ./launcher-linux.sh <VaultName>
set -euo pipefail

VAULT_NAME="${1:?usage: launcher-linux.sh <VaultName>}"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICON_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/icons"
DESKTOP_FILE="$APPS_DIR/${VAULT_NAME}.desktop"
ICON_FILE="$ICON_DIR/${VAULT_NAME}.png"

mkdir -p "$APPS_DIR" "$ICON_DIR"
cp "$(dirname "$0")/../assets/brain.png" "$ICON_FILE"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=$VAULT_NAME
Comment=Second brain
Exec=xdg-open "obsidian://open?vault=$VAULT_NAME"
Icon=$ICON_FILE
Terminal=false
Categories=Utility;
EOF

chmod +x "$DESKTOP_FILE"
update-desktop-database "$APPS_DIR" 2>/dev/null || true

# Also drop a copy on the desktop if there is one (GNOME needs it marked trusted)
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
  cp "$DESKTOP_FILE" "$DESKTOP_DIR/"
  chmod +x "$DESKTOP_DIR/${VAULT_NAME}.desktop"
  gio set "$DESKTOP_DIR/${VAULT_NAME}.desktop" metadata::trusted true 2>/dev/null || true
fi

echo "launcher ✓ $DESKTOP_FILE"
echo "note: the obsidian:// handler only resolves after the vault has been opened in Obsidian once."
