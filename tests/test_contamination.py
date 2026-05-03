"""Tests for ``idc_simulation.contamination``.

Hand-computed boundary cases and vectorisation properties.
"""

from __future__ import annotations

import numpy as np
import pytest

from idc_simulation.contamination import (
    REGIMES,
    REGIME_CORRECTED,
    REGIME_UNCORRECTED,
    contamination,
    contamination_dual_regime,
    geometric_sum_factor,
)


# ---------------------------------------------------------------------------
# Closed-form boundary cases (hand-computed reference values)
# ---------------------------------------------------------------------------


def test_n_zero_returns_E0_times_epsilon() -> None:
    # At n=0: G(P, 0) = (1 - P) / (1 - P) = 1, decay = (1-R)^0 = 1.
    # So Contamination(0) = E0 * epsilon for any P, R.
    val = contamination(E0=0.025, epsilon=0.30, P=0.5, R=0.02, n=0)
    assert val == pytest.approx(0.025 * 0.30)


def test_R_zero_no_decay() -> None:
    # With R=0 the decay factor is 1.
    # Contamination(n) = E0 * epsilon * (1 - P^(n+1)) / (1 - P)
    val = contamination(E0=0.05, epsilon=0.5, P=0.5, R=0.0, n=3)
    expected = 0.05 * 0.5 * (1 - 0.5**4) / (1 - 0.5)
    assert val == pytest.approx(expected)


def test_P_zero_geometric_factor_is_one() -> None:
    # With P=0: (1 - 0^(n+1)) / (1 - 0) = 1.
    val = contamination(E0=0.025, epsilon=0.3, P=0.0, R=0.02, n=10)
    expected = 0.025 * 0.3 * 1.0 * (1 - 0.02) ** 10
    assert val == pytest.approx(expected)


def test_P_near_one_uses_lhopital_limit() -> None:
    # With P -> 1, G(P, n) -> n + 1. We test the analytic branch by
    # passing P exactly 1.0.
    g = geometric_sum_factor(1.0, 5)
    assert g == pytest.approx(6.0)

    # And verify continuity: G(1 - 1e-8, 5) is close to 6.
    g_near = geometric_sum_factor(1.0 - 1e-8, 5)
    assert g_near == pytest.approx(6.0, abs=1e-3)


def test_full_function_against_manual_calculation() -> None:
    # Pick a non-trivial set of parameters and compute by hand.
    E0, eps, P, R, n = 0.03, 0.4, 0.6, 0.02, 5
    geom = (1 - P ** (n + 1)) / (1 - P)
    decay = (1 - R) ** n
    expected = E0 * eps * geom * decay
    val = contamination(E0=E0, epsilon=eps, P=P, R=R, n=n)
    assert val == pytest.approx(expected)


def test_negative_n_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        contamination(E0=0.025, epsilon=0.3, P=0.5, R=0.02, n=-1)


# ---------------------------------------------------------------------------
# Vectorisation
# ---------------------------------------------------------------------------


def test_vectorised_over_K_samples_returns_K_array() -> None:
    K = 1000
    rng = np.random.default_rng(0)
    E0 = rng.beta(12.5, 487.5, size=K)
    eps = rng.beta(9.0, 21.0, size=K)
    P = rng.beta(10.0, 10.0, size=K)
    R = rng.beta(2.0, 98.0, size=K)
    out = contamination(E0=E0, epsilon=eps, P=P, R=R, n=10)
    assert out.shape == (K,)
    assert np.all(np.isfinite(out))
    assert np.all(out >= 0.0)


def test_broadcast_over_horizons() -> None:
    # If parameters are length K and n is shape (H,), broadcasting via
    # explicit reshape gives shape (K, H).
    K, H = 100, 4
    rng = np.random.default_rng(1)
    E0 = rng.beta(12.5, 487.5, size=K)[:, None]
    eps = rng.beta(9.0, 21.0, size=K)[:, None]
    P = rng.beta(10.0, 10.0, size=K)[:, None]
    R = rng.beta(2.0, 98.0, size=K)[:, None]
    horizons = np.array([[1, 5, 10, 20]])
    out = contamination(E0=E0, epsilon=eps, P=P, R=R, n=horizons)
    assert out.shape == (K, H)
    assert np.all(np.isfinite(out))


def test_contamination_in_unit_interval_for_typical_priors() -> None:
    # The function returns a probability-like quantity that should not
    # exceed 1 under any combination of physically valid parameters in
    # the prior support. We test only with moderate-prior random draws.
    K = 5000
    rng = np.random.default_rng(2)
    out = contamination(
        E0=rng.beta(12.5, 487.5, size=K),
        epsilon=rng.beta(9.0, 21.0, size=K),
        P=rng.beta(10.0, 10.0, size=K),
        R=rng.beta(2.0, 98.0, size=K),
        n=10,
    )
    assert np.all(out >= 0.0)
    # Loose upper bound: function is bounded by E0 * epsilon * (n+1) when
    # P -> 1 and R = 0, which for moderate priors gives <<< 1.
    assert np.all(out < 1.0)


def test_geometric_sum_at_n_zero_is_one_for_any_P() -> None:
    Ps = np.array([0.0, 0.1, 0.5, 0.9, 0.999])
    g = geometric_sum_factor(Ps, 0)
    np.testing.assert_allclose(g, 1.0, atol=1e-12)


# ---------------------------------------------------------------------------
# v2.0 dual-regime helper
# ---------------------------------------------------------------------------


def test_regime_constants_have_expected_names() -> None:
    assert REGIME_UNCORRECTED == "uncorrected"
    assert REGIME_CORRECTED == "corrected"
    assert REGIMES == ("uncorrected", "corrected")


def test_dual_regime_uncorrected_matches_R_zero() -> None:
    K = 1000
    rng = np.random.default_rng(0)
    E0 = rng.beta(12.5, 487.5, size=K)
    eps = rng.beta(9.0, 21.0, size=K)
    P = rng.beta(10.0, 10.0, size=K)
    R = rng.beta(2.0, 98.0, size=K)
    uncorr, _ = contamination_dual_regime(E0, eps, P, R, n=10)
    expected = contamination(E0=E0, epsilon=eps, P=P, R=0.0, n=10)
    np.testing.assert_allclose(uncorr, expected, rtol=0, atol=1e-15)


def test_dual_regime_corrected_matches_full_formula() -> None:
    K = 1000
    rng = np.random.default_rng(1)
    E0 = rng.beta(12.5, 487.5, size=K)
    eps = rng.beta(9.0, 21.0, size=K)
    P = rng.beta(10.0, 10.0, size=K)
    R = rng.beta(2.0, 98.0, size=K)
    _, corr = contamination_dual_regime(E0, eps, P, R, n=10)
    expected = contamination(E0=E0, epsilon=eps, P=P, R=R, n=10)
    np.testing.assert_allclose(corr, expected, rtol=0, atol=1e-15)


def test_dual_regime_corrected_le_uncorrected_pointwise() -> None:
    K = 5000
    rng = np.random.default_rng(2)
    E0 = rng.beta(12.5, 487.5, size=K)
    eps = rng.beta(9.0, 21.0, size=K)
    P = rng.beta(10.0, 10.0, size=K)
    R = rng.beta(2.0, 98.0, size=K)
    for n in (1, 5, 10, 20):
        uncorr, corr = contamination_dual_regime(E0, eps, P, R, n=n)
        assert (corr <= uncorr + 1e-15).all(), (
            f"corrected exceeded uncorrected at n={n}"
        )


def test_dual_regime_equal_at_R_zero() -> None:
    K = 500
    rng = np.random.default_rng(3)
    E0 = rng.beta(12.5, 487.5, size=K)
    eps = rng.beta(9.0, 21.0, size=K)
    P = rng.beta(10.0, 10.0, size=K)
    R_zero = np.zeros(K)
    uncorr, corr = contamination_dual_regime(E0, eps, P, R_zero, n=15)
    np.testing.assert_allclose(uncorr, corr, rtol=0, atol=1e-15)


def test_dual_regime_negative_n_raises() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        contamination_dual_regime(
            E0=0.025, epsilon=0.3, P=0.5, R=0.02, n=-1
        )
