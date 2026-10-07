# freeze-v1: pre-freeze checks and decisions

Recorded 2026-10-07 on the commit tagged `freeze-v1`. Environment:
`requirements-freeze.txt` (Python 3.12, Windows 11).

## Pre-freeze checks

| Check | Target | Result |
|---|---|---|
| Unit and data tests (`pytest`) | all pass | 31 passed |
| Lint (`ruff check .`) | clean | clean |
| Split V counts (`scripts/check_splits.py`) | 3323 / 465 | 3323 / 465 OK |
| Detector on clean DS1 (`scripts/check_detector.py`) | Se and PPV >= 0.99 | Se 0.9972, PPV 0.9903 |
| Base V sensitivity, grouped CV on DS1-train (`scripts/check_base.py`) | >= 70 % | 91.5 % |
| C band-pass vs Python (`c/tests/test_bandpass.c`) | within 1e-4 mV | identical (0 mV) |
| Mixer vs NSTDB 118e12 (`tests/test_mixer.py`) | < 1 % RMS | 0.96 % at NSTDB's gain; our gain within 0.35 % (1.45 % end to end) |
| DS2 path dry run (`scripts/run_ds2.py --dry-run`) | runs end to end | runs; verdict machinery exercised on DS1-cal |

The C tests were built with `zig cc -std=gnu99 -O2 -ffp-contract=off` (no CMake on
the development laptop); CI builds them with CMake.

## Decisions taken for the freeze

1. **DS2 operating points:** matched on DS2 by fixed rules that do not look at false
   V calls; gated arms keep the SVM at its default threshold.
2. **Claim rule:** decided on all DS2 records (Gcs vs raised threshold); results
   without clean-error records are reported, not deciding.
3. **C core check:** band-pass only before the freeze; the rest of the chain is
   ported after it.
4. **118e12:** accepted as a split test (mechanics at NSTDB's gain, plus our gain
   within 0.35 % of NSTDB's), with the deviation recorded in the report.

Full protocol: `scripts/run_ds2.py` docstring and `docs/report_section3_additions.md`.

## Deviations from the Phase 0 checklist (recorded after the DS2 run)

DS2 ran on 2026-10-07 from `freeze-v1` before these checklist items were complete.
None of them could change the verdict, which follows from rules frozen in the tag;
the post-freeze additions below are labelled as such.

| Checklist item | Status at the freeze | After the freeze |
|---|---|---|
| Commit three noise schedules per record | Generated deterministically by the frozen code from committed configs; not written to a file | `configs/noise_schedules.json` (`scripts/export_schedules.py`): 44 records x 3 offsets with per-noise gains; all 396 processed noisy copies match it |
| Tag paired differences by cause and place | Pairs used for the risk labels; cause split done by hand for record 114 only | `docs/paired_differences.md` (`scripts/analyze_differences.py`), post-hoc, DS1-cal and DS2 |
| C core matches Python on synthetic vectors | Real MIT-BIH 119 vectors and a pass-through test only | Impulse, step, 10 Hz and 0.2 Hz sines and white noise added; all six sets bit-identical |
| Pilot's predicted DS2 CI width | **Not done.** A width computed now would be written after seeing DS2, so it is not reported as a prediction | none |
| Freeze operating paths for 0.9 / 0.8 / 0.95 | Rules frozen for all three targets; no numeric paths (decision 1: matched on DS2) | none |
| 118e12 within 1 % RMS | 0.96 % at NSTDB's gain, 1.45 % at our gain (decision 4) | none |
| Reproducible frozen repo | Tag and commits only on the development laptop; `ziglang` (used to build the C tests) missing from `requirements-freeze.txt`; DS2 models in `results/` (not in git) | `ziglang` added to `requirements-freeze.txt` on main (the tag's copy lacks it) |
