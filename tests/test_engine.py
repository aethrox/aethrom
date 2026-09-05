import sys

sys.dont_write_bytecode = True

import importlib
import io
import json
import os
import sys as _sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

HOOKS_DIR = Path(__file__).resolve().parent.parent / "template" / ".claude" / "hooks"
_sys.path.insert(0, str(HOOKS_DIR))

import _common  # noqa: E402
import hooks  # noqa: E402
import flush  # noqa: E402
import portalock  # noqa: E402


def reload_modules():
    importlib.reload(_common)
    importlib.reload(hooks)


class VaultTestCase(unittest.TestCase):
    """Base case: sets CLAUDE_PROJECT_DIR to a fresh temp vault for each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        self._old_env = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.vault)
        reload_modules()

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._old_env
        self._tmp.cleanup()

    def run_subcommand(self, subcommand, session_id="test-session"):
        payload = json.dumps({"session_id": session_id})
        with mock.patch("sys.stdin", io.StringIO(payload)):
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                hooks.main(["hooks.py", subcommand])
            return buf.getvalue()


class TestSessionKey(unittest.TestCase):
    def test_stable_and_lowercase_hex(self):
        key = _common.session_key("abc-123")
        self.assertEqual(key, _common.session_key("abc-123"))
        self.assertEqual(len(key), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in key))

    def test_differs_for_different_ids(self):
        self.assertNotEqual(_common.session_key("session-a"), _common.session_key("session-b"))

    def test_empty_id_gives_nosession(self):
        self.assertEqual(_common.session_key(""), "nosession")
        self.assertEqual(_common.session_key(None), "nosession")


class TestPromptCounterConcurrency(VaultTestCase):
    def test_separate_sessions_have_separate_counters(self):
        self.run_subcommand("prompt-counter", session_id="session-a")
        self.run_subcommand("prompt-counter", session_id="session-a")
        self.run_subcommand("prompt-counter", session_id="session-b")

        key_a = _common.session_key("session-a")
        key_b = _common.session_key("session-b")
        sdir = _common.state_dir()

        count_a = int((sdir / "prompt_count.{}".format(key_a)).read_text().strip())
        count_b = int((sdir / "prompt_count.{}".format(key_b)).read_text().strip())

        self.assertEqual(count_a, 2)
        self.assertEqual(count_b, 1)


class TestPromptCounterNudge(VaultTestCase):
    def test_nudges_at_multiples_of_fifteen(self):
        outputs = {}
        for i in range(1, 31):
            outputs[i] = self.run_subcommand("prompt-counter", session_id="fixed-session")

        for silent_count in (1, 14, 16, 29):
            self.assertEqual(outputs[silent_count].strip(), "", "count {} should be silent".format(silent_count))

        for nudge_count in (15, 30):
            self.assertNotEqual(outputs[nudge_count].strip(), "", "count {} should nudge".format(nudge_count))
            parsed = json.loads(outputs[nudge_count])
            self.assertEqual(parsed["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")


class TestEmitContext(unittest.TestCase):
    def _captured(self, event, text):
        buf = io.StringIO()
        with mock.patch("sys.stdout", buf):
            _common.emit_context(event, text)
        return buf.getvalue()

    def test_emits_single_line_valid_json(self):
        out = self._captured("SessionStart", "hello")
        lines = out.splitlines()
        self.assertEqual(len(lines), 1)
        parsed = json.loads(lines[0])
        self.assertEqual(
            parsed,
            {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "hello"}},
        )

    def test_empty_or_whitespace_produces_nothing(self):
        self.assertEqual(self._captured("SessionStart", ""), "")
        self.assertEqual(self._captured("SessionStart", "   \n\t"), "")

    def test_escapes_special_characters(self):
        text = 'has "quotes", a \\ backslash and a\nnewline'
        out = self._captured("SessionStart", text)
        parsed = json.loads(out.splitlines()[0])
        self.assertEqual(parsed["hookSpecificOutput"]["additionalContext"], text)


class TestCapSection(unittest.TestCase):
    def test_under_limit_returned_unchanged(self):
        text = "short text"
        self.assertEqual(_common.cap_section(text, 100, "example"), text)

    def test_over_limit_truncates_with_note(self):
        text = "line1\n" * 500
        result = _common.cap_section(text, 100, "example")
        self.assertLessEqual(len(result), 200)
        self.assertIn("example", result)
        self.assertIn("truncated", result)


class TestCleanupState(VaultTestCase):
    def test_deletes_old_and_keeps_fresh(self):
        sdir = _common.state_dir()
        old_file = sdir / "prompt_count.oldkey"
        fresh_file = sdir / "prompt_count.freshkey"
        old_file.write_text("1")
        fresh_file.write_text("1")

        old_time = time.time() - 8 * 86400
        os.utime(old_file, (old_time, old_time))

        _common.cleanup_state(sdir)

        self.assertFalse(old_file.exists())
        self.assertTrue(fresh_file.exists())


class TestMemoryDir(VaultTestCase):
    def test_globs_rather_than_hardcodes(self):
        mem = self.vault / "\U0001F52E 850-Aether"
        mem.mkdir()
        found = _common.memory_dir()
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "\U0001F52E 850-Aether")

    def test_none_when_no_match(self):
        self.assertIsNone(_common.memory_dir())


class TestSessionEndReflection(VaultTestCase):
    def _seed_session(self, session_id, prompt_count, memory_touched_after_start):
        key = _common.session_key(session_id)
        sdir = _common.state_dir()
        start_time = int(time.time())
        (sdir / "session_start_time.{}".format(key)).write_text(str(start_time))
        (sdir / "prompt_count.{}".format(key)).write_text(str(prompt_count))

        mem_dir = self.vault / "\U0001F52E 850-Aether"
        mem_dir.mkdir(parents=True, exist_ok=True)
        last_session = mem_dir / "Last-Session.md"
        last_session.write_text("content")
        if memory_touched_after_start:
            touch_time = start_time + 10
        else:
            touch_time = start_time - 10
        os.utime(last_session, (touch_time, touch_time))
        return key

    def test_writes_marker_when_untouched_and_five_prompts(self):
        key = self._seed_session("s1", 5, memory_touched_after_start=False)
        self.run_subcommand("session-end", session_id="s1")
        marker = _common.state_dir() / "needs_reflection.{}".format(key)
        self.assertTrue(marker.exists())

    def test_no_marker_when_memory_touched_after_start(self):
        key = self._seed_session("s2", 5, memory_touched_after_start=True)
        self.run_subcommand("session-end", session_id="s2")
        marker = _common.state_dir() / "needs_reflection.{}".format(key)
        self.assertFalse(marker.exists())


class TestVaultRoot(unittest.TestCase):
    def setUp(self):
        self._old_env = os.environ.get("CLAUDE_PROJECT_DIR")

    def tearDown(self):
        if self._old_env is None:
            os.environ.pop("CLAUDE_PROJECT_DIR", None)
        else:
            os.environ["CLAUDE_PROJECT_DIR"] = self._old_env
        reload_modules()

    def test_honours_claude_project_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["CLAUDE_PROJECT_DIR"] = tmp
            reload_modules()
            self.assertEqual(_common.vault_root(), Path(tmp).resolve())

    def test_falls_back_to_grandparent(self):
        os.environ["CLAUDE_PROJECT_DIR"] = str(Path(tempfile.gettempdir()) / "does-not-exist-xyz")
        reload_modules()
        expected = Path(_common.__file__).resolve().parent.parent.parent
        self.assertEqual(_common.vault_root(), expected)


def _write_transcript(path, turns):
    """Write a minimal Claude Code JSONL transcript from (role, text) tuples."""
    with open(path, "w", encoding="utf-8") as handle:
        for role, text in turns:
            handle.write(json.dumps({"message": {"role": role, "content": text}}) + "\n")


def _write_hook_input(path, session_id, transcript_path):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"session_id": session_id, "transcript_path": str(transcript_path)}, handle)


class FlushTestCase(VaultTestCase):
    """VaultTestCase plus helpers to drive flush.py end to end."""

    def run_flush(self, session_id, turns, reason="sessionend", hook_input_name="hookin-test.json"):
        transcript_path = self.vault / "transcript.jsonl"
        _write_transcript(transcript_path, turns)
        hook_input_path = _common.state_dir() / hook_input_name
        _write_hook_input(hook_input_path, session_id, transcript_path)
        flush.main(["--hook-input", str(hook_input_path), "--reason", reason])
        return hook_input_path

    def daily_path(self):
        date_text = time.strftime("%Y-%m-%d")
        return self.vault / "daily" / "{}.md".format(date_text)

    def five_turns(self):
        return [
            ("user", "hello {}".format(i)) if i % 2 == 0 else ("assistant", "reply {}".format(i))
            for i in range(5)
        ]


class TestFormatTurns(unittest.TestCase):
    def test_keeps_last_turns_only(self):
        turns = [("user", "t{}".format(i)) for i in range(40)]
        rendered, count = flush.format_turns(turns, max_turns=30, max_chars=100_000)
        self.assertEqual(count, 30)
        self.assertNotIn("t0\n", rendered)
        self.assertIn("t39", rendered)

    def test_respects_character_cap(self):
        turns = [("user", "x" * 1000) for _ in range(20)]
        rendered, _count = flush.format_turns(turns, max_turns=30, max_chars=5_000)
        self.assertLessEqual(len(rendered), 5_000)

    def test_cuts_on_turn_boundary_not_mid_turn(self):
        turns = [("user", "a" * 100), ("assistant", "b" * 100), ("user", "c" * 100)]
        rendered, _count = flush.format_turns(turns, max_turns=30, max_chars=120)
        self.assertTrue(rendered.startswith("**"))
        # A mid-turn cut would start with a fragment of "b"*100 or "c"*100, not
        # the "**Role:**" prefix of a fresh turn.
        self.assertRegex(rendered, r"^\*\*(User|Assistant):\*\* ")


class TestTextFromContent(unittest.TestCase):
    def test_bare_string(self):
        self.assertEqual(flush._text_from_content("hello"), "hello")

    def test_list_of_text_blocks(self):
        content = [{"type": "text", "text": "one"}, {"type": "tool_use"}, {"type": "text", "text": "two"}]
        self.assertEqual(flush._text_from_content(content), "one\ntwo")

    def test_non_text_returns_empty(self):
        self.assertEqual(flush._text_from_content(42), "")
        self.assertEqual(flush._text_from_content(None), "")


class TestReadTranscript(FlushTestCase):
    def test_skips_unparseable_lines_but_counts_them(self):
        path = self.vault / "t.jsonl"
        with open(path, "w", encoding="utf-8") as handle:
            # 1 broken line out of 4 non-empty lines sits exactly at the
            # quarter threshold, which the spec requires to stay undegraded:
            # only *more* than a quarter of failures should trip the flag.
            handle.write(json.dumps({"message": {"role": "user", "content": "ok"}}) + "\n")
            handle.write(json.dumps({"message": {"role": "assistant", "content": "ok2"}}) + "\n")
            handle.write(json.dumps({"message": {"role": "user", "content": "ok3"}}) + "\n")
            handle.write("not json at all\n")
        turns, degraded = flush.read_transcript(path)
        self.assertEqual(turns, [("user", "ok"), ("assistant", "ok2"), ("user", "ok3")])
        self.assertFalse(degraded)

    def test_flags_degraded_past_quarter_threshold(self):
        path = self.vault / "t2.jsonl"
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({"message": {"role": "user", "content": "ok"}}) + "\n")
            for _ in range(3):
                handle.write("broken\n")
        turns, degraded = flush.read_transcript(path)
        self.assertEqual(turns, [("user", "ok")])
        self.assertTrue(degraded)


class TestMinimumTurns(FlushTestCase):
    def test_sessionend_writes_with_one_turn(self):
        self.run_flush("s1", [("user", "hi")], reason="sessionend")
        self.assertTrue(self.daily_path().exists())

    def test_precompact_needs_five_turns(self):
        self.run_flush("s2", [("user", "hi"), ("assistant", "yo")], reason="precompact")
        self.assertFalse(self.daily_path().exists())

    def test_precompact_writes_with_five_turns(self):
        self.run_flush("s3", self.five_turns(), reason="precompact")
        self.assertTrue(self.daily_path().exists())


class TestDailyFileCreation(FlushTestCase):
    def test_creates_skeleton_when_absent(self):
        self.run_flush("s4", self.five_turns())
        content = self.daily_path().read_text(encoding="utf-8")
        self.assertTrue(content.startswith("# Daily Log: "))
        self.assertIn("## Sessions", content)

    def test_appends_when_present(self):
        self.run_flush("s5", self.five_turns())
        first_len = len(self.daily_path().read_text(encoding="utf-8"))
        self.run_flush("s6", self.five_turns())
        second_len = len(self.daily_path().read_text(encoding="utf-8"))
        self.assertGreater(second_len, first_len)


class TestPrecompactHeading(FlushTestCase):
    def test_precompact_heading_differs_from_sessionend(self):
        self.run_flush("s7", self.five_turns(), reason="sessionend")
        sessionend_content = self.daily_path().read_text(encoding="utf-8")
        self.run_flush("s8", self.five_turns(), reason="precompact")
        combined = self.daily_path().read_text(encoding="utf-8")
        precompact_addition = combined[len(sessionend_content) :]
        self.assertNotIn("before compaction", sessionend_content)
        self.assertIn("before compaction", precompact_addition)


class TestDeduplication(FlushTestCase):
    def test_two_runs_within_window_append_once(self):
        self.run_flush("dup-session", self.five_turns())
        content_after_first = self.daily_path().read_text(encoding="utf-8")
        self.run_flush("dup-session", self.five_turns(), hook_input_name="hookin-second.json")
        content_after_second = self.daily_path().read_text(encoding="utf-8")
        self.assertEqual(content_after_first, content_after_second)
        self.assertEqual(content_after_second.count("### Session"), 1)


class TestEmDashNormalization(FlushTestCase):
    def test_em_dash_stripped_from_daily_output(self):
        em_dash = chr(0x2014)
        turns = [("user", "before {} after".format(em_dash))] + self.five_turns()
        self.run_flush("emdash-session", turns)
        content = self.daily_path().read_text(encoding="utf-8")
        self.assertNotIn(em_dash, content)


class TestHealthJson(FlushTestCase):
    def _health(self):
        health_path = _common.state_dir() / "health.json"
        return json.loads(health_path.read_text(encoding="utf-8"))

    def test_written_on_success(self):
        self.run_flush("health-ok", self.five_turns())
        payload = self._health()
        self.assertEqual(payload["component"], "flush")
        self.assertEqual(payload["error"], "ok")

    def test_written_on_failure(self):
        hook_input_path = _common.state_dir() / "hookin-bad.json"
        _write_hook_input(hook_input_path, "health-fail", self.vault / "does-not-exist.jsonl")
        flush.main(["--hook-input", str(hook_input_path), "--reason", "sessionend"])
        payload = self._health()
        self.assertTrue(payload["error"])

    def test_warning_history_caps_at_twenty(self):
        sdir = _common.state_dir()
        for i in range(25):
            flush.write_health(sdir, "warn:test-{}".format(i), warning=True)
        payload = self._health()
        self.assertEqual(len(payload["warnings"]), 20)
        self.assertEqual(payload["warnings"][-1], "warn:test-24")


class TestHookInputSweep(FlushTestCase):
    def test_consumed_input_is_deleted(self):
        hook_input_path = self.run_flush("sweep-session", self.five_turns(), hook_input_name="hookin-consumed.json")
        self.assertFalse(hook_input_path.exists())

    def test_stale_hookin_is_swept_and_fresh_is_kept(self):
        sdir = _common.state_dir()
        stale = sdir / "hookin-stale.json"
        stale.write_text("{}", encoding="utf-8")
        old_time = time.time() - 7200
        os.utime(stale, (old_time, old_time))

        self.run_flush("sweep-session-2", self.five_turns(), hook_input_name="hookin-fresh.json")

        self.assertFalse(stale.exists())

    def test_non_hookin_file_never_swept(self):
        sdir = _common.state_dir()
        other = sdir / "not-a-hook-input.json"
        other.write_text("{}", encoding="utf-8")
        old_time = time.time() - 7200
        os.utime(other, (old_time, old_time))

        self.run_flush("sweep-session-3", self.five_turns())

        self.assertTrue(other.exists())


if __name__ == "__main__":
    unittest.main()
