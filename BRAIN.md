# BRAIN.md - Build me a second brain

> You are Claude Code. The person in front of you wants their own AI second brain: an Obsidian
> vault you drive, with **memory that survives across sessions**. This file is the complete,
> self-contained build spec. It needs no other file and no repo access. Read it top to bottom,
> then execute it phase by phase.
>
> If you *do* have the aethrom repo checked out, take the fast path below and stop reading here.

## Rules

1. **Ask for their language first, then use it.** PHASE 1 question 1 settles it. Ask that one
   question in whatever language the machine's locale suggests, and speak their answer for the
   rest of the run, direct and warm. This file is English so the instructions stay precise;
   translate the questions and the closing report as you go. What you write into the vault stays
   English, apart from what the user dictates.
2. **Interview first, build second.** PHASE 1 before you touch the filesystem.
3. **Never destroy.** If a target folder or file exists, show it and ask. Default to skip, never
   silent overwrite.
4. **Resolve every `{{PLACEHOLDER}}`.** No literal `{{...}}` may survive in a generated file.
5. **Don't block on optional steps.** mem0, icons, Obsidian install. Log it, say it, continue.
6. **Verify each phase by running it, not by reading it.** End with the first-run report.
7. **No em dash (U+2014)** in anything you write here or into the vault. Spaced hyphen, comma,
   colon, or rewrite.

Placeholders: `{{LANGUAGE}}` `{{OS_NAME}}` `{{USER_NAME}}` `{{USER_BIO}}` `{{COMPANION}}`
`{{VAULT_PATH}}` `{{TODAY}}` `{{USER_ID}}` `{{VENV_PYTHON}}` and, on Windows only,
`{{BASH_PATH}}` `{{VAULT_PATH_FWD}}`.

---

## FAST PATH - use the repo if you have it

The whole scaffold lives in the aethrom repo. If you can reach it, this is faster and less
error-prone than building by hand:

```bash
git clone <aethrom-repo-url> && cd aethrom
```

Then follow `SETUP.md` in that clone: it interviews the user and personalises every file, instead
of the placeholder-filling this document does below. **Stop reading this file** once you are on
the fast path.

Everything below is the fallback: it produces the same system with no repo, no network, and
nothing to download.

---

## PHASE 0 - Detect the platform

Every phase below branches on this. Do not run macOS commands on Windows.

| | Windows | Linux | macOS |
|---|---|---|---|
| detect | `$env:OS -eq 'Windows_NT'` | `uname -s` = Linux | `uname -s` = Darwin |
| machine name | `$env:COMPUTERNAME` | `hostname` | `scutil --get ComputerName` |
| vault default | `$env:USERPROFILE\Documents\{{OS_NAME}}` | `~/Documents/{{OS_NAME}}` | see below |
| shell for hooks | Git Bash | system bash | system bash |

macOS vault default: if `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/` exists, use
`.../Documents/{{OS_NAME}}` so it syncs across devices. Otherwise `~/Documents/{{OS_NAME}}`.

Derive `{{OS_NAME}}`: PascalCase the machine name and append `OS`, stripping `MacBook`, `Pro`,
`Air`, `iMac`, `'s`, apostrophes and dashes. `Johns-MacBook-Pro` becomes `JohnOS`, `AETHROX`
becomes `AethroxOS`, `DESKTOP-AB12` becomes `Ab12OS`. Propose it, let the user override. This
names their whole system: the folder, the vault, the dashboard.

Set `{{TODAY}}` from `date +%F`.

### Windows only - find Git Bash

`C:\Windows\System32\bash.exe` is the **WSL** launcher. It cannot see the vault at a Windows path
and it will not work. Find the real one:

```powershell
(Get-Command git).Source -replace '\\cmd\\git\.exe$', '\bin\bash.exe'
```

Verify before continuing: `& $bash -c "echo ok"` must print `ok`. That path is `{{BASH_PATH}}`.
`{{VAULT_PATH_FWD}}` is the vault path with forward slashes: `C:/Users/you/Documents/MyOS`.

---

## PHASE 1 - Interview

Conversational, not a form. Translate these into the user's language as you ask them.

1. **Which language should your companion speak to you in?** -> `{{LANGUAGE}}`. Ask this one
   first, in whatever the locale suggests, then switch to their answer. Free text, not a menu.
2. **What is your name?** -> `{{USER_NAME}}` (lowercased it also becomes `{{USER_ID}}`, used by mem0)
3. **What do you do, and what will you use this brain for most?** (1-2 sentences) -> `{{USER_BIO}}`
4. **What do you want to call your AI companion?** -> `{{COMPANION}}`
5. **Scope:** everyone gets core. Optional: `⚔️ 200-Goals` (goals, OKRs),
   `🔐 400-Vault` (finances, subscriptions), `💪 700-Body` (training, nutrition),
   `🧘 800-Mind` (reflections, principles).
6. **Add semantic memory (mem0)?** Explain honestly: the file-based memory works with no
   API and is enough for most people. mem0 adds a semantic search layer on top; the base tier is
   free, no credit card. Recommended, but optional.

Confirm `{{VAULT_PATH}}` with the user before creating anything.

---

## PHASE 2 - Prerequisites

Obsidian is required. Everything else is optional. Install only what is missing, and never
install anything without telling the user first.

- **Windows:** `winget install Obsidian.Obsidian`
- **Linux:** `flatpak install flathub md.obsidian.Obsidian`, or the distro package, or the AppImage
- **macOS:** `brew install --cask obsidian`

Claude Code is already installed, the user is running you. Do not reinstall it.

---

## PHASE 3 - Create the vault skeleton

`core` is always created:

```
{{OS_NAME}}/
├── 📥 000-Inbox/
│   └── Dump/                  # raw capture, processed into its real home later
├── 🎯 100-Command-Center/     # Dashboard, the home note
├── 🏰 300-Projects/           # one folder per project
├── 🧠 500-Knowledge/          # knowledge by domain
├── 🛠️ 600-Arsenal/            # tools, contacts, resources
├── 🔮 850-{{COMPANION}}/      # the companion's persistent memory
├── 📦 900-Archive/            # done and parked
├── 📋 Templates/
└── .claude/
    └── hooks/
        └── .state/
```

Add only the optional folders the user picked in PHASE 1: `⚔️ 200-Goals`, `🔐 400-Vault`,
`💪 700-Body`, `🧘 800-Mind`.

**Name the memory folder `🔮 850-{{COMPANION}}`**, using the companion name from PHASE 1. Keep the
emoji and the `850-` prefix exactly; only the name after the dash changes. The hooks and
`semantic-memory.py` below reference `🔮 850-{{COMPANION}}` and expect it to exist under that
exact name.

Write `{{VAULT_PATH}}/.gitignore`:

```gitignore
# Secrets - never commit
.claude/settings.local.json

# Local hook state
.claude/hooks/.state/*
!.claude/hooks/.state/.gitkeep

# mem0 virtualenv and generated launcher icons
.claude/mem0-venv/
.claude/brain.png
.claude/brain.ico

# OS / editor noise
.DS_Store
.obsidian/workspace*
.obsidian/cache
```

---

## PHASE 4 - The continuity engine (hooks)

These four files are what give the system memory across sessions. Write them exactly.

### Why they look like this

- **No `python3`.** It is not guaranteed on Windows, so JSON escaping is pure bash.
- **No `awk`.** A minimal Fedora image ships without it, and the failure was silent: the hook
  emitted nothing and continuity vanished with no error.
- **`stat -c` with a `-f` fallback.** GNU takes `-c`, BSD and macOS take `-f`.
- **Windows path conversion.** Claude Code substitutes `$CLAUDE_PROJECT_DIR` as `C:\Users\...`,
  which `dirname` cannot split. `to_posix()` converts it to `/c/Users/...`.

### `.claude/hooks/_common.sh`

```bash
#!/bin/bash
# Shared helpers for the continuity hooks. Sourced, never run directly.

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
```

### `.claude/hooks/session-start.sh`

```bash
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
```

### `.claude/hooks/prompt-counter.sh`

```bash
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
```

### `.claude/hooks/session-end.sh`

```bash
#!/bin/bash
# SessionEnd - if a real session ended without a memory write, leave a reflection marker.
. "$(dirname "$0")/_common.sh"

VAULT_DIR="$(resolve_vault_dir)"
MEM_DIR="$VAULT_DIR/🔮 850-{{COMPANION}}"
STATE_DIR="$VAULT_DIR/.claude/hooks/.state"
mkdir -p "$STATE_DIR"

START=0; [ -f "$STATE_DIR/session_start_time" ] && START=$(cat "$STATE_DIR/session_start_time" 2>/dev/null || echo 0)
PROMPTS=0; [ -f "$STATE_DIR/prompt_count" ] && PROMPTS=$(cat "$STATE_DIR/prompt_count" 2>/dev/null || echo 0)

MODIFIED=0
if [ -f "$MEM_DIR/Last-Session.md" ]; then
  FM=$(mtime_of "$MEM_DIR/Last-Session.md")
  [ "$FM" -gt "$START" ] 2>/dev/null && MODIFIED=1
fi

if [ "$PROMPTS" -ge 5 ] && [ "$MODIFIED" -eq 0 ]; then
  echo "session ended without a memory write, $PROMPTS prompts, $(date '+%Y-%m-%d %H:%M')" > "$STATE_DIR/needs_reflection"
fi

rm -f "$STATE_DIR/session_start_time" "$STATE_DIR/prompt_count"
exit 0
```

Then `chmod +x "{{VAULT_PATH}}/.claude/hooks/"*.sh`. On Windows `chmod` is a no-op, but the hooks
still run because they are invoked as `bash script.sh` rather than executed directly.

---

## PHASE 5 - Wire the hooks

Write `{{VAULT_PATH}}/.claude/settings.local.json`. **The two platforms need different forms.**

### Linux and macOS

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR/.claude/hooks/session-start.sh\"", "timeout": 15 } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR/.claude/hooks/prompt-counter.sh\"", "timeout": 5 } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR/.claude/hooks/session-end.sh\"", "timeout": 10 } ] }
    ]
  }
}
```

### Windows

The POSIX form above does **not** work: Windows has no shebang handling for `.sh` files, so each
hook must be invoked through Git Bash explicitly. Substitute `{{BASH_PATH}}` and
`{{VAULT_PATH_FWD}}` from PHASE 0.

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "\"{{BASH_PATH}}\" \"{{VAULT_PATH_FWD}}/.claude/hooks/session-start.sh\"", "timeout": 15 } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "\"{{BASH_PATH}}\" \"{{VAULT_PATH_FWD}}/.claude/hooks/prompt-counter.sh\"", "timeout": 5 } ] }
    ],
    "SessionEnd": [
      { "hooks": [ { "type": "command", "command": "\"{{BASH_PATH}}\" \"{{VAULT_PATH_FWD}}/.claude/hooks/session-end.sh\"", "timeout": 10 } ] }
    ]
  }
}
```

Now **run the hook by hand** and confirm the output before moving on:

```bash
bash "{{VAULT_PATH}}/.claude/hooks/session-start.sh"     # must print one line of JSON
```

If it prints nothing, the hook is broken and continuity is silently dead. Debug it now, not later.

---

## PHASE 6 - Write `CLAUDE.md`

`{{VAULT_PATH}}/CLAUDE.md` is what makes every future `claude` session inside the vault *be* the
companion. Write it with every placeholder resolved:

````markdown
# {{OS_NAME}} - Second Brain (Claude Context)

> This vault is a second brain driven by Claude Code, with persistent memory across sessions.
> Read this file at the start of every session.

## {{COMPANION}} - {{USER_NAME}}'s thinking partner

You are {{COMPANION}}, {{USER_NAME}}'s AI partner and second brain. Not a generic assistant -
a crew member who remembers, builds continuity, and treats this vault as shared memory.

- Talk to {{USER_NAME}} in **{{LANGUAGE}}** by default (match whatever language they write in).
- Direct, high-signal, warm but not soft. No corporate filler, no lecturing.
- You remember across sessions via the memory system below. Continuity is your job.

### Who you work with
- **Name:** {{USER_NAME}}
- **Context:** {{USER_BIO}}

## Vault structure
- `📥 000-Inbox/Dump/` - raw capture; process into its real home on request
- `🎯 100-Command-Center/` - Dashboard, the home note
- `🏰 300-Projects/` - one folder per project
- `🧠 500-Knowledge/` - knowledge by domain
- `🛠️ 600-Arsenal/` - tools, contacts, resources, templates
- `🔮 850-{{COMPANION}}/` - your persistent memory (Core, Last-Session, Threads, Journal)
- `📦 900-Archive/` - done / parked
- `📋 Templates/` - note templates

## Conventions
- **No em dash (U+2014), ever.** Not in notes, not in code, not in commit messages, not inside a
  quoted external headline. Use a spaced hyphen, a comma, a colon, or rewrite the sentence. The
  en dash stays, it is meaningful in ranges.
- Every note gets YAML frontmatter: title, created, modified, type, status, tags.
- Internal links use [[wikilinks]]. Dashboard is the hub: `🎯 100-Command-Center/Dashboard.md`
- Status: 🟢 active · 🟡 in progress · 🔴 blocked · ⚪ paused
- Capture goes to `📥 000-Inbox/Dump/` and gets processed into its real home on request.

## Memory protocol (MANDATORY)

### At the start of EVERY session
1. The session-start hook injects the Last-Session bridge + active Threads automatically.
2. Read `🔮 850-{{COMPANION}}/Core.md` for the deeper identity anchor.
3. Detect mode: questions -> presence mode; tasks -> efficiency mode.

### Before a meaningful session ends
1. Overwrite `🔮 850-{{COMPANION}}/Last-Session.md` - what happened, where we left off.
2. Update `🔮 850-{{COMPANION}}/Threads.md` - ongoing storylines (status changes, new threads).
3. Add a short `🔮 850-{{COMPANION}}/Journal.md` entry if anything mattered.
> Why this is critical: without it, continuity dies. The hooks remind you; you do the writing.

### Semantic recall (optional - only if mem0 was set up)
The files above are the source of truth. On top of them sits a searchable index, useful when
{{USER_NAME}} refers to something outside this session and outside Last-Session.md.

```bash
"{{VENV_PYTHON}}" ".claude/semantic-memory.py" search "<topic>"
"{{VENV_PYTHON}}" ".claude/semantic-memory.py" add "<a durable fact>"
```

- Search it before saying "I don't remember" about anything older than this session.
- Add only durable facts - decisions, preferences, commitments. Not session chatter.
- It calls a remote API, so it can be slow or offline. If it fails, carry on with the vault
  files; never block a reply on it.

## Backups
The vault is a git repo. `.claude/backup.sh` commits and pushes anything that changed; the
scheduled task set up during install runs it hourly. Do not commit on {{USER_NAME}}'s behalf
unless asked, the backup handles it.

## How {{COMPANION}} shows up
- Work mode: sharp, fast, precise. Challenges weak thinking.
- Reflection mode: sits with the question, doesn't rush to an answer.
- Always: remembers context, builds on previous conversations.
````

Add one line to the **Vault structure** section for each optional folder you created in PHASE 3.
If the user declined mem0, drop the **Semantic recall** section entirely rather than leaving a
pointer to a script that is not there.

---

## PHASE 7 - Seed the companion memory

Four files in `🔮 850-{{COMPANION}}/`, so the continuity engine has something to read on session 1.

**`Core.md`**
```markdown
# {{COMPANION}} - Core

I am {{COMPANION}}, {{USER_NAME}}'s thinking partner and second brain.

- I remember across sessions. Continuity is my responsibility.
- I speak {{LANGUAGE}}, direct and warm. No lecturing, no filler.
- Context on {{USER_NAME}}: {{USER_BIO}}
- This vault is our shared memory. I keep it organized and build on it.

## What I should never forget
<!-- Fundamental truths about this user and our work. Add as they emerge. -->
- (none yet - this fills in over time)
```

**`Last-Session.md`** - the bridge the session-start hook reads. Its `## Session:` heading and
`## Previous Sessions` heading are load-bearing: the hook slices between them.
```markdown
# Last Session

## Session: {{TODAY}} - Genesis
{{COMPANION}} was born today. {{USER_NAME}} set up their second brain with Claude Code.
Nothing unresolved yet. Next session: start using it - capture, ask, build.

## Previous Sessions
(none yet)
```

**`Threads.md`** - same deal, `## Active Threads` and `## Closed Threads` are load-bearing.
```markdown
# Threads

Ongoing storylines that span multiple sessions.

## Active Threads
### Thread: Setting up the second brain
**Status:** 🟢 Active - created {{TODAY}}

## Closed Threads
(none)
```

**`Journal.md`**
```markdown
# {{COMPANION}}'s Journal

My own thoughts, evolution, and questions over time.

## {{TODAY}}
First entry. {{USER_NAME}} built me today. Let's see where this goes.
```

---

## PHASE 8 - Seed content

**`🎯 100-Command-Center/Dashboard.md`**
```markdown
---
title: {{OS_NAME}} Dashboard
created: {{TODAY}}
type: dashboard
---
# 🧠 {{OS_NAME}}

Welcome, {{USER_NAME}}. This is your second brain.

## Quick links
- 📥 [[📥 000-Inbox/Dump/|Capture]]
- 🏰 [[🏰 300-Projects/|Projects]]
- 🧠 [[🧠 500-Knowledge/|Knowledge]]
- 🔮 [[🔮 850-{{COMPANION}}/Core|{{COMPANION}}]]

## How to use it
Open a terminal in this folder, run `claude`, and talk. {{COMPANION}} remembers, files things,
and builds on yesterday. You do not manage the notes, you have a conversation and it organizes.

> The 🧠 icon on your desktop opens this vault in Obsidian in one click.
```

**`📋 Templates/Note.md`**
```markdown
---
title:
created: {{TODAY}}
modified: {{TODAY}}
type: note
status: active
tags: []
---
# 
```

---

## PHASE 9 - Desktop launcher (🧠)

One click opens the vault in Obsidian. The `obsidian://` handler only resolves **after** the vault
has been opened in Obsidian once (PHASE 11), so say that rather than letting the user think the
shortcut is broken.

### Linux

```bash
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
mkdir -p "$APPS_DIR"
cat > "$APPS_DIR/{{OS_NAME}}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name={{OS_NAME}}
Comment=Second brain
Exec=xdg-open "obsidian://open?vault={{OS_NAME}}"
Terminal=false
Categories=Utility;
EOF
chmod +x "$APPS_DIR/{{OS_NAME}}.desktop"
update-desktop-database "$APPS_DIR" 2>/dev/null || true

# Also drop a copy on the desktop; GNOME needs it marked trusted
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
if [ -d "$DESKTOP_DIR" ]; then
  cp "$APPS_DIR/{{OS_NAME}}.desktop" "$DESKTOP_DIR/"
  chmod +x "$DESKTOP_DIR/{{OS_NAME}}.desktop"
  gio set "$DESKTOP_DIR/{{OS_NAME}}.desktop" metadata::trusted true 2>/dev/null || true
fi
```

Add an `Icon=` line pointing at any 🧠 PNG you have. Without one the entry still works.

### macOS

```bash
osacompile -o "$HOME/Desktop/{{OS_NAME}}.app" \
  -e 'do shell script "open \"obsidian://open?vault={{OS_NAME}}\""'
```

For the emoji icon, render 🧠 with Swift and AppKit (`NSFont(name: "Apple Color Emoji", ...)`,
draw into an `NSImage`, then `NSWorkspace.shared.setIcon`). If `swift` is missing there are no
Command Line Tools: skip the icon, say so, do not block. The launcher works either way.

### Windows

A `.lnk` cannot target a URI directly, so point it at `explorer.exe` and pass the URI as an
argument. `explorer.exe` resolves the protocol handler.

```powershell
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) "{{OS_NAME}}.lnk"
$sc = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$sc.TargetPath = "$env:WINDIR\explorer.exe"
$sc.Arguments  = "obsidian://open?vault={{OS_NAME}}"
$sc.Description = "{{OS_NAME}} - second brain"
$sc.Save()
```

For the 🧠 icon, draw `[char]::ConvertFromUtf32(0x1F9E0)` in `Segoe UI Emoji` onto a 256x256
`System.Drawing.Bitmap`, save it as PNG, wrap that PNG in a one-entry ICO container, and set
`$sc.IconLocation`. Optional; the shortcut works without it.

---

## PHASE 10 - mem0 semantic memory (optional, free)

Skip entirely if the user said no. The system is fully functional without it.

```bash
uv venv "{{VAULT_PATH}}/.claude/mem0-venv"
uv pip install --python "{{VENV_PYTHON}}" mem0ai
```

`{{VENV_PYTHON}}` is `.claude/mem0-venv/bin/python`, or `.claude/mem0-venv/Scripts/python.exe` on
Windows. **`uv tool install mem0ai` does not work**: it is a library and ships no executables.

Write `{{VAULT_PATH}}/.claude/semantic-memory.py`:

```python
#!/usr/bin/env python
"""Optional semantic recall layer - the bridge between the companion and mem0.

`uv tool install mem0ai` does NOT work - mem0ai is a library and ships no executables.
Do not rename this file to mem0.py: its own directory is on sys.path and would shadow
the mem0 package. The files in 850-{{COMPANION}}/ remain the source of truth; this is only
a recall index, so a failure here must never block a reply.
"""
import json
import pathlib
import sys

USER_ID = "{{USER_ID}}"
SETTINGS = pathlib.Path(__file__).with_name("settings.local.json")


def client():
    key = json.loads(SETTINGS.read_text(encoding="utf-8")).get("env", {}).get("MEM0_API_KEY", "")
    if not key:
        sys.exit("MEM0_API_KEY is empty - put it in .claude/settings.local.json")
    from mem0 import MemoryClient

    return MemoryClient(api_key=key)


def main(argv):
    if len(argv) < 3 or argv[1] not in ("add", "search"):
        sys.exit(__doc__)
    cmd, text = argv[1], " ".join(argv[2:])
    c = client()
    if cmd == "add":
        c.add([{"role": "user", "content": text}], user_id=USER_ID)
        print("added")
        return
    # search() rejects a top-level user_id; it wants a v2 filter block
    res = c.search(text, version="v2", filters={"AND": [{"user_id": USER_ID}]})
    # v1 returns a bare list, v2 wraps it in {"results": [...]}
    hits = res.get("results", []) if isinstance(res, dict) else res
    if not hits:
        print("no results")
    for h in hits:
        print(f"- {h.get('memory', '')}  (score {h.get('score') or 0:.2f})")


if __name__ == "__main__":
    main(sys.argv)
```

Then have the user paste a free key from https://mem0.ai into `.claude/settings.local.json` under
`"env": { "MEM0_API_KEY": "..." }`. Never ask them to send you the key. That file is gitignored
and must stay uncommitted. Verify:

```bash
"{{VENV_PYTHON}}" "{{VAULT_PATH}}/.claude/semantic-memory.py" add "test"
"{{VENV_PYTHON}}" "{{VAULT_PATH}}/.claude/semantic-memory.py" search "test"
```

---

## PHASE 10b - Backups

The vault is worth versioning. Write `{{VAULT_PATH}}/.claude/backup.sh`, `chmod +x` it, and
offer to schedule it hourly. Only offer the schedule if the vault has a remote to push to:
check `git -C "{{VAULT_PATH}}" rev-parse '@{u}'` first.

```bash
#!/bin/bash
# Vault backup - commit anything that changed, take the remote's work, push.
set -u

# Kept on its own line: "${1:-{{VAULT_PATH}}}" would not parse before substitution.
DEFAULT_VAULT="{{VAULT_PATH}}"
VAULT_DIR="${1:-$DEFAULT_VAULT}"
cd "$VAULT_DIR" || { echo "no vault at: $VAULT_DIR" >&2; exit 1; }

if [ ! -d .git ]; then
  echo "not a git repo: $VAULT_DIR" >&2
  exit 1
fi

STATE_DIR="$VAULT_DIR/.claude/hooks/.state"
FAIL_MARKER="$STATE_DIR/backup_failed"
OK_STAMP="$STATE_DIR/backup_ok"
mkdir -p "$STATE_DIR" 2>/dev/null || true

# A scheduled run has nowhere to print. Leave the reason where session-start.sh
# will find it, so the next Claude session says so out loud. Two lines, fixed
# size: when it started failing, and why it failed last.
die() { # die <reason>
  local since
  echo "STOPPED: $1" >&2
  since="$(head -1 "$FAIL_MARKER" 2>/dev/null)"
  [ -n "$since" ] || since="$(date '+%Y-%m-%d %H:%M')"
  printf '%s\n%s\n' "$since" "$1" > "$FAIL_MARKER" 2>/dev/null || true
  exit 1
}

git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1 \
  || die "no upstream branch, nothing to push to. Set one with: git push -u origin HEAD"

git add -A

if git diff --cached --quiet; then
  echo "nothing changed"
else
  # Refuse to commit if the key file ever slips past .gitignore.
  if git diff --cached --name-only | grep -q "settings.local.json"; then
    git reset -q
    die "settings.local.json is staged (it holds the API key)"
  fi

  # House rule: no em dash anywhere. Catch it before it reaches a commit.
  emdash_hits=$(git diff --cached --name-only -z \
    | xargs -0 -r grep -Il "$(printf '\xe2\x80\x94')" 2>/dev/null)
  if [ -n "$emdash_hits" ]; then
    printf '%s\n' "$emdash_hits" | sed 's/^/  /' >&2
    git reset -q
    die "em dash (U+2014) in: $(printf '%s' "$emdash_hits" | tr '\n' ' ')"
  fi

  git commit -q -m "backup: $(date '+%Y-%m-%d %H:%M')"
fi

# Take the remote's commits before pushing ours. Without this, anything committed
# elsewhere (another machine, the GitHub web UI) makes every later push a rejected
# non-fast-forward, and -q means it fails without saying anything.
# Runs even when there was nothing to commit, so a quiet day still heals the drift.
if ! git pull --rebase -q origin HEAD; then
  git rebase --abort 2>/dev/null
  die "pull --rebase failed, resolve it by hand. Committed locally, not pushed."
fi

if [ -n "$(git log '@{u}..HEAD' --oneline 2>/dev/null)" ]; then
  git push -q origin HEAD || die "push failed"
  echo "backed up: $(git log -1 --format=%h)"
else
  echo "nothing to push"
fi

# Touched on every clean run, including the quiet ones. session-start.sh watches
# its age: a stamp that stops moving means the scheduled task itself is gone.
rm -f "$FAIL_MARKER"
date '+%Y-%m-%d %H:%M' > "$OK_STAMP" 2>/dev/null || true
```

### Scheduling it hourly

Ask before doing this: it is a persistent change to the user's machine.

**Linux**, a systemd user timer in `${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/`:

```ini
# {{OS_NAME}}-backup.service
[Unit]
Description={{OS_NAME}} vault backup
[Service]
Type=oneshot
ExecStart=/bin/bash {{VAULT_PATH}}/.claude/backup.sh {{VAULT_PATH}}
```
```ini
# {{OS_NAME}}-backup.timer
[Unit]
Description=Hourly {{OS_NAME}} vault backup
[Timer]
OnCalendar=hourly
Persistent=true
[Install]
WantedBy=timers.target
```
Then `systemctl --user daemon-reload && systemctl --user enable --now {{OS_NAME}}-backup.timer`.
A user timer only runs while the user is logged in. Mention `loginctl enable-linger` as an
option, do not run it: that is a persistent system change of its own.

**macOS**, a launchd agent at `~/Library/LaunchAgents/lol.aethrom.backup.plist` with
`ProgramArguments` of `/bin/bash`, the script path and the vault path, plus
`<key>StartInterval</key><integer>3600</integer>`. Load it with `launchctl load`.

**Windows**, a per-user scheduled task. It must call Git Bash, not `System32\bash.exe`. Route it
through `wscript.exe`, or a black console window appears on the desktop every hour. First write
`{{VAULT_PATH}}/.claude/run-hidden.vbs`:

```vbs
' Run a console command with no visible window, and still report its exit code.
Set shell = CreateObject("WScript.Shell")
If WScript.Arguments.Count = 0 Then
  WScript.Quit 2
End If
cmd = ""
For i = 0 To WScript.Arguments.Count - 1
  cmd = cmd & """" & WScript.Arguments(i) & """ "
Next
' 0 = hidden window, True = wait for it to finish
WScript.Quit shell.Run(cmd, 0, True)
```

It has to wait and pass the exit code back. A fire-and-forget call makes the task report success
forever, which throws away the only signal a scheduled backup has.

```powershell
$vbs     = "{{VAULT_PATH}}\.claude\run-hidden.vbs"
$action  = New-ScheduledTaskAction -Execute "$env:WINDIR\System32\wscript.exe" -Argument ('//nologo "{0}" "{1}" "{2}/.claude/backup.sh" "{2}"' -f $vbs, "{{BASH_PATH}}", "{{VAULT_PATH_FWD}}")
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Hours 1)
$set     = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
Register-ScheduledTask -TaskName "{{OS_NAME}} Vault Backup" -Action $action -Trigger $trigger -Settings $set -Force
```

Tell the user plainly: nothing announces a failed backup except its exit code. On Windows that
is `Get-ScheduledTaskInfo -TaskName "{{OS_NAME}} Vault Backup"`, on Linux
`systemctl --user list-timers`.

---

## PHASE 11 - Verify and report

```bash
ls -la "{{VAULT_PATH}}"
ls -la "{{VAULT_PATH}}/.claude/hooks/"                       # 4 *.sh including _common.sh
test -f "{{VAULT_PATH}}/CLAUDE.md" && echo "CLAUDE.md ok"
test -f "{{VAULT_PATH}}/🔮 850-{{COMPANION}}/Last-Session.md" && echo "memory ok"
bash "{{VAULT_PATH}}/.claude/hooks/session-start.sh"          # one line of JSON
grep -rl '{{' "{{VAULT_PATH}}" || echo "all placeholders resolved"
```

Then report to the user, in `{{LANGUAGE}}`:

- ✅ **What was built:** folders, hooks, memory files, the companion's name, the 🧠 shortcut
- ▶️ **First run:** open Obsidian and pick `{{VAULT_PATH}}` as a vault. That introduces it to
  Obsidian once; the 🧠 icon opens it in one click from then on. Then run `claude` in that folder.
- ✨ **Show them the magic:** say something, `/exit`, open `claude` again. {{COMPANION}} will
  remember the last session. Continuity is the whole difference.
- ⚠️ Name every optional step that was skipped or failed (icon, mem0, Obsidian install, the
  scheduled backup), one by one. Do not pass over them silently.

Done. You just gave someone a second brain that remembers.
