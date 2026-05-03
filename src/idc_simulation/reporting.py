"""Tables and figures for the manuscript (ANALYSIS_PLAN.md Section 7).

Reads from the canonical Parquet output via :mod:`idc_simulation.analyses`
and writes:

  outputs/tables/table1_primary_summary.csv     - Section 7.1 / 7.2
  outputs/tables/table_hospital_scale.csv       - Section 7.5
  outputs/tables/robustness_summary.json        - Section 7.4.d
  outputs/tables/severity_weighting_status.json - Section 7.3 status
  outputs/figures/credible_intervals_by_horizon.png - Section 7.1 visual
  outputs/figures/contamination_box_h10.png     - Section 7.1 visual

Every output is written deterministically and hashed into the supplied
run log via :func:`idc_simulation.run_log.attach_output_file`.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless rendering

import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

# Pin font rendering to matplotlib's bundled DejaVu Sans + the in-package
# math font so figure rendering does not depend on the host system's
# fontconfig database. Some macOS environments fail to resolve even the
# bundled DejaVu Sans through fontconfig; setting these rcParams ensures
# rendering works in CI containers and on developer machines alike.
matplotlib.rcParams["font.family"] = "DejaVu Sans"
matplotlib.rcParams["mathtext.fontset"] = "dejavusans"
matplotlib.rcParams["axes.unicode_minus"] = False

from .analyses import (
    HOSPITAL_HORIZON,
    AnalysisResult,
    analyse_canonical,
)
from .run_log import attach_output_file

FIGURE_DPI: int = 300


def _to_json_safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(_to_json_safe(payload), fh, indent=2, sort_keys=True, default=str)
        fh.write("\n")
    return path


def _write_csv(path: Path, df: pd.DataFrame) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n")
    return path


def _figure_credible_intervals(df_primary: pd.DataFrame, out_path: Path) -> Path:
    """Median + 90% CI of contamination at each horizon, per prior set,
    per regime (v2.0). Two panels: commission (left), omission (right).
    Solid line = uncorrected (principal regime); dashed line = corrected
    (counterfactual regime).
    """
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    colors = {"optimistic": "#2c7bb6", "moderate": "#fdae61", "pessimistic": "#d7191c"}
    regime_styles = {"uncorrected": ("-", "o"), "corrected": ("--", "s")}
    for ax, etype in zip(axes, ("commission", "omission")):
        cell = df_primary[df_primary["error_type"] == etype]
        for ps in ("optimistic", "moderate", "pessimistic"):
            for regime, (ls, marker) in regime_styles.items():
                row = cell[
                    (cell["prior_set"] == ps) & (cell["regime"] == regime)
                ].sort_values("horizon")
                if regime == "uncorrected":
                    ax.fill_between(
                        row["horizon"],
                        row["ci90_low"],
                        row["ci90_high"],
                        color=colors[ps],
                        alpha=0.20,
                    )
                ax.plot(
                    row["horizon"],
                    row["median"],
                    linestyle=ls,
                    marker=marker,
                    color=colors[ps],
                    label=f"{ps} ({regime})",
                )
        ax.set_xlabel("Encounter index n")
        ax.set_title(f"{etype.capitalize()} errors")
        ax.grid(True, alpha=0.3)
    axes[0].set_ylabel("Per-confabulation contamination")
    axes[0].legend(loc="upper left", frameon=False, fontsize=7, ncol=2)
    fig.suptitle(
        "Contamination(n): median and 90% prior credible interval, "
        "uncorrected (solid) vs corrected (dashed)"
    )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=FIGURE_DPI)
    plt.close(fig)
    return out_path


def _figure_box_at_horizon(
    df_canonical: pd.DataFrame, horizon: int, out_path: Path
) -> Path:
    """Boxplot of the contamination distribution at one horizon, both
    regimes shown as adjacent boxes per prior set (v2.0).
    """
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), sharey=True)
    prior_order = ("optimistic", "moderate", "pessimistic")
    for ax, etype in zip(axes, ("commission", "omission")):
        sub = df_canonical[
            (df_canonical["horizon"] == horizon) & (df_canonical["error_type"] == etype)
        ]
        groups = []
        labels = []
        for ps in prior_order:
            for regime in ("uncorrected", "corrected"):
                vals = sub.loc[
                    (sub["prior_set"] == ps) & (sub["regime"] == regime),
                    "contamination",
                ].to_numpy()
                groups.append(vals)
                labels.append(f"{ps[:3]}\n{regime[:5]}")
        ax.boxplot(
            groups,
            tick_labels=labels,
            showfliers=False,
            whis=(5, 95),
        )
        ax.set_yscale("log")
        ax.set_title(f"{etype.capitalize()} errors")
        ax.grid(True, which="both", axis="y", alpha=0.3)
    axes[0].set_ylabel("Per-confabulation contamination (log)")
    fig.suptitle(
        f"Contamination(n={horizon}) by prior set and regime "
        "(box: IQR; whiskers: 5th-95th percentile)"
    )
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=FIGURE_DPI)
    plt.close(fig)
    return out_path


def _write_csv_six_sig_figs(path: Path, df: pd.DataFrame) -> Path:
    """Write a CSV with floats formatted to six significant figures.

    Used for severity-weighted Table 3 so the manuscript table is
    cross-platform stable (the Section 6.3 reproducibility precision).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, lineterminator="\n", float_format="%.6g")
    return path


def write_all_outputs(
    parquet_path: str | Path,
    *,
    weights_path: str | Path,
    output_dir: str | Path,
    run_log: dict[str, Any] | None = None,
) -> AnalysisResult:
    """Run all analyses and write tables + figures under ``output_dir``.

    If ``run_log`` is supplied, every written file is hashed and
    attached to the log via :func:`attach_output_file`.
    """
    parquet_path = Path(parquet_path)
    output_dir = Path(output_dir)
    tables_dir = output_dir / "tables"
    figures_dir = output_dir / "figures"

    result = analyse_canonical(
        parquet_path,
        weights_path=weights_path,
        output_dir=output_dir,
    )

    written: list[tuple[Path, str]] = []

    # Tables
    written.append(
        (
            _write_csv(tables_dir / "table1_primary_summary.csv", result.primary),
            "Table 1: primary distributional summaries (Section 7.1 / 7.2)",
        )
    )
    written.append(
        (
            _write_csv(tables_dir / "table_hospital_scale.csv", result.hospital),
            "Hospital-scale summary at horizon "
            f"{HOSPITAL_HORIZON} (Section 7.6, regime-stratified)",
        )
    )
    written.append(
        (
            _write_csv(tables_dir / "regime_contrast.csv", result.regime_contrast),
            "Regime contrast statistic (Section 7.2)",
        )
    )
    written.append(
        (
            _write_json(
                tables_dir / "robustness_summary.json",
                {
                    "uncorrected": result.robustness_uncorrected,
                    "corrected": result.robustness_corrected,
                },
            ),
            "Robustness ratio per regime (Section 7.5)",
        )
    )
    written.append(
        (
            _write_json(
                tables_dir / "severity_weighting_status.json",
                result.severity_status,
            ),
            "Severity-weighting status (Section 7.3, gated)",
        )
    )
    if result.severity_weighted is not None:
        written.append(
            (
                _write_csv_six_sig_figs(
                    tables_dir / "severity_weighted.csv",
                    result.severity_weighted,
                ),
                "Table 3: severity-weighted contamination (Section 7.3)",
            )
        )
    if result.severity_weighted_path is not None:
        written.append(
            (
                result.severity_weighted_path,
                "Severity-weighted Parquet output (Section 7.3 source-of-truth)",
            )
        )

    # Figures (regime-aware, v2.0)
    from .analyses import add_regime_dimension

    df_canonical = add_regime_dimension(pd.read_parquet(parquet_path))
    written.append(
        (
            _figure_credible_intervals(
                result.primary, figures_dir / "credible_intervals_by_horizon.png"
            ),
            "Figure: median + 90% CI by horizon, both regimes (Section 7.1 visual)",
        )
    )
    written.append(
        (
            _figure_box_at_horizon(
                df_canonical, HOSPITAL_HORIZON, figures_dir / "contamination_box_h10.png"
            ),
            f"Figure: contamination distribution at n={HOSPITAL_HORIZON} by regime",
        )
    )

    if run_log is not None:
        for path, description in written:
            attach_output_file(run_log, path, description=description)

    return result
