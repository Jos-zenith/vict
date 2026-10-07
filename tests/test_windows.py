import numpy as np
import pytest

from vgate import config, windows
from vgate.windows import WindowTable

# Two 100-sample windows, tol 5. Window 1: an N-matched call, an unmatched call
# (false) and a Q-matched call (not false); the V at 160 has no detection.
REF = np.array([10, 40, 70, 130, 160, 188])
REF_AAMI = np.array(["N", "V", "V", "N", "V", "Q"])
DET = np.array([12, 41, 72, 135, 150, 190])
DEC = np.array([-1.0, 2.0, 0.5, 1.0, 3.0, 3.0])


def test_v_counts_hand_example():
    n_true, n_pred, false, lost = windows.v_counts(
        DET, DEC, REF, REF_AAMI, np.array([0, 100]), 100, np.array([0.0, 1.0]), tol=5
    )
    assert n_true.tolist() == [2, 1]
    assert n_pred.tolist() == [[2, 1], [3, 2]]
    assert false.tolist() == [[0, 0], [2, 1]]
    assert lost.tolist() == [[0, 1], [1, 1]]


def test_threshold_sweep_contains_default():
    thr = windows.thresholds()
    assert np.all(np.diff(thr) > 0)
    assert thr[windows.default_index(thr)] == config.pipeline()["thresholds"]["default"]


def _table(copy="noisy", noise_type="em", offset=0) -> WindowTable:
    fs = 360
    starts = windows.window_starts(5 * 3600, fs)
    rng = np.random.default_rng(0)
    det = np.sort(rng.choice(np.arange(starts[0], 5 * 3600), 12, replace=False))
    snr = np.full(len(starts), np.nan) if copy == "clean" else np.array([np.nan, 6.0, 6.0, 0.0])
    return windows.from_record(
        record=119, split="train", copy=copy, noise_type=noise_type, offset=offset,
        starts=starts, snr_db=snr,
        sqis=rng.normal(size=(len(starts), 4)),
        det=det, decision=rng.normal(size=len(det)),
        ref_sample=det[::2] + 3, ref_aami=np.array(["V", "N", "V", "N", "V", "Q"]),
    )  # fmt: skip


def test_round_trip(tmp_path):
    t = WindowTable.concat([_table(), _table("clean", "none", -1)])
    assert len(t) == 8 and t.gate_features(sqi=True).shape == (8, 8)
    t.save(tmp_path / "w.npz")
    u = WindowTable.load(tmp_path / "w.npz")
    assert np.array_equal(u.false_v, t.false_v) and u.split.tolist() == t.split.tolist()


def test_validate_rejects_broken_rows():
    t = _table()
    t.false_v[0, :] = t.n_pred_v[0, :] + 1
    with pytest.raises(ValueError, match="false_v"):
        t.validate()
    with pytest.raises(ValueError, match="duplicate"):
        WindowTable.concat([_table(), _table()]).validate()
