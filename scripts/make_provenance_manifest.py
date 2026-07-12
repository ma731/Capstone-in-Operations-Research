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
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def build() -> str:
    lines = [f"{_digest(p)}  {p.name}" for p in sorted(SNAP_DIR.glob("*.csv"))]
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
        if MANIFEST.read_text() != current:
            cur = {n: d for d, n in (l.split("  ", 1) for l in current.strip().splitlines())}
            com = {n: d for d, n in (l.split("  ", 1) for l in MANIFEST.read_text().strip().splitlines())}
            for name in sorted(set(cur) | set(com)):
                if cur.get(name) != com.get(name):
                    a = (com.get(name) or "none")[:12]
                    b = (cur.get(name) or "none")[:12]
                    print(f"DRIFT: {name}: manifest={a} actual={b}")
            return 1
        print(f"OK: {len(current.strip().splitlines())} snapshots match the manifest.")
        return 0
    MANIFEST.write_text(current)
    print(f"Wrote {MANIFEST} ({len(current.strip().splitlines())} files).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
