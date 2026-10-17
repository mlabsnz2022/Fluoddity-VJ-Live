#version 330 core
in vec2 in_position;
in vec2 in_texcoord;
out vec2 v_uv;

void main() {
    gl_Position = vec4(in_position, 0.0, 1.0);
    // Flip Y so OpenGL bottom-left origin matches standard top-left video convention
    v_uv = vec2(in_texcoord.x, 1.0 - in_texcoord.y);
}
