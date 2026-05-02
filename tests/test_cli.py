"""Smoke tests for the ``idc-simulation`` CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from idc_simulation.cli import main

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_help_returns_zero(capsys) -> None:
    with pytest.raises(SystemExit) as ei:
        main(["--help"])
    assert ei.value.code == 0
    out = capsys.readouterr().out
    assert "idc-simulation" in out


def test_run_subcommand_executes(tmp_path: Path) -> None:
    rc = main(
        [
            "run",
            "--priors-dir", str(REPO_ROOT / "priors"),
            "--weights-path", str(REPO_ROOT / "weights" / "severity_weights.yaml"),
            "--output-dir", str(tmp_path / "out"),
            "--runs-dir", str(tmp_path / "runs"),
            "--repo-root", str(REPO_ROOT),
            "--K", "500",
            "--seed", "1",
            "--exploratory",
        ]
    )
    assert rc == 0
    assert any((tmp_path / "out").glob("*.parquet"))
    assert any((tmp_path / "runs").glob("*.json"))


def test_all_subcommand_writes_tables_and_figures(tmp_path: Path) -> None:
    rc = main(
        [
            "all",
            "--priors-dir", str(REPO_ROOT / "priors"),
            "--weights-path", str(REPO_ROOT / "weights" / "severity_weights.yaml"),
            "--output-dir", str(tmp_path / "out"),
            "--runs-dir", str(tmp_path / "runs"),
            "--repo-root", str(REPO_ROOT),
            "--K", "500",
            "--seed", "1",
            "--exploratory",
        ]
    )
    assert rc == 0
    assert (tmp_path / "out" / "tables" / "table1_primary_summary.csv").is_file()
    assert (tmp_path / "out" / "figures" / "credible_intervals_by_horizon.png").is_file()


def test_run_with_single_prior_set(tmp_path: Path) -> None:
    rc = main(
        [
            "run",
            "--priors-dir", str(REPO_ROOT / "priors"),
            "--weights-path", str(REPO_ROOT / "weights" / "severity_weights.yaml"),
            "--output-dir", str(tmp_path / "out"),
            "--runs-dir", str(tmp_path / "runs"),
            "--repo-root", str(REPO_ROOT),
            "--K", "200",
            "--seed", "1",
            "--exploratory",
            "--prior-set", "moderate",
        ]
    )
    assert rc == 0


def test_analyse_subcommand_consumes_existing_parquet(tmp_path: Path) -> None:
    # First produce a Parquet
    rc1 = main(
        [
            "run",
            "--priors-dir", str(REPO_ROOT / "priors"),
            "--weights-path", str(REPO_ROOT / "weights" / "severity_weights.yaml"),
            "--output-dir", str(tmp_path / "out"),
            "--runs-dir", str(tmp_path / "runs"),
            "--repo-root", str(REPO_ROOT),
            "--K", "300",
            "--seed", "5",
            "--exploratory",
        ]
    )
    assert rc1 == 0
    parquet = next((tmp_path / "out").glob("*.parquet"))
    rc2 = main(
        [
            "analyse",
            "--output-dir", str(tmp_path / "rendered"),
            "--weights-path", str(REPO_ROOT / "weights" / "severity_weights.yaml"),
            str(parquet),
        ]
    )
    assert rc2 == 0
    assert (tmp_path / "rendered" / "tables" / "table1_primary_summary.csv").is_file()
