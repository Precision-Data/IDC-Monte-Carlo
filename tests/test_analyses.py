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
    HARM_TIERS_REQUIRED,
    HOSPITAL_DOCS_PER_YEAR,
    HOSPITAL_HORIZON,
    HOSPITAL_YEARS,
    MULTI_AGENT_P_KAPPA,
    MULTI_AGENT_P_MU,
    PROB_THRESHOLD,
    SeverityWeightingError,
    add_regime_dimension,
    analyse_canonical,
    expected_harm_weight,
    hospital_scale,
    load_severity_weighting,
    regime_contrast_statistic,
    robustness_ratio,
    sensitivity_R_zero,
    sensitivity_copula,
    sensitivity_multi_agent_P,
    severity_weighted_contamination,
    summarise_primary,
)
from idc_simulation.contamination import (
    REGIME_CORRECTED,
    REGIME_UNCORRECTED,
    REGIMES,
    contamination,
    geometric_sum_factor,
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
    df = add_regime_dimension(canonical_df)
    summary = summarise_primary(df)
    # v2.0: regime x prior_set x error_type x horizon = 2 * 3 * 2 * 4 = 48
    expected_rows = len(REGIMES) * 3 * len(ERROR_TYPES) * len(DEFAULT_HORIZONS)
    assert len(summary) == expected_rows
    assert set(summary["regime"].unique()) == set(REGIMES)
    for col in (
        "regime",
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
    df = add_regime_dimension(canonical_df)
    s = summarise_primary(df)
    # Pessimistic median > moderate median > optimistic median (uncorrected, commission, n=10)
    cell = s[
        (s["regime"] == REGIME_UNCORRECTED)
        & (s["error_type"] == "commission")
        & (s["horizon"] == 10)
    ]
    medians = cell.set_index("prior_set")["median"]
    assert medians["pessimistic"] > medians["moderate"] > medians["optimistic"]


def test_prob_exceeds_uses_threshold(canonical_df: pd.DataFrame) -> None:
    df = add_regime_dimension(canonical_df)
    s = summarise_primary(df)
    # Manual recompute on one (corrected) cell -- this is the v1.2.1 contamination
    cell_df = canonical_df[
        (canonical_df["prior_set"] == "moderate")
        & (canonical_df["error_type"] == "commission")
        & (canonical_df["horizon"] == 10)
    ]
    expected = float((cell_df["contamination"] > PROB_THRESHOLD).mean())
    actual = float(
        s[
            (s["regime"] == REGIME_CORRECTED)
            & (s["prior_set"] == "moderate")
            & (s["error_type"] == "commission")
            & (s["horizon"] == 10)
        ]["prob_exceeds_0_01"].iloc[0]
    )
    assert actual == pytest.approx(expected)


# ---------------------------------------------------------------------------
# v2.0: regime expansion and the brief's required regime tests
# ---------------------------------------------------------------------------


def test_add_regime_dimension_doubles_row_count(canonical_df: pd.DataFrame) -> None:
    expanded = add_regime_dimension(canonical_df)
    assert len(expanded) == 2 * len(canonical_df)
    assert set(expanded["regime"].unique()) == {REGIME_UNCORRECTED, REGIME_CORRECTED}


def test_corrected_regime_equals_v1_2_1_contamination(
    canonical_df: pd.DataFrame,
) -> None:
    """The corrected-regime contamination values must equal the
    v1.2.1 contamination values per sample (this is the same
    computation under a different name; brief Section 4 spec).
    """
    expanded = add_regime_dimension(canonical_df)
    corr = expanded[expanded["regime"] == REGIME_CORRECTED].sort_values(
        ["prior_set", "error_type", "sample_index", "horizon"]
    ).reset_index(drop=True)
    base = canonical_df.sort_values(
        ["prior_set", "error_type", "sample_index", "horizon"]
    ).reset_index(drop=True)
    np.testing.assert_allclose(
        corr["contamination"].to_numpy(),
        base["contamination"].to_numpy(),
        rtol=0,
        atol=1e-9,
    )


def test_uncorrected_regime_matches_closed_form_geometric_series(
    canonical_df: pd.DataFrame,
) -> None:
    """The uncorrected-regime contamination values must equal the
    closed-form geometric series E0 * eps * (1 - P^(n+1)) / (1 - P)
    per sample within 1e-12 (exact arithmetic, no Monte Carlo error).
    """
    expanded = add_regime_dimension(canonical_df)
    uncorr = expanded[expanded["regime"] == REGIME_UNCORRECTED]
    expected = (
        uncorr["E0"].to_numpy()
        * uncorr["epsilon"].to_numpy()
        * geometric_sum_factor(uncorr["P"].to_numpy(), uncorr["horizon"].to_numpy())
    )
    np.testing.assert_allclose(
        uncorr["contamination"].to_numpy(),
        expected,
        rtol=0,
        atol=1e-12,
    )


def test_regime_contrast_monotonicity_ge_one(canonical_df: pd.DataFrame) -> None:
    """The regime contrast (median uncorrected / median corrected)
    must be >= 1.0 for every cell because (1 - R)^n <= 1 for R in [0, 1].
    """
    df = add_regime_dimension(canonical_df)
    summary = summarise_primary(df)
    contrast = regime_contrast_statistic(summary)
    assert (contrast["regime_contrast"] >= 1.0 - 1e-12).all(), (
        "Regime contrast violated 1.0 lower bound: " +
        contrast[contrast["regime_contrast"] < 1.0].to_string()
    )


def test_regime_contrast_increases_with_horizon_for_moderate(
    canonical_df: pd.DataFrame,
) -> None:
    """For moderate prior + commission, the regime contrast ratio
    should increase monotonically with horizon n (the benefit of
    correction compounds over time, since (1 - R)^n decays in n).
    """
    df = add_regime_dimension(canonical_df)
    summary = summarise_primary(df)
    contrast = regime_contrast_statistic(summary)
    cell = contrast[
        (contrast["prior_set"] == "moderate")
        & (contrast["error_type"] == "commission")
    ].sort_values("horizon")
    ratios = cell["regime_contrast"].to_numpy()
    assert (np.diff(ratios) >= -1e-9).all(), (
        f"Regime contrast not monotonically non-decreasing in n: {ratios}"
    )


# ---------------------------------------------------------------------------
# Section 7.3 (gated)
# ---------------------------------------------------------------------------


def test_severity_weighting_loads_with_full_structure() -> None:
    status = load_severity_weighting(WEIGHTS_PATH)
    assert status.enabled is True
    assert status.skipped_reason is None
    # Harm cost multipliers per the (5,5) NOHARM scheme
    assert status.harm_weights == {"mild": 1.0, "moderate": 5.0, "severe": 25.0}
    # Three tier distribution options present, primary is anchored_severe_22_2_percent
    assert set(status.tier_options) == {
        "severe_only",
        "uniform_severe_moderate_mild",
        "anchored_severe_22_2_percent",
    }
    assert status.primary_tier_option == "anchored_severe_22_2_percent"
    # Type distribution for severe errors: 76.6% omission per Wu et al.
    assert status.type_distribution_severe["p_omission"] == pytest.approx(0.766)
    assert status.type_distribution_severe["p_commission"] == pytest.approx(0.234)


def test_severity_weighting_each_tier_option_sums_to_one() -> None:
    status = load_severity_weighting(WEIGHTS_PATH)
    for name, probs in status.tier_options.items():
        s = probs["p_mild"] + probs["p_moderate"] + probs["p_severe"]
        assert abs(s - 1.0) < 1e-3, f"{name} sums to {s}"


def test_severity_weighting_rejects_missing_harm_block(tmp_path) -> None:
    bad = tmp_path / "no_harm.yaml"
    bad.write_text(
        "enabled: true\n"
        "tier_distribution_options:\n"
        "  severe_only: {p_mild: 0, p_moderate: 0, p_severe: 1}\n"
    )
    with pytest.raises(SeverityWeightingError, match="harm_cost_multipliers"):
        load_severity_weighting(bad)


def test_severity_weighting_rejects_non_numeric_weight(tmp_path) -> None:
    bad = tmp_path / "bad_weight.yaml"
    bad.write_text(
        "enabled: true\n"
        "harm_cost_multipliers:\n"
        "  mild: {weight: 'one'}\n"
        "  moderate: {weight: 5}\n"
        "  severe: {weight: 25}\n"
        "tier_distribution_options:\n"
        "  severe_only: {p_mild: 0, p_moderate: 0, p_severe: 1}\n"
    )
    with pytest.raises(SeverityWeightingError, match="must be numeric"):
        load_severity_weighting(bad)


def test_severity_weighting_rejects_tier_probs_not_summing_to_one(tmp_path) -> None:
    bad = tmp_path / "bad_probs.yaml"
    bad.write_text(
        "enabled: true\n"
        "harm_cost_multipliers:\n"
        "  mild: {weight: 1}\n"
        "  moderate: {weight: 5}\n"
        "  severe: {weight: 25}\n"
        "tier_distribution_options:\n"
        "  bad_option: {p_mild: 0.5, p_moderate: 0.5, p_severe: 0.5}\n"
    )
    with pytest.raises(SeverityWeightingError, match="within"):
        load_severity_weighting(bad)


def test_expected_harm_weight_severe_only_is_25() -> None:
    status = load_severity_weighting(WEIGHTS_PATH)
    assert expected_harm_weight(status, "severe_only") == pytest.approx(25.0)


def test_expected_harm_weight_uniform_is_31_over_3() -> None:
    status = load_severity_weighting(WEIGHTS_PATH)
    # E[w] = (1+5+25)/3 = 31/3 ~= 10.333
    assert expected_harm_weight(status, "uniform_severe_moderate_mild") == pytest.approx(
        31.0 / 3.0, abs=1e-3
    )


def test_severity_weighted_writes_parquet_with_expected_schema(
    prior_sets, tmp_path
) -> None:
    res = run_simulation(
        prior_sets,
        K=TEST_K,
        seed=42,
        prespecified=False,
        output_dir=tmp_path / "out",
        runs_dir=tmp_path / "runs",
        repo_root=REPO_ROOT,
    )
    out = severity_weighted_contamination(
        res.output_path, WEIGHTS_PATH, tmp_path / "rendered"
    )
    assert out.is_file()
    sw = pd.read_parquet(out)
    expected_cols = {
        "regime",
        "prior_set",
        "horizon",
        "tier_option",
        "median",
        "mean",
        "p5",
        "p95",
        "p_exceeds_threshold",
        "p_omission",
        "p_commission",
    }
    assert set(sw.columns) == expected_cols
    # v2.0: 2 regimes * 3 prior_sets * 4 horizons * 3 tier_options = 72 rows
    assert len(sw) == 2 * 3 * 4 * 3
    assert set(sw["regime"].unique()) == set(REGIMES)
    assert sw["p_omission"].to_list() == pytest.approx([0.766] * len(sw))
    assert sw["p_commission"].to_list() == pytest.approx([0.234] * len(sw))


def test_severity_weighted_severe_only_equals_25x_type_weighted(
    prior_sets, tmp_path
) -> None:
    """Per the brief: severity-weighted under severe_only should be 25x
    the type-mixed contamination, where 25 is the severe tier weight
    from the YAML. Verified for the corrected regime (which equals
    v1.2.1 contamination). Same property holds for the uncorrected
    regime by construction.
    """
    import numpy as np

    res = run_simulation(
        prior_sets,
        K=TEST_K,
        seed=11,
        prespecified=False,
        output_dir=tmp_path / "out",
        runs_dir=tmp_path / "runs",
        repo_root=REPO_ROOT,
    )
    out = severity_weighted_contamination(
        res.output_path, WEIGHTS_PATH, tmp_path / "rendered"
    )
    sw = pd.read_parquet(out)
    df = pd.read_parquet(res.output_path)

    p_om, p_co = 0.766, 0.234
    for (ps, h), grp in df.groupby(["prior_set", "horizon"]):
        comm = grp.loc[grp["error_type"] == "commission", "contamination"].to_numpy()
        omis = grp.loc[grp["error_type"] == "omission", "contamination"].to_numpy()
        type_weighted = p_co * comm + p_om * omis
        expected_median = float(np.median(type_weighted * 25.0))
        actual = sw[
            (sw["regime"] == REGIME_CORRECTED)
            & (sw["prior_set"] == ps)
            & (sw["horizon"] == int(h))
            & (sw["tier_option"] == "severe_only")
        ]["median"].iloc[0]
        assert actual == pytest.approx(expected_median, rel=1e-9)


def test_severity_weighted_fails_loud_when_disabled(prior_sets, tmp_path) -> None:
    res = run_simulation(
        prior_sets,
        K=500,
        seed=1,
        prespecified=False,
        output_dir=tmp_path / "out",
        runs_dir=tmp_path / "runs",
        repo_root=REPO_ROOT,
    )
    disabled_yaml = tmp_path / "disabled.yaml"
    disabled_yaml.write_text("enabled: false\nstatus: 'manual disable for test'\n")
    with pytest.raises(SeverityWeightingError, match="enabled=false"):
        severity_weighted_contamination(
            res.output_path, disabled_yaml, tmp_path / "rendered"
        )


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
    df = add_regime_dimension(canonical_df)
    out = robustness_ratio(
        df, horizon=10, error_type="commission", regime=REGIME_UNCORRECTED
    )
    assert out["regime"] == REGIME_UNCORRECTED
    assert out["pessimistic_p95"] > out["optimistic_p5"] > 0
    assert out["ratio"] > 1.0
    assert out["verdict"] in {"robust", "intermediate", "sensitive"}


# ---------------------------------------------------------------------------
# Section 7.5
# ---------------------------------------------------------------------------


def test_hospital_scale_uses_full_multiplier(canonical_df: pd.DataFrame) -> None:
    df = add_regime_dimension(canonical_df)
    h = hospital_scale(df)
    # v2.0: 2 regimes * 3 prior_sets * 2 error_types = 12 rows
    assert len(h) == len(REGIMES) * 3 * len(ERROR_TYPES)
    assert (h["docs_per_year"] == HOSPITAL_DOCS_PER_YEAR).all()
    assert (h["years"] == HOSPITAL_YEARS).all()
    assert (h["horizon"] == HOSPITAL_HORIZON).all()
    # Corrected median scales by docs_per_year * years compared with the
    # v1.2.1 per-confab contamination median at horizon 10.
    pcc = canonical_df[
        (canonical_df["horizon"] == HOSPITAL_HORIZON)
        & (canonical_df["prior_set"] == "moderate")
        & (canonical_df["error_type"] == "commission")
    ]["contamination"]
    expected = float(np.median(pcc) * HOSPITAL_DOCS_PER_YEAR * HOSPITAL_YEARS)
    actual = float(
        h[
            (h["regime"] == REGIME_CORRECTED)
            & (h["prior_set"] == "moderate")
            & (h["error_type"] == "commission")
        ]["median"].iloc[0]
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
    out = analyse_canonical(
        res.output_path,
        weights_path=WEIGHTS_PATH,
        output_dir=tmp_path / "rendered",
    )
    # v2.0 shapes:
    #   primary: 2 regimes * 3 prior_sets * 2 error_types * 4 horizons = 48
    #   hospital: 2 regimes * 3 prior_sets * 2 error_types = 12
    #   regime_contrast: 3 prior_sets * 2 error_types * 4 horizons = 24
    #   severity_weighted: 2 regimes * 3 prior_sets * 4 horizons * 3 tier_options = 72
    assert len(out.primary) == len(REGIMES) * 3 * len(ERROR_TYPES) * len(DEFAULT_HORIZONS)
    assert len(out.hospital) == len(REGIMES) * 3 * len(ERROR_TYPES)
    assert len(out.regime_contrast) == 3 * len(ERROR_TYPES) * len(DEFAULT_HORIZONS)
    assert "ratio" in out.robustness_uncorrected
    assert "ratio" in out.robustness_corrected
    assert out.robustness_uncorrected["regime"] == REGIME_UNCORRECTED
    assert out.robustness_corrected["regime"] == REGIME_CORRECTED
    assert out.severity_status.enabled is True
    assert out.severity_weighted is not None
    assert len(out.severity_weighted) == len(REGIMES) * 3 * len(DEFAULT_HORIZONS) * 3
    assert out.severity_weighted_path is not None
    assert out.severity_weighted_path.is_file()
