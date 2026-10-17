"""Built-in MIDI controller profiles for popular hardware."""
from services.midi.midi_mapping import MidiBinding

BUILTIN_PROFILES: dict[str, list[dict]] = {
    "Novation Launch Control XL": [
        # Top Row (Send A, CC 13-20)
        {"target_id": "sim.SENSOR_GAIN", "msg_type": "cc", "channel": -1, "control": 13, "soft_takeover": True},
        {"target_id": "sim.SENSOR_ANGLE", "msg_type": "cc", "channel": -1, "control": 14, "soft_takeover": True},
        {"target_id": "sim.SENSOR_DISTANCE", "msg_type": "cc", "channel": -1, "control": 15, "soft_takeover": True},
        {"target_id": "sim.STEP_SIZE", "msg_type": "cc", "channel": -1, "control": 16, "soft_takeover": True},
        {"target_id": "sim.TRAIL_PERSISTENCE", "msg_type": "cc", "channel": -1, "control": 17, "soft_takeover": True},
        {"target_id": "sim.TRAIL_DIFFUSION", "msg_type": "cc", "channel": -1, "control": 18, "soft_takeover": True},
        {"target_id": "sim.DRAG", "msg_type": "cc", "channel": -1, "control": 19, "soft_takeover": True},
        {"target_id": "sim.AXIAL_FORCE", "msg_type": "cc", "channel": -1, "control": 20, "soft_takeover": True},
        # Mid Row (Send B, CC 29-36)
        {"target_id": "sim.STRAFE_FORCE", "msg_type": "cc", "channel": -1, "control": 29, "soft_takeover": True},
        {"target_id": "sim.ORIENTATION_MIX", "msg_type": "cc", "channel": -1, "control": 30, "soft_takeover": True},
        {"target_id": "sim.HAZARD_RATE", "msg_type": "cc", "channel": -1, "control": 31, "soft_takeover": True},
        {"target_id": "sim.MUTATION_SCALE", "msg_type": "cc", "channel": -1, "control": 32, "soft_takeover": True},
        {"target_id": "prefs.exposure", "msg_type": "cc", "channel": -1, "control": 33, "soft_takeover": True},
        {"target_id": "prefs.bloom_intensity", "msg_type": "cc", "channel": -1, "control": 34, "soft_takeover": True},
        {"target_id": "prefs.brightness", "msg_type": "cc", "channel": -1, "control": 35, "soft_takeover": True},
        {"target_id": "cam.zoom", "msg_type": "cc", "channel": -1, "control": 36, "soft_takeover": True},
        # Bottom Row (Pan, CC 49-56)
        {"target_id": "prefs.bloom_threshold", "msg_type": "cc", "channel": -1, "control": 49, "soft_takeover": True},
        {"target_id": "prefs.draw_power", "msg_type": "cc", "channel": -1, "control": 50, "soft_takeover": True},
        {"target_id": "prefs.draw_size", "msg_type": "cc", "channel": -1, "control": 51, "soft_takeover": True},
        {"target_id": "multi_load.current_progress", "msg_type": "cc", "channel": -1, "control": 52, "soft_takeover": True},
        {"target_id": "multi_load.simultaneous_configs", "msg_type": "cc", "channel": -1, "control": 53, "soft_takeover": True},
        {"target_id": "cam.pos_x", "msg_type": "cc", "channel": -1, "control": 54, "soft_takeover": True},
        {"target_id": "cam.pos_y", "msg_type": "cc", "channel": -1, "control": 55, "soft_takeover": True},
        {"target_id": "prefs.tonemap_softness", "msg_type": "cc", "channel": -1, "control": 56, "soft_takeover": True},
        # Faders (CC 77-84)
        {"target_id": "sim.SENSOR_GAIN", "msg_type": "cc", "channel": -1, "control": 77, "soft_takeover": True},
        {"target_id": "sim.SENSOR_DISTANCE", "msg_type": "cc", "channel": -1, "control": 78, "soft_takeover": True},
        {"target_id": "sim.TRAIL_PERSISTENCE", "msg_type": "cc", "channel": -1, "control": 79, "soft_takeover": True},
        {"target_id": "sim.TRAIL_DIFFUSION", "msg_type": "cc", "channel": -1, "control": 80, "soft_takeover": True},
        {"target_id": "sim.DRAG", "msg_type": "cc", "channel": -1, "control": 81, "soft_takeover": True},
        {"target_id": "sim.AXIAL_FORCE", "msg_type": "cc", "channel": -1, "control": 82, "soft_takeover": True},
        {"target_id": "prefs.bloom_intensity", "msg_type": "cc", "channel": -1, "control": 83, "soft_takeover": True},
        {"target_id": "prefs.exposure", "msg_type": "cc", "channel": -1, "control": 84, "soft_takeover": True},
        # Buttons (Track Focus Notes 41-48)
        {"target_id": "action.prev_preset", "msg_type": "note", "channel": -1, "control": 41, "mode": "trigger"},
        {"target_id": "action.next_preset", "msg_type": "note", "channel": -1, "control": 42, "mode": "trigger"},
        {"target_id": "action.random_preset", "msg_type": "note", "channel": -1, "control": 43, "mode": "trigger"},
        {"target_id": "action.reset_sim", "msg_type": "note", "channel": -1, "control": 44, "mode": "trigger"},
        {"target_id": "action.clear_canvas", "msg_type": "note", "channel": -1, "control": 45, "mode": "trigger"},
        {"target_id": "action.randomize_mutations", "msg_type": "note", "channel": -1, "control": 46, "mode": "trigger"},
        {"target_id": "action.toggle_pause", "msg_type": "note", "channel": -1, "control": 47, "mode": "trigger"},
        {"target_id": "action.tap_tempo", "msg_type": "note", "channel": -1, "control": 48, "mode": "trigger"},
        # Buttons (Track Control Notes 73-76)
        {"target_id": "action.screenshot", "msg_type": "note", "channel": -1, "control": 73, "mode": "trigger"},
        {"target_id": "action.full_reset", "msg_type": "note", "channel": -1, "control": 74, "mode": "trigger"},
    ],
    "Akai APC Key 25": [
        # Knobs 1-8 (CC 48-55)
        {"target_id": "sim.SENSOR_GAIN", "msg_type": "cc", "channel": -1, "control": 48, "soft_takeover": True},
        {"target_id": "sim.SENSOR_ANGLE", "msg_type": "cc", "channel": -1, "control": 49, "soft_takeover": True},
        {"target_id": "sim.SENSOR_DISTANCE", "msg_type": "cc", "channel": -1, "control": 50, "soft_takeover": True},
        {"target_id": "sim.STEP_SIZE", "msg_type": "cc", "channel": -1, "control": 51, "soft_takeover": True},
        {"target_id": "sim.TRAIL_PERSISTENCE", "msg_type": "cc", "channel": -1, "control": 52, "soft_takeover": True},
        {"target_id": "sim.TRAIL_DIFFUSION", "msg_type": "cc", "channel": -1, "control": 53, "soft_takeover": True},
        {"target_id": "sim.DRAG", "msg_type": "cc", "channel": -1, "control": 54, "soft_takeover": True},
        {"target_id": "sim.AXIAL_FORCE", "msg_type": "cc", "channel": -1, "control": 55, "soft_takeover": True},
        # Scene Launch Buttons (Notes 82-86)
        {"target_id": "action.prev_preset", "msg_type": "note", "channel": -1, "control": 82, "mode": "trigger"},
        {"target_id": "action.next_preset", "msg_type": "note", "channel": -1, "control": 83, "mode": "trigger"},
        {"target_id": "action.random_preset", "msg_type": "note", "channel": -1, "control": 84, "mode": "trigger"},
        {"target_id": "action.reset_sim", "msg_type": "note", "channel": -1, "control": 85, "mode": "trigger"},
        {"target_id": "action.clear_canvas", "msg_type": "note", "channel": -1, "control": 86, "mode": "trigger"},
    ],
    "Generic 8-Knob Controller (CC 1-8)": [
        {"target_id": "sim.SENSOR_GAIN", "msg_type": "cc", "channel": -1, "control": 1, "soft_takeover": True},
        {"target_id": "sim.SENSOR_ANGLE", "msg_type": "cc", "channel": -1, "control": 2, "soft_takeover": True},
        {"target_id": "sim.SENSOR_DISTANCE", "msg_type": "cc", "channel": -1, "control": 3, "soft_takeover": True},
        {"target_id": "sim.STEP_SIZE", "msg_type": "cc", "channel": -1, "control": 4, "soft_takeover": True},
        {"target_id": "sim.TRAIL_PERSISTENCE", "msg_type": "cc", "channel": -1, "control": 5, "soft_takeover": True},
        {"target_id": "sim.TRAIL_DIFFUSION", "msg_type": "cc", "channel": -1, "control": 6, "soft_takeover": True},
        {"target_id": "sim.DRAG", "msg_type": "cc", "channel": -1, "control": 7, "soft_takeover": True},
        {"target_id": "sim.AXIAL_FORCE", "msg_type": "cc", "channel": -1, "control": 8, "soft_takeover": True},
    ],
    "Generic 8-Knob Controller (CC 16-23)": [
        {"target_id": "sim.SENSOR_GAIN", "msg_type": "cc", "channel": -1, "control": 16, "soft_takeover": True},
        {"target_id": "sim.SENSOR_ANGLE", "msg_type": "cc", "channel": -1, "control": 17, "soft_takeover": True},
        {"target_id": "sim.SENSOR_DISTANCE", "msg_type": "cc", "channel": -1, "control": 18, "soft_takeover": True},
        {"target_id": "sim.STEP_SIZE", "msg_type": "cc", "channel": -1, "control": 19, "soft_takeover": True},
        {"target_id": "sim.TRAIL_PERSISTENCE", "msg_type": "cc", "channel": -1, "control": 20, "soft_takeover": True},
        {"target_id": "sim.TRAIL_DIFFUSION", "msg_type": "cc", "channel": -1, "control": 21, "soft_takeover": True},
        {"target_id": "sim.DRAG", "msg_type": "cc", "channel": -1, "control": 22, "soft_takeover": True},
        {"target_id": "sim.AXIAL_FORCE", "msg_type": "cc", "channel": -1, "control": 23, "soft_takeover": True},
    ],
}


def load_profile_bindings(profile_name: str) -> list[MidiBinding]:
    """Return a list of MidiBinding objects for a given builtin profile name."""
    profile_data = BUILTIN_PROFILES.get(profile_name, [])
    return [MidiBinding(**item) for item in profile_data]
