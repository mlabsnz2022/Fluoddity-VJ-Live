"""NDI Video Output Service: streams final assembled frames over NDI with aspect ratio selection."""
import time
from fractions import Fraction
from typing import Optional
import numpy as np
import moderngl

# NDI library
try:
    from cyndilib.sender import Sender
    from cyndilib.video_frame import VideoSendFrame
    from cyndilib.wrapper.ndi_structs import FourCC
    HAS_NDI = True
except ImportError:
    Sender = None
    VideoSendFrame = None
    FourCC = None
    HAS_NDI = False

from utilities.gl_helpers import read_shader


RESOLUTION_PRESETS = {
    "16:9 (1920x1080)": (1920, 1080),
    "16:9 (1280x720)": (1280, 720),
    "9:16 (1080x1920)": (1080, 1920),
    "9:16 (720x1280)": (720, 1280),
    "1:1 (1080x1080)": (1080, 1080),
    "1:1 (720x720)": (720, 720),
    "4:5 (1080x1350)": (1080, 1350),
    "4:3 (1440x1080)": (1440, 1080),
    "21:9 (2560x1080)": (2560, 1080),
}


class NdiOutputService:
    """Streams Fluoddity output over NDI network protocol."""

    def __init__(self, ctx: Optional[moderngl.Context] = None):
        self.ctx = ctx
        self.enabled: bool = False
        self.stream_name: str = "Fluoddity"
        self.resolution_preset: str = "16:9 (1920x1080)"
        self.fit_mode: str = "Fill / Crop"  # 'Fill / Crop' or 'Fit / Letterbox'
        self.source_mode: str = "Camera"  # 'Camera' (interactive) or 'World' (fixed world bounds)
        self.target_fps: int = 60

        # Output dimensions
        self.output_width, self.output_height = RESOLUTION_PRESETS[self.resolution_preset]

        # NDI objects
        self._sender = None
        self._video_frame = None

        # GPU resources
        self._target_texture: Optional[moderngl.Texture] = None
        self._fbo: Optional[moderngl.Framebuffer] = None
        self._program: Optional[moderngl.Program] = None
        self._vao: Optional[moderngl.VertexArray] = None

        # Stats
        self.frames_sent: int = 0
        self.num_connections: int = 0
        self.actual_fps: float = 0.0
        self._last_fps_calc = time.time()
        self._fps_counter = 0

        if ctx:
            self.init_gpu(ctx)

    def init_gpu(self, ctx: moderngl.Context):
        self.ctx = ctx
        vert_src = read_shader('shaders/ndi_fit.vert')
        frag_src = read_shader('shaders/ndi_fit.frag')

        self._program = self.ctx.program(
            vertex_shader=vert_src,
            fragment_shader=frag_src
        )

        quad_vertices = np.array([
            -1.0, -1.0,  0.0, 0.0,
             1.0, -1.0,  1.0, 0.0,
             1.0,  1.0,  1.0, 1.0,
            -1.0,  1.0,  0.0, 1.0
        ], dtype=np.float32)
        quad_indices = np.array([0, 1, 2, 2, 3, 0], dtype=np.uint32)

        vbo = self.ctx.buffer(quad_vertices.tobytes())
        ibo = self.ctx.buffer(quad_indices.tobytes())
        self._vao = self.ctx.vertex_array(
            self._program,
            [(vbo, '2f 2f', 'in_position', 'in_texcoord')],
            ibo
        )

    def set_preset(self, preset_name: str):
        if preset_name in RESOLUTION_PRESETS:
            self.resolution_preset = preset_name
            w, h = RESOLUTION_PRESETS[preset_name]
            if (w, h) != (self.output_width, self.output_height):
                self.output_width, self.output_height = w, h
                self._recreate_resources()

    def set_fit_mode(self, fit_mode: str):
        if fit_mode in ["Fill / Crop", "Fit / Letterbox"]:
            self.fit_mode = fit_mode

    def set_source_mode(self, source_mode: str):
        if source_mode in ["Camera", "World"]:
            self.source_mode = source_mode

    def set_stream_name(self, stream_name: str):
        if stream_name and stream_name != self.stream_name:
            self.stream_name = stream_name
            if self.enabled:
                self._open_ndi()

    def set_enabled(self, enabled: bool):
        if enabled == self.enabled:
            return
        self.enabled = enabled
        if self.enabled:
            self._open_ndi()
        else:
            self._close_ndi()

    def _open_ndi(self):
        if not HAS_NDI:
            print("[NDI] cyndilib is not available.")
            self.enabled = False
            return

        self._close_ndi()
        try:
            self._sender = Sender(self.stream_name)
            self._video_frame = VideoSendFrame()
            self._video_frame.set_resolution(self.output_width, self.output_height)
            self._video_frame.set_frame_rate(Fraction(self.target_fps, 1))
            self._video_frame.set_fourcc(FourCC.RGBA)
            self._sender.set_video_frame(self._video_frame)
            self._sender.open()
            print(f"[NDI] Output started: '{self.stream_name}' at {self.output_width}x{self.output_height} @ {self.target_fps}fps")
        except Exception as e:
            print(f"[NDI] Failed to open sender: {e}")
            self.enabled = False

    def _close_ndi(self):
        if self._sender:
            try:
                self._sender.close()
            except Exception:
                pass
            self._sender = None
            self._video_frame = None
        self.num_connections = 0

    def _recreate_resources(self):
        if self._target_texture:
            self._target_texture.release()
            self._target_texture = None
        if self._fbo:
            self._fbo.release()
            self._fbo = None
        if self.enabled:
            self._open_ndi()

    def process_frame(self, assembled_texture: moderngl.Texture):
        """Resample assembled texture to NDI target resolution and send asynchronously."""
        if not self.enabled or not self._sender or assembled_texture is None:
            return

        # Ensure FBO exists at desired resolution
        if self._fbo is None or self._target_texture is None or self._target_texture.size != (self.output_width, self.output_height):
            self._target_texture = self.ctx.texture((self.output_width, self.output_height), 4, dtype='f1')
            self._fbo = self.ctx.framebuffer([self._target_texture])

        # Blit & fit into FBO
        self._fbo.use()
        self.ctx.viewport = (0, 0, self.output_width, self.output_height)
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        assembled_texture.use(location=0)
        self._program['src_tex'].value = 0
        self._program['src_size'].value = assembled_texture.size
        self._program['dst_size'].value = (self.output_width, self.output_height)
        self._program['fit_mode'].value = 0 if self.fit_mode == "Fill / Crop" else 1

        self._vao.render()

        # Read back RGBA bytes from FBO as writable buffer
        raw_bytes = bytearray(self._fbo.read(components=4, dtype='f1'))

        # Send asynchronously via NDI
        try:
            self._sender.write_video_async(raw_bytes)
            self.frames_sent += 1
            self._fps_counter += 1
        except Exception as e:
            print(f"[NDI] Send error: {e}")

        # Update stats
        now = time.time()
        if now - self._last_fps_calc >= 1.0:
            self.actual_fps = self._fps_counter / (now - self._last_fps_calc)
            self._fps_counter = 0
            self._last_fps_calc = now
            try:
                self.num_connections = self._sender.get_num_connections(0)
            except Exception:
                pass

    def cleanup(self):
        self._close_ndi()
        if self._target_texture:
            self._target_texture.release()
        if self._fbo:
            self._fbo.release()
        if self._program:
            self._program.release()
        if self._vao:
            self._vao.release()
