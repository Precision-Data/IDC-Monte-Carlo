"""Tests for ``idc_simulation.priors``.

Covers the happy path (loading the three committed prior sets) and each
documented failure mode of the validator.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from idc_simulation.priors import (
    PARAMETER_NAMES,
    Prior,
    PriorSet,
    PriorValidationError,
    load_all_prior_sets,
    load_prior_set,
)

PRIORS_DIR = Path(__file__).resolve().parent.parent / "priors"


# ---------------------------------------------------------------------------
# Happy-path: each committed prior set loads and exposes the four parameters
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["optimistic", "moderate", "pessimistic"])
def test_committed_prior_sets_load(name: str) -> None:
    ps = load_prior_set(PRIORS_DIR / f"{name}.yaml")
    assert ps.name == name
    assert ps.plan_version == "1.1"
    assert set(ps.parameters) == set(PARAMETER_NAMES)
    for p in ps.parameters.values():
        assert isinstance(p, Prior)
        assert p.alpha > 0 and p.beta > 0
        assert p.citation, "citation must not be empty"


def test_load_all_prior_sets_returns_three() -> None:
    sets = load_all_prior_sets(PRIORS_DIR)
    assert set(sets) == {"optimistic", "moderate", "pessimistic"}


def test_omission_adjustment_present_in_each_set() -> None:
    for name in ("optimistic", "moderate", "pessimistic"):
        ps = load_prior_set(PRIORS_DIR / f"{name}.yaml")
        assert "epsilon" in ps.omission_adjustments
        assert ps.omission_adjustments["epsilon"].mean > ps.parameters["epsilon"].mean


def test_with_omission_epsilon_swaps_epsilon() -> None:
    ps = load_prior_set(PRIORS_DIR / "moderate.yaml")
    swapped = ps.with_omission_epsilon()
    assert swapped.parameters["epsilon"].mean == ps.omission_adjustments["epsilon"].mean
    assert swapped.parameters["E0"].alpha == ps.parameters["E0"].alpha
    assert swapped.name == "moderate__omission"


# ---------------------------------------------------------------------------
# Failure modes (each raises PriorValidationError)
# ---------------------------------------------------------------------------


def _make_minimal_prior_set(tmp_path: Path, mutate=lambda d: None) -> Path:
    """Write a valid moderate-style prior YAML, optionally mutated, to tmp_path."""
    base = yaml.safe_load((PRIORS_DIR / "moderate.yaml").read_text())
    mutate(base)
    out = tmp_path / "test.yaml"
    out.write_text(yaml.safe_dump(base))
    return out


def test_invalid_alpha_raises(tmp_path: Path) -> None:
    def mutate(d):
        d["parameters"]["E0"]["alpha"] = 0.0
        d["parameters"]["E0"]["beta"] = 100.0
        d["parameters"]["E0"]["mean"] = 0.0
        d["parameters"]["E0"]["precision"] = 100.0

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="alpha must be > 0"):
        load_prior_set(p)


def test_invalid_beta_raises(tmp_path: Path) -> None:
    def mutate(d):
        d["parameters"]["E0"]["beta"] = -1.0

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="beta must be > 0"):
        load_prior_set(p)


def test_mean_mismatch_raises(tmp_path: Path) -> None:
    def mutate(d):
        d["parameters"]["E0"]["mean"] = 0.5  # plan: 0.025

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="stated mean"):
        load_prior_set(p)


def test_precision_mismatch_raises(tmp_path: Path) -> None:
    def mutate(d):
        d["parameters"]["E0"]["precision"] = 999.0  # plan: 500

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="stated precision"):
        load_prior_set(p)


def test_ci_mismatch_raises(tmp_path: Path) -> None:
    def mutate(d):
        d["parameters"]["E0"]["ci_95_plan"] = [0.5, 0.6]

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="quantile"):
        load_prior_set(p)


def test_missing_citation_raises(tmp_path: Path) -> None:
    def mutate(d):
        d["parameters"]["E0"]["citation"] = ""

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="citation"):
        load_prior_set(p)


def test_missing_required_top_level_raises(tmp_path: Path) -> None:
    def mutate(d):
        del d["plan_version"]

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="plan_version"):
        load_prior_set(p)


def test_missing_parameter_raises(tmp_path: Path) -> None:
    def mutate(d):
        del d["parameters"]["R"]

    p = _make_minimal_prior_set(tmp_path, mutate)
    with pytest.raises(PriorValidationError, match="missing parameters"):
        load_prior_set(p)


def test_with_omission_epsilon_errors_when_unavailable() -> None:
    ps = load_prior_set(PRIORS_DIR / "moderate.yaml")
    bare = PriorSet(
        name=ps.name,
        plan_section=ps.plan_section,
        plan_version=ps.plan_version,
        description=ps.description,
        parameters=ps.parameters,
        omission_adjustments={},
    )
    with pytest.raises(PriorValidationError):
        bare.with_omission_epsilon()
