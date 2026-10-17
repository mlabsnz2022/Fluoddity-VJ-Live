"""MIDI mapping definitions and controller profiles."""
from dataclasses import dataclass, field
from typing import Optional, Any
import json
from pathlib import Path
from utilities.paths import get_user_performance_dir
from services.modulation.targets import get_target


@dataclass
class MidiBinding:
    """A mapping from a MIDI control (CC, Note, PitchBend) to a target parameter or action."""
    target_id: str                  # e.g. 'sim.SENSOR_GAIN' or 'action.next_preset'
    msg_type: str = "cc"            # 'cc', 'note', 'pitchbend', 'program_change'
    channel: int = -1               # -1 for all channels (Omni), or 0-15
    control: int = 1                # CC number or Note number
    min_out: float = 0.0            # Normalized output min (0.0 to 1.0)
    max_out: float = 1.0            # Normalized output max (0.0 to 1.0)
    invert: bool = False
    mode: str = "absolute"          # 'absolute', 'toggle', 'momentary', 'trigger'
    soft_takeover: bool = True      # Pickup mode: knob must cross current value before taking control
    
    # Runtime state (not saved)
    _pickup_engaged: bool = field(default=False, repr=False)
    _last_normalized_val: float = field(default=0.0, repr=False)

    @property
    def key(self) -> str:
        """Unique key for matching incoming MIDI messages."""
        ch_str = "*" if self.channel < 0 else str(self.channel)
        return f"{self.msg_type}:{ch_str}:{self.control}"


class MidiMappingManager:
    """Manages MIDI bindings and profiles."""

    def __init__(self):
        self.bindings: dict[str, MidiBinding] = {}  # key -> MidiBinding
        self.target_to_bindings: dict[str, list[MidiBinding]] = {}

    def _rebuild_indices(self):
        self.target_to_bindings.clear()
        for b in self.bindings.values():
            self.target_to_bindings.setdefault(b.target_id, []).append(b)

    def add_binding(self, binding: MidiBinding):
        self.bindings[binding.key] = binding
        self._rebuild_indices()

    def remove_binding(self, key: str):
        if key in self.bindings:
            del self.bindings[key]
            self._rebuild_indices()

    def remove_bindings_for_target(self, target_id: str):
        to_del = [k for k, b in self.bindings.items() if b.target_id == target_id]
        for k in to_del:
            del self.bindings[k]
        self._rebuild_indices()

    def clear(self):
        self.bindings.clear()
        self.target_to_bindings.clear()

    def find_binding(self, msg_type: str, channel: int, control: int) -> list[MidiBinding]:
        """Find any bindings matching this message (matching specific channel or omni)."""
        matches = []
        # Check specific channel
        key_specific = f"{msg_type}:{channel}:{control}"
        if key_specific in self.bindings:
            matches.append(self.bindings[key_specific])
        # Check omni channel
        key_omni = f"{msg_type}:*:{control}"
        if key_omni in self.bindings:
            matches.append(self.bindings[key_omni])
        return matches

    def save_to_file(self, filepath: Optional[Path | str] = None) -> bool:
        if filepath is None:
            filepath = get_user_performance_dir() / "midi_mappings.json"
        try:
            filepath = Path(filepath)
            data = []
            for b in self.bindings.values():
                data.append({
                    'target_id': b.target_id,
                    'msg_type': b.msg_type,
                    'channel': b.channel,
                    'control': b.control,
                    'min_out': b.min_out,
                    'max_out': b.max_out,
                    'invert': b.invert,
                    'mode': b.mode,
                    'soft_takeover': b.soft_takeover,
                })
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(json.dumps(data, indent=2))
            return True
        except Exception as e:
            print(f"Error saving MIDI mappings: {e}")
            return False

    def load_from_file(self, filepath: Optional[Path | str] = None) -> bool:
        if filepath is None:
            filepath = get_user_performance_dir() / "midi_mappings.json"
        try:
            filepath = Path(filepath)
            if not filepath.exists():
                return False
            data = json.loads(filepath.read_text())
            self.clear()
            for item in data:
                b = MidiBinding(**item)
                self.add_binding(b)
            return True
        except Exception as e:
            print(f"Error loading MIDI mappings: {e}")
            return False

    def load_profile(self, profile_name: str) -> bool:
        """Load a built-in controller profile (e.g. Novation Launch Control XL, Akai APC Key 25)."""
        from services.midi.profiles import load_profile_bindings
        bindings = load_profile_bindings(profile_name)
        if not bindings:
            return False
        self.clear()
        for b in bindings:
            self.add_binding(b)
        return True

