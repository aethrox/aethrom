#!/bin/bash
# Shared helpers for the continuity hooks. Sourced, never run directly.
#
# Portability notes (why this file exists at all):
#  - Claude Code on Windows substitutes $CLAUDE_PROJECT_DIR as a Windows path
#    (C:\Users\...), which dirname cannot split. Convert it to the /c/Users/... form
#    Git Bash understands before touching it.
#  - stat takes -c on GNU (Linux, Git Bash) and -f on BSD (macOS).
#  - python3 is not guaranteed on Windows, so JSON escaping is done with sed/awk.

# C:\Users\x  ->  /c/Users/x   (anything already POSIX passes through untouched)
to_posix() {
  case "$1" in
    [A-Za-z]:[\\/]*)
      printf '%s' "$1" | sed -e 's|\\|/|g' -e 's|^\(.\):|/\L\1|'
      ;;
    *) printf '%s' "$1" ;;
  esac
}

# The vault is the grandparent of this file's directory: <vault>/.claude/hooks/
resolve_vault_dir() {
  local base
  if [ -n "$CLAUDE_PROJECT_DIR" ]; then
    base="$(to_posix "$CLAUDE_PROJECT_DIR")"
    [ -d "$base" ] && { printf '%s' "$base"; return; }
  fi
  base="$(to_posix "$0")"
  ( cd "$(dirname "$base")/../.." && pwd )
}

# Modification time of a file, or 0. GNU first, BSD second.
mtime_of() {
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0
}

# stdin -> a complete JSON string literal, quotes included.
# Pure bash on purpose: a minimal Fedora WSL image ships without awk, and a hook that
# silently emits nothing is worse than one that is slightly more verbose.
json_string() {
  local s
  s=$(cat)
  s=${s//\\/\\\\}
  s=${s//\"/\\\"}
  s=${s//$'\r'/}
  s=${s//$'\t'/\\t}
  s=${s//$'\n'/\\n}
  printf '"%s"' "$s"
}

# Emit a Claude Code hook payload: emit_context <hookEventName> <text>
emit_context() {
  local esc
  esc=$(printf '%s' "$2" | json_string)
  [ -n "$esc" ] && printf '{"hookSpecificOutput":{"hookEventName":"%s","additionalContext":%s}}\n' "$1" "$esc"
}
