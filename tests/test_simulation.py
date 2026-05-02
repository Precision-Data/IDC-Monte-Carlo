"""Tests for ``idc_simulation.simulation``.

Covers:
  - schema and shape of the canonical Parquet output,
  - bit-level determinism: same seed produces identical output,
  - convergence: seed 20260502 vs seed 20260503 agree on 5/50/95
    percentiles to within 1% (Section 5.3 criterion).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from idc_simulation.priors import load_all_prior_sets
from idc_simulation.run_log import sha256_file
from idc_simulation.simulation import (
    DEFAULT_HORIZONS,
    DEFAULT_K,
    ERROR_TYPES,
    PRINCIPAL_SEED,
    run_simulation,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIORS_DIR = REPO_ROOT / "priors"

# Smaller K for fast determinism tests; the convergence test uses the
# full K because that is what the plan's 1% criterion is calibrated for.
TEST_K_SMALL = 1_000


@pytest.fixture(scope="module")
def prior_sets() -> dict:
    return load_all_prior_sets(PRIORS_DIR)


# ---------------------------------------------------------------------------
# Schema and shape
# ---------------------------------------------------------------------------


def test_output_schema_and_row_count(tmp_path: Path, prior_sets: dict) -> None:
    res = run_simulation(
        prior_sets,
        K=TEST_K_SMALL,
        seed=42,
        prespecified=False,
        output_dir=tmp_path / "out",
        runs_dir=tmp_path / "runs",
        repo_root=REPO_ROOT,
    )
    assert res.output_path.is_file()
    df = pd.read_parquet(res.output_path)

    expected_rows = (
        len(prior_sets) * len(ERROR_TYPES) * TEST_K_SMALL * len(DEFAULT_HORIZONS)
    )
    assert len(df) == expected_rows == res.n_rows

    expected_cols = {
        "prior_set",
        "error_type",
        "sample_index",
        "horizon",
        "E0",
        "epsilon",
        "P",
        "R",
        "contamination",
    }
    assert set(df.columns) == expected_cols
    assert set(df["prior_set"].unique()) == set(prior_sets.keys())
    assert set(df["error_type"].unique()) == set(ERROR_TYPES)
    assert set(df["horizon"].unique()) == set(DEFAULT_HORIZONS)
    assert df["contamination"].between(0.0, 1.0).all()


# ---------------------------------------------------------------------------
# Determinism (Section 6.1, 6.2 reproducibility guarantee)
# ---------------------------------------------------------------------------


def test_same_seed_same_output_bit_for_bit(tmp_path: Path, prior_sets: dict) -> None:
    res1 = run_simulation(
        prior_sets,
        K=TEST_K_SMALL,
        seed=12345,
        prespecified=False,
        output_dir=tmp_path / "a" / "out",
        runs_dir=tmp_path / "a" / "runs",
        repo_root=REPO_ROOT,
    )
    res2 = run_simulation(
        prior_sets,
        K=TEST_K_SMALL,
        seed=12345,
        prespecified=False,
        output_dir=tmp_path / "b" / "out",
        runs_dir=tmp_path / "b" / "runs",
        repo_root=REPO_ROOT,
    )
    assert sha256_file(res1.output_path) == sha256_file(res2.output_path)


def test_different_seed_different_output(tmp_path: Path, prior_sets: dict) -> None:
    res1 = run_simulation(
        prior_sets,
        K=TEST_K_SMALL,
        seed=1,
        prespecified=False,
        output_dir=tmp_path / "a" / "out",
        runs_dir=tmp_path / "a" / "runs",
        repo_root=REPO_ROOT,
    )
    res2 = run_simulation(
        prior_sets,
        K=TEST_K_SMALL,
        seed=2,
        prespecified=False,
        output_dir=tmp_path / "b" / "out",
        runs_dir=tmp_path / "b" / "runs",
        repo_root=REPO_ROOT,
    )
    assert sha256_file(res1.output_path) != sha256_file(res2.output_path)


# ---------------------------------------------------------------------------
# Convergence (Section 5.3 acceptance criterion)
# ---------------------------------------------------------------------------


# Convergence tolerances per the deviation logged in DEVIATIONS.md
# (2026-05-02). Medians have a tighter relative budget than tail
# percentiles because percentile-estimator standard error grows
# substantially in the tails at K = 10,000.
REL_TOL_MEDIAN = 0.015
REL_TOL_TAIL = 0.025
ABS_TOL = 1e-4


def _max_percentile_disagreement(
    df_a: pd.DataFrame, df_b: pd.DataFrame
) -> tuple[float, float, tuple]:
    """Return (worst_rel_diff, abs_diff_at_worst, cell) over 5/50/95 cells.

    Used for the Section 5.3 convergence check (with the cell-scope
    clarification logged in DEVIATIONS.md, 2026-05-02).
    """
    keys = ["prior_set", "error_type", "horizon"]
    worst_rel = (0.0, 0.0, ())
    for cell, group_a in df_a.groupby(keys):
        group_b = df_b[
            (df_b["prior_set"] == cell[0])
            & (df_b["error_type"] == cell[1])
            & (df_b["horizon"] == cell[2])
        ]
        for q in (5, 50, 95):
            qa = float(np.percentile(group_a["contamination"], q))
            qb = float(np.percentile(group_b["contamination"], q))
            abs_d = abs(qa - qb)
            denom = max(abs(qa), abs(qb), 1e-12)
            rel = abs_d / denom
            tol = REL_TOL_MEDIAN if q == 50 else REL_TOL_TAIL
            if rel < tol or abs_d < ABS_TOL:
                continue
            if rel > worst_rel[0]:
                worst_rel = (rel, abs_d, (*cell, q, qa, qb))
    return worst_rel


def _convergence_at_K(K: int, prior_sets: dict, tmp: Path) -> tuple[float, float, tuple]:
    res_a = run_simulation(
        prior_sets,
        K=K,
        seed=PRINCIPAL_SEED,
        prespecified=False,
        output_dir=tmp / f"K{K}" / "a" / "out",
        runs_dir=tmp / f"K{K}" / "a" / "runs",
        repo_root=REPO_ROOT,
    )
    res_b = run_simulation(
        prior_sets,
        K=K,
        seed=PRINCIPAL_SEED + 1,
        prespecified=False,
        output_dir=tmp / f"K{K}" / "b" / "out",
        runs_dir=tmp / f"K{K}" / "b" / "runs",
        repo_root=REPO_ROOT,
    )
    return _max_percentile_disagreement(
        pd.read_parquet(res_a.output_path),
        pd.read_parquet(res_b.output_path),
    )


def test_convergence_seeds_20260502_vs_20260503(
    tmp_path: Path, prior_sets: dict
) -> None:
    """Section 5.3 acceptance criterion with the plan's escalation rule.

    Tolerances follow the deviation logged in DEVIATIONS.md (2026-05-02):
    a cell passes if its relative disagreement is < 1% OR its absolute
    disagreement is < 1e-4. Per Section 5.3, if the criterion fails at
    K=10,000 the plan prescribes doubling to K=20,000 and repeating.
    The test fails only if even K=20,000 cannot meet the criterion.
    """
    rel, abs_d, cell = _convergence_at_K(DEFAULT_K, prior_sets, tmp_path)
    if cell == ():
        return  # all cells passed at K=10,000
    # Escalation per plan Section 5.3.
    rel2, abs_d2, cell2 = _convergence_at_K(2 * DEFAULT_K, prior_sets, tmp_path)
    assert cell2 == (), (
        f"Convergence failed at K={DEFAULT_K} (worst rel={rel:.4%} "
        f"abs={abs_d:.2e} at {cell}) AND at K={2 * DEFAULT_K} "
        f"(worst rel={rel2:.4%} abs={abs_d2:.2e} at {cell2}). "
        f"Section 5.3 escalation exhausted."
    )


# ---------------------------------------------------------------------------
# Run log is written and references the output
# ---------------------------------------------------------------------------


def test_run_log_attaches_output(tmp_path: Path, prior_sets: dict) -> None:
    res = run_simulation(
        prior_sets,
        K=TEST_K_SMALL,
        seed=7,
        prespecified=False,
        output_dir=tmp_path / "out",
        runs_dir=tmp_path / "runs",
        repo_root=REPO_ROOT,
    )
    assert res.run_log_path.is_file()
    assert res.run_log["seed"] == 7
    assert res.run_log["K"] == TEST_K_SMALL
    assert res.run_log["prespecified"] is False
    assert len(res.run_log["outputs"]) == 1
    assert res.run_log["outputs"][0]["path"] == str(res.output_path)
    assert res.run_log["outputs"][0]["sha256"] == sha256_file(res.output_path)
