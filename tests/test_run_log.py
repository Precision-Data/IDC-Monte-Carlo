"""Tests for ``idc_simulation.run_log``.

Verifies the log structure, that every Section 6.2 field is populated,
that file hashing is deterministic, and that the written JSON is
schema-stable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from idc_simulation.run_log import (
    TRACKED_DEPENDENCIES,
    attach_output_file,
    create_run_log,
    sha256_dataframe_content,
    sha256_file,
    write_run_log,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Section 6.2 structural requirements
# ---------------------------------------------------------------------------


def test_create_run_log_has_all_section_6_2_fields() -> None:
    log = create_run_log(
        seed=20260502, K=10000, prespecified=True, plan_version="1.1", repo_root=REPO_ROOT
    )
    # Section 6.2 required fields:
    assert "timestamp_utc" in log
    assert "seed" in log and log["seed"] == 20260502
    assert "K" in log and log["K"] == 10000
    assert "dependencies" in log and isinstance(log["dependencies"], dict)
    assert "platform" in log
    assert "git_commit" in log
    assert "outputs" in log and log["outputs"] == []
    assert "prespecified" in log and log["prespecified"] is True


def test_dependency_versions_include_all_tracked() -> None:
    log = create_run_log(
        seed=1, K=10, prespecified=False, plan_version="1.1", repo_root=REPO_ROOT
    )
    for name in TRACKED_DEPENDENCIES:
        assert name in log["dependencies"]
        # Each version is either a real version string or 'not-installed'
        assert log["dependencies"][name]


def test_platform_info_populated() -> None:
    log = create_run_log(
        seed=1, K=10, prespecified=False, plan_version="1.1", repo_root=REPO_ROOT
    )
    plat = log["platform"]
    for key in ("platform", "machine", "processor", "python", "hostname"):
        assert key in plat and plat[key]


def test_timestamp_is_iso_utc() -> None:
    log = create_run_log(
        seed=1, K=10, prespecified=False, plan_version="1.1", repo_root=REPO_ROOT
    )
    ts = log["timestamp_utc"]
    # YYYY-MM-DDTHH:MM:SSZ
    assert len(ts) == 20 and ts.endswith("Z") and ts[10] == "T"


def test_git_commit_is_hex_or_unknown() -> None:
    log = create_run_log(
        seed=1, K=10, prespecified=False, plan_version="1.1", repo_root=REPO_ROOT
    )
    commit = log["git_commit"]
    if commit != "unknown":
        assert len(commit) == 40
        int(commit, 16)  # hex-decodable


# ---------------------------------------------------------------------------
# Output attachment and hashing
# ---------------------------------------------------------------------------


def test_sha256_file_is_deterministic(tmp_path: Path) -> None:
    p = tmp_path / "data.bin"
    p.write_bytes(b"some bytes for the IDC monte carlo run")
    h1 = sha256_file(p)
    h2 = sha256_file(p)
    assert h1 == h2
    assert len(h1) == 64


def test_attach_output_file_records_size_and_hash(tmp_path: Path) -> None:
    p = tmp_path / "out.parquet"
    p.write_bytes(b"x" * 256)
    log = create_run_log(
        seed=1, K=10, prespecified=False, plan_version="1.1", repo_root=REPO_ROOT
    )
    attach_output_file(log, p, description="canonical sim output")
    assert len(log["outputs"]) == 1
    o = log["outputs"][0]
    assert o["path"] == str(p)
    assert o["size_bytes"] == 256
    assert len(o["sha256"]) == 64
    assert o["description"] == "canonical sim output"


def test_attach_missing_file_raises(tmp_path: Path) -> None:
    log = create_run_log(
        seed=1, K=10, prespecified=False, plan_version="1.1", repo_root=REPO_ROOT
    )
    with pytest.raises(FileNotFoundError):
        attach_output_file(log, tmp_path / "nope.parquet")


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def test_content_hash_invariant_to_row_order(tmp_path: Path) -> None:
    """Content hash is computed after canonical sort, so row-order
    permutations of the same Parquet should hash identically.
    """
    import pandas as pd

    df = pd.DataFrame(
        {
            "prior_set": ["a", "a", "b", "b"],
            "error_type": ["x", "y", "x", "y"],
            "sample_index": [0, 1, 0, 1],
            "horizon": [1, 1, 1, 1],
            "value": [0.1, 0.2, 0.3, 0.4],
        }
    )
    p1 = tmp_path / "ordered.parquet"
    p2 = tmp_path / "shuffled.parquet"
    df.to_parquet(p1)
    df.iloc[[2, 0, 3, 1]].to_parquet(p2)
    assert sha256_dataframe_content(p1) == sha256_dataframe_content(p2)


def test_content_hash_changes_with_data(tmp_path: Path) -> None:
    import pandas as pd

    df = pd.DataFrame(
        {
            "prior_set": ["a"],
            "error_type": ["x"],
            "sample_index": [0],
            "horizon": [1],
            "value": [0.1],
        }
    )
    p1 = tmp_path / "v1.parquet"
    p2 = tmp_path / "v2.parquet"
    df.to_parquet(p1)
    df.assign(value=[0.2]).to_parquet(p2)
    assert sha256_dataframe_content(p1) != sha256_dataframe_content(p2)


def test_write_run_log_round_trip(tmp_path: Path) -> None:
    log = create_run_log(
        seed=20260502, K=10000, prespecified=True, plan_version="1.1", repo_root=REPO_ROOT
    )
    out = write_run_log(log, tmp_path)
    assert out.is_file()
    assert out.parent == tmp_path
    assert "seed20260502" in out.name
    parsed = json.loads(out.read_text())
    assert parsed["seed"] == 20260502
    assert parsed["K"] == 10000
    assert parsed["prespecified"] is True
