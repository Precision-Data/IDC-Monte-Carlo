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
# Section 7.3: severity-weighted contamination (gated on severity_weights.yaml)
# ---------------------------------------------------------------------------

# Required NOHARM tiers in the harm_cost_multipliers block of the YAML.
# The framework's severity-weighted contamination uses mild / moderate /
# severe; ``no_harm`` is permitted in the YAML for documentation but does
# not feed the weighted-aggregate computation (no_harm errors contribute
# zero by definition).
HARM_TIERS_REQUIRED: tuple[str, ...] = ("mild", "moderate", "severe")

# Per-tier-option probability mass functions are validated to sum to 1
# within this tolerance. The YAML uses 0.3333333 for the uniform option,
# which sums to 0.9999999; 1e-3 is a comfortable budget that catches
# typos without demanding numerical perfection.
TIER_PROBABILITY_SUM_TOLERANCE: float = 1e-3


class SeverityWeightingError(ValueError):
    """Raised when severity_weights.yaml is structurally invalid or when
    severity-weighted analysis is requested while the gate is closed."""


@dataclass(frozen=True)
class SeverityWeightingStatus:
    enabled: bool
    citation: str
    skipped_reason: str | None
    harm_weights: Mapping[str, float]
    tier_options: Mapping[str, Mapping[str, float]]
    primary_tier_option: str
    sensitivity_tier_options: tuple[str, ...]
    type_distribution_severe: Mapping[str, float]
    type_distribution_all: Mapping[str, float]


def _validate_harm_cost_multipliers(raw: Mapping) -> dict[str, float]:
    if "harm_cost_multipliers" not in raw:
        raise SeverityWeightingError(
            "severity_weights.yaml: missing 'harm_cost_multipliers' block"
        )
    block = raw["harm_cost_multipliers"]
    weights: dict[str, float] = {}
    for tier in HARM_TIERS_REQUIRED:
        if tier not in block:
            raise SeverityWeightingError(
                f"severity_weights.yaml: harm_cost_multipliers missing tier '{tier}'"
            )
        entry = block[tier]
        if "weight" not in entry:
            raise SeverityWeightingError(
                f"severity_weights.yaml: tier '{tier}' has no 'weight' field"
            )
        w = entry["weight"]
        if not isinstance(w, (int, float)) or isinstance(w, bool):
            raise SeverityWeightingError(
                f"severity_weights.yaml: tier '{tier}' weight must be numeric "
                f"(got {type(w).__name__})"
            )
        weights[tier] = float(w)
    return weights


def _validate_tier_options(
    raw: Mapping,
) -> dict[str, dict[str, float]]:
    if "tier_distribution_options" not in raw:
        raise SeverityWeightingError(
            "severity_weights.yaml: missing 'tier_distribution_options' block"
        )
    block = raw["tier_distribution_options"]
    if not isinstance(block, Mapping) or not block:
        raise SeverityWeightingError(
            "severity_weights.yaml: tier_distribution_options must be a non-empty mapping"
        )
    out: dict[str, dict[str, float]] = {}
    for name, opt in block.items():
        probs = {
            "p_mild": float(opt.get("p_mild", 0.0)),
            "p_moderate": float(opt.get("p_moderate", 0.0)),
            "p_severe": float(opt.get("p_severe", 0.0)),
        }
        s = sum(probs.values())
        if abs(s - 1.0) > TIER_PROBABILITY_SUM_TOLERANCE:
            raise SeverityWeightingError(
                f"tier_distribution_options['{name}']: p_mild+p_moderate+p_severe = "
                f"{s:.6f} (must be within {TIER_PROBABILITY_SUM_TOLERANCE} of 1.0)"
            )
        out[str(name)] = probs
    return out


def load_severity_weighting(weights_path: str | Path) -> SeverityWeightingStatus:
    """Read ``weights/severity_weights.yaml`` and return its parsed status.

    Returns a ``SeverityWeightingStatus`` regardless of the gate; the
    caller decides whether ``enabled`` and ``primary_tier_option`` are
    sufficient to proceed with Section 7.3 computation.

    Validates the structure of the YAML even when ``enabled`` is false,
    so that a malformed file is loud instead of silently disabled.
    """
    raw = yaml.safe_load(Path(weights_path).read_text())
    enabled = bool(raw.get("enabled", False))
    citation = str((raw.get("source") or {}).get("citation", "")).strip()

    skipped_reason: str | None = None
    harm_weights: dict[str, float] = {}
    tier_options: dict[str, dict[str, float]] = {}
    primary_tier_option = ""
    sensitivity: tuple[str, ...] = ()
    td_severe: Mapping[str, float] = {}
    td_all: Mapping[str, float] = {}

    has_richness = "harm_cost_multipliers" in raw or "tier_distribution_options" in raw

    if has_richness:
        # Always validate when the structured blocks exist so a typo is
        # caught even with enabled=false.
        harm_weights = _validate_harm_cost_multipliers(raw)
        tier_options = _validate_tier_options(raw)
        usage = raw.get("usage") or {}
        primary_tier_option = str(usage.get("primary_tier_option", ""))
        if primary_tier_option and primary_tier_option not in tier_options:
            raise SeverityWeightingError(
                f"usage.primary_tier_option '{primary_tier_option}' is not a "
                f"defined tier_distribution_options entry"
            )
        sensitivity = tuple(str(x) for x in (usage.get("sensitivity_tier_options") or ()))
        td_severe = {
            "p_omission": float((raw.get("type_distribution_severe") or {}).get("p_omission", 0.0)),
            "p_commission": float((raw.get("type_distribution_severe") or {}).get("p_commission", 0.0)),
        }
        td_all = {
            "p_omission": float((raw.get("type_distribution_all") or {}).get("p_omission", 0.0)),
            "p_commission": float((raw.get("type_distribution_all") or {}).get("p_commission", 0.0)),
        }
    elif enabled:
        # enabled but no structured blocks -- fail loudly per the no-judgement rule.
        raise SeverityWeightingError(
            "severity_weights.yaml has enabled=true but neither "
            "harm_cost_multipliers nor tier_distribution_options is present"
        )

    if not enabled:
        skipped_reason = str(raw.get("status", "disabled"))

    return SeverityWeightingStatus(
        enabled=enabled,
        citation=citation,
        skipped_reason=skipped_reason,
        harm_weights=harm_weights,
        tier_options=tier_options,
        primary_tier_option=primary_tier_option,
        sensitivity_tier_options=sensitivity,
        type_distribution_severe=td_severe,
        type_distribution_all=td_all,
    )


def expected_harm_weight(
    status: SeverityWeightingStatus, tier_option: str
) -> float:
    """Compute E[harm cost per error] under one tier_distribution_option.

      E[harm] = p_mild * w_mild + p_moderate * w_moderate + p_severe * w_severe

    Used by :func:`severity_weighted_contamination` to scale the raw
    contamination samples per tier scenario. ``no_harm`` contributes
    zero by definition and is not part of the sum.
    """
    if tier_option not in status.tier_options:
        raise SeverityWeightingError(
            f"unknown tier_option '{tier_option}'; available: "
            f"{sorted(status.tier_options)}"
        )
    p = status.tier_options[tier_option]
    w = status.harm_weights
    return (
        p["p_mild"] * w["mild"]
        + p["p_moderate"] * w["moderate"]
        + p["p_severe"] * w["severe"]
    )


def severity_weighted_contamination(
    canonical_output_path: str | Path,
    weights_path: str | Path,
    output_dir: str | Path,
    *,
    threshold: float = 0.01,
) -> Path:
    """Compute severity-weighted contamination per Section 7.3 of the plan.

    Reads the canonical simulation Parquet (one row per
    (prior_set, error_type, sample_index, horizon)) and the severity
    weights YAML. For every (prior_set, horizon, tier_option) combination
    the function constructs a per-sample, type-weighted, severity-weighted
    contamination value:

        type_weighted[k]   = p_omission * omission[k] + p_commission * commission[k]
        weighted[k]        = type_weighted[k] * E[harm | tier_option]

    where p_omission / p_commission come from
    ``type_distribution_severe`` (per the YAML's ``usage.type_decomposition_basis``
    setting) and ``E[harm | tier_option]`` is the harm-weighted expectation
    over the NOHARM tier mass function defined by ``tier_option``.

    Summary statistics (median, mean, p5, p95, P[weighted > threshold]) are
    then computed across the K samples per cell and written as
    ``severity_weighted.parquet`` under ``output_dir``. The columns p_omission
    and p_commission are emitted alongside as informational documentation
    of the type-mixing weights actually used.

    Raises :class:`SeverityWeightingError` if the YAML gate is closed
    (``enabled: false``); the analysis must never be silently skipped at
    the function boundary.
    """
    status = load_severity_weighting(weights_path)
    if not status.enabled:
        raise SeverityWeightingError(
            "severity_weights.yaml has enabled=false; severity-weighted "
            "analysis cannot run. Either flip the gate or call this "
            "function only when status.enabled is true."
        )

    df = pd.read_parquet(canonical_output_path)
    p_om = status.type_distribution_severe["p_omission"]
    p_co = status.type_distribution_severe["p_commission"]

    rows: list[dict] = []
    cells = df.groupby(["prior_set", "horizon"], sort=True)
    tier_names = [status.primary_tier_option, *status.sensitivity_tier_options]
    seen: set[str] = set()
    ordered_tiers = [t for t in tier_names if not (t in seen or seen.add(t))]

    for (ps, h), grp in cells:
        comm = grp.loc[grp["error_type"] == "commission", "contamination"].to_numpy()
        omis = grp.loc[grp["error_type"] == "omission", "contamination"].to_numpy()
        if comm.size != omis.size or comm.size == 0:
            raise SeverityWeightingError(
                f"cell prior_set={ps} horizon={h}: expected matched K samples "
                f"of commission and omission (got {comm.size} vs {omis.size})"
            )
        type_weighted = p_co * comm + p_om * omis
        for tname in ordered_tiers:
            ew = expected_harm_weight(status, tname)
            weighted = type_weighted * ew
            p5, p50, p95 = np.percentile(weighted, [5, 50, 95])
            rows.append(
                {
                    "prior_set": ps,
                    "horizon": int(h),
                    "tier_option": tname,
                    "median": float(p50),
                    "mean": float(weighted.mean()),
                    "p5": float(p5),
                    "p95": float(p95),
                    "p_exceeds_threshold": float((weighted > threshold).mean()),
                    "p_omission": p_om,
                    "p_commission": p_co,
                }
            )

    out_df = pd.DataFrame(rows)
    out_df = out_df.sort_values(["prior_set", "horizon", "tier_option"]).reset_index(
        drop=True
    )

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "severity_weighted.parquet"

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(out_df, preserve_index=False)
    pq.write_table(
        table,
        out_path,
        compression="snappy",
        use_dictionary=True,
        write_statistics=False,
    )
    return out_path


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
    severity_weighted_path: Path | None


def analyse_canonical(
    parquet_path: str | Path,
    *,
    weights_path: str | Path,
    output_dir: str | Path | None = None,
) -> AnalysisResult:
    """Run all Section 7 analyses that consume only the canonical Parquet.

    When the severity-weighting gate (severity_weights.yaml ``enabled``)
    is true and ``output_dir`` is supplied, the Section 7.3 weighted
    analysis is computed via :func:`severity_weighted_contamination` and
    written as ``severity_weighted.parquet`` under ``output_dir``. The
    in-memory DataFrame and the file path are both returned in the
    :class:`AnalysisResult`.

    When ``output_dir`` is omitted but the gate is open, the weighted
    analysis still runs in-memory (no Parquet written). When the gate
    is closed (``enabled: false``) the analysis is skipped and the
    deviation justification is recorded in ``severity_status``.
    """
    df = pd.read_parquet(parquet_path)
    primary = summarise_primary(df)
    hospital = hospital_scale(df)
    rob = robustness_ratio(df)
    sev_status = load_severity_weighting(weights_path)
    sev_df: pd.DataFrame | None = None
    sev_path: Path | None = None
    if sev_status.enabled:
        if output_dir is not None:
            sev_path = severity_weighted_contamination(
                parquet_path, weights_path, output_dir
            )
            sev_df = pd.read_parquet(sev_path)
        else:
            # In-memory recomputation when no output_dir is supplied
            # (used by tests that don't want filesystem side effects).
            import tempfile

            with tempfile.TemporaryDirectory() as td:
                p = severity_weighted_contamination(parquet_path, weights_path, td)
                sev_df = pd.read_parquet(p)
    return AnalysisResult(
        primary=primary,
        hospital=hospital,
        robustness=rob,
        severity_status=sev_status,
        severity_weighted=sev_df,
        severity_weighted_path=sev_path,
    )
