"""Snapshot integrity: the archived result CSVs match the committed SHA-256
manifest.  This enforces the repo's standing rule that snapshots are
append-only: new results get NEW dated files; existing files never change.
A failing test means a cited number's source was edited after archiving.
Added post-defense (July 2026) as reproducibility hardening.
"""
from pathlib import Path
import hashlib

SNAP = Path(__file__).resolve().parents[1] / "docs" / "results_snapshots"


def test_snapshots_match_manifest():
    manifest = SNAP / "MANIFEST.sha256"
    assert manifest.exists(), (
        "MANIFEST.sha256 missing: run python -m scripts.make_provenance_manifest"
    )
    expected = {}
    for line in manifest.read_text().strip().splitlines():
        digest, name = line.split("  ", 1)
        expected[name] = digest
    actual = {
        p.name: hashlib.sha256(p.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        for p in SNAP.glob("*.csv")
    }
    assert actual == expected, {
        "changed_or_new": sorted(k for k in actual if expected.get(k) != actual[k]),
        "missing": sorted(k for k in expected if k not in actual),
    }
