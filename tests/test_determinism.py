"""Seed determinism: stochastic components regenerate bit-identical output
under a fixed seed.  This is the property that makes the snapshot CSVs
regenerable-in-principle: same code + same data + same seed = same numbers.
Covers the numpy-only copula samplers (no licensed data needed).
Added post-defense (July 2026) as reproducibility hardening.
"""
import numpy as np

from src.analysis.metrics import cvar_upper_tail
from src.models.copula_scenarios import CopulaModel, sample_uniforms

R, N_DAYS, T = 3, 30, 24


def _toy_model(kind: str, theta: float | None = None) -> CopulaModel:
    rng = np.random.default_rng(0)
    profiles = rng.random((R, N_DAYS, T))
    rank_map = np.tile(np.arange(N_DAYS), (R, 1))
    chol = np.linalg.cholesky(0.5 * np.eye(R) + 0.5 * np.ones((R, R))) if kind == "gaussian" else None
    return CopulaModel(
        kind=kind,
        region_profiles=profiles,
        summary_rank_to_day=rank_map,
        gaussian_chol=chol,
        clayton_theta=theta,
        kendall_tau=0.3,
    )


def test_cvar_is_a_pure_function():
    x = np.linspace(-3.0, 5.0, 400)
    assert cvar_upper_tail(x, 0.95) == cvar_upper_tail(x.copy(), 0.95)


def test_samplers_seed_determinism():
    for kind, theta in [("independence", None), ("comonotone", None), ("clayton", 1.5)]:
        model = _toy_model(kind, theta)
        a = sample_uniforms(model, S=256, rng=np.random.default_rng(20260712))
        b = sample_uniforms(model, S=256, rng=np.random.default_rng(20260712))
        assert np.array_equal(a, b), f"{kind}: same seed must reproduce identical draws"


def test_samplers_seed_sensitivity():
    model = _toy_model("clayton", 1.5)
    a = sample_uniforms(model, S=256, rng=np.random.default_rng(1))
    b = sample_uniforms(model, S=256, rng=np.random.default_rng(2))
    assert not np.array_equal(a, b), "different seeds must differ"
