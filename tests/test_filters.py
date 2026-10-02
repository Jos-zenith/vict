import numpy as np
from scipy import signal

from vgate.dsp.filters import bandpass, design_bandpass

FS = 360


def test_design_is_float32_sos():
    sos = design_bandpass()
    assert sos.dtype == np.float32 and sos.shape[1] == 6


def test_passband_and_stopband():
    sos = design_bandpass().astype(np.float64)
    w, h = signal.sosfreqz(sos, worN=[0.05, 10.0, 100.0], fs=FS)
    g = np.abs(h)
    assert g[1] > 0.95          # 10 Hz passes
    assert g[0] < 0.2           # 0.05 Hz (baseline) suppressed
    assert g[2] < 0.2           # 100 Hz suppressed


def test_steady_state_init_has_no_startup_transient():
    y = bandpass(np.full(FS * 2, 1.5))
    assert np.max(np.abs(y)) < 1e-3
