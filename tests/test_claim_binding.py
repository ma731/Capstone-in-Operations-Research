"""Claim-binding tests: the code certifies the thesis's theoretical claims.

Most of the suite checks implementation correctness. This file is different: each
test pins a statement the *thesis* makes, so the central arguments are not just
proved on paper but enforced in continuous integration.

  1. Shuffle preserves validity  -- Sigma_shuf is still a covariance (PSD), so the
     falsification arm compares two legitimate models (Sec. methodology).
  2. CVaR translation-invariance  -- the algebraic backbone of Proposition 1: the
     mean field passes through additively (Sec. mechanism).
  3. The mean-dominance bound holds -- |OPT(Sigma) - OPT(Sigma_shuf)| is bounded by
     eps * max||x|| * sqrt(||Sigma_off||) on a solved toy (Proposition 1).
  4. Mean-dominance is monotone   -- because the Proposition-1 bound is independent
     of the mean field, scaling the mean up drowns the fixed covariance term: the
     relative spatial gap shrinks monotonically toward zero (the mechanism).
"""
from __future__ import annotations

import numpy as np
import pytest

from src.analysis.metrics import cvar_upper_tail
from src.models.covariance import block_diagonal_by_region
from src.models.algorithm_2b_mahalanobis import solve_mahalanobis_dro

REGION_ORDER = ("REG_A", "REG_B")


def _toy_sigma(cross_val: float, R: int = 2, T: int = 3) -> np.ndarray:
    """R*T covariance: 100*I within-region, cross_val*I_T on the cross blocks.

    Stays positive-definite for |cross_val| < 100 (eigenvalues 100 +/- cross_val).
    """
    D = R * T
    Sig = 100.0 * np.eye(D)
    c = cross_val * np.eye(T)
    Sig[0:T, T:2 * T] = c
    Sig[T:2 * T, 0:T] = c
    return Sig


# ---------------------------------------------------------------------------
# 1. The shuffle yields a *valid* covariance (PSD). "Is Sigma_shuf legitimate?"
# ---------------------------------------------------------------------------
class TestShufflePreservesValidity:
    def test_shuffle_preserves_psd(self):
        """A block-diagonal of the diagonal blocks of a PSD matrix is PSD: each
        block is a principal submatrix (hence PSD) and a block-diagonal of PSD
        blocks is PSD. So zeroing the cross blocks keeps a valid covariance."""
        rng = np.random.default_rng(7)
        R, T = 4, 24
        D = R * T
        A = rng.normal(size=(D, D))
        cov = A @ A.T  # PSD (possibly singular)
        shuf = block_diagonal_by_region(cov, R=R, T=T)
        min_eig = float(np.linalg.eigvalsh((shuf + shuf.T) / 2).min())
        assert min_eig >= -1e-8, f"shuffled matrix not PSD: min eig {min_eig}"

    def test_shuffle_preserves_positive_definite_and_is_factorizable(self):
        """If the joint matrix is PD, the shuffled one is PD too, so the DRO can
        Cholesky-factor it exactly the same way -- the shuffled arm is solvable."""
        rng = np.random.default_rng(8)
        R, T = 3, 8
        D = R * T
        cov = rng.normal(size=(D, D))
        cov = cov @ cov.T + np.eye(D)  # PD
        shuf = block_diagonal_by_region(cov, R=R, T=T)
        assert float(np.linalg.eigvalsh(shuf).min()) > 0.0
        np.linalg.cholesky(shuf)  # must not raise


# ---------------------------------------------------------------------------
# 2. CVaR translation-invariance: the backbone of Proposition 1.
# ---------------------------------------------------------------------------
class TestCVaRTranslationInvariance:
    def test_translation_invariance(self):
        """CVaR(e + c) == CVaR(e) + c. A constant shift (the mean field) passes
        straight through the risk measure -- it cannot interact with dependence."""
        rng = np.random.default_rng(0)
        for _ in range(25):
            e = rng.normal(50.0, 12.0, size=200)
            c = float(rng.normal() * 25.0)
            np.testing.assert_allclose(
                cvar_upper_tail(e + c), cvar_upper_tail(e) + c, rtol=1e-12, atol=1e-9
            )

    def test_positive_homogeneity(self):
        """CVaR(a*e) == a*CVaR(e) for a > 0 (coherent-risk positive homogeneity)."""
        rng = np.random.default_rng(1)
        for a in (0.5, 2.0, 7.3):
            e = rng.normal(100.0, 25.0, size=300)
            np.testing.assert_allclose(
                cvar_upper_tail(a * e), a * cvar_upper_tail(e), rtol=1e-12, atol=1e-9
            )


# ---------------------------------------------------------------------------
# 3. Proposition 1 (the mean-dominance bound) holds on a solved instance.
# ---------------------------------------------------------------------------
class TestPropositionOneBound:
    def test_per_x_penalty_lemma(self):
        """For every feasible x: |eps*||L_J^T x|| - eps*||L_S^T x|||
        <= eps*||x||*sqrt(||Sigma_off||). The fast, solver-free lemma the bound
        rests on (sqrt-subadditivity of the Mahalanobis penalty)."""
        R, T = 2, 3
        Sig = _toy_sigma(40.0, R, T)
        shuf = block_diagonal_by_region(Sig, R=R, T=T)
        L_j, L_s = np.linalg.cholesky(Sig), np.linalg.cholesky(shuf)
        Sig_off = Sig - shuf
        off_norm = float(np.linalg.norm(Sig_off, 2))
        eps = 150.0
        ceiling = np.full((R, T), 50.0)
        rng = np.random.default_rng(3)
        for _ in range(50):
            x = rng.uniform(0.0, ceiling).reshape(-1)
            pen_j = eps * float(np.linalg.norm(L_j.T @ x))
            pen_s = eps * float(np.linalg.norm(L_s.T @ x))
            rhs = eps * float(np.linalg.norm(x)) * np.sqrt(off_norm)
            assert abs(pen_j - pen_s) <= rhs + 1e-7

    def test_solved_optimal_value_gap_within_bound(self):
        """|OPT(Sigma) - OPT(Sigma_shuf)| <= eps * max||x|| * sqrt(||Sigma_off||),
        with max||x|| bounded by the box ceiling. Proposition 1, on a real solve."""
        R, T = 2, 3
        Sig = _toy_sigma(40.0, R, T)
        shuf = block_diagonal_by_region(Sig, R=R, T=T)
        L_j, L_s = np.linalg.cholesky(Sig), np.linalg.cholesky(shuf)
        rho_bar = np.array([[100.0, 200.0, 300.0], [300.0, 200.0, 100.0]])
        workloads = np.array([30.0, 30.0])
        ceiling = np.full((R, T), 50.0)
        eps = 150.0
        kw = dict(rho_bar=rho_bar, workloads=workloads, ceiling=ceiling,
                  epsilon=eps, region_order=REGION_ORDER)
        opt_j = solve_mahalanobis_dro(L=L_j, **kw).objective_value
        opt_s = solve_mahalanobis_dro(L=L_s, **kw).objective_value
        gap = abs(opt_j - opt_s)
        off_norm = float(np.linalg.norm(Sig - shuf, 2))
        bound = eps * float(np.linalg.norm(ceiling.reshape(-1))) * np.sqrt(off_norm)
        assert gap <= bound + 1e-6, f"gap {gap:.4f} exceeds bound {bound:.4f}"


# ---------------------------------------------------------------------------
# 4. Mean-dominance, as a property: flatten the mean -> the gap widens.
# ---------------------------------------------------------------------------
class TestMeanDominanceMonotonicity:
    def test_growing_mean_field_shrinks_relative_spatial_gap(self):
        """The Proposition-1 bound eps*max||x||*sqrt(||Sigma_off||) is independent
        of the mean field. So as the mean grows, it drowns the fixed covariance
        term: the relative spatial gap |OPT_joint - OPT_shuf| / |OPT| must shrink
        monotonically toward zero. That decay *is* the mean-dominance mechanism."""
        R, T = 2, 3
        Sig = _toy_sigma(-50.0, R, T)  # strong cross-block so the gap starts large
        L_j = np.linalg.cholesky(Sig)
        L_s = np.linalg.cholesky(block_diagonal_by_region(Sig, R=R, T=T))
        rho_bar = np.array([[100.0, 200.0, 300.0], [300.0, 200.0, 100.0]])
        workloads = np.array([30.0, 30.0])
        ceiling = np.full((R, T), 50.0)
        eps = 200.0

        rel_gaps = []
        for k in (1.0, 2.0, 4.0, 8.0, 16.0):
            kw = dict(rho_bar=k * rho_bar, workloads=workloads, ceiling=ceiling,
                      epsilon=eps, region_order=REGION_ORDER)
            opt_j = solve_mahalanobis_dro(L=L_j, **kw).objective_value
            opt_s = solve_mahalanobis_dro(L=L_s, **kw).objective_value
            rel_gaps.append(abs(opt_j - opt_s) / abs(opt_j))

        # monotone non-increasing: a larger mean field can only shrink the gap
        for prev, nxt in zip(rel_gaps, rel_gaps[1:]):
            assert nxt <= prev + 1e-4, f"relative gap not monotone: {rel_gaps}"
        # and the mechanism is real: the covariance is drowned out at large scale
        assert rel_gaps[-1] < 0.05 * rel_gaps[0] + 1e-6, (
            f"mean did not dominate: {rel_gaps}"
        )
