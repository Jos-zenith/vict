import numpy as np

from vgate.noise import mixer
from vgate.noise.strap import heartbeat_check, to_pipeline_rate

FS = 360


def test_resample_to_360_hz_keeps_duration_and_removes_mean():
    x = np.sin(2 * np.pi * 5 * np.arange(5000) / 500) + 3.0
    y = to_pipeline_rate(x, 500)
    assert len(y) == 3600 and abs(y.mean()) < 0.01


def test_heartbeat_check_flags_ecg_and_passes_noise():
    rng = np.random.default_rng(0)
    n = 180 * FS
    noise = np.cumsum(rng.normal(size=n)) * 0.002 + 0.05 * rng.normal(size=n)
    t = np.arange(n)
    beats = sum(np.exp(-0.5 * ((t - p) / 4.0) ** 2) for p in range(200, n, int(0.8 * FS)))
    assert heartbeat_check(noise)["contaminated_fraction"] == 0.0
    assert heartbeat_check(noise + beats)["contaminated_fraction"] == 1.0


def test_strap_noise_works_with_the_mixer():
    noise = to_pipeline_rate(np.random.default_rng(1).normal(size=16 * 60 * 500), 500)
    sched = mixer.build_schedule(650_000, FS, blocks=[1, 2, 3], offset=0)
    y = mixer.mix(np.zeros(650_000), noise, sched, 0.5, FS)
    seg = sched[0]
    added = y[seg["start"] : seg["stop"]]
    assert abs(10 * np.log10(0.5 / mixer.noise_power(added, FS)) - seg["snr_db"]) < 0.5
