---
name: doctor
description: Health check for the memory engine. Hooks, state files, memory files, daily logs, compile status and vault hygiene reported in one table. Use on "doctor", "health check", "is the memory working", "is memory broken", or whenever a memory mechanism is suspected of silently failing.
---

# Doctor

This skill audits the mechanical layer of the memory engine: are the hooks firing, have the
scripts actually run, are the logs staying fresh, is the vault clean. The goal is to make a
silent failure visible.

## How to run

1. Work from the vault root (the folder containing CLAUDE.md/AGENTS.md). All paths below are
   relative, never write an absolute path.
2. Run the checks below **with Bash, in order**. Use the commands as given, do not guess at them.
3. Classify each check's output as green / yellow / red.
4. Report the result as one table, with one fix line per red row.
5. Close with a single-sentence verdict.

Checks are read-only. Never fix anything on your own, report first, then fix only if the user
asks.

## Resolving Python

Several checks below need a working Python interpreter, and this skill exists partly to detect
the case where `python3` on PATH does not work: on Windows, `python3` is a Microsoft Store stub
that resolves on PATH and then fails when actually run. A check that shells out to a bare
`python3` cannot run on the very machine where that failure happens. Every check below that needs
Python resolves one first, with this line, in this order: the interpreter recorded in
`.claude/settings.local.json`'s `SessionStart` hook (the same value check 4 tests), then `python3`,
then `python`, taking the first one that actually runs:

```bash
PY=$(grep -o '"command":[[:space:]]*"[^"]*"' .claude/settings.local.json 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
for candidate in "$PY" python3 python; do
  [ -n "$candidate" ] && "$candidate" -c "1" >/dev/null 2>&1 && { PY="$candidate"; break; }
done
```

This uses only `grep` and `sed`, never Python, to find the configured path, so it works even when
every Python on the machine is broken. Each check below that needs Python repeats this line first
(the Bash tool does not keep shell variables between separate commands), then uses `"$PY"` instead
of a bare `python3`.

## Checks

### 1. Hook files present

```bash
for f in hooks.py _common.py flush.py compile.py graph_check.py portalock.py; do
  if [ -f ".claude/hooks/$f" ]; then echo "$f: ok"; else echo "$f: MISSING"; fi
done
```

Green: all six present. Red: any missing.
Fix: copy the missing file back from the repo.

### 2. Hooks wired into settings.json

```bash
for h in session-start prompt-counter session-end pre-compact; do
  if grep -q "\"$h\"" .claude/settings.local.json 2>/dev/null || grep -q "\"$h\"" .claude/settings.json 2>/dev/null; then
    echo "$h: wired"
  else
    echo "$h: NOT WIRED"
  fi
done
```

Green: all four wired. Red: any missing, that hook never fires at all.
Fix: add the missing subcommand entry to the `hooks` block in `.claude/settings.local.json`
(SessionStart, UserPromptSubmit, SessionEnd, PreCompact), then restart Claude Code.

### 3. Both settings.json and settings.local.json active at once

```bash
PY=$(grep -o '"command":[[:space:]]*"[^"]*"' .claude/settings.local.json 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
for candidate in "$PY" python3 python; do
  [ -n "$candidate" ] && "$candidate" -c "1" >/dev/null 2>&1 && { PY="$candidate"; break; }
done
"$PY" - <<'PYCHK'
import json
EVENTS = ("SessionStart", "UserPromptSubmit", "SessionEnd", "PreCompact")
counts = {e: 0 for e in EVENTS}
for f in (".claude/settings.json", ".claude/settings.local.json"):
    try:
        data = json.load(open(f, encoding="utf-8"))
    except FileNotFoundError:
        continue
    except ValueError:
        print("%s: INVALID JSON" % f)
        raise SystemExit(0)
    if not isinstance(data, dict):
        print("%s: not a JSON object" % f)
        continue
    for event, matchers in (data.get("hooks") or {}).items():
        if event not in EVENTS:
            continue
        for matcher in matchers or []:
            for hook in matcher.get("hooks") or []:
                if "hooks.py" in " ".join(hook.get("args") or []):
                    counts[event] += 1
for event in EVENTS:
    print("%s: %d" % (event, counts[event]))
PYCHK
```

Green: all four events count exactly `1`. Red: any count of `2` or more, that event's hook fires
twice, so every prompt is counted twice and every session end triggers two flushes. `0` means the
event is not wired at all (see check 2).

`SETUP.md` tells the installer to rename `settings.json` to `settings.local.json`; renaming is one
slip away from copying, and copying is exactly what produces this failure.

Fix: delete the memory hook entries from whichever of the two files should not carry them
(`settings.local.json` is the one meant to be live after install), leave unrelated hooks and keys
such as `env` and `permissions` alone. Only one of the two files should carry the memory hooks.

### 4. The configured Python actually runs

This is the check most likely to run on the very machine where the failure happens, so it must
not itself shell out to a bare `python3`: it tests the configured interpreter directly with shell
tools only.

```bash
INTERPRETER=$(grep -o '"command":[[:space:]]*"[^"]*"' .claude/settings.local.json 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
if [ -z "$INTERPRETER" ]; then
  echo "python check: no SessionStart dispatcher entry found in settings.local.json"
elif "$INTERPRETER" -c "import sys; print(sys.version)" 2>/tmp/aethrom-py-check.err; then
  echo "python check: ok, configured interpreter $INTERPRETER runs"
else
  echo "python check: FAILED, could not run $INTERPRETER ($(cat /tmp/aethrom-py-check.err 2>/dev/null))"
fi
```

Green: `ok`. Red: `FAILED`, the interpreter configured in `settings.local.json` does not run on
this machine, so every hook silently produces nothing.
Fix: find a working interpreter (`command -v python3`, `command -v python`, or a venv path),
update `{{PYTHON_PATH}}` in `.claude/settings.local.json` to that path.

### 5. The engine scripts import cleanly

```bash
PY=$(grep -o '"command":[[:space:]]*"[^"]*"' .claude/settings.local.json 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
for candidate in "$PY" python3 python; do
  [ -n "$candidate" ] && "$candidate" -c "1" >/dev/null 2>&1 && { PY="$candidate"; break; }
done
for f in hooks.py _common.py flush.py compile.py graph_check.py portalock.py; do
  "$PY" -c "import py_compile; py_compile.compile('.claude/hooks/$f', doraise=True)" 2>&1 \
    && echo "$f: ok" || echo "$f: SYNTAX ERROR"
done
```

Green: all six `ok`. Red: any syntax error, that script cannot run at all.
Fix: read the traceback, fix the file, or restore it from the repo.

### 6. No unresolved placeholders

```bash
grep -rlE '\{\{[A-Z_]+\}\}' --include='*.md' --include='*.json' . 2>/dev/null | grep -v '/\.git/' | head -20
```

Green: empty output. Red: any file listed, install substitution missed a placeholder.
Fix: re-run the install step that fills in placeholders, or replace the value by hand.

### 7. Daily log freshness

```bash
f=$(ls -t daily/*.md 2>/dev/null | head -1)
if [ -z "$f" ]; then
  echo "daily: no log yet"
else
  m=$(stat -f %m "$f" 2>/dev/null || stat -c %Y "$f")
  n=$(date +%s)
  echo "daily: $f, written $(( (n - m) / 3600 )) hours ago"
fi
```

Green: newer than 48 hours. Yellow: 48 to 96 hours. Red: older than 96 hours, or no log at all.
Fix: end a session and start a new one, then repeat this check. Still empty means the flush
chain is broken, go back to checks 1, 2 and 4.

### 8. Compile status

```bash
PY=$(grep -o '"command":[[:space:]]*"[^"]*"' .claude/settings.local.json 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
for candidate in "$PY" python3 python; do
  [ -n "$candidate" ] && "$candidate" -c "1" >/dev/null 2>&1 && { PY="$candidate"; break; }
done
f=".claude/hooks/.state/compile-state.json"
if [ -f "$f" ]; then
  "$PY" -c "
import json
d = json.load(open('$f', encoding='utf-8'))
print('last_run:', d.get('last_run', 'none'))
print('last_status:', d.get('last_status', 'none'))
ingested = set(d.get('ingested', {}).keys())
import glob, os
daily_files = {os.path.basename(p) for p in glob.glob('daily/*.md')}
print('uningested daily files:', len(daily_files - ingested))
quarantined = [n for n, e in (d.get('failures') or {}).items() if e.get('quarantined')]
if quarantined:
    print('QUARANTINED, these days will never compile until someone looks:')
    for name in sorted(quarantined):
        entry = d['failures'][name]
        print('  ', name, '->', entry.get('reason'), entry.get('detail', ''))
else:
    print('quarantined daily files: none')
" 2>&1 || echo "compile: state file is corrupt, could not parse JSON"
else
  echo "compile: no state file yet, the compiler has never run"
fi
```

Green: `last_status` is `ok` and `last_run` is within 48 hours. Yellow: no state file yet, on a
new vault or before the first evening pass. Red: `last_status` starts with `fail:`, or `last_run`
is older than 48 hours.
Fix: run one pass by hand with `"$PY"` resolved as above and read the error:
`"$PY" .claude/hooks/compile.py --dry-run`, then `"$PY" .claude/hooks/compile.py`.

### 9. Both health channels

```bash
if [ -f .claude/hooks/.state/backup_failed ]; then echo "backup: FAILED, $(cat .claude/hooks/.state/backup_failed)"; elif [ -f .claude/hooks/.state/backup_ok ]; then echo "backup: ok"; else echo "backup: no signal yet"; fi
if [ -f .claude/hooks/.state/health.json ]; then tail -c 1000 .claude/hooks/.state/health.json; else echo "engine health: no record"; fi
```

There are two independent health signals and a check that reads only one misses half the
failures: `backup_ok` / `backup_failed`, written by `backup.sh`, and `health.json`, written by
the flush/compile engine.

Green: backup channel is `ok` or has no signal yet on a fresh vault, and `health.json` has no
record or its last entry is older than 7 days. Red: `backup_failed` exists, or `health.json` has
an entry from the last 48 hours.
Fix: for a backup failure, check that the scheduled task or cron job still exists and that git
has push access. For an engine failure, read the `component` field: `flush` points at the
transcript or the model CLI, `compile` points at the model call itself. The file can be deleted
after reading, the script recreates it.

### 10. Knowledge index size

```bash
if [ -f knowledge/index.md ]; then echo "index: $(wc -l < knowledge/index.md | tr -d ' ') lines"; else echo "index: MISSING"; fi
```

Only the first 150 lines of the index are injected at session start.
Green: 150 lines or fewer. Yellow: 151 to 300 lines, the tail rows stop being injected.
Red: over 300 lines, time to summarize the index.
Fix: group the index by topic, collapse old rows into a single summary line, keep detail in the
article itself. If the file is missing entirely, restore the seed file from the repo.

### 11. iCloud conflict files

```bash
find . -name "* 2.*" -not -path "./.git/*" 2>/dev/null | head -20
```

Green: empty. Red: any result, iCloud kept two copies of the same file, part of the memory may
be in the wrong copy.
Fix: diff each listed file against its original (`diff "file.md" "file 2.md"`), move any real
content into the original, then delete the conflict copy. Never delete without asking the user.

### 12. Git repo and uncommitted changes

```bash
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "git: repo present, uncommitted: $(git status --porcelain | wc -l | tr -d ' ') files"
else
  echo "git: NO REPO"
fi
```

Green: repo present and fewer than 50 uncommitted files. Yellow: 50 or more piled up. Red: no
repo, meaning memory has no recoverable history.
Fix: `git init` and an initial commit if there is no repo. Commit if changes have piled up.

### 13. Rules file present

```bash
r=$(ls "🔮 850-"*/Rules.md 2>/dev/null | head -1)
if [ -n "$r" ]; then echo "rules: present, $(wc -l < "$r" | tr -d ' ') lines"; else echo "rules: MISSING"; fi
```

The folder is globbed, never named. Install renames it to the companion's name, so
a check written against `🔮 850-Companion/` reports MISSING on every real vault.

Green: present. Yellow: missing, the user's corrections are not becoming durable.
Fix: copy the seed `Rules.md` from the repo into the companion memory folder.

### 14. Leftover backup artifacts that may carry secrets

```bash
find . -path ./.git -prune -o -type f \( -name "*.bak" -o -name "*.bak-*" -o -name "settings.local.json.*" -o -name "*.orig" \) -print 2>/dev/null | head -10
echo "---"
git ls-files 2>/dev/null | grep -E 'settings\.local\.json|\.bak$|\.env$' || echo "no tracked secret-bearing files"
```

Green: both sections empty. Red: a backup file shows up, it may be a copy of
`settings.local.json` carrying an API key; anything in the second section means git is already
tracking it.
Fix: move the backup outside the vault and restrict its permissions; if git tracks it, remove it
with `git rm --cached <file>`, confirm the `.gitignore` rule, and rotate any key that leaked.

### 15. Graph integrity (broken links and orphan notes)

```bash
PY=$(grep -o '"command":[[:space:]]*"[^"]*"' .claude/settings.local.json 2>/dev/null | head -1 | sed -E 's/.*"([^"]+)"$/\1/')
for candidate in "$PY" python3 python; do
  [ -n "$candidate" ] && "$candidate" -c "1" >/dev/null 2>&1 && { PY="$candidate"; break; }
done
"$PY" .claude/hooks/graph_check.py
```

Memory is not a flat pile of files, it is a **graph**: a note is found only if something links to
it. An orphan note sits on disk but the agent has to scan the whole vault to find it, so it either
burns tokens or never finds it and invents an answer instead. A broken link points at an address
that does not exist on the map. No other check catches either one.

Green: 0 broken links. Yellow: 1 to 20 broken links. Red: over 20 broken links.
An orphan count alone is not automatically red: drafts, archive material and one-off notes are
naturally orphaned. The files injected into every session are already exempted in the scanner;
the rest is an advisory signal for discoverability.
Fix: run with `--full` to see the complete list. For a broken link either create the target note
or fix the link; if the target is deliberately absent (a `[[wikilink]]` used as an example in
documentation), leave it alone. For an orphan note, link it from its relevant hub note or from
`Dashboard.md`.

## Report format

Once every check has run, print one table:

```
| Check | Status | Finding |
| --- | --- | --- |
| Hook files | green | all six present |
| settings.json wiring | green | all four events wired |
| Double-active hooks | green | each event counted once |
| Python interpreter | green | 3.11.6 |
| Script imports | green | all six ok |
| Placeholders | green | none unresolved |
| Daily log freshness | yellow | last log 51 hours ago |
| Compile status | red | last_status fail:timeout |
| Health channels | red | compile error yesterday |
| Knowledge index | green | 42 lines |
| iCloud conflicts | green | clean |
| Git | green | repo present, 3 files uncommitted |
| Rules file | green | present, 24 lines |
| Backup artifacts | green | clean |
| Graph integrity | yellow | 4 broken links, 12 orphan notes |
```

After the table, write one "Fix:" line with the command for each red row only. Close with a
single-sentence verdict, for example "The engine is up but the compiler has been stuck for two
days, fix that first." When everything is green, keep the verdict short too: "Memory is healthy,
nothing to do."
