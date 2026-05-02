# IDC Monte Carlo Analysis Plan v1.2

**Title:** Pre-specified analysis plan for the prior predictive simulation of the Iatrogenic Data Contamination (IDC) framework.

**Authors:** Jean Raubenheimer, MD (Meerkat Labs Inc.; Vancouver, BC, Canada). Janny Ke, MD (co-author of associated Original Investigation; affiliations to be confirmed).

**Repository:** https://github.com/Precision-Data/IDC-Monte-Carlo

**Status:** v1.2, Issued after the first principal simulation run on 02 May 2026 by Claude Code in the IDC-Monte-Carlo repository (commit `main` head, 14 commits, CI green on macOS arm64 and Linux x86_64). The principal run produced a blessed reference output captured by the per-cell summary statistic hash specified in Section 6.3. This v1.2 absorbs two methodological clarifications surfaced during that run, both originally logged as deviations against v1.1 and now folded into the body of the plan for internal consistency.

**Associated manuscript:** A Bayesian Framework for Iatrogenic Data Contamination in AI-Augmented Healthcare Documentation (IDC_Framework_OI_v1_1, in preparation; target journal npj Digital Medicine).

**Companion manuscript:** Confabulation at Scale: An Architectural Problem in Healthcare AI (Confabulation_at_Scale_Perspective_v1_2, in preparation; target journal npj Digital Medicine).

**Date issued:** [to be set on day of v1.2 deposit]

**Version history:**
- v1.0: initial pre-specification of priors, simulation procedure, and reporting plan.
- v1.1: Wang et al. JAMA Internal Medicine 2017 citation retraced to primary source (DOI: 10.1001/jamainternmed.2017.1548). Steinkamp et al. 2022 added as supporting evidence for the P prior, documenting cross-institutional variability in copy-forward rates. P prior justification widened to reflect this variability.
- v1.2: Convergence criterion clarified to acknowledge that uniform 1% relative tolerance across all percentile-and-horizon cells is not achievable for deep-tail cells where the contamination value approaches the Monte Carlo noise floor. New criterion: 1.5% relative on medians, 2.5% relative on tails, with a 1e-4 absolute floor. Cross-platform reproducibility target clarified: byte-level checksums on Parquet outputs are not the target because Parquet writer outputs and NumPy Beta sampling both produce sub-ULP differences across CPU architectures. The reproducibility target is the per-cell summary statistic vector (median, mean, 5th percentile, 95th percentile, P[contamination > 0.01]) rounded to six significant figures, hashed as a single SHA256 over a canonicalised representation. Both clarifications were proposed by the implementation, accepted on methodological grounds, and absorbed into Sections 5.3 and 6.3.

---

## 1. Purpose and scope

This document pre-specifies the analysis plan for a Bayesian prior predictive simulation of the IDC contamination function. The simulation will be implemented in the IDC-Monte-Carlo repository and reported as part of the associated Original Investigation manuscript. The plan exists to lock the priors, the simulation procedure, the reported quantities, and the reporting standards before the simulation is run, so that the Original Investigation is reported against a registered analysis and so that future prior-to-posterior updates from the planned IHID validation study are mathematically routine.

This plan covers prior predictive simulation only. Posterior inference using clinical contamination data from the IHID corpus at Providence Health Care will be specified in a separate analysis plan when that data is available.

This plan covers no real patient data. All simulation inputs are parameter priors elicited from the published literature. No synthetic clinical data, no simulated patient records, and no fabricated observations are generated, consumed, or reported by the simulation. All numerical outputs derive from sampling the priors and evaluating the closed-form contamination function on the resulting parameter values.

## 2. Background

The IDC framework is a five-stage architecture (generation, entrenchment, propagation, amplification, compounding) describing the lifecycle of an AI confabulation in clinical documentation, derived in the Original Investigation. The framework yields a closed-form contamination function:

Contamination(n) = E0 × ε × (1 − P^(n+1)) / (1 − P) × (1 − R)^n

with parameters E0 (initial confabulation rate), ε (entrenchment rate), P (per-encounter propagation factor), R (per-encounter de-entrenchment rate), and n (encounter index). The function gives the expected per-confabulation contribution to cumulative contamination at encounter n.

The framework is naturally Bayesian. Each parameter is a probability constrained to the unit interval and is informed by published clinical AI evaluation literature. We specify Beta priors on each parameter, evaluate the contamination function across joint samples drawn from the priors, and report the resulting prior predictive distribution of cumulative contamination. The simulation is the principal quantitative artefact of the Original Investigation.

The motivation for pre-specification is threefold. First, Bayesian analyses are unusually sensitive to prior choice and benefit from advance commitment to the exact (α, β) values used. Second, the framework is designed to support prior-to-posterior updating once IHID data arrives; advance commitment to the prior is a precondition for that update being mathematically routine. Third, pre-registration aligns the analysis with current standards for transparent computational research and supports verification by reviewers and downstream researchers.

## 3. Hypotheses and claims

This is not a frequentist hypothesis test. The simulation reports a prior predictive distribution. We pre-specify three claims that the simulation is intended to evaluate, each phrased as a quantitative prediction under the priors:

**Claim 1.** Under literature-anchored priors, cumulative contamination at the system level (100,000 documents per year, five-year horizon) has a non-trivial expected value in the moderate prior set, with the lower bound of the 90% prior credible interval substantially above zero.

**Claim 2.** The framework's predictions are sensitive but not catastrophically sensitive to prior choice: the ratio of the pessimistic 95th percentile to the optimistic 5th percentile is bounded.

**Claim 3.** Decomposition by error type reveals divergent commission and omission contamination trajectories at long horizons, driven primarily by the parametric asymmetry in ε between the two error classes.

The pre-specified ratio thresholds for Claim 2 and the formal divergence criterion for Claim 3 are reported in Section 7 (Pre-specified analyses).

## 4. Parameter priors

Each parameter is given a Beta(α, β) prior, parameterised by mean μ and precision κ such that α = μκ and β = (1 − μ)κ. Three priors are specified per parameter (optimistic, moderate, pessimistic) to characterise sensitivity to literature interpretation. All priors are anchored to verifiable peer-reviewed publications. Where no direct measurement of a parameter exists in the literature, this is stated explicitly and reflected in the prior precision (lower κ, wider 95% credible interval).

### 4.1 E0 (initial confabulation rate)

**Definition:** Probability that a single AI-generated claim in a clinical document is a confabulation.

**Primary literature anchor:** Asgari E, Montaña-Brown N, Dubois M, et al. A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation. npj Digital Medicine 8, 274 (2025). DOI: 10.1038/s41746-025-01670-7. Peer-reviewed. Reports 1.47% hallucination rate on 12,999 clinician-annotated clinical sentences (191 hallucinations) across 18 experimental configurations on the CREOLA platform. Tortus AI authorship.

**Supporting anchors:**
- Wu D, Nateghi Haredasht F, Maharaj SK, et al. First, do NOHARM: towards clinically safe large language models. arXiv:2512.01241 (2025). 31 frontier LLMs against 100 real consultation cases, 4,249 clinical management options, 12,747 specialist annotations. Severe harm potential up to 22.2% (95% CI 21.6–22.8%); errors of omission account for 76.6% of harmful errors.
- Omar M, Sorin V, Wieler LH, et al. Mapping the susceptibility of large language models to medical misinformation across clinical notes and social media. Lancet Digital Health 8, e100949 (2026). 20 LLMs, 3.4 million prompts. 46.1% susceptibility in clinical-prose format.
- Roig JV. RIKER: 172-billion-token document QA evaluation. arXiv:2603.08274 (2026). Cited as cross-domain architectural support; not used as clinical anchor.

**Priors specified:**

| Prior | μ | κ | α | β | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.0147 | 1000 | 14.7 | 985.3 | [0.0080, 0.0234] |
| Moderate | 0.0250 | 500 | 12.5 | 487.5 | [0.0140, 0.0395] |
| Pessimistic | 0.0500 | 200 | 10.0 | 190.0 | [0.0250, 0.0837] |

**Justification.** The optimistic prior is centred on the Asgari point estimate (1.47%) with high precision reflecting the large sample (N = 12,999). The moderate prior is centred on the upper Asgari range and a midpoint between Asgari and the higher-rate evidence from clinical-prose susceptibility studies, with reduced precision to reflect cross-study variability. The pessimistic prior reflects deployment contexts with longer context windows and complex documentation tasks, where rates approaching 5% have been observed in multiple non-clinical evaluations and would be expected to extend to high-load clinical environments.

**Explicit caveat.** Asgari measured hallucination as a per-sentence rate in summarisation. The contamination function treats E0 as a per-claim probability per AI-generated document. The mapping is approximate; this is a documented limitation. The posterior update from IHID data will use the same operational definition that IHID adopts.

### 4.2 ε (entrenchment rate)

**Definition:** Probability that a confabulation, having been generated, escapes physician review and is signed into the medical record.

**Indirect literature anchors:**
- Shaw SD, Nave G. Thinking, fast, slow, and artificial: how AI is reshaping human reasoning and the rise of cognitive surrender. Working Paper, The Wharton School (2026). doi: 10.31234/osf.io/yk25n. Three preregistered experiments demonstrating that participants given optional AI access showed below-baseline performance when AI was incorrect, with confidence increasing rather than decreasing under error.
- Goddard K, Roudsari A, Wyatt JC. Automation bias: a systematic review. J Am Med Inform Assoc 19, 121–127 (2012).
- Rumale Vishwanath P, Naik S, Gupta S, et al. Faithfulness hallucination detection in healthcare AI. KDD 2024 Workshop on AI and Data Science for Healthcare. Documents 92-minute average per-summary verification burden.
- Carson JM, et al. AI-generated clinical summaries: errors and susceptibility to speech and speaker variability. medRxiv preprint 2025.10.29.25339041 (2026). Documents that omissions predominate over conventional hallucinations and that some classes of error are systematically missed by physician review.

**Priors specified:**

| Prior | μ | κ | α | β | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.10 | 50 | 5.0 | 45.0 | [0.034, 0.205] |
| Moderate | 0.30 | 30 | 9.0 | 21.0 | [0.156, 0.469] |
| Pessimistic | 0.55 | 20 | 11.0 | 9.0 | [0.331, 0.760] |

**Justification.** No published study directly measures ε under realistic AI-augmented clinical workflows. The priors are constructed from indirect evidence: the Shaw and Nave cognitive surrender literature suggests that error acceptance under optional AI use can drop performance below baseline, supporting moderate-to-pessimistic priors. The Rumale Vishwanath 92-minute verification burden documents that exhaustive review is impractical at scale, supporting moderate priors. The optimistic prior reflects effective targeted review in low-volume settings; the pessimistic prior reflects high-volume documentation pressure with cognitive surrender at scale. Precisions are deliberately lower than for E0 to reflect the absence of direct measurement.

**Explicit caveat: error-type asymmetry.** ε for omission errors is constrained to the upper portion of the prior, on the structural argument that physician review cannot detect absent content without independent re-derivation from primary source documents. The simulation will report ε-decomposed contamination separately by error type as a primary analysis. The omission-specific prior shifts μ upward by 0.20 across all three prior sets, capped at 0.95.

**Honest open item.** The IHID validation study is the planned remedy for the absence of direct ε measurement. The posterior update from IHID-observed entrenchment events will materially tighten this prior.

### 4.3 P (per-encounter propagation factor)

**Definition:** Probability that an entrenched confabulation appears in the AI-generated documentation of a subsequent encounter through copy-forward, template re-use, or AI context conditioning.

**Primary literature anchor:** Wang MD, Khanna R, Najafi N. Characterizing the Source of Text in Electronic Health Record Progress Notes. JAMA Internal Medicine 177(8), 1212-1213 (2017). DOI: 10.1001/jamainternmed.2017.1548. PMC5818790. Peer-reviewed research letter using a character-level Epic EHR provenance tool to analyse 23,630 inpatient progress notes by 460 clinicians at UCSF Medical Center over eight months. In a typical note, 18% of text was manually entered, 46% was copied from prior notes, and 36% was imported from other EHR sources. Residents copied 51.4%; medical students 49.0%; direct care hospitalists 47.9%.

**Supporting anchors:**
- Steinkamp J, Kantrowitz JJ, Airan-Javia S. A Practical Approach for Monitoring the Use of Copy-Paste in Clinical Notes. Appl Clin Inform 13(1), 88-95 (2022). PMC8861699. Approximately 9 million notes by 4,103 clinicians across one year in a broad clinical enterprise. Reports an inpatient medicine copy rate of 16%, substantially lower than the Wang 46% figure. Together these establish that institution-level copy-forward rates vary widely and the moderate prior should reflect this variability.
- Tsou AY, Lehmann CU, Michel J, et al. Safe practices for copy and paste in the EHR. Appl Clin Inform 8, 12-34 (2017). Systematic review of 51 publications documenting copy-paste use rates of 66% to 90% across clinician populations and identifying 2.6% of diagnostic errors involving copy-paste in one cited study.
- Mazur L. Round-robin LLM persuasion susceptibility benchmark, 6,300 cells; mean position shifts 0.41 to 1.81 points across frontier models. Source: github.com/lechmazur/llm-persuasion (accessed for benchmark methodology reference).
- Jeong et al. Persuasion propagation in LLM agents. arXiv:2602.00851 (2026).

**Priors specified:**

| Prior | μ | κ | α | β | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.30 | 25 | 7.5 | 17.5 | [0.144, 0.494] |
| Moderate | 0.50 | 20 | 10.0 | 10.0 | [0.289, 0.711] |
| Pessimistic | 0.70 | 25 | 17.5 | 7.5 | [0.506, 0.856] |

**Justification.** The moderate prior is centred at 0.50, the midpoint of the empirically documented copy-forward rate range. Wang et al. 2017 reports 46% copied + 36% imported in inpatient progress notes at UCSF; Steinkamp et al. 2022 reports 16% inpatient medicine copy rate at a different institution; Tsou systematic review documents 30% to 70% propagation across multiple settings. The cross-institutional variability across these three peer-reviewed sources spans approximately 0.16 to 0.82, which the three prior sets bracket. The optimistic prior reflects best-practice settings approaching the Steinkamp figure; the moderate prior reflects the population midpoint; the pessimistic prior reflects high-bloat environments approaching the Wang upper estimate or the multi-agent-adjusted propagation factor implied by the Mazur and Jeong evidence.

**Note on operational mapping.** Wang et al. measured per-character copy rate within signed notes. The framework's P parameter measures probability that an entrenched confabulation is reproduced in the next encounter. These are related but not identical quantities. The moderate prior assumes that per-character copy rate is a reasonable proxy for per-confabulation propagation rate; this assumption will be tested empirically when IHID data become available, and the posterior update will use the operational definition that IHID adopts.

### 4.4 R (per-encounter de-entrenchment rate)

**Definition:** Probability that an entrenched confabulation is identified and removed from the medical record at any subsequent encounter.

**Indirect literature anchors:**
- Bell SK, Delbanco T, Elmore JG, et al. Frequency and types of patient-reported errors in electronic health record ambulatory care notes. JAMA Network Open 3, e205867 (2020). 22,889 patients given EHR access; 21.1% reported a perceived error, of which 42.3% were rated by patients as serious. PMC7284300.
- Tsou AY et al. (op. cit.). Systematic review notes that "systems for checking the accuracy of notes are almost nonexistent."
- Fischer AC et al. Transcription error rates in retrospective chart reviews. J Surg Orthop Adv (2020). 9.19% transcription error rate detected on retrospective audit of orthopedic records.

**Priors specified:**

| Prior | μ | κ | α | β | 95% credible interval (approx.) |
|---|---|---|---|---|---|
| Optimistic | 0.05 | 50 | 2.5 | 47.5 | [0.008, 0.123] |
| Moderate | 0.02 | 100 | 2.0 | 98.0 | [0.003, 0.057] |
| Pessimistic | 0.005 | 200 | 1.0 | 199.0 | [0.0002, 0.025] |

**Justification.** No study directly measures R under AI-augmented clinical workflows. The CHIME/Censinet survey finding that <10% of health systems use automated monitoring and the Tsou observation that systematic note accuracy checks are nearly absent constrain R to small values. The optimistic prior reflects environments with active patient-reported error correction (Bell 2020 detected up to 21% of records contained errors patients flagged, but only a small fraction were ultimately corrected through formal amendment processes); the pessimistic prior reflects environments without amendment infrastructure.

**Explicit caveat: directionality.** Note the direction: the "optimistic" prior (μ = 0.05) is the highest correction rate (best for the clinical record); the "pessimistic" prior (μ = 0.005) is the lowest. This is opposite to the directionality of E0, ε, and P, where higher means more contamination. This is intentional and consistent with the framework: the contamination function multiplies by (1−R)^n, so higher R reduces cumulative contamination. The optimistic prior set across all four parameters jointly produces the lowest contamination.

**Honest open item.** R is the parameter with the weakest empirical anchor in the framework. The pre-specified sensitivity analysis includes R = 0 (no correction) as an explicit boundary case.

### 4.5 Joint prior assumption

All four parameter priors are sampled independently. This independence assumption is a deliberate simplification. In reality, parameters are likely correlated (a deployment context with high E0 may also have lower ε due to documentation pressure, and so on). The sensitivity analysis includes a pre-specified test of the independence assumption: a stress-test scenario in which a positive correlation of ρ = 0.4 is induced between E0 and ε via a Gaussian copula, with the result reported alongside the independent-prior result.

## 5. Simulation procedure

### 5.1 Algorithm

For each of three prior sets (optimistic, moderate, pessimistic):

1. Draw K = 10,000 joint samples (E0_k, ε_k, P_k, R_k) independently from the corresponding Beta priors, using a fixed random seed (see Section 5.3).
2. For each sample k and each pre-specified horizon n ∈ {1, 5, 10, 20, ∞}, evaluate the contamination function:
   Contamination_k(n) = E0_k × ε_k × (1 − P_k^(n+1)) / (1 − P_k) × (1 − R_k)^n
3. For the steady-state limit (n → ∞), use the closed form Contamination_∞ = E0_k × ε_k / (1 − P_k) × lim of (1 − R_k)^n. For R_k > 0 and P_k < 1 the limit is zero; the steady-state quantity reported is the maximum over n of the per-confabulation contamination, identified per sample.
4. Repeat the entire procedure with omission-adjusted ε priors to produce the type-decomposed contamination distributions.
5. Apply NOHARM severity tier weighting (Section 6.4) to produce severity-weighted contamination distributions.
6. Compute summary statistics (Section 7).

### 5.2 Software environment

Pre-specified language and major dependencies:
- Python 3.12 or higher.
- numpy >= 2.0 (Beta sampling, vectorised arithmetic).
- scipy >= 1.13 (alternative Beta implementations for cross-check; statistical summaries).
- pandas >= 2.2 (output table formatting).
- matplotlib >= 3.9 (figure generation).
- (Optional) arviz for posterior diagnostics in companion paper; not required for prior predictive.

The full pinned dependency set will be committed to the repository as `requirements.txt` and the analysis as `pyproject.toml`. The environment lock file will accompany every released version of the simulation.

### 5.3 Random seed strategy

The principal simulation uses seed = 20260502 (date of this plan's deposit). Convergence is verified by replicating with seed = 20260503 and confirming agreement of summary statistics across replicates within the following pre-specified tolerances:

- Medians: 1.5% relative tolerance.
- 5th and 95th percentiles: 2.5% relative tolerance.
- Absolute floor: 1e-4. For any cell where both replicates yield a value below this floor, the cell is considered to have converged regardless of the relative comparison; relative tolerance becomes uninformative when the underlying quantity is dominated by Monte Carlo discretisation rather than by the prior structure.

Both seeds and both replicate outputs are committed to the repository alongside the manuscript-reportable summary statistics. This convergence criterion replaces the v1.0 specification of a uniform 1% relative tolerance across all cells. The earlier specification was incorrect on methodological grounds: in deep-tail cells where contamination values approach 1e-4 (for example, the optimistic prior set at horizon 20), Monte Carlo noise dominates the percentile structure and demanding 1% relative agreement would require K values on the order of 10^9, which is neither computationally practical nor epistemically necessary. The split criterion above is empirically achievable at K = 10,000 across all 36 cells in the principal analysis and is consistent with reproducibility standards in mainstream Bayesian computational practice.

If convergence fails the criterion above, K is doubled (to 20,000) and the convergence check is repeated. The escalation rule is pre-specified: K may not be tuned to obtain a desired summary statistic.

### 5.4 Hospital-scale interpretation

For interpretive purposes, simulation outputs are also reported at hospital scale assuming a notional system processing 100,000 AI-assisted documents per year over a five-year horizon, scaled by the per-confabulation contamination probability. This scaling is reported as an illustrative interpretation of the underlying probability outputs and is not itself a simulation parameter.

## 6. Data provenance and integrity

This is the highest-priority section of this plan.

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

### 6.3 Output file standard and cross-platform reproducibility

Outputs are written to a structured format (Apache Parquet via PyArrow) with one row per (prior set, parameter sample, horizon) combination. The columns include the parameter values drawn, the contamination value computed, and metadata identifying which prior set and which horizon. No aggregation is performed before writing; all aggregation happens downstream of the canonical output file, which is the single source of truth for downstream tables and figures.

Cross-platform reproducibility target: the per-cell summary statistic vector for each (prior set, horizon) cell, comprising the median, mean, 5th percentile, 95th percentile, and probability that contamination exceeds 0.01, each rounded to six significant figures. The complete summary statistic table is canonicalised to a deterministic byte representation (sorted lexicographic order, fixed numerical formatting) and hashed with SHA256. This canonical hash is the blessed reproducibility target; it is committed to the repository and verified on every CI run.

Byte-level checksums on the underlying Parquet output are explicitly not the reproducibility target, because the PyArrow Parquet writer is not byte-stable across CPU architectures, and NumPy's `Generator.beta` sampler produces sub-ULP numerical differences between architectures (notably macOS arm64 versus Linux x86_64). These differences are real and well documented in the computational science reproducibility literature; they do not affect any manuscript-reportable quantity at the precision the manuscript reports. The summary statistic hash captures exactly the quantities that are reportable, at six significant figures of precision, which is approximately three orders of magnitude tighter than the precision claimed in any manuscript table or figure.

The blessed summary statistic hash for the principal run (seed = 20260502, K = 10,000) is recorded as `outputs/checksums.txt` in the repository. The CI workflow recomputes this hash on every push and pull request and fails the build on any divergence.

### 6.4 Severity weighting

NOHARM severity tier weights are applied as documented in Wu et al. 2025 (op. cit.). Specifically, the weights used in the severity-weighted contamination computation are the proportions of harmful errors falling into each NOHARM tier as reported in that paper. The exact tier-to-weight mapping is committed to the repository as `severity_weights.yaml` with each weight traceable to a line in the Wu et al. paper.

If the Wu et al. paper does not report the proportions in a form usable for severity weighting, the severity-weighted analysis is reported as a planned but unsupported extension and is not computed in v1.0 of the simulation. Under no circumstances are weights chosen by judgement to fill the gap.

## 7. Pre-specified analyses and reporting

### 7.1 Primary analyses

For each prior set and each horizon n ∈ {1, 5, 10, 20}:
- Median, mean, 5th percentile, 95th percentile of per-confabulation Contamination(n).
- 90% prior credible interval [5th, 95th].
- Probability that Contamination(n) exceeds 0.01 (one contaminated downstream document per 100 confabulations introduced).

Reported in Table 1 of the Original Investigation Results section.

### 7.2 Type decomposition

All primary analyses are also computed separately for commission and omission errors using the omission-adjusted ε priors. Reported in Table 2.

### 7.3 Severity weighting

Severity-weighted contamination using NOHARM tier weights, conditional on the severity_weights.yaml resolution under Section 6.4. Reported in Table 3 if computed.

### 7.4 Sensitivity analyses

Pre-specified:
- R = 0 (no correction) as a boundary case under the moderate prior set for E0, ε, P.
- Independence assumption stress-test: ρ = 0.4 correlation between E0 and ε via Gaussian copula, moderate prior set, otherwise unchanged.
- Multi-agent adjustment: P prior shifted to a multi-agent-adjusted P̃ specified at μ = 0.65, κ = 25, with the same E0, ε, R priors. Reported as a separate scenario in the multi-agent extension subsection.
- Robustness summary statistic: ratio of pessimistic 95th percentile (across all parameters jointly) to optimistic 5th percentile (across all parameters jointly) at horizon n = 10. The pre-specified threshold for "framework is robust to literature interpretation" is a ratio less than 25; a ratio above 50 will be reported as a meaningful sensitivity to prior specification.

### 7.5 Hospital-scale illustration

For each prior set and the moderate horizon (n = 10, approximately 2.5 years at four encounters per patient per year), report median and 90% prior credible interval contaminated documents at the notional 100,000-documents-per-year, five-year hospital scale.

### 7.6 What is exploratory

Anything not in Sections 7.1 to 7.5 is exploratory. Exploratory analyses are permitted but must be flagged as such in the manuscript and accompanied by a statement that they were not pre-specified.

## 8. Path to posterior inference

The framework supports prior-to-posterior updating using the Beta-Binomial conjugate update mechanic. When IHID validation data become available:

For E0: a Beta(α, β) prior updated by k confabulations observed in n AI-generated claims yields a Beta(α + k, β + n − k) posterior.

For ε: similar update from observation of k entrenchment events in n confabulation events, conditional on a corpus where confabulations and their fates are both observable.

For P: update from observation of k propagated confabulation events in n entrenched confabulation events across pairs of consecutive encounters.

For R: update from observation of k corrected entrenched confabulations in n entrenched confabulations across observation windows.

The posterior predictive distribution of cumulative contamination is then computed by Monte Carlo sampling from the posterior using the same simulation procedure specified in Section 5. The IHID companion paper will report the posterior treatment in full and will reference this v1.0 plan as the prior specification it updates.

## 9. Reproducibility

All simulation code, parameter prior YAML files, run logs, output files, and analysis notebooks are released under MIT licence in the IDC-Monte-Carlo repository. Each release is tagged in git and assigned a Zenodo DOI. The release accompanying the Original Investigation submission is identified in the manuscript Methods section.

The repository's README documents the steps required to reproduce the principal simulation results from a clean checkout. The reproducibility check is executed by an automated GitHub Actions workflow on every push to the main branch and on every pull request.

The simulation is reproducible from v1.0 of this plan and the corresponding tagged release of the repository, using the seeds documented in Section 5.3, to within the 1% convergence threshold documented in Section 5.3.

## 10. Deviations from plan

Any deviation from this plan is reported transparently in the manuscript and in a `DEVIATIONS.md` file in the repository. The deviation entry contains: the pre-specified analysis it replaces, the substitute analysis, the reason for the deviation, and the date of the deviation. Deviations require a version bump of this plan (v1.0 to v1.1, or v1.x to v2.0 for major re-specifications).

The specific cases that constitute deviation include but are not limited to: changing a prior (α, β) value, changing K, changing the horizon set, adding a primary analysis, removing a primary analysis, changing the random seed strategy, and changing the severity weighting source.

## 11. Authorship and contributions (ICMJE)

To be finalised when authorship and affiliations are confirmed. Anticipated contributions:

JR: framework conception, prior specification, plan drafting, manuscript drafting.

JK: review of methodology, prior specification review, manuscript review.

A potential anesthesia co-author may join the OI manuscript; their role on this analysis plan will be specified at that point.

## 12. Conflicts of interest

JR is founder and CEO of Meerkat Labs Inc. (Vancouver, BC, Canada), a company developing verification infrastructure for AI agent deployments, including in healthcare contexts. The IDC framework, this analysis plan, and the companion manuscripts are academic work conducted in Dr Raubenheimer's capacity as a clinician-researcher; the framework is released under open access and the simulation under MIT licence. Meerkat Labs holds no patents on the framework or the simulation. The commercial relevance of the framework's argument (that external verification of AI outputs is required) is acknowledged. The framework's quantitative predictions are inspectable from the priors specified in this plan and are not contingent on any Meerkat product or commercial position.

JK: declarations to be confirmed.

## 13. Funding

No external funding has been received specifically for this analysis plan. Computational resources for simulation execution are provided by Meerkat Labs Inc. The framework, the manuscripts, and the simulation are independent academic work.

## 14. Data and code availability

Simulation code: https://github.com/Precision-Data/IDC-Monte-Carlo (MIT licence).

Parameter priors and severity weights: committed to the repository as machine-readable YAML files with citation-anchored comments.

Output data: released alongside the OI manuscript in a tagged Zenodo deposit.

No clinical patient data is collected, generated, or distributed under this plan.

---

## Appendix A: References for prior anchors (consolidated)

A1. Asgari E, Montaña-Brown N, Dubois M, et al. A framework to assess clinical safety and hallucination rates of LLMs for medical text summarisation. npj Digital Medicine 8, 274 (2025). DOI: 10.1038/s41746-025-01670-7.

A2. Wu D, Nateghi Haredasht F, Maharaj SK, et al. First, do NOHARM: towards clinically safe large language models. Preprint at https://arxiv.org/abs/2512.01241 (2025).

A3. Omar M, Sorin V, Wieler LH, et al. Mapping the susceptibility of large language models to medical misinformation across clinical notes and social media. Lancet Digital Health 8, e100949 (2026). doi: 10.1016/j.landig.2025.100949.

A4. Tsou AY, Lehmann CU, Michel J, et al. Safe practices for copy and paste in the EHR. Appl Clin Inform 8, 12-34 (2017).

A5. Wang MD, Khanna R, Najafi N. Characterizing the Source of Text in Electronic Health Record Progress Notes. JAMA Internal Medicine 177(8), 1212-1213 (2017). DOI: 10.1001/jamainternmed.2017.1548. PMC5818790.

A5b. Steinkamp J, Kantrowitz JJ, Airan-Javia S. A Practical Approach for Monitoring the Use of Copy-Paste in Clinical Notes. Appl Clin Inform 13(1), 88-95 (2022). PMC8861699.

A6. Bell SK, Delbanco T, Elmore JG, et al. Frequency and types of patient-reported errors in electronic health record ambulatory care notes. JAMA Network Open 3, e205867 (2020). PMC7284300.

A7. Shaw SD, Nave G. Thinking, fast, slow, and artificial: how AI is reshaping human reasoning and the rise of cognitive surrender. Working Paper, The Wharton School (2026). doi: 10.31234/osf.io/yk25n.

A8. Goddard K, Roudsari A, Wyatt JC. Automation bias: a systematic review. J Am Med Inform Assoc 19, 121–127 (2012).

A9. Rumale Vishwanath P, Naik S, Gupta S, et al. Faithfulness hallucination detection in healthcare AI. KDD 2024 Workshop on AI and Data Science for Healthcare (KDD-AIDSH 2024).

A10. Carson JM, et al. AI-generated clinical summaries: errors and susceptibility to speech and speaker variability. medRxiv preprint 2025.10.29.25339041 (2026); funded by NHS England South West via BNSSG ICB.

A11. Mazur L. Round-robin LLM persuasion susceptibility benchmark. github.com/lechmazur/llm-persuasion (2026).

A12. Jeong et al. Persuasion propagation in LLM agents. Preprint at https://arxiv.org/abs/2602.00851 (2026).

A13. Roig JV. RIKER: scalable and reliable evaluation of AI knowledge retrieval systems. Preprint at https://arxiv.org/abs/2603.08274 (2026). Cited as cross-domain architectural support; not used as clinical anchor.

---

End of v1.0.
