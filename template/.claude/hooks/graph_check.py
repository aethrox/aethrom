#!/usr/bin/env python3
"""Scan an Obsidian vault for broken wikilinks and orphan Markdown notes."""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path
import unicodedata
from urllib.parse import unquote


# --- CONFIG -------------------------------------------------------------------
SKIP_DIRS = {
    ".git",
    ".claude",
    ".obsidian",
    "node_modules",
    "\U0001F4E6 900-Archive",  # 900-Archive
}
ORPHAN_EXEMPT_DIRS = {"\U0001F4CB Templates", "daily", "knowledge"}  # Templates
ORPHAN_EXEMPT_PATHS = {
    "README.md",
    "CLAUDE.md",
    "AGENTS.md",
    "MEMORY.md",
    "SETUP.md",
    "SETUP-WINDOWS.md",
    "\U0001F3AF 100-Command-Center/Dashboard.md",
}
# The memory files cannot be listed above. The install step renames their folder
# to '\U0001F52E 850-{{COMPANION}}', so a fixed path matches the template and no real
# vault: listing '850-Companion' here reported every real vault's five memory
# files as orphans, while the doctor skill told the user they were exempt.
# _common.memory_dir() globs the prefix for exactly this reason.
MEMORY_DIR_PREFIX = "\U0001F52E 850-"
MEMORY_FILES = {
    "Core.md",
    "Journal.md",
    "Last-Session.md",
    "Rules.md",
    "Threads.md",
}
# --------------------------------------------------------------------------------

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
INLINE_CODE = re.compile(r"`+[^`\n]*`+")
OBSIDIAN_COMMENT = re.compile(r"%%.*?%%", re.DOTALL)
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
TRUNCATE_LISTING = 10


def _key(value: str) -> str:
    value = unquote(value).replace("\\", "/").strip().lstrip("/")
    value = unicodedata.normalize("NFC", value)
    return value.casefold()


def _is_skipped(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in SKIP_DIRS for part in parts)


def _wikilink_text(text: str) -> str:
    """Remove regions where Obsidian does not create graph edges."""
    text = OBSIDIAN_COMMENT.sub("", text)
    kept: list[str] = []
    fence_character: str | None = None
    for line in text.splitlines():
        match = FENCE.match(line)
        if match:
            character = match.group(1)[0]
            if fence_character is None:
                fence_character = character
            elif character == fence_character:
                fence_character = None
            continue
        if fence_character is None:
            kept.append(INLINE_CODE.sub("", line))
    return "\n".join(kept)


def _target(raw: str) -> str:
    # Markdown tables escape the alias separator as \|. In both forms the
    # portion after the first pipe is display text, not the target.
    target = raw.split("|", 1)[0].rstrip("\\").strip()
    target = re.split(r"[#^]", target, maxsplit=1)[0].strip()
    return unquote(target)


def _find_files(root: Path) -> tuple[list[Path], list[Path]]:
    all_files: list[Path] = []
    notes: list[Path] = []
    for path in root.rglob("*"):
        if _is_skipped(path, root):
            continue
        try:
            is_file = path.is_file()
        except OSError:
            continue
        if not is_file:
            continue
        all_files.append(path)
        if path.suffix.casefold() == ".md":
            notes.append(path)
    return all_files, notes


def _target_map(
    root: Path,
    all_files: list[Path],
) -> tuple[dict[str, set[Path]], dict[str, set[Path]]]:
    by_path: dict[str, set[Path]] = {}
    by_name: dict[str, set[Path]] = {}

    def add(mapping: dict[str, set[Path]], key: str, path: Path) -> None:
        mapping.setdefault(_key(key), set()).add(path)

    for path in all_files:
        relative = path.relative_to(root)
        for start in range(len(relative.parts)):
            add(by_path, Path(*relative.parts[start:]).as_posix(), path)
        add(by_name, path.name, path)
        if path.suffix.casefold() == ".md":
            without_suffix = relative.with_suffix("")
            for start in range(len(without_suffix.parts)):
                add(
                    by_path,
                    Path(*without_suffix.parts[start:]).as_posix(),
                    path,
                )
            add(by_name, path.stem, path)
    return by_path, by_name


def _resolve(
    root: Path,
    source: Path,
    target: str,
    by_path: dict[str, set[Path]],
    by_name: dict[str, set[Path]],
) -> set[Path]:
    key = _key(target)
    candidates = set(by_path.get(key, set()))
    if not candidates and ("/" in target or target.startswith(".")):
        source_parent = source.relative_to(root).parent.as_posix()
        relative_key = _key(posixpath.normpath(f"{source_parent}/{target}"))
        candidates.update(by_path.get(relative_key, set()))
    if not candidates and "/" not in target:
        candidates.update(by_name.get(key, set()))
    return candidates


def _is_memory_file(relative: str) -> bool:
    """True for a companion memory file, whatever the companion is called.

    These are injected into every session, so nothing needs to link to them.
    Matched on the folder prefix rather than a fixed name, because the folder
    carries the companion's name after install.
    """
    head, _, tail = relative.partition("/")
    return head.startswith(MEMORY_DIR_PREFIX) and tail in MEMORY_FILES


def scan(root: Path):
    """Return (scanned Markdown count, broken links, orphan notes)."""
    root = root.resolve()
    all_files, notes = _find_files(root)
    by_path, by_name = _target_map(root, all_files)
    note_set = set(notes)
    incoming = {path: 0 for path in notes}
    broken: list[tuple[Path, str]] = []

    for path in notes:
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for raw in WIKILINK.findall(_wikilink_text(text)):
            target = _target(raw)
            if (
                not target
                or target.endswith("/")
                or target.startswith(("http://", "https://"))
            ):
                continue
            candidates = _resolve(root, path, target, by_path, by_name)
            if not candidates:
                broken.append((path.relative_to(root), target))
                continue
            # A basename may map to more than one note. Obsidian resolves that
            # by source proximity. Counting every candidate is conservative:
            # the advisory orphan report must not invent a false broken chain.
            for destination in candidates & note_set:
                if destination != path:
                    incoming[destination] += 1

    orphans = [
        path.relative_to(root)
        for path, count in incoming.items()
        if count == 0
        and not any(
            part in ORPHAN_EXEMPT_DIRS
            for part in path.relative_to(root).parts
        )
        and path.relative_to(root).as_posix() not in ORPHAN_EXEMPT_PATHS
        and not _is_memory_file(path.relative_to(root).as_posix())
    ]
    return len(notes), broken, sorted(
        orphans, key=lambda item: str(item).casefold()
    )


def main() -> None:
    full = "--full" in sys.argv
    total, broken, orphans = scan(Path("."))
    print(
        f"scanned: {total} notes | broken links: {len(broken)} | "
        f"orphan notes: {len(orphans)}"
    )

    if broken:
        print("\nBROKEN LINKS:")
        shown = broken if full else broken[:TRUNCATE_LISTING]
        for source, target in shown:
            print(f"  {source} -> [[{target}]]")
        if len(broken) > len(shown):
            print(
                f"  ... +{len(broken) - len(shown)} more "
                "(--full for the complete list)"
            )

    if orphans:
        print("\nORPHAN NOTES (nothing links here):")
        if full:
            for orphan in orphans:
                print(f"  {orphan}")
        else:
            counts: dict[str, int] = {}
            for orphan in orphans:
                directory = (
                    orphan.parts[0] if len(orphan.parts) > 1 else "(root)"
                )
                counts[directory] = counts.get(directory, 0) + 1
            for directory, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0].casefold())
            ):
                print(f"  {count:3d}  {directory}")
            print("  (--full for the file listing)")


def _selftest() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        (root / "a.md").write_text(
            "[[b]] and [[does-not-exist]] and `[[code-example]]`",
            encoding="utf-8",
        )
        (root / "b.md").write_text("body", encoding="utf-8")
        (root / "c.md").write_text(
            "nothing links to me", encoding="utf-8"
        )
        total, broken, orphans = scan(root)
        assert total == 3, total
        assert [target for _, target in broken] == ["does-not-exist"], broken
        assert [str(orphan) for orphan in orphans] == [
            "a.md",
            "c.md",
        ], orphans
    print("selftest: passed")


if __name__ == "__main__":
    _selftest() if "--selftest" in sys.argv else main()
