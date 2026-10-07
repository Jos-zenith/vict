# Additions for report.md §3 (methods), from the DS1 pilot code

Each item is a decision the code makes that the report does not state yet.

- **Error-risk label (C1).** A window of a noisy copy is *risky* when, at the
  default SVM threshold, noise added a false V call or lost a true V beat relative
  to the same window of the paired clean copy scored by the same classifier
  (`false_v > clean false_v` or `lost_v > clean lost_v`). Clean-copy windows are
  never risky, so errors the classifier also makes on clean signal (e.g. record
  207's bundle-branch beats called V) are not counted as noise risk. Gates are
  trained on noisy copies only. (`src/vgate/windows.py`, `risky_vs_clean`)
- **Operating points (§3.5).** For every arm, the operating point is the one with
  the fewest false V calls whose V retention is at least the target
  (0.9 / 0.8 / 0.95 × Robust's default retention). Gated arms search all pairs of
  SVM threshold (−1 to 3, step 0.01) and gate cut-off. The coverage rule is a
  constraint on that search (a gate may reject at most 20 % of windows), not only
  a check afterwards. A fixed-SVM variant (`Gcs@default`) is reported alongside.
- **Primary analysis.** Operating points chosen on the held-out noise itself
  (retention exactly matched), leave-one-noise-type-out over em / ma / bw. Points
  chosen on the other two noise types and transferred are reported as secondary.
  Coverage is checked per fold, not on the average across folds.
- **Ventricular flutter/fibrillation.** Windows overlapping a VF/VFL episode
  (MIT-BIH `[` … `]`, only record 207 in DS1) are left out of scoring, as in
  ANSI/AAMI EC57: they contain no beats to score.
- **RR prematurity ratios.** Two features are added to the specified list:
  RR-before / mean of last 10 RR and RR-after / mean of last 10 RR. A linear SVM
  cannot form ratios, and prematurity carries most of the inter-patient V signal.
- **SQI log floor.** SQIs are clipped at 1e-3 before the log (an empty window
  gives log 1e-3 = −6.9 rather than −27.6, which would dominate the gate's scaling).
- **Threshold grid.** Per-window counts are kept at SVM thresholds −1.0 to 3.0 in
  steps of 0.01; at 0.05 one step changed V retention by ~4 points, too coarse to
  match retention targets.
- **Noise mixing.** Each 2-min noisy segment's gain is set from the power of the
  noise block it uses (sigamp definitions: S = trimmed-mean QRS p-p² / 8 over the
  first 300 normal beats; N = trimmed-mean RMS² of mean-removed 1 s chunks), with
  the block mean removed and 1 s linear ramps inside the segment. nst instead
  measures N once over the first 300 s of the noise record.
- **118e12 acceptance (open).** With NSTDB's own gain our mixing reproduces
  118e12 at 0.96 % RMS difference; with the gain we compute it is 1.45 %, because
  our gain is 0.35 % below NSTDB's. The team has to decide whether this passes.
