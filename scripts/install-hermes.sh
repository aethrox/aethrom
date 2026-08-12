#!/usr/bin/env bash
# Install the Aethrom skill into hermes and point hermes at the vault (Linux/macOS).
# Idempotent: safe to run repeatedly. Backs up config.yaml the way hermes itself does.
# Usage: ./install-hermes.sh /home/me/Documents/MyOS [hermes_home]
set -euo pipefail

VAULT_PATH="${1:?usage: install-hermes.sh <vault-path> [hermes-home]}"
HERMES_HOME="${2:-${HERMES_HOME:-$HOME/.hermes}}"

[ -d "$VAULT_PATH" ] || { echo "no vault at: $VAULT_PATH" >&2; exit 1; }
[ -d "$HERMES_HOME" ] || { echo "no hermes at: $HERMES_HOME" >&2; exit 1; }

SKILLS_DIR="$(cd "$(dirname "$0")/../hermes/skills" && pwd)"
CONFIG="$HERMES_HOME/config.yaml"
ENV_FILE="$HERMES_HOME/.env"

# --- 1. register the skills dir in config.yaml -------------------------------
if grep -qF "$SKILLS_DIR" "$CONFIG" 2>/dev/null; then
  echo "external_dirs: already registered, skipped"
else
  cp "$CONFIG" "$CONFIG.bak.$(date +%Y%m%d_%H%M%S)"
  if ! grep -qE "^[[:space:]]+external_dirs:[[:space:]]*\[\][[:space:]]*$" "$CONFIG"; then
    echo "no 'external_dirs: []' in config.yaml. Add it by hand: external_dirs: ['$SKILLS_DIR']" >&2
    exit 1
  fi
  # Replace the empty list with a one-entry list, preserving indentation.
  tmp="$(mktemp)"
  while IFS= read -r line; do
    case "$line" in
      *external_dirs:*"[]"*)
        indent="${line%%external_dirs*}"
        printf '%sexternal_dirs:\n%s  - %s\n' "$indent" "$indent" "'$SKILLS_DIR'" >> "$tmp"
        ;;
      *) printf '%s\n' "$line" >> "$tmp" ;;
    esac
  done < "$CONFIG"
  mv "$tmp" "$CONFIG"
  echo "external_dirs: added -> $SKILLS_DIR"
fi

# --- 2. point hermes at the vault -------------------------------------------
touch "$ENV_FILE"
if grep -qE "^[[:space:]]*OBSIDIAN_VAULT_PATH=" "$ENV_FILE"; then
  tmp="$(mktemp)"
  while IFS= read -r line; do
    case "$line" in
      OBSIDIAN_VAULT_PATH=*) printf 'OBSIDIAN_VAULT_PATH=%s\n' "$VAULT_PATH" >> "$tmp" ;;
      *) printf '%s\n' "$line" >> "$tmp" ;;
    esac
  done < "$ENV_FILE"
  mv "$tmp" "$ENV_FILE"
  echo "OBSIDIAN_VAULT_PATH updated -> $VAULT_PATH"
else
  printf 'OBSIDIAN_VAULT_PATH=%s\n' "$VAULT_PATH" >> "$ENV_FILE"
  echo "OBSIDIAN_VAULT_PATH added -> $VAULT_PATH"
fi

echo
echo "Done. Restart hermes, then ask it what you worked on last session."
