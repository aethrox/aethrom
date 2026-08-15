# aethrom

An Obsidian vault that **remembers across sessions**, driven by whichever coding agent you already
use, with a scaffold and a build runbook that work on **Windows, Linux and macOS**.

Most chat assistants forget you every session. This does not. A local Obsidian vault holds
everything you know and do, an agent drives it, and four memory files carry what matters from one
session to the next. You do not manage files, you talk to it.

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

Continuity is four markdown files and a protocol. `Core.md`, `Last-Session.md`, `Threads.md` and
`Journal.md` live in a folder named after your companion, `🔮 850-Aether/` for Aether, and
`AGENTS.md` tells the agent to read them when a session opens and write them back before it ends.
Nothing there is specific to any one agent.

In Claude Code three hooks make that automatic rather than voluntary. `session-start.sh` reads
`Last-Session.md` and `Threads.md` and injects them as context, so the model opens every session
knowing where the last one stopped. `prompt-counter.sh` nudges once at fifteen prompts to write
memory before the session ends. `session-end.sh` notices when a session ended without a memory
write and leaves a marker the next `session-start.sh` surfaces.

The vault files are the source of truth. mem0, if you enable it, is a searchable index on top and
never more than that.

`.claude/backup.sh` commits and pushes whatever changed, refusing to commit the API key file or
anything with an em dash in it, and pulling before it pushes so a push is never rejected. SETUP.md
offers to schedule it hourly: a scheduled task on Windows, a systemd user timer on Linux, a
launchd agent on macOS.

A scheduled backup has nowhere to print, so a broken one is normally invisible until the day you
need it. `backup.sh` writes the reason it stopped into the hook state directory, and
`session-start.sh` reads it out at the top of the next session, along with a warning if the
hourly run has not happened in over a day. It stays quiet on a vault where no backup was ever set
up, and quiet again as soon as one succeeds.

## Layout

```
template/            the vault scaffold, copied to its real home during setup
  AGENTS.md          the companion's whole context: identity, structure, memory protocol
  CLAUDE.md          three lines pointing Claude Code at AGENTS.md
  .claude/hooks/     the continuity engine (session-start, prompt-counter, session-end,
                     plus _common.sh, the portability shims they all source)
  .claude/backup.sh  commit and push the vault, scheduled hourly during setup
  .claude/run-hidden.vbs       Windows only: runs the hourly backup with no console window
  .claude/semantic-memory.py   optional mem0 recall bridge
hermes/skills/       the same memory protocol, as a hermes skill
scripts/             desktop launchers and the backup scheduler, one per platform, both called
                     from SETUP.md, plus the hermes installer (opt-in, run by hand)
SETUP.md             the runbook the agent follows, needs this clone
BRAIN.md             the same build as one self-contained file, needs nothing
```

## Platform support

| | Windows | Linux | macOS |
|---|---|---|---|
| Continuity hooks (Claude Code) | ✅ verified | ✅ verified | ⚠️ untested |
| `backup.sh` | ✅ verified | ✅ verified | ⚠️ untested |
| Backup scheduler | ✅ verified (scheduled task) | ✅ verified (systemd user timer) | ⚠️ untested (launchd agent) |
| Desktop launcher | ✅ verified (.lnk + 🧠 icon) | ⚠️ partially verified (.desktop) | ⚠️ untested (upstream applet) |
| mem0 recall | ✅ verified | ⚠️ untested | ⚠️ untested |

Verified means it was actually executed on that platform, not reasoned about. What that covered:

- **Hooks.** A five-case suite: context injection, reflection marker written, marker injected and
  cleared, no marker when memory was written, and the 15-prompt nudge. Run on Git Bash 5.3 under
  Windows 11 and on Fedora 44 under WSL, with the emitted payload parsed as JSON every time.
- **`backup.sh`.** Run against a throwaway remote on both platforms: the clean run, a normal commit
  and push, a push rejected because the clone was behind, a real add/add rebase conflict that left
  no half-rebase state, the failure marker holding one "since" timestamp across repeated failures,
  the marker clearing on the next success, and the em dash refusal.
- **Schedulers.** Both registered and unregistered for real. On Linux that meant a live
  `systemd --user` timer, checked with `systemctl --user list-timers`, triggered once by hand, then
  torn down with `disable --now` and its unit files removed. The failing and the succeeding backup
  were both fired through the unit itself, with the reason readable in `journalctl --user`.
- **The Linux launcher.** Script logic, `.desktop` syntax and the icon copy were all exercised, but
  only against a fake `$HOME` in a headless WSL session, so it has never reached Obsidian.

### Portability decisions

- **No `awk`.** JSON escaping is pure bash. A minimal Fedora image ships without `awk`, and the
  failure mode was silent: the hook emitted nothing and continuity vanished with no error.
- **`stat -c` with a `-f` fallback.** GNU takes `-c`, BSD and macOS take `-f`.
- **No `python3` dependency** in the hooks. It is not guaranteed on Windows.
- **Windows path conversion.** Claude Code substitutes `$CLAUDE_PROJECT_DIR` as `C:\Users\...`,
  which `dirname` cannot split. `to_posix()` in `_common.sh` converts it to `/c/Users/...`.
- **Windows: the hourly backup goes through `wscript.exe`.** Git Bash is a console program, so
  Task Scheduler pops a black window on the desktop every hour while you are logged in.
  `.claude/run-hidden.vbs` runs it with no window, waits, and returns the exit code, so
  `LastTaskResult` still reports a failed backup. A fire-and-forget call would report success
  forever.

> [!WARNING]
> On Windows the hooks must be invoked with Git Bash. `C:\Windows\System32\bash.exe` is the WSL
> launcher: it cannot see the vault at a Windows path and the hooks will silently do nothing.

## Which agent drives it

The vault ships two context files. `AGENTS.md` is the whole thing: identity, vault structure,
conventions, the memory protocol. `CLAUDE.md` is three lines pointing at it, because Claude Code
loads that name automatically. One source, no copy to keep in sync.

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
- `SETUP.md` and `BRAIN.md` describe the same build and can drift apart. The three hooks embedded
  in `BRAIN.md` are byte-identical to `template/.claude/hooks/` today; `_common.sh`, `backup.sh`,
  `run-hidden.vbs` and `semantic-memory.py` are the same code with their header comments trimmed.
  Nothing checks any of this, so a change to one side has to be made on the other by hand.

## Credits

Fork of [avenoxai/avenoxbeyin](https://github.com/avenoxai/avenoxbeyin), whose original spec lives
at [avenox.lol/beyin.md](https://avenox.lol/beyin.md). The upstream is macOS-only. This fork keeps
the idea and the vault layout and replaces the platform-specific machinery. Original concept,
vault layout and the macOS launcher are Avenox's.

## License

MIT, see [LICENSE](LICENSE).
