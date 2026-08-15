#!/bin/bash
# SessionStart - inject continuity (last session + threads + identity).
# Runs on macOS, Linux and Windows (Git Bash). See _common.sh for the portability shims.
. "$(dirname "$0")/_common.sh"

VAULT_DIR="$(resolve_vault_dir)"
MEM_DIR="$VAULT_DIR/🔮 850-{{COMPANION}}"
STATE_DIR="$VAULT_DIR/.claude/hooks/.state"
mkdir -p "$STATE_DIR"
date +%s > "$STATE_DIR/session_start_time"
echo "0" > "$STATE_DIR/prompt_count"

LAST_SESSION=""
[ -f "$MEM_DIR/Last-Session.md" ] && LAST_SESSION=$(sed -n '/^## Session:/,/^## Previous/p' "$MEM_DIR/Last-Session.md" 2>/dev/null | head -50 | sed '$d')

THREADS=""
[ -f "$MEM_DIR/Threads.md" ] && THREADS=$(sed -n '/^## Active/,/^## Closed/p' "$MEM_DIR/Threads.md" 2>/dev/null | grep -E "^### |^\*\*Status:\*\*" | head -12)

REFLECTION=""
if [ -f "$STATE_DIR/needs_reflection" ]; then
  REFLECTION="⚠️ The previous session ended without a memory write: $(cat "$STATE_DIR/needs_reflection"). If anything mattered, update the 🔮 850-{{COMPANION}} files."
  rm -f "$STATE_DIR/needs_reflection"
fi

# A scheduled backup has nowhere to print, so a broken one is invisible until the
# day you need it. backup.sh leaves its reason here; a stamp that stops moving
# means the scheduled task itself is gone. Silent when no backup was ever set up.
BACKUP_WARN=""
if [ -f "$STATE_DIR/backup_failed" ]; then
  since=$(head -1 "$STATE_DIR/backup_failed" 2>/dev/null)
  why=$(sed -n '2p' "$STATE_DIR/backup_failed" 2>/dev/null)
  BACKUP_WARN="⚠️ Vault backup failing since $since: $why (nothing else reports this, tell the user)"
elif [ -f "$STATE_DIR/backup_ok" ]; then
  age=$(( ( $(date +%s) - $(mtime_of "$STATE_DIR/backup_ok") ) / 3600 ))
  if [ "$age" -ge 24 ] 2>/dev/null; then
    BACKUP_WARN="⚠️ The vault backup has not run for $age hours. Its scheduled task may be gone. Tell the user."
  fi
fi

CTX=""
[ -n "$REFLECTION" ] && CTX="${CTX}${REFLECTION}

"
[ -n "$BACKUP_WARN" ] && CTX="${CTX}${BACKUP_WARN}

"
[ -n "$LAST_SESSION" ] && CTX="${CTX}[Memory - Last Session]
${LAST_SESSION}

"
[ -n "$THREADS" ] && CTX="${CTX}[Memory - Active Threads]
${THREADS}

"
CTX="${CTX}[Memory] Identity: {{COMPANION}}, {{USER_NAME}}'s thinking partner. Continuity is your job."

emit_context "SessionStart" "$CTX"
exit 0
