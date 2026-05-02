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

Implements analysis plan v1.1, with one logged deviation
([DEVIATIONS.md](DEVIATIONS.md)) clarifying the Section 5.3 convergence
criterion. Ready to run the principal simulation against seed 20260502.

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
severity_weighting_status). `outputs/figures/` contains the
manuscript figures at 300 dpi. `runs/` holds a structured JSON run log
per simulation invocation, recording the seed, K, dependency versions,
git commit, and the SHA256 of every output file produced.

## Reproducibility

Same seed produces bit-identical Parquet output (verified by SHA256). The
GitHub Actions workflow `.github/workflows/reproduce.yml` regenerates the
principal-seed output on every push to `main` and verifies its hash against
[outputs/checksums.txt](outputs/checksums.txt); divergence fails the build.

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
