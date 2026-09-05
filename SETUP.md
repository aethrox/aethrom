# SETUP.md - Activate this second brain (Claude Code runbook)

> You are a coding agent running inside a fresh clone of this repo. The user wants their own AI
> second brain. The scaffold is in `./template/`. Interview them, copy it to its real home,
> personalize it, and build the launcher.
>
> Most of this runbook is agent-independent. PHASE 4 is the exception: hooks are a Claude Code
> feature. If you are another agent, skip it and say so in the final report.

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
`{{VAULT_PATH}}` · `{{TODAY}}` · `{{USER_ID}}` · `{{VENV_PYTHON}}` · `{{PYTHON_PATH}}` ·
`{{GUARD_COMMAND}}` · `{{GUARD_ARG1}}` · `{{GUARD_SCRIPT}}`

---

## PHASE 0 - Detect the platform

| | Windows | Linux | macOS |
|---|---|---|---|
| detect | `$env:OS -eq 'Windows_NT'` | `uname -s` = Linux | `uname -s` = Darwin |
| machine name | `$env:COMPUTERNAME` | `hostname` | `scutil --get ComputerName` |
| vault default | `$env:USERPROFILE\Documents\{{OS_NAME}}` | `~/Documents/{{OS_NAME}}` | see below |

macOS vault default: if `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/` exists use
`.../Documents/{{OS_NAME}}` (syncs across devices), else `~/Documents/{{OS_NAME}}`.

Derive `{{OS_NAME}}`: PascalCase the machine name and append `OS`, stripping
`MacBook/Pro/Air/iMac/'s` and dashes. `Johns-MacBook-Pro` → `JohnOS`, `AETHROX` → `AethroxOS`.
Propose it, let the user override. Set `{{TODAY}}` = `date +%F`.

### Find a working Python
The hooks are Python now, invoked directly (exec form, no shell, no shebang), so `{{PYTHON_PATH}}`
must be an absolute path to an interpreter that actually runs. Presence on PATH is not enough: on
this user's Windows machine `python3` resolves to a Microsoft Store stub that exists on PATH but
fails the moment it is executed, while `python` works. So **run** each candidate, don't just check
for it:

```bash
python3 -c "import sys; print(sys.version_info[0])"   # try first
python -c "import sys; print(sys.version_info[0])"    # fall back to this
```

Take the first candidate that actually prints `3`, then resolve it to an absolute path
(`command -v python3` / `(Get-Command python).Source`) and use that as `{{PYTHON_PATH}}`.

The guard is the second hook entry on `SessionStart` only, a dependency-free fallback that warns
the user when `{{PYTHON_PATH}}` stops working. It sits on `SessionStart` alone because that is the
only event whose output reaches the user as injected context, and one warning per session is
enough. Resolve its three placeholders per platform:

| | `{{GUARD_COMMAND}}` | `{{GUARD_ARG1}}` | `{{GUARD_SCRIPT}}` |
|---|---|---|---|
| Linux, macOS | `sh` | `--` | `${CLAUDE_PROJECT_DIR}/.claude/hooks/guard.sh` |
| Windows | `cmd` | `/c` | `${CLAUDE_PROJECT_DIR}\\.claude\\hooks\\guard.cmd` |

The `--` on POSIX is what keeps both platforms on the same three-slot argument shape, so
`settings.json` stays valid JSON with placeholders only ever appearing inside strings.

`backup.sh` and `scripts/schedule-backup.ps1` still require Git Bash on Windows: the Git Bash
dependency was removed from the hooks, not from the repository. `scripts/schedule-backup.ps1`
throws if it cannot find one. See PHASE 6b for finding it.

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
mkdir -p "{{VAULT_PATH}}"
cp -R ./template/. "{{VAULT_PATH}}/"
```
```powershell
# Windows
New-Item -ItemType Directory -Force "{{VAULT_PATH}}" | Out-Null
Copy-Item ".\template\*" "{{VAULT_PATH}}" -Recurse -Force
```

The trailing `/.` is not a typo: `cp -R ./template/ dest/` puts a `template/` folder *inside* an
existing destination instead of copying the contents out. Check afterwards that `AGENTS.md` sits
at the vault root and there is no `template` directory under it.

Nothing here needs `chmod +x`. The hooks are invoked in exec form (`{{PYTHON_PATH}}` with
`hooks.py` as an argument, `sh`/`cmd` with `guard.sh`/`guard.cmd` as an argument), so no shebang
or execute bit is ever relied on, on any platform.

Create only the optional scope folders the user picked:
`⚔️ 200-Goals` · `🔐 400-Vault` · `💪 700-Body` · `🧘 800-Mind`

Then make the vault a git repo. `backup.sh` refuses to run outside one, and PHASE 6b has nothing
to schedule without it. The `.gitignore` came with the template, so the key file is already
excluded:

```bash
git -C "{{VAULT_PATH}}" init -b main
git -C "{{VAULT_PATH}}" add -A
git -C "{{VAULT_PATH}}" commit -m "{{OS_NAME}}: initial vault"
```

If the commit fails because git has no identity on this machine, ask the user for the name and
email to use and set them with `git config`. Do not guess them.

---

## PHASE 4 - Wire up the hooks (Claude Code only)

Hooks are what make the memory protocol automatic: they inject the last session at startup and
nudge for a memory write before the session ends. No other agent has them. If you are not Claude
Code, skip to PHASE 5 and tell the user at the end that the protocol in `AGENTS.md` holds either
way, it is just read rather than enforced.

`template/.claude/settings.json` is the same file on every platform: one Python dispatcher
(`hooks.py`) on each of the three events, plus one guard fallback on `SessionStart`, wired in
exec form. Rename it to
`settings.local.json` in the vault, then substitute the placeholders found in PHASE 0:
`{{PYTHON_PATH}}`, `{{GUARD_COMMAND}}`, `{{GUARD_ARG1}}`, `{{GUARD_SCRIPT}}`.

Then **run each subcommand by hand** and confirm the output before moving on:

```bash
echo '{"session_id":"test"}' | "{{PYTHON_PATH}}" "{{VAULT_PATH}}/.claude/hooks/hooks.py" session-start
```

That must print exactly one line of JSON. If it prints nothing, the hook is broken and continuity
is silently dead, debug it now.

---

## PHASE 5 - Personalize

First rename the folder from `🔮 850-Companion` to `🔮 850-{{COMPANION}}` (same value used
everywhere else). `hooks.py` never hardcodes this name (it globs for `🔮 850-*`), but
`semantic-memory.py` does reference the resolved name and expects it post-personalization. Keep
the emoji and the `850-` prefix exactly; only the name after the dash changes.

Then replace every placeholder in every file under the vault. Files that contain them:
`AGENTS.md`, `CLAUDE.md`, `🎯 100-Command-Center/Dashboard.md`, all of
`🔮 850-{{COMPANION}}/*.md`, `.claude/settings.local.json` (`{{PYTHON_PATH}}`, `{{GUARD_COMMAND}}`,
`{{GUARD_ARG1}}`, `{{GUARD_SCRIPT}}`), `.claude/backup.sh`, and `.claude/semantic-memory.py`. `hooks.py` and
`_common.py` themselves carry no placeholders. Then verify:

```bash
grep -rl "{{" "{{VAULT_PATH}}" || echo "all placeholders resolved"
```

Also add a line to the vault structure section of `AGENTS.md` for each optional folder created.
`CLAUDE.md` is a pointer to it and carries no structure of its own, so it needs nothing here.

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

The backup pushes to a remote, so the vault needs one. PHASE 3 made it a repo; check whether it
already tracks anything with `git -C "{{VAULT_PATH}}" rev-parse '@{u}'`. If that fails, offer to
set one up before scheduling.

> **The repo must be private.** This vault holds notes, plans and possibly finances. Never create
> it public, and say this out loud rather than assuming the user knows.

With the `gh` CLI available and the user agreeing:

```bash
gh repo create "{{OS_NAME}}" --private --source "{{VAULT_PATH}}" --remote origin --push
```

Without `gh`, ask the user to create an empty **private** repo and paste its URL, then:

```bash
git -C "{{VAULT_PATH}}" remote add origin <url>
git -C "{{VAULT_PATH}}" push -u origin main
```

If the user declines a remote, skip the rest of this phase and say the backup is not scheduled,
so it does not look like it silently failed.

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

Note that `backup.sh` and `scripts/schedule-backup.ps1` still require Git Bash on Windows even
though the hooks no longer do. `scripts/schedule-backup.ps1` locates it itself and throws if it
cannot find one; the Git Bash dependency was removed from the hooks, not from the repository.

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
test -f "{{VAULT_PATH}}/AGENTS.md" && echo "AGENTS.md ok"
test -f "{{VAULT_PATH}}/🔮 850-{{COMPANION}}/Last-Session.md" && echo "memory ok"
ls -la "{{VAULT_PATH}}/.claude/hooks/"                       # only if you did PHASE 4
```

Report to the user in `{{LANGUAGE}}`:
- ✅ **What was built:** folders, memory files, the companion's name, the 🧠 shortcut, and the
  hooks if you wired them
- ▶️ **First run:** open Obsidian and pick `{{VAULT_PATH}}` as a vault. That introduces it to
  Obsidian once; the 🧠 icon opens it in one click from then on. Then open your agent in that
  folder.
- ✨ **Show them the magic:** say something, end the session, start a new one. {{COMPANION}} will
  remember the last one. Continuity is the whole difference.
- ⚠️ Name every optional step that was skipped or failed (icon, mem0, Obsidian install, the
  scheduled backup). Do not pass over them silently. If you skipped the hooks, say that the memory
  protocol now depends on the agent following `AGENTS.md` rather than being reminded by the
  harness.
