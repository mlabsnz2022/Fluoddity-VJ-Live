"""MIDI service: input port management, background listener, MIDI learn, and parameter updates."""
import threading
import queue
import time
from typing import Optional, Any
import mido
from .midi_mapping import MidiMappingManager, MidiBinding
from services.modulation.targets import get_target
from services.modulation.signals import SignalBus


class MidiService:
    """Manages MIDI inputs, learn mode, and dispatching incoming messages."""

    def __init__(self, mapping_manager: MidiMappingManager, signal_bus: SignalBus):
        self.mapping_manager = mapping_manager
        self.bus = signal_bus

        self._active_ports: dict[str, mido.ports.BaseInput] = {}
        self._selected_port_name: str = "All Available"
        self._msg_queue: queue.Queue = queue.Queue()
        self._running: bool = False
        self._thread: Optional[threading.Thread] = None

        # Learn state
        self.learn_target_id: Optional[str] = None
        self.last_learned_binding: Optional[MidiBinding] = None

        # Activity indicators for UI
        self.last_message_str: str = "None"
        self.last_message_time: float = 0.0

        # Auto-start with all available ports
        self.start()

    def get_available_ports(self) -> list[str]:
        """Query available MIDI input devices."""
        try:
            return mido.get_input_names()
        except Exception as e:
            print(f"Error querying MIDI ports: {e}")
            return []

    def set_port(self, port_name: str):
        """Set desired port ('All Available' or specific port name)."""
        if self._selected_port_name != port_name:
            self._selected_port_name = port_name
            self.restart()

    @property
    def selected_port_name(self) -> str:
        return self._selected_port_name

    def is_connected(self) -> bool:
        return len(self._active_ports) > 0

    def start(self):
        """Open selected or all ports and start listener thread."""
        if self._running:
            return

        self._running = True
        self._open_ports()

        self._thread = threading.Thread(target=self._read_loop, name="Fluoddity-MIDI", daemon=True)
        self._thread.start()

    def stop(self):
        """Stop listener thread and close ports."""
        self._running = False
        self._close_ports()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)
        self._thread = None

    def restart(self):
        self.stop()
        self.start()

    def _open_ports(self):
        self._close_ports()
        avail = self.get_available_ports()
        if not avail:
            return

        if self._selected_port_name == "All Available":
            for name in avail:
                try:
                    p = mido.open_input(name)
                    self._active_ports[name] = p
                except Exception as e:
                    print(f"Failed to open MIDI port {name}: {e}")
        else:
            if self._selected_port_name in avail:
                try:
                    p = mido.open_input(self._selected_port_name)
                    self._active_ports[self._selected_port_name] = p
                except Exception as e:
                    print(f"Failed to open MIDI port {self._selected_port_name}: {e}")

    def _close_ports(self):
        for name, port in list(self._active_ports.items()):
            try:
                port.close()
            except Exception:
                pass
        self._active_ports.clear()

    def _read_loop(self):
        """Poll open ports for messages and push to thread-safe queue."""
        while self._running:
            got_msg = False
            for port in list(self._active_ports.values()):
                try:
                    for msg in port.iter_pending():
                        got_msg = True
                        self._msg_queue.put(msg)
                except Exception:
                    pass
            if not got_msg:
                time.sleep(0.002)  # Low-latency polling sleep

    def start_learn(self, target_id: str):
        """Enter MIDI Learn mode for the given target."""
        self.learn_target_id = target_id
        self.last_learned_binding = None

    def cancel_learn(self):
        """Cancel MIDI Learn mode."""
        self.learn_target_id = None

    def process_messages(self, ui_state: Any):
        """Drain incoming MIDI messages, handle Learn, and update targets."""
        while not self._msg_queue.empty():
            try:
                msg = self._msg_queue.get_nowait()
            except queue.Empty:
                break

            self._handle_single_message(msg, ui_state)

    def _handle_single_message(self, msg: mido.Message, ui_state: Any):
        now = time.time()
        self.last_message_time = now

        msg_type = msg.type
        channel = getattr(msg, 'channel', 0)

        # Normalize message details
        if msg_type == 'control_change':
            control = msg.control
            val_norm = msg.value / 127.0
            self.last_message_str = f"Ch {channel+1} CC {control} = {msg.value}"
            # Register in signal bus for monitoring
            self.bus.set_signal(f"midi.cc_{channel+1}_{control}", val_norm)
        elif msg_type == 'note_on':
            control = msg.note
            val_norm = msg.velocity / 127.0
            self.last_message_str = f"Ch {channel+1} Note {control} Vel {msg.velocity}"
        elif msg_type == 'note_off':
            control = msg.note
            val_norm = 0.0
            self.last_message_str = f"Ch {channel+1} Note Off {control}"
        elif msg_type == 'pitchwheel':
            control = 0
            val_norm = (msg.pitch + 8192) / 16383.0
            self.last_message_str = f"Ch {channel+1} PitchBend {msg.pitch}"
        elif msg_type == 'program_change':
            control = msg.program
            val_norm = 1.0
            self.last_message_str = f"Ch {channel+1} ProgChange {control}"
        else:
            return  # Ignore other messages (clock, active sensing, etc.)

        # 1. MIDI Learn intercept
        if self.learn_target_id is not None:
            target = get_target(self.learn_target_id)
            if target:
                # Decide mode and soft takeover based on message and target type
                if target.is_action:
                    mode = "trigger"
                    soft = False
                elif target.target_type == "bool":
                    mode = "toggle"
                    soft = False
                elif target.target_type == "enum":
                    if msg_type in ('note_on', 'note_off'):
                        mode = "cycle"
                    else:
                        mode = "cycle" if val_norm in (0.0, 1.0) else "proportional"
                    soft = False
                else:
                    mode = "absolute"
                    soft = True

                binding = MidiBinding(
                    target_id=self.learn_target_id,
                    msg_type=msg_type,
                    channel=channel,
                    control=control,
                    min_out=0.0,
                    max_out=1.0,
                    mode=mode,
                    soft_takeover=soft
                )
                self.mapping_manager.add_binding(binding)
                self.last_learned_binding = binding
                print(f"[MIDI] Learned: {binding.key} -> {self.learn_target_id} (mode={mode})")
            self.learn_target_id = None
            return

        # 2. Match bindings and apply
        bindings = self.mapping_manager.find_binding(msg_type, channel, control)
        for b in bindings:
            self._apply_binding(b, val_norm, ui_state)

    def _apply_binding(self, b: MidiBinding, val_norm: float, ui_state: Any):
        target = get_target(b.target_id)
        if target is None:
            return

        # 1. Handle Action Triggers
        if target.is_action or b.mode == "trigger":
            if b.msg_type == 'note_on' and val_norm > 0.0:
                self.bus.queue_action(b.target_id)
            elif b.msg_type == 'control_change' and val_norm > 0.5 and b._last_normalized_val <= 0.5:
                self.bus.queue_action(b.target_id)
            b._last_normalized_val = val_norm
            return

        # 2. Handle Boolean Checkbox Toggles
        if target.target_type == "bool":
            if b.msg_type == 'note_on':
                if val_norm > 0.0:
                    target.toggle(ui_state)
            elif b.msg_type == 'control_change':
                if b.mode == "toggle":
                    if val_norm > 0.5 and b._last_normalized_val <= 0.5:
                        target.toggle(ui_state)
                elif b.mode == "momentary":
                    target.set_bool(ui_state, val_norm > 0.5)
                else:
                    target.set_bool(ui_state, val_norm >= 0.5)
            b._last_normalized_val = val_norm
            return

        # 3. Handle Enum Dropdown Selectors
        if target.target_type == "enum":
            if b.mode == "cycle":
                if b.msg_type == 'note_on':
                    if val_norm > 0.0:
                        target.cycle_next(ui_state)
                elif b.msg_type == 'control_change':
                    if val_norm > 0.5 and b._last_normalized_val <= 0.5:
                        target.cycle_next(ui_state)
            else:  # Proportional / Absolute (knob / fader)
                if b.invert:
                    val_norm = 1.0 - val_norm
                mapped_norm = b.min_out + val_norm * (b.max_out - b.min_out)
                num_opts = len(target.options)
                if num_opts > 0:
                    idx = min(num_opts - 1, max(0, int(mapped_norm * num_opts)))
                    target.set_enum_by_index(ui_state, idx)
            b._last_normalized_val = val_norm
            return

        # 4. Continuous Parameter Targets (Sliders)
        if b.invert:
            val_norm = 1.0 - val_norm

        # Scale to mapping range [min_out, max_out]
        mapped_norm = b.min_out + val_norm * (b.max_out - b.min_out)

        # Scale to parameter world range
        p_min, p_max = target.get_range(ui_state.sim)
        target_val = p_min + mapped_norm * (p_max - p_min)

        # Soft takeover / pickup check
        if b.soft_takeover:
            current_base = target.get_base_value(ui_state.sim, ui_state.preferences, ui_state.camera, ui_state.multi_load)
            current_norm = (current_base - p_min) / max(0.0001, (p_max - p_min))
            if not b._pickup_engaged:
                if abs(mapped_norm - current_norm) < 0.08:
                    b._pickup_engaged = True
                else:
                    b._last_normalized_val = val_norm
                    return  # Wait for hardware knob to meet the parameter

        # Set base value
        target.set_base_value(ui_state.sim, ui_state.preferences, ui_state.camera, ui_state.multi_load, target_val, ui_state=ui_state)
        b._last_normalized_val = val_norm

    def reset_all_pickups(self):
        """Call on preset load so hardware knobs don't immediately jump parameters."""
        for b in self.mapping_manager.bindings.values():
            b._pickup_engaged = False
