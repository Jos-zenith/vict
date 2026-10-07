# vgate — signal-quality gating vs a conservative threshold

Final-year project: does an error-risk gate using SQIs cut false ventricular (V)
calls more than raising the threshold of a noise-trained classifier, on an
inter-patient MIT-BIH split with held-out NSTDB noise?

## Setup (Windows PowerShell)

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
python scripts/download_data.py     # MIT-BIH + NSTDB into data/raw (~100 MB)
pytest                              # data tests run once data/raw exists
python scripts/check_splits.py      # DS1 V-beat counts vs configs/splits.toml
python scripts/check_detector.py    # Pan-Tompkins Se / PPV on clean DS1 (target >= 0.99)
python scripts/check_base.py        # Base V sensitivity, grouped CV on DS1-train (>= 70 %)
python scripts/run_pilot.py --record 114   # whole chain, one DS1-cal record
python scripts/run_pilot.py         # DS1 pilot: Robust, gates, matched retention, bootstrap
```

`run_pilot.py` caches each processed record copy under `results/cache/`; bump
`CACHE_VERSION` in `src/vgate/pipeline.py` after changing anything upstream of the
classifier.

macOS / Linux: `source .venv/bin/activate` instead of the Activate line.

## Layout

| Path | What | Owner |
| --- | --- | --- |
| `configs/` | Record splits and every pipeline parameter. Part of the freeze tag. | all |
| `src/vgate/data/` | MIT-BIH / NSTDB loading, AAMI mapping, DS2 access guard | Chandru |
| `src/vgate/dsp/` | Classifier band-pass (0.5–40 Hz, float32 SOS, causal) | Chandru |
| `src/vgate/detectors/` | Pan–Tompkins and Mexican-hat streaming detectors | Zenith |
| `src/vgate/noise/` | NSTDB-style mixer and SNR schedules | Shapari |
| `src/vgate/sqi.py` | qSQI, pSQI, kSQI, basSQI | Shapari |
| `src/vgate/features.py` | Per-beat features | Chandru |
| `src/vgate/models/` | Base/Robust SVM, Gc/Gcs gates | Chandru |
| `src/vgate/pipeline.py` | One record copy: mix, detect, features, labels, window SQIs (cached) | all |
| `src/vgate/windows.py` | Per-window table: the contract between classifier and evaluation | all |
| `src/vgate/evaluation/` | Beat matching, bootstrap CIs | Chandru |
| `c/` | Portable C core (post-freeze port), CMake + tests | Zenith |
| `firmware/` | ESP32-S3 project (Should tier) | Zenith |
| `docs/papers/` | Supplied PDFs (git-ignored) | — |

Stubs raise `NotImplementedError` and carry their spec in the docstring.

## The window table

Everything after the classifier (gate training, risky labels, threshold sweeps,
matched retention, bootstrap, coverage) reads one table with a row per 10 s window
per record copy: `vgate.windows.WindowTable`. Build rows with
`windows.from_record(...)`; the scoring rules and column meanings are in the
`vgate/windows.py` docstring, and `WindowTable.validate()` enforces them on every
build, save and load. Change the schema there, in one place, and tell the team.

## Rules that the code enforces

- **DS2 is locked.** `mitdb.load_record` refuses DS2 records (and 202) unless
  called with `allow_test=True`. Only the frozen DS2 run should pass it.
- **Config is the source of truth.** Record lists, filter/detector parameters,
  SNR schedule and claim-rule constants live in `configs/*.toml`, not in code.
- **Freeze = git tag.** Before running DS2, tag the commit (e.g. `freeze-v1`)
  with code, configs, weights and thresholds; run DS2 from that tag only.

## Freeze and the DS2 run

1. Pre-freeze checks: `pytest`, `scripts/check_splits.py`, `scripts/check_detector.py`,
   `scripts/check_base.py`, the C tests (`ctest --test-dir c/build`), and
   `python scripts/run_ds2.py --dry-run` (whole DS2 path with DS1-cal standing in).
2. Commit, then `git tag -a freeze-v1 -m "..."`.
3. `git checkout freeze-v1 && python scripts/run_ds2.py`. It refuses to run off a
   clean `freeze-*` tag and refuses a second run; the verdict lands in
   `results/ds2/<tag>/verdict.md`. Protocol and claim rule:
   `scripts/run_ds2.py` docstring and `docs/report_section3_additions.md`.

## C core

Needs CMake and a C compiler (e.g. MSVC Build Tools, or MinGW via MSYS2):

```powershell
cmake -S c -B c/build
cmake --build c/build
ctest --test-dir c/build
```

`python scripts/export_c_vectors.py` regenerates the Python reference vectors the C
tests compare against.
