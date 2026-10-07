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
  Coverage is checked per fold, not on the average across folds. In this oracle
  setting the gated arms tune two settings on the held-out data (SVM threshold and
  gate cut-off) and the raised-threshold arm one, which slightly favours the gates;
  `Gcs@default` tunes only the cut-off.
- **Clean-error records.** Every result is given for all records and without the
  records whose clean copy already has more than 60 false V/h under Robust at the
  default threshold (`[evaluation] clean_error_fv_h`; record 207 in DS1-cal). Their
  false V calls are classifier errors on clean signal, which a noise gate neither
  can nor should remove, and they otherwise dominate pooled totals.
- **Coverage curve.** Gated arms are reported at deferral caps of 5, 10, 15 and 20 %
  of windows (`[evaluation] coverage_curve`), since every gate uses the whole
  allowance it is given.
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

# Pilot results worth reporting (DS1-cal, retention 0.9 x Robust default)

`python scripts/run_pilot.py`; full output in `results/pilot/summary.json`,
figure in `results/pilot/coverage_curve.png`.

- **Record 207 decides the pooled number.** Gcs vs raised threshold (oracle, 20 %
  deferral cap): +40 % [11, 90] over all six records, +87 % [80, 93] without 207
  (per fold em/ma/bw +86/+80/+93 %); on 207 alone −2 %. 207 holds 52 % of the
  threshold arm's false V calls, almost all bundle-branch beats called V on clean
  signal (2706 false V/h on its clean copy). Expect the same on DS2: report the
  effect with and without clean-error records.
- **Gates use (nearly) the full deferral allowance.** Gcs sits at the cap at every
  coverage level and Gc within 2 points of it (`@default` variants stop earlier,
  where the retention target binds), so "gate vs threshold" is largely "defer x % vs defer
  nothing". The like-for-like evidence that the SQIs help is **Gcs vs Gc at the same
  cap**: +8 / +12 / +13 / +17 % at 5 / 10 / 15 / 20 % deferral (all records), all
  three folds positive at every cap; +34 % [16, 53] at 20 % without 207.
- **Gate settings do not transfer to a new noise type** (secondary, cut-offs set
  on the other two noise types): Gcs keeps 75 % (ma) and 76 % (bw) of windows,
  failing the coverage rule in two of three folds, and misses its retention target
  in bw (0.582 vs 0.619). Gcs vs Gc falls to −8.5 % (−65 % on em, where Gcs deferred
  7 % of windows and Gc 20 %). The SQI advantage seen with matched settings does not
  survive this deployment-like case; DS2 cut-offs must be fixed before the run, so
  this is the realistic expectation.
- **Where the false V calls come from** (Base, record 114): clean copy 8 false V/h;
  em copy 565 = 245 from spurious detections + 320 from real non-V beats called V.
