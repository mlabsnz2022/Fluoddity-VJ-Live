#version 330 core
in vec2 texcoord;
uniform sampler2D view_tex;
out vec4 fragColor;

uniform vec2 window_size;
uniform float screen_aspect;
uniform vec2 mouse_screen_coords;
uniform float TRAIL_DRAW_RADIUS;
uniform float camera_zoom;
uniform vec2 canvas_resolution;
uniform bool PARAMETER_SWEEP_MODE;
uniform vec2 sweep_reticle_pos;
uniform bool sweep_reticle_visible;
uniform bool WATERCOLOR_MODE;

//#define KAL 1
#ifdef KAL
void pR(inout vec2 p, float a) {
	p = cos(a)*p + sin(a)*vec2(p.y, -p.x);
}
//space fold on the position
void kalTransform(inout vec2 pos,inout vec2 vel){
    float wedge = 3.1415926*2/3.;
    float old_angle = atan(pos.y,pos.x);
    float new_angle = mod(old_angle+wedge/2.,wedge)-wedge/2.;//new angle is restricted to -wedge/2, wedge/2
    pR(pos,old_angle-new_angle);
    pR(vel,old_angle-new_angle);
    if(pos.y<0){
        pos = reflect(pos,vec2(0,1));
        vel = reflect(vel,vec2(0,1));
    }
}
#endif

void main() {
    vec2 uv = texcoord;
    #ifdef KAL
    uv=uv*2-1;
    vec2 dum=vec2(0);
    kalTransform(uv,dum);
    uv=(uv+1)/2.;
    #endif
    fragColor = texture(view_tex, uv);

    vec2 screen_uv = (window_size.x > 0.0 && window_size.y > 0.0) ? (gl_FragCoord.xy / window_size) : uv;
    float aspect = (screen_aspect > 0.0) ? screen_aspect : ((window_size.y > 0.0) ? (window_size.x / window_size.y) : 1.0);

    // Sweep reticle overlay
    if (PARAMETER_SWEEP_MODE && sweep_reticle_visible) {
        vec2 sweep_gl = vec2(sweep_reticle_pos.x, 1.0 - sweep_reticle_pos.y);
        vec2 s_delta = screen_uv - sweep_gl;
        s_delta.x *= aspect;
        float s_dist = length(s_delta);
        float inner_radius = 0.02;
        float outer_radius = 0.03;
        float line_thickness = 0.004;
        float crosshair_length = 0.05;
        float s_ring = smoothstep(inner_radius - line_thickness, inner_radius, s_dist)
                     - smoothstep(outer_radius, outer_radius + line_thickness, s_dist);
        float cross_x = step(abs(s_delta.y), line_thickness)
                      * step(outer_radius, abs(s_delta.x))
                      * step(abs(s_delta.x), crosshair_length);
        float cross_y = step(abs(s_delta.x), line_thickness)
                      * step(outer_radius, abs(s_delta.y))
                      * step(abs(s_delta.y), crosshair_length);
        float sweep_val = max(s_ring, max(cross_x, cross_y));
        if (sweep_val > 0.0) {
            vec3 reticle_color = WATERCOLOR_MODE ? vec3(0.0) : vec3(1.0);
            fragColor.rgb = mix(fragColor.rgb, reticle_color, sweep_val * 0.8);
        }
    }

    // Trail draw circle overlay (UI cursor only on screen, does not glow or feed into simulation)
    if (TRAIL_DRAW_RADIUS > 0.0) {
        vec2 mouse_gl = vec2(mouse_screen_coords.x, 1.0 - mouse_screen_coords.y);
        vec2 delta = screen_uv - mouse_gl;
        delta.x *= aspect;
        float dist = length(delta);

        float min_dim = min(canvas_resolution.x, canvas_resolution.y);
        float max_dim = max(canvas_resolution.x, canvas_resolution.y);
        float aspect_shrink = (max_dim > 0.0) ? sqrt(min_dim / max_dim) : 1.0;
        if (canvas_resolution.x > canvas_resolution.y) {
            aspect_shrink *= 4.0 / 3.0;
        }
        float zoom = max(camera_zoom, 0.001);
        float radius = aspect_shrink * 2.0 * TRAIL_DRAW_RADIUS / zoom;
        float line_thickness = 0.003;

        float ring = smoothstep(radius - line_thickness, radius, dist)
                   - smoothstep(radius, radius + line_thickness, dist);
        if (ring > 0.0) {
            vec3 ring_color = WATERCOLOR_MODE ? vec3(0.0) : vec3(1.0);
            fragColor.rgb = mix(fragColor.rgb, ring_color, ring * 0.7);
        }
    }
}