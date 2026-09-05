"""Cross-platform advisory file locking for the continuity engine.

Windows has no ``fcntl``, so importing it unconditionally kills a module at
load time on that platform: any file that does ``import fcntl`` at the top
level becomes unimportable on Windows before a single line of its logic runs.
This module provides the two primitives the engine actually needs, with a
POSIX path that behaves exactly like ``fcntl`` would and a Windows path built
on ``msvcrt.locking``.

Locking a single byte at offset 0 is enough: these are advisory locks between
our own processes, not a general file-range API.
"""

import sys

sys.dont_write_bytecode = True

import contextlib
import subprocess
import time

# Windows LK_LOCK gives up after roughly 10 seconds. A blocking waiter retries
# until this ceiling so a wedged peer cannot hang a hook forever. TimeoutError
# subclasses OSError, so the engine's existing handlers already catch it.
BLOCKING_TIMEOUT_SECONDS = 600.0
_RETRY_SECONDS = 0.5

if sys.platform == "win32":  # pragma: no cover - platform branch
    import msvcrt

    def _try_acquire(handle, blocking):
        mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), mode, 1)
            return True
        except OSError:
            return False

    def _release(handle):
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass

    def detached_kwargs():
        flags = subprocess.CREATE_NEW_PROCESS_GROUP
        flags |= getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        return {"creationflags": flags}

else:
    import fcntl

    def _try_acquire(handle, blocking):
        flags = fcntl.LOCK_EX if blocking else fcntl.LOCK_EX | fcntl.LOCK_NB
        try:
            fcntl.flock(handle.fileno(), flags)
            return True
        except OSError:
            return False

    def _release(handle):
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass

    def detached_kwargs():
        return {"start_new_session": True}


def acquire(handle, blocking=True):
    """Take an exclusive advisory lock. Returns False only when non-blocking."""
    if _try_acquire(handle, blocking):
        return True
    if not blocking:
        return False
    deadline = time.monotonic() + BLOCKING_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        time.sleep(_RETRY_SECONDS)
        if _try_acquire(handle, blocking):
            return True
    raise TimeoutError("lock-wait-timeout")


@contextlib.contextmanager
def exclusive(handle, blocking=True):
    """Context manager wrapper around :func:`acquire`."""
    held = acquire(handle, blocking)
    try:
        yield held
    finally:
        if held:
            _release(handle)
