#!/usr/bin/env bash
# Aethrom setup wizard (Linux and macOS).
#
#   ./scripts/install.sh
#
# Asks where the vault should live, pulls an existing vault repo if you have one,
# scaffolds a fresh vault from template/ if you do not, wires the hooks and offers
# the desktop launcher.
#
# Idempotent: it never overwrites an existing vault without asking.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VAULT_REPO="${VAULT_REPO:-}"
VAULT_PATH="${VAULT_PATH:-}"
OS_NAME="${OS_NAME:-}"
USER_NAME_IN="${USER_NAME_IN:-}"
COMPANION="${COMPANION:-}"
NO_LAUNCHER="${NO_LAUNCHER:-}"

while [ $# -gt 0 ]; do
  case "$1" in
    --repo) VAULT_REPO="$2"; shift 2 ;;
    --path) VAULT_PATH="$2"; shift 2 ;;
    --name) OS_NAME="$2"; shift 2 ;;
    --no-launcher) NO_LAUNCHER=1; shift ;;
    -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
    *) echo "bilinmeyen argüman: $1" >&2; exit 1 ;;
  esac
done

step() { printf '\n> %s\n' "$1"; }
ok()   { printf '  %s\n' "$1"; }
note() { printf '  %s\n' "$1"; }
fail() { printf '\n  HATA: %s\n' "$1" >&2; exit 1; }

ask() { # ask <question> <default>
  local ans
  read -r -p "  $1${2:+ [$2]}: " ans
  printf '%s' "${ans:-$2}"
}

ask_yes_no() { # ask_yes_no <question> <default y|n>
  local ans hint
  if [ "$2" = "y" ]; then hint="[E/h]"; else hint="[e/H]"; fi
  while true; do
    read -r -p "  $1 $hint " ans
    ans="$(printf '%s' "$ans" | tr '[:upper:]' '[:lower:]')"
    [ -z "$ans" ] && { [ "$2" = "y" ] && return 0 || return 1; }
    case "$ans" in
      e|evet|y|yes) return 0 ;;
      h|hayir|hayır|n|no) return 1 ;;
    esac
  done
}

echo
echo "  Aethrom kurulum sihirbazı"
echo "  Oturumlar arası hafızası olan bir ikinci beyin kurar."

# --- prerequisites ----------------------------------------------------------
step "Gereksinimler"
command -v git >/dev/null 2>&1 || fail "git bulunamadı."
command -v bash >/dev/null 2>&1 || fail "bash bulunamadı."
ok "git ve bash hazır"

if command -v obsidian >/dev/null 2>&1 || [ -d "/Applications/Obsidian.app" ] \
   || flatpak info md.obsidian.Obsidian >/dev/null 2>&1; then
  ok "Obsidian kurulu"
else
  note "Obsidian kurulu görünmüyor. Vault yine kurulur; sonra:"
  note "  flatpak install flathub md.obsidian.Obsidian   (Linux)"
  note "  brew install --cask obsidian                   (macOS)"
fi

# --- existing vault or a new one -------------------------------------------
step "Vault kaynağı"

ALREADY_INSTALLED=0
if [ -n "$VAULT_PATH" ] && [ -d "$VAULT_PATH/.claude/hooks" ]; then
  # Re-run against a vault that is already in place: skip straight to wiring.
  ALREADY_INSTALLED=1
  ok "$VAULT_PATH zaten bir Aethrom vault'u, sadece bağlantılar kontrol edilecek"
fi

if [ -z "$VAULT_REPO" ] && [ "$ALREADY_INSTALLED" = "0" ]; then
  echo "  Hazır bir vault repon varsa URL'sini gir (boş bırak = sıfırdan kur)."
  VAULT_REPO="$(ask "Vault repo URL'si" "")"
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
  OS_NAME="$(ask "Sistemin adı" "$default_name")"
fi

[ -z "$VAULT_PATH" ] && VAULT_PATH="$(ask "Vault yolu" "$HOME/Documents/$OS_NAME")"

if [ "$ALREADY_INSTALLED" = "0" ] && [ -d "$VAULT_PATH" ] && [ -n "$(ls -A "$VAULT_PATH" 2>/dev/null)" ]; then
  echo "  $VAULT_PATH zaten var ve dolu:"
  ls -A "$VAULT_PATH" | head -8 | sed 's/^/    - /'
  ask_yes_no "Devam edilsin mi? (var olan dosyaların üzerine YAZILMAZ)" "n" \
    || fail "İptal edildi. Başka bir yol seç."
fi

# --- fetch or scaffold ------------------------------------------------------
if [ "$ALREADY_INSTALLED" = "1" ]; then
  step "Var olan vault kullanılıyor"
  note "$VAULT_PATH"
elif [ "$CLONING" = "1" ]; then
  step "Vault çekiliyor"
  if [ -d "$VAULT_PATH/.git" ]; then
    note "Zaten bir git deposu, pull ediliyor"
    git -C "$VAULT_PATH" pull --ff-only || fail "pull başarısız. Önce elle çöz."
  else
    # Cloning into a non-empty directory fails, so clone beside it and move in.
    tmp="$(mktemp -d)"
    git clone "$VAULT_REPO" "$tmp/v" || fail "clone başarısız: $VAULT_REPO"
    mkdir -p "$VAULT_PATH"
    (
      shopt -s dotglob
      for item in "$tmp/v"/*; do
        target="$VAULT_PATH/$(basename "$item")"
        if [ -e "$target" ]; then note "atlandı (zaten var): $(basename "$item")"
        else mv "$item" "$target"; fi
      done
    )
    rm -rf "$tmp"
  fi
  ok "vault hazır: $VAULT_PATH"
else
  step "Sıfırdan vault kuruluyor"
  [ -z "$USER_NAME_IN" ] && USER_NAME_IN="$(ask "İsmin" "${USER:-me}")"
  [ -z "$COMPANION" ] && COMPANION="$(ask "AI ortağının adı" "Echo")"

  [ -d "$REPO_ROOT/template" ] || fail "template/ bulunamadı: $REPO_ROOT/template"
  mkdir -p "$VAULT_PATH"
  (
    shopt -s dotglob
    for item in "$REPO_ROOT/template"/*; do
      target="$VAULT_PATH/$(basename "$item")"
      if [ -e "$target" ]; then note "atlandı (zaten var): $(basename "$item")"
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
        -e "s|{{USER_BIO}}|(bunu CLAUDE.md içinde doldur)|g" \
        -e "s|{{TODAY}}|$TODAY|g" \
        -e "s|{{USER_ID}}|$USER_ID|g" \
        -e "s|{{VAULT_PATH}}|$VAULT_PATH|g" \
        -e "s|{{VENV_PYTHON}}|$VENV_PY|g" \
        -e "s|850-Companion|850-$COMPANION|g" \
        "$f" && rm -f "$f.bak"
    done
  ok "iskelet kuruldu ve kişiselleştirildi"
fi

# --- hooks ------------------------------------------------------------------
step "Süreklilik hook'ları"

HOOKS_DIR="$VAULT_PATH/.claude/hooks"
[ -d "$HOOKS_DIR" ] || fail "$HOOKS_DIR yok. Çekilen repo bir Aethrom vault'u değil gibi görünüyor."
mkdir -p "$HOOKS_DIR/.state"
chmod +x "$HOOKS_DIR"/*.sh 2>/dev/null

SETTINGS="$VAULT_PATH/.claude/settings.local.json"
if [ -f "$SETTINGS" ]; then
  note "settings.local.json zaten var, dokunulmadı"
else
  # A cloned vault will not carry settings.local.json: it holds the API key and is
  # gitignored by design. Fall back to this repo's template so a pulled vault still
  # gets wired up.
  if [ -f "$VAULT_PATH/.claude/settings.json" ]; then
    src="$VAULT_PATH/.claude/settings.json"
  elif [ -f "$REPO_ROOT/template/.claude/settings.json" ]; then
    src="$REPO_ROOT/template/.claude/settings.json"
    note "vault kendi settings'ini taşımıyor (gitignore), şablondan üretiliyor"
  else
    fail "settings.json ne vault'ta ne şablonda bulundu."
  fi
  cp "$src" "$SETTINGS"
  ok "settings.local.json yazıldı"
fi
rm -f "$VAULT_PATH/.claude/settings.windows.json"

# --- prove the hook actually runs -------------------------------------------
step "Doğrulama"

hook_out="$(bash "$HOOKS_DIR/session-start.sh" 2>&1)"
[ -n "$hook_out" ] || fail "session-start.sh hiçbir şey yazmadı. Hook bozuk, süreklilik sessizce ölür. Önce bunu çöz."
case "$hook_out" in
  '{"hookSpecificOutput"'*) ok "session-start.sh beklenen JSON'u üretiyor" ;;
  *) fail "session-start.sh beklenmeyen çıktı verdi:\n$hook_out" ;;
esac

leftover="$(grep -rl '{{[A-Z_]*}}' "$VAULT_PATH" --include='*.md' --include='*.sh' --include='*.py' --include='*.json' 2>/dev/null)"
if [ -n "$leftover" ]; then
  echo "  Doldurulmamış placeholder kalan dosyalar:"
  printf '%s\n' "$leftover" | sed "s|$VAULT_PATH/|    - |"
else
  ok "doldurulmamış placeholder yok"
fi

# --- launcher ---------------------------------------------------------------
if [ -z "$NO_LAUNCHER" ]; then
  step "Masaüstü kısayolu"
  if ask_yes_no "Beyin ikonlu masaüstü kısayolu oluşturulsun mu?" "y"; then
    case "$(uname -s)" in
      Darwin) "$REPO_ROOT/scripts/launcher-macos.sh" "$OS_NAME" ;;
      *)      "$REPO_ROOT/scripts/launcher-linux.sh" "$OS_NAME" ;;
    esac
  fi
fi

# --- done -------------------------------------------------------------------
cat <<EOF

  Kurulum tamam.
  Vault: $VAULT_PATH

  Sırasıyla:
    1. Obsidian'ı aç ve bu klasörü vault olarak seç (kısayol bundan sonra çalışır).
    2. Aynı klasörde 'claude' çalıştır.
    3. Bir şey konuş, /exit yap, tekrar aç. Geçen oturumu hatırlayacak.

  İsteğe bağlı: semantik hafıza için .claude/semantic-memory.py başındaki adımlar,
  ve hermes ile paylaşım için scripts/install-hermes.sh
EOF
