"""Real-time FFT audio analyzer for frequency bands, amplitude, onsets, and spectrum display."""
import numpy as np
from services.modulation.signals import SignalBus


FREQUENCY_BANDS = {
    'sub': (20.0, 60.0),
    'bass': (60.0, 250.0),
    'low_mid': (250.0, 500.0),
    'mid': (500.0, 2000.0),
    'high_mid': (2000.0, 4000.0),
    'presence': (4000.0, 6000.0),
    'air': (6000.0, 20000.0),
}


class AudioAnalyzer:
    """Analyzes raw audio buffers into normalized modulation signals and visual spectrum."""

    def __init__(self, sample_rate: int = 44100, buffer_size: int = 2048):
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.window = np.hanning(buffer_size)
        self.freqs = np.fft.rfftfreq(buffer_size, 1.0 / sample_rate)

        # Settings
        self.gain: float = 1.0
        self.agc_enabled: bool = True
        self.custom_band_range: tuple[float, float] = (100.0, 1000.0)

        # Running envelopes & AGC
        self._running_peak: float = 0.05
        self._running_band_peaks: dict[str, float] = {k: 0.05 for k in FREQUENCY_BANDS}
        self._running_band_peaks['custom'] = 0.05
        self._prev_magnitudes = np.zeros(len(self.freqs), dtype=np.float32)

        # UI Visual Spectrum (64 log-spaced bins)
        self.spectrum_display = np.zeros(64, dtype=np.float32)

        # Precompute band bin indices
        self._band_indices = {}
        for name, (low, high) in FREQUENCY_BANDS.items():
            idx = np.where((self.freqs >= low) & (self.freqs <= high))[0]
            self._band_indices[name] = idx if len(idx) > 0 else np.array([0])

    def update_custom_band(self, low_hz: float, high_hz: float):
        self.custom_band_range = (min(low_hz, high_hz), max(low_hz, high_hz))
        idx = np.where((self.freqs >= self.custom_band_range[0]) & (self.freqs <= self.custom_band_range[1]))[0]
        self._band_indices['custom'] = idx if len(idx) > 0 else np.array([0])

    def process(self, samples: np.ndarray, bus: SignalBus):
        """Analyze samples and update SignalBus with audio signals."""
        if len(samples) < self.buffer_size:
            return

        # 1. Overall Amplitude (RMS & Peak)
        rms = float(np.sqrt(np.mean(samples ** 2)))
        peak = float(np.max(np.abs(samples)))

        # AGC tracking for overall amplitude
        if self.agc_enabled:
            if rms > self._running_peak:
                self._running_peak = rms
            else:
                self._running_peak = max(0.01, self._running_peak * 0.995)
            norm_rms = min(1.0, (rms / self._running_peak) * self.gain)
            norm_peak = min(1.0, (peak / self._running_peak) * self.gain)
        else:
            norm_rms = min(1.0, rms * 5.0 * self.gain)
            norm_peak = min(1.0, peak * 2.5 * self.gain)

        bus.set_signal('audio.amplitude', norm_rms)
        bus.set_signal('audio.peak', norm_peak)

        # 2. FFT & Magnitudes
        windowed = samples * self.window
        fft_complex = np.fft.rfft(windowed)
        magnitudes = np.abs(fft_complex) / (self.buffer_size / 2.0)

        # 3. Spectral Flux (Onset / Transient detection)
        flux_diff = np.maximum(0.0, magnitudes - self._prev_magnitudes)
        # Weight lower/mid frequencies more heavily for punchy beats
        bass_mid_mask = (self.freqs >= 40.0) & (self.freqs <= 1500.0)
        flux_val = float(np.sum(flux_diff[bass_mid_mask]))
        self._prev_magnitudes[:] = magnitudes

        norm_flux = min(1.0, flux_val * 4.0 * self.gain)
        bus.set_signal('audio.onset_flux', norm_flux)

        # 4. Frequency Bands
        for name in list(FREQUENCY_BANDS.keys()) + ['custom']:
            if name == 'custom' and 'custom' not in self._band_indices:
                self.update_custom_band(*self.custom_band_range)

            idx = self._band_indices.get(name)
            if idx is not None and len(idx) > 0:
                band_energy = float(np.mean(magnitudes[idx]))
            else:
                band_energy = 0.0

            # Band AGC
            if self.agc_enabled:
                curr_peak = self._running_band_peaks.get(name, 0.05)
                if band_energy > curr_peak:
                    self._running_band_peaks[name] = band_energy
                else:
                    self._running_band_peaks[name] = max(0.005, curr_peak * 0.995)
                band_norm = min(1.0, (band_energy / self._running_band_peaks[name]) * self.gain)
            else:
                band_norm = min(1.0, band_energy * 20.0 * self.gain)

            bus.set_signal(f'audio.band_{name}' if name != 'custom' else 'audio.custom_band', band_norm)

        # 5. Visual Log-frequency Spectrum for ImGui (64 bars)
        # Sample between 30Hz and 18kHz logarithmically
        log_edges = np.geomspace(30.0, 18000.0, 65)
        for i in range(64):
            f_low, f_high = log_edges[i], log_edges[i+1]
            b_idx = np.where((self.freqs >= f_low) & (self.freqs <= f_high))[0]
            if len(b_idx) > 0:
                val = float(np.mean(magnitudes[b_idx]))
            else:
                val = 0.0
            # dB-like scaling for display
            disp_val = min(1.0, np.log10(1.0 + val * 100.0 * self.gain))
            # Smooth display
            self.spectrum_display[i] = 0.7 * self.spectrum_display[i] + 0.3 * disp_val
