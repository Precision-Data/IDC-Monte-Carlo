# Deviations from the IDC Monte Carlo Analysis Plan

This file records any deviation from `ANALYSIS_PLAN.md` (currently v1.2).
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
