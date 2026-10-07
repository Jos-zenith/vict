"""NSTDB-style noise mixer.

Acceptance (Objectives table): reproduce NSTDB 118e12 from 118 + em at 12 dB with
sample-wise RMS difference < 1 % of signal RMS, and every per-block mixture's
measured SNR within 0.5 dB of its target.

Power definitions follow WFDB ``sigamp`` as called by ``nst``:
  S = (5 %-trimmed mean of QRS peak-to-peak amplitude in +/-50 ms)^2 / 8
  N = (5 %-trimmed mean of the RMS of 1 s chunks, each with its own mean removed)^2
``nst`` measures N over the first 300 s of the noise record and uses one gain for the
whole record. Our ``mix`` instead sets each segment's gain from the power of the
noise block it uses, so every segment hits its target SNR.
"""

from __future__ import annotations

import numpy as np

from vgate import config


def _trimmed_mean(v: np.ndarray) -> float:
    """sigamp's trimmed mean: drop the lowest and highest n // 20 values."""
    v = np.sort(np.asarray(v, float))
    k = len(v) // 20
    return float(v[k : len(v) - k].mean())


def signal_power(x: np.ndarray, r_peaks: np.ndarray, fs: int = 360, n_qrs: int = 300) -> float:
    """nst definition: (trimmed mean p-p amplitude of the first n_qrs normal QRS)^2 / 8.

    ``r_peaks``: reference annotation samples of normal beats (AAMI N).
    """
    h = round(0.05 * fs)
    r = [int(q) for q in r_peaks if q - h >= 0 and q + h < len(x)][:n_qrs]
    if not r:
        raise ValueError("no normal beats to measure the signal amplitude")
    pp = [np.ptp(x[q - h : q + h + 1]) for q in r]
    return _trimmed_mean(pp) ** 2 / 8


def noise_power(noise: np.ndarray, fs: int = 360) -> float:
    """Power over 1 s chunks, each with its own mean removed (sigamp -r, squared).

    A trailing partial chunk is ignored; a segment shorter than 1 s is one chunk.
    """
    noise = np.asarray(noise, float)
    m = max(len(noise) // fs, 1)
    chunks = noise[: m * fs].reshape(m, -1) if len(noise) >= fs else noise[None, :]
    rms = np.sqrt(((chunks - chunks.mean(1, keepdims=True)) ** 2).mean(1))
    return _trimmed_mean(rms) ** 2


def noise_scale(s_power: float, n_power: float, snr_db: float) -> float:
    """Gain applied to the noise so that the mixture has the target SNR."""
    return float(np.sqrt(s_power / (n_power * 10 ** (snr_db / 10))))


def build_schedule(n_samples: int, fs: int, blocks: list[int], offset: int) -> list[dict]:
    """5 clean min, then alternating 2 min clean / noisy, cycling SNRs and blocks.

    Returns the noisy segments: {"start", "stop", "snr_db", "block"} (samples,
    stop exclusive). Noisy segment j uses SNR index (j + offset) % n_snr and block
    blocks[(j + offset) % len(blocks)]. The last segment may be cut short.
    """
    ns = config.pipeline()["noise_schedule"]
    snrs = ns["snr_db"]
    seg = ns["segment_min"] * 60 * fs
    out = []
    for j, start in enumerate(range(ns["clean_lead_min"] * 60 * fs, n_samples, 2 * seg)):
        out.append({
            "start": start,
            "stop": min(start + seg, n_samples),
            "snr_db": float(snrs[(j + offset) % len(snrs)]),
            "block": int(blocks[(j + offset) % len(blocks)]),
        })  # fmt: skip
    return out


def block_slice(block: int, length: int, fs: int = 360) -> slice:
    """Samples of noise block ``block`` (1-based, configs/splits.toml block_s)."""
    start = (block - 1) * config.splits()["noise"]["block_s"] * fs
    return slice(start, start + length)


def mix(
    x: np.ndarray, noise: np.ndarray, schedule: list[dict], s_power: float, fs: int = 360
) -> np.ndarray:
    """Apply a schedule at 360 Hz before any filtering, with 1 s ramps at segment edges.

    Each noisy segment adds its noise block (mean removed) scaled so that
    S / noise_power(added noise) equals the segment's SNR; ramps lie inside the segment.
    """
    y = np.asarray(x, float).copy()
    ramp = round(config.pipeline()["noise_schedule"]["ramp_s"] * fs)
    for s in schedule:
        n = s["stop"] - s["start"]
        blk = np.asarray(noise[block_slice(s["block"], n, fs)], float)
        if len(blk) < n:
            raise IndexError(f"noise block {s['block']} too short for a {n}-sample segment")
        blk = blk - blk.mean()
        env = np.ones(n)
        r = min(ramp, n // 2)
        if r:
            env[:r] = np.arange(r) / r
            env[n - r :] = env[:r][::-1]
        g = noise_scale(s_power, noise_power(blk, fs), s["snr_db"])
        y[s["start"] : s["stop"]] += g * env * blk
    return y


def mix_nst(
    x: np.ndarray, noise: np.ndarray, changes: list[tuple[int, float]], adc_gain: float = 200.0
) -> np.ndarray:
    """nst's mixing, for reproducing NSTDB records: out = x + g * noise[t] - z.

    ``changes``: (sample, gain) in time order. Noise is read at the same sample
    index. At each change z is reset so the output is continuous, which leaves a DC
    offset in the following clean segment. Like nst, works in integer ADC units
    (``adc_gain`` per mV) with C truncation of z and of every output sample.
    """
    xi = np.round(np.asarray(x, float) * adc_gain)
    ni = np.round(np.asarray(noise, float) * adc_gain)
    y = xi.copy()
    bounds = [*changes, (len(x), 0.0)]
    for (t, g), (t_next, _) in zip(bounds[:-1], bounds[1:], strict=True):
        z = np.trunc(xi[t - 1] + g * ni[t - 1] - y[t - 1]) if t > 0 else 0.0
        y[t:t_next] = np.trunc(xi[t:t_next] + g * ni[t:t_next] - z)
    return y / adc_gain
