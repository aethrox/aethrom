#!/usr/bin/env bash
# Aethrom setup wizard (Linux and macOS).
#
#   ./scripts/install.sh
#
# Asks which language your companion should speak, where the vault should live,
# pulls an existing vault repo if you have one, scaffolds a fresh vault from
# template/ if you do not, wires the hooks, and offers the desktop launcher and
# an hourly backup.
#
# Idempotent: it never overwrites an existing vault without asking.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_REPO="${VAULT_REPO:-}"
VAULT_PATH="${VAULT_PATH:-}"
OS_NAME="${OS_NAME:-}"
USER_NAME_IN="${USER_NAME_IN:-}"
COMPANION="${COMPANION:-}"
LANGUAGE="${LANGUAGE:-}"
NO_LAUNCHER="${NO_LAUNCHER:-}"
NO_BACKUP="${NO_BACKUP:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) VAULT_REPO="$2"; shift 2 ;;
    --path) VAULT_PATH="$2"; shift 2 ;;
    --name) OS_NAME="$2"; shift 2 ;;
    --language) LANGUAGE="$2"; shift 2 ;;
    --no-launcher) NO_LAUNCHER=1; shift ;;
    --no-backup) NO_BACKUP=1; shift ;;
    -h|--help) sed -n '2,11p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 1 ;;
  esac
done

step() { printf '\n> %s\n' "$1"; }
ok()   { printf '  %s\n' "$1"; }
note() { printf '  %s\n' "$1"; }
fail() { printf '\n  ERROR: %s\n' "$1" >&2; exit 1; }

ask() { # ask <question> <default>
  local ans
  read -r -p "  $1${2:+ [$2]}: " ans
  printf '%s' "${ans:-$2}"
}

ask_yes_no() { # ask_yes_no <question> <default y|n>
  local ans hint
  if [ "$2" = "y" ]; then hint="[Y/n]"; else hint="[y/N]"; fi
  while true; do
    read -r -p "  $1 $hint " ans
    ans="$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')"
    [ -z "$ans" ] && { [ "$2" = "y" ] && return 0 || return 1; }
    case "$ans" in
      y|yes) return 0 ;;
      n|no) return 1 ;;
    esac
  done
}

echo
echo "  Aethrom setup wizard"
echo "  Builds a second brain that remembers across sessions."

# --- language ---------------------------------------------------------------
# Asked first because it decides how the thing you are building will talk to you.
# The wizard itself stays in English; this is the vault's language, not the
# installer's. Free text on purpose: write it however you name it.
step "Language"
if [ -z "$LANGUAGE" ]; then
  lang_default="English"
  case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
    tr*) lang_default="Turkish" ;;
    de*) lang_default="German" ;;
    fr*) lang_default="French" ;;
    es*) lang_default="Spanish" ;;
    it*) lang_default="Italian" ;;
    pt*) lang_default="Portuguese" ;;
    nl*) lang_default="Dutch" ;;
    ru*) lang_default="Russian" ;;
    ja*) lang_default="Japanese" ;;
    zh*) lang_default="Chinese" ;;
    ar*) lang_default="Arabic" ;;
  esac
  echo "  Which language should your companion speak to you in?"
  LANGUAGE="$(ask "Language" "$lang_default")"
fi
ok "your companion will speak $LANGUAGE"

# --- prerequisites ----------------------------------------------------------
step "Prerequisites"
command -v git >/dev/null 2>&1 || fail "git not found."
command -v bash >/dev/null 2>&1 || fail "bash not found."
ok "git and bash are ready"

if command -v obsidian >/dev/null 2>&1 || [ -d "/Applications/Obsidian.app" ] \
   || flatpak info md.obsidian.Obsidian >/dev/null 2>&1; then
  ok "Obsidian is installed"
else
  note "Obsidian does not look installed. The vault is still set up; afterwards:"
  note "  flatpak install flathub md.obsidian.Obsidian   (Linux)"
  note "  brew install --cask obsidian                   (macOS)"
fi

# --- existing vault or a new one -------------------------------------------
step "Vault source"

ALREADY_INSTALLED=0
if [ -n "$VAULT_PATH" ] && [ -d "$VAULT_PATH/.claude/hooks" ]; then
  # Re-run against a vault that is already in place: skip straight to wiring.
  ALREADY_INSTALLED=1
  ok "$VAULT_PATH is already an Aethrom vault, only the wiring will be rechecked"
fi

if [ -z "$VAULT_REPO" ] && [ "$ALREADY_INSTALLED" = "0" ]; then
  echo "  If you already have a vault repo, enter its URL (leave empty to start fresh)."
  VAULT_REPO="$(ask "Vault repo URL" "")"
fi

CLONING=0
[ -n "$VAULT_REPO" ] && [ "$ALREADY_INSTALLED" = "0" ] && CLONING=1

if [ -z "$OS_NAME" ]; then
  if [ "$CLONING" = "1" ]; then
    default_name="$(basename "${VAULT_REPO%.git}")"
  else
    raw="$(hostname 2>/dev/null | sed 's/\..*//' | tr -cd '[:alnum:]')"
    if [ -n "$raw" ]; then
      first="$(printf '%s' "${raw%"${raw#?}"}" | tr '[:lower:]' '[:upper:]')"
      rest="$(printf '%s' "${raw#?}" | tr '[:upper:]' '[:lower:]')"
      default_name="${first}${rest}OS"
    else
      default_name="MyOS"
    fi
  fi
  OS_NAME="$(ask "Name of your system" "$default_name")"
fi

[ -z "$VAULT_PATH" ] && VAULT_PATH="$(ask "Vault path" "$HOME/Documents/$OS_NAME")"

if [ "$ALREADY_INSTALLED" = "0" ] && [ -d "$VAULT_PATH" ] && [ -n "$(ls -A "$VAULT_PATH" 2>/dev/null)" ]; then
  echo "  $VAULT_PATH already exists and is not empty:"
  ls -A "$VAULT_PATH" | head -8 | sed 's/^/    - /'
  ask_yes_no "Continue? (existing files are NOT overwritten)" "n" \
    || fail "Cancelled. Pick another path."
fi

# --- fetch or scaffold ------------------------------------------------------
if [ "$ALREADY_INSTALLED" = "1" ]; then
  step "Using the existing vault"
  note "$VAULT_PATH"
elif [ "$CLONING" = "1" ]; then
  step "Fetching the vault"
  if [ -d "$VAULT_PATH/.git" ]; then
    note "Already a git repo, pulling"
    git -C "$VAULT_PATH" pull --ff-only || fail "pull failed. Resolve it by hand first."
  else
    # Cloning into a non-empty directory fails, so clone beside it and move in.
    tmp="$(mktemp -d)"
    git clone "$VAULT_REPO" "$tmp/v" || fail "clone failed: $VAULT_REPO"
    mkdir -p "$VAULT_PATH"
    (
      shopt -s dotglob
      for item in "$tmp/v"/*; do
        target="$VAULT_PATH/$(basename "$item")"
        if [ -e "$target" ]; then note "skipped (already there): $(basename "$item")"
        else mv "$item" "$target"; fi
      done
    )
    rm -rf "$tmp"
  fi
  ok "vault ready: $VAULT_PATH"
else
  step "Scaffolding a fresh vault"
  [ -z "$USER_NAME_IN" ] && USER_NAME_IN="$(ask "Your name" "${USER:-me}")"
  [ -z "$COMPANION" ] && COMPANION="$(ask "Name for your AI companion" "Echo")"

  [ -d "$REPO_ROOT/template" ] || fail "template/ not found: $REPO_ROOT/template"
  mkdir -p "$VAULT_PATH"
  (
    shopt -s dotglob
    for item in "$REPO_ROOT/template"/*; do
      target="$VAULT_PATH/$(basename "$item")"
      if [ -e "$target" ]; then note "skipped (already there): $(basename "$item")"
      else cp -R "$item" "$target"; fi
    done
  )

  # The companion's memory folder is named after the companion.
  if [ -d "$VAULT_PATH/🔮 850-Companion" ] && [ ! -d "$VAULT_PATH/🔮 850-$COMPANION" ]; then
    mv "$VAULT_PATH/🔮 850-Companion" "$VAULT_PATH/🔮 850-$COMPANION"
  fi

  TODAY="$(date +%F)"
  VENV_PY="$VAULT_PATH/.claude/mem0-venv/bin/python"
  USER_ID="$(printf '%s' "$USER_NAME_IN" | tr '[:upper:]' '[:lower:]')"

  # Resolve every placeholder. Use | as the sed delimiter since paths contain /.
  find "$VAULT_PATH" -type f \( -name '*.md' -o -name '*.sh' -o -name '*.py' -o -name '*.json' \) -print0 \
  | while IFS= read -r -d '' f; do
      grep -q '{{' "$f" 2>/dev/null || continue
      sed -i.bak \
        -e "s|{{OS_NAME}}|$OS_NAME|g" \
        -e "s|{{USER_NAME}}|$USER_NAME_IN|g" \
        -e "s|{{COMPANION}}|$COMPANION|g" \
        -e "s|{{LANGUAGE}}|$LANGUAGE|g" \
        -e "s|{{USER_BIO}}|(fill this in inside CLAUDE.md)|g" \
        -e "s|{{TODAY}}|$TODAY|g" \
        -e "s|{{USER_ID}}|$USER_ID|g" \
        -e "s|{{VAULT_PATH}}|$VAULT_PATH|g" \
        -e "s|{{VENV_PYTHON}}|$VENV_PY|g" \
        -e "s|850-Companion|850-$COMPANION|g" \
        "$f" && rm -f "$f.bak"
    done
  ok "scaffolded and personalised"
fi

# --- hooks ------------------------------------------------------------------
step "Continuity hooks"

HOOKS_DIR="$VAULT_PATH/.claude/hooks"
[ -d "$HOOKS_DIR" ] || fail "$HOOKS_DIR is missing. The vault you fetched does not look like an Aethrom vault."
mkdir -p "$HOOKS_DIR/.state"
chmod +x "$HOOKS_DIR"/*.sh 2>/dev/null
chmod +x "$VAULT_PATH/.claude/backup.sh" 2>/dev/null

SETTINGS="$VAULT_PATH/.claude/settings.local.json"
if [ -f "$SETTINGS" ]; then
  note "settings.local.json already exists, left alone"
else
  # A cloned vault will not carry settings.local.json: it holds the API key and is
  # gitignored by design. Fall back to this repo's template so a pulled vault still
  # gets wired up.
  if [ -f "$VAULT_PATH/.claude/settings.json" ]; then
    src="$VAULT_PATH/.claude/settings.json"
  elif [ -f "$REPO_ROOT/template/.claude/settings.json" ]; then
    src="$REPO_ROOT/template/.claude/settings.json"
    note "the vault carries no settings of its own (gitignored), generating from the template"
  else
    fail "settings.json found neither in the vault nor in the template."
  fi
  cp "$src" "$SETTINGS"
  ok "settings.local.json written"
fi
rm -f "$VAULT_PATH/.claude/settings.windows.json"

# --- prove the hook actually runs -------------------------------------------
step "Verification"

hook_out="$(bash "$HOOKS_DIR/session-start.sh" 2>&1)"
[ -n "$hook_out" ] || fail "session-start.sh printed nothing. The hook is broken and continuity dies silently. Fix this first."
case "$hook_out" in
  '{"hookSpecificOutput"'*) ok "session-start.sh emits the expected JSON" ;;
  *) fail "session-start.sh gave unexpected output:\n$hook_out" ;;
esac

leftover="$(grep -rl '{{[A-Z_]*}}' "$VAULT_PATH" --include='*.md' --include='*.sh' --include='*.py' --include='*.json' 2>/dev/null)"
if [ -n "$leftover" ]; then
  echo "  Files with unresolved placeholders:"
  printf '%s\n' "$leftover" | sed "s|$VAULT_PATH/|    - |"
else
  ok "no unresolved placeholders"
fi

# --- launcher ---------------------------------------------------------------
if [ -z "$NO_LAUNCHER" ]; then
  step "Desktop shortcut"
  if ask_yes_no "Create a desktop shortcut with a brain icon?" "y"; then
    case "$(uname -s)" in
      Darwin) "$REPO_ROOT/scripts/launcher-macos.sh" "$OS_NAME" ;;
      *)      "$REPO_ROOT/scripts/launcher-linux.sh" "$OS_NAME" ;;
    esac
  fi
fi

# --- scheduled backup -------------------------------------------------------
# Only offered when the vault has a remote to push to, since backup.sh needs one.
if [ -z "$NO_BACKUP" ] && [ -f "$VAULT_PATH/.claude/backup.sh" ]; then
  step "Hourly backup"
  if git -C "$VAULT_PATH" rev-parse '@{u}' >/dev/null 2>&1; then
    note "backup.sh commits and pushes whatever changed, and pulls first so a push never gets rejected."
    if ask_yes_no "Schedule it to run hourly?" "y"; then
      "$REPO_ROOT/scripts/schedule-backup.sh" "$VAULT_PATH" "$OS_NAME" \
        || note "scheduling failed, the vault is fine. Run backup.sh by hand or schedule it yourself."
    fi
  else
    note "the vault has no upstream branch yet, so there is nothing to push to."
    note "push it once (git push -u origin HEAD), then run:"
    note "  ./scripts/schedule-backup.sh \"$VAULT_PATH\" \"$OS_NAME\""
  fi
fi

# --- done -------------------------------------------------------------------
cat <<EOF

  Setup complete.
  Vault: $VAULT_PATH

  Next:
    1. Open Obsidian and pick this folder as a vault (the shortcut works after that).
    2. Run 'claude' in the same folder.
    3. Say something, /exit, open it again. It will remember the last session.

  Optional: semantic memory, see the header of .claude/semantic-memory.py,
  and scripts/install-hermes.sh to share the vault with hermes.
EOF
