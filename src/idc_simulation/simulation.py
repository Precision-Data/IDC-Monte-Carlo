"""Monte Carlo simulation core (ANALYSIS_PLAN.md Section 5).

Draws K joint samples from each prior set, evaluates the contamination
function at each pre-specified horizon, and writes one canonical
Parquet output file with one row per (prior_set, sample_index, horizon,
error_type). All aggregation downstream of this file (analyses,
tables, figures) reads the Parquet and never re-runs the simulation.

Determinism contract (Section 5.3):

  - Sampling uses a single ``numpy.random.default_rng(seed)``.
  - Samples are drawn in a fixed order:
        for each prior_set in sorted name order:
            E0_base, epsilon_base, P_base, R_base, epsilon_omission
  - The omission scenario reuses the base E0, P, R samples and only
    swaps the epsilon draws for the omission-adjusted distribution.
  - With the same seed, the same priors, and the same K, the output
    Parquet is bit-identical (verified by SHA256 in the run log).

The principal seed is 20260502 (the plan's deposit date). Convergence
is checked by replicating with seed 20260503 and demanding agreement of
the 5th, 50th, and 95th percentiles to within 1%.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .contamination import contamination
from .priors import PARAMETER_NAMES, PriorSet
from .run_log import attach_output_file, create_run_log, write_run_log

# Pre-specified horizons (Section 7.1).
DEFAULT_HORIZONS: tuple[int, ...] = (1, 5, 10, 20)

# Default principal seed (Section 5.3).
PRINCIPAL_SEED: int = 20260502

# Default sample count (Section 5.1).
DEFAULT_K: int = 10_000

# Default plan version executed by this simulation. Bump on plan
# revision via DEVIATIONS.md (Section 10).
DEFAULT_PLAN_VERSION: str = "2.0"

ERROR_TYPES: tuple[str, ...] = ("commission", "omission")


@dataclass(frozen=True)
class SimulationResult:
    """Locations and metadata for one simulation run."""

    output_path: Path
    run_log_path: Path
    run_log: dict
    n_rows: int


def _draw_samples(
    rng: np.random.Generator,
    prior_set: PriorSet,
    K: int,
) -> dict[str, np.ndarray]:
    """Draw K samples per parameter from the base prior set + omission epsilon.

    Sampling order is fixed: E0, epsilon (commission), P, R, then the
    omission-adjusted epsilon. Reordering would change the byte-for-byte
    output for the same seed.
    """
    samples: dict[str, np.ndarray] = {}
    for pname in PARAMETER_NAMES:
        p = prior_set.get(pname)
        samples[pname] = rng.beta(p.alpha, p.beta, size=K)

    # Omission-adjusted epsilon (Section 4.2): independent draw, fresh
    # samples from the shifted Beta distribution. E0, P, R reused.
    omission_eps_prior = prior_set.omission_adjustments.get("epsilon")
    if omission_eps_prior is None:
        raise ValueError(
            f"Prior set '{prior_set.name}' is missing omission epsilon"
        )
    samples["epsilon_omission"] = rng.beta(
        omission_eps_prior.alpha, omission_eps_prior.beta, size=K
    )
    return samples


def _evaluate_long(
    prior_set_name: str,
    samples: Mapping[str, np.ndarray],
    horizons: Sequence[int],
) -> pd.DataFrame:
    """Build the long-format DataFrame for one prior set."""
    K = samples["E0"].size
    horizons_arr = np.asarray(horizons, dtype=np.int64)
    H = horizons_arr.size

    # Broadcast: parameters shape (K, 1), horizons shape (1, H)
    E0 = samples["E0"][:, None]
    P = samples["P"][:, None]
    R = samples["R"][:, None]
    n = horizons_arr[None, :]

    eps_comm = samples["epsilon"][:, None]
    eps_om = samples["epsilon_omission"][:, None]

    cont_comm = contamination(E0=E0, epsilon=eps_comm, P=P, R=R, n=n)
    cont_om = contamination(E0=E0, epsilon=eps_om, P=P, R=R, n=n)

    sample_idx = np.arange(K, dtype=np.int64)
    rows = []
    for et, eps_arr, cont_arr in (
        ("commission", samples["epsilon"], cont_comm),
        ("omission", samples["epsilon_omission"], cont_om),
    ):
        df = pd.DataFrame(
            {
                "prior_set": np.repeat(prior_set_name, K * H),
                "error_type": np.repeat(et, K * H),
                "sample_index": np.repeat(sample_idx, H),
                "horizon": np.tile(horizons_arr, K),
                "E0": np.repeat(samples["E0"], H),
                "epsilon": np.repeat(eps_arr, H),
                "P": np.repeat(samples["P"], H),
                "R": np.repeat(samples["R"], H),
                "contamination": cont_arr.reshape(-1),
            }
        )
        rows.append(df)
    return pd.concat(rows, ignore_index=True)


def run_simulation(
    prior_sets: Mapping[str, PriorSet],
    *,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    K: int = DEFAULT_K,
    seed: int = PRINCIPAL_SEED,
    prespecified: bool = True,
    plan_version: str = DEFAULT_PLAN_VERSION,
    output_dir: str | Path = "outputs",
    runs_dir: str | Path = "runs",
    repo_root: str | Path | None = None,
    output_filename: str | None = None,
) -> SimulationResult:
    """Run the full prior predictive simulation and write outputs.

    Iterates over the supplied prior sets in sorted name order, draws
    K joint samples per set with the determinism contract above,
    evaluates the contamination function at each horizon for both error
    types, and writes one Parquet file containing all rows.

    Returns a :class:`SimulationResult` with paths to the canonical
    output file and the accompanying run log.
    """
    output_dir = Path(output_dir)
    runs_dir = Path(runs_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    runs_dir.mkdir(parents=True, exist_ok=True)

    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    repo_root = Path(repo_root)

    rng = np.random.default_rng(seed)
    frames: list[pd.DataFrame] = []
    for name in sorted(prior_sets):
        prior_set = prior_sets[name]
        samples = _draw_samples(rng, prior_set, K)
        frames.append(_evaluate_long(name, samples, horizons))
    df = pd.concat(frames, ignore_index=True)

    # Stable column order for the canonical Parquet output.
    df = df[
        [
            "prior_set",
            "error_type",
            "sample_index",
            "horizon",
            "E0",
            "epsilon",
            "P",
            "R",
            "contamination",
        ]
    ]

    if output_filename is None:
        output_filename = f"contamination_seed{seed}_K{K}.parquet"
    out_path = output_dir / output_filename

    # Write deterministically: explicit pyarrow Table, no metadata that
    # carries a timestamp into the file body.
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        table,
        out_path,
        compression="snappy",
        use_dictionary=True,
        write_statistics=False,
    )

    # Build and write the run log.
    log = create_run_log(
        seed=seed,
        K=K,
        prespecified=prespecified,
        plan_version=plan_version,
        repo_root=repo_root,
        extra={
            "horizons": list(horizons),
            "prior_sets": sorted(prior_sets),
            "error_types": list(ERROR_TYPES),
        },
    )
    attach_output_file(log, out_path, description="canonical contamination samples")
    log_path = write_run_log(log, runs_dir)

    return SimulationResult(
        output_path=out_path,
        run_log_path=log_path,
        run_log=log,
        n_rows=len(df),
    )
