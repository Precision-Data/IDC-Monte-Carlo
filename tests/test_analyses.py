"""Tests for ``idc_simulation.analyses``.

End-to-end checks against the canonical Parquet output, plus targeted
checks of each sensitivity scenario.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from idc_simulation.analyses import (
    HOSPITAL_DOCS_PER_YEAR,
    HOSPITAL_HORIZON,
    HOSPITAL_YEARS,
    MULTI_AGENT_P_KAPPA,
    MULTI_AGENT_P_MU,
    PROB_THRESHOLD,
    analyse_canonical,
    hospital_scale,
    load_severity_weighting,
    robustness_ratio,
    sensitivity_R_zero,
    sensitivity_copula,
    sensitivity_multi_agent_P,
    summarise_primary,
)
from idc_simulation.priors import load_all_prior_sets
from idc_simulation.simulation import (
    DEFAULT_HORIZONS,
    ERROR_TYPES,
    PRINCIPAL_SEED,
    run_simulation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIORS_DIR = REPO_ROOT / "priors"
WEIGHTS_PATH = REPO_ROOT / "weights" / "severity_weights.yaml"

TEST_K = 2_000


@pytest.fixture(scope="module")
def prior_sets() -> dict:
    return load_all_prior_sets(PRIORS_DIR)


@pytest.fixture(scope="module")
def canonical_df(prior_sets, tmp_path_factory) -> pd.DataFrame:
    tmp = tmp_path_factory.mktemp("sim")
    res = run_simulation(
        prior_sets,
        K=TEST_K,
        seed=PRINCIPAL_SEED,
        prespecified=False,
        output_dir=tmp / "out",
        runs_dir=tmp / "runs",
        repo_root=REPO_ROOT,
    )
    return pd.read_parquet(res.output_path)


# ---------------------------------------------------------------------------
# Section 7.1 + 7.2
# ---------------------------------------------------------------------------


def test_summarise_primary_shape_and_columns(canonical_df: pd.DataFrame) -> None:
    summary = summarise_primary(canonical_df)
    expected_rows = 3 * len(ERROR_TYPES) * len(DEFAULT_HORIZONS)
    assert len(summary) == expected_rows
    for col in (
        "prior_set",
        "error_type",
        "horizon",
        "median",
        "mean",
        "p5",
        "p95",
        "ci90_low",
        "ci90_high",
        "prob_exceeds_0_01",
    ):
        assert col in summary.columns


def test_summarise_primary_orders_make_sense(canonical_df: pd.DataFrame) -> None:
    s = summarise_primary(canonical_df)
    # Pessimistic median > moderate median > optimistic median (commission, n=10)
    cell = s[(s["error_type"] == "commission") & (s["horizon"] == 10)]
    medians = cell.set_index("prior_set")["median"]
    assert medians["pessimistic"] > medians["moderate"] > medians["optimistic"]


def test_prob_exceeds_uses_threshold(canonical_df: pd.DataFrame) -> None:
    s = summarise_primary(canonical_df)
    # Manual recompute on one cell
    cell_df = canonical_df[
        (canonical_df["prior_set"] == "moderate")
        & (canonical_df["error_type"] == "commission")
        & (canonical_df["horizon"] == 10)
    ]
    expected = float((cell_df["contamination"] > PROB_THRESHOLD).mean())
    actual = float(
        s[
            (s["prior_set"] == "moderate")
            & (s["error_type"] == "commission")
            & (s["horizon"] == 10)
        ]["prob_exceeds_0_01"].iloc[0]
    )
    assert actual == pytest.approx(expected)


# ---------------------------------------------------------------------------
# Section 7.3 (gated)
# ---------------------------------------------------------------------------


def test_severity_weighting_is_disabled_in_v1_0() -> None:
    status = load_severity_weighting(WEIGHTS_PATH)
    assert status.enabled is False
    assert status.skipped_reason is not None
    assert status.weights == {}


# ---------------------------------------------------------------------------
# Section 7.4 sensitivity scenarios
# ---------------------------------------------------------------------------


def test_R_zero_sensitivity_forces_R_to_zero(prior_sets) -> None:
    df = sensitivity_R_zero(prior_sets["moderate"], K=500, seed=1)
    assert (df["R"] == 0.0).all()
    assert df["prior_set"].iloc[0].endswith("__R0")


def test_copula_induces_positive_correlation(prior_sets) -> None:
    df_corr = sensitivity_copula(prior_sets["moderate"], rho=0.4, K=4000, seed=1)
    # Take any one horizon to avoid duplicating samples
    h0 = df_corr[df_corr["horizon"] == DEFAULT_HORIZONS[0]]
    obs = float(np.corrcoef(h0["E0"], h0["epsilon"])[0, 1])
    # Beta-margin-induced correlation under Gaussian copula is bounded
    # below the underlying Gaussian correlation; expect positive and
    # non-trivial.
    assert obs > 0.2, f"Expected positive correlation; got {obs:.3f}"


def test_copula_independent_at_rho_zero(prior_sets) -> None:
    df_indep = sensitivity_copula(prior_sets["moderate"], rho=0.0, K=4000, seed=1)
    h0 = df_indep[df_indep["horizon"] == DEFAULT_HORIZONS[0]]
    obs = float(np.corrcoef(h0["E0"], h0["epsilon"])[0, 1])
    assert abs(obs) < 0.05


def test_copula_rejects_invalid_rho(prior_sets) -> None:
    with pytest.raises(ValueError):
        sensitivity_copula(prior_sets["moderate"], rho=1.0)


def test_multi_agent_P_centred_at_0_65(prior_sets) -> None:
    df = sensitivity_multi_agent_P(prior_sets["moderate"], K=8000, seed=1)
    h0 = df[df["horizon"] == DEFAULT_HORIZONS[0]]
    sample_mean_P = float(h0["P"].mean())
    # Beta(16.25, 8.75) sample mean within 1% of population mean for K=8000.
    assert abs(sample_mean_P - MULTI_AGENT_P_MU) < 0.01
    # And the expected variance is mu*(1-mu)/(kappa+1)
    expected_var = MULTI_AGENT_P_MU * (1 - MULTI_AGENT_P_MU) / (MULTI_AGENT_P_KAPPA + 1)
    assert abs(float(h0["P"].var()) - expected_var) < 0.01


def test_robustness_ratio_returns_sensible_verdict(canonical_df: pd.DataFrame) -> None:
    out = robustness_ratio(canonical_df, horizon=10, error_type="commission")
    assert out["pessimistic_p95"] > out["optimistic_p5"] > 0
    assert out["ratio"] > 1.0
    assert out["verdict"] in {"robust", "intermediate", "sensitive"}


# ---------------------------------------------------------------------------
# Section 7.5
# ---------------------------------------------------------------------------


def test_hospital_scale_uses_full_multiplier(canonical_df: pd.DataFrame) -> None:
    h = hospital_scale(canonical_df)
    assert len(h) == 3 * len(ERROR_TYPES)
    assert (h["docs_per_year"] == HOSPITAL_DOCS_PER_YEAR).all()
    assert (h["years"] == HOSPITAL_YEARS).all()
    assert (h["horizon"] == HOSPITAL_HORIZON).all()
    # Median scales by docs_per_year * years compared with the per-confab
    # contamination median at horizon 10.
    pcc = canonical_df[
        (canonical_df["horizon"] == HOSPITAL_HORIZON)
        & (canonical_df["prior_set"] == "moderate")
        & (canonical_df["error_type"] == "commission")
    ]["contamination"]
    expected = float(np.median(pcc) * HOSPITAL_DOCS_PER_YEAR * HOSPITAL_YEARS)
    actual = float(
        h[(h["prior_set"] == "moderate") & (h["error_type"] == "commission")][
            "median"
        ].iloc[0]
    )
    assert actual == pytest.approx(expected)


# ---------------------------------------------------------------------------
# End-to-end orchestrator
# ---------------------------------------------------------------------------


def test_analyse_canonical_runs_end_to_end(prior_sets, tmp_path) -> None:
    res = run_simulation(
        prior_sets,
        K=TEST_K,
        seed=42,
        prespecified=False,
        output_dir=tmp_path / "out",
        runs_dir=tmp_path / "runs",
        repo_root=REPO_ROOT,
    )
    out = analyse_canonical(res.output_path, weights_path=WEIGHTS_PATH)
    assert len(out.primary) == 3 * len(ERROR_TYPES) * len(DEFAULT_HORIZONS)
    assert len(out.hospital) == 3 * len(ERROR_TYPES)
    assert "ratio" in out.robustness
    assert out.severity_status.enabled is False
    assert out.severity_weighted is None
