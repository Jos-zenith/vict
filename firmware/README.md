# ESP32-S3 replay firmware

An ESP-IDF project that compiles the portable C core in `../c` unchanged (as the
`vgate_core` component) and runs MIT-BIH records streamed from the laptop over the
board's native USB port. The goal of this stage is narrow: **show that the board
produces exactly the same answers as Python.** No electrodes yet.

> Status: written but **not yet built or run on hardware.** The same C core passes
> on the laptop (see below). The firmware's main file has only been compile-checked
> against stub ESP-IDF headers.

## Build and flash

Needs ESP-IDF v5.x.

```
cd firmware
idf.py set-target esp32s3
idf.py build flash
```

Plug the laptop into the board's **native USB** port (labelled `USB` on the
DevKitC-1, not `UART`). The replay protocol owns that port. ESP-IDF logs stay on
UART0.

## Replay and compare

```
pip install -e ".[board]"          # pyserial
python scripts/check_c_core.py --serial COM5 --clean-only --records 119
python scripts/check_c_core.py --serial COM5        # every DS1 copy, clean + noisy
```

For each record copy the host sends `"VGR1"`, a little-endian uint32 sample count,
and the raw samples (mV) as little-endian float64. The board prints the same lines
as the laptop tool `c/tools/vgate_replay` (`B` beat, `W` window, `E` end), followed
by a timing line:

```
T n_samples max_sample_us mean_sample_us max_window_ms
```

Time spent writing to USB is excluded from these figures. The host checks the
board's output against `vgate.reference` with the same criteria as the laptop build:
- R peaks, QRS widths, V calls and window states are identical.
- Features agree within 1e-12 relative. All but `log()` should be bit-identical;
  newlib's `log()` may differ by an ulp.
- Decision values agree within 1e-12.
- There are no late detections.

Floating-point notes:
- The classifier band-pass is float32 on the S3 FPU. The component builds with
  `-ffp-contract=off` so that `a*b + c` is never fused into `madd.s`.
- The detector and features run in float64. On the S3 that is IEEE soft-float,
  which is correctly rounded, so it should match the laptop exactly.

Memory: `vgate_pipeline_t` is about 160 KB, allocated statically in internal RAM.
The core never uses the heap. Most of that memory is the detector's 4,680-sample
float64 history. The detector needs it to clip its look-backs exactly where the
Python reference does, because the reference pushes 3,600-sample chunks.

## Acceptance (from the project plan)

- Firmware output matches Python within the tolerances above on every DS1 copy.
- Worst-case processing time per 10 s window (`max_window_ms`) is under 2.5 s.

## Later: live input

AD8232 → ADS1115, with a timer-triggered single-shot conversion every 2.78 ms
(360 Hz) feeding `vgate_pipeline_push`. Only after the replay matches.
