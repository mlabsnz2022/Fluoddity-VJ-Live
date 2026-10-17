"""Audio capture service supporting sounddevice (mic/line-in) and PyAudioWPatch (WASAPI loopback)."""
import threading
import numpy as np
from typing import Optional, Callable
import sounddevice as sd

# Optional PyAudioWPatch for WASAPI Loopback
try:
    import pyaudiowpatch as pyaudio
    HAS_WASAPI_LOOPBACK = True
except ImportError:
    pyaudio = None
    HAS_WASAPI_LOOPBACK = False


class AudioInput:
    """Manages audio capture stream and maintains a thread-safe ring buffer of recent samples."""

    SAMPLE_RATE = 44100
    BUFFER_SIZE = 2048

    def __init__(self):
        self.device_name: str = "Default Input"
        self.is_loopback: bool = False
        self._running: bool = False

        # Ring buffer for latest samples
        self._buffer = np.zeros(self.BUFFER_SIZE, dtype=np.float32)
        self._lock = threading.Lock()

        # Stream handles
        self._sd_stream: Optional[sd.InputStream] = None
        self._pa_instance = None
        self._pa_stream = None
        self._pa_thread: Optional[threading.Thread] = None

    @classmethod
    def get_input_devices(cls) -> list[tuple[str, bool, int]]:
        """List available devices: (display_name, is_loopback, device_id)."""
        devices = []
        # Standard input devices from sounddevice
        try:
            sd_devs = sd.query_devices()
            for i, d in enumerate(sd_devs):
                if d.get('max_input_channels', 0) > 0:
                    api = sd.query_hostapis(d['hostapi'])['name']
                    devices.append((f"{d['name']} ({api})", False, i))
        except Exception as e:
            print(f"Error querying sounddevice devices: {e}")

        # WASAPI Loopback devices from PyAudioWPatch
        if HAS_WASAPI_LOOPBACK:
            try:
                p = pyaudio.PyAudio()
                try:
                    for d in p.get_loopback_device_info_generator():
                        devices.append((f"[Loopback] {d['name']}", True, d['index']))
                finally:
                    p.terminate()
            except Exception as e:
                print(f"Error querying WASAPI loopback devices: {e}")

        return devices

    def start(self, device_id: Optional[int] = None, is_loopback: bool = False):
        """Start capturing audio from the specified device."""
        self.stop()
        self.is_loopback = is_loopback

        if is_loopback and HAS_WASAPI_LOOPBACK:
            self._start_loopback(device_id)
        else:
            self._start_standard(device_id)

    def _start_standard(self, device_id: Optional[int]):
        try:
            def callback(indata, frames, time_info, status):
                if status:
                    pass
                # Convert stereo/multichannel to mono
                if indata.ndim > 1:
                    mono = np.mean(indata, axis=1)
                else:
                    mono = indata
                with self._lock:
                    n = len(mono)
                    if n >= self.BUFFER_SIZE:
                        self._buffer[:] = mono[-self.BUFFER_SIZE:]
                    else:
                        self._buffer[:-n] = self._buffer[n:]
                        self._buffer[-n:] = mono

            self._sd_stream = sd.InputStream(
                device=device_id,
                channels=1,
                samplerate=self.SAMPLE_RATE,
                blocksize=512,
                dtype=np.float32,
                callback=callback
            )
            self._sd_stream.start()
            self._running = True
        except Exception as e:
            print(f"[AudioInput] Failed to open sounddevice stream: {e}")

    def _start_loopback(self, device_index: Optional[int]):
        try:
            self._pa_instance = pyaudio.PyAudio()
            if device_index is None:
                dev = self._pa_instance.get_default_wasapi_loopback()
            else:
                dev = self._pa_instance.get_device_info_by_index(device_index)

            rate = int(dev.get('defaultSampleRate', self.SAMPLE_RATE))
            channels = int(dev.get('maxInputChannels', 2))

            def pa_callback(in_data, frame_count, time_info, status):
                samples = np.frombuffer(in_data, dtype=np.float32)
                if channels > 1:
                    samples = samples.reshape(-1, channels)
                    mono = np.mean(samples, axis=1)
                else:
                    mono = samples

                with self._lock:
                    n = len(mono)
                    if n >= self.BUFFER_SIZE:
                        self._buffer[:] = mono[-self.BUFFER_SIZE:]
                    else:
                        self._buffer[:-n] = self._buffer[n:]
                        self._buffer[-n:] = mono
                return (None, pyaudio.paContinue)

            self._pa_stream = self._pa_instance.open(
                format=pyaudio.paFloat32,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=dev['index'],
                frames_per_buffer=512,
                stream_callback=pa_callback
            )
            self._pa_stream.start_stream()
            self._running = True
        except Exception as e:
            print(f"[AudioInput] Failed to open WASAPI loopback stream: {e}")
            self.stop()

    def get_latest_samples(self) -> np.ndarray:
        """Return a snapshot copy of the latest BUFFER_SIZE samples."""
        with self._lock:
            return self._buffer.copy()

    def is_active(self) -> bool:
        return self._running

    def stop(self):
        self._running = False
        if self._sd_stream:
            try:
                self._sd_stream.stop()
                self._sd_stream.close()
            except Exception:
                pass
            self._sd_stream = None

        if self._pa_stream:
            try:
                self._pa_stream.stop_stream()
                self._pa_stream.close()
            except Exception:
                pass
            self._pa_stream = None

        if self._pa_instance:
            try:
                self._pa_instance.terminate()
            except Exception:
                pass
            self._pa_instance = None
