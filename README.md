# aethrom

An Obsidian vault driven by Claude Code that **remembers across sessions**, with a scaffold and
a build runbook that work on **Windows, Linux and macOS**.

Fork of [avenoxai/avenoxbeyin](https://github.com/avenoxai/avenoxbeyin) (MIT), whose original
spec lives at [avenox.lol/beyin.md](https://avenox.lol/beyin.md). The upstream is macOS-only;
this fork keeps the idea and the vault layout, and replaces the platform-specific machinery.

## What it is

Most chat assistants forget you every session. This does not. A local Obsidian vault holds
everything you know and do; Claude Code drives it; three hooks carry memory from one session to
the next. You do not manage files - you talk to it.

## How to use it

Clone it and run the wizard. It asks where the vault should live, pulls your existing vault repo
if you have one, scaffolds a fresh vault from `template/` if you do not, wires the hooks for your
platform, proves the hook actually runs, and offers the desktop launcher.

```bash
git clone <this-repo> && cd aethrom
./scripts/install.sh                 # Linux and macOS
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install.ps1
```

Non-interactive, for scripting or a second machine:

```bash
./scripts/install.sh --repo https://github.com/you/your-vault.git --path ~/Documents/MyOS --name MyOS
```

It is safe to re-run: an existing vault is detected and only the wiring is rechecked, and nothing
already in the target directory is overwritten. A vault pulled from git will not carry
`settings.local.json`, since that file holds the API key and is gitignored, so the wizard
regenerates it from the template.

For the interview-driven path where Claude does the whole build and personalises the prose, open
Claude Code in the clone and tell it to follow `SETUP.md` instead.

## Layout

```
template/            the vault scaffold, copied to its real home during setup
  .claude/hooks/     the continuity engine (session-start, prompt-counter, session-end)
  .claude/semantic-memory.py   optional mem0 recall bridge
hermes/skills/       the same memory protocol, as a hermes skill
scripts/install.*    the setup wizard, one per platform
scripts/             desktop launchers and the hermes installer
SETUP.md             the runbook Claude follows
```

## House rule: no em dash

No em dash (U+2014) anywhere in this repo or in a vault built from it: not in notes, not in code,
not in commit messages, not inside a quoted external headline. Use a spaced hyphen, a comma, a
colon, or rewrite. The en dash stays, it is meaningful in ranges. The vault's `.claude/backup.sh`
refuses to commit a file containing one.

## Sharing the brain with hermes

If you also run [hermes](https://github.com/NousResearch), it can share the same vault and the
same memory files, so a thread one agent opens the other sees.

```bash
./scripts/install-hermes.sh ~/Documents/MyOS            # Linux/macOS
```
```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-hermes.ps1 -VaultPath C:\Users\me\Documents\MyOS
```

The installer registers `hermes/skills/` in `skills.external_dirs` (so `git pull` updates the
skill, with no copy to keep in sync) and sets `OBSIDIAN_VAULT_PATH`. It is idempotent and backs
up `config.yaml` first, in hermes' own `config.yaml.bak.<timestamp>` style.

**Continuity is not equal on both sides.** Claude Code has hooks, so its memory reads and reminders
are enforced by the harness. Hermes has no hook system - `hooks/` is empty - so on that side the
protocol is only as reliable as the skill the model chooses to follow.

## Platform support

| | Windows | Linux | macOS |
|---|---|---|---|
| Continuity hooks | ✅ verified | ✅ verified | ⚠️ untested |
| Desktop launcher | ✅ verified (.lnk + 🧠 icon) | ⚠️ untested (.desktop) | ⚠️ untested (upstream applet) |
| mem0 recall | ✅ verified | ⚠️ untested | ⚠️ untested |

Verified means it was actually executed on that platform: the hooks were run through a five-case
suite (context injection, reflection marker written, marker injected and cleared, no marker when
memory was written, the 15-prompt nudge) on Git Bash 5.3 under Windows 11 and on Fedora 44 under
WSL, and the emitted payload was parsed as JSON.

### Portability decisions

- **No `awk`.** JSON escaping is pure bash. A minimal Fedora image ships without `awk`, and the
  failure mode was silent: the hook emitted nothing and continuity vanished with no error.
- **`stat -c` with a `-f` fallback.** GNU takes `-c`, BSD/macOS takes `-f`.
- **No `python3` dependency** in the hooks. It is not guaranteed on Windows.
- **Windows path conversion.** Claude Code substitutes `$CLAUDE_PROJECT_DIR` as `C:\Users\...`,
  which `dirname` cannot split; `to_posix()` in `_common.sh` converts it to `/c/Users/...`.
- **Git Bash, not WSL.** On Windows the hooks must be invoked with Git Bash. `C:\Windows\System32\bash.exe`
  is the WSL launcher and cannot see the vault at a Windows path.

## Limitations

- **macOS is untested.** The BSD `stat` fallback and the `osacompile`/Swift launcher are carried
  over from upstream and reasoned about, not executed. Treat that column as best-effort.
- **The Linux launcher is untested.** It was written against the freedesktop spec but never run
  on a desktop session; the WSL image used for hook testing is headless.
- The `obsidian://` handler only resolves after the vault has been opened in Obsidian once, so
  the desktop launcher does nothing until then.
- mem0 relevance scores are weak until enough memories accumulate. It is a recall index, not the
  source of truth - the files in `🔮 850-Companion/` are.
- `uv tool install mem0ai` fails: it is a library with no executables. Use a venv.

## Credits

Original concept, vault layout and the macOS launcher: Avenox - MIT licensed, see `LICENSE`.
