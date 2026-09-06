# aethrom

A second brain for your coding agent: an Obsidian vault that **remembers across sessions**, built
and driven by whichever agent you already use, with a scaffold and a build runbook that work on
**Windows, Linux and macOS**.

Most chat assistants forget you every session. This does not. A local Obsidian vault holds
everything you know and do, an agent drives it, and four memory files carry what matters from one
session to the next. You do not manage files, you talk to it. In Claude Code, hooks make the
memory read and write automatic instead of relying on the model to remember to remember.

## Quick start

Open your coding agent in any folder and paste this. You do not run anything yourself, the agent
clones the repo and builds the vault from there.

```text
Clone https://github.com/aethrox/aethrom.git, work from inside that clone, and follow its
SETUP.md to set up my second brain.
```

It interviews you first: which language your companion should speak, who you are, what to call it,
where the vault should live. Then it scaffolds the vault from `template/` and writes your answers
into every file instead of leaving a placeholder. In Claude Code it also wires the hooks for your
platform and proves one runs. The desktop launcher and the hourly backup are offered at the end.

The interview is the point: `AGENTS.md`, the companion's name and every placeholder come out
written for you, not filled with defaults you edit later. SETUP.md detects the platform itself, so
there is no per-platform installer to maintain.

If the target vault path already exists, the agent shows it to you and asks before touching
anything. `settings.local.json` holds the API key and is gitignored, so it is written from the
template on every run rather than ever travelling with a vault.

## Two ways in

| Path | Needs | Use when |
|---|---|---|
| `SETUP.md` | access to this repo | The normal case |
| `BRAIN.md` | nothing at all | The agent cannot reach this repo |

Both ask, as their first question, which language your companion should speak. Everything in this
repo is English; that answer is what decides how the thing you build talks back to you.

`BRAIN.md` is the whole system as one self-contained file: `AGENTS.md`, the hooks, seed memory,
settings for both platform forms, launchers, per-platform branches, all inline. Hand its contents
to an agent and tell it to apply the file. No clone, no network, no download. That is the copy to
send to someone who does not have access here.

## How it works

Continuity is five markdown files and a protocol. `Core.md`, `Last-Session.md`, `Threads.md`,
`Rules.md` and `Journal.md` live in a folder named after your companion, `🔮 850-Aether/` for
Aether, and `AGENTS.md` tells the agent to read them when a session opens and write them back
before it ends. Nothing there is specific to any one agent. The hook injects four of them;
`Core.md` is the one the agent opens itself, because it is identity rather than state.

In Claude Code a single Python dispatcher, `hooks.py`, makes that automatic rather than voluntary.
Claude Code invokes it directly (`{{PYTHON_PATH}} -S hooks.py <subcommand>`, no shell, no shebang) on
four events. On `SessionStart` it reads `Last-Session.md`, `Threads.md`, the first 60 lines of
`Rules.md`, the journal bridge, the knowledge index and the daily log tail, and injects all of it
as context inside a fixed character budget, so the model opens every session knowing where the
last one stopped. On `UserPromptSubmit` it nudges once every fifteen prompts to write memory
before the session ends. On `SessionEnd` and `PreCompact` it hands the session transcript to
`flush.py`, which summarizes it with a model call and appends the result to the day's file in
`daily/`; if a session ended without a memory write, it leaves a marker the next `SessionStart`
surfaces. A dependency-free guard (`guard.sh` / `guard.cmd`) sits on `SessionStart` alone and warns
instead of leaving continuity silently dead if the configured Python stops running.

Once an evening, `compile.py` reads whatever changed in `daily/` and folds it into `knowledge/`, a
compiled, cross-session concept base, through the same model subscription, isolated in a temp
stage and checked against an allow-list before anything is promoted back into the vault (see
`docs/COMPILE-SECURITY.md`).

The vault files are the source of truth. mem0, if you enable it, is a searchable index on top and
never more than that.

`.claude/backup.sh` commits and pushes whatever changed, refusing to commit the API key file or
anything with an em dash in it, and pulling before it pushes so a push is never rejected. SETUP.md
offers to schedule it hourly: a scheduled task on Windows, a systemd user timer on Linux, a
launchd agent on macOS.

A scheduled backup has nowhere to print, so a broken one is normally invisible until the day you
need it. `backup.sh` writes the reason it stopped into the hook state directory, and the
`SessionStart` hook reads it out at the top of the next session, along with a warning if the
hourly run has not happened in over a day. It stays quiet on a vault where no backup was ever set
up, and quiet again as soon as one succeeds.

## Layout

```
template/            the vault scaffold, copied to its real home during setup
  AGENTS.md          the companion's whole context: identity, structure, memory protocol
  CLAUDE.md          imports AGENTS.md, so Claude Code loads it automatically
  .aethrom-version   the installed template's version stamp, read by upgrade-check.py
  .claude/hooks/     the continuity engine, Python, standard library only:
                     hooks.py (the SessionStart/UserPromptSubmit/SessionEnd/PreCompact dispatcher),
                     _common.py (shared helpers), flush.py (transcript to daily/), compile.py
                     (daily/ to knowledge/, the guarded evening pass), graph_check.py (broken
                     links and orphan notes), portalock.py (cross-platform file locking), and
                     guard.sh / guard.cmd (the dependency-free SessionStart fallback)
  .claude/skills/    doctor (health check) and import-history (ChatGPT/Claude/Gemini import)
  .claude/backup.sh  commit and push the vault, scheduled hourly during setup
  .claude/run-hidden.vbs       Windows only: runs the hourly backup with no console window
  .claude/semantic-memory.py   optional mem0 recall bridge
hermes/skills/       the same memory protocol, as a hermes skill
scripts/             desktop launchers, the backup scheduler and upgrade-check.py, called from
                     SETUP.md, plus the hermes installer (opt-in, run by hand)
tests/               the engine's test suite (`python -m unittest discover -s tests`), run on
                     Windows, Linux and macOS in CI
docs/COMPILE-SECURITY.md     the threat model and defenses around the unattended evening compile
SETUP.md             the runbook the agent follows, needs this clone
BRAIN.md             the same build as one self-contained file, needs nothing
```

## Platform support

| | Windows | Linux | macOS |
|---|---|---|---|
| Continuity engine (Claude Code) | ✅ verified | ✅ verified | ⚠️ CI only, never run by hand |
| `backup.sh` | ✅ verified | ✅ verified | ⚠️ untested |
| Backup scheduler | ✅ verified (scheduled task) | ✅ verified (systemd user timer) | ⚠️ untested (launchd agent) |
| Desktop launcher | ✅ verified (.lnk + 🧠 icon) | ⚠️ partially verified (.desktop) | ⚠️ untested (upstream applet) |
| mem0 recall | ✅ verified | ⚠️ untested | ⚠️ untested |

Verified means it was actually executed on that platform, not reasoned about. What that covered:

- **The continuity engine.** `python -m unittest discover -s tests` is a 119-case suite covering
  the hook dispatcher, the transcript-to-daily-log flush, the guarded evening compile, and the
  knowledge graph checker. It runs in CI on Windows, Linux and macOS on every push
  (`.github/workflows/ci.yml`), and was also run by hand on Windows 11 (three cases that need
  symlink privilege skip there) and on Fedora 44 under WSL, with the hooks' emitted context parsed
  as JSON every time.
- **`backup.sh`.** Run against a throwaway remote on both Windows and Linux: the clean run, a
  normal commit and push, a push rejected because the clone was behind, a real add/add rebase
  conflict that left no half-rebase state, the failure marker holding one "since" timestamp across
  repeated failures, the marker clearing on the next success, and the em dash refusal.
- **Schedulers.** Both registered and unregistered for real. On Linux that meant a live
  `systemd --user` timer, checked with `systemctl --user list-timers`, triggered once by hand, then
  torn down with `disable --now` and its unit files removed. The failing and the succeeding backup
  were both fired through the unit itself, with the reason readable in `journalctl --user`.
- **The Linux launcher.** Script logic, `.desktop` syntax and the icon copy were all exercised, but
  only against a fake `$HOME` in a headless WSL session, so it has never reached Obsidian.

### Portability decisions

- **Python, standard library only.** The engine (`hooks.py`, `flush.py`, `compile.py`,
  `graph_check.py`, `portalock.py`) is Python 3.7+ with no third-party dependency, works on
  Python 3.7 through current, and is invoked directly (`{{PYTHON_PATH}}` with `-S` and the
  script path as arguments, no shell, no shebang), so the same file runs identically on Windows,
  Linux and macOS. This is a hard dependency now: a vault with no working Python interpreter gets
  no automatic memory at all, only the `guard.sh` / `guard.cmd` warning on `SessionStart`. Having
  no third-party dependency is also what makes `-S` safe, and `-S` is worth roughly 15 ms of
  interpreter startup on every hook invocation.
- **Finding a Python that actually runs.** Presence on PATH is not enough: on Windows, `python3`
  can resolve to a Microsoft Store stub that exists on PATH and fails the moment it runs, while
  `python` works. SETUP.md runs each candidate rather than checking for it, and the `doctor` skill
  resolves the same way at audit time.
- **State files are suffixed by a session key.** A sha256 of the session id, so two concurrent
  Claude sessions in the same vault never corrupt each other's counters.
- **Windows: the hourly backup goes through `wscript.exe`.** `backup.sh` and the backup scheduler
  still need Git Bash on Windows even though the hooks no longer do; that dependency was removed
  from the continuity engine, not from the repository. Git Bash is a console program, so Task
  Scheduler would otherwise flash a black window on the desktop every hour while you are logged
  in. `.claude/run-hidden.vbs` runs it with no window, waits, and returns the exit code, so
  `LastTaskResult` still reports a failed backup. A fire-and-forget call would report success
  forever.

## Which agent drives it

The vault ships two context files. `AGENTS.md` is the whole thing: identity, vault structure,
conventions, the memory protocol. `CLAUDE.md` is a short wrapper that imports it with an
`@AGENTS.md` line, since Claude Code loads that filename automatically and follows the import.
One source, no copy to keep in sync.

The import matters more than it looks. Tested here with a real `claude -p` run in a filled vault:
with `CLAUDE.md` merely telling the model to go read `AGENTS.md`, it answered without having read
it and could not say who it was. With the `@AGENTS.md` import, the same question came back in the
companion's voice on the first try.

Any agent that reads `AGENTS.md` picks up the protocol. That was verified here with Codex, which
applied an `AGENTS.md` rule without being told the file existed. Cursor, Gemini CLI and Copilot
read the same filename by convention, but none of them were tested.

What actually differs is enforcement. Claude Code has hooks, so the memory read and the write
reminder come from the harness whether the model cooperates or not. Everywhere else the protocol
is only as reliable as the agent choosing to follow what `AGENTS.md` says.

### Sharing the brain with hermes

If you also run [hermes](https://github.com/NousResearch), it can share the same vault and the
same memory files, so a thread one agent opens the other sees.

```bash
./scripts/install-hermes.sh ~/Documents/MyOS            # Linux and macOS
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-hermes.ps1 -VaultPath C:\Users\me\Documents\MyOS
```

The installer registers `hermes/skills/` in `skills.external_dirs`, so `git pull` updates the
skill and there is no copy to keep in sync, and sets `OBSIDIAN_VAULT_PATH`. It is idempotent and
backs up `config.yaml` first, in hermes' own `config.yaml.bak.<timestamp>` style.

> [!IMPORTANT]
> Hermes does not read `AGENTS.md`, it loads the skill instead. That means the same protocol is
> written down twice, in `AGENTS.md` and in `hermes/skills/aethrom/memory/SKILL.md`, and a change
> to one has to be made in the other by hand.

## House rule: no em dash

No em dash (U+2014) anywhere in this repo or in a vault built from it: not in notes, not in code,
not in commit messages, not inside a quoted external headline. Use a spaced hyphen, a comma, a
colon, or rewrite. The en dash stays, it is meaningful in ranges. The vault's `.claude/backup.sh`
refuses to commit a file containing one.

## Limitations

- **macOS is untested.** The BSD `stat` fallback, the `osacompile` applet with its Swift icon, and
  the launchd branch of `schedule-backup.sh` are all carried over from upstream and reasoned about,
  never executed; there is no macOS machine here. Treat that column as best-effort.
- **A systemd user timer stops when you log out** unless you enable linger, which
  `schedule-backup.sh` prints as an option but deliberately does not do for you.
- **Outside Claude Code the memory protocol is not enforced, only written down.** Hooks are what
  make it automatic, and no other agent has them. `AGENTS.md` was confirmed to reach Codex on this
  machine; Cursor, Gemini CLI and Copilot were not tested at all.
- **Setting up a second machine against a vault you already have is not covered.** `SETUP.md`
  builds a new vault from `template/`; it does not clone an existing one. By hand that means
  cloning the vault, making the hooks executable, and writing `settings.local.json` from the
  template.
- The `obsidian://` handler only resolves after the vault has been opened in Obsidian once, so the
  desktop launcher does nothing until then.
- mem0 relevance scores are weak until enough memories accumulate. It is a recall index, not the
  source of truth. The files in the companion's memory folder are.
- `uv tool install mem0ai` fails: it is a library with no executables. Use a venv.
- **Python is now a hard dependency.** There is no bash fallback: a vault whose configured
  interpreter stops working gets no automatic memory at all until someone fixes it.
- **macOS was never run by hand for the continuity engine.** CI runs the full test suite on
  `macos-latest` on every push, and it passes there, but nobody has driven a real Claude Code
  session against a real macOS vault. Treat the macOS column above as CI-verified, not hand-verified.
- `SETUP.md` and `BRAIN.md` describe the same build and can drift apart, and nothing checks that
  they stay in sync. `BRAIN.md` tells the installer to copy `hooks.py`, `_common.py`, `flush.py`,
  `compile.py`, `graph_check.py` and `portalock.py` straight from this repo rather than inlining
  them, so those cannot drift from the source, but it still inlines `backup.sh`, `run-hidden.vbs`
  and `semantic-memory.py` as heredoc text with their header comments trimmed, and those copies can
  go stale against the real files.

## Credits

Fork of [avenoxai/avenoxbeyin](https://github.com/avenoxai/avenoxbeyin), whose original spec lives
at [avenox.lol/beyin.md](https://avenox.lol/beyin.md). The upstream is macOS-only. This fork keeps
the idea and the vault layout and replaces the platform-specific machinery. Original concept,
vault layout and the macOS launcher are Avenox's.

## License

MIT, see [LICENSE](LICENSE).
