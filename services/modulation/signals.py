"""Signal bus: stores live normalized signals (0.0 - 1.0) and action events."""
from dataclasses import dataclass, field
from typing import Optional
import math
import time


AUDIO_SIGNALS = [
    ('audio.amplitude', 'Overall Amplitude (RMS)'),
    ('audio.peak', 'Peak Amplitude'),
    ('audio.band_sub', 'Sub Bass (20-60 Hz)'),
    ('audio.band_bass', 'Bass (60-250 Hz)'),
    ('audio.band_low_mid', 'Low Mid (250-500 Hz)'),
    ('audio.band_mid', 'Mid (500-2k Hz)'),
    ('audio.band_high_mid', 'High Mid (2k-4k Hz)'),
    ('audio.band_presence', 'Presence (4k-6k Hz)'),
    ('audio.band_air', 'Air (6k-20k Hz)'),
    ('audio.custom_band', 'Custom Band'),
    ('audio.onset_flux', 'Onset / Beat Transient'),
]

TEMPO_SIGNALS = [
    ('tempo.beat_pulse', 'Beat Pulse (Attack/Decay)'),
    ('tempo.bar_phase', 'Bar Phase (0->1 Ramp)'),
    ('tempo.lfo_sine_1b', 'LFO Sine (1 Beat)'),
    ('tempo.lfo_sine_2b', 'LFO Sine (2 Beats)'),
    ('tempo.lfo_sine_4b', 'LFO Sine (1 Bar / 4 Beats)'),
    ('tempo.lfo_sine_8b', 'LFO Sine (2 Bars / 8 Beats)'),
    ('tempo.lfo_sine_16b', 'LFO Sine (4 Bars / 16 Beats)'),
    ('tempo.lfo_tri_4b', 'LFO Triangle (1 Bar)'),
    ('tempo.lfo_saw_4b', 'LFO Saw (1 Bar)'),
]


class SignalBus:
    """Central store for live modulation signals and event queues."""

    def __init__(self):
        self._signals: dict[str, float] = {}
        self._pending_actions: list[str] = []

    def set_signal(self, name: str, value: float):
        """Set a signal value, clamped to [0.0, 1.0]."""
        self._signals[name] = max(0.0, min(1.0, float(value)))

    def get_signal(self, name: str, default: float = 0.0) -> float:
        """Get current value of a signal."""
        return self._signals.get(name, default)

    def get_all_signals(self) -> dict[str, float]:
        return self._signals.copy()

    def queue_action(self, action_id: str):
        """Queue a one-shot action event (e.g. 'action.next_preset')."""
        self._pending_actions.append(action_id)

    def consume_actions(self) -> list[str]:
        """Return and clear all pending actions."""
        actions = self._pending_actions
        self._pending_actions = []
        return actions

    def update_tempo_lfos(self, beat_progress: float, phase: float, is_beat: bool = False):
        """Update LFO signals derived from tempo clock.
        
        Args:
            beat_progress: Continuous beat count (float)
            phase: Current beat phase within bar [0.0, 1.0]
            is_beat: True if this frame had a beat hit
        """
        # Bar phase: 0..1
        self.set_signal('tempo.bar_phase', phase)

        # Beat pulse with exponential decay
        prev_pulse = self.get_signal('tempo.beat_pulse', 0.0)
        decay = 0.82  # per-frame decay
        if is_beat:
            new_pulse = 1.0
        else:
            new_pulse = prev_pulse * decay
        self.set_signal('tempo.beat_pulse', new_pulse)

        # LFOs (sine mapped from [-1, 1] to [0, 1])
        # 1 beat cycle
        sine_1b = 0.5 + 0.5 * math.sin(2.0 * math.pi * beat_progress)
        self.set_signal('tempo.lfo_sine_1b', sine_1b)

        # 2 beats cycle
        sine_2b = 0.5 + 0.5 * math.sin(2.0 * math.pi * (beat_progress / 2.0))
        self.set_signal('tempo.lfo_sine_2b', sine_2b)

        # 4 beats cycle (1 bar)
        sine_4b = 0.5 + 0.5 * math.sin(2.0 * math.pi * (beat_progress / 4.0))
        self.set_signal('tempo.lfo_sine_4b', sine_4b)

        # 8 beats cycle (2 bars)
        sine_8b = 0.5 + 0.5 * math.sin(2.0 * math.pi * (beat_progress / 8.0))
        self.set_signal('tempo.lfo_sine_8b', sine_8b)

        # 16 beats cycle (4 bars)
        sine_16b = 0.5 + 0.5 * math.sin(2.0 * math.pi * (beat_progress / 16.0))
        self.set_signal('tempo.lfo_sine_16b', sine_16b)

        # Triangle 4 beats
        bar_frac = (beat_progress / 4.0) % 1.0
        tri_4b = 2.0 * bar_frac if bar_frac < 0.5 else 2.0 * (1.0 - bar_frac)
        self.set_signal('tempo.lfo_tri_4b', tri_4b)

        # Saw 4 beats
        self.set_signal('tempo.lfo_saw_4b', bar_frac)
