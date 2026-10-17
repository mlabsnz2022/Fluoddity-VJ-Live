"""Target registry for modulation: parameters and actions that can be controlled by MIDI, Audio, or Tempo."""
from dataclasses import dataclass, field
from typing import Callable, Any, Optional
from ui.physics_params import PHYSICS_PARAMS, PARAM_BY_NAME


@dataclass
class ModTarget:
    """A controllable parameter, toggle, dropdown cycle, or triggerable action."""
    target_id: str             # e.g., 'sim.SENSOR_GAIN', 'prefs.brightness', 'toggle.motion_blur', 'cycle.world_shape'
    label: str                 # User-facing label
    group: str                 # 'Physics (Basics)', 'Visuals', 'Preferences Sliders', 'Checkbox Toggles', 'Dropdown Selectors', etc.
    target_type: str = "float" # 'float', 'bool', 'enum', 'action'
    is_action: bool = False    # True if one-shot trigger
    default_min: float = 0.0
    default_max: float = 1.0
    hard_min: Optional[float] = None
    hard_max: Optional[float] = None
    options: list[str] = field(default_factory=list) # For enum/dropdown targets
    description: str = ""

    def get_range(self, sim_state: Any) -> tuple[float, float]:
        """Get the current min/max range for this parameter (accounting for customized slider ranges)."""
        if self.is_action or self.target_type in ('bool', 'enum', 'action'):
            return (0.0, 1.0)
        if self.target_id.startswith('sim.'):
            param_name = self.target_id.split('.', 1)[1]
            pdef = PARAM_BY_NAME.get(param_name)
            if pdef and sim_state and hasattr(sim_state, 'slider_ranges'):
                r = sim_state.slider_ranges.get(pdef.label)
                if r and len(r) >= 2:
                    return (float(r[0]), float(r[1]))
        return (self.default_min, self.default_max)

    def get_base_value(self, sim_state: Any, prefs_state: Any, camera_state: Any, multi_load_state: Any) -> float:
        """Read the current base value from the appropriate state object."""
        if self.is_action:
            return 0.0
        try:
            if self.target_type == 'bool':
                return 1.0 if self._get_bool_state(sim_state, prefs_state) else 0.0
            if self.target_type == 'enum':
                curr_opt = self._get_enum_state(sim_state, prefs_state)
                if curr_opt in self.options:
                    return float(self.options.index(curr_opt))
                elif isinstance(curr_opt, int) and 0 <= curr_opt < len(self.options):
                    return float(curr_opt)
                return 0.0

            domain, attr = self.target_id.split('.', 1)
            if domain == 'sim' and sim_state is not None:
                return float(getattr(sim_state, attr, 0.0))
            elif domain == 'prefs' and prefs_state is not None:
                return float(getattr(prefs_state, attr, 0.0))
            elif domain == 'cam' and camera_state is not None:
                if attr == 'zoom':
                    return float(camera_state.zoom)
                elif attr == 'pos_x':
                    return float(camera_state.position[0])
                elif attr == 'pos_y':
                    return float(camera_state.position[1])
            elif domain == 'multi_load' and multi_load_state is not None:
                return float(getattr(multi_load_state, attr, 0.0))
        except Exception:
            pass
        return 0.0

    def set_base_value(self, sim_state: Any, prefs_state: Any, camera_state: Any, multi_load_state: Any, val: float, ui_state: Any = None):
        """Set the base value on the appropriate state container."""
        if self.is_action:
            return
        if self.hard_min is not None and val < self.hard_min:
            val = self.hard_min
        if self.hard_max is not None and val > self.hard_max:
            val = self.hard_max

        try:
            domain, attr = self.target_id.split('.', 1)
            if domain == 'sim' and sim_state is not None:
                setattr(sim_state, attr, val)
            elif domain == 'prefs' and prefs_state is not None:
                if attr in ('speedmult', 'blur_quality'):
                    setattr(prefs_state, attr, int(round(val)))
                else:
                    setattr(prefs_state, attr, val)
                    if attr == 'world_size' and ui_state is not None:
                        if hasattr(ui_state, 'request_world_size_change'):
                            ui_state.request_world_size_change = True
                        if hasattr(ui_state, '_request_world_size_change'):
                            ui_state._request_world_size_change = True
            elif domain == 'cam' and camera_state is not None:
                if attr == 'zoom':
                    camera_state.zoom = max(0.01, val)
                elif attr == 'pos_x':
                    camera_state.position[0] = val
                elif attr == 'pos_y':
                    camera_state.position[1] = val
            elif domain == 'multi_load' and multi_load_state is not None:
                setattr(multi_load_state, attr, val)
        except Exception as e:
            print(f"Error setting {self.target_id}: {e}")

    def toggle(self, ui_state: Any):
        """Toggle a boolean checkbox target."""
        curr = self._get_bool_state(ui_state.sim, ui_state.preferences)
        self.set_bool(ui_state, not curr)

    def set_bool(self, ui_state: Any, val: bool):
        """Set a boolean checkbox target."""
        tid = self.target_id
        prefs = ui_state.preferences
        sim = ui_state.sim

        if tid == 'toggle.motion_blur':
            prefs.motion_blur = val
        elif tid == 'toggle.bloom':
            prefs.bloom_enabled = val
        elif tid == 'toggle.watercolor':
            sim.watercolor_mode = val
        elif tid == 'toggle.debug_arrows':
            prefs.debug_arrows = val
        elif tid == 'toggle.ndi_broadcast':
            prefs.ndi_enabled = val
            ndi = getattr(ui_state, 'ndi_service', None)
            if ndi:
                ndi.set_enabled(val)
        elif tid == 'toggle.physics_tooltips':
            prefs.physics_tooltips_enabled = val
        elif tid == 'toggle.strong_determinism':
            prefs.strong_determinism = val
        elif tid == 'toggle.adv_canvas':
            prefs.advanced_draw_canvas = val
            if val:
                prefs.advanced_draw_force_field = False
                prefs.advanced_draw_strafe_field = False
        elif tid == 'toggle.adv_force_field':
            prefs.advanced_draw_force_field = val
            if val:
                prefs.advanced_draw_canvas = False
                prefs.advanced_draw_strafe_field = False
        elif tid == 'toggle.adv_strafe_field':
            prefs.advanced_draw_strafe_field = val
            if val:
                prefs.advanced_draw_canvas = False
                prefs.advanced_draw_force_field = False

    def cycle_next(self, ui_state: Any):
        """Cycle dropdown target to next option."""
        if not self.options:
            return
        curr = self._get_enum_state(ui_state.sim, ui_state.preferences)
        if curr in self.options:
            curr_idx = self.options.index(curr)
        elif isinstance(curr, int) and 0 <= curr < len(self.options):
            curr_idx = curr
        else:
            curr_idx = 0
        next_idx = (curr_idx + 1) % len(self.options)
        self.set_enum_by_index(ui_state, next_idx)

    def set_enum_by_index(self, ui_state: Any, idx: int):
        """Set dropdown target option by index."""
        if not self.options or idx < 0 or idx >= len(self.options):
            return
        tid = self.target_id
        opt = self.options[idx]
        prefs = ui_state.preferences
        sim = ui_state.sim

        if tid == 'cycle.world_shape':
            if prefs.canvas_aspect_ratio != opt:
                prefs.canvas_aspect_ratio = opt
                if hasattr(ui_state, 'request_world_size_change'):
                    ui_state.request_world_size_change = True
                if hasattr(ui_state, '_request_world_size_change'):
                    ui_state._request_world_size_change = True
                if hasattr(ui_state, 'request_reload'):
                    ui_state.request_reload = True
                if hasattr(ui_state, '_request_reload'):
                    ui_state._request_reload = True
        elif tid == 'cycle.mouse_mode':
            prefs.mouse_mode = opt
        elif tid == 'cycle.view_mode':
            sim.current_view_option = idx
            if idx in (1, 2):
                ui_state.camera.cam_brush_mode = True
            else:
                ui_state.camera.cam_brush_mode = False
                sim.watercolor_mode = False
        elif tid == 'cycle.brush_mode':
            prefs.brush_mode = idx
        elif tid == 'cycle.ndi_source_mode':
            prefs.ndi_source_mode = opt
            ndi = getattr(ui_state, 'ndi_service', None)
            if ndi:
                ndi.set_source_mode(opt)
        elif tid == 'cycle.ndi_fit_mode':
            prefs.ndi_fit_mode = opt
            ndi = getattr(ui_state, 'ndi_service', None)
            if ndi:
                ndi.set_fit_mode(opt)

    def _get_bool_state(self, sim_state: Any, prefs_state: Any) -> bool:
        tid = self.target_id
        if tid == 'toggle.motion_blur':
            return getattr(prefs_state, 'motion_blur', False)
        elif tid == 'toggle.bloom':
            return getattr(prefs_state, 'bloom_enabled', False)
        elif tid == 'toggle.watercolor':
            return getattr(sim_state, 'watercolor_mode', False)
        elif tid == 'toggle.debug_arrows':
            return getattr(prefs_state, 'debug_arrows', False)
        elif tid == 'toggle.ndi_broadcast':
            return getattr(prefs_state, 'ndi_enabled', False)
        elif tid == 'toggle.physics_tooltips':
            return getattr(prefs_state, 'physics_tooltips_enabled', False)
        elif tid == 'toggle.strong_determinism':
            return getattr(prefs_state, 'strong_determinism', False)
        elif tid == 'toggle.adv_canvas':
            return getattr(prefs_state, 'advanced_draw_canvas', True)
        elif tid == 'toggle.adv_force_field':
            return getattr(prefs_state, 'advanced_draw_force_field', False)
        elif tid == 'toggle.adv_strafe_field':
            return getattr(prefs_state, 'advanced_draw_strafe_field', False)
        return False

    def _get_enum_state(self, sim_state: Any, prefs_state: Any) -> Any:
        tid = self.target_id
        if tid == 'cycle.world_shape':
            return getattr(prefs_state, 'canvas_aspect_ratio', "1:1")
        elif tid == 'cycle.mouse_mode':
            return getattr(prefs_state, 'mouse_mode', "Select Particle")
        elif tid == 'cycle.view_mode':
            return getattr(sim_state, 'current_view_option', 1)
        elif tid == 'cycle.brush_mode':
            return getattr(prefs_state, 'brush_mode', 0)
        elif tid == 'cycle.ndi_source_mode':
            return getattr(prefs_state, 'ndi_source_mode', "Camera")
        elif tid == 'cycle.ndi_fit_mode':
            return getattr(prefs_state, 'ndi_fit_mode', "Fill / Crop")
        return ""


def _build_target_registry() -> dict[str, ModTarget]:
    reg: dict[str, ModTarget] = {}

    # 1. Physics Parameters from single source of truth
    for p in PHYSICS_PARAMS:
        group_name = f"Physics ({p.group.capitalize()})"
        tid = f"sim.{p.name}"
        reg[tid] = ModTarget(
            target_id=tid,
            label=p.label,
            group=group_name,
            is_action=False,
            default_min=p.default_min,
            default_max=p.default_max,
            hard_min=p.hard_min,
            hard_max=p.hard_max,
            description=p.description
        )

    # 2. Sim Extra & Appearance parameters
    reg['sim.ORIENTATION_MIX'] = ModTarget(
        target_id='sim.ORIENTATION_MIX',
        label='Orientation Mix',
        group='Sim Settings',
        default_min=0.0,
        default_max=1.0,
        description='Mix between particle velocity and absolute orientation'
    )
    reg['sim.ink_weight'] = ModTarget(
        target_id='sim.ink_weight',
        label='Ink Weight',
        group='Appearance',
        default_min=0.1,
        default_max=5.0,
        description='Watercolor mode optical density'
    )
    reg['sim.hue_sensitivity'] = ModTarget(
        target_id='sim.hue_sensitivity',
        label='Hue Sensitivity',
        group='Appearance',
        default_min=0.0,
        default_max=2.0,
        description='Color sensitivity when coloring particles'
    )

    # 3. Preferences / Visual Post-processing Sliders
    reg['prefs.brightness'] = ModTarget(
        target_id='prefs.brightness',
        label='Brightness',
        group='Visuals',
        default_min=0.01,
        default_max=10.0,
        description='Global brightness multiplier'
    )
    reg['prefs.exposure'] = ModTarget(
        target_id='prefs.exposure',
        label='Exposure (Motion Blend)',
        group='Visuals',
        default_min=0.0,
        default_max=1.0,
        description='Temporal frame exposure'
    )
    reg['prefs.tonemap_softness'] = ModTarget(
        target_id='prefs.tonemap_softness',
        label='Tonemap Softness',
        group='Visuals',
        default_min=0.1,
        default_max=5.0,
        description='Highlight compression'
    )
    reg['prefs.bloom_intensity'] = ModTarget(
        target_id='prefs.bloom_intensity',
        label='Bloom Intensity',
        group='Visuals',
        default_min=0.0,
        default_max=3.0,
        description='Glow/bloom brightness'
    )
    reg['prefs.bloom_threshold'] = ModTarget(
        target_id='prefs.bloom_threshold',
        label='Bloom Threshold',
        group='Visuals',
        default_min=0.0,
        default_max=2.0,
        description='Brightness cutoff for bloom'
    )
    reg['prefs.bloom_radius'] = ModTarget(
        target_id='prefs.bloom_radius',
        label='Bloom Radius',
        group='Visuals',
        default_min=0.1,
        default_max=3.0,
        description='Spread of the bloom blur kernel'
    )
    reg['prefs.world_size'] = ModTarget(
        target_id='prefs.world_size',
        label='World Size',
        group='Preferences Sliders',
        default_min=0.02,
        default_max=4.0,
        hard_min=0.02,
        hard_max=4.0,
        description='Controls the size and density of the simulation world'
    )
    reg['prefs.speedmult'] = ModTarget(
        target_id='prefs.speedmult',
        label='Simulation Rate (Speedmult)',
        group='Preferences Sliders',
        default_min=1.0,
        default_max=30.0,
        hard_min=1.0,
        hard_max=30.0,
        description='Physics sub-steps per frame'
    )
    reg['prefs.blur_quality'] = ModTarget(
        target_id='prefs.blur_quality',
        label='Motion Blur Quality',
        group='Preferences Sliders',
        default_min=1.0,
        default_max=20.0,
        hard_min=1.0,
        hard_max=20.0,
        description='Motion blur frame skipping interval'
    )
    reg['prefs.arrow_sensitivity'] = ModTarget(
        target_id='prefs.arrow_sensitivity',
        label='Arrow Sensitivity',
        group='Preferences Sliders',
        default_min=1.0,
        default_max=20.0,
        hard_min=1.0,
        hard_max=20.0,
        description='Scaling factor for vector field debug arrows'
    )
    reg['prefs.draw_power'] = ModTarget(
        target_id='prefs.draw_power',
        label='Brush Draw Power',
        group='Drawing',
        default_min=0.1,
        default_max=5.0,
        description='Trail drawing force'
    )
    reg['prefs.draw_size'] = ModTarget(
        target_id='prefs.draw_size',
        label='Brush Size',
        group='Drawing',
        default_min=0.01,
        default_max=0.5,
        description='Trail brush radius'
    )
    reg['prefs.fixed_direction_heading'] = ModTarget(
        target_id='prefs.fixed_direction_heading',
        label='Brush Fixed Heading',
        group='Drawing',
        default_min=-3.14159,
        default_max=3.14159,
        hard_min=-3.14159,
        hard_max=3.14159,
        description='Heading angle for Fixed Direction brush mode'
    )
    reg['prefs.force_field_strength'] = ModTarget(
        target_id='prefs.force_field_strength',
        label='Force Field Strength',
        group='Drawing',
        default_min=0.0001,
        default_max=10.0,
        hard_min=0.0001,
        hard_max=10.0,
        description='Multiplier for force field effects'
    )
    reg['prefs.strafe_field_strength'] = ModTarget(
        target_id='prefs.strafe_field_strength',
        label='Strafe Field Strength',
        group='Drawing',
        default_min=0.0001,
        default_max=10.0,
        hard_min=0.0001,
        hard_max=10.0,
        description='Multiplier for strafe field effects'
    )
    reg['prefs.draw_target_overlay_opacity'] = ModTarget(
        target_id='prefs.draw_target_overlay_opacity',
        label='Draw Target Overlay Opacity',
        group='Drawing',
        default_min=0.0,
        default_max=1.0,
        hard_min=0.0,
        hard_max=1.0,
        description='Opacity of the force/strafe field color overlay'
    )

    # 4. Checkbox Toggles
    checkboxes = [
        ('toggle.motion_blur', 'Motion Blur', 'Toggle physics motion blur accumulation'),
        ('toggle.bloom', 'Bloom', 'Toggle post-process glow / bloom effect'),
        ('toggle.watercolor', 'Watercolor Mode', 'Toggle watercolor pigment simulation'),
        ('toggle.debug_arrows', 'Debug / Vector Arrows', 'Toggle vector field arrow grid overlay'),
        ('toggle.ndi_broadcast', 'NDI Broadcast', 'Toggle NDI network video streaming'),
        ('toggle.physics_tooltips', 'Physics Tooltips', 'Toggle verbose tooltips and vector diagrams'),
        ('toggle.strong_determinism', 'Strong Determinism', 'Toggle CPU/GPU synchronization determinism'),
        ('toggle.adv_canvas', 'Draw Target: Canvas/Trails', 'Set active draw target to particle trail canvas'),
        ('toggle.adv_force_field', 'Draw Target: Force Field', 'Set active draw target to force field'),
        ('toggle.adv_strafe_field', 'Draw Target: Strafe Field', 'Set active draw target to strafe field'),
    ]
    for cid, clabel, cdesc in checkboxes:
        reg[cid] = ModTarget(
            target_id=cid,
            label=clabel,
            group='Checkbox Toggles',
            target_type='bool',
            description=cdesc
        )

    # 5. Dropdown Selectors
    reg['cycle.world_shape'] = ModTarget(
        target_id='cycle.world_shape',
        label='World Shape (Aspect Ratio)',
        group='Dropdown Selectors',
        target_type='enum',
        options=["1:1", "4:3", "16:9", "2:1", "3:1", "3:4", "9:16", "1:2", "1:3"],
        description='Cycle or select canvas aspect ratio'
    )
    reg['cycle.mouse_mode'] = ModTarget(
        target_id='cycle.mouse_mode',
        label='Mouse Mode',
        group='Dropdown Selectors',
        target_type='enum',
        options=["Select Particle", "Draw Trail"],
        description='Cycle or select mouse interaction mode'
    )
    reg['cycle.view_mode'] = ModTarget(
        target_id='cycle.view_mode',
        label='View Mode',
        group='Dropdown Selectors',
        target_type='enum',
        options=["Canvas (Persistent particle trails)", "Camera (Particles rendered as dots)", "Camera [Tiled]"],
        description='Cycle or select viewport rendering view'
    )
    reg['cycle.brush_mode'] = ModTarget(
        target_id='cycle.brush_mode',
        label='Brush Mode',
        group='Dropdown Selectors',
        target_type='enum',
        options=["Mouse Direction", "Inverse Mouse Direction", "Fixed Direction", "In - Attract", "Out - Repel"],
        description='Cycle or select brush heading/direction mode'
    )
    reg['cycle.ndi_source_mode'] = ModTarget(
        target_id='cycle.ndi_source_mode',
        label='NDI Source Framing',
        group='Dropdown Selectors',
        target_type='enum',
        options=["Camera", "World"],
        description='Cycle or select NDI frame capture source (Camera or World)'
    )
    reg['cycle.ndi_fit_mode'] = ModTarget(
        target_id='cycle.ndi_fit_mode',
        label='NDI Fit Mode',
        group='Dropdown Selectors',
        target_type='enum',
        options=["Fill / Crop", "Fit / Letterbox"],
        description='Cycle or select NDI output aspect ratio fitting'
    )

    # 6. Camera controls
    reg['cam.zoom'] = ModTarget(
        target_id='cam.zoom',
        label='Camera Zoom',
        group='Camera',
        default_min=0.1,
        default_max=10.0,
        description='Camera magnification factor'
    )
    reg['cam.pos_x'] = ModTarget(
        target_id='cam.pos_x',
        label='Camera Pan X',
        group='Camera',
        default_min=-2.0,
        default_max=2.0,
        description='Camera horizontal position'
    )
    reg['cam.pos_y'] = ModTarget(
        target_id='cam.pos_y',
        label='Camera Pan Y',
        group='Camera',
        default_min=-2.0,
        default_max=2.0,
        description='Camera vertical position'
    )

    # 7. Multi-Load Controls
    reg['multi_load.current_progress'] = ModTarget(
        target_id='multi_load.current_progress',
        label='Multi-Load Progress',
        group='Multi-Load',
        default_min=0.0,
        default_max=1.0,
        description='Position in circular multi-load buffer'
    )
    reg['multi_load.simultaneous_configs'] = ModTarget(
        target_id='multi_load.simultaneous_configs',
        label='Simultaneous Configs',
        group='Multi-Load',
        default_min=1.0,
        default_max=16.0,
        description='Number of concurrent mixed configs'
    )

    # 8. Action Triggers
    actions = [
        ('action.next_preset', 'Next Preset', 'Advance to the next preset in playlist'),
        ('action.prev_preset', 'Previous Preset', 'Go back to previous preset'),
        ('action.random_preset', 'Random Preset', 'Jump to a random preset'),
        ('action.reset_sim', 'Reset Simulation (R)', 'Reset particle positions to initial conditions'),
        ('action.full_reset', 'Full Reset (Z)', 'Zero rule and randomize'),
        ('action.clear_canvas', 'Clear Canvas', 'Clear all active trails on canvas'),
        ('action.randomize_mutations', 'Randomize Mutations (M)', 'Mutate current rule with new seed'),
        ('action.toggle_pause', 'Toggle Pause (Space)', 'Pause or resume simulation'),
        ('action.screenshot', 'Take Screenshot', 'Trigger high-quality screenshot capture'),
        ('action.tap_tempo', 'Tap Tempo', 'Tap beat for tempo synchronization'),
    ]
    for aid, alabel, adesc in actions:
        reg[aid] = ModTarget(
            target_id=aid,
            label=alabel,
            group='Actions / Triggers',
            is_action=True,
            default_min=0.0,
            default_max=1.0,
            description=adesc
        )

    return reg


TARGET_REGISTRY = _build_target_registry()


def get_target(target_id: str) -> Optional[ModTarget]:
    return TARGET_REGISTRY.get(target_id)


def get_targets_by_group() -> dict[str, list[ModTarget]]:
    groups: dict[str, list[ModTarget]] = {}
    for t in TARGET_REGISTRY.values():
        groups.setdefault(t.group, []).append(t)
    return groups
