"""Model-independent processing of one record copy, cached under results/cache.

A copy is a record either clean or mixed with one NSTDB noise type at one schedule
cycle offset. Processing runs everything before the classifier: mixing at 360 Hz,
Pan-Tompkins on the raw mixture, Mexican-hat, the classifier filter, beat features,
reference labels for each detection, and per-window SNR and log SQIs. The
classifier's decision values are then turned into window rows by
windows.from_record (see ``to_windows``).

Windows overlapping a ventricular flutter/fibrillation episode are left out, as in
EC57. Noise blocks follow configs/splits.toml: DS1-train copies use train_blocks, DS1-cal
copies cal_blocks, all from the development half of each noise record.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vgate import config, windows
from vgate.data import mitdb, nstdb
from vgate.detectors import mexican_hat, pan_tompkins
from vgate.dsp.filters import bandpass
from vgate.evaluation.matching import match
from vgate.features import beat_features
from vgate.noise import mixer
from vgate.sqi import window_sqis

CACHE_DIR = config.RESULTS_DIR / "cache"
CACHE_VERSION = 2  # bump when processing changes


@dataclass(frozen=True)
class Copy:
    record: int
    split: str  # train | cal | test
    noise_type: str  # none | em | ma | bw
    offset: int = -1  # schedule cycle offset; -1 for the clean copy

    @property
    def copy(self) -> str:
        return "clean" if self.noise_type == "none" else "noisy"

    @property
    def name(self) -> str:
        return f"{self.record}_{self.noise_type}_{self.offset}"


def ds1_copies() -> list[Copy]:
    """Every DS1 record clean, plus one copy per noise type and cycle offset."""
    types = config.splits()["noise"]["types"]
    offsets = config.pipeline()["noise_schedule"]["cycle_offsets"]
    out = []
    for split, recs in (("train", mitdb.ds1_train()), ("cal", mitdb.ds1_cal())):
        for r in recs:
            out.append(Copy(r, split, "none"))
            out += [Copy(r, split, t, o) for t in types for o in offsets]
    return out


def ds2_copies(include_202: bool = False) -> list[Copy]:
    """DS2 records clean plus one copy per noise type and cycle offset (test blocks)."""
    types = config.splits()["noise"]["types"]
    offsets = config.pipeline()["noise_schedule"]["cycle_offsets"]
    out = []
    for r in mitdb.ds2(include_202):
        out.append(Copy(r, "test", "none"))
        out += [Copy(r, "test", t, o) for t in types for o in offsets]
    return out


def _noisy_signal(c: Copy, rec: mitdb.Record) -> tuple[np.ndarray, list[dict]]:
    if c.noise_type == "none":
        return rec.signal, []
    blocks = config.splits()["noise"][f"{c.split}_blocks"]
    sched = mixer.build_schedule(len(rec.signal), rec.fs, blocks, c.offset)
    s_power = mixer.signal_power(
        rec.signal,
        rec.ann_sample[rec.ann_aami == "N"],
        rec.fs,
        config.pipeline()["noise_schedule"]["signal_power_qrs"],
    )
    return mixer.mix(rec.signal, nstdb.load_noise(c.noise_type), sched, s_power, rec.fs), sched


def process(c: Copy, cache: bool = True, allow_test: bool = False) -> dict[str, np.ndarray]:
    """allow_test: passed to the DS2 guard; only the frozen DS2 run sets it."""
    if c.split == "test" and not allow_test:  # also guards the cache
        raise mitdb.TestSetAccessError(f"{c.name} is a DS2 copy; only the frozen run may load it")
    sub = "ds2" if c.split == "test" else ""
    path = CACHE_DIR / f"v{CACHE_VERSION}" / sub / f"{c.name}.npz"
    if cache and path.exists():
        with np.load(path, allow_pickle=False) as z:
            return dict(z)

    rec = mitdb.load_record(c.record, allow_test=allow_test)
    fs = rec.fs
    raw, sched = _noisy_signal(c, rec)
    det, widths = pan_tompkins.detect_with_widths(raw, fs)
    x = bandpass(raw).astype(float)
    feats = beat_features(x, det, fs, widths)

    tol = round(config.pipeline()["scoring"]["match_tolerance_ms"] * fs / 1000)
    d2r, _ = match(det, rec.ann_sample, tol)
    label = np.full(len(det), "-", dtype="U1")  # "-" = no reference beat
    label[d2r >= 0] = rec.ann_aami[d2r[d2r >= 0]]

    win = config.pipeline()["window_s"] * fs
    starts = windows.window_starts(len(raw), fs)
    for a, b in rec.vf_episodes:  # no beats to score inside VF/VFL episodes
        starts = starts[(starts + win <= a) | (starts >= b)]
    mh = mexican_hat.detect(raw, fs)
    sqis = np.zeros((len(starts), 4))
    snr = np.full(len(starts), np.nan)
    for i, s in enumerate(starts):
        in_pt = det[(det >= s) & (det < s + win)] - s
        in_mh = mh[(mh >= s) & (mh < s + win)] - s
        sqis[i] = window_sqis(raw[s : s + win], in_pt, in_mh, fs)
        for seg in sched:
            if seg["start"] < s + win and s < seg["stop"]:
                snr[i] = seg["snr_db"]

    out = {
        "det": det,
        "features": feats,
        "label": label,
        "starts": starts,
        "sqis": sqis,
        "snr_db": snr,
        "ref_sample": rec.ann_sample,
        "ref_aami": rec.ann_aami.astype("U1"),
    }
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **out)
    return out


def training_data(data: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    """Features and V labels of one copy's detections; detections on Q beats dropped.

    Unmatched detections are labelled non-V: calling them V is a false V call.
    """
    keep = data["label"] != "Q"
    return data["features"][keep], (data["label"][keep] == "V").astype(int)


def to_windows(
    c: Copy,
    data: dict[str, np.ndarray],
    decision: np.ndarray,
    clean: windows.WindowTable | None = None,
) -> windows.WindowTable:
    """Window rows for one copy; ``clean``: the record's clean-copy rows (same model)."""
    return windows.from_record(
        record=c.record,
        split=c.split,
        copy=c.copy,
        noise_type=c.noise_type,
        offset=c.offset,
        starts=data["starts"],
        snr_db=data["snr_db"],
        sqis=data["sqis"],
        det=data["det"],
        decision=decision,
        ref_sample=data["ref_sample"],
        ref_aami=data["ref_aami"],
        clean=clean,
    )
