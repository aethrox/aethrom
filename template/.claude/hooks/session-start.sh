#!/bin/bash
# SessionStart — inject continuity (last session + threads + identity).
# Runs on macOS, Linux and Windows (Git Bash). See _common.sh for the portability shims.
. "$(dirname "$0")/_common.sh"

VAULT_DIR="$(resolve_vault_dir)"
MEM_DIR="$VAULT_DIR/🔮 850-Companion"
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
  REFLECTION="⚠️ Önceki oturum hafıza güncellemeden bitti: $(cat "$STATE_DIR/needs_reflection"). Anlamlı bir şey olduysa 🔮 850-Companion dosyalarını güncelle."
  rm -f "$STATE_DIR/needs_reflection"
fi

CTX=""
[ -n "$REFLECTION" ] && CTX="${CTX}${REFLECTION}

"
[ -n "$LAST_SESSION" ] && CTX="${CTX}[Memory — Last Session]
${LAST_SESSION}

"
[ -n "$THREADS" ] && CTX="${CTX}[Memory — Active Threads]
${THREADS}

"
CTX="${CTX}[Memory] Identity: {{COMPANION}}, {{USER_NAME}}'s thinking partner. Continuity is your job."

emit_context "SessionStart" "$CTX"
exit 0
