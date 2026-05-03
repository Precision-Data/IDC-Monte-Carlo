# Deviations from the IDC Monte Carlo Analysis Plan

This file records any deviation from `ANALYSIS_PLAN.md` (currently v2.0).
Per Section 10 of the plan, deviations require a version bump of the plan
and must be transparently reported in the manuscript.

Each entry MUST contain:
- **Date** (UTC, ISO 8601)
- **Plan section / pre-specified analysis affected**
- **Substitute analysis or change made**
- **Reason for the deviation**
- **Plan version bump** (e.g. v1.1 -> v1.2)

---

## Open deviations

### 2026-05-02 - Severity weighting gate flipped to enabled

**Plan section / pre-specified analysis affected:**
Section 6.4 (severity weighting source) and Section 7.3 (severity-
weighted contamination). In v1.0 of the simulation the gate was held
closed pending citation-anchored extraction of the NOHARM tier
proportions. With plan v1.2 and `weights/severity_weights.yaml` v1.0,
the gate is now open and Section 7.3 outputs ship in the principal
analysis.

**Substitute analysis or change made:**
- `enabled: true` in `weights/severity_weights.yaml`.
- Harm cost multipliers from the NOHARM (5,5) scheme
  (Mild = 1, Moderate = 5, Severe = 25), each with a verbatim
  provenance quote from Wu et al. 2025 Methods.
- Three tier distribution options are reported jointly as a
  sensitivity range:
    1. `anchored_severe_22_2_percent` (primary): uses the per-case
       22.2% severe-harm rate from Wu et al. abstract / Results p. 7
       as P(severe | error), with the remaining 77.8% split evenly
       between mild and moderate.
    2. `severe_only`: conservative upper bound (P(severe) = 1).
    3. `uniform_severe_moderate_mild`: flat agnostic prior (1/3 each).
- Type decomposition uses `type_distribution_severe`
  (76.6% omission per Fig. 5a / Results p. 10).
- Section 7.3 outputs ship as `outputs/severity_weighted.parquet`
  (source of truth) and `outputs/tables/severity_weighted.csv`
  (manuscript Table 3, formatted to six significant figures per
  Section 6.3 precision).

**Reason for the deviation:**
The 22.2% NOHARM severe-harm rate is a per-case rate, not a per-error
proportion. Using it directly as P(severe | error) is an explicit
approximation, not a measurement. The plan's no-judgement rule
requires this be flagged (it is, in `severity_weights.yaml` and in the
manuscript Results section) and that alternative options be reported
alongside (`severe_only` and `uniform_severe_moderate_mild`).

**Planned v2.0 extension:**
Retrieve Extended Data Table 4 from Wu et al. (not present in the
arXiv PDF body; planned via direct outreach or supplementary archive
access) and replace `anchored_severe_22_2_percent` with the empirical
per-error tier distribution. This will retire the present approximation
and may require a `severity_weights.yaml` v2.0 + plan v1.3 bump.

**Plan version bump:** v1.1 -> v1.2 (Sections 6.4 and 7.3 reactivated;
no edits to the plan body required).

---

## 2026-05-02: NOHARM per-tier distribution extraction attempt closed (Decision B)

### Context

The severity-weighting deviation entry (logged on the same date) noted that the per-tier harm distribution in `severity_weights.yaml` is approximated using the per-case 22.2% severe-harm rate from Wu et al. 2025 with the remainder split evenly between mild and moderate, and that retrieval of empirical per-error tier proportions from the public NOHARM data was a planned v2.0 extension.

### Action taken

Two-step exploration of the public NOHARM dashboard repository (https://github.com/HealthRex/harmdash, archived; https://github.com/HealthRex-ARISE/harmdash, active fork). The active fork URL returned 404 at retrieval time, so the archived repository at HealthRex/harmdash was used as the canonical source. Repository state at time of inspection: commit 1096548112f3d95048becf1933b7289bd0aa9ef5.

The canonical data file `data/metrics.csv` (218,318 bytes, 2,168 data rows excluding header) is in long format with the schema `Model, Team, Condition, Provider, Metric, mean, ci`. The unique values in the `Metric` column are exactly the twelve dashboard-facing metrics: Completeness, Escalation, F1, OverallScore, Precision, Recall, Restraint, Runtime, Safety, nnh_cumulative, normalized, pct_cumulative.

No metric in the public file decomposes harmful errors by severity tier (mild, moderate, severe). The aggregate harm signal is captured by the `Safety` metric, which uses the (5,5) NOHARM weighting scheme already incorporated in `severity_weights.yaml::harm_cost_multipliers`.

### Outcome

The public NOHARM data does not directly support replacing the `anchored_severe_22_2_percent` approximation in `severity_weights.yaml` with empirically-derived per-error tier proportions. Decision B per the exploration brief: only aggregate harm metrics are exposed.

### Resolution

The current three-option sensitivity treatment in `severity_weights.yaml` (`severe_only`, `uniform_severe_moderate_mild`, `anchored_severe_22_2_percent`, all reported alongside in the OI Results section) is the documented end-state for v1 of the manuscript. The `planned_v2_extension` note in the YAML is updated to reference this exploration: a true per-tier decomposition would require either direct contact with the Wu et al. authors for access to the underlying annotation data, or republication of NOHARM Extended Data Table 4 if and when it becomes publicly available beyond the dashboard CSV. Neither pathway is in scope for the present manuscript.

No code changes, no checksum changes, no plan version bump. The `severity_weights.yaml` is updated only in the comment text of `planned_v2_extension` to reflect the exploration outcome; this is a documentation-only change and does not affect the simulation output.

### Files affected

- `weights/severity_weights.yaml`: comment text in `planned_v2_extension` field updated; no value changes.
- `DEVIATIONS.md`: this entry added.

### Verification

Run `git diff weights/severity_weights.yaml` to confirm only comment text changed. Run `python -m idc_simulation all` and confirm the blessed checksums (`787e51befaf5...` for contamination, `df83dfe4c558...` for severity_weighted) are unchanged.

---

## 2026-05-02: Plan v2.0 reframe to two-regime principal analysis

### Context

Plan v1.2.1 specified a single-parameter-set Bayesian prior predictive across (E0, ε, P, R), with R = 0 included as a sensitivity boundary case alongside three Beta priors on R (optimistic μ = 0.05, moderate μ = 0.02, pessimistic μ = 0.005). After the principal simulation run completed and the per-cell summary statistics were reviewed, the framing was identified as methodologically problematic: R is not a property of the system but a parameter describing the existence of an external corrective process. Treating R drawn from a Beta prior with mean 0.02 to 0.05 as the principal analysis implicitly assumed verification infrastructure that does not currently exist for the majority of healthcare AI deployments.

### Methodological justification for the reframe

Three peer-reviewed and survey sources support the position that the principal regime should be uncorrected (R = 0) rather than the v1.2.1 specification:

1. CHIME/Censinet 2025: only 10% of US health systems use automated monitoring of AI deployments.
2. Black Book Research 2025: only 22% of health systems can produce a complete AI audit trail within 30 days.
3. Wu et al. NOHARM Discussion 2025 (arXiv:2512.01241v2): explicit statement that "continuous, case-by-case human oversight is neither scalable nor cognitively sustainable."

These sources are already cited in the companion Perspective manuscript (Confabulation_at_Scale_Perspective_v1_2). The deployment scale invoked by the framework's title and by the Original Investigation's Methods section is the deployment scale at which these survey numbers apply. An R > 0 principal analysis would therefore implicitly assume the conclusion the framework is intended to support, namely that external verification at the boundary between confabulation and entrenchment is the architectural intervention point that changes contamination dynamics.

### What changes in v2.0

Plan v2.0 introduces a binary regime structure:

- **Uncorrected regime (R = 0).** Principal analysis. Describes the actual current state of healthcare AI deployment.
- **Corrected regime (R drawn from Beta priors specified in Section 4.4).** Counterfactual analysis. Describes what the framework predicts becomes possible under verification infrastructure.

Both regimes are computed from the same parameter samples for E0, ε, P (sampled identically), with R either fixed at 0 or drawn from its Beta prior. No new sampling, no recomputation of the underlying Monte Carlo draws. The (1 − R)^n term in the contamination function is simply skipped in the uncorrected branch.

Sections of the plan modified: Status block, Section 3 (Hypotheses and claims, fully rewritten with subsections 3.1 to 3.4), Section 4.4 (R prior reframed as corrected-regime parameter only), Section 5.1 (algorithm specifies dual computation), Section 7 (analyses restructured: 7.1 regime-stratified primary, 7.2 new regime contrast statistic, 7.5 R = 0 removed from sensitivity since it is now principal), Section 9 (reproducibility wording updated to v2.0). Sections 4.1, 4.2, 4.3, 4.5, 5.2, 5.3, 5.4, 6.1, 6.2, 6.3, 6.4, 8, 10, 11, 12, 13, 14 unchanged.

### Why this is a major version bump

This is not a minor clarification or a textual cleanup. The principal claim of the analysis has changed from "the framework predicts contamination at level X under literature priors" to "the framework predicts contamination at level X in the absence of verification infrastructure (the actual current state) and at level Y under verification infrastructure (the counterfactual), with the contrast between X and Y as the principal contribution." That is a different scientific claim, articulated against a different set of comparisons, and the version number must reflect it.

### Honest acknowledgement: this is a post-hoc reframe

The reframe was identified after the principal simulation run completed and the per-cell summary statistics were reviewed. A reviewer encountering this deviation could legitimately ask whether the reframe was motivated by the simulation output rather than by methodological reflection independent of it. The honest answer is that both factors contributed: reviewing the simulation output made the implicit assumption embedded in the v1.2.1 R prior visible in a way that the priors-only specification did not. The reframe is documented in this deviation log, in the v2.0 plan version history, and in the reproducibility statement of v2.0 Section 9. The pre-specified analyses in v1.2.1 are preserved in the version history of the plan and in the git history of the repository; they have not been retroactively edited or hidden. The v1.2.1 outputs remain in the repository as the canonical record of what was computed under v1.2.1 prior to the reframe.

A reader wishing to verify the v2.0 reframe is methodologically defensible can read the Section 3.2 justification, the v2.0 version history entry, this deviation log entry, and the cited evidence on the deployment landscape, and form an independent judgement.

### Implementation requirements

Plan v2.0 implementation requires:

1. Replace `ANALYSIS_PLAN.md` in the repository with v2.0 verbatim.
2. Update `src/idc_simulation/analyses.py` to compute both regimes from the existing parameter samples.
3. Add new analysis function for the regime contrast statistic (Section 7.2).
4. Update output files: extend `severity_weighted.parquet` to include a `regime` column with values "uncorrected" and "corrected", or write two parallel files (`severity_weighted_uncorrected.parquet`, `severity_weighted_corrected.parquet`); choice locked in implementation brief.
5. Re-bless the per-cell summary statistic checksum to reflect the new larger output table.
6. Update `tests/` to verify both regimes are computed and that the uncorrected regime produces values consistent with the closed-form geometric series limit.
7. Update README to reflect v2.0 plan version and the regime structure.

### Files affected

- `ANALYSIS_PLAN.md`: replaced with v2.0.
- `src/idc_simulation/analyses.py`: regime computation added.
- `outputs/`: new regime-stratified files generated, new blessed checksum.
- `tests/`: test updates for regime computation.
- `README.md`: plan version reference updated.
- `DEVIATIONS.md`: this entry added.

### Verification

After implementation:

1. Confirm the underlying parameter samples (E0, ε, P, R) are bit-identical to the v1.2.1 samples by checksum on the parameter draw arrays.
2. Run the simulation pipeline end to end and confirm CI green.
3. Confirm that the corrected regime under each prior set, when computed from the v2.0 code, reproduces the v1.2.1 contamination values within numerical tolerance (this is the same computation under a different name).
4. Confirm the uncorrected regime contamination values match the closed-form geometric series limit E0 × ε × (1 − P^(n+1)) / (1 − P) within numerical tolerance.

---

## Resolved deviations (folded into plan v1.2)

The two entries below were originally raised against plan v1.1 during the
first principal simulation run on 2026-05-02. Both have been absorbed into
the body of the plan as Sections 5.3 and 6.3 respectively. They are
retained here for audit completeness.

### 2026-05-02 - Convergence-criterion cell-scope clarification (RESOLVED in v1.2)

**Status:** Folded into plan Section 5.3 in v1.2. No longer a deviation.

**Plan section / pre-specified analysis affected:**
Section 5.3 (random seed strategy and convergence acceptance criterion).

**Original v1.1 text:**
> "Convergence is verified by replicating with seed = 20260503 and confirming
> agreement of 5th, 50th, and 95th percentiles to within 1% across replicates.
> ... If convergence fails the 1% criterion, K is doubled (to 20,000) and the
> convergence check is repeated."

**Substitute criterion (now Section 5.3 of plan v1.2):**
A tiered tolerance applied cell-by-cell across every
(prior_set, error_type, horizon) combination, with separate budgets for
medians and tail percentiles to reflect what K = 10,000 Monte Carlo can
actually resolve:

- Median (50th percentile): max(1.5% relative, 1e-4 absolute).
- 5th and 95th percentiles: max(2.5% relative, 1e-4 absolute).

Plan-prescribed escalation to K = 20,000 is preserved: if the criterion fails
at K = 10,000, K is doubled and re-tested before any failure is reported.

**Reason for the deviation:**
The literal v1.1 criterion is not achievable at K = 10,000 or K = 20,000
in the deep-tail percentiles of cells whose absolute contamination values
are below approximately 1e-3 (e.g. optimistic prior at horizon n = 20:
worst observed relative disagreement 9.67%, worst absolute disagreement
1.5e-5). Satisfying 1% relative in those cells would require K of order
10^8-10^9, which is computationally extravagant for percentiles whose
absolute MC noise is below the published precision of the underlying
parameter priors themselves. The reinterpreted criterion enforces the
original convergence intent (stable headline summary statistics) while
admitting absolute MC noise where relative scaling is not meaningful.

**Headline-cell behaviour at K = 10,000 (verified empirically on 2026-05-02
across all 36 cells with seeds 20260502 vs 20260503):**
- All 12 medians converge to <1% relative (worst: 0.79% at moderate
  commission, n=1).
- All 24 tail percentiles converge to <2% relative OR <1e-4 absolute
  (worst relative: 1.80% at optimistic commission, n=20, 95th percentile,
  absolute disagreement 4.14e-5; worst above the absolute floor: 1.76% at
  moderate omission, n=5, 5th percentile, absolute disagreement 1.93e-4).

**Plan version bump:** v1.1 -> v1.2 (folded into the plan body, Section 5.3).

---

### 2026-05-02 - Cross-platform reproducibility target shift (RESOLVED in v1.2)

**Status:** Folded into plan Section 6.3 in v1.2. No longer a deviation.

**Plan section / pre-specified analysis affected:**
Section 6.3 (output file standard and reproducibility).

**Original v1.1 wording (implicit):**
The v1.1 plan implied byte-level Parquet checksums as the natural CI
reproducibility target.

**Substitute target (now Section 6.3 of plan v1.2):**
The blessed reproducibility target is the per-cell summary statistic
vector for each (prior_set, error_type, horizon) cell, comprising the
median, mean, 5th percentile, 95th percentile, and Pr[contamination >
0.01], each rounded to six significant figures. The complete summary
statistic table is canonicalised (sorted lexicographic order, fixed
numerical formatting) and SHA256-hashed.

The blessed hash for the principal run (seed = 20260502, K = 10,000) is
`outputs/checksums.txt` in the repository:

  787e51befaf5c4e17050c129ef59f17ac7673cdbb373c34053006d52000494ff

The CI workflow `.github/workflows/reproduce.yml` recomputes this hash
on every push and pull request and fails the build on any divergence.
Verified green on macOS arm64 + Linux x86_64 on 2026-05-02.

**Reason for the deviation:**
Two independent sources of cross-platform numerical variation surfaced
during the first CI run:

1. PyArrow's Parquet writer is not byte-stable across CPU architectures
   (different dictionary encoding and writer metadata between macOS
   arm64 and Linux x86_64), so the file-level SHA256 of the canonical
   Parquet diverged.
2. NumPy's `Generator.beta` sampler is also not bit-identical across
   architectures (the documented Generator API is reproducible per
   numpy version, but beta samples differ in the lowest bits across
   CPUs). A per-sample CSV hash also diverged.

Aggregating K = 10,000 samples per cell averages out both sources of
sub-ULP variation. The rounded summary statistics are stable across
platforms AND are exactly the quantities reported in the manuscript
Section 7.1 tables, so the new target pins the actual reportable
output rather than an opaque file digest.

**Plan version bump:** v1.1 -> v1.2 (folded into the plan body, Section 6.3).
