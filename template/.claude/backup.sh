#!/bin/bash
# Vault backup - commit anything that changed, take the remote's work, push.
# Portable the same way the hooks are: no awk, no python, GNU and BSD stat both fine.
# Safe on a clean tree (it still syncs) and safe to run repeatedly.
#
# The install wizard schedules this hourly. Run it by hand any time:
#   bash .claude/backup.sh [vault-path]
set -u

# Kept on its own line: "${1:-{{VAULT_PATH}}}" would not parse before substitution.
DEFAULT_VAULT="{{VAULT_PATH}}"
VAULT_DIR="${1:-$DEFAULT_VAULT}"
cd "$VAULT_DIR" || { echo "no vault at: $VAULT_DIR" >&2; exit 1; }

if [ ! -d .git ]; then
  echo "not a git repo: $VAULT_DIR" >&2
  exit 1
fi

git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1 || {
  echo "no upstream branch, nothing to push to. Set one with: git push -u origin HEAD" >&2
  exit 1
}

git add -A

if git diff --cached --quiet; then
  echo "nothing changed"
else
  # Refuse to commit if the key file ever slips past .gitignore.
  if git diff --cached --name-only | grep -q "settings.local.json"; then
    echo "STOPPED: settings.local.json is staged (it holds the API key)" >&2
    git reset -q
    exit 1
  fi

  # House rule: no em dash anywhere. Catch it before it reaches a commit.
  emdash_hits=$(git diff --cached --name-only -z \
    | xargs -0 -r grep -Il "$(printf '\xe2\x80\x94')" 2>/dev/null)
  if [ -n "$emdash_hits" ]; then
    echo "STOPPED: em dash (U+2014) found in:" >&2
    printf '%s\n' "$emdash_hits" | sed 's/^/  /' >&2
    echo "Use a spaced hyphen, a comma or a colon. The en dash is fine." >&2
    git reset -q
    exit 1
  fi

  git commit -q -m "backup: $(date '+%Y-%m-%d %H:%M')"
fi

# Take the remote's commits before pushing ours. Without this, anything committed
# elsewhere (another machine, the GitHub web UI) makes every later push a rejected
# non-fast-forward, and -q means it fails without saying anything.
# Runs even when there was nothing to commit, so a quiet day still heals the drift.
if ! git pull --rebase -q origin HEAD; then
  git rebase --abort 2>/dev/null
  echo "STOPPED: pull --rebase failed, resolve it by hand. Committed locally, not pushed." >&2
  exit 1
fi

if [ -n "$(git log '@{u}..HEAD' --oneline 2>/dev/null)" ]; then
  git push -q origin HEAD || { echo "STOPPED: push failed." >&2; exit 1; }
  echo "backed up: $(git log -1 --format=%h)"
else
  echo "nothing to push"
fi
