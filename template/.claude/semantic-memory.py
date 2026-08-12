#!/usr/bin/env python
"""Optional semantic recall layer — the bridge between the companion and mem0.

Setup:
    uv venv .claude/mem0-venv
    uv pip install --python .claude/mem0-venv/bin/python mem0ai      # Scripts/python.exe on Windows
    # then put a free key from https://mem0.ai into .claude/settings.local.json:
    #   "env": { "MEM0_API_KEY": "..." }

Usage:
    .claude/mem0-venv/bin/python .claude/semantic-memory.py add "a durable fact"
    .claude/mem0-venv/bin/python .claude/semantic-memory.py search "topic"

`uv tool install mem0ai` does NOT work — mem0ai is a library and ships no executables.
Do not rename this file to mem0.py: its own directory is on sys.path and would shadow
the mem0 package. The files in 850-Companion/ remain the source of truth; this is only
a recall index, so a failure here must never block a reply.
"""
import json
import pathlib
import sys

USER_ID = "{{USER_ID}}"
SETTINGS = pathlib.Path(__file__).with_name("settings.local.json")


def client():
    key = json.loads(SETTINGS.read_text(encoding="utf-8")).get("env", {}).get("MEM0_API_KEY", "")
    if not key:
        sys.exit("MEM0_API_KEY is empty — put it in .claude/settings.local.json")
    from mem0 import MemoryClient

    return MemoryClient(api_key=key)


def main(argv):
    if len(argv) < 3 or argv[1] not in ("add", "search"):
        sys.exit(__doc__)
    cmd, text = argv[1], " ".join(argv[2:])
    c = client()
    if cmd == "add":
        c.add([{"role": "user", "content": text}], user_id=USER_ID)
        print("added")
        return
    # search() rejects a top-level user_id; it wants a v2 filter block
    res = c.search(text, version="v2", filters={"AND": [{"user_id": USER_ID}]})
    # v1 returns a bare list, v2 wraps it in {"results": [...]}
    hits = res.get("results", []) if isinstance(res, dict) else res
    if not hits:
        print("no results")
    for h in hits:
        print(f"- {h.get('memory', '')}  (score {h.get('score') or 0:.2f})")


if __name__ == "__main__":
    main(sys.argv)
