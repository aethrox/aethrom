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
`<vault>/🔮 850-<Companion>/`, named after the companion itself, e.g. `🔮 850-Aether/` - list the
vault root once and use the `850-` folder you find.

## At the start of a session

Read, in this order, before answering anything that depends on history:

1. `Core.md` - who the companion is and who it works with.
2. `Last-Session.md` - what happened last time and where it was left off.
3. `Threads.md` - the storylines still open.
4. `Rules.md` - standing corrections the user has already made. Its rules are binding on you the
   same way they bind Claude Code; it is the same file, read by both agents.
5. The tail of the most recent file under `<vault>/daily/` (the last 25 lines is enough, matching
   what Claude Code's session-start hook injects). This is the shared session log described below
   - reading it tells you what happened in sessions the other agent ran, not just what you ran.

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
4. Append a session entry to `<vault>/daily/YYYY-MM-DD.md` (today's date, create the file with a
   `# Daily Log: YYYY-MM-DD` / `## Sessions` skeleton if it does not exist yet). This is the same
   file Claude Code's `flush.py` hook writes after every session, and the evening compile reads
   whatever landed in `daily/` regardless of which agent wrote it. Skip this and a Hermes session
   leaves no trace the compiler will ever see - half the memory system stops working for you.

   Match the shape `flush.py` renders exactly, since the compile step treats every session
   the same way and a differently-shaped entry either gets misread or silently ignored:

   ```
   ### Session (HH:MM)

   ## Context

   <what the session was about>

   ## Key Conversations

   <what was actually discussed>

   ## Decisions

   <what was decided>

   ## Lessons

   <anything learned>

   ## To-Dos

   <what is left open>
   ```

   The block above is indented here only because it sits inside this list. Write the headings at
   the start of the line, with no leading spaces: an indented `## Context` is not a heading, and
   the entry stops matching what `flush.py` writes.

   Use the current local time for `HH:MM`. Omit a section only when it is genuinely empty, the
   same way `flush.py` does. If literally nothing durable happened, skip the daily entry too - do
   not write an empty session block just to have written one.

## Knowledge base: read-only

`<vault>/knowledge/` is compiled by Claude Code's `compile.py` from `daily/` entries, and the
compiler fails closed the moment it finds a file it did not write itself: it diffs a manifest of
that folder before and after each run, and any change it cannot attribute to its own write is
treated as tampering, not a merge. **Never write into `knowledge/`.** Reading it is fine and
encouraged - it is durable, cross-session knowledge distilled from `daily/`, including from your
own sessions once they have been compiled.

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
| `daily/` | machine-written session log, one file per day - write your session entry here, never hand-edit older entries |
| `knowledge/` | machine-compiled knowledge base - read-only, see above |

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
