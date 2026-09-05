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


if __name__ == "__main__":
    unittest.main()
