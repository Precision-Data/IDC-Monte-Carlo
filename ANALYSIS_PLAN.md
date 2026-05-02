# IDC Monte Carlo Analysis Plan v1.1

**Title:** Pre-specified analysis plan for the prior predictive simulation of the Iatrogenic Data Contamination (IDC) framework.

**Authors:** Jean Raubenheimer, MD (Meerkat Labs Inc.; Vancouver, BC, Canada). Janny Ke, MD (co-author of associated Original Investigation; affiliations to be confirmed).

**Repository:** https://github.com/Precision-Data/IDC-Monte-Carlo

**Status:** v1.1, Issued before any simulation runs against this specification. Intended for archival deposit (Open Science Framework or Zenodo) once authorship and affiliations are confirmed.

**Associated manuscript:** A Bayesian Framework for Iatrogenic Data Contamination in AI-Augmented Healthcare Documentation (IDC_Framework_OI_v1_1, in preparation; target journal npj Digital Medicine).

**Companion manuscript:** Confabulation at Scale: An Architectural Problem in Healthcare AI (Confabulation_at_Scale_Perspective_v1_2, in preparation; target journal npj Digital Medicine).

**Date issued:** [to be set on day of v1.1 deposit]

**Version history:**
- v1.0: initial pre-specification of priors, simulation procedure, and reporting plan.
- v1.1: Wang et al. JAMA Internal Medicine 2017 citation retraced to primary source (DOI: 10.1001/jamainternmed.2017.1548). Steinkamp et al. 2022 added as supporting evidence for the P prior, documenting cross-institutional variability in copy-forward rates. P prior justification widened to reflect this variability.

---

## 1. Purpose and scope

This document pre-specifies the analysis plan for a Bayesian prior predictive simulation of the IDC contamination function. The simulation will be implemented in the IDC-Monte-Carlo repository and reported as part of the associated Original Investigation manuscript. The plan exists to lock the priors, the simulation procedure, the reported quantities, and the reporting standards before the simulation is run, so that the Original Investigation is reported against a registered analysis and so that future prior-to-posterior updates from the planned IHID validation study are mathematically routine.

This plan covers prior predictive simulation only. Posterior inference using clinical contamination data from the IHID corpus at Providence Health Care will be specified in a separate analysis plan when that data is available.

This plan covers no real patient data. All simulation inputs are parameter priors elicited from the published literature. No synthetic clinical data, no simulated patient records, and no fabricated observations are generated, consumed, or reported by the simulation. All numerical outputs derive from sampling the priors and evaluating the closed-form contamination function on the resulting parameter values.

## 2. Background

The IDC framework is a five-stage architecture (generation, entrenchment, propagation, amplification, compounding) describing the lifecycle of an AI confabulation in clinical documentation, derived in the Original Investigation. The framework yields a closed-form contamination function:

Contamination(n) = E0 x epsilon x (1 - P^(n+1)) / (1 - P) x (1 - R)^n

with parameters E0 (initial confabulation rate), epsilon (entrenchment rate), P (per-encounter propagation factor), R (per-encounter de-entrenchment rate), and n (encounter index). The function gives the expected per-confabulation contribution to cumulative contamination at encounter n.

The framework is naturally Bayesian. Each parameter is a probability constrained to the unit interval and is informed by published clinical AI evaluation literature. We specify Beta priors on each parameter, evaluate the contamination function across joint samples drawn from the priors, and report the resulting prior predictive distribution of cumulative contamination. The simulation is the principal quantitative artefact of the Original Investigation.

The motivation for pre-specification is threefold. First, Bayesian analyses are unusually sensitive to prior choice and benefit from advance commitment to the exact (alpha, beta) values used. Second, the framework is designed to support prior-to-posterior updating once IHID data arrives; advance commitment to the prior is a precondition for that update being mathematically routine. Third, pre-registration aligns the analysis with current standards for transparent computational research and supports verification by reviewers and downstream researchers.

## 3. Hypotheses and claims

This is not a frequentist hypothesis test. The simulation reports a prior predictive distribution. We pre-specify three claims that the simulation is intended to evaluate, each phrased as a quantitative prediction under the priors:

**Claim 1.** Under literature-anchored priors, cumulative contamination at the system level (100,000 documents per year, five-year horizon) has a non-trivial expected value in the moderate prior set, with the lower bound of the 90% prior credible interval substantially above zero.

**Claim 2.** The framework's predictions are sensitive but not catastrophically sensitive to prior choice: the ratio of the pessimistic 95th percentile to the optimistic 5th percentile is bounded.

**Claim 3.** Decomposition by error type reveals divergent commission and omission contamination trajectories at long horizons, driven primarily by the parametric asymmetry in epsilon between the two error classes.

The pre-specified ratio thresholds for Claim 2 and the formal divergence criterion for Claim 3 are reported in Section 7 (Pre-specified analyses).

## 4. Parameter priors

Each parameter is given a Beta(alpha, beta) prior, parameterised by mean mu and precision kappa such that alpha = mu*kappa and beta = (1 - mu)*kappa. Three priors are specified per parameter (optimistic, moderate, pessimistic) to characterise sensitivity to literature interpretation. All priors are anchored to verifiable peer-reviewed publications. Where no direct measurement of a parameter exists in the literature, this is stated explicitly and reflected in the prior precision (lower kappa, wider 95% credible interval).

### 4.1 E0 (initial confabulation rate)

**Definition:** Probability that a single AI-generated claim in a clinical document is a confabulation.

**Primary literature anchor:** Asgari E, Montana-Brown N, Dubois M, et al. A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation. npj Digital Medicine 8, 274 (2025). DOI: 10.1038/s41746-025-01670-7.

**Priors specified:**

| Prior | mu | kappa | alpha | beta | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.0147 | 1000 | 14.7 | 985.3 | [0.0080, 0.0234] |
| Moderate | 0.0250 | 500 | 12.5 | 487.5 | [0.0140, 0.0395] |
| Pessimistic | 0.0500 | 200 | 10.0 | 190.0 | [0.0250, 0.0837] |

### 4.2 epsilon (entrenchment rate)

**Definition:** Probability that a confabulation, having been generated, escapes physician review and is signed into the medical record.

**Priors specified:**

| Prior | mu | kappa | alpha | beta | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.10 | 50 | 5.0 | 45.0 | [0.034, 0.205] |
| Moderate | 0.30 | 30 | 9.0 | 21.0 | [0.156, 0.469] |
| Pessimistic | 0.55 | 20 | 11.0 | 9.0 | [0.331, 0.760] |

**Error-type asymmetry.** epsilon for omission errors shifts mu upward by 0.20 across all three prior sets, capped at 0.95. The simulation reports epsilon-decomposed contamination separately by error type as a primary analysis.

### 4.3 P (per-encounter propagation factor)

**Definition:** Probability that an entrenched confabulation appears in the AI-generated documentation of a subsequent encounter through copy-forward, template re-use, or AI context conditioning.

**Primary literature anchor:** Wang MD, Khanna R, Najafi N. Characterizing the Source of Text in Electronic Health Record Progress Notes. JAMA Internal Medicine 177(8), 1212-1213 (2017). DOI: 10.1001/jamainternmed.2017.1548.

**Supporting:** Steinkamp J, Kantrowitz JJ, Airan-Javia S. A Practical Approach for Monitoring the Use of Copy-Paste in Clinical Notes. Appl Clin Inform 13(1), 88-95 (2022).

**Priors specified:**

| Prior | mu | kappa | alpha | beta | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.30 | 25 | 7.5 | 17.5 | [0.144, 0.494] |
| Moderate | 0.50 | 20 | 10.0 | 10.0 | [0.289, 0.711] |
| Pessimistic | 0.70 | 25 | 17.5 | 7.5 | [0.506, 0.856] |

### 4.4 R (per-encounter de-entrenchment rate)

**Definition:** Probability that an entrenched confabulation is identified and removed from the medical record at any subsequent encounter.

**Priors specified:**

| Prior | mu | kappa | alpha | beta | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.05 | 50 | 2.5 | 47.5 | [0.008, 0.123] |
| Moderate | 0.02 | 100 | 2.0 | 98.0 | [0.003, 0.057] |
| Pessimistic | 0.005 | 200 | 1.0 | 199.0 | [0.0002, 0.025] |

**Directionality caveat.** For R the "optimistic" prior (mu = 0.05) is the highest correction rate; "pessimistic" (mu = 0.005) is the lowest. This is opposite to E0, epsilon, and P. The contamination function multiplies by (1 - R)^n, so higher R reduces cumulative contamination.

### 4.5 Joint prior assumption

All four parameter priors are sampled independently. The sensitivity analysis includes a stress test in which a positive correlation rho = 0.4 is induced between E0 and epsilon via a Gaussian copula.

## 5. Simulation procedure

### 5.1 Algorithm

For each of three prior sets (optimistic, moderate, pessimistic):

1. Draw K = 10,000 joint samples (E0_k, epsilon_k, P_k, R_k) independently from the corresponding Beta priors, using a fixed random seed (see Section 5.3).
2. For each sample k and each pre-specified horizon n in {1, 5, 10, 20, infinity}, evaluate the contamination function:
   Contamination_k(n) = E0_k x epsilon_k x (1 - P_k^(n+1)) / (1 - P_k) x (1 - R_k)^n
3. For the steady-state limit (n -> infinity), use the closed form Contamination_inf = E0_k x epsilon_k / (1 - P_k) x lim of (1 - R_k)^n. For R_k > 0 and P_k < 1 the limit is zero; the steady-state quantity reported is the maximum over n of the per-confabulation contamination, identified per sample.
4. Repeat the entire procedure with omission-adjusted epsilon priors to produce the type-decomposed contamination distributions.
5. Apply NOHARM severity tier weighting (Section 6.4) to produce severity-weighted contamination distributions.
6. Compute summary statistics (Section 7).

### 5.2 Software environment

Python 3.12+, numpy >= 2.0, scipy >= 1.13, pandas >= 2.2, matplotlib >= 3.9. The full pinned dependency set is committed to the repository as `requirements.txt`. The environment lock file accompanies every released version of the simulation.

### 5.3 Random seed strategy

The principal simulation uses seed = 20260502 (date of this plan's deposit). Convergence is verified by replicating with seed = 20260503 and confirming agreement of 5th, 50th, and 95th percentiles to within 1% across replicates. Both seeds are committed to the repository and reported in the manuscript.

If convergence fails the 1% criterion, K is doubled (to 20,000) and the convergence check is repeated. The escalation rule is pre-specified: K may not be tuned to obtain a desired result.

### 5.4 Hospital-scale interpretation

For interpretive purposes, simulation outputs are also reported at hospital scale assuming a notional system processing 100,000 AI-assisted documents per year over a five-year horizon, scaled by the per-confabulation contamination probability.

## 6. Data provenance and integrity

### 6.1 No synthetic data, ever

The simulation generates probability distributions over a contamination function. It does not generate synthetic clinical data, simulated patient records, or any artefact resembling clinical observations. Every numerical input is either a parameter prior anchored to a cited publication or a fixed framework parameter (n, hospital scale). Every numerical output is a deterministic function of those inputs and the documented random seed.

If at any point the analysis requires data that does not exist in the literature, the analysis stops. The prior is widened to reflect the missing data and the gap is reported as an open item. Synthesis is not an alternative to acknowledged uncertainty.

### 6.2 Logging requirements

Every simulation run shall produce, alongside its numerical outputs, a structured run log containing:
- Run date and time (UTC).
- Random seed used.
- K (number of samples).
- Software versions for all major dependencies (numpy, scipy, pandas).
- Operating system and hardware identifier (CPU model, available memory).
- Git commit hash of the simulation code.
- SHA256 hash of the output file produced.
- Pre-specified versus exploratory designation.

The run log is committed to the repository alongside the output file. No simulation result is reported in the manuscript without an accompanying run log.

### 6.3 Output file standard

Outputs are written as Apache Parquet with one row per (prior set, parameter sample, horizon) combination. The columns include the parameter values drawn, the contamination value computed, and metadata identifying which prior set and which horizon. No aggregation is performed before writing; all aggregation happens downstream of the canonical output file, which is the single source of truth for downstream tables and figures.

### 6.4 Severity weighting

NOHARM severity tier weights are applied as documented in Wu et al. 2025. The exact tier-to-weight mapping is committed to the repository as `severity_weights.yaml` with each weight traceable to a line in the Wu et al. paper. If the Wu et al. paper does not report the proportions in a form usable for severity weighting, the severity-weighted analysis is reported as a planned but unsupported extension and is not computed in v1.0 of the simulation. Under no circumstances are weights chosen by judgement to fill the gap.

## 7. Pre-specified analyses and reporting

### 7.1 Primary analyses

For each prior set and each horizon n in {1, 5, 10, 20}:
- Median, mean, 5th percentile, 95th percentile of per-confabulation Contamination(n).
- 90% prior credible interval [5th, 95th].
- Probability that Contamination(n) exceeds 0.01.

### 7.2 Type decomposition

All primary analyses also computed separately for commission and omission errors using the omission-adjusted epsilon priors.

### 7.3 Severity weighting

Severity-weighted contamination using NOHARM tier weights, conditional on the severity_weights.yaml resolution under Section 6.4.

### 7.4 Sensitivity analyses

- R = 0 (no correction) as a boundary case under the moderate prior set for E0, epsilon, P.
- Independence assumption stress-test: rho = 0.4 correlation between E0 and epsilon via Gaussian copula, moderate prior set, otherwise unchanged.
- Multi-agent adjustment: P prior shifted to a multi-agent-adjusted P' specified at mu = 0.65, kappa = 25, with the same E0, epsilon, R priors.
- Robustness summary statistic: ratio of pessimistic 95th percentile (across all parameters jointly) to optimistic 5th percentile (across all parameters jointly) at horizon n = 10. Pre-specified threshold for "framework is robust to literature interpretation" is a ratio less than 25; ratio above 50 will be reported as a meaningful sensitivity to prior specification.

### 7.5 Hospital-scale illustration

For each prior set and the moderate horizon (n = 10, approximately 2.5 years at four encounters per patient per year), report median and 90% prior credible interval contaminated documents at the notional 100,000-documents-per-year, five-year hospital scale.

### 7.6 What is exploratory

Anything not in Sections 7.1 to 7.5 is exploratory. Exploratory analyses are permitted but must be flagged as such in the manuscript and accompanied by a statement that they were not pre-specified.

## 8. Path to posterior inference

The framework supports prior-to-posterior updating using the Beta-Binomial conjugate update mechanic. When IHID validation data become available, the IHID companion paper will report the posterior treatment in full and will reference this v1.1 plan as the prior specification it updates.

## 9. Reproducibility

All simulation code, parameter prior YAML files, run logs, output files, and analysis notebooks are released under MIT licence in the IDC-Monte-Carlo repository. Each release is tagged in git and assigned a Zenodo DOI.

The repository's README documents the steps required to reproduce the principal simulation results from a clean checkout. The reproducibility check is executed by an automated GitHub Actions workflow on every push to the main branch and on every pull request.

## 10. Deviations from plan

Any deviation from this plan is reported transparently in the manuscript and in a `DEVIATIONS.md` file in the repository. Deviations require a version bump of this plan.

The specific cases that constitute deviation include but are not limited to: changing a prior (alpha, beta) value, changing K, changing the horizon set, adding a primary analysis, removing a primary analysis, changing the random seed strategy, and changing the severity weighting source.

## 11. Authorship and contributions (ICMJE)

To be finalised when authorship and affiliations are confirmed.

JR: framework conception, prior specification, plan drafting, manuscript drafting.
JK: review of methodology, prior specification review, manuscript review.

## 12. Conflicts of interest

JR is founder and CEO of Meerkat Labs Inc. (Vancouver, BC, Canada). The IDC framework, this analysis plan, and the companion manuscripts are academic work conducted in Dr Raubenheimer's capacity as a clinician-researcher; the framework is released under open access and the simulation under MIT licence.

## 13. Funding

No external funding has been received specifically for this analysis plan. Computational resources for simulation execution are provided by Meerkat Labs Inc.

## 14. Data and code availability

Simulation code: https://github.com/Precision-Data/IDC-Monte-Carlo (MIT licence).
Parameter priors and severity weights: committed to the repository as machine-readable YAML files with citation-anchored comments.
No clinical patient data is collected, generated, or distributed under this plan.

---

End of v1.1.
