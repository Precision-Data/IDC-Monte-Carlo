"""Tests for ``idc_simulation.reporting``.

Verifies that tables and figures are written, that the run log is
updated with a hash for each file, and that figure files contain valid
PNG headers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from idc_simulation.priors import load_all_prior_sets
from idc_simulation.reporting import write_all_outputs
from idc_simulation.run_log import sha256_file
from idc_simulation.simulation import run_simulation

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIORS_DIR = REPO_ROOT / "priors"
WEIGHTS_PATH = REPO_ROOT / "weights" / "severity_weights.yaml"


@pytest.fixture(scope="module")
def prior_sets() -> dict:
    return load_all_prior_sets(PRIORS_DIR)


@pytest.fixture(scope="module")
def sim_artifacts(prior_sets, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sim")
    res = run_simulation(
        prior_sets,
        K=2_000,
        seed=42,
        prespecified=False,
        output_dir=tmp / "out",
        runs_dir=tmp / "runs",
        repo_root=REPO_ROOT,
    )
    return res


def test_write_all_outputs_creates_expected_files(sim_artifacts, tmp_path) -> None:
    out_dir = tmp_path / "rendered"
    write_all_outputs(
        sim_artifacts.output_path,
        weights_path=WEIGHTS_PATH,
        output_dir=out_dir,
        run_log=None,
    )
    assert (out_dir / "tables" / "table1_primary_summary.csv").is_file()
    assert (out_dir / "tables" / "table_hospital_scale.csv").is_file()
    assert (out_dir / "tables" / "robustness_summary.json").is_file()
    assert (out_dir / "tables" / "severity_weighting_status.json").is_file()
    assert (out_dir / "figures" / "credible_intervals_by_horizon.png").is_file()
    assert (out_dir / "figures" / "contamination_box_h10.png").is_file()
    # Severity weighting is now enabled in plan v1.2 + the populated YAML;
    # the manuscript Table 3 CSV and the source-of-truth Parquet are
    # both produced.
    assert (out_dir / "tables" / "severity_weighted.csv").is_file()
    assert (out_dir / "severity_weighted.parquet").is_file()


def test_run_log_records_every_output_hash(sim_artifacts, tmp_path) -> None:
    log_before_count = len(sim_artifacts.run_log["outputs"])
    out_dir = tmp_path / "rendered2"
    write_all_outputs(
        sim_artifacts.output_path,
        weights_path=WEIGHTS_PATH,
        output_dir=out_dir,
        run_log=sim_artifacts.run_log,
    )
    # 2 csv tables + 2 json status files + 2 figures + 1 severity csv +
    # 1 severity parquet = 8 attached
    assert len(sim_artifacts.run_log["outputs"]) == log_before_count + 8
    for entry in sim_artifacts.run_log["outputs"][log_before_count:]:
        assert len(entry["sha256"]) == 64
        # Verify hash matches file
        assert sha256_file(entry["path"]) == entry["sha256"]


def test_figure_files_are_valid_png(sim_artifacts, tmp_path) -> None:
    out_dir = tmp_path / "rendered3"
    write_all_outputs(
        sim_artifacts.output_path,
        weights_path=WEIGHTS_PATH,
        output_dir=out_dir,
        run_log=None,
    )
    PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
    for png in (out_dir / "figures").glob("*.png"):
        assert png.read_bytes()[:8] == PNG_MAGIC
