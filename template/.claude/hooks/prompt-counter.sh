#!/bin/bash
# UserPromptSubmit - count prompts; nudge once at 15 to save memory at session end.
. "$(dirname "$0")/_common.sh"

VAULT_DIR="$(resolve_vault_dir)"
STATE_DIR="$VAULT_DIR/.claude/hooks/.state"
mkdir -p "$STATE_DIR"

COUNT=0; [ -f "$STATE_DIR/prompt_count" ] && COUNT=$(cat "$STATE_DIR/prompt_count" 2>/dev/null || echo 0)
COUNT=$((COUNT + 1)); echo "$COUNT" > "$STATE_DIR/prompt_count"

if [ "$COUNT" -eq 15 ]; then
  emit_context "UserPromptSubmit" "[Memory] This session is running long. Before it ends, update Last-Session.md and Threads.md."
fi
exit 0
