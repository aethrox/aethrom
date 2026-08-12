---
name: memory
description: Read and write the second brain's persistent memory so continuity survives across sessions and across agents.
platforms: [linux, macos, windows]
---

# Second brain memory

The vault at `OBSIDIAN_VAULT_PATH` is shared with Claude Code. Both agents read and write the
same memory files, so whatever you record here the other agent sees on its next session, and
whatever it recorded you can see now.

Resolve `OBSIDIAN_VAULT_PATH` first and pass a concrete absolute path to the file tools - they do
not expand shell variables, and the folder names contain emoji and spaces. The memory lives in
`<vault>/🔮 850-Companion/` (in this user's vault the folder is named after the companion, e.g.
`🔮 850-Aether/` - list the vault root once and use the `850-` folder you find).

## At the start of a session

Read, in this order, before answering anything that depends on history:

1. `Core.md` - who the companion is and who it works with.
2. `Last-Session.md` - what happened last time and where it was left off.
3. `Threads.md` - the storylines still open.

Claude Code gets this injected automatically by a hook. **You do not** - hermes has no hook
system, so reading these is your own responsibility. If you skip it you will contradict what the
other agent already established.

## Before a meaningful session ends

Do not wait to be asked. If the session produced anything durable:

1. Overwrite `Last-Session.md` - what happened, what was decided, where it stopped. Keep the
   `## Session: <date> - <title>` heading and move the old block under `## Previous Sessions`.
2. Update `Threads.md` - add new threads, change statuses, move finished ones to `## Closed`.
   Keep the `### Thread:` and `**Status:**` line format; the Claude Code hook greps for exactly
   those two patterns and will not see a thread written any other way.
3. Append to `Journal.md` if something mattered.

## Where things go

| Folder | Contents |
|---|---|
| `📥 000-Inbox/Dump/` | raw capture, processed into its real home later |
| `🎯 100-Command-Center/` | Dashboard, the hub note |
| `⚔️ 200-Goals/` | vision, OKRs |
| `🏰 300-Projects/` | one folder per project |
| `🔐 400-Vault/` | finances, assets, subscriptions - sensitive, never echo into a reply |
| `🧠 500-Knowledge/` | durable knowledge by domain |
| `🛠️ 600-Arsenal/` | tools, contacts, resources |
| `🧘 800-Mind/` | reflections, principles |
| `📦 900-Archive/` | done or parked |

## Conventions

- **No em dash (U+2014), ever.** Not in notes, not in code, not in commit messages, not inside a
  quoted external headline. Use a spaced hyphen, a comma, a colon, or rewrite the sentence. The
  en dash stays, it is meaningful in ranges.
- YAML frontmatter on every note: title, created, modified, type, status, tags.
- Link with `[[wikilinks]]`. Status vocabulary: 🟢 active · 🟡 in progress · 🔴 blocked · ⚪ paused.
- Never write into `.claude/` - that is Claude Code's control plane, and
  `.claude/settings.local.json` holds an API key.
- The vault is a git repo backed up by `.claude/backup.sh`. Do not commit on the user's behalf
  unless asked; the scheduled backup handles it.
