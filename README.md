# IDC-Monte-Carlo

## What this is

The IDC-Monte-Carlo repository implements the prior predictive Monte Carlo
simulation specified in the
[IDC Monte Carlo Analysis Plan](ANALYSIS_PLAN.md). It supports the Bayesian
framework presented in Raubenheimer and Ke (in preparation): for each of three
literature-anchored prior sets, the simulation draws K = 10,000 joint samples
from Beta priors over (E0, epsilon, P, R) and evaluates the closed-form IDC
contamination function at each pre-specified horizon, separately for
commission and omission errors.

## Status

Implements analysis plan v1.2 ([ANALYSIS_PLAN.md](ANALYSIS_PLAN.md)).
Severity weighting is enabled per `weights/severity_weights.yaml`
(NOHARM (5,5) scheme, citation-anchored to Wu et al. arXiv:2512.01241).
Three tier distribution options are reported as a sensitivity range; the
primary is `anchored_severe_22_2_percent`. The two methodological
clarifications surfaced during the first principal run (Section 5.3
convergence criterion, Section 6.3 cross-platform reproducibility
target) are folded into the plan body; their original deviation entries
plus the severity-weighting activation are retained for audit in
[DEVIATIONS.md](DEVIATIONS.md).

## How to run

```bash
git clone https://github.com/Precision-Data/IDC-Monte-Carlo.git
cd IDC-Monte-Carlo
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
python -m idc_simulation all
```

The `all` subcommand runs the principal simulation (K=10,000, seed=20260502)
and renders the manuscript tables and figures in one invocation.
`python -m idc_simulation --help` lists `run`, `analyse`, and `all` in
detail.

## What the outputs mean

`outputs/contamination_seed<seed>_K<K>.parquet` is the canonical long-format
output: one row per (prior_set, error_type, sample_index, horizon) with the
drawn parameter values and the evaluated contamination. All downstream
artefacts derive from this file.

`outputs/tables/` contains the Section 7 tables in CSV/JSON form
(table1_primary_summary, table_hospital_scale, robustness_summary,
severity_weighting_status, severity_weighted). `outputs/figures/`
contains the manuscript figures at 300 dpi.
`outputs/severity_weighted.parquet` is the source-of-truth table for
the Section 7.3 severity-weighted analysis (one row per
prior_set x horizon x tier_option). `runs/` holds a structured JSON
run log per simulation invocation, recording the seed, K, dependency
versions, git commit, and the SHA256 of every output file produced.

## Reproducibility

Same seed produces stable per-cell summary statistics across CPU
architectures (cross-platform reproducibility target per plan v1.2
Section 6.3). Two blessed checksums live in
[outputs/checksums.txt](outputs/checksums.txt): one over the canonical
contamination output's per-cell summary vector, one over the
severity-weighted summary table. The GitHub Actions workflow
`.github/workflows/reproduce.yml` regenerates both on every push to
`main` and fails the build on any divergence.

## Citation

```bibtex
@misc{idc_monte_carlo_2026,
  author       = {Raubenheimer, Jean and Ke, Janny},
  title        = {{IDC-Monte-Carlo: Prior Predictive Simulation for the
                  Iatrogenic Data Contamination Bayesian Framework}},
  year         = {2026},
  howpublished = {\url{https://github.com/Precision-Data/IDC-Monte-Carlo}},
  note         = {Implements analysis plan v1.1; Zenodo DOI on first
                  tagged release.}
}
```

The associated Original Investigation manuscript ("A Bayesian Framework for
Iatrogenic Data Contamination in AI-Augmented Healthcare Documentation") is
in preparation; full citation will be added on submission.

## Licence

[MIT](LICENSE).
