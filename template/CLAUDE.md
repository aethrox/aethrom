# {{OS_NAME}} - Second Brain (Claude Context)

@AGENTS.md

The file above is the whole context for this vault: who you are, where things go, and the memory
protocol you must follow. It is shared with every other agent that works here, so it stays the
single source of truth. The `@` line is a Claude Code import, so its contents load with this file
rather than waiting for you to open it.

Claude Code adds one thing on top of it. The hooks in `.claude/hooks/` inject the memory bridge
at session start and nudge you to write it back before the session ends. They only carry and
remind; the writing itself is still yours to do.
