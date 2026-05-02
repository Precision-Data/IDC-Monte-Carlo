"""Structured run-log infrastructure (ANALYSIS_PLAN.md Section 6.2).

Every simulation run produces a JSON log file under ``runs/`` capturing:

  - ISO 8601 UTC timestamp,
  - random seed,
  - K (number of samples),
  - the version of every major dependency,
  - operating system and CPU identifier,
  - the git commit hash of the simulation code,
  - the SHA256 hash of each output file produced,
  - the pre-specified vs exploratory designation.

These fields are exactly the set required by Section 6.2 of the plan.
The plan forbids reporting any simulation result in the manuscript
without an accompanying run log; the simulation entry-point uses
:func:`write_run_log` to make that guarantee mechanical.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

# Major dependencies whose versions are recorded in every run log.
TRACKED_DEPENDENCIES: tuple[str, ...] = (
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "pyyaml",
    "pyarrow",
    "idc-simulation",
)

# Bytes read at a time when hashing output files. 1 MiB is comfortable
# for Parquet outputs (low tens of MB at K=10,000).
_HASH_CHUNK_BYTES: int = 1 << 20


def _utc_timestamp() -> str:
    """Return current UTC time as an ISO 8601 string with Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _dep_versions() -> dict[str, str]:
    """Resolve installed versions of the tracked dependencies."""
    out: dict[str, str] = {}
    for name in TRACKED_DEPENDENCIES:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            out[name] = "not-installed"
    return out


def _git_commit_hash(repo_root: Path) -> str:
    """Return the git HEAD commit hash for ``repo_root``, or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"


def _git_dirty(repo_root: Path) -> bool:
    """Return True if the working tree has uncommitted changes."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _platform_info() -> dict[str, str]:
    """OS and CPU identifiers."""
    return {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "python": sys.version.split()[0],
        "hostname": socket.gethostname(),
    }


def sha256_file(path: str | Path) -> str:
    """Return the SHA256 hex digest of the file at ``path``."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_HASH_CHUNK_BYTES), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dataframe_content(
    parquet_path: str | Path,
    *,
    sort_keys: tuple[str, ...] = (
        "prior_set",
        "error_type",
        "sample_index",
        "horizon",
    ),
    float_precision: int = 15,
) -> str:
    """Return a platform-invariant SHA256 over the contents of a Parquet file.

    Reads the file with pandas, sorts by the supplied keys for stable
    row order, formats every float column with ``float_precision`` digits
    of significand, and serialises to CSV with a newline-only line
    terminator. The resulting byte stream depends only on the data
    values, not on Parquet metadata, dictionary encoding, compression,
    or platform-specific writer state. Suitable for CI reproducibility
    checks that need to compare numerical output across operating
    systems and CPU architectures.
    """
    import pandas as pd  # local import to keep run_log import-light

    df = pd.read_parquet(parquet_path)
    df = df.sort_values(list(sort_keys)).reset_index(drop=True)
    fmt = f"%.{float_precision}g"
    csv_bytes = df.to_csv(index=False, lineterminator="\n", float_format=fmt).encode(
        "utf-8"
    )
    return hashlib.sha256(csv_bytes).hexdigest()


def create_run_log(
    *,
    seed: int,
    K: int,
    prespecified: bool,
    plan_version: str,
    repo_root: Path,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the in-memory run log.

    Parameters
    ----------
    seed
        The random seed used to draw the joint samples.
    K
        Number of joint samples drawn per prior set.
    prespecified
        ``True`` for runs against the principal seed and pre-specified
        configuration; ``False`` for exploratory runs.
    plan_version
        The version string of the analysis plan being executed (e.g. "1.1").
    repo_root
        Path to the simulation repository root (for git commit lookup).
    extra
        Optional additional metadata merged into the log.
    """
    log: dict[str, Any] = {
        "schema_version": "1",
        "timestamp_utc": _utc_timestamp(),
        "seed": int(seed),
        "K": int(K),
        "prespecified": bool(prespecified),
        "plan_version": str(plan_version),
        "git_commit": _git_commit_hash(repo_root),
        "git_dirty": _git_dirty(repo_root),
        "dependencies": _dep_versions(),
        "platform": _platform_info(),
        "outputs": [],  # filled by attach_output_file
    }
    if extra:
        log["extra"] = dict(extra)
    return log


def attach_output_file(
    run_log: dict[str, Any],
    path: str | Path,
    *,
    description: str = "",
) -> None:
    """Hash an output file and record it in the run log."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Cannot attach non-existent output: {p}")
    run_log["outputs"].append(
        {
            "path": str(p),
            "size_bytes": p.stat().st_size,
            "sha256": sha256_file(p),
            "description": description,
        }
    )


def write_run_log(
    run_log: dict[str, Any],
    runs_dir: str | Path,
    *,
    name_prefix: str = "run",
) -> Path:
    """Write the run log to ``runs_dir`` as a JSON file.

    Returns the absolute path to the written log. The filename combines
    the timestamp and the seed for uniqueness across replicates of the
    same configuration.
    """
    runs_dir = Path(runs_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)
    safe_ts = run_log["timestamp_utc"].replace(":", "").replace("-", "")
    filename = f"{name_prefix}_{safe_ts}_seed{run_log['seed']}.json"
    out_path = runs_dir / filename
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(run_log, fh, indent=2, sort_keys=True)
        fh.write(os.linesep)
    return out_path
