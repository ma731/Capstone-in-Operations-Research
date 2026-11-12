"""Pre-compute the console's answers and pre-render its voice, so the demo runs offline.

    python -m agentic.warm_cache            # run the night before (needs internet once)
    python -m agentic.warm_cache --check    # exit 1 if a Present or meta line has no audio

Everything lands in agentic/.cache/, which is gitignored: it is derived from licensed data.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

from . import console, voice


def _speeches(x, out: list[str]) -> None:
    if isinstance(x, dict):
        if isinstance(x.get("tts"), str) and "caption" in x:
            out.append(x["tts"])
            return
        for v in x.values():
            _speeches(v, out)
    elif isinstance(x, list):
        for v in x:
            _speeches(v, out)


def required_lines() -> list[str]:
    """Lines that must play offline: the Present script and the fixed meta lines."""
    out: list[str] = []
    _speeches(console.present()["steps"], out)
    _speeches(console.lines(), out)
    return list(dict.fromkeys(out))


def _step(name: str, fn, results: list) -> None:
    t0 = time.perf_counter()
    try:
        results.append(fn())
        print(f"  ok    {name} ({time.perf_counter() - t0:.1f}s)", flush=True)
    except console.ApiError as e:
        print(f"  skip  {name}: {e.code}", flush=True)
    except Exception as e:
        print(f"  FAIL  {name}: {type(e).__name__}: {e}".encode("ascii", "replace").decode(), flush=True)


def warm() -> int:
    has = console.data_available()
    print(f"data available: {has}", flush=True)
    results: list = [console.meta(), console.findings(), console.graph(), console.interfaces()]
    if has:
        for j in console._jobs():
            _step(f"plan {j['job']}", lambda j=j: console.plan(j["job"], console.DEFAULT["day"], 0.3), results)
        _step("sweep llm_training", lambda: console.sweep("llm_training", console.DEFAULT["day"]), results)
        _step("drift all", lambda: console.drift("all"), results)
        _step("evals", console.evals, results)
    for q in console.SUGGESTIONS + [console.PRESENT_QUERY, "What about July 4th?"]:
        ctx = {"job": "llm_training", "day": console.DEFAULT["day"]}
        _step(f"ask {q!r}", lambda q=q, ctx=ctx: console.ask(q, ctx), results)
    _step("present", console.present, results)
    # the no-data tour too, so GRIDSHIFT_NO_DATA=1 still speaks with the neural voice
    old = os.environ.get("GRIDSHIFT_NO_DATA")
    os.environ["GRIDSHIFT_NO_DATA"] = "1"
    try:
        _step("present (no data)", console.present, results)
    finally:
        if old is None:
            os.environ.pop("GRIDSHIFT_NO_DATA", None)
        else:
            os.environ["GRIDSHIFT_NO_DATA"] = old
    for d in ("approve", "reject"):
        results.append({"speech": console.speech(console.DECISION_LINES[d])})

    texts: list[str] = []
    _speeches(results, texts)
    texts = list(dict.fromkeys(required_lines() + texts))
    print(f"speaking {len(texts)} lines (voice {voice.voice()}, engine {voice.engine_name()})", flush=True)
    made = hits = fails = 0
    for t in texts:
        if voice.is_cached(t):
            hits += 1
            continue
        try:
            voice.synthesize(t)
            made += 1
        except voice.TTSUnavailable as e:
            fails += 1
            print(f"  no audio: {e}: {t[:60]}".encode("ascii", "replace").decode(), flush=True)
    print(f"voice: {hits} already cached, {made} rendered, {fails} failed; {voice.cached_count()} mp3 on disk",
          flush=True)
    return 0 if fails == 0 else 1


def check() -> int:
    missing = [t for t in required_lines() if not voice.is_cached(t)]
    total = len(required_lines())
    print(f"{total - len(missing)} of {total} Present and meta lines cached")
    for t in missing:
        print("  missing: " + t[:80].encode("ascii", "replace").decode())
    return 1 if missing else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Warm the Gridshift caches (answers and voice).")
    ap.add_argument("--check", action="store_true", help="only check that every Present and meta line is cached")
    a = ap.parse_args(argv)
    return check() if a.check else warm()


if __name__ == "__main__":
    sys.exit(main())
