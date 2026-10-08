"""Check the C core against the Python reference on whole records.

  python scripts/check_c_core.py                 # DS1 clean + every NSTDB copy, laptop C build
  python scripts/check_c_core.py --clean-only --records 119 208
  python scripts/check_c_core.py --serial COM5   # the same records replayed on the ESP32-S3

Each record copy (the DS1 copies of pipeline.ds1_copies: clean, and em/ma/bw mixed at
every schedule offset) goes through the Python reference (vgate.reference.run) and
through the C core: c/build/vgate_replay (laptop) or the replay firmware (firmware/, over USB).

Pass criteria, per copy:
  detector    R peaks and integrator QRS widths identical (raw detector emissions
              and the beats the pipeline classifies)
  features    |C - Python| <= 1e-12 * max(1, |value|); all but log() is expected to
              be bit-identical, log() may differ by an ulp between C libraries
  decision    |C - Python| <= 1e-12 (Python's dot product goes through BLAS)
  V calls     identical
  windows     identical states
  pipeline    no late detections, no pending-queue overflow, no stale QRS
DS2 is never loaded.
"""

from __future__ import annotations

import argparse
import os
import struct
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from vgate import config, design
from vgate.data import mitdb
from vgate.pipeline import Copy, _noisy_signal, ds1_copies
from vgate.reference import run as reference

EXE = config.ROOT / "c" / "build" / ("vgate_replay.exe" if os.name == "nt" else "vgate_replay")
FEATURE_TOL = 1e-12
DECISION_TOL = 1e-12
STATES = {0: "insufficient", 1: "V suspected", 2: "no V"}
MAGIC = b"VGR1"


def signal_of(c: Copy) -> np.ndarray:
    return _noisy_signal(c, mitdb.load_record(c.record))[0]


def parse(lines: list[str]) -> dict:
    """Parse the replay protocol (see c/tools/vgate_replay.c)."""
    d, b, w, e = [], [], [], None
    for line in lines:
        f = line.split()
        if not f:
            continue
        if f[0] == "D":
            d.append((int(f[1]), float(f[2])))
        elif f[0] == "B":
            b.append([float(v) for v in f[1:]])
        elif f[0] == "W":
            w.append(STATES[int(f[4])])
        elif f[0] == "E":
            e = [int(v) for v in f[1:]]
    b = np.array(b).reshape(-1, 4 + 14)
    return {"emitted": d, "beats": b, "states": w, "end": e}


def run_exe(raw: np.ndarray, exe: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "x.f64"
        raw.astype("<f8").tofile(path)
        out = {}
        for mode in (["--detector"], []):
            res = subprocess.run([str(exe), *mode, str(path)], capture_output=True, text=True,
                                 check=True)  # fmt: skip
            out.update({k: v for k, v in parse(res.stdout.splitlines()).items()
                        if v is not None and (mode or k != "emitted")})  # fmt: skip
    return out


def run_serial(raw: np.ndarray, port: str, baud: int = 2_000_000) -> dict:
    """Stream the record to the replay firmware and collect its output lines."""
    import serial  # pyserial, only needed for the board

    with serial.Serial(port, baud, timeout=30) as s:
        s.reset_input_buffer()
        payload = MAGIC + struct.pack("<I", len(raw)) + raw.astype("<f8").tobytes()
        writer = threading.Thread(target=s.write, args=(payload,), daemon=True)
        t0 = time.perf_counter()
        writer.start()
        lines = []
        while True:
            line = s.readline().decode("ascii", "replace").strip()
            if not line:
                raise TimeoutError("no output from the board for 30 s")
            if line[0] in "BWE" or line.startswith("T "):
                lines.append(line)
            if line.startswith("E "):
                break
        writer.join()
    out = parse(lines)
    out["timing"] = [ln for ln in lines if ln.startswith("T ")]
    out["seconds"] = time.perf_counter() - t0
    return out


def compare(ref: dict, out: dict) -> dict:
    det, width = ref["det"], ref["width"]
    row = {"beats": len(det), "problems": []}

    if "emitted" in out:  # raw detector emissions, deduplicated like detect_with_widths
        em = dict(out["emitted"])
        r = np.array(sorted(em), dtype=int)
        if not np.array_equal(r, det):
            row["problems"].append(
                f"detector: {len(np.setdiff1d(det, r))} only in Python, "
                f"{len(np.setdiff1d(r, det))} only in C")
        elif not np.array_equal([em[k] for k in r], width):
            row["problems"].append("detector: QRS widths differ")

    b = out["beats"]
    br = b[:, 0].astype(int)
    if not np.array_equal(br, det):
        row["problems"].append(f"pipeline beats: {len(br)} in C vs {len(det)} in Python")
        return row
    feats = b[:, 4:]
    diff = np.abs(feats - ref["features"])
    row["feature_max_diff"] = float(diff.max(initial=0.0))
    row["bit_identical"] = float((feats == ref["features"]).mean()) if len(det) else 1.0
    if (diff > FEATURE_TOL * np.maximum(1.0, np.abs(ref["features"]))).any():
        row["problems"].append(f"features: max |diff| {row['feature_max_diff']:.3g}")
    ddiff = np.abs(b[:, 2] - ref["decision"])
    row["decision_max_diff"] = float(ddiff.max(initial=0.0))
    if (ddiff > DECISION_TOL).any():
        row["problems"].append(f"decision: max |diff| {row['decision_max_diff']:.3g}")
    if not np.array_equal(b[:, 3] == 1, ref["decision"] > design.THRESHOLD):
        row["problems"].append("V calls differ")
    if out["states"] != ref["states"]:
        n = sum(a != c for a, c in zip(out["states"], ref["states"], strict=False))
        row["problems"].append(
            f"windows: {len(out['states'])} vs {len(ref['states'])}, {n} states differ")
    _, late, overflow, stale = out["end"]
    if late or overflow or stale:
        row["problems"].append(f"pipeline: late {late}, overflow {overflow}, stale {stale}")
    lat = (b[:, 1] - br) / 360
    row["latency_max_s"] = float(lat.max(initial=0.0))
    return row


def check_copy(c: Copy, exe: Path) -> tuple[str, dict]:
    raw = signal_of(c)
    return c.name, compare(reference(raw), run_exe(raw, exe))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--records", type=int, nargs="*", help="DS1 records (default: all)")
    ap.add_argument("--clean-only", action="store_true")
    ap.add_argument("--exe", type=Path, default=EXE)
    ap.add_argument("--serial", help="replay on the ESP32 at this port instead")
    args = ap.parse_args()

    copies = [c for c in ds1_copies() if c.copy == "clean" or not args.clean_only]
    if args.records:
        copies = [c for c in copies if c.record in args.records]

    rows = {}
    if args.serial:
        for c in copies:
            raw = signal_of(c)
            out = run_serial(raw, args.serial)
            rows[c.name] = compare(reference(raw), out)
            print(c.name, f"{out['seconds']:.0f} s", *out["timing"], flush=True)
    else:
        if not args.exe.exists():
            sys.exit(f"{args.exe} not found: build c/ first (see c/CMakeLists.txt)")
        with ProcessPoolExecutor() as ex:
            futures = [ex.submit(check_copy, c, args.exe) for c in copies]
            for f in futures:
                name, row = f.result()
                rows[name] = row

    print(f"{'copy':<14} {'beats':>6} {'bit-id':>7} {'feat diff':>9} {'dec diff':>9} "
          f"{'lat s':>6}  result")  # fmt: skip
    for name, r in rows.items():
        print(f"{name:<14} {r['beats']:6d} {r.get('bit_identical', 0):7.4f} "
              f"{r.get('feature_max_diff', np.nan):9.2g} {r.get('decision_max_diff', np.nan):9.2g} "
              f"{r.get('latency_max_s', np.nan):6.2f}  {'; '.join(r['problems']) or 'OK'}")
    bad = [n for n, r in rows.items() if r["problems"]]
    total = sum(r["beats"] for r in rows.values())
    print(f"\n{len(rows)} copies, {total} beats: "
          + ("PASS" if not bad else f"FAIL ({len(bad)} copies: {', '.join(bad[:10])})"))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
