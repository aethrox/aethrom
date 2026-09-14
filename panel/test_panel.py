#!/usr/bin/env python3
"""Standard-library checks for panel.py.

Runs against a throwaway vault built in a temp directory, so it works on any machine and
never touches real notes. The fixture deliberately names the companion folder
'850-Sage', not '850-Aether', because hardcoding that name is exactly the bug this
guards against.
"""

import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import panel  # noqa: E402

THREADS = """# Threads

## Active Threads

### Thread: Ship the thing
**Status:** 🟢 Active - created 2026-01-02
Still no outreach. See [[Goals]].

### Thread: Fix the flaky check
**Status:** 🟡 Open - created 2026-01-03
It crashes under cp1252.

## Closed Threads

### Thread: Old idea
**Status:** ✅ Closed 2026-01-04 - opened 2026-01-01
Parked for good.
"""

LAST_SESSION = """# Last Session

## Session: 2026-01-05 - A short one

We did a thing.

## Where it stopped

Waiting on review.

## Previous
"""

CONCEPT = """---
title: A Concept
aliases: [concept]
tags: [one, two]
sources: [2026-01-05.md]
created: 2026-01-05
updated: 2026-01-05
---

# A Concept

Body text linking to [[Goals]].
"""

GOALS = """---
title: Goals
created: 2026-01-01
---

# Goals

Nothing links out of here.
"""

DAILY = """# Daily Log: 2026-01-05

## Sessions

### Session (09:00)

## Context

Did some work.

## To-Dos

Finish the panel.
"""


def build_vault(root: Path) -> Path:
    (root / "🔮 850-Sage").mkdir(parents=True)
    (root / "🔮 850-Sage" / "Threads.md").write_text(THREADS, encoding="utf-8")
    (root / "🔮 850-Sage" / "Last-Session.md").write_text(LAST_SESSION, encoding="utf-8")
    (root / "knowledge" / "concepts").mkdir(parents=True)
    (root / "knowledge" / "concepts" / "a-concept.md").write_text(CONCEPT, encoding="utf-8")
    (root / "⚔️ 200-Goals").mkdir()
    (root / "⚔️ 200-Goals" / "Goals.md").write_text(GOALS, encoding="utf-8")
    (root / "daily").mkdir()
    (root / "daily" / "2026-01-05.md").write_text(DAILY, encoding="utf-8")
    (root / ".claude" / "hooks" / ".state").mkdir(parents=True)
    (root / ".claude" / "settings.local.json").write_text('{"secret": "do-not-serve"}', encoding="utf-8")
    return root


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="panel-test-"))
    try:
        vault = build_vault(tmp / "vault")

        # the companion folder is found by globbing, not by its name
        mem = panel.memory_dir(vault)
        assert mem is not None and mem.name == "🔮 850-Sage", mem

        # threads: two active with resolved status classes, one closed, kept with its data
        threads = panel.parse_threads((mem / "Threads.md").read_text(encoding="utf-8"))
        assert len(threads["active"]) == 2, threads["active"]
        assert [t["status_class"] for t in threads["active"]] == ["ok", "warn"], threads["active"]
        assert threads["active"][0]["name"] == "Ship the thing"
        assert threads["closed_count"] == 1, threads["closed_count"]
        closed = threads.get("closed", [])
        assert closed and closed[0]["name"] == "Old idea", closed

        # frontmatter, including an inline list
        meta, body = panel.parse_frontmatter(
            (vault / "knowledge" / "concepts" / "a-concept.md").read_text(encoding="utf-8"))
        assert meta["title"] == "A Concept", meta
        assert meta["tags"] == ["one", "two"], meta
        assert body.lstrip().startswith("# A Concept"), body[:40]

        # wikilinks: a real one resolves, a dangling one stays plain text
        note_map = panel.build_note_map(vault)
        html = panel.render_body("[[Goals]] and [[NoSuchNoteXYZ]]", note_map)
        assert '<a href="/note?path=' in html, html
        assert "NoSuchNoteXYZ" in html and ">NoSuchNoteXYZ</a>" not in html, html

        # backlinks both ways: Threads.md and the concept both link to Goals
        back = panel.find_backlinks(vault, "⚔️ 200-Goals/Goals.md", note_map)
        assert len(back) == 2, back
        assert panel.find_backlinks(vault, "daily/2026-01-05.md", note_map) == []

        # folders are read from the vault, not from a fixed list
        folders = panel.top_folders(vault)
        assert "⚔️ 200-Goals" in folders and "daily" in folders, folders
        assert not any(f.startswith(".") for f in folders), folders

        # path guard: traversal, absolute paths and .claude are all refused
        assert panel.safe_join(vault, "../../etc/passwd") is None
        assert panel.safe_join(vault, ".claude/settings.local.json") is None
        assert panel.safe_join(vault, "C:/Windows/System32/drivers/etc/hosts") is None
        assert panel.safe_join(vault, "daily/2026-01-05.md") is not None

        # missing state files degrade instead of raising
        assert panel.read_state(vault, "health.json") == {}
        strip = panel.render_engine_strip({}, {}, {}, "", "")
        assert "engine-strip bad" in strip, strip
        assert "has not run yet" in strip.lower(), strip

        # a vault that does not exist is reported, not guessed at
        assert not panel.resolve_vault(str(tmp / "nope")).is_dir()

        print("all checks passed")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
