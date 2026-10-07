import numpy as np
import pytest

from vgate import sqi
from vgate.data import mitdb
from vgate.detectors import mexican_hat, pan_tompkins
from vgate.evaluation.matching import match
from vgate.features import FEATURE_NAMES, beat_features

FS = 360


def synthetic_ecg(seconds: float = 30, hr: float = 72, seed: int = 0):
    """Gaussian QRS spikes plus a slow baseline; returns signal and R positions."""
    rng = np.random.default_rng(seed)
    n = int(seconds * FS)
    r = np.arange(int(0.5 * FS), n - FS // 2, int(60 / hr * FS))
    t = np.arange(n)
    x = 0.3 * np.sin(2 * np.pi * 0.2 * t / FS) + 0.01 * rng.normal(size=n)
    for p in r:
        x += 1.2 * np.exp(-0.5 * ((t - p) / 4.0) ** 2)
        x += 0.25 * np.exp(-0.5 * ((t - p - 90) / 18.0) ** 2)  # T wave
    return x, r


def run_streaming(x, chunk):
    d = pan_tompkins.PanTompkins(FS)
    out = []
    for k in range(0, len(x), chunk):
        out += d.push(x[k : k + chunk])
    return np.unique(out)


@pytest.mark.parametrize("chunk", [1, 97, 3600])
def test_pan_tompkins_finds_synthetic_beats_in_any_chunking(chunk):
    x, r = synthetic_ecg()
    det = run_streaming(x, chunk)
    d2r, r2d = match(det, r, tol=54)
    assert (r2d >= 0).mean() > 0.97 and len(det) <= len(r) + 1
    assert np.abs(det[d2r >= 0] - r[d2r[d2r >= 0]]).max() <= 10


def test_mexican_hat_and_qsqi_on_synthetic():
    x, r = synthetic_ecg()
    mh = mexican_hat.detect(x)
    _, r2d = match(mh, r, tol=54)
    assert (r2d >= 0).mean() > 0.95
    assert sqi.qsqi(r, mh) > 0.9
    assert sqi.qsqi(np.array([]), np.array([])) == 0.0


def test_sqis_rank_clean_above_noise():
    x, r = synthetic_ecg(10)
    noise = np.random.default_rng(3).normal(size=len(x))
    clean = sqi.window_sqis(x, r, r)
    noisy = sqi.window_sqis(noise, r, np.array([], int))
    assert clean[0] > noisy[0] and clean[2] > noisy[2]  # qSQI, kSQI


def test_features_shape_and_rr():
    x, r = synthetic_ecg()
    f = beat_features(x, r, FS)
    assert f.shape == (len(r), len(FEATURE_NAMES)) and np.isfinite(f).all()
    rr = 60 / 72
    assert np.allclose(f[1:-1, 0], rr, atol=0.01) and np.allclose(f[1:-1, 3], 1, atol=0.02)
    assert f[-1, 1] == 2.0  # censored RR after the last beat


@pytest.mark.data
@pytest.mark.skipif(not (mitdb.MITDB_DIR / "100.hea").exists(), reason="no data")
def test_pan_tompkins_on_record_119():
    rec = mitdb.load_record(119)
    det = pan_tompkins.detect(rec.signal)
    _, r2d = match(det, rec.ann_sample, tol=54)
    tp = (r2d >= 0).sum()
    assert tp / len(rec.ann_sample) > 0.99 and tp / len(det) > 0.99
