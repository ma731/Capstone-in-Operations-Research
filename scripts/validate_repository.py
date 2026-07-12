"""Validate repository-level claims and artifact wiring without licensed data.

This complements the numerical pytest suite. It checks the failure modes that unit
tests do not cover: broken public-document links, missing canonical artifacts,
headline numbers drifting from archived snapshots, and accidental document-date
changes.

Run: python -m scripts.validate_repository
"""
from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_DATE = "June 2026"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"repository validation failed: {message}")


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _check_required_files() -> None:
    required = (
        "LICENSE",
        "constraints-numerics.txt",
        "uv.lock",
        "LICENSES/MIT-CODE.txt",
        "thesis/capstone_thesis.pdf",
        "full_thesis/full_thesis.pdf",
        "poster/build_v24.js",
        "poster/poster_capstone_v24.pdf",
        "poster/poster_capstone_v24.pptx",
        "deck/capstone_defense.pptx",
        "docs/results_snapshots/part3_transfer_value_2026-06-15.csv",
        "docs/results_snapshots/carbon_ceiling_2026-06-24.csv",
    )
    missing = [path for path in required if not (ROOT / path).is_file()]
    _require(not missing, f"missing required files: {', '.join(missing)}")


def _check_public_links() -> None:
    readme = _read("README.md")
    markdown_targets = re.findall(r"(?<!!)\[[^]]+\]\(([^)#]+)", readme)
    missing_links = [
        target
        for target in markdown_targets
        if not re.match(r"https?://", target) and not (ROOT / target).exists()
    ]
    _require(not missing_links, f"broken README links: {', '.join(missing_links)}")

    explainer = _read("capstone_explained.html")
    image_targets = re.findall(r'<img\s+[^>]*src="([^"]+)"', explainer)
    missing_images = [
        target
        for target in image_targets
        if not re.match(r"(?:https?:|data:)", target) and not (ROOT / target).is_file()
    ]
    _require(not missing_images, f"broken explainer images: {', '.join(missing_images)}")


def _check_headline_snapshots() -> None:
    transfer_path = ROOT / "docs/results_snapshots/part3_transfer_value_2026-06-15.csv"
    with transfer_path.open(newline="", encoding="utf-8") as handle:
        transfer = {row["grid"]: float(row["reduction_pct"]) for row in csv.DictReader(handle)}
    expected_transfer = {"us_west": 4.04, "taskc": 9.91, "us_hetero": 9.04}
    observed_transfer = {key: round(transfer[key], 2) for key in expected_transfer}
    _require(observed_transfer == expected_transfer, "RQ1 headline values drifted")

    severity_path = ROOT / "docs/results_snapshots/carbon_ceiling_2026-06-24.csv"
    with severity_path.open(newline="", encoding="utf-8") as handle:
        severity = {
            row["key"]: float(row["severity"])
            for row in csv.DictReader(handle)
            if row["kind"] == "joint"
        }
    expected_severity = {"us_west": 1.34, "taskc": 1.29, "us_hetero": 1.89}
    observed_severity = {key: round(severity[key], 2) for key in expected_severity}
    _require(observed_severity == expected_severity, "RQ3 joint-severity values drifted")

    readme = _read("README.md")
    _require(
        "Western 4.04%, Eastern 9.91%, Diversified 9.04%" in readme,
        "README RQ1 headline does not match its snapshot",
    )
    _require(
        "joint grids $M=1.29$--$1.89$" in readme,
        "README RQ3 severity range does not match its snapshot",
    )


def _check_document_dates() -> None:
    date_markers = {
        "thesis/capstone_thesis.tex": r"{\large June 2026\par}",
        "full_thesis/full_thesis.tex": r"{\large June 2026\par}",
        "thesis/paper_twocolumn.tex": r"\date{June 2026}",
    }
    for path, marker in date_markers.items():
        _require(marker in _read(path), f"{path} document date is not {DOCUMENT_DATE}")


def _check_tex_assets_and_public_privacy() -> None:
    """Require clean-clone TeX assets and keep the public copy unsigned."""
    missing: list[str] = []
    tex_files = list((ROOT / "thesis").glob("*.tex")) + list(
        (ROOT / "full_thesis").glob("*.tex")
    )
    for tex_path in tex_files:
        source = tex_path.read_text(encoding="utf-8")
        for target in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", source):
            candidate = tex_path.parent / target
            if candidate.suffix:
                exists = candidate.is_file()
            else:
                exists = any(candidate.with_suffix(ext).is_file() for ext in (".pdf", ".png", ".jpg"))
            if not exists:
                missing.append(f"{tex_path.relative_to(ROOT)} -> {target}")
    _require(not missing, f"missing TeX graphics: {', '.join(missing)}")

    _require(not (ROOT / "thesis/signature.png").exists(), "public handwritten signature is present")
    thesis = _read("thesis/capstone_thesis.tex")
    _require(
        "Signature withheld from public copy" in thesis,
        "public thesis does not contain the signature-withheld notice",
    )


def _check_project_metadata() -> None:
    with (ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]
    dependencies = {item.split(">=", 1)[0] for item in project["dependencies"]}
    required_solvers = {"cvxpy", "clarabel", "scs", "highspy"}
    _require(required_solvers <= dependencies, "a documented default solver is undeclared")

    canonical = (
        "poster/build_v24.js",
        "poster/poster_capstone_v24.pdf",
        "poster/poster_capstone_v24.pptx",
    )
    ignored = []
    for path in canonical:
        result = subprocess.run(
            ["git", "check-ignore", "-q", path], cwd=ROOT, check=False
        )
        if result.returncode == 0:
            ignored.append(path)
    _require(not ignored, f"canonical poster files are ignored: {', '.join(ignored)}")


def main() -> None:
    _check_required_files()
    _check_public_links()
    _check_headline_snapshots()
    _check_document_dates()
    _check_tex_assets_and_public_privacy()
    _check_project_metadata()
    print("repository validation passed")


if __name__ == "__main__":
    main()
