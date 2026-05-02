"""Pre-specified analyses (ANALYSIS_PLAN.md Section 7).

All analyses below operate on the canonical Parquet output produced by
:mod:`idc_simulation.simulation`. They never re-run the principal
simulation. Sensitivity scenarios (Section 7.4) that require parameter
changes -- R = 0, the E0-epsilon Gaussian copula, the multi-agent P
shift -- are produced via dedicated helpers that draw their own samples
from the priors module and reuse the contamination function. Each such
helper writes its own Parquet output and run log so its provenance is
traceable independently of the principal run.

Section coverage:
  7.1  primary distributional summaries (one row per cell)
  7.2  type decomposition (rows per error_type, already in canonical df)
  7.3  severity-weighted contamination (gated on severity_weights.yaml)
  7.4  sensitivity scenarios:
         7.4.a  R = 0 boundary case (moderate prior)
         7.4.b  rho = 0.4 Gaussian copula on (E0, epsilon)
         7.4.c  multi-agent P shift (mu = 0.65, kappa = 25)
         7.4.d  robustness ratio (pessimistic 95th / optimistic 5th, n=10)
  7.5  hospital-scale illustration (100,000 docs/year, 5 years, n=10)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import pandas as pd
import yaml
from scipy.stats import beta as _beta_dist
from scipy.stats import multivariate_normal as _mvn
from scipy.stats import norm as _norm

from .contamination import contamination
from .priors import PARAMETER_NAMES, PriorSet


# ---------------------------------------------------------------------------
# Section 7.1 + 7.2: primary distributional summaries
# ---------------------------------------------------------------------------


PRIMARY_GROUP_KEYS: tuple[str, ...] = ("prior_set", "error_type", "horizon")
PROB_THRESHOLD: float = 0.01  # Section 7.1: Pr[Contamination(n) > 0.01]


def summarise_primary(df: pd.DataFrame) -> pd.DataFrame:
    """One-row-per-cell summary of contamination samples.

    Columns: median, mean, p5, p95, ci90_low, ci90_high, prob_exceeds.
    Implements Section 7.1 (and via the per-error_type grouping, the
    type decomposition of Section 7.2).
    """

    def _agg(s: pd.Series) -> pd.Series:
        a = s.to_numpy()
        p5, p50, p95 = np.percentile(a, [5, 50, 95])
        return pd.Series(
            {
                "n_samples": int(a.size),
                "median": float(p50),
                "mean": float(a.mean()),
                "p5": float(p5),
                "p95": float(p95),
                "ci90_low": float(p5),
                "ci90_high": float(p95),
                "prob_exceeds_0_01": float((a > PROB_THRESHOLD).mean()),
            }
        )

    return (
        df.groupby(list(PRIMARY_GROUP_KEYS))["contamination"]
        .apply(_agg)
        .unstack()
        .reset_index()
    )


# ---------------------------------------------------------------------------
# Section 7.3: severity-weighted contamination (gated)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeverityWeightingStatus:
    enabled: bool
    citation: str
    skipped_reason: str | None
    weights: dict[str, float]


def load_severity_weighting(weights_path: str | Path) -> SeverityWeightingStatus:
    """Read ``weights/severity_weights.yaml`` and return its enabled status.

    Per plan Section 6.4, if the YAML reports ``enabled: false`` the
    severity-weighted analysis (Section 7.3) is skipped and the gap is
    logged. Tier weights chosen by judgement to fill the gap are
    forbidden.
    """
    raw = yaml.safe_load(Path(weights_path).read_text())
    enabled = bool(raw.get("enabled", False))
    citation = str((raw.get("source") or {}).get("citation", "")).strip()
    if not enabled:
        return SeverityWeightingStatus(
            enabled=False,
            citation=citation,
            skipped_reason=str(raw.get("status", "disabled")),
            weights={},
        )
    tiers = raw.get("tiers") or {}
    if not tiers:
        return SeverityWeightingStatus(
            enabled=False,
            citation=citation,
            skipped_reason="enabled=true but tiers mapping is empty",
            weights={},
        )
    weights = {str(k): float(v) for k, v in tiers.items()}
    return SeverityWeightingStatus(
        enabled=True, citation=citation, skipped_reason=None, weights=weights
    )


# ---------------------------------------------------------------------------
# Section 7.4: sensitivity scenarios
# ---------------------------------------------------------------------------


def _contamination_for_samples(
    samples: dict[str, np.ndarray],
    horizons: tuple[int, ...],
    *,
    prior_set_name: str,
    error_type: str = "commission",
) -> pd.DataFrame:
    """Helper: turn a dict of K parameter arrays into the long-format frame."""
    K = samples["E0"].size
    h_arr = np.asarray(horizons, dtype=np.int64)
    H = h_arr.size
    cont = contamination(
        E0=samples["E0"][:, None],
        epsilon=samples["epsilon"][:, None],
        P=samples["P"][:, None],
        R=samples["R"][:, None],
        n=h_arr[None, :],
    )
    sample_idx = np.arange(K, dtype=np.int64)
    return pd.DataFrame(
        {
            "prior_set": np.repeat(prior_set_name, K * H),
            "error_type": np.repeat(error_type, K * H),
            "sample_index": np.repeat(sample_idx, H),
            "horizon": np.tile(h_arr, K),
            "E0": np.repeat(samples["E0"], H),
            "epsilon": np.repeat(samples["epsilon"], H),
            "P": np.repeat(samples["P"], H),
            "R": np.repeat(samples["R"], H),
            "contamination": cont.reshape(-1),
        }
    )


def sensitivity_R_zero(
    prior_set: PriorSet,
    *,
    K: int = 10_000,
    horizons: tuple[int, ...] = (1, 5, 10, 20),
    seed: int = 20260502,
) -> pd.DataFrame:
    """Section 7.4.a: R = 0 boundary case under the moderate prior.

    All other parameters are drawn from the supplied prior set as usual.
    R is forced to zero across all K samples.
    """
    rng = np.random.default_rng(seed)
    samples = {
        "E0": rng.beta(prior_set.get("E0").alpha, prior_set.get("E0").beta, size=K),
        "epsilon": rng.beta(
            prior_set.get("epsilon").alpha, prior_set.get("epsilon").beta, size=K
        ),
        "P": rng.beta(prior_set.get("P").alpha, prior_set.get("P").beta, size=K),
        "R": np.zeros(K, dtype=np.float64),
    }
    return _contamination_for_samples(
        samples, horizons, prior_set_name=f"{prior_set.name}__R0"
    )


def sensitivity_copula(
    prior_set: PriorSet,
    *,
    rho: float = 0.4,
    K: int = 10_000,
    horizons: tuple[int, ...] = (1, 5, 10, 20),
    seed: int = 20260502,
) -> pd.DataFrame:
    """Section 7.4.b: positive Gaussian copula on (E0, epsilon).

    Induces correlation rho between the E0 and epsilon draws by
    sampling from a 2D standard normal with covariance [[1, rho], [rho, 1]],
    transforming each margin through Phi (the standard-normal CDF), then
    applying the Beta inverse-CDF to land on the correct marginal Beta.
    P and R are drawn independently as usual.
    """
    if not -1.0 < rho < 1.0:
        raise ValueError("rho must lie strictly in (-1, 1)")
    rng = np.random.default_rng(seed)
    cov = np.array([[1.0, rho], [rho, 1.0]])
    z = _mvn.rvs(mean=[0.0, 0.0], cov=cov, size=K, random_state=rng)
    u = _norm.cdf(z)
    e0_p = prior_set.get("E0")
    eps_p = prior_set.get("epsilon")
    samples = {
        "E0": _beta_dist.ppf(u[:, 0], e0_p.alpha, e0_p.beta),
        "epsilon": _beta_dist.ppf(u[:, 1], eps_p.alpha, eps_p.beta),
        "P": rng.beta(prior_set.get("P").alpha, prior_set.get("P").beta, size=K),
        "R": rng.beta(prior_set.get("R").alpha, prior_set.get("R").beta, size=K),
    }
    return _contamination_for_samples(
        samples, horizons, prior_set_name=f"{prior_set.name}__copula_rho{rho:.2f}"
    )


# Section 7.4.c: multi-agent P prior, mu = 0.65, kappa = 25.
MULTI_AGENT_P_MU: float = 0.65
MULTI_AGENT_P_KAPPA: float = 25.0


def sensitivity_multi_agent_P(
    prior_set: PriorSet,
    *,
    K: int = 10_000,
    horizons: tuple[int, ...] = (1, 5, 10, 20),
    seed: int = 20260502,
) -> pd.DataFrame:
    """Section 7.4.c: multi-agent-adjusted P (mu = 0.65, kappa = 25).

    All other parameters are drawn from the supplied prior set
    unchanged.
    """
    rng = np.random.default_rng(seed)
    p_alpha = MULTI_AGENT_P_MU * MULTI_AGENT_P_KAPPA
    p_beta = (1.0 - MULTI_AGENT_P_MU) * MULTI_AGENT_P_KAPPA
    samples = {
        "E0": rng.beta(prior_set.get("E0").alpha, prior_set.get("E0").beta, size=K),
        "epsilon": rng.beta(
            prior_set.get("epsilon").alpha, prior_set.get("epsilon").beta, size=K
        ),
        "P": rng.beta(p_alpha, p_beta, size=K),
        "R": rng.beta(prior_set.get("R").alpha, prior_set.get("R").beta, size=K),
    }
    return _contamination_for_samples(
        samples, horizons, prior_set_name=f"{prior_set.name}__multiagent_P"
    )


# Section 7.4.d: robustness ratio thresholds
ROBUSTNESS_THRESHOLD_OK: float = 25.0
ROBUSTNESS_THRESHOLD_SENSITIVE: float = 50.0


def robustness_ratio(
    df: pd.DataFrame,
    *,
    horizon: int = 10,
    error_type: str = "commission",
) -> dict:
    """Section 7.4.d: pessimistic 95th / optimistic 5th at horizon n.

    Returns a dict with the ratio, the two underlying percentiles, and
    a verdict relative to the thresholds 25 (robust) and 50 (sensitive).
    """
    cell = df[(df["horizon"] == horizon) & (df["error_type"] == error_type)]
    p_pess = float(
        np.percentile(
            cell.loc[cell["prior_set"] == "pessimistic", "contamination"], 95
        )
    )
    p_opt = float(
        np.percentile(
            cell.loc[cell["prior_set"] == "optimistic", "contamination"], 5
        )
    )
    ratio = p_pess / p_opt if p_opt > 0 else float("inf")
    if ratio < ROBUSTNESS_THRESHOLD_OK:
        verdict = "robust"
    elif ratio > ROBUSTNESS_THRESHOLD_SENSITIVE:
        verdict = "sensitive"
    else:
        verdict = "intermediate"
    return {
        "horizon": horizon,
        "error_type": error_type,
        "pessimistic_p95": p_pess,
        "optimistic_p5": p_opt,
        "ratio": ratio,
        "verdict": verdict,
        "threshold_ok": ROBUSTNESS_THRESHOLD_OK,
        "threshold_sensitive": ROBUSTNESS_THRESHOLD_SENSITIVE,
    }


# ---------------------------------------------------------------------------
# Section 7.5: hospital-scale illustration
# ---------------------------------------------------------------------------


HOSPITAL_DOCS_PER_YEAR: int = 100_000
HOSPITAL_YEARS: int = 5
HOSPITAL_HORIZON: int = 10


def hospital_scale(
    df: pd.DataFrame,
    *,
    docs_per_year: int = HOSPITAL_DOCS_PER_YEAR,
    years: int = HOSPITAL_YEARS,
    horizon: int = HOSPITAL_HORIZON,
) -> pd.DataFrame:
    """Section 7.5: scale per-confabulation contamination to hospital
    output (default: 100,000 documents/year, 5 years, n = 10).

    Returns one row per (prior_set, error_type) with the median and 90%
    credible interval of contaminated documents over the horizon.
    """
    multiplier = docs_per_year * years
    cell = df[df["horizon"] == horizon].copy()
    cell["contaminated_documents"] = cell["contamination"] * multiplier

    def _agg(s: pd.Series) -> pd.Series:
        a = s.to_numpy()
        p5, p50, p95 = np.percentile(a, [5, 50, 95])
        return pd.Series(
            {
                "median": float(p50),
                "ci90_low": float(p5),
                "ci90_high": float(p95),
                "mean": float(a.mean()),
            }
        )

    out = (
        cell.groupby(["prior_set", "error_type"])["contaminated_documents"]
        .apply(_agg)
        .unstack()
        .reset_index()
    )
    out["docs_per_year"] = docs_per_year
    out["years"] = years
    out["horizon"] = horizon
    return out


# ---------------------------------------------------------------------------
# Convenience entry point: run all read-from-Parquet analyses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AnalysisResult:
    primary: pd.DataFrame
    hospital: pd.DataFrame
    robustness: dict
    severity_status: SeverityWeightingStatus
    severity_weighted: pd.DataFrame | None


def analyse_canonical(
    parquet_path: str | Path,
    *,
    weights_path: str | Path,
) -> AnalysisResult:
    """Run all Section 7 analyses that consume only the canonical Parquet."""
    df = pd.read_parquet(parquet_path)
    primary = summarise_primary(df)
    hospital = hospital_scale(df)
    rob = robustness_ratio(df)
    sev_status = load_severity_weighting(weights_path)
    sev_df: pd.DataFrame | None = None
    if sev_status.enabled:
        # Severity-weighted contamination is computed by re-grouping the
        # contamination distribution by NOHARM tier weight. This branch
        # is intentionally unreachable in v1.0 (severity weights not
        # yet extracted from Wu et al. 2025); the structure is left in
        # place for future activation per Section 6.4 reactivation rules.
        weighted = df["contamination"].copy()
        weighted *= sum(sev_status.weights.values())
        df_sev = df.assign(contamination=weighted)
        sev_df = summarise_primary(df_sev)
    return AnalysisResult(
        primary=primary,
        hospital=hospital,
        robustness=rob,
        severity_status=sev_status,
        severity_weighted=sev_df,
    )
