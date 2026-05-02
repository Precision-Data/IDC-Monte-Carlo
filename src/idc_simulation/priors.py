"""Prior loading and validation.

Implements the data-side of ANALYSIS_PLAN.md Section 4. Reads the YAML
files under ``priors/`` and validates each Beta(alpha, beta) prior
against three properties:

1. The stored ``alpha`` and ``beta`` are strictly positive.
2. The implied mean (alpha / (alpha + beta)) matches the stored ``mean``.
3. The implied precision (alpha + beta) matches the stored ``precision``.
4. The 95% credible interval from ``scipy.stats.beta`` matches the
   plan's published approximation within tolerance.
5. A non-empty citation field is present.

If any check fails the loader raises :class:`PriorValidationError` with
a message naming the failing parameter and the failed property. There
is no silent fallback: a malformed prior file is a stop-the-line event.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

import yaml
from scipy.stats import beta as _beta_dist

PARAMETER_NAMES: tuple[str, ...] = ("E0", "epsilon", "P", "R")

# Tolerance used when comparing the YAML-stated 95% credible interval to
# the value computed from ``scipy.stats.beta``. The plan describes the
# stored CIs as approximate; 0.01 is wide enough for the published
# rounding while still catching transposition or arithmetic errors.
CI_TOLERANCE: float = 0.01

# Tolerance for the algebraic identities mean == alpha/(alpha+beta) and
# precision == alpha+beta. These are exact relationships, so we only
# allow numerical-rounding noise.
ALGEBRAIC_TOLERANCE: float = 1e-9


class PriorValidationError(ValueError):
    """Raised when a prior YAML fails validation."""


@dataclass(frozen=True)
class Prior:
    """A single Beta(alpha, beta) prior with its citation anchor."""

    name: str
    alpha: float
    beta: float
    mean: float
    precision: float
    citation: str
    plan_subsection: str
    description: str = ""
    ci_95_plan: tuple[float, float] | None = None


@dataclass(frozen=True)
class PriorSet:
    """A complete prior set: four base parameters + optional adjustments."""

    name: str
    plan_section: str
    plan_version: str
    description: str
    parameters: Mapping[str, Prior]
    omission_adjustments: Mapping[str, Prior] = field(default_factory=dict)
    source_path: Path | None = None

    def get(self, parameter_name: str) -> Prior:
        """Return the base prior for ``parameter_name``."""
        return self.parameters[parameter_name]

    def with_omission_epsilon(self) -> "PriorSet":
        """Return a copy of this set with epsilon replaced by its omission-adjusted form.

        Used by the type-decomposition analysis (Section 7.2) to evaluate
        the contamination function under omission errors.
        """
        if "epsilon" not in self.omission_adjustments:
            raise PriorValidationError(
                f"Prior set '{self.name}' has no omission adjustment for epsilon"
            )
        new_params = dict(self.parameters)
        new_params["epsilon"] = self.omission_adjustments["epsilon"]
        return PriorSet(
            name=f"{self.name}__omission",
            plan_section=self.plan_section,
            plan_version=self.plan_version,
            description=f"{self.description} [epsilon -> omission-adjusted]",
            parameters=new_params,
            omission_adjustments={},
            source_path=self.source_path,
        )


def _validate_prior(name: str, raw: Mapping, *, require_ci: bool = True) -> Prior:
    """Validate one parameter dict and return a Prior.

    Base parameters must carry a literature ``citation``. Derived
    omission-adjusted entries (``require_ci=False``) may instead carry a
    ``rationale`` documenting the structural argument behind the shift;
    in that case we accept the rationale as the provenance string.
    """
    for required in ("alpha", "beta", "mean", "precision"):
        if required not in raw:
            raise PriorValidationError(
                f"Parameter '{name}' is missing required field '{required}'"
            )

    alpha = float(raw["alpha"])
    b = float(raw["beta"])
    if alpha <= 0:
        raise PriorValidationError(
            f"Parameter '{name}': alpha must be > 0 (got {alpha})"
        )
    if b <= 0:
        raise PriorValidationError(
            f"Parameter '{name}': beta must be > 0 (got {b})"
        )

    mean_stated = float(raw["mean"])
    precision_stated = float(raw["precision"])
    mean_implied = alpha / (alpha + b)
    precision_implied = alpha + b
    if abs(mean_implied - mean_stated) > ALGEBRAIC_TOLERANCE:
        raise PriorValidationError(
            f"Parameter '{name}': stated mean {mean_stated} does not equal "
            f"alpha/(alpha+beta) = {mean_implied}"
        )
    if abs(precision_implied - precision_stated) > ALGEBRAIC_TOLERANCE:
        raise PriorValidationError(
            f"Parameter '{name}': stated precision {precision_stated} does not "
            f"equal alpha+beta = {precision_implied}"
        )

    # Provenance: base parameters must cite literature; omission
    # adjustments may instead document the structural rationale for
    # the shift (per plan Section 4.2).
    if "citation" in raw and str(raw["citation"]).strip():
        citation = str(raw["citation"]).strip()
    elif not require_ci and "rationale" in raw and str(raw["rationale"]).strip():
        citation = str(raw["rationale"]).strip()
    else:
        raise PriorValidationError(
            f"Parameter '{name}': citation field is empty"
            if require_ci
            else f"Parameter '{name}': must provide either 'citation' or 'rationale'"
        )

    ci_plan = None
    if "ci_95_plan" in raw:
        ci_lo_p, ci_hi_p = raw["ci_95_plan"]
        ci_plan = (float(ci_lo_p), float(ci_hi_p))
        ci_lo_calc = float(_beta_dist.ppf(0.025, alpha, b))
        ci_hi_calc = float(_beta_dist.ppf(0.975, alpha, b))
        if abs(ci_lo_calc - ci_plan[0]) > CI_TOLERANCE:
            raise PriorValidationError(
                f"Parameter '{name}': computed 2.5%-quantile {ci_lo_calc:.4f} "
                f"differs from plan {ci_plan[0]:.4f} by more than {CI_TOLERANCE}"
            )
        if abs(ci_hi_calc - ci_plan[1]) > CI_TOLERANCE:
            raise PriorValidationError(
                f"Parameter '{name}': computed 97.5%-quantile {ci_hi_calc:.4f} "
                f"differs from plan {ci_plan[1]:.4f} by more than {CI_TOLERANCE}"
            )
    elif require_ci:
        raise PriorValidationError(
            f"Parameter '{name}': missing ci_95_plan field"
        )

    return Prior(
        name=name,
        alpha=alpha,
        beta=b,
        mean=mean_stated,
        precision=precision_stated,
        citation=citation,
        plan_subsection=str(raw.get("plan_subsection", "")),
        description=str(raw.get("description", "")).strip(),
        ci_95_plan=ci_plan,
    )


def load_prior_set(path: str | Path) -> PriorSet:
    """Load and validate a prior YAML file."""
    p = Path(path)
    with p.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    for required in ("name", "plan_section", "plan_version", "parameters"):
        if required not in raw:
            raise PriorValidationError(
                f"Prior file {p} is missing required top-level field '{required}'"
            )

    raw_params = raw["parameters"]
    missing = set(PARAMETER_NAMES) - set(raw_params)
    if missing:
        raise PriorValidationError(
            f"Prior file {p} is missing parameters: {sorted(missing)}"
        )

    parameters = {
        name: _validate_prior(name, raw_params[name], require_ci=True)
        for name in PARAMETER_NAMES
    }

    omission: dict[str, Prior] = {}
    for name, raw_p in (raw.get("omission_adjustments") or {}).items():
        # Omission adjustments do not need to publish a CI in the plan.
        omission[name] = _validate_prior(name, raw_p, require_ci=False)

    return PriorSet(
        name=str(raw["name"]),
        plan_section=str(raw["plan_section"]),
        plan_version=str(raw["plan_version"]),
        description=str(raw.get("description", "")).strip(),
        parameters=parameters,
        omission_adjustments=omission,
        source_path=p,
    )


def load_all_prior_sets(priors_dir: str | Path) -> dict[str, PriorSet]:
    """Load every ``*.yaml`` file under ``priors_dir`` keyed by its ``name`` field."""
    d = Path(priors_dir)
    out: dict[str, PriorSet] = {}
    for path in sorted(d.glob("*.yaml")):
        ps = load_prior_set(path)
        if ps.name in out:
            raise PriorValidationError(
                f"Duplicate prior set name '{ps.name}' (in {path} and "
                f"{out[ps.name].source_path})"
            )
        out[ps.name] = ps
    return out
