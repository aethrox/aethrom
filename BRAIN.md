# BRAIN.md - Build me a second brain

> You are a coding agent. The person in front of you wants their own AI second brain: an Obsidian
> vault you drive, with **memory that survives across sessions**. This file is the complete,
> self-contained build spec. It needs no other file and no repo access. Read it top to bottom,
> then execute it phase by phase.
>
> PHASES 4 and 5 build hooks, which only Claude Code has. Every other phase is agent-independent.
> If you are another agent, skip those two and say so in the closing report.
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
`{{VAULT_PATH}}` `{{TODAY}}` `{{USER_ID}}` `{{VENV_PYTHON}}` `{{PYTHON_PATH}}`
`{{GUARD_COMMAND}}` `{{GUARD_ARG1}}` `{{GUARD_SCRIPT}}` and, on Windows only, for the scheduled backup task in
PHASE 10b: `{{BASH_PATH}}` `{{VAULT_PATH_FWD}}`.

---

## FAST PATH - use the repo if you have it

The whole scaffold lives in the aethrom repo. If you can reach it, this is faster and less
error-prone than building by hand:

```bash
git clone https://github.com/aethrox/aethrom.git && cd aethrom
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

macOS vault default: if `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/` exists, use
`.../Documents/{{OS_NAME}}` so it syncs across devices. Otherwise `~/Documents/{{OS_NAME}}`.

Derive `{{OS_NAME}}`: PascalCase the machine name and append `OS`, stripping `MacBook`, `Pro`,
`Air`, `iMac`, `'s`, apostrophes and dashes. `Johns-MacBook-Pro` becomes `JohnOS`, `AETHROX`
becomes `AethroxOS`, `DESKTOP-AB12` becomes `Ab12OS`. Propose it, let the user override. This
names their whole system: the folder, the vault, the dashboard.

Set `{{TODAY}}` from `date +%F`.

### Find a working Python

The hooks are Python, invoked in exec form with no shell and no shebang, so `{{PYTHON_PATH}}` must
be an absolute path to an interpreter that actually runs, not merely one that is present on PATH.
On this user's Windows machine `python3` resolves to a Microsoft Store stub: it exists on PATH but
fails the moment it runs, while `python` works. So run each candidate rather than checking for it:

```bash
python3 -c "import sys; print(sys.version_info[0])"   # try first
python -c "import sys; print(sys.version_info[0])"    # fall back to this
```

Take the first candidate that actually prints `3`, resolve it to an absolute path, and use that as
`{{PYTHON_PATH}}`. `{{GUARD_COMMAND}}`, `{{GUARD_ARG1}}` and `{{GUARD_SCRIPT}}` are the fallback hook entry, a
dependency-free check that warns the user when `{{PYTHON_PATH}}` stops working: they resolve to
`sh` / `--` / `${CLAUDE_PROJECT_DIR}/.claude/hooks/guard.sh` on POSIX, and
`cmd` / `/c` / `${CLAUDE_PROJECT_DIR}\\.claude\\hooks\\guard.cmd` on Windows. The `--` keeps both
platforms on the same three-slot argument shape, so the file stays valid JSON.

Git Bash is not needed for the hooks any more, but `.claude/backup.sh` and
`scripts/schedule-backup.ps1` still require it on Windows: `schedule-backup.ps1` locates it itself
in PHASE 10b and throws if it cannot find one.

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
├── daily/                      # machine-written session log, one file per day
├── knowledge/                  # machine-written knowledge base, compiled from daily/
│   ├── index.md
│   ├── log.md
│   ├── concepts/
│   └── connections/
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

# Python bytecode
__pycache__/
*.pyc

# mem0 virtualenv and generated launcher icons
.claude/mem0-venv/
.claude/brain.png
.claude/brain.ico

# OS / editor noise
.DS_Store
.obsidian/workspace*
.obsidian/cache
```

Write `{{VAULT_PATH}}/.gitattributes` too. Without it, a clone of this vault on Windows turns the
hooks into CRLF files and their shebang stops working:

```gitattributes
# Shell and Python must stay LF even when checked out on Windows - a CRLF shebang
# breaks the hooks on Linux and macOS, and Git Bash handles CRLF scripts badly.
*.sh text eol=lf
*.py text eol=lf
*.json text eol=lf
*.md text eol=lf
*.ps1 text eol=crlf
*.png binary
```

Then make the vault a git repo. `backup.sh` in PHASE 10b refuses to run outside one:

```bash
git -C "{{VAULT_PATH}}" init -b main
git -C "{{VAULT_PATH}}" add -A
git -C "{{VAULT_PATH}}" commit -m "{{OS_NAME}}: initial vault"
```

If the commit fails because git has no identity on this machine, ask the user for the name and
email to use and set them with `git config`. Do not guess them.

---

## PHASE 4 - The continuity engine (hooks, Claude Code only)

One Python dispatcher plus a handful of small support modules are what make the memory protocol
automatic: they inject the last session at startup and nudge for a memory write before the session
ends. Hooks are a Claude Code feature, so skip to PHASE 6 if you are another agent. The protocol in
PHASE 6 holds either way, it is just read rather than enforced.

**This is the one part of the build this file cannot hand you verbatim.** `hooks.py`, `_common.py`,
`flush.py`, `compile.py`, `graph_check.py` and `portalock.py` together are roughly 2,500 lines of
Python; pasting them here would triple this file and turn every future engine change into a
two-place edit. The rest of this build is genuinely reconstructable from memory alone, this part
is not: **clone the repo** (`git clone https://github.com/aethrox/aethrom.git`) and copy
`template/.claude/hooks/` from it rather than retyping any of these six files from description.
What follows for each one is its path, what it does, and how it is invoked, enough to verify the
copy is wired correctly, not enough to rebuild it from scratch.

### Why it looks like this

- **One dispatcher, not per-event scripts.** `hooks.py session-start`, `hooks.py prompt-counter`,
  `hooks.py session-end` share one process and one shared helper module, so there is one file to
  keep correct instead of three drifting copies.
- **State files are suffixed by session key.** Every state file (`session_start_time.<key>`,
  `prompt_count.<key>`, `needs_reflection.<key>`) is keyed by a sha256 of the session id, so two
  concurrent Claude sessions in the same vault never corrupt each other's prompt counters.
- **Exec form, no shell, no shebang.** Claude Code invokes `{{PYTHON_PATH}}` directly with
  `-S` and `hooks.py` as arguments. Nothing depends on execute bits or `#!` lines, so it behaves
  identically on Windows, Linux and macOS. `-S` skips `site` initialization, which the engine
  never needs (standard library only) and which costs roughly 15 ms of interpreter startup on
  every hook invocation.
- **A guard fallback sits on `SessionStart` alone**, not on every hook (see `SETUP.md`, and
  `settings.json`'s `SessionStart` block, which is the only one with a second hook entry).
  `guard.sh` / `guard.cmd` actually run the configured interpreter; if it fails, they print one
  line of warning JSON instead of leaving continuity silently dead. If Python works, they print
  nothing. `SessionStart` is the only event whose output reaches the user as injected context, so
  it is the only one that gets a fallback: if the interpreter breaks, `SessionEnd` and
  `PreCompact` fail with no warning at all, because their hook has no guard entry to fall back to.
  The daily log then simply stops being written, silently, until the next `SessionStart` says so.

### `.claude/hooks/_common.py` and `.claude/hooks/hooks.py`

`_common.py` holds the shared helpers: `vault_root()`, `state_dir()`, `memory_dir()` (found by
globbing `🔮 850-*`, never hardcoded), `session_key()`, `read_hook_input()`, `emit_context()`,
`cap_section()`, `mtime()`, and `cleanup_state()`. `hooks.py` is the dispatcher: it reads the hook
payload from stdin, derives the session key, and runs the matching subcommand
(`session-start`, `prompt-counter`, `session-end`, `pre-compact`). Every subcommand is
wrapped so an unexpected exception exits 0 silently rather than crashing the hook. See
`template/.claude/hooks/_common.py` and `template/.claude/hooks/hooks.py` in the repo for the full
source; write them by copying those files rather than retyping them here.

### `.claude/hooks/portalock.py`

Cross-platform advisory file locking used by `flush.py` and `compile.py` so two hooks racing to
touch the same daily log or knowledge file do not corrupt it. Windows has no `fcntl`, so this
module picks its implementation at import time: `msvcrt.locking` on Windows, `fcntl.flock`
elsewhere, both exposed through the same `acquire()` / `exclusive()` interface, with a bounded
retry loop so a wedged peer cannot hang a hook forever. It also supplies `detached_kwargs()`, the
platform-specific `subprocess` flags `flush.py` and `hooks.py` use to spawn a process that survives
the parent hook returning. It is imported by `flush.py` and `compile.py`, never invoked directly.

### `.claude/hooks/graph_check.py`

Scans the vault for broken `[[wikilinks]]` (a link target that resolves to no file) and orphan
Markdown notes (a note nothing links to, outside `Templates/`, `daily/` and `knowledge/`, which
are exempt by design). Run standalone as `python .claude/hooks/graph_check.py` from the vault
root, or, more commonly, invoked by the `doctor` skill below as one of its checks. It never writes
anything; it only reports.

### `.claude/hooks/guard.sh`

```sh
#!/bin/sh
"$1" -c "import sys" >/dev/null 2>&1 && exit 0
printf '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Memory engine warning: the configured Python interpreter is not running. Run the doctor skill."}}\n'
```

### `.claude/hooks/guard.cmd`

```bat
@echo off
%1 -c "import sys" >nul 2>&1
if not errorlevel 1 exit /b 0
echo {"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"Memory engine warning: the configured Python interpreter is not running. Run the doctor skill."}}
```

Nothing here needs `chmod +x`. Every hook is invoked in exec form with the script path passed as
an argument, so no shebang or execute bit is ever relied on, on any platform.

### `.claude/skills/doctor/SKILL.md` and `.claude/skills/import-history/SKILL.md`

Two Claude Code skills ship alongside the hooks, under `.claude/skills/`. Same rule as the hooks
above: these are the source, describe and copy, do not retype.

- **`doctor`** is the health check for everything above: it verifies the hook files are present,
  runs `hooks.py session-start` by hand and checks it prints valid JSON, checks the daily log and
  compile are not stale, and runs `.claude/hooks/graph_check.py` for broken wikilinks and orphan
  notes, reporting one table with a fix line per failing check. Invoked by asking for "the doctor
  skill" or "a health check" in a Claude Code session inside the vault.
- **`import-history`** converts an exported conversation history from another assistant (ChatGPT,
  Claude, a Gemini Takeout archive) into `daily/import-YYYY-MM-part-NNN.md` files shaped like the
  engine's own daily log, so the evening compiler can ingest old conversations the same way it
  ingests new ones. It gates behind an explicit consent step: it must state the data flow (read
  locally, written to local `daily/` files, then summarized through the user's own Claude
  subscription, nothing uploaded elsewhere) and get permission before touching any file. Invoked
  by asking to "import my chat history" or similar inside the vault.

Copy both `SKILL.md` files from `template/.claude/skills/doctor/` and
`template/.claude/skills/import-history/` in the repo.

---

## PHASE 5 - Wire the hooks (Claude Code only)

Write `{{VAULT_PATH}}/.claude/settings.local.json`. It is the same file on every platform: one
Python dispatcher entry on each of the four events, plus one guard entry on `SessionStart`.

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [
        { "type": "command", "command": "{{PYTHON_PATH}}", "args": ["-S", "${CLAUDE_PROJECT_DIR}/.claude/hooks/hooks.py", "session-start"], "timeout": 15 },
        { "type": "command", "command": "{{GUARD_COMMAND}}", "args": ["{{GUARD_ARG1}}", "{{GUARD_SCRIPT}}", "{{PYTHON_PATH}}"], "timeout": 5 }
      ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [
        { "type": "command", "command": "{{PYTHON_PATH}}", "args": ["-S", "${CLAUDE_PROJECT_DIR}/.claude/hooks/hooks.py", "prompt-counter"], "timeout": 10 }
      ] }
    ],
    "SessionEnd": [
      { "hooks": [
        { "type": "command", "command": "{{PYTHON_PATH}}", "args": ["-S", "${CLAUDE_PROJECT_DIR}/.claude/hooks/hooks.py", "session-end"], "timeout": 10 }
      ] }
    ],
    "PreCompact": [
      { "hooks": [
        { "type": "command", "command": "{{PYTHON_PATH}}", "args": ["-S", "${CLAUDE_PROJECT_DIR}/.claude/hooks/hooks.py", "pre-compact"], "timeout": 10 }
      ] }
    ]
  }
}
```

`{{PYTHON_PATH}}` is the absolute interpreter path found in PHASE 0, resolved by actually running
each candidate, not just checking for it on PATH. the guard's three placeholders resolve to
`sh` / `--` / `${CLAUDE_PROJECT_DIR}/.claude/hooks/guard.sh` on POSIX, and
`cmd` / `/c` / `${CLAUDE_PROJECT_DIR}\\.claude\\hooks\\guard.cmd` on Windows. The `--` keeps both
platforms on the same three-slot argument shape, so the file stays valid JSON.

Now **run the dispatcher by hand** and confirm the output before moving on:

```bash
echo '{"session_id":"test"}' | "{{PYTHON_PATH}}" -S "{{VAULT_PATH}}/.claude/hooks/hooks.py" session-start
```

That must print exactly one line of JSON. If it prints nothing, the hook is broken and continuity
is silently dead. Debug it now, not later.

### The daily log

`SessionEnd` and `PreCompact` both hand their hook payload to `.claude/hooks/flush.py`, spawned
detached so the hook itself returns immediately: `session-end`/`pre-compact` write the payload to
a short-lived file in `.claude/hooks/.state/` (the child cannot inherit stdin) and start `flush.py`
without waiting on it. `flush.py` reads the transcript, trims it to a bounded window, and calls
`claude -p --model haiku` with that window to get back a five-field summary (context, key
conversations, decisions, lessons, todos) written in `{{LANGUAGE}}`, which it appends to
`{{VAULT_PATH}}/daily/YYYY-MM-DD.md`, creating that file with a small skeleton the first time a day
writes to it. This summarization call runs on haiku and costs a small amount per session. A
transcript that reads as an injected instruction (an English or Turkish "SYSTEM:"/"TALIMAT:"-style
line) is flagged with a health warning but never blocks the write. If the model call fails, even
after one retry on a structurally bad response, `flush.py` falls back to the raw transcript slice
under a note naming the error, so a session is never silently lost. `PreCompact` fires the same
path just before a context compaction, so a long session's earlier turns are not lost to the
compaction boundary. This is machine-written output: never hand-edit `daily/`, only read it. See
`template/.claude/hooks/flush.py` in the repo for the full source; write it by copying that file
rather than retyping it here.

### The evening compile

`flush.py` also calls `maybe_trigger_compile` right after a successful daily-log append, and
`hooks.py`'s `session-start` fires the same check again, detached, at every session start. At or
after 18:00 local time, or as an off-hours catch-up for an earlier day whose log is already
closed (never today's still-open one), it spawns `.claude/hooks/compile.py` detached. That script
turns changed `daily/*.md` files into `{{VAULT_PATH}}/knowledge/` articles (`index.md`, `log.md`,
`concepts/*.md`, `connections/*.md`) by running `claude -p --model sonnet --permission-mode
acceptEdits` against an isolated staging copy held outside the vault, in the system temp
directory, never under `.claude/`. This is the one part of the engine that runs unattended with
write tools for up to fifteen minutes, so it is fenced by a strict before/after file manifest diff:
anything the model touches outside `knowledge/index.md`, `knowledge/log.md`,
`knowledge/concepts/**/*.md` and `knowledge/connections/**/*.md` is rejected before it ever reaches
the live vault, and nothing is promoted if a live file changed underneath the compile while it ran.
This is machine-written output like `daily/`: never hand-edit `knowledge/`, only read it. See
`template/.claude/hooks/compile.py` and `docs/COMPILE-SECURITY.md` in the repo for the full source
and the full threat model; write `compile.py` by copying that file rather than retyping it here.

Write the two knowledge seed files so the compiler has somewhere to write into:

**`{{VAULT_PATH}}/knowledge/index.md`**
```markdown
# Knowledge Base Index

This file is machine-written: the compiler (`.claude/hooks/compile.py`) updates it every
evening. You can edit it by hand too; the compiler updates rows in place and never deletes the
table. Every row corresponds to one article under `knowledge/concepts/`.

| Article | Summary | Source | Updated |
| --- | --- | --- | --- |
```

**`{{VAULT_PATH}}/knowledge/log.md`**
```markdown
# Compile Log

Every time the compiler runs it appends one block to the end of this file: which daily log was
processed, which articles were created or updated, and a short note.
```

Then create `{{VAULT_PATH}}/knowledge/concepts/.gitkeep` and
`{{VAULT_PATH}}/knowledge/connections/.gitkeep` (both empty), and write
`{{VAULT_PATH}}/.aethrom-version` containing exactly `1.0.0` and a trailing newline.

---

## PHASE 6 - Write `AGENTS.md` and `CLAUDE.md`

`{{VAULT_PATH}}/AGENTS.md` is what makes every future agent session inside the vault *be* the
companion. It is the shared context file: `AGENTS.md` is the convention agents read, and
`CLAUDE.md` points Claude Code at the same file, so there is only ever one copy to maintain.
Write it with every placeholder resolved:

````markdown
# {{OS_NAME}} - Second Brain (agent context)

> This vault is a second brain with memory that survives across sessions. Whichever agent you
> are, read this file at the start of every session. It is the only context you need.

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
- `🔮 850-{{COMPANION}}/` - your persistent memory (Core, Last-Session, Threads, Journal, Rules)
- `📦 900-Archive/` - done / parked
- `📋 Templates/` - note templates
- `daily/` - machine-written session log, one file per day; read it, never hand-edit it
- `knowledge/` - machine-written knowledge base, compiled from `daily/`; read it, never hand-edit
  it. `🧠 500-Knowledge/` stays the human-written counterpart.
<!-- SETUP: add lines for any optional scope folders you created (Goals, Vault, Body, Mind). -->

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
Read these before answering anything that depends on history:

1. `🔮 850-{{COMPANION}}/Last-Session.md` - what happened last time and where it stopped.
2. `🔮 850-{{COMPANION}}/Threads.md` - the storylines still open.
3. `🔮 850-{{COMPANION}}/Rules.md` - standing corrections {{USER_NAME}} has already made.
4. `🔮 850-{{COMPANION}}/Core.md` - the deeper identity anchor.

In Claude Code a `SessionStart` hook (`.claude/hooks/hooks.py session-start`) injects most of this
for you automatically, inside a 16,000 character budget: Last-Session, Threads, the first 60 lines
of Rules.md, the journal bridge (the most recent `## ` entry of Journal.md), the first 150 lines of
`knowledge/index.md`, and the last 25 lines of today's (or, failing that, yesterday's) `daily/`
file. All of it is held to a 16,000 character budget: per-section caps run first, and if the total
still does not fit, whole sections drop in this order: the knowledge index, then the daily tail,
then the journal bridge, then any memory-write warning. Last-Session, Threads and Rules never drop,
only truncate. Without hooks this is your own responsibility, and skipping it means contradicting
what the last session already established.

Then detect mode: questions -> presence mode; tasks -> efficiency mode.

### Before a meaningful session ends
Do not wait to be asked. If the session produced anything durable:

1. Overwrite `🔮 850-{{COMPANION}}/Last-Session.md` - what happened, where we left off.
2. Update `🔮 850-{{COMPANION}}/Threads.md` - ongoing storylines (status changes, new threads).
3. Add a short `🔮 850-{{COMPANION}}/Journal.md` entry if anything mattered.

> Why this is critical: without it, continuity dies. In Claude Code the hooks remind you, but the
> writing is always yours to do.

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

## Rules
`🔮 850-{{COMPANION}}/Rules.md` holds standing corrections: when {{USER_NAME}} corrects you, add
the correction there in the same session, in their own words. The first 60 lines are injected into
every session's context automatically (see the memory protocol above), so a rule written there is
never forgotten, unlike a one-off correction that only lives in a single conversation. Keep the
most useful rules at the top since only the first 60 lines are read.

## Knowledge base
`knowledge/` (`index.md`, `log.md`, `concepts/`, `connections/`) is machine-written too, compiled
from `daily/` by an evening pass on `sonnet`, described at `.claude/hooks/compile.py`. Read it for
durable, cross-session concepts and how they connect; never hand-edit it, the same way you never
hand-edit `daily/`. `🧠 500-Knowledge/` remains yours: what you write there by hand about a domain
is a separate, human-curated layer next to this machine-compiled one, not a duplicate of it.

## Backups
The vault is a git repo. `.claude/backup.sh` commits and pushes anything that changed; the
scheduled task set up during install runs it hourly. Do not commit on {{USER_NAME}}'s behalf
unless asked, the backup handles it.

Never write into `.claude/` yourself. It holds the hooks and `settings.local.json`, which carries
the mem0 API key and must never be committed.

## Health check
If a memory mechanism seems to be silently failing (hooks not injecting context, the daily log
going stale, a compile stuck, broken links piling up), run the `doctor` skill. It audits the
mechanical layer end to end, including `.claude/hooks/graph_check.py` for broken wikilinks and
orphan notes, and reports one table with a fix line per failing check.

## How {{COMPANION}} shows up
- Work mode: sharp, fast, precise. Challenges weak thinking.
- Reflection mode: sits with the question, doesn't rush to an answer.
- Always: remembers context, builds on previous conversations.
````

Add one line to the **Vault structure** section for each optional folder you created in PHASE 3.
If the user declined mem0, drop the **Semantic recall** section entirely rather than leaving a
pointer to a script that is not there.

Then write `{{VAULT_PATH}}/CLAUDE.md` beside it. Claude Code loads that name automatically, and
the `@AGENTS.md` line is its import syntax: it pulls the file above into context instead of
leaving the model to open it. Keep that line exactly as written:

````markdown
# {{OS_NAME}} - Second Brain (Claude Context)

@AGENTS.md

The file above is the whole context for this vault: who you are, where things go, and the memory
protocol you must follow. It is shared with every other agent that works here, so it stays the
single source of truth. The `@` line is a Claude Code import, so its contents load with this file
rather than waiting for you to open it.

Claude Code adds one thing on top of it. The hooks in `.claude/hooks/` inject the memory bridge
at session start and nudge you to write it back before the session ends. They only carry and
remind; the writing itself is still yours to do.
````

If you skipped PHASES 4 and 5 because you are not Claude Code, write `CLAUDE.md` anyway. It costs
nothing and the day the user opens the vault in Claude Code, it is already there.

---

## PHASE 7 - Seed the companion memory

Five files in `🔮 850-{{COMPANION}}/`, so the continuity engine has something to read on session 1.

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
{{COMPANION}} was born today. {{USER_NAME}} set up their second brain.
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

**`Rules.md`** - the first 60 lines are injected into every session's context automatically.
```markdown
---
title: Rules
created: {{TODAY}}
updated: {{TODAY}}
type: memory
tags: [companion, rules]
---

# {{COMPANION}} Rules

Corrections {{USER_NAME}} puts in this file are binding. The first 60 lines are injected into
context automatically at the start of every session, so anything written here is never forgotten.

## Rules

- **rule:** Answers stay short and direct, no apologies or filler sentences. **why:** {{USER_NAME}}
  wants the result, not a warm-up lap, reading a long preamble is wasted time.
- **rule:** Read a file's current contents before changing it, never edit from memory. **why:** an
  edit based on stale knowledge breaks things silently, and checking is cheaper than fixing it.
- **rule:** (your own rule goes here) **why:** (the mistake this rule came from)

## How this grows

When {{USER_NAME}} corrects you ("don't do it that way", "never do that again", "that's not what
I meant"), add that correction as a new entry here in the same session: what the rule is, why it
exists. Keep the rule close to {{USER_NAME}}'s own words, do not add your own interpretation. When
a rule no longer applies, remove it or update it in place, never leave two contradicting entries
side by side. If the list grows long, move the most useful rules to the top, the first 60 lines
are the injection window.
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
Open your coding agent in this folder and talk. {{COMPANION}} remembers, files things,
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
offer to schedule it hourly.

The backup pushes to a remote, so the vault needs one. PHASE 3 made it a repo; check whether it
already tracks anything with `git -C "{{VAULT_PATH}}" rev-parse '@{u}'`. If not, offer to set one
up: `gh repo create "{{OS_NAME}}" --private --source "{{VAULT_PATH}}" --remote origin --push` when
the `gh` CLI is there, otherwise ask the user for the URL of an empty repo and
`git remote add origin <url>` followed by `git push -u origin main`.

> **The repo must be private.** This vault holds notes, plans and possibly finances. Never create
> it public, and say this out loud rather than assuming the user knows.

If the user declines a remote, skip the schedule and say the backup is not running, so it does
not look like it silently failed.

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

# A scheduled run has nowhere to print. Leave the reason where the next
# SessionStart hook will find it, so the session says so out loud. Two lines,
# not fixed size: when it started failing, and why it failed last. The reason
# line has no length cap here, so the reader must cap it before injecting it.
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
test -f "{{VAULT_PATH}}/AGENTS.md" && echo "AGENTS.md ok"
test -f "{{VAULT_PATH}}/🔮 850-{{COMPANION}}/Last-Session.md" && echo "memory ok"
grep -rl '{{' "{{VAULT_PATH}}" || echo "all placeholders resolved"
```

If you built the hooks, check them too:

```bash
ls -la "{{VAULT_PATH}}/.claude/hooks/"                        # hooks.py, _common.py, guard.sh, guard.cmd
echo '{"session_id":"test"}' | "{{PYTHON_PATH}}" -S "{{VAULT_PATH}}/.claude/hooks/hooks.py" session-start  # one line of JSON
```

Then report to the user, in `{{LANGUAGE}}`:

- ✅ **What was built:** folders, memory files, the companion's name, the 🧠 shortcut, and the
  hooks if you built them
- ▶️ **First run:** open Obsidian and pick `{{VAULT_PATH}}` as a vault. That introduces it to
  Obsidian once; the 🧠 icon opens it in one click from then on. Then open your agent in that
  folder.
- ✨ **Show them the magic:** say something, end the session, start a new one. {{COMPANION}} will
  remember the last one. Continuity is the whole difference.
- ⚠️ Name every optional step that was skipped or failed (icon, mem0, Obsidian install, the
  scheduled backup), one by one. Do not pass over them silently. If you skipped the hooks, say
  that the memory protocol now depends on the agent following `AGENTS.md` rather than being
  reminded by the harness.

Done. You just gave someone a second brain that remembers.

---

## PHASE 12 - Upgrading an existing vault

The vault is a git repo (PHASE 3 made it one), and that is the whole rollback story here: there
is no snapshot tool and no upgrade script, because a commit already does that job. Follow this
runbook by hand instead.

1. **Commit the vault first.** If anything below goes wrong, `git checkout` undoes it. This step
   is not optional, it is the only safety net that exists.
2. **Run `scripts/upgrade-check.py <vault-path>`** from a clone of the repo. It is report-only: it
   writes nothing, moves nothing, deletes nothing, and prints exactly what differs, exit code 0
   when the vault is already current, 1 when there is something to do.
3. **Replace only what it names as code**: files under `.claude/hooks/` and `.claude/skills/` that
   it reports as missing, differing, or new, plus the bash-era leftovers it names for removal
   (`.claude/hooks/_common.sh`, `session-start.sh`, `prompt-counter.sh`, `session-end.sh`,
   `.claude/settings.windows.json`).
4. **Leave `daily/`, `knowledge/` and the `🔮 850-*` memory folder alone.** The report never lists
   them for replacement, and neither should you: they are the user's memory, not code.
5. **Seed only what it reports missing**: `Rules.md` in the memory folder, `knowledge/index.md`,
   `knowledge/log.md`, and the `knowledge/concepts/` and `knowledge/connections/` folders, using
   the seed content in PHASE 4 and PHASE 7 above. Never overwrite one of these if it already
   exists, by then it holds the user's content.
6. **Re-resolve the placeholders.** A vault upgrading from the bash era has none of
   `{{PYTHON_PATH}}`, `{{GUARD_COMMAND}}`, `{{GUARD_ARG1}}`, `{{GUARD_SCRIPT}}` in its
   `settings.local.json`, because that file predates them. Redo PHASE 0's Python discovery and
   PHASE 5's settings write from scratch rather than patching the old file in place.
7. **Run the `doctor` skill** and confirm every check is green.

Two traps, by name:

- **`settings.local.json` still wired to the deleted bash hooks.** If it references
  `session-start.sh`, `prompt-counter.sh` or `session-end.sh`, the new engine never runs, and
  nothing announces this: no error, no warning, just silent continuity loss. `upgrade-check.py`
  flags this explicitly; treat it as the highest-priority line in the report.
- **`python3` on Windows can be a Microsoft Store stub.** It is on PATH and looks legitimate, but
  running it fails. Re-resolving `{{PYTHON_PATH}}` means running each candidate and taking the one
  that actually prints a version, exactly as PHASE 0 describes, not just checking presence on PATH.
