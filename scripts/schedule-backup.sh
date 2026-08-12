#!/usr/bin/env bash
# Schedule the vault backup to run hourly.
# Usage: ./schedule-backup.sh <vault-path> [name]
#
# Linux: a systemd user timer. macOS: a launchd agent. Both run as the logged-in
# user, no root, and both are removable with one command (printed at the end).
set -euo pipefail

VAULT_PATH="${1:?usage: schedule-backup.sh <vault-path> [name]}"
NAME="${2:-$(basename "$VAULT_PATH")}"
SLUG="$(printf '%s' "$NAME" | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-')"
[ -n "$SLUG" ] || SLUG="aethrom"
BACKUP="$VAULT_PATH/.claude/backup.sh"

[ -f "$BACKUP" ] || { echo "no backup.sh at $BACKUP" >&2; exit 1; }
chmod +x "$BACKUP" 2>/dev/null || true

case "$(uname -s)" in
Darwin)
  LABEL="lol.aethrom.$SLUG.backup"
  PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
  mkdir -p "$(dirname "$PLIST")"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$BACKUP</string>
    <string>$VAULT_PATH</string>
  </array>
  <key>StartInterval</key><integer>3600</integer>
  <key>RunAtLoad</key><false/>
</dict>
</plist>
EOF
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "scheduled: $LABEL, hourly"
  echo "remove with: launchctl unload \"$PLIST\" && rm \"$PLIST\""
  ;;
*)
  command -v systemctl >/dev/null 2>&1 || {
    echo "systemctl not found. Schedule $BACKUP hourly with cron instead:" >&2
    echo "  0 * * * * /bin/bash \"$BACKUP\" \"$VAULT_PATH\"" >&2
    exit 1
  }
  UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
  mkdir -p "$UNIT_DIR"
  cat > "$UNIT_DIR/$SLUG-backup.service" <<EOF
[Unit]
Description=$NAME vault backup

[Service]
Type=oneshot
ExecStart=/bin/bash $BACKUP $VAULT_PATH
EOF
  cat > "$UNIT_DIR/$SLUG-backup.timer" <<EOF
[Unit]
Description=Hourly $NAME vault backup

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl --user daemon-reload
  systemctl --user enable --now "$SLUG-backup.timer"
  echo "scheduled: $SLUG-backup.timer, hourly"
  echo "check with:  systemctl --user list-timers $SLUG-backup.timer"
  echo "remove with: systemctl --user disable --now $SLUG-backup.timer"
  echo
  echo "note: a user timer only runs while you are logged in. To let it run after logout:"
  echo "  loginctl enable-linger $USER"
  ;;
esac
