"""Generate SHA-256 provenance manifest for the archived result snapshots.

Every number cited in the thesis, deck, or paper traces to a CSV in
docs/results_snapshots/.  This script freezes that directory state into a
manifest so any later edit (accidental or otherwise) is detectable:

    python -m scripts.make_provenance_manifest            # write manifest
    python -m scripts.make_provenance_manifest --check    # verify, exit 1 on drift

The companion test tests/test_snapshot_manifest.py runs the check in CI.
Added post-defense (July 2026) as reproducibility hardening for the journal
submission; it certifies integrity of the snapshots, whose content and dates
are unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

SNAP_DIR = Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"
MANIFEST = SNAP_DIR / "MANIFEST.sha256"


def _digest(path: Path) -> str:
    """SHA-256 over line-ending-normalized bytes (CRLF -> LF), so the digest is
    identical whether the file was checked out on Windows (autocrlf) or Unix."""
    h = hashlib.sha256()
    h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return h.hexdigest()


def build() -> str:
    # sort by name STRING: Path ordering is case-insensitive on Windows, so sorting
    # Path objects produces platform-dependent manifests. String sort is byte-order
    # everywhere.
    lines = [f"{_digest(p)}  {p.name}" for p in sorted(SNAP_DIR.glob("*.csv"), key=lambda q: q.name)]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify instead of write")
    args = ap.parse_args()
    current = build()
    if args.check:
        if not MANIFEST.exists():
            print("MANIFEST.sha256 missing; run without --check to create it.")
            return 1
        def _parse(text: str) -> dict:
            return {n: d for d, n in (l.split("  ", 1) for l in text.strip().splitlines())}
        if _parse(MANIFEST.read_text()) != _parse(current):
            cur_d, com_d = _parse(current), _parse(MANIFEST.read_text())
            for name in sorted(set(cur_d) | set(com_d)):
                if cur_d.get(name) != com_d.get(name):
                    a = (com_d.get(name) or "none")[:12]
                    b = (cur_d.get(name) or "none")[:12]
                    print(f"DRIFT: {name}: manifest={a} actual={b}")
            return 1
        print(f"OK: {len(current.strip().splitlines())} snapshots match the manifest.")
        return 0
    MANIFEST.write_text(current)
    print(f"Wrote {MANIFEST} ({len(current.strip().splitlines())} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
