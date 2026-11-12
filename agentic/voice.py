"""Neural voice for the Gridshift console: edge-tts with an on-disk mp3 cache.

edge-tts is not a project dependency. It usually lives in the system Python, so the
engine is found once (in process, then GRIDSHIFT_TTS_PYTHON, then the py launcher) and
called as a subprocess. Cached lines play offline.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import threading
import uuid
from pathlib import Path

CACHE = Path(__file__).with_name(".cache") / "voice"
RATE = "-6%"
PITCH = "-2Hz"
TIMEOUT_S = 15
PROBE_TIMEOUT_S = 6
MAX_CHARS = 1200

_UNSET = object()
_engine = _UNSET
_engine_lock = threading.Lock()
_key_locks: dict[str, threading.Lock] = {}
_key_locks_lock = threading.Lock()
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class TTSUnavailable(RuntimeError):  # noqa: N818 (name from the spec)
    pass


def voice() -> str:
    return os.environ.get("GRIDSHIFT_VOICE", "en-US-AvaNeural")


def disabled() -> bool:
    return os.environ.get("GRIDSHIFT_TTS", "").strip().lower() == "off"


def _probe(cmd: list[str]) -> bool:
    try:
        r = subprocess.run([*cmd, "-c", "import edge_tts"], capture_output=True, timeout=PROBE_TIMEOUT_S,
                           creationflags=_NO_WINDOW)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _discover():
    try:
        import edge_tts  # noqa: F401
        return "inproc"
    except ImportError:
        pass
    candidates = []
    if os.environ.get("GRIDSHIFT_TTS_PYTHON"):
        candidates.append([os.environ["GRIDSHIFT_TTS_PYTHON"]])
    candidates += [["py", "-3.14"], ["py", "-3"], [r"C:\Python314\python.exe"]]
    for cmd in candidates:
        if _probe(cmd):
            return cmd
    return None


def engine():
    """"inproc", a python command list, or None. Found once and cached."""
    global _engine
    if disabled():
        return None
    with _engine_lock:
        if _engine is _UNSET:
            _engine = _discover()
        return _engine


def engine_name() -> str:
    return "edge-tts" if engine() else "none"


def cache_path(text: str) -> Path:
    key = hashlib.sha1(f"{voice()}|{RATE}|{PITCH}|{text}".encode()).hexdigest()[:16]
    return CACHE / f"{key}.mp3"


def is_cached(text: str) -> bool:
    return cache_path(text).is_file()


def cached_count() -> int:
    return len(list(CACHE.glob("*.mp3"))) if CACHE.is_dir() else 0


def _lock_for(key: str) -> threading.Lock:
    with _key_locks_lock:
        return _key_locks.setdefault(key, threading.Lock())


def _render(text: str, out: Path) -> None:
    eng = engine()
    if not eng:
        raise TTSUnavailable("edge-tts not found")
    if eng == "inproc":
        import asyncio

        import edge_tts

        async def go():
            await edge_tts.Communicate(text, voice(), rate=RATE, pitch=PITCH).save(str(out))
        asyncio.run(asyncio.wait_for(go(), TIMEOUT_S))
        return
    cmd = [*eng, "-m", "edge_tts", "--voice", voice(), f"--rate={RATE}", f"--pitch={PITCH}",
           "--text", text, "--write-media", str(out)]
    r = subprocess.run(cmd, capture_output=True, timeout=TIMEOUT_S, creationflags=_NO_WINDOW)
    if r.returncode != 0:
        raise TTSUnavailable("edge-tts failed (offline?)")


def synthesize(text: str) -> bytes:
    """mp3 bytes for one line, from the cache when possible. Raises TTSUnavailable."""
    path = cache_path(text)
    if path.is_file():
        return path.read_bytes()
    with _lock_for(path.name):
        if path.is_file():
            return path.read_bytes()
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.stem}.{uuid.uuid4().hex[:8]}.part")
        try:
            _render(text, tmp)
            if not tmp.is_file() or tmp.stat().st_size == 0:
                raise TTSUnavailable("edge-tts wrote nothing")
            os.replace(tmp, path)
        except TTSUnavailable:
            raise
        except Exception as e:  # timeouts, network, odd subprocess errors
            raise TTSUnavailable(f"edge-tts failed: {type(e).__name__}") from e
        finally:
            tmp.unlink(missing_ok=True)
    return path.read_bytes()
