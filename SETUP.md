# SETUP.md - Activate this second brain (Claude Code runbook)

> You are Claude Code, running inside a fresh clone of this repo. The user wants their own AI
> second brain. The scaffold is in `./template/`. Interview them, copy it to its real home,
> personalize it, and build the launcher.

## Rules
0. **Ask for their language first, then use it.** PHASE 1 question 1 settles which language the
   user wants. Ask that first question in the language the machine's locale suggests, and speak
   whatever they answer for the rest of the run. Every question and message below is written in
   English so the instructions stay precise; translate them as you go. What you write into the
   vault stays English except where a placeholder says otherwise.
1. Interview first, build second. Never leave a literal `{{...}}` in any file.
2. Never destroy. If the target vault path exists, show it and ask before overwriting.
3. Don't block on optional steps (mem0, icons). Log it, tell the user, continue.
4. **Detect the OS first** - every phase below branches on it. Don't run macOS commands on Windows.
5. Verify each phase by running it, not by reading it. End with the first-run report.

Placeholders: `{{LANGUAGE}}` · `{{OS_NAME}}` · `{{USER_NAME}}` · `{{USER_BIO}}` · `{{COMPANION}}` ·
`{{VAULT_PATH}}` · `{{TODAY}}` · `{{USER_ID}}` · `{{VENV_PYTHON}}` ·
(Windows only) `{{BASH_PATH}}` · `{{VAULT_PATH_FWD}}`

---

## PHASE 0 - Detect the platform

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

### Windows only - find Git Bash
`C:\Windows\System32\bash.exe` is the **WSL** launcher and will not work; it cannot see the vault
at a Windows path. Find the real one and use its full path as `{{BASH_PATH}}`:

```powershell
(Get-Command git).Source -replace '\\cmd\\git\.exe$', '\bin\bash.exe'
```

Verify it before continuing: `& $bash -c "echo ok"` must print `ok`.
`{{VAULT_PATH_FWD}}` is the vault path with forward slashes: `C:/Users/you/Documents/MyOS`.

---

## PHASE 1 - Interview (conversational - not a form)

1. **Which language should your companion speak to you in?** → `{{LANGUAGE}}`. Ask this first,
   in the language the locale suggests, and switch to their answer for everything after it. Free
   text, not a menu.
2. **What is your name?** → `{{USER_NAME}}` (also becomes `{{USER_ID}}`, lowercased, for mem0)
3. **What do you do, and what will you use this brain for most?** (1-2 sentences) → `{{USER_BIO}}`
4. **What do you want to call your AI companion?** → `{{COMPANION}}`
5. **Scope:** core (everyone) plus the optional `⚔️ 200-Goals`, `🔐 400-Vault`, `💪 700-Body`,
   `🧘 800-Mind`
6. **Semantic memory (mem0)?** The file-based memory works with no API and is enough for most
   people. mem0 adds semantic search on top; the base tier is free (mem0.ai, no credit card).
   Recommended, but optional.

Confirm the vault path with the user before creating anything.

---

## PHASE 2 - Prerequisites

Obsidian is required; everything else is optional. Install only what is missing, and never
install anything without telling the user first.

- **Windows:** `winget install Obsidian.Obsidian`
- **Linux:** `flatpak install flathub md.obsidian.Obsidian` (or the distro package / AppImage)
- **macOS:** `brew install --cask obsidian`

Claude Code is already installed - the user is running you. Don't reinstall it.

---

## PHASE 3 - Place the vault

```bash
cp -R ./template/ "{{VAULT_PATH}}/"
chmod +x "{{VAULT_PATH}}/.claude/hooks/"*.sh
```
On Windows use `Copy-Item -Recurse`; `chmod` is a no-op there but the hooks still run,
because they are invoked as `bash script.sh` rather than executed directly.

Create only the optional scope folders the user picked:
`⚔️ 200-Goals` · `🔐 400-Vault` · `💪 700-Body` · `🧘 800-Mind`

---

## PHASE 4 - Wire up the hooks

- **Linux/macOS:** `template/.claude/settings.json` already ships in the right form. Rename it to
  `settings.local.json` in the vault.
- **Windows:** delete `settings.json` and use `settings.windows.json` instead - rename it to
  `settings.local.json` and substitute `{{BASH_PATH}}` and `{{VAULT_PATH_FWD}}`. The POSIX form
  does not work: Windows has no shebang handling for `.sh` files.

Then **run each hook by hand** and confirm the output before moving on:

```bash
bash "{{VAULT_PATH}}/.claude/hooks/session-start.sh"     # must print one line of JSON
```

If it prints nothing, the hook is broken and continuity is silently dead - debug it now.

---

## PHASE 5 - Personalize

First rename the folder from `🔮 850-Companion` to `🔮 850-{{COMPANION}}` (same value used
everywhere else) - the hooks and `semantic-memory.py` reference `🔮 850-{{COMPANION}}` and
expect it post-personalization. Keep the emoji and the `850-` prefix exactly; only the name
after the dash changes.

Then replace every placeholder in every file under the vault. Files that contain them:
`CLAUDE.md`, `🎯 100-Command-Center/Dashboard.md`, all of `🔮 850-{{COMPANION}}/*.md`, the
three hooks, `.claude/backup.sh`, and `.claude/semantic-memory.py`. Then verify:

```bash
grep -rl "{{" "{{VAULT_PATH}}" || echo "all placeholders resolved"
```

Also add a line to the vault structure section of `CLAUDE.md` for each optional folder created.

---

## PHASE 6 - Desktop launcher (🧠)

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

## PHASE 6b - Hourly backup

Only if the vault has a remote to push to. Check with
`git -C "{{VAULT_PATH}}" rev-parse '@{u}'`; if it fails, tell the user to
`git push -u origin HEAD` first and schedule it afterwards.

```bash
# Linux (systemd user timer) and macOS (launchd agent)
./scripts/schedule-backup.sh "{{VAULT_PATH}}" "{{OS_NAME}}"
```
```powershell
# Windows (per-user scheduled task)
powershell -ExecutionPolicy Bypass -File scripts\schedule-backup.ps1 -VaultPath "{{VAULT_PATH}}" -VaultName "{{OS_NAME}}"
```

Ask before running it: this is a persistent change to the user's machine. Then confirm it
registered, and say plainly that nothing announces a failed backup except its exit code and the
warning the session-start hook prints.

On Windows the script routes the task through `.claude/run-hidden.vbs`, because Git Bash is a
console program and the task would otherwise flash a black window on the desktop every hour. If
the vault does not carry that file, the task still works but the window comes back.

> On Linux a user timer only runs while the user is logged in. Mention `loginctl enable-linger`
> as an option, do not run it: it is a persistent system change of its own.

---

## PHASE 7 - mem0 semantic memory (optional, free)

Skip entirely if the user said no; the system is fully functional without it.

```bash
uv venv "{{VAULT_PATH}}/.claude/mem0-venv"
uv pip install --python "{{VENV_PYTHON}}" mem0ai
```
`{{VENV_PYTHON}}` is `.claude/mem0-venv/bin/python`, or `.claude/mem0-venv/Scripts/python.exe`
on Windows. **`uv tool install mem0ai` does not work** - it is a library and ships no executables.

Then have the user paste a free key from https://mem0.ai into `.claude/settings.local.json`
under `"env": { "MEM0_API_KEY": "..." }`. Never ask them to send you the key; that file is
gitignored and must stay uncommitted. Verify with:

```bash
"{{VENV_PYTHON}}" "{{VAULT_PATH}}/.claude/semantic-memory.py" add "test"
"{{VENV_PYTHON}}" "{{VAULT_PATH}}/.claude/semantic-memory.py" search "test"
```

---

## PHASE 8 - Verify & first-run report

```bash
ls -la "{{VAULT_PATH}}"
ls -la "{{VAULT_PATH}}/.claude/hooks/"                       # 4 *.sh incl. _common.sh
test -f "{{VAULT_PATH}}/CLAUDE.md" && echo "CLAUDE.md ok"
test -f "{{VAULT_PATH}}/🔮 850-{{COMPANION}}/Last-Session.md" && echo "memory ok"
```

Report to the user in `{{LANGUAGE}}`:
- ✅ **What was built:** folders, hooks, memory files, the companion's name, the 🧠 shortcut
- ▶️ **First run:** open Obsidian and pick `{{VAULT_PATH}}` as a vault. That introduces it to
  Obsidian once; the 🧠 icon opens it in one click from then on. Then run `claude` in that folder.
- ✨ **Show them the magic:** say something, `/exit`, open `claude` again. {{COMPANION}} will
  remember the last session. Continuity is the whole difference.
- ⚠️ Name every optional step that was skipped or failed (icon, mem0, Obsidian install, the
  scheduled backup). Do not pass over them silently.
