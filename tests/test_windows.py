import numpy as np
import pytest

from vgate import config, windows
from vgate.windows import WindowTable

FS = 360

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


def _table(copy="noisy", noise_type="em", offset=0, clean=None) -> WindowTable:
    """Clean copy: one beat per second, every 5th V, all called correctly. The noisy
    copy adds a spurious detection called V in its second window."""
    starts = windows.window_starts(5 * 3600, FS)
    ref = np.arange(starts[0] + 100, 5 * 3600 - 100, FS)
    aami = np.where(np.arange(len(ref)) % 5 == 0, "V", "N")
    det, dec = ref.copy(), np.where(aami == "V", 1.0, -1.0)
    if copy == "noisy":
        det, dec = np.append(det, starts[1] + 200), np.append(dec, 2.0)
        det, dec = det[np.argsort(det)], dec[np.argsort(det)]
    snr = np.full(len(starts), np.nan) if copy == "clean" else np.array([np.nan, 6.0, 6.0, 0.0])
    return windows.from_record(
        record=119, split="train", copy=copy, noise_type=noise_type, offset=offset,
        starts=starts, snr_db=snr, sqis=np.zeros((len(starts), 4)),
        det=det, decision=dec, ref_sample=ref, ref_aami=aami, clean=clean,
    )  # fmt: skip


def _pair() -> tuple[WindowTable, WindowTable]:
    clean = _table("clean", "none", -1)
    return clean, _table(clean=clean)


def test_risky_is_relative_to_the_clean_pair():
    clean, noisy = _pair()
    assert not clean.risky.any() and clean.false_v.sum() == 0
    assert noisy.risky.tolist() == [False, True, False, False]
    with pytest.raises(ValueError, match="clean copy"):
        _table()


def test_round_trip(tmp_path):
    clean, noisy = _pair()
    t = WindowTable.concat([clean, noisy])
    assert len(t) == 8 and t.gate_features(sqi=True).shape == (8, 8)
    t.save(tmp_path / "w.npz")
    u = WindowTable.load(tmp_path / "w.npz")
    assert np.array_equal(u.false_v, t.false_v) and u.split.tolist() == t.split.tolist()


def test_validate_rejects_broken_rows():
    t = _pair()[1]
    t.false_v[0, :] = t.n_pred_v[0, :] + 1
    with pytest.raises(ValueError, match="false_v"):
        t.validate()
    with pytest.raises(ValueError, match="duplicate"):
        WindowTable.concat(list(_pair()) * 2).validate()
    clean, noisy = _pair()
    noisy.risky[:] = ~noisy.risky
    with pytest.raises(ValueError, match="clean pair"):
        WindowTable.concat([clean, noisy]).validate()
