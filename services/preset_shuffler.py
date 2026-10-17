"""Preset Shuffler: automatically transitions through presets on musical beat/bar intervals."""
import random
from pathlib import Path
from typing import Optional, Any
from services.config_saver import ConfigSaver, PhysicsConfig


class PresetShuffler:
    """Manages preset playlist and beat-synced automatic transitions."""

    def __init__(self, config_saver: ConfigSaver):
        self.config_saver = config_saver
        self.playlist: list[tuple[str, str]] = []  # [(filename, category), ...]
        self.current_index: int = 0
        self.enabled: bool = False
        self.mode: str = "Sequential"              # 'Sequential', 'Random', 'Shuffle'
        self.interval_bars: int = 4                # Change every N bars (1 bar = 4 beats)
        self.transition_mode: str = "Morph"        # 'Morph' (default), 'Glide', 'Cut'
        self.hold: bool = False                    # Pause auto-advance

        # Runtime tracking
        self._bars_since_last_change: int = 0
        self._shuffle_pool: list[int] = []
        self._current_filename: str = "_Default"
        self._current_category: str = "Core"

    def populate_from_categories(self, config_files_by_category: dict[str, list[str]], categories: Optional[list[str]] = None):
        """Populate playlist from config category lists (e.g. ['Core', 'Custom'])."""
        if categories is None:
            categories = ["Core", "Custom"]
        self.playlist.clear()
        for cat in categories:
            for name in config_files_by_category.get(cat, []):
                self.playlist.append((name, cat))
        self.current_index = 0
        self._reset_shuffle_pool()

    def add_to_playlist(self, filename: str, category: str):
        item = (filename, category)
        if item not in self.playlist:
            self.playlist.append(item)
            self._reset_shuffle_pool()

    def remove_from_playlist(self, index: int):
        if 0 <= index < len(self.playlist):
            self.playlist.pop(index)
            self._reset_shuffle_pool()

    def clear_playlist(self):
        self.playlist.clear()
        self.current_index = 0
        self._reset_shuffle_pool()

    def _reset_shuffle_pool(self):
        self._shuffle_pool = list(range(len(self.playlist)))
        random.shuffle(self._shuffle_pool)

    def trigger_next(self, app_context: Any):
        """Manually advance to next preset."""
        if not self.playlist:
            return
        if self.mode == "Random":
            self.current_index = random.randint(0, len(self.playlist) - 1)
        elif self.mode == "Shuffle":
            if not self._shuffle_pool:
                self._reset_shuffle_pool()
            self.current_index = self._shuffle_pool.pop() if self._shuffle_pool else 0
        else:  # Sequential
            self.current_index = (self.current_index + 1) % len(self.playlist)

        self._load_current_preset(app_context)
        self._bars_since_last_change = 0

    def trigger_prev(self, app_context: Any):
        """Manually go to previous preset."""
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self._load_current_preset(app_context)
        self._bars_since_last_change = 0

    def trigger_random(self, app_context: Any):
        """Jump to random preset."""
        if not self.playlist:
            return
        self.current_index = random.randint(0, len(self.playlist) - 1)
        self._load_current_preset(app_context)
        self._bars_since_last_change = 0

    def update(self, tempo_clock: Any, app_context: Any):
        """Called each frame: checks for bar crossings and triggers transitions."""
        if not self.enabled or self.hold or not self.playlist:
            return

        if tempo_clock.just_crossed_bar:
            self._bars_since_last_change += 1
            if self._bars_since_last_change >= self.interval_bars:
                self._bars_since_last_change = 0
                self.trigger_next(app_context)

    def _load_current_preset(self, app):
        """Perform preset load without clearing canvas (Morph) or with Cut."""
        if not (0 <= self.current_index < len(self.playlist)):
            return

        filename, category = self.playlist[self.current_index]
        self._current_filename = filename
        self._current_category = category

        # Resolve path
        filepath = app.ui._get_config_path(filename, category)
        config = self.config_saver.load_from_file(filepath)
        if config is None:
            print(f"[PresetShuffler] Failed to load {filepath}")
            return

        ui_state = app.ui.state

        # Apply config with parameter lock support
        rule = app.command_handler._apply_config_with_locks(config, ui_state)

        # Apply rule to sim
        app.sim.apply_rule(rule)

        # Handle field texture if present
        if app.field_handler:
            app.field_handler.apply_for_config(config, filepath, ui_state)

        # If transition is Cut, reset particle positions
        if self.transition_mode == "Cut":
            app.sim.reset()

        # Reset MIDI soft-takeover pickups so knobs don't immediately jump
        if hasattr(app, 'midi_service') and app.midi_service:
            app.midi_service.reset_all_pickups()

        # Update UI defaults
        app.ui.update_physics_defaults(filename)
        print(f"[PresetShuffler] Loaded: {filename} ({category}) [{self.transition_mode}]")

    @property
    def bars_remaining(self) -> int:
        return max(0, self.interval_bars - self._bars_since_last_change)

    @property
    def current_preset_name(self) -> str:
        return self._current_filename
