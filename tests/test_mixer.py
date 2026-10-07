import numpy as np
import pytest
import wfdb

from vgate import config
from vgate.data import mitdb, nstdb
from vgate.noise import mixer

FS = 360
needs_nstdb = pytest.mark.skipif(
    not (nstdb.NSTDB_DIR / "118e12.hea").exists() or not (mitdb.MITDB_DIR / "118.hea").exists(),
    reason="run scripts/download_data.py first",
)


def test_schedule_cycles_snr_and_blocks():
    s = mixer.build_schedule(650_000, FS, blocks=[1, 2, 3, 4], offset=1)
    assert [x["start"] for x in s[:2]] == [300 * FS, 540 * FS]
    assert all(x["stop"] - x["start"] == 120 * FS for x in s[:-1])
    assert s[-1]["stop"] == 650_000
    assert [x["snr_db"] for x in s[:4]] == [12, 6, 0, 18]
    assert [x["block"] for x in s[:4]] == [2, 3, 4, 1]


def test_mix_hits_target_snr_per_segment():
    rng = np.random.default_rng(1)
    x = np.zeros(1000 * FS)
    noise = np.cumsum(rng.normal(size=30 * 60 * FS)) * 0.01 + rng.normal(size=30 * 60 * FS)
    sched = mixer.build_schedule(len(x), FS, blocks=[1, 2, 3, 4], offset=0)
    s_power = 0.5
    y = mixer.mix(x, noise, sched, s_power, FS)
    for s in sched:
        added = y[s["start"] : s["stop"]] - x[s["start"] : s["stop"]]
        snr = 10 * np.log10(s_power / mixer.noise_power(added, FS))
        assert abs(snr - s["snr_db"]) < 0.5
    assert np.array_equal(y[: 300 * FS], x[: 300 * FS])


def _load_118e12():
    rec = mitdb.load_record(118)
    em = wfdb.rdrecord(str(nstdb.NSTDB_DIR / "em")).p_signal[:, 0]
    # nst removes the input's ADC zero but its header keeps baseline 1024, so read
    # digital values: they are already offset-free. nst does not write the last frame.
    r = wfdb.rdrecord(str(nstdb.NSTDB_DIR / "118e12"), physical=False)
    ref = r.d_signal[:-1, 0] / r.adc_gain[0]
    starts = list(range(300 * FS, len(ref), 120 * FS))
    return rec, em, ref, starts


def _nstdb_gain(x, em, ref, starts):
    """NSTDB's own gain: least squares of ref - x on em, one offset per noisy segment."""
    cols, ys = [], []
    noisy = starts[::2]
    for k, t in enumerate(noisy):
        s = slice(t, min(t + 120 * FS, len(ref)))
        off = np.zeros((s.stop - s.start, len(noisy)))
        off[:, k] = 1
        cols.append(np.column_stack([em[s], off]))
        ys.append(ref[s] - x[s])
    return np.linalg.lstsq(np.vstack(cols), np.concatenate(ys), rcond=None)[0][0]


@pytest.mark.data
@needs_nstdb
def test_reproduces_nstdb_118e12():
    """Mixing mechanics (alignment, continuity offsets) at NSTDB's own gain."""
    rec, em, ref, starts = _load_118e12()
    g = _nstdb_gain(rec.signal, em, ref, starts)
    changes = [(t, g if k % 2 == 0 else 0.0) for k, t in enumerate(starts)]
    y = mixer.mix_nst(rec.signal, em, changes)[: len(ref)]
    err = np.sqrt(np.mean((y - ref) ** 2))
    assert err < 0.01 * np.std(rec.signal)


@pytest.mark.data
@needs_nstdb
def test_gain_matches_nstdb_118e12():
    """Our S and N definitions give NSTDB's gain to within 0.5 % (MLII).

    The remaining 0.35 % is on the noise side (1990 sigamp vs today's); because em
    drifts slowly it alone gives ~3 % RMS error, hence the separate mechanics test.
    """
    rec, em, ref, starts = _load_118e12()
    s = mixer.signal_power(rec.signal, rec.ann_sample[rec.ann_aami == "N"], FS)
    n = mixer.noise_power(em[: 300 * FS], FS)  # sigamp reads the first 300 s
    g = mixer.noise_scale(s, n, 12.0)
    assert abs(g / _nstdb_gain(rec.signal, em, ref, starts) - 1) < 0.005


@pytest.mark.data
@needs_nstdb
def test_measured_snr_per_block_on_real_noise():
    rec = mitdb.load_record(118)
    s = mixer.signal_power(rec.signal, rec.ann_sample[rec.ann_aami == "N"], FS)
    blocks = config.splits()["noise"]["train_blocks"]
    for kind in config.splits()["noise"]["types"]:
        noise = nstdb.load_noise(kind)
        sched = mixer.build_schedule(len(rec.signal), FS, blocks, offset=0)
        y = mixer.mix(rec.signal, noise, sched, s, FS)
        for seg in sched:
            added = (y - rec.signal)[seg["start"] : seg["stop"]]
            snr = 10 * np.log10(s / mixer.noise_power(added, FS))
            assert abs(snr - seg["snr_db"]) < 0.5, (kind, seg)
