#!/usr/bin/env python3
"""Report-only comparison of an installed vault against this repo's template/.

Writes nothing, moves nothing, deletes nothing, and has no flag that would make it do so.
Run it, read the report, then act on it by hand (see the "Upgrading" section of SETUP.md).

Usage: python scripts/upgrade-check.py <vault-path>

Exit codes: 0 = vault already current, 1 = something to do, 2 = usage error.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:  # the report contains emoji (folder names); Windows consoles default to cp1252
    sys.stdout.reconfigure(encoding="utf-8")
except AttributeError:
    pass

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "template"

# Directories that hold the user's own memory. Never diffed, never suggested for
# replacement, no matter what changed in template/.
USER_MEMORY_DIRS = ("daily", "knowledge/concepts", "knowledge/connections")

BASH_ERA_LEFTOVERS = (
    ".claude/hooks/_common.sh",
    ".claude/hooks/session-start.sh",
    ".claude/hooks/prompt-counter.sh",
    ".claude/hooks/session-end.sh",
    ".claude/settings.windows.json",
)

ADDED_FOLDERS = ("daily", "knowledge", "knowledge/concepts", "knowledge/connections")

# Engine/skill trees compared wholesale: code, meant to be replaced, never the user's memory.
COMPARE_TREES = (".claude/hooks", ".claude/skills")

BASH_HOOK_NAMES = ("session-start.sh", "prompt-counter.sh", "session-end.sh", "_common.sh")


def iter_files(root: Path):
    if not root.is_dir():
        return
    for p in sorted(root.rglob("*")):
        if p.is_file() and ".state" not in p.relative_to(root).parts and p.name != "__pycache__":
            yield p


def find_memory_folder(vault: Path) -> Path | None:
    matches = sorted(vault.glob("\U0001F52E 850-*"))
    return matches[0] if matches else None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    vault = Path(argv[1])
    if not vault.is_dir():
        print(f"not a directory: {vault}", file=sys.stderr)
        return 2

    todo = False
    print(f"Comparing {vault} against {TEMPLATE}\n")

    # 1. Version stamp.
    tpl_version = (TEMPLATE / ".aethrom-version").read_text(encoding="utf-8").strip()
    vault_version_file = vault / ".aethrom-version"
    if vault_version_file.is_file():
        v = vault_version_file.read_text(encoding="utf-8").strip()
        if v != tpl_version:
            print(f"[version] vault is {v}, repo ships {tpl_version}")
            todo = True
        else:
            print(f"[version] up to date ({v})")
    else:
        print(f"[version] no .aethrom-version: vault predates version stamping (repo ships {tpl_version})")
        todo = True

    # 2. Engine and skill files: differ / missing / new. These are code, replace wholesale.
    print("\n[engine/skills] code files (replace wholesale, never the files below under Leftovers):")
    any_code_change = False
    for tree in COMPARE_TREES:
        tpl_tree = TEMPLATE / tree
        vault_tree = vault / tree
        tpl_files = {f.relative_to(tpl_tree): f for f in iter_files(tpl_tree)}
        vault_files = {f.relative_to(vault_tree): f for f in iter_files(vault_tree)}
        for rel, tpl_f in tpl_files.items():
            vf = vault_files.get(rel)
            if vf is None:
                print(f"  missing: {tree}/{rel.as_posix()}")
                any_code_change = True
            elif vf.read_bytes() != tpl_f.read_bytes():
                print(f"  differs: {tree}/{rel.as_posix()}")
                any_code_change = True
        for rel in vault_files:
            if rel not in tpl_files:
                print(f"  new (not in repo template): {tree}/{rel.as_posix()}")
                any_code_change = True
    if not any_code_change:
        print("  none, engine and skills match")
    else:
        todo = True

    # 3. Bash-era leftovers to remove.
    print("\n[leftovers] bash-era files this vault should remove:")
    any_leftover = False
    for rel in BASH_ERA_LEFTOVERS:
        if (vault / rel).exists():
            print(f"  remove: {rel}")
            any_leftover = True
            todo = True
    if not any_leftover:
        print("  none")

    # 4. Folders the port added.
    print("\n[folders] added by the port, missing from this vault:")
    any_missing_folder = False
    for rel in ADDED_FOLDERS:
        if not (vault / rel).is_dir():
            print(f"  missing: {rel}/")
            any_missing_folder = True
            todo = True
    if not any_missing_folder:
        print("  none")

    # 5. Seed files, only when absent, never overwrite.
    print("\n[seeds] seeded only when absent, never overwritten (the vault's content wins):")
    any_missing_seed = False
    mem_dir = find_memory_folder(vault)
    if mem_dir is None:
        print("  memory folder (\U0001F52E 850-*) not found, cannot check Rules.md")
        any_missing_seed = True
    elif not (mem_dir / "Rules.md").is_file():
        print(f"  missing: {mem_dir.name}/Rules.md")
        any_missing_seed = True
    for rel in ("knowledge/index.md", "knowledge/log.md"):
        if not (vault / rel).is_file():
            print(f"  missing: {rel}")
            any_missing_seed = True
    if any_missing_seed:
        todo = True
    else:
        print("  none")

    # 6. Never touch the user's memory. Say so explicitly.
    print(
        "\n[memory] daily/, knowledge/concepts/, knowledge/connections/, and the "
        "\U0001F52E 850-* memory folder hold the user's own content. This report never lists "
        "them for replacement, and nothing here should be copied over them."
    )

    # 7. settings.local.json still wired to the dead bash hooks.
    print("\n[settings] settings.local.json engine wiring:")
    settings_local = vault / ".claude" / "settings.local.json"
    if not settings_local.is_file():
        print("  no settings.local.json found")
    else:
        text = settings_local.read_text(encoding="utf-8", errors="replace")
        stale = [name for name in BASH_HOOK_NAMES if name in text]
        if stale:
            print(f"  STILL WIRED TO DEAD BASH HOOKS: {', '.join(stale)}")
            print("  this is the one thing that silently keeps a vault on the dead engine")
            todo = True
        else:
            print("  ok, not pointing at bash-era hooks")

    print(f"\n{'Upgrade needed.' if todo else 'Vault is already current.'}")
    return 1 if todo else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
