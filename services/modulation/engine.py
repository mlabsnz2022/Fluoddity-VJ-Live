"""Modulation Engine: applies audio, tempo, and MIDI modulation to targets."""
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
import copy
import json
from pathlib import Path
from utilities.paths import get_user_performance_dir
from .targets import TARGET_REGISTRY, get_target, ModTarget
from .signals import SignalBus


@dataclass
class AudioModMapping:
    """Mapping from an audio/tempo signal to a parameter target."""
    target_id: str                      # Target parameter identifier
    signal_name: str = "audio.amplitude"# Source signal name from SignalBus
    depth: float = 0.5                  # Modulation depth (-1.0 to 1.0)
    bipolar: bool = False               # False = additive offset, True = symmetric +/- around base
    threshold: float = 0.0              # Input noise gate / cutoff (0.0 to 1.0)
    attack: float = 0.0                 # Attack smoothing (0.0=instant, 0.99=slow)
    release: float = 0.15               # Release smoothing (0.0=instant, 0.99=slow)
    curve: str = "linear"               # 'linear', 'exp', 'log', 'smooth'
    invert: bool = False
    enabled: bool = True
    # Internal runtime state
    _current_filtered_val: float = field(default=0.0, repr=False)


class ModulationEngine:
    """Coordinates signal evaluation, parameter modulation, and action execution."""

    def __init__(self, signal_bus: SignalBus):
        self.bus = signal_bus
        self.audio_mappings: dict[str, AudioModMapping] = {}  # target_id -> mapping
        self._effective_values: dict[str, float] = {}         # target_id -> modulated value
        self.enabled: bool = True

    def get_effective_value(self, target_id: str, default: float = 0.0) -> float:
        """Get the current calculated effective value for a target."""
        return self._effective_values.get(target_id, default)

    def is_modulated(self, target_id: str) -> bool:
        """Check if target has an active modulation mapping."""
        m = self.audio_mappings.get(target_id)
        return m is not None and m.enabled and abs(m.depth) > 0.001

    def add_or_update_audio_mapping(self, mapping: AudioModMapping):
        """Register or update an audio modulation mapping."""
        self.audio_mappings[mapping.target_id] = mapping

    def remove_audio_mapping(self, target_id: str):
        """Remove a modulation mapping."""
        self.audio_mappings.pop(target_id, None)
        self._effective_values.pop(target_id, None)

    def clear_all_audio_mappings(self):
        self.audio_mappings.clear()
        self._effective_values.clear()

    def _shape_signal(self, raw: float, m: AudioModMapping) -> float:
        """Apply threshold, smoothing, invert, and curve shaping."""
        # 1. Gate / Threshold
        if raw < m.threshold:
            val = 0.0
        elif m.threshold < 1.0:
            val = (raw - m.threshold) / (1.0 - m.threshold)
        else:
            val = 0.0

        # 2. Invert if requested
        if m.invert:
            val = 1.0 - val

        # 3. Curve shaping
        if m.curve == "exp":
            val = val * val
        elif m.curve == "log":
            val = val ** 0.5
        elif m.curve == "smooth":
            val = val * val * (3.0 - 2.0 * val)

        # 4. Attack / Release smoothing
        prev = m._current_filtered_val
        if val > prev:
            coeff = max(0.0, min(0.99, m.attack))
        else:
            coeff = max(0.0, min(0.99, m.release))
        smoothed = coeff * prev + (1.0 - coeff) * val
        m._current_filtered_val = smoothed
        return smoothed

    def process_frame(self, ui_state: Any) -> Any:
        """Evaluate all modulation mappings and return an effective copy of SimState for sim.apply_state.
        
        The base ui_state.sim remains UNTOUCHED so user slider interactions and preset saves are clean.
        """
        self._effective_values.clear()

        if not self.enabled or not self.audio_mappings:
            return ui_state.sim

        # Make a shallow copy of sim state
        effective_sim = copy.copy(ui_state.sim)

        for target_id, m in self.audio_mappings.items():
            if not m.enabled or abs(m.depth) < 0.001:
                continue

            target = get_target(target_id)
            if target is None or target.is_action:
                continue

            # Read raw signal from bus
            raw_sig = self.bus.get_signal(m.signal_name, 0.0)
            shaped = self._shape_signal(raw_sig, m)

            # Determine parameter range and base value
            min_val, max_val = target.get_range(ui_state.sim)
            param_span = max_val - min_val
            base_val = target.get_base_value(ui_state.sim, ui_state.preferences, ui_state.camera, ui_state.multi_load)

            if m.bipolar:
                # Bipolar: shaped [0, 1] mapped to [-1, 1] offset
                offset = (shaped * 2.0 - 1.0) * m.depth * param_span * 0.5
            else:
                # Unipolar offset
                offset = shaped * m.depth * param_span

            effective_val = base_val + offset

            # Clamp to limits
            hard_min = target.hard_min if target.hard_min is not None else min_val
            hard_max = target.hard_max if target.hard_max is not None else max_val
            effective_val = max(hard_min, min(hard_max, effective_val))

            self._effective_values[target_id] = effective_val

            # Apply to effective_sim if it belongs to sim
            if target_id.startswith('sim.'):
                attr = target_id.split('.', 1)[1]
                if hasattr(effective_sim, attr):
                    setattr(effective_sim, attr, effective_val)

        return effective_sim

    # --- Persistence ---

    def save_mappings(self, filepath: Optional[Path | str] = None) -> bool:
        if filepath is None:
            filepath = get_user_performance_dir() / "audio_mappings.json"
        try:
            filepath = Path(filepath)
            data = {}
            for tid, m in self.audio_mappings.items():
                data[tid] = {
                    'target_id': m.target_id,
                    'signal_name': m.signal_name,
                    'depth': m.depth,
                    'bipolar': m.bipolar,
                    'threshold': m.threshold,
                    'attack': m.attack,
                    'release': m.release,
                    'curve': m.curve,
                    'invert': m.invert,
                    'enabled': m.enabled,
                }
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(json.dumps(data, indent=2))
            return True
        except Exception as e:
            print(f"Error saving audio mappings: {e}")
            return False

    def load_mappings(self, filepath: Optional[Path | str] = None) -> bool:
        if filepath is None:
            filepath = get_user_performance_dir() / "audio_mappings.json"
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                return False
            data = json.loads(filepath.read_text())
            self.audio_mappings.clear()
            for tid, item in data.items():
                self.audio_mappings[tid] = AudioModMapping(**item)
            return True
        except Exception as e:
            print(f"Error loading audio mappings: {e}")
            return False
