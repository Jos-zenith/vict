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
```

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

## C core

Needs CMake and a C compiler (e.g. MSVC Build Tools, or MinGW via MSYS2):

```powershell
cmake -S c -B c/build
cmake --build c/build
ctest --test-dir c/build
```
