"""Audio service: coordinates input stream and analyzer."""
from typing import Optional
from .audio_input import AudioInput
from .analyzer import AudioAnalyzer
from services.modulation.signals import SignalBus


class AudioService:
    """Facade for audio capture, FFT analysis, and signal bus updates."""

    def __init__(self, signal_bus: SignalBus):
        self.bus = signal_bus
        self.audio_input = AudioInput()
        self.analyzer = AudioAnalyzer()
        self.enabled: bool = True

        # Try to auto-start default audio input
        self.start_default()

    def start_default(self):
        try:
            self.audio_input.start()
        except Exception as e:
            print(f"[AudioService] Auto-start input failed: {e}")

    def update(self):
        """Call once per frame in orchestrate_frame to analyze audio and update signals."""
        if not self.enabled or not self.audio_input.is_active():
            return

        samples = self.audio_input.get_latest_samples()
        self.analyzer.process(samples, self.bus)

    def cleanup(self):
        self.audio_input.stop()
