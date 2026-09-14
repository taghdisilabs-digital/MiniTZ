#!/usr/bin/env python3
"""Measure real mixer gain against independently recorded solo events."""
import hashlib
from pathlib import Path
import wave
import numpy as np
from scipy.signal import correlate, correlation_lags


def read_wave(path):
    with wave.open(str(path)) as w:
        assert w.getframerate() == 48000 and w.getnchannels() in (2, 6) and w.getsampwidth() == 2, 'Expected 48 kHz stereo or 5.1 PCM16 mixer recording'
        channels = w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').astype(float).reshape(-1, channels) / 32768
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data * data)))
    assert 0.001 < peak < 0.98 and rms > 0.0001, 'Silent or clipping runtime recording'
    return data, dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      frames=len(data), peak=peak, rms=rms, sample_rate=48000, channels=channels)


def aligned(source, target):
    # Full waveform correlation tolerates mixer buffer start offsets. Bound the
    # search to 100 ms; never stretch, resynthesize or normalize a capture.
    corr = correlate(target.sum(axis=1), source.sum(axis=1), mode='full', method='fft')
    lags = correlation_lags(len(target), len(source), mode='full')
    valid = np.abs(lags) <= 4800
    lag = int(lags[valid][np.argmax(corr[valid])])
    result = np.zeros_like(target)
    first, last = max(0, lag), min(len(target), len(source) + lag)
    result[first:last] = source[first-lag:last-lag]
    return result, lag


def measure(folder):
    arrays, records = {}, []
    for name in ('combat', 'critical', 'mixed'):
        arrays[name], record = read_wave(Path(folder) / (name + '.wav'))
        records.append(record)
    assert len({r['channels'] for r in records}) == 1, 'Solo/mixed channel layouts differ'
    combat, lag_c = aligned(arrays['combat'], arrays['mixed'])
    critical, lag_p = aligned(arrays['critical'], arrays['mixed'])
    design = np.column_stack((combat.ravel(), critical.ravel()))
    actual = arrays['mixed'].ravel()
    gains, _, rank, _ = np.linalg.lstsq(design, actual, rcond=None)
    residual = float(np.linalg.norm(actual - design @ gains) / np.linalg.norm(actual))
    assert rank == 2, 'Solo recordings cannot distinguish sources'
    return dict(recordings=records, combat_gain=float(gains[0]), critical_gain=float(gains[1]),
                relative_residual=residual, combat_lag_samples=lag_c, critical_lag_samples=lag_p,
                method='Least-squares gain fit against time-aligned native solo recordings; raw capture bytes unchanged')
