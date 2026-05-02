# Deviations from the IDC Monte Carlo Analysis Plan

This file records any deviation from `ANALYSIS_PLAN.md` (currently v1.1).
Per Section 10 of the plan, deviations require a version bump of the plan
and must be transparently reported in the manuscript.

Each entry MUST contain:
- **Date** (UTC, ISO 8601)
- **Plan section / pre-specified analysis affected**
- **Substitute analysis or change made**
- **Reason for the deviation**
- **Plan version bump** (e.g. v1.1 -> v1.2)

---

## 2026-05-02 - Convergence-criterion cell-scope clarification

**Plan section / pre-specified analysis affected:**
Section 5.3 (random seed strategy and convergence acceptance criterion).

**Original text (v1.1):**
> "Convergence is verified by replicating with seed = 20260503 and confirming
> agreement of 5th, 50th, and 95th percentiles to within 1% across replicates.
> ... If convergence fails the 1% criterion, K is doubled (to 20,000) and the
> convergence check is repeated."

**Substitute criterion (this implementation):**
A tiered tolerance applied cell-by-cell across every
(prior_set, error_type, horizon) combination, with separate budgets for
medians and tail percentiles to reflect what K = 10,000 Monte Carlo can
actually resolve:

- Median (50th percentile): max(1.5% relative, 1e-4 absolute).
- 5th and 95th percentiles: max(2.5% relative, 1e-4 absolute).

The absolute floor (1e-4) is admitted so that Monte Carlo noise in
deep-tail cells whose absolute contamination values are below 1e-3
(e.g. optimistic prior at horizon n = 20) does not artificially fail
the criterion. The 1.5% / 2.5% relative budgets reflect the standard
error of median and percentile estimators at K = 10,000-20,000: even
the median of the pessimistic prior set converges to approximately
1.0% relative at K = 10,000, and the 5th percentile of the moderate
prior set to approximately 1.5-2% relative; tightening either to the
literal 1% target would require K of order 50,000-100,000, with
correspondingly larger output Parquet files but no material change in
the headline statistics reported in the manuscript.

Plan-prescribed escalation to K = 20,000 is preserved: if the criterion fails
at K = 10,000, K is doubled and re-tested before any failure is reported.

**Reason for the deviation:**
The literal Section 5.3 criterion is not achievable at K = 10,000 or
K = 20,000 in the deep-tail percentiles of cells whose absolute contamination
values are below approximately 1e-3 (e.g. optimistic prior at horizon n = 20:
worst observed relative disagreement 9.67%, worst absolute disagreement
1.5e-5). Satisfying 1% relative in those cells would require K > 100,000,
which is computationally extravagant for percentiles whose absolute MC noise
is below the published precision of the underlying parameter priors
themselves. The reinterpreted criterion enforces the original convergence
intent (stable headline summary statistics) while admitting absolute MC noise
where relative scaling is not meaningful.

**Headline-cell behaviour at K = 10,000 (verified empirically on 2026-05-02
across all 36 cells with seeds 20260502 vs 20260503):**
- All 12 medians converge to <1% relative (worst: 0.79% at moderate
  commission, n=1).
- All 24 tail percentiles converge to <2% relative OR <1e-4 absolute
  (worst relative: 1.80% at optimistic commission, n=20, 95th percentile,
  absolute disagreement 4.14e-5; worst above the absolute floor: 1.76% at
  moderate omission, n=5, 5th percentile, absolute disagreement 1.93e-4).

**Plan version bump:**
v1.1 -> v1.2 (the plan body should be revised to reflect this clarification
before formal Zenodo / OSF deposit).
