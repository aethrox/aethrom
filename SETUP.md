# SETUP.md — Activate this second brain (Claude Code runbook)

> You are Claude Code, running inside a fresh clone of this repo. The user wants their own AI
> second brain. The scaffold is in `./template/`. Interview them, copy it to its real home,
> personalize it, and build the launcher. Speak **Turkish** to the user.

## Rules
1. Interview first, build second. Never leave a literal `{{...}}` in any file.
2. Never destroy. If the target vault path exists, show it and ask before overwriting.
3. Don't block on optional steps (mem0, icons). Log it, tell the user, continue.
4. **Detect the OS first** — every phase below branches on it. Don't run macOS commands on Windows.
5. Verify each phase by running it, not by reading it. End with the first-run report.

Placeholders: `{{OS_NAME}}` · `{{USER_NAME}}` · `{{USER_BIO}}` · `{{COMPANION}}` · `{{VAULT_PATH}}` ·
`{{TODAY}}` · `{{USER_ID}}` · `{{VENV_PYTHON}}` · (Windows only) `{{BASH_PATH}}` · `{{VAULT_PATH_FWD}}`

---

## PHASE 0 — Detect the platform

| | Windows | Linux | macOS |
|---|---|---|---|
| detect | `$env:OS -eq 'Windows_NT'` | `uname -s` = Linux | `uname -s` = Darwin |
| machine name | `$env:COMPUTERNAME` | `hostname` | `scutil --get ComputerName` |
| vault default | `$env:USERPROFILE\Documents\{{OS_NAME}}` | `~/Documents/{{OS_NAME}}` | see below |
| shell for hooks | Git Bash | system bash | system bash |

macOS vault default: if `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/` exists use
`.../Documents/{{OS_NAME}}` (syncs across devices), else `~/Documents/{{OS_NAME}}`.

Derive `{{OS_NAME}}`: PascalCase the machine name and append `OS`, stripping
`MacBook/Pro/Air/iMac/'s` and dashes. `Johns-MacBook-Pro` → `JohnOS`, `AETHROX` → `AethroxOS`.
Propose it, let the user override. Set `{{TODAY}}` = `date +%F`.

### Windows only — find Git Bash
`C:\Windows\System32\bash.exe` is the **WSL** launcher and will not work; it cannot see the vault
at a Windows path. Find the real one and use its full path as `{{BASH_PATH}}`:

```powershell
(Get-Command git).Source -replace '\\cmd\\git\.exe$', '\bin\bash.exe'
```

Verify it before continuing: `& $bash -c "echo ok"` must print `ok`.
`{{VAULT_PATH_FWD}}` is the vault path with forward slashes: `C:/Users/you/Documents/MyOS`.

---

## PHASE 1 — Interview (Turkish, conversational — not a form)

1. **İsmin ne?** → `{{USER_NAME}}` (also becomes `{{USER_ID}}`, lowercased, for mem0)
2. **Ne iş yapıyorsun / bu beyni en çok ne için kullanacaksın?** (1-2 cümle) → `{{USER_BIO}}`
3. **AI ortağına ne isim vermek istersin?** → `{{COMPANION}}`
4. **Kapsam:** core (herkes) + opsiyonel `⚔️ 200-Goals`, `🔐 400-Vault`, `💪 700-Body`, `🧘 800-Mind`
5. **Semantik hafıza (mem0)?** Dosya tabanlı hafıza API'siz çalışır ve herkese yeter. mem0 üstüne
   anlamsal arama koyar — temel sürümü ücretsiz (mem0.ai, kredi kartı yok). Önerilir.

Confirm the vault path with the user before creating anything.

---

## PHASE 2 — Prerequisites

Obsidian is required; everything else is optional. Install only what is missing, and never
install anything without telling the user first.

- **Windows:** `winget install Obsidian.Obsidian`
- **Linux:** `flatpak install flathub md.obsidian.Obsidian` (or the distro package / AppImage)
- **macOS:** `brew install --cask obsidian`

Claude Code is already installed — the user is running you. Don't reinstall it.

---

## PHASE 3 — Place the vault

```bash
cp -R ./template/ "{{VAULT_PATH}}/"
chmod +x "{{VAULT_PATH}}/.claude/hooks/"*.sh
```
On Windows use `Copy-Item -Recurse`; `chmod` is a no-op there but the hooks still run,
because they are invoked as `bash script.sh` rather than executed directly.

Create only the optional scope folders the user picked:
`⚔️ 200-Goals` · `🔐 400-Vault` · `💪 700-Body` · `🧘 800-Mind`

---

## PHASE 4 — Wire up the hooks

- **Linux/macOS:** `template/.claude/settings.json` already ships in the right form. Rename it to
  `settings.local.json` in the vault.
- **Windows:** delete `settings.json` and use `settings.windows.json` instead — rename it to
  `settings.local.json` and substitute `{{BASH_PATH}}` and `{{VAULT_PATH_FWD}}`. The POSIX form
  does not work: Windows has no shebang handling for `.sh` files.

Then **run each hook by hand** and confirm the output before moving on:

```bash
bash "{{VAULT_PATH}}/.claude/hooks/session-start.sh"     # must print one line of JSON
```

If it prints nothing, the hook is broken and continuity is silently dead — debug it now.

---

## PHASE 5 — Personalize

Replace every placeholder in every file under the vault. Files that contain them: `CLAUDE.md`,
`🎯 100-Command-Center/Dashboard.md`, all of `🔮 850-Companion/*.md`, the three hooks, and
`.claude/semantic-memory.py`. Then verify:

```bash
grep -rl "{{" "{{VAULT_PATH}}" || echo "✓ tüm placeholder'lar dolduruldu"
```

Keep the folder named `🔮 850-Companion` — the hooks reference that exact path. The companion's
name lives in the file *contents*, not the folder name.

Also add a line to the vault structure section of `CLAUDE.md` for each optional folder created.

---

## PHASE 6 — Desktop launcher (🧠)

```bash
# Linux
./scripts/launcher-linux.sh "{{OS_NAME}}"
# macOS
./scripts/launcher-macos.sh "{{OS_NAME}}"
```
```powershell
# Windows
powershell -ExecutionPolicy Bypass -File scripts\launcher-windows.ps1 -VaultName "{{OS_NAME}}" -VaultPath "{{VAULT_PATH}}"
```

The `obsidian://` handler only resolves after the vault has been opened in Obsidian once, so the
launcher does nothing until PHASE 8. Say so rather than letting the user think it is broken.

---

## PHASE 7 — mem0 semantic memory (optional, free)

Skip entirely if the user said no; the system is fully functional without it.

```bash
uv venv "{{VAULT_PATH}}/.claude/mem0-venv"
uv pip install --python "{{VENV_PYTHON}}" mem0ai
```
`{{VENV_PYTHON}}` is `.claude/mem0-venv/bin/python`, or `.claude/mem0-venv/Scripts/python.exe`
on Windows. **`uv tool install mem0ai` does not work** — it is a library and ships no executables.

Then have the user paste a free key from https://mem0.ai into `.claude/settings.local.json`
under `"env": { "MEM0_API_KEY": "..." }`. Never ask them to send you the key; that file is
gitignored and must stay uncommitted. Verify with:

```bash
"{{VENV_PYTHON}}" "{{VAULT_PATH}}/.claude/semantic-memory.py" add "test"
"{{VENV_PYTHON}}" "{{VAULT_PATH}}/.claude/semantic-memory.py" search "test"
```

---

## PHASE 8 — Verify & first-run report

```bash
ls -la "{{VAULT_PATH}}"
ls -la "{{VAULT_PATH}}/.claude/hooks/"                       # 4 *.sh incl. _common.sh
test -f "{{VAULT_PATH}}/CLAUDE.md" && echo "CLAUDE.md ✓"
test -f "{{VAULT_PATH}}/🔮 850-Companion/Last-Session.md" && echo "memory ✓"
```

Report to the user in Turkish:
- ✅ Ne kuruldu (klasörler, hooks, hafıza, companion adı, 🧠 kısayolu)
- ▶️ **İlk çalıştırma:** Obsidian'ı aç → vault olarak `{{VAULT_PATH}}` seç (bu vault'u Obsidian'a
  bir kez tanıtır; 🧠 ikonu bundan sonra tek tıkla açar). Sonra o klasörde `claude` çalıştır.
- ✨ **Sihri göster:** Bir şey konuş, `/exit` yap, tekrar `claude` aç — {{COMPANION}} geçen
  oturumu hatırlıyor olacak. Devamlılık = fark.
