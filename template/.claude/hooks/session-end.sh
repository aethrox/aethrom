#!/bin/bash
# SessionEnd - if a real session ended without a memory write, leave a reflection marker.
. "$(dirname "$0")/_common.sh"

VAULT_DIR="$(resolve_vault_dir)"
MEM_DIR="$VAULT_DIR/🔮 850-{{COMPANION}}"
STATE_DIR="$VAULT_DIR/.claude/hooks/.state"
mkdir -p "$STATE_DIR"

START=0; [ -f "$STATE_DIR/session_start_time" ] && START=$(cat "$STATE_DIR/session_start_time" 2>/dev/null || echo 0)
PROMPTS=0; [ -f "$STATE_DIR/prompt_count" ] && PROMPTS=$(cat "$STATE_DIR/prompt_count" 2>/dev/null || echo 0)

MODIFIED=0
if [ -f "$MEM_DIR/Last-Session.md" ]; then
  FM=$(mtime_of "$MEM_DIR/Last-Session.md")
  [ "$FM" -gt "$START" ] 2>/dev/null && MODIFIED=1
fi

if [ "$PROMPTS" -ge 5 ] && [ "$MODIFIED" -eq 0 ]; then
  echo "session ended without a memory write, $PROMPTS prompts, $(date '+%Y-%m-%d %H:%M')" > "$STATE_DIR/needs_reflection"
fi

rm -f "$STATE_DIR/session_start_time" "$STATE_DIR/prompt_count"
exit 0
