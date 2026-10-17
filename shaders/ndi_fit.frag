#version 330 core
in vec2 v_uv;
out vec4 fragColor;

uniform sampler2D src_tex;
uniform vec2 src_size;
uniform vec2 dst_size;
uniform int fit_mode; // 0 = Fill / Crop, 1 = Fit / Letterbox

void main() {
    float src_aspect = src_size.x / max(1.0, src_size.y);
    float dst_aspect = dst_size.x / max(1.0, dst_size.y);

    vec2 uv = v_uv;

    if (fit_mode == 0) {
        // Fill / Crop
        if (src_aspect > dst_aspect) {
            float scale_x = dst_aspect / src_aspect;
            uv.x = (uv.x - 0.5) * scale_x + 0.5;
        } else {
            float scale_y = src_aspect / dst_aspect;
            uv.y = (uv.y - 0.5) * scale_y + 0.5;
        }
        fragColor = texture(src_tex, uv);
    } else {
        // Fit / Letterbox
        if (src_aspect > dst_aspect) {
            float scale_y = dst_aspect / src_aspect;
            uv.y = (uv.y - 0.5) * scale_y + 0.5;
            if (uv.y < 0.0 || uv.y > 1.0) {
                fragColor = vec4(0.0, 0.0, 0.0, 1.0);
                return;
            }
        } else {
            float scale_x = src_aspect / dst_aspect;
            uv.x = (uv.x - 0.5) * scale_x + 0.5;
            if (uv.x < 0.0 || uv.x > 1.0) {
                fragColor = vec4(0.0, 0.0, 0.0, 1.0);
                return;
            }
        }
        fragColor = texture(src_tex, uv);
    }
}
