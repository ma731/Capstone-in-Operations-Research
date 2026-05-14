# carbon-dro-capstone

Spatially-correlated DRO scheduling for carbon-aware data centers.

**Capstone project · IE School of Science & Technology · 2026**
**Supervisor:** Prof. Bissan Ghaddar
**Student:** Marco Ortiz Togashi

## What this is

We extend Hall et al. (2024)'s distributionally robust optimization framework for carbon-aware data center scheduling by treating carbon intensity as a stochastic vector across multiple co-regional clusters (e.g., CAISO sub-regions), capturing spatial correlation that the existing literature ignores.

**Two phases:**

- **Phase 1 (capstone, ends June 2026):** Empirical correlation analysis on real ISO data + Algorithm 2 implementation + sensitivity analysis. Deliverable: capstone report.
- **Phase 2 (publication, ends August 2026):** Methodological extension via vine copulas + paper submission to HotCarbon or e-Energy.

See `docs/algorithm-spec.pdf` for the formal specification.

## Project structure

```
carbon-dro-capstone/
├── README.md
├── pyproject.toml          # dependencies, project metadata
├── .gitignore
├── .env.example            # template for API keys (real .env is gitignored)
├── data/
│   ├── raw/                # downloaded ISO / Electricity Maps data (gitignored)
│   └── processed/          # cleaned parquet files
├── src/
│   ├── data/               # ingestion: CAISO, Electricity Maps, Google traces
│   ├── models/             # Algorithm 1, 2, 3 implementations
│   └── analysis/           # correlation studies, sensitivity analyses
├── notebooks/              # exploratory Jupyter notebooks
├── tests/                  # pytest unit + sanity tests
├── scripts/                # one-off CLI scripts (e.g., bulk data pulls)
└── docs/
    ├── proposal.pdf
    ├── algorithm-spec.pdf
    ├── decisions.md        # log of every meaningful design decision
    └── meeting_notes/
```

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/carbon-dro-capstone.git
cd carbon-dro-capstone

# Using uv (recommended)
uv venv
source .venv/bin/activate          # macOS/Linux
# .venv\Scripts\activate           # Windows
uv pip install -e ".[dev]"

# Alternative: regular venv + pip
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### 2. Configure API keys

```bash
cp .env.example .env
# Edit .env and fill in your tokens:
#   ELECTRICITY_MAPS_TOKEN=...
#   GUROBI_LICENSE_FILE=...  (path to gurobi.lic)
```

### 3. Verify the setup

```bash
pytest tests/                       # should pass
python -m src.models.algorithm_1    # solves a synthetic problem
```

## Workflow conventions

- **Branches:** work on feature branches (`feat/caiso-ingestion`, `fix/timezone-alignment`), open PRs to `main`.
- **Commits:** present-tense imperative ("add CAISO parser", not "added").
- **Notebooks:** explore in `notebooks/`, promote stable logic to `src/`.
- **Data:** never commit raw data. Keep it in `data/raw/` (gitignored). Processed data goes to `data/processed/` and *can* be committed if small.
- **Decisions:** log meaningful choices in `docs/decisions.md`. Date, decision, alternatives considered, reason.

## Phase 1 milestones

- [ ] Week 1: repo + Algorithm 1 + first CAISO data pull
- [ ] Week 2: full data pipeline, 2 years of CAISO across 3 sub-regions
- [ ] Week 3: empirical correlation analysis; **decision gate**
- [ ] Week 4: Algorithm 2 multi-cluster deterministic
- [ ] Week 5–6: Algorithm 2 DRO layer; validate against Hall et al.
- [ ] Week 7–8: sensitivity analysis; capstone report

## References

- Hall et al. 2024 — [arXiv:2410.21510](https://arxiv.org/abs/2410.21510)
- Radovanović et al. 2022 — IEEE TPS 38(2), 1270–1280
- Yang et al. 2025 — [arXiv:2510.04053](https://arxiv.org/abs/2510.04053)
- Li, Liu, Ding 2024 — HotCarbon '24
- Esfahani & Kuhn 2018 — *Mathematical Programming* 171, 115–166

## License

Not yet licensed. Decide with Bissan before any external publication.
