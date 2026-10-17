"""Live performance window mixin: MIDI, Audio Reactivity, Tempo & Preset Shuffling, and NDI Output."""
from imgui_bundle import imgui
import numpy as np
from services.modulation.targets import TARGET_REGISTRY, get_targets_by_group, get_target
from services.modulation.signals import AUDIO_SIGNALS, TEMPO_SIGNALS
from services.modulation.engine import AudioModMapping
from services.midi.midi_mapping import MidiBinding
from services.ndi_output_service import RESOLUTION_PRESETS
from state import save_preferences


class LiveWindowMixin:
    """Mixin for rendering the Live Performance panel (MIDI, Audio, Tempo/Shuffle, NDI)."""

    def _init_live_window_state(self):
        self.show_live_window: bool = True
        self.live_selected_tab: int = 0
        self._new_audio_target_idx: int = 0
        self._new_audio_signal_idx: int = 0
        self._custom_band_low: float = 100.0
        self._custom_band_high: float = 1000.0
        self._selected_midi_profile_idx: int = 0

    def render_live_window(self):
        """Render the unified Live Performance window."""
        if not self.show_sidebar or not getattr(self, 'show_live_window', False):
            return

        imgui.set_next_window_size(imgui.ImVec2(520, 560), imgui.Cond_.first_use_ever)
        opened, self.show_live_window = imgui.begin("Live Performance Controls", self.show_live_window)
        if not opened:
            imgui.end()
            return

        if imgui.begin_tab_bar("LiveTabs"):
            # --- Tab 1: MIDI ---
            if imgui.begin_tab_item("MIDI")[0]:
                self._render_midi_tab()
                imgui.end_tab_item()

            # --- Tab 2: Audio Reactivity ---
            if imgui.begin_tab_item("Audio Reactivity")[0]:
                self._render_audio_tab()
                imgui.end_tab_item()

            # --- Tab 3: Tempo & Shuffle ---
            if imgui.begin_tab_item("Tempo & Shuffle")[0]:
                self._render_tempo_shuffle_tab()
                imgui.end_tab_item()

            # --- Tab 4: NDI Output ---
            if imgui.begin_tab_item("NDI Output")[0]:
                self._render_ndi_tab()
                imgui.end_tab_item()

            imgui.end_tab_bar()

        imgui.end()

    # =========================================================================
    # TAB 1: MIDI
    # =========================================================================
    def _render_midi_tab(self):
        midi = getattr(self, 'midi_service', None)
        if not midi:
            imgui.text_disabled("MIDI Service not initialized.")
            return

        # Device Selection
        ports = ["All Available"] + midi.get_available_ports()
        curr_port = midi.selected_port_name
        curr_idx = ports.index(curr_port) if curr_port in ports else 0

        imgui.text("MIDI Input Device:")
        imgui.same_line()
        imgui.set_next_item_width(220)
        changed, new_idx = imgui.combo("##MidiPort", curr_idx, ports)
        if changed:
            midi.set_port(ports[new_idx])

        imgui.same_line()
        if imgui.button("Rescan"):
            midi.restart()

        # Connection & Activity Monitor
        is_conn = midi.is_connected()
        led_color = imgui.ImVec4(0.2, 0.9, 0.3, 1.0) if is_conn else imgui.ImVec4(0.5, 0.5, 0.5, 1.0)
        imgui.text_colored(led_color, "● Connected" if is_conn else "○ No Device")
        imgui.same_line(spacing=20)
        imgui.text_disabled(f"Last Event: {midi.last_message_str}")

        # MIDI Learn Banner
        if midi.learn_target_id:
            imgui.separator()
            target = get_target(midi.learn_target_id)
            label = target.label if target else midi.learn_target_id
            imgui.push_style_color(imgui.Col_.text, imgui.ImVec4(1.0, 0.8, 0.2, 1.0))
            imgui.text(f"LEARNING: Move a knob, fader, or press a key for '{label}'...")
            imgui.pop_style_color()
            imgui.same_line()
            if imgui.button("Cancel Learn"):
                midi.cancel_learn()

        imgui.separator()

        # Preset Controller Profiles
        from services.midi.profiles import BUILTIN_PROFILES
        profile_names = list(BUILTIN_PROFILES.keys())
        imgui.text("Hardware Profile:")
        imgui.same_line()
        imgui.set_next_item_width(220)
        _, self._selected_midi_profile_idx = imgui.combo("##MidiProfiles", self._selected_midi_profile_idx, profile_names)
        imgui.same_line()
        if imgui.button("Load Profile"):
            p_name = profile_names[self._selected_midi_profile_idx]
            mgr.load_profile(p_name)

        # Inline Target Learn Selector
        targets_by_grp = get_targets_by_group()
        all_target_items = []
        for grp_name, tgts in targets_by_grp.items():
            for t in tgts:
                all_target_items.append((t.target_id, f"[{grp_name}] {t.label}"))
        target_display_labels = [item[1] for item in all_target_items]

        imgui.text("Target:")
        imgui.same_line()
        imgui.set_next_item_width(260)
        curr_t_idx = getattr(self, '_selected_midi_target_idx', 0)
        changed_t, self._selected_midi_target_idx = imgui.combo("##MidiTargetSelect", curr_t_idx, target_display_labels)
        imgui.same_line()
        if imgui.button("+ Learn"):
            if 0 <= self._selected_midi_target_idx < len(all_target_items):
                sel_tid = all_target_items[self._selected_midi_target_idx][0]
                midi.start_learn(sel_tid)

        imgui.separator()

        # Active Mappings Table
        mgr = midi.mapping_manager
        imgui.text(f"Active Mappings ({len(mgr.bindings)}):")
        imgui.same_line()
        if imgui.button("Save Mappings"):
            mgr.save_to_file()
        imgui.same_line()
        if imgui.button("Load Mappings"):
            mgr.load_from_file()
        imgui.same_line()
        if imgui.button("Clear All##Midi"):
            mgr.clear()

        if imgui.begin_table("MidiBindingsTable", 6, imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.scroll_y, imgui.ImVec2(0, 240)):
            imgui.table_setup_column("Target", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("Control", imgui.TableColumnFlags_.width_fixed, 100)
            imgui.table_setup_column("Mode", imgui.TableColumnFlags_.width_fixed, 60)
            imgui.table_setup_column("Pickup", imgui.TableColumnFlags_.width_fixed, 45)
            imgui.table_setup_column("Invert", imgui.TableColumnFlags_.width_fixed, 45)
            imgui.table_setup_column("Del", imgui.TableColumnFlags_.width_fixed, 35)
            imgui.table_headers_row()

            for key, b in list(mgr.bindings.items()):
                imgui.table_next_row()
                target = get_target(b.target_id)
                t_label = target.label if target else b.target_id

                imgui.table_next_column()
                imgui.text(t_label)

                imgui.table_next_column()
                ch_str = "Omni" if b.channel < 0 else f"Ch {b.channel+1}"
                imgui.text(f"{b.msg_type.upper()} {b.control} ({ch_str})")

                imgui.table_next_column()
                imgui.text_disabled(b.mode[:6])

                imgui.table_next_column()
                if target and target.target_type == 'float' and not target.is_action:
                    changed_st, b.soft_takeover = imgui.checkbox(f"##st_{key}", b.soft_takeover)
                else:
                    imgui.text_disabled("-")

                imgui.table_next_column()
                if target and target.target_type == 'float':
                    changed_inv, b.invert = imgui.checkbox(f"##inv_{key}", b.invert)
                else:
                    imgui.text_disabled("-")

                imgui.table_next_column()
                if imgui.button(f"X##del_{key}"):
                    mgr.remove_binding(key)

            imgui.end_table()

    # =========================================================================
    # TAB 2: Audio Reactivity
    # =========================================================================
    def _render_audio_tab(self):
        audio_svc = getattr(self, 'audio_service', None)
        mod_engine = getattr(self, 'modulation_engine', None)
        if not audio_svc or not mod_engine:
            imgui.text_disabled("Audio/Modulation service not available.")
            return

        ainput = audio_svc.audio_input
        analyzer = audio_svc.analyzer

        # Device selector
        devices = ainput.get_input_devices()
        dev_names = [d[0] for d in devices]
        if not dev_names:
            dev_names = ["No Audio Devices Found"]

        imgui.text("Audio Input:")
        imgui.same_line()
        imgui.set_next_item_width(280)
        curr_idx = 0
        changed, new_idx = imgui.combo("##AudioDev", curr_idx, dev_names)
        if changed and new_idx < len(devices):
            d_name, is_loop, d_id = devices[new_idx]
            ainput.start(d_id, is_loop)

        # Gain & AGC
        imgui.same_line(spacing=15)
        _, analyzer.agc_enabled = imgui.checkbox("Auto-Gain (AGC)", analyzer.agc_enabled)

        changed_gain, analyzer.gain = imgui.slider_float("Gain", analyzer.gain, 0.1, 5.0, "%.1fx")

        # Live Levels
        rms = mod_engine.bus.get_signal('audio.amplitude')
        peak = mod_engine.bus.get_signal('audio.peak')
        onset = mod_engine.bus.get_signal('audio.onset_flux')

        imgui.text(f"RMS: {rms:.2f}")
        imgui.same_line()
        imgui.progress_bar(rms, imgui.ImVec2(100, 14), "")
        imgui.same_line()
        imgui.text(f"Peak: {peak:.2f}")
        imgui.same_line()
        imgui.progress_bar(peak, imgui.ImVec2(100, 14), "")
        imgui.same_line()
        imgui.text_colored(imgui.ImVec4(1.0, 0.3, 0.3, 1.0) if onset > 0.4 else imgui.ImVec4(0.4, 0.4, 0.4, 1.0), "BEAT")

        # Visual Spectrum plot
        imgui.text("Frequency Spectrum (30 Hz - 18 kHz):")
        spec = analyzer.spectrum_display
        imgui.plot_lines("##Spectrum", spec, overlay_text="", scale_min=0.0, scale_max=1.0, graph_size=imgui.ImVec2(0, 50))

        # Frequency Band Energy Sliders (Read-only monitor)
        imgui.text("Bands:")
        for b_name in ['sub', 'bass', 'low_mid', 'mid', 'high_mid', 'presence', 'air']:
            val = mod_engine.bus.get_signal(f'audio.band_{b_name}')
            imgui.same_line()
            imgui.progress_bar(val, imgui.ImVec2(55, 12), b_name[:4])

        imgui.separator()

        # Active Audio Mappings Table
        imgui.text(f"Active Audio Mappings ({len(mod_engine.audio_mappings)}):")
        imgui.same_line()
        if imgui.button("Save##Aud"):
            mod_engine.save_mappings()
        imgui.same_line()
        if imgui.button("Load##Aud"):
            mod_engine.load_mappings()
        imgui.same_line()
        if imgui.button("Clear All##Aud"):
            mod_engine.clear_all_audio_mappings()

        # Add new mapping inline
        all_targets = [t for t in TARGET_REGISTRY.values() if not t.is_action]
        t_labels = [t.label for t in all_targets]
        sig_ids = [s[0] for s in AUDIO_SIGNALS]
        sig_labels = [s[1] for s in AUDIO_SIGNALS]

        imgui.set_next_item_width(160)
        _, self._new_audio_target_idx = imgui.combo("##NewModTarget", self._new_audio_target_idx, t_labels)
        imgui.same_line()
        imgui.set_next_item_width(160)
        _, self._new_audio_signal_idx = imgui.combo("##NewModSig", self._new_audio_signal_idx, sig_labels)
        imgui.same_line()
        if imgui.button("+ Add Mapping"):
            tgt = all_targets[self._new_audio_target_idx]
            sig = sig_ids[self._new_audio_signal_idx]
            mod_engine.add_or_update_audio_mapping(AudioModMapping(target_id=tgt.target_id, signal_name=sig, depth=0.4))

        if imgui.begin_table("AudioMappingsTable", 6, imgui.TableFlags_.borders | imgui.TableFlags_.row_bg | imgui.TableFlags_.scroll_y, imgui.ImVec2(0, 160)):
            imgui.table_setup_column("Target", imgui.TableColumnFlags_.width_stretch)
            imgui.table_setup_column("Band / Signal", imgui.TableColumnFlags_.width_fixed, 110)
            imgui.table_setup_column("Depth", imgui.TableColumnFlags_.width_fixed, 110)
            imgui.table_setup_column("+/-", imgui.TableColumnFlags_.width_fixed, 40)
            imgui.table_setup_column("On", imgui.TableColumnFlags_.width_fixed, 35)
            imgui.table_setup_column("Del", imgui.TableColumnFlags_.width_fixed, 35)
            imgui.table_headers_row()

            for tid, m in list(mod_engine.audio_mappings.items()):
                imgui.table_next_row()
                target = get_target(tid)
                t_label = target.label if target else tid

                imgui.table_next_column()
                imgui.text(t_label)

                imgui.table_next_column()
                # Friendly signal label
                disp_sig = m.signal_name.replace("audio.band_", "").replace("audio.", "")
                imgui.text(disp_sig)

                imgui.table_next_column()
                imgui.set_next_item_width(100)
                _, m.depth = imgui.slider_float(f"##depth_{tid}", m.depth, -1.0, 1.0, "%.2f")

                imgui.table_next_column()
                _, m.bipolar = imgui.checkbox(f"##bip_{tid}", m.bipolar)

                imgui.table_next_column()
                _, m.enabled = imgui.checkbox(f"##en_{tid}", m.enabled)

                imgui.table_next_column()
                if imgui.button(f"X##aud_{tid}"):
                    mod_engine.remove_audio_mapping(tid)

            imgui.end_table()

    # =========================================================================
    # TAB 3: Tempo & Preset Shuffle
    # =========================================================================
    def _render_tempo_shuffle_tab(self):
        clock = getattr(self, 'tempo_clock', None)
        shuffler = getattr(self, 'preset_shuffler', None)
        if not clock or not shuffler:
            imgui.text_disabled("Tempo/Shuffler not available.")
            return

        # 1. Master Tempo Section
        imgui.text("Master Musical Clock")
        imgui.separator()

        sources = ["Manual", "Tap", "Audio", "Ableton Link"]
        curr_src_idx = sources.index(clock.source) if clock.source in sources else 0
        imgui.text("Clock Source:")
        imgui.same_line()
        imgui.set_next_item_width(130)
        changed_src, new_src_idx = imgui.combo("##ClkSrc", curr_src_idx, sources)
        if changed_src:
            new_src = sources[new_src_idx]
            clock.source = new_src
            if new_src == "Ableton Link":
                clock.enable_link(True)
            else:
                clock.enable_link(False)

        # BPM Slider & Controls
        imgui.set_next_item_width(140)
        changed_bpm, new_bpm = imgui.slider_float("##BpmVal", clock.bpm, 40.0, 220.0, "%.1f BPM")
        if changed_bpm:
            clock.set_bpm(new_bpm)

        imgui.same_line()
        if imgui.button("/2"):
            clock.set_bpm(clock.bpm / 2.0)
        imgui.same_line()
        if imgui.button("x2"):
            clock.set_bpm(clock.bpm * 2.0)
        imgui.same_line(spacing=15)

        # Tap Tempo Button (styled big)
        imgui.push_style_color(imgui.Col_.button, imgui.ImVec4(0.2, 0.45, 0.7, 1.0))
        if imgui.button("  TAP TEMPO  "):
            clock.tap()
        imgui.pop_style_color()

        # Status for Link / Audio
        if clock.source == "Ableton Link":
            imgui.text_colored(imgui.ImVec4(0.3, 0.9, 0.4, 1.0), f"● Ableton Link Active - {clock.link_peers} peer(s) connected")
        elif clock.source == "Audio":
            bdet = clock.bpm_detector
            lock_label = "Locked" if bdet.is_locked else "Tracking"
            imgui.text(f"Audio Detected BPM: {bdet.estimated_bpm:.1f} (Conf: {bdet.confidence*100:.0f}%) [{lock_label}]")
            imgui.same_line()
            _, bdet.is_locked = imgui.checkbox("Lock BPM", bdet.is_locked)

        # Beat Visual Metronome (4 dots)
        beat_idx = int(clock.beat_count) % 4
        imgui.text("Beat: ")
        for i in range(4):
            imgui.same_line()
            if i == beat_idx:
                color = imgui.ImVec4(1.0, 0.8, 0.2, 1.0) if i == 0 else imgui.ImVec4(0.2, 0.9, 0.3, 1.0)
            else:
                color = imgui.ImVec4(0.3, 0.3, 0.3, 1.0)
            imgui.text_colored(color, "●")

        imgui.separator()

        # 2. Preset Shuffler Section
        imgui.text("Automated Preset Shuffler")

        _, shuffler.enabled = imgui.checkbox("Enable Auto-Shuffle", shuffler.enabled)
        imgui.same_line(spacing=20)
        _, shuffler.hold = imgui.checkbox("Hold / Freeze", shuffler.hold)

        # Mode and Interval
        modes = ["Sequential", "Random", "Shuffle"]
        m_idx = modes.index(shuffler.mode) if shuffler.mode in modes else 0
        imgui.set_next_item_width(120)
        c_m, n_m = imgui.combo("Shuffle Mode", m_idx, modes)
        if c_m:
            shuffler.mode = modes[n_m]

        intervals = [1, 2, 4, 8, 16, 32]
        int_labels = [f"{n} Bar{'s' if n>1 else ''} ({n*4} beats)" for n in intervals]
        i_idx = intervals.index(shuffler.interval_bars) if shuffler.interval_bars in intervals else 2
        imgui.set_next_item_width(150)
        c_i, n_i = imgui.combo("Change Interval", i_idx, int_labels)
        if c_i:
            shuffler.interval_bars = intervals[n_i]

        # Transition Mode
        trans_modes = ["Morph", "Glide", "Cut"]
        t_idx = trans_modes.index(shuffler.transition_mode) if shuffler.transition_mode in trans_modes else 0
        imgui.set_next_item_width(120)
        c_t, n_t = imgui.combo("Transition Mode", t_idx, trans_modes)
        if c_t:
            shuffler.transition_mode = trans_modes[n_t]

        # Live Status & Manual Controls
        app_ref = getattr(self, '_app_ref', None)
        imgui.text_colored(imgui.ImVec4(0.4, 0.8, 1.0, 1.0), f"Current: {shuffler.current_preset_name}")
        imgui.same_line(spacing=20)
        imgui.text(f"Next in: {shuffler.bars_remaining} bar(s)")

        if imgui.button("<< Prev Preset"):
            if app_ref:
                shuffler.trigger_prev(app_ref)
        imgui.same_line()
        if imgui.button("Next Preset >>"):
            if app_ref:
                shuffler.trigger_next(app_ref)
        imgui.same_line()
        if imgui.button("Random Jump"):
            if app_ref:
                shuffler.trigger_random(app_ref)

        # Playlist management
        imgui.separator()
        imgui.text(f"Playlist ({len(shuffler.playlist)} presets):")
        imgui.same_line()
        if imgui.button("Load All Core"):
            shuffler.populate_from_categories(self.config_files_by_category, ["Core"])
        imgui.same_line()
        if imgui.button("Load Core+Custom"):
            shuffler.populate_from_categories(self.config_files_by_category, ["Core", "Custom"])
        imgui.same_line()
        if imgui.button("Clear##Pl"):
            shuffler.clear_playlist()

        # Playlist item list
        if imgui.begin_list_box("##PlaylistItems", imgui.ImVec2(0, 110)):
            for idx, (pname, pcat) in enumerate(shuffler.playlist):
                is_selected = (idx == shuffler.current_index)
                if imgui.selectable(f"{pname} ({pcat})##pl_{idx}", is_selected)[0]:
                    shuffler.current_index = idx
                    if app_ref:
                        shuffler._load_current_preset(app_ref)
            imgui.end_list_box()

    # =========================================================================
    # TAB 4: NDI Output
    # =========================================================================
    def _render_ndi_tab(self):
        ndi = getattr(self, 'ndi_service', None)
        if not ndi:
            imgui.text_disabled("NDI service not available.")
            return

        imgui.text("Network Device Interface (NDI) Video Streaming")
        imgui.separator()

        # Master Stream Toggle
        changed_en, new_en = imgui.checkbox("Enable NDI Stream", ndi.enabled)
        self.render_control_context_menu('toggle.ndi_broadcast', "NDI Broadcast")
        if changed_en:
            ndi.set_enabled(new_en)
            self.state.preferences.ndi_enabled = new_en
            save_preferences(self.state.preferences)

        # Stream Framing / Source View Mode
        source_modes = ["Camera", "World"]
        source_labels = [
            "Interactive Camera (Follows Zoom & Pan)",
            "Fixed World Bounds (Full Simulation World)"
        ]
        curr_src_idx = source_modes.index(ndi.source_mode) if ndi.source_mode in source_modes else 0
        imgui.set_next_item_width(280)
        changed_s, new_s_idx = imgui.combo("Stream Framing", curr_src_idx, source_labels)
        self.render_control_context_menu('cycle.ndi_source_mode', "NDI Source Framing")
        if changed_s:
            ndi.set_source_mode(source_modes[new_s_idx])
            self.state.preferences.ndi_source_mode = source_modes[new_s_idx]
            save_preferences(self.state.preferences)

        # Stream Name
        imgui.set_next_item_width(200)
        changed_name, ndi.stream_name = imgui.input_text("Stream Name", ndi.stream_name)
        if changed_name:
            ndi.set_stream_name(ndi.stream_name)
            self.state.preferences.ndi_stream_name = ndi.stream_name
            save_preferences(self.state.preferences)

        # Aspect Ratio / Resolution Preset
        presets = list(RESOLUTION_PRESETS.keys())
        p_idx = presets.index(ndi.resolution_preset) if ndi.resolution_preset in presets else 0
        imgui.set_next_item_width(200)
        changed_p, new_p_idx = imgui.combo("Format / Aspect", p_idx, presets)
        if changed_p:
            ndi.set_preset(presets[new_p_idx])
            self.state.preferences.ndi_resolution_preset = presets[new_p_idx]
            save_preferences(self.state.preferences)

        # Fit Mode
        fit_modes = ["Fill / Crop", "Fit / Letterbox"]
        f_idx = fit_modes.index(ndi.fit_mode) if ndi.fit_mode in fit_modes else 0
        imgui.set_next_item_width(200)
        changed_f, new_f_idx = imgui.combo("Fit Mode", f_idx, fit_modes)
        self.render_control_context_menu('cycle.ndi_fit_mode', "NDI Fit Mode")
        if changed_f:
            ndi.set_fit_mode(fit_modes[new_f_idx])
            self.state.preferences.ndi_fit_mode = fit_modes[new_f_idx]
            save_preferences(self.state.preferences)

        # Target FPS
        fps_opts = [30, 60]
        curr_fps_idx = fps_opts.index(ndi.target_fps) if ndi.target_fps in fps_opts else 1
        imgui.set_next_item_width(120)
        changed_fps, new_fps_idx = imgui.combo("Target FPS", curr_fps_idx, ["30 FPS", "60 FPS"])
        if changed_fps:
            ndi.target_fps = fps_opts[new_fps_idx]
            if ndi.enabled:
                ndi._open_ndi()

        imgui.separator()

        # Stream Status
        if ndi.enabled:
            status_color = imgui.ImVec4(0.2, 0.9, 0.3, 1.0)
            status_text = f"● BROADCASTING: '{ndi.stream_name}'"
        else:
            status_color = imgui.ImVec4(0.5, 0.5, 0.5, 1.0)
            status_text = "○ Stream Inactive"

        imgui.text_colored(status_color, status_text)
        imgui.text(f"Output Resolution: {ndi.output_width} x {ndi.output_height}")
        imgui.text(f"Actual Framerate: {ndi.actual_fps:.1f} FPS")
        imgui.text(f"Total Frames Sent: {ndi.frames_sent}")
        imgui.text(f"Active Receivers (Studio Monitor / Resolume / OBS): {ndi.num_connections}")
