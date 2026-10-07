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
