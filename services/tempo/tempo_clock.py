"""Tempo Clock: master timing source supporting Manual, Tap Tempo, Audio BPM, and Ableton Link."""
import time
import asyncio
from typing import Optional
from .bpm_detector import BPMDetector
from services.modulation.signals import SignalBus

# Ableton Link
try:
    import aalink
    HAS_LINK = True
except ImportError:
    aalink = None
    HAS_LINK = False


class TempoClock:
    """Master musical clock providing beat tracking, tempo sync, and phase signals."""

    def __init__(self, signal_bus: SignalBus):
        self.bus = signal_bus
        self.source: str = "Manual"  # 'Manual', 'Tap', 'Audio', 'Ableton Link'
        self.bpm: float = 120.0
        self.quantum: int = 4        # 4 beats per bar

        # Tap Tempo state
        self._tap_times: list[float] = []

        # Audio BPM Detector
        self.bpm_detector = BPMDetector()

        # Ableton Link state
        self._link_instance = None
        self._link_loop = None
        self.link_enabled: bool = False
        self.link_peers: int = 0

        # Runtime clock state
        self.beat_count: float = 0.0
        self.last_update_time: float = time.time()
        self.is_playing: bool = True
        self.just_crossed_beat: bool = False
        self.just_crossed_bar: bool = False

    def tap(self):
        """Register a tap tempo event."""
        now = time.time()
        # Reset if last tap was more than 2.5 seconds ago
        if self._tap_times and (now - self._tap_times[-1]) > 2.5:
            self._tap_times.clear()

        self._tap_times.append(now)
        if len(self._tap_times) > 8:
            self._tap_times.pop(0)

        if len(self._tap_times) >= 2:
            intervals = [self._tap_times[i] - self._tap_times[i-1] for i in range(1, len(self._tap_times))]
            avg_interval = sum(intervals) / len(intervals)
            if avg_interval > 0.05:
                calc_bpm = 60.0 / avg_interval
                self.set_bpm(calc_bpm)

    def set_bpm(self, new_bpm: float):
        """Set BPM within valid range [30, 300]."""
        self.bpm = max(30.0, min(300.0, float(new_bpm)))
        if self.link_enabled and self._link_instance:
            try:
                self._link_instance.tempo = self.bpm
            except Exception:
                pass

    def enable_link(self, enabled: bool = True):
        """Toggle Ableton Link network tempo sync."""
        if not HAS_LINK:
            self.link_enabled = False
            return

        if enabled and not self.link_enabled:
            try:
                if self._link_loop is None:
                    self._link_loop = asyncio.new_event_loop()
                self._link_instance = aalink.Link(self.bpm, self._link_loop)
                self._link_instance.enabled = True
                self.link_enabled = True
                self.source = "Ableton Link"
                print(f"[TempoClock] Ableton Link enabled at {self.bpm:.1f} BPM")
            except Exception as e:
                print(f"[TempoClock] Failed to enable Ableton Link: {e}")
                self.link_enabled = False
        elif not enabled and self.link_enabled:
            if self._link_instance:
                try:
                    self._link_instance.enabled = False
                except Exception:
                    pass
                self._link_instance = None
            self.link_enabled = False
            if self.source == "Ableton Link":
                self.source = "Manual"
            print("[TempoClock] Ableton Link disabled")

    def update(self, dt: float):
        """Advance the clock and update tempo LFOs in SignalBus."""
        now = time.time()
        prev_beat = self.beat_count

        # 1. Update tempo from active source
        if self.source == "Ableton Link" and self.link_enabled and self._link_instance:
            try:
                self.bpm = float(self._link_instance.tempo)
                self.link_peers = int(self._link_instance.num_peers)
                self.beat_count = float(self._link_instance.beat)
            except Exception:
                pass
        elif self.source == "Audio":
            # Read from BPM detector if confident
            if self.bpm_detector.confidence > 0.3:
                self.bpm = float(self.bpm_detector.estimated_bpm)
            if self.is_playing:
                self.beat_count += (self.bpm / 60.0) * dt
        else:  # Manual / Tap
            if self.is_playing:
                self.beat_count += (self.bpm / 60.0) * dt

        # 2. Detect integer beat and bar crossings
        curr_int_beat = int(self.beat_count)
        prev_int_beat = int(prev_beat)
        self.just_crossed_beat = (curr_int_beat > prev_int_beat)

        curr_bar = curr_int_beat // self.quantum
        prev_bar = prev_int_beat // self.quantum
        self.just_crossed_bar = (curr_bar > prev_bar)

        # 3. Bar phase [0.0, 1.0]
        bar_phase = (self.beat_count % float(self.quantum)) / float(self.quantum)

        # 4. Feed LFOs in SignalBus
        self.bus.update_tempo_lfos(
            beat_progress=self.beat_count,
            phase=bar_phase,
            is_beat=self.just_crossed_beat
        )
