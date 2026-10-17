"""Real-time tempo (BPM) detection from audio onset flux using autocorrelation."""
import time
import numpy as np


class BPMDetector:
    """Estimates BPM from audio onset flux envelope via autocorrelation."""

    def __init__(self, sample_rate_flux: float = 60.0, history_seconds: float = 6.0):
        self.sample_rate = sample_rate_flux
        self.history_len = int(sample_rate_flux * history_seconds)
        self.flux_history = np.zeros(self.history_len, dtype=np.float32)
        self.ptr = 0

        self.min_bpm = 70.0
        self.max_bpm = 180.0
        self.estimated_bpm: float = 120.0
        self.confidence: float = 0.0
        self.is_locked: bool = False
        self._last_calc_time = 0.0

    def feed_onset(self, flux_value: float):
        """Feed a single onset flux measurement (called ~60Hz from orchestrate_frame)."""
        self.flux_history[self.ptr] = flux_value
        self.ptr = (self.ptr + 1) % self.history_len

        now = time.time()
        # Re-estimate tempo every 0.35 seconds
        if not self.is_locked and (now - self._last_calc_time) > 0.35:
            self._last_calc_time = now
            self._estimate_tempo()

    def _estimate_tempo(self):
        # Unwrap circular buffer
        buf = np.roll(self.flux_history, -self.ptr)
        # Detrend / center
        buf = buf - np.mean(buf)
        if np.max(np.abs(buf)) < 0.01:
            self.confidence = 0.0
            return

        # Autocorrelation
        n = len(buf)
        corr = np.correlate(buf, buf, mode='full')
        corr = corr[n - 1:]  # Keep non-negative lags

        # Lag range corresponding to [min_bpm, max_bpm]
        # lag = (60.0 / bpm) * sample_rate
        min_lag = int((60.0 / self.max_bpm) * self.sample_rate)
        max_lag = int((60.0 / self.min_bpm) * self.sample_rate)

        if min_lag >= len(corr) or max_lag >= len(corr):
            return

        search_slice = corr[min_lag:max_lag + 1]
        if len(search_slice) == 0:
            return

        peak_idx = int(np.argmax(search_slice))
        peak_val = search_slice[peak_idx]
        mean_val = np.mean(search_slice)
        best_lag = min_lag + peak_idx

        # Calculate BPM
        raw_bpm = (60.0 * self.sample_rate) / float(best_lag)

        # Confidence metric based on peak prominence
        prominence = (peak_val - mean_val) / max(0.001, peak_val)
        self.confidence = max(0.0, min(1.0, float(prominence * 1.5)))

        if self.confidence > 0.25:
            # Smoothly track
            self.estimated_bpm = 0.8 * self.estimated_bpm + 0.2 * raw_bpm
