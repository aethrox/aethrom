import sys

sys.dont_write_bytecode = True

import hashlib
import json
import os
import time
from pathlib import Path


def vault_root():
    """The vault directory: prefer $CLAUDE_PROJECT_DIR, else the grandparent of this file."""
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    if env_dir:
        candidate = Path(env_dir)
        if candidate.is_dir():
            return candidate.resolve()
    return Path(__file__).resolve().parent.parent.parent


def state_dir():
    """<vault>/.claude/hooks/.state, created if missing."""
    path = vault_root() / ".claude" / "hooks" / ".state"
    path.mkdir(parents=True, exist_ok=True)
    return path


def memory_dir():
    """The companion memory folder, found by globbing '🔮 850-*' under the vault root.

    Never hardcode the companion name: the install step renames this folder to
    '🔮 850-{{COMPANION}}', so a fixed name would break every real vault.
    """
    matches = sorted(vault_root().glob("🔮 850-*"))
    matches = [m for m in matches if m.is_dir()]
    return matches[0] if matches else None


def session_key(session_id):
    """Lowercase hex sha256 of session_id, or the literal 'nosession' when it is missing."""
    if not session_id:
        return "nosession"
    return hashlib.sha256(str(session_id).encode("utf-8")).hexdigest()


def read_hook_input():
    """Read and parse the hook's JSON payload from stdin. Never raises; returns {} on failure."""
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def emit_context(event_name, text):
    """Print one line of hook JSON, or nothing when text is empty/whitespace."""
    if not text or not text.strip():
        return
    payload = {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": text}}
    print(json.dumps(payload))


def cap_section(text, limit, label):
    """Truncate text to at most limit characters, cutting at a line boundary when possible."""
    if len(text) <= limit:
        return text
    note = "[note: {} truncated at {} characters, run the doctor skill]".format(label, limit)
    keep = max(limit - len(note) - 1, 0)
    truncated = text[:keep]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    return "{}\n{}".format(truncated, note)


def mtime(path):
    """Integer mtime of path, or 0 when it does not exist."""
    try:
        return int(os.stat(path).st_mtime)
    except OSError:
        return 0


def cleanup_state(state_directory):
    """Delete session state files older than 7 days. Never raises.

    'flush-' covers both of flush.py's per-session files, the dedup record and
    its lock. They are keyed by session id, so nothing ever revisits one and
    they otherwise accumulate one pair per session for the life of the vault.
    A week is far outside the 60 second dedup window, and a session id never
    recurs, so no live flush can be holding a file this old.

    The prefix is 'flush-' with the dash: 'last-flush.json' is the vault's
    single most recent flush record and must survive, as must health.json,
    compile-state.json and the backup markers.
    """
    cutoff = time.time() - 7 * 86400
    prefixes = ("session_start_time.", "prompt_count.", "needs_reflection.", "flush-")
    try:
        entries = os.listdir(state_directory)
    except OSError:
        return
    for name in entries:
        if not name.startswith(prefixes):
            continue
        path = os.path.join(str(state_directory), name)
        try:
            if os.path.isfile(path) and os.stat(path).st_mtime < cutoff:
                os.remove(path)
        except OSError:
            pass


CLI_REASON_LIMIT = 80


def claude_exit_reason(returncode, stdout):
    """Name a failed `claude -p` run, using the CLI's own message when it gave one.

    The CLI reports a failure like an expired token as JSON on stdout while
    still exiting non-zero, so a caller that reads only the exit code turns an
    actionable sentence into an opaque 'claude-exit-1'. That string is what
    reaches health.json and the daily-log fallback note, and it is the only
    thing the user ever sees, so it carries the reason when there is one.

    Flattened and capped: the same string goes into a JSON health record and a
    single Markdown line, and neither survives a multi-line CLI message.
    """
    base = "claude-exit-{}".format(returncode)
    try:
        payload = json.loads(stdout)
    except (ValueError, TypeError):
        return base
    if not isinstance(payload, dict):
        return base
    message = payload.get("result")
    if not isinstance(message, str) or not message.strip():
        return base
    return "{}:{}".format(base, " ".join(message.split())[:CLI_REASON_LIMIT])
