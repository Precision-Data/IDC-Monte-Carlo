"""Command-line entry point for the IDC Monte Carlo simulation.

Two subcommands:

  ``idc-simulation run``      Execute the principal simulation: draws
                              K samples per prior set, evaluates the
                              contamination function at each horizon,
                              writes the canonical Parquet output and
                              its accompanying run log.

  ``idc-simulation analyse``  Read an existing canonical Parquet file
                              and write the manuscript tables and
                              figures (Section 7) with each output
                              hash attached to the run log.

  ``idc-simulation all``      Run the simulation followed by analysis
                              in one invocation. Default behaviour for
                              the principal end-to-end pipeline.

Defaults match the values pre-specified in the plan: K = 10,000,
seed = 20260502 (the principal seed of Section 5.3), all three prior
sets, prespecified = True. Override only when running an exploratory
configuration; the run log records the prespecified flag explicitly so
exploratory output can be distinguished in the audit trail.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from .priors import load_all_prior_sets, load_prior_set
from .reporting import write_all_outputs
from .run_log import write_run_log
from .simulation import (
    DEFAULT_HORIZONS,
    DEFAULT_K,
    DEFAULT_PLAN_VERSION,
    PRINCIPAL_SEED,
    run_simulation,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idc-simulation",
        description=(
            "IDC Monte Carlo prior predictive simulation. See "
            "ANALYSIS_PLAN.md for the authoritative specification."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--priors-dir",
        type=Path,
        default=Path("priors"),
        help="Directory containing prior YAML files (default: ./priors)",
    )
    common.add_argument(
        "--weights-path",
        type=Path,
        default=Path("weights/severity_weights.yaml"),
        help="Path to severity_weights.yaml (default: ./weights/severity_weights.yaml)",
    )
    common.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Directory for canonical Parquet, tables, and figures (default: ./outputs)",
    )
    common.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("runs"),
        help="Directory for structured run logs (default: ./runs)",
    )
    common.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root for git-commit lookup (default: cwd)",
    )

    run_p = sub.add_parser("run", parents=[common], help="Run the principal simulation")
    run_p.add_argument(
        "--prior-set",
        action="append",
        help=(
            "Prior set name to include. May be repeated. "
            "If omitted, all YAML files under --priors-dir are used."
        ),
    )
    run_p.add_argument(
        "--K", type=int, default=DEFAULT_K, help=f"Sample count (default: {DEFAULT_K})"
    )
    run_p.add_argument(
        "--seed",
        type=int,
        default=PRINCIPAL_SEED,
        help=f"Random seed (default: {PRINCIPAL_SEED}, the principal seed)",
    )
    run_p.add_argument(
        "--exploratory",
        action="store_true",
        help="Mark the run as exploratory (default: prespecified=True)",
    )
    run_p.add_argument(
        "--plan-version",
        default=DEFAULT_PLAN_VERSION,
        help=f"Plan version executed (default: {DEFAULT_PLAN_VERSION})",
    )
    run_p.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=list(DEFAULT_HORIZONS),
        help=f"Horizons to evaluate (default: {list(DEFAULT_HORIZONS)})",
    )

    ana_p = sub.add_parser(
        "analyse",
        parents=[common],
        help="Render Section 7 tables and figures from an existing Parquet",
    )
    ana_p.add_argument(
        "parquet_path",
        type=Path,
        help="Path to a canonical contamination Parquet file",
    )

    all_p = sub.add_parser(
        "all",
        parents=[common],
        help="Run the principal simulation and immediately render outputs",
    )
    all_p.add_argument("--K", type=int, default=DEFAULT_K)
    all_p.add_argument("--seed", type=int, default=PRINCIPAL_SEED)
    all_p.add_argument("--exploratory", action="store_true")
    all_p.add_argument("--plan-version", default=DEFAULT_PLAN_VERSION)
    all_p.add_argument("--horizons", type=int, nargs="+", default=list(DEFAULT_HORIZONS))
    all_p.add_argument(
        "--prior-set",
        action="append",
        help="Prior set name to include (repeatable). Default: all under --priors-dir.",
    )

    return parser


def _select_prior_sets(args: argparse.Namespace) -> dict:
    if args.prior_set:
        sets = {}
        for name in args.prior_set:
            path = args.priors_dir / f"{name}.yaml"
            sets[name] = load_prior_set(path)
        return sets
    return load_all_prior_sets(args.priors_dir)


def _cmd_run(args: argparse.Namespace) -> int:
    sets = _select_prior_sets(args)
    res = run_simulation(
        sets,
        K=args.K,
        seed=args.seed,
        prespecified=not args.exploratory,
        plan_version=args.plan_version,
        horizons=tuple(args.horizons),
        output_dir=args.output_dir,
        runs_dir=args.runs_dir,
        repo_root=args.repo_root,
    )
    print(f"Wrote {res.n_rows:,} rows to {res.output_path}")
    print(f"Run log: {res.run_log_path}")
    return 0


def _cmd_analyse(args: argparse.Namespace) -> int:
    if not args.parquet_path.is_file():
        print(f"Parquet not found: {args.parquet_path}", file=sys.stderr)
        return 2
    write_all_outputs(
        args.parquet_path,
        weights_path=args.weights_path,
        output_dir=args.output_dir,
        run_log=None,
    )
    print(
        f"Wrote tables to {args.output_dir / 'tables'} and figures to "
        f"{args.output_dir / 'figures'}"
    )
    return 0


def _cmd_all(args: argparse.Namespace) -> int:
    sets = _select_prior_sets(args)
    res = run_simulation(
        sets,
        K=args.K,
        seed=args.seed,
        prespecified=not args.exploratory,
        plan_version=args.plan_version,
        horizons=tuple(args.horizons),
        output_dir=args.output_dir,
        runs_dir=args.runs_dir,
        repo_root=args.repo_root,
    )
    write_all_outputs(
        res.output_path,
        weights_path=args.weights_path,
        output_dir=args.output_dir,
        run_log=res.run_log,
    )
    # Re-write the run log so the attached output hashes are persisted.
    log_path = write_run_log(res.run_log, args.runs_dir, name_prefix="run_with_outputs")
    print(f"Wrote {res.n_rows:,} rows to {res.output_path}")
    print(f"Tables under {args.output_dir / 'tables'}; figures under {args.output_dir / 'figures'}")
    print(f"Run log (with output hashes): {log_path}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "run":
        return _cmd_run(args)
    if args.command == "analyse":
        return _cmd_analyse(args)
    if args.command == "all":
        return _cmd_all(args)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
