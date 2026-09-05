import sys

sys.dont_write_bytecode = True

import datetime as dt
import json
import os
import re
import secrets
import subprocess
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _common import (  # noqa: E402
    cap_section,
    cleanup_state,
    emit_context,
    memory_dir,
    mtime,
    read_hook_input,
    session_key,
    state_dir,
    vault_root,
)
import portalock  # noqa: E402

LOCK_ATTEMPTS = 200
LOCK_SLEEP_SECONDS = 0.01
NUDGE_MULTIPLE = 15
REFLECTION_MIN_PROMPTS = 5

SESSION_CONTEXT_BUDGET = 16000
CAP_LAST_SESSION = 4000
CAP_THREADS = 2000
CAP_RULES = 4000
CAP_JOURNAL = 1500
CAP_REFLECTION = 1000
CAP_BACKUP_WARN = 1000
RULES_LINE_LIMIT = 60
JOURNAL_BLOCK_LINES = 10  # the '## ' heading plus 9 following lines
INDEX_LINE_LIMIT = 150
DAILY_TAIL_LINES = 25
SESSION_CONTEXT_DIAGNOSTIC = (
    "Memory warning: the session-start context did not fit the 16,000 character "
    "budget even after dropping the knowledge index, the daily log, the journal "
    "bridge and the reflection warning. Run the doctor skill."
)


def _read_int(path, default=0):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return default


def _write_text(path, text):
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass


def _extract_last_session(text):
    """Block from '## Session:' up to (and including) '## Previous', first 50 lines,
    dropping the last line of that selection (mirrors the shell pipeline this replaces:
    sed range include both bounds, head -50, then drop the final line).
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## Session:"):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## Previous"):
            end = j + 1
            break
    block = lines[start:end][:50]
    if block:
        block = block[:-1]
    return "\n".join(block)


def _extract_active_threads(text):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("## Active"):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].startswith("## Closed"):
            end = j + 1
            break
    block = lines[start:end]
    filtered = [
        line
        for line in block
        if re.match(r"^### ", line) or re.match(r"^\*\*Status:\*\*", line)
    ]
    return "\n".join(filtered[:12])


def _read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _extract_rules(text):
    """The first 60 lines of Rules.md, the injection window it documents itself."""
    return "\n".join(text.splitlines()[:RULES_LINE_LIMIT])


def _extract_journal_bridge(text):
    """The last '## ' entry of Journal.md: that heading plus the 9 lines after it.

    This is the first place anything reads Journal.md back. Without it the
    companion writes a journal it can never remember.
    """
    lines = text.splitlines()
    last_heading = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            last_heading = i
    if last_heading is None:
        return ""
    return "\n".join(lines[last_heading : last_heading + JOURNAL_BLOCK_LINES])


def _extract_knowledge_index(text):
    """The first 150 lines of knowledge/index.md."""
    return "\n".join(text.splitlines()[:INDEX_LINE_LIMIT])


def _daily_tail(root):
    """Last 25 lines of today's daily log, or yesterday's when today has none yet."""
    today = dt.date.today()
    for day in (today, today - dt.timedelta(days=1)):
        path = root / "daily" / "{}.md".format(day.isoformat())
        if path.is_file():
            return "\n".join(_read_file(path).splitlines()[-DAILY_TAIL_LINES:])
    return ""


def _assemble_session_context(
    reflection, backup_warn, last_session, threads, rules, journal, index_block, daily, identity
):
    parts = []
    if reflection:
        parts.append(reflection + "\n\n")
    if backup_warn:
        parts.append(backup_warn + "\n\n")
    if last_session:
        parts.append("[Memory - Last Session]\n{}\n\n".format(last_session))
    if threads:
        parts.append("[Memory - Active Threads]\n{}\n\n".format(threads))
    if rules:
        parts.append("[Memory - Rules]\n{}\n\n".format(rules))
    if journal:
        parts.append("[Memory - Journal]\n{}\n\n".format(journal))
    if index_block:
        parts.append("[Knowledge - Index]\n{}\n\n".format(index_block))
    if daily:
        parts.append("[Memory - Daily Log]\n{}\n\n".format(daily))
    parts.append(identity)
    return "".join(parts)


def _spawn_catchup_compile():
    """Fire the off-hours catch-up compile, detached, and never wait on it.

    session-start.sh did this at its tail in the shell-based engine: an
    earlier day's log can finish (SessionEnd closes it) without ever passing
    through the 18:00 evening path, so a catch-up chance is needed somewhere
    that runs on every session start regardless of the hour. Detached and
    fire-and-forget, because SessionStart has a 15 second budget and
    flush.py decides internally whether anything is even due; a session with
    nothing to catch up on returns almost immediately, but this call must add
    nothing measurable to the hook either way.
    """
    flush_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flush.py")
    try:
        subprocess.Popen(
            [sys.executable, flush_script, "--maybe-compile"],
            cwd=str(vault_root()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **portalock.detached_kwargs()
        )
    except OSError:
        pass


def cmd_session_start(argv):
    payload = read_hook_input()
    key = session_key(payload.get("session_id"))
    sdir = state_dir()

    _write_text(os.path.join(str(sdir), "session_start_time.{}".format(key)), str(int(time.time())))
    _write_text(os.path.join(str(sdir), "prompt_count.{}".format(key)), "0")
    cleanup_state(sdir)

    reflection = ""
    for reflection_file in sorted(sdir.glob("needs_reflection.*")):
        detail = _read_file(reflection_file).strip()
        if detail:
            piece = (
                "The previous session ended without a memory write: {}. "
                "If anything mattered, update the companion memory files.".format(detail)
            )
            reflection = "{}\n{}".format(reflection, piece) if reflection else piece
        try:
            reflection_file.unlink()
        except OSError:
            pass

    backup_warn = ""
    backup_failed = sdir / "backup_failed"
    backup_ok = sdir / "backup_ok"
    if backup_failed.is_file():
        lines = _read_file(backup_failed).splitlines()
        since = lines[0] if len(lines) > 0 else ""
        why = lines[1] if len(lines) > 1 else ""
        backup_warn = (
            "Vault backup failing since {}: {} (nothing else reports this, tell the user)".format(
                since, why
            )
        )
    elif backup_ok.is_file():
        age = (int(time.time()) - mtime(backup_ok)) // 3600
        if age >= 24:
            backup_warn = (
                "The vault backup has not run for {} hours. "
                "Its scheduled task may be gone. Tell the user.".format(age)
            )

    mem_dir = memory_dir()
    last_session = ""
    threads = ""
    rules = ""
    journal = ""
    if mem_dir is not None:
        last_session_path = mem_dir / "Last-Session.md"
        if last_session_path.is_file():
            last_session = _extract_last_session(_read_file(last_session_path))
        threads_path = mem_dir / "Threads.md"
        if threads_path.is_file():
            threads = _extract_active_threads(_read_file(threads_path))
        rules_path = mem_dir / "Rules.md"
        if rules_path.is_file():
            rules = _extract_rules(_read_file(rules_path))
        journal_path = mem_dir / "Journal.md"
        if journal_path.is_file():
            journal = _extract_journal_bridge(_read_file(journal_path))

    root = vault_root()
    index_path = root / "knowledge" / "index.md"
    index_block = _extract_knowledge_index(_read_file(index_path)) if index_path.is_file() else ""
    daily = _daily_tail(root)

    identity = "[Memory] Identity: {{COMPANION}}, {{USER_NAME}}'s thinking partner. Continuity is your job."

    # Layer one: cap each section on its own so one bloated file cannot starve
    # the others. Last Session, Threads and Rules are the continuity this whole
    # system exists to carry, so they never drop entirely, only truncate.
    last_session = cap_section(last_session, CAP_LAST_SESSION, "last session") if last_session else ""
    threads = cap_section(threads, CAP_THREADS, "active threads") if threads else ""
    rules = cap_section(rules, CAP_RULES, "rules") if rules else ""
    journal = cap_section(journal, CAP_JOURNAL, "journal") if journal else ""
    reflection = cap_section(reflection, CAP_REFLECTION, "memory warnings") if reflection else ""
    # backup.sh's die() writes the failure reason as a single line, and that
    # line can be arbitrarily long: the em-dash check reports every offending
    # file on one line. Uncapped, that line alone could consume the whole
    # session budget below and evict every other section. Same cap as the
    # reflection warning, for the same kind of message.
    backup_warn = cap_section(backup_warn, CAP_BACKUP_WARN, "backup warning") if backup_warn else ""

    ctx = _assemble_session_context(
        reflection, backup_warn, last_session, threads, rules, journal, index_block, daily, identity
    )

    # Layer two: a global 16,000 character budget. If still over after the
    # per-section caps, drop whole sections in this order until it fits.
    # Last Session, Active Threads and Rules are never dropped.
    if len(ctx) > SESSION_CONTEXT_BUDGET:
        for name in ("index", "daily", "journal", "reflection", "backup_warn"):
            if name == "index":
                index_block = ""
            elif name == "daily":
                daily = ""
            elif name == "journal":
                journal = ""
            elif name == "reflection":
                reflection = ""
            elif name == "backup_warn":
                backup_warn = ""
            ctx = _assemble_session_context(
                reflection, backup_warn, last_session, threads, rules, journal, index_block, daily, identity
            )
            if len(ctx) <= SESSION_CONTEXT_BUDGET:
                break

    if len(ctx) > SESSION_CONTEXT_BUDGET:
        ctx = SESSION_CONTEXT_DIAGNOSTIC

    emit_context("SessionStart", ctx)
    _spawn_catchup_compile()


def cmd_prompt_counter(argv):
    payload = read_hook_input()
    key = session_key(payload.get("session_id"))
    sdir = state_dir()
    count_file = sdir / "prompt_count.{}".format(key)
    lock_dir = sdir / "prompt_count.{}.lock".format(key)

    locked = False
    for _ in range(LOCK_ATTEMPTS):
        try:
            os.mkdir(lock_dir)
            locked = True
            break
        except FileExistsError:
            time.sleep(LOCK_SLEEP_SECONDS)
        except OSError:
            break

    try:
        count = _read_int(count_file, 0) + 1
        _write_text(str(count_file), str(count))
    finally:
        if locked:
            try:
                os.rmdir(lock_dir)
            except OSError:
                pass

    if count % NUDGE_MULTIPLE == 0:
        emit_context(
            "UserPromptSubmit",
            "[Memory] This session is running long. Before it ends, update Last-Session.md and Threads.md.",
        )


def _handoff_to_flush(payload, reason):
    """Hand the hook payload to a detached flush.py run and return immediately.

    The child process cannot inherit this process's stdin (it is already
    consumed, and a detached child has none anyway), so the payload goes
    through a file instead. Permissions are 0600 because the payload carries
    the transcript path. The hook must never wait on the child: SessionEnd and
    PreCompact both have short timeouts, and the whole point of detaching is
    that the flush can take longer than either allows.
    """
    sdir = state_dir()
    name = "hookin-{}-{}.json".format(os.getpid(), secrets.token_hex(4))
    hook_input_path = sdir / name
    try:
        descriptor = os.open(str(hook_input_path), os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(payload, handle)
        except BaseException:
            os.close(descriptor)
            raise
    except OSError:
        return

    flush_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flush.py")
    try:
        subprocess.Popen(
            [sys.executable, flush_script, "--hook-input", str(hook_input_path), "--reason", reason],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            **portalock.detached_kwargs()
        )
    except OSError:
        try:
            hook_input_path.unlink()
        except OSError:
            pass


def cmd_pre_compact(argv):
    payload = read_hook_input()
    _handoff_to_flush(payload, "precompact")


def cmd_session_end(argv):
    payload = read_hook_input()
    key = session_key(payload.get("session_id"))
    sdir = state_dir()
    start_file = sdir / "session_start_time.{}".format(key)
    count_file = sdir / "prompt_count.{}".format(key)
    reflection_file = sdir / "needs_reflection.{}".format(key)

    start = _read_int(start_file, 0)
    count = _read_int(count_file, 0)

    modified = False
    mem_dir = memory_dir()
    if mem_dir is not None:
        last_session_path = mem_dir / "Last-Session.md"
        if last_session_path.is_file():
            modified = mtime(last_session_path) > start

    if count >= REFLECTION_MIN_PROMPTS and not modified:
        reason = "session ended without a memory write, {} prompts, {}".format(
            count, time.strftime("%Y-%m-%d %H:%M")
        )
        _write_text(str(reflection_file), reason + "\n")

    for path in (start_file, count_file):
        try:
            path.unlink()
        except OSError:
            pass

    _handoff_to_flush(payload, "sessionend")


SUBCOMMANDS = {
    "session-start": cmd_session_start,
    "prompt-counter": cmd_prompt_counter,
    "session-end": cmd_session_end,
    "pre-compact": cmd_pre_compact,
}


def main(argv):
    if len(argv) < 2:
        return 0
    handler = SUBCOMMANDS.get(argv[1])
    if handler is None:
        return 0
    try:
        handler(argv)
    except Exception as exc:  # noqa: BLE001 - a crashing hook is worse than a silent one
        print("hooks.py: {} failed: {}".format(argv[1], exc), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
