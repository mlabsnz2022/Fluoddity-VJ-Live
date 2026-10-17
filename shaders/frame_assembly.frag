#version 330 core
uniform sampler2D input_frame;
uniform sampler2D accumulation_buffer;
uniform sampler2D field_texture;                    // Force/Strafe field (.xy=force, .zw=strafe)
uniform bool advanced_drawing_resources_initialized; // True when field_texture has valid data
uniform float draw_target_overlay_opacity; // Opacity of field color overlay (0-1)
uniform bool is_first_frame;
uniform bool final_sample;
uniform int view_mode;  // 0=can, 1=cam_brush, 2=tiled, 3=force, 4=strafe
uniform float screen_aspect;        // Screen width/height for aspect-correct circles
uniform float BRIGHTNESS;           // Global brightness multiplier (applied before gamma)
uniform float EXPOSURE;//undo gamma from last frame and blend it with this frame, allows long exposure effect
uniform float TONEMAP_SOFTNESS;    // Asinh stretch parameter (higher = more highlight compression)
#define BRIGHTNESS_CONSTANT (3.*BRIGHTNESS)
uniform float INK_WEIGHT;           // Watercolor mode: controls optical density in exp()
uniform bool WATERCOLOR_MODE;       // Whether to use watercolor rendering

// Camera state for screen-to-canvas UV conversion
uniform vec2 camera_position;       // Camera position in world space
uniform float camera_zoom;          // Camera zoom level

// Tiling mode parameters
uniform bool tiling_mode_enabled;   // Whether tiling mode is active
uniform vec2 view_min;              // Entity-space minimum of view rectangle
uniform vec2 view_max;              // Entity-space maximum of view rectangle
uniform vec2 tiling_scale;          // Converts frame_assembly world_pos to entity space
uniform vec2 canvas_resolution;     // Canvas pixel dimensions (width, height)

// Tiling margin: controls how much particles are shrunk inward to allow sprite overhang.
// Must match the value in cam_brush.vert. Smaller = more margin for edge blending.
const float TILING_MARGIN = 0.993;

in vec2 uv;
out vec4 fragColor;

// TOTAL_SAMPLES placeholder - will be replaced by Python during shader creation
const int TOTAL_SAMPLES = {total_samples};

vec3 hsv2rgb(vec3 c)
{
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// Convert screen UV coordinates to canvas texture coordinates
// Screen UV (0,0) to (1,1) -> world space -> canvas texture coords
vec2 screen_to_canvas_uv(vec2 screen_uv) {
    // Screen UV to normalized device coordinates (-1 to 1)
    vec2 ndc = screen_uv * 2.0 - 1.0;
    // Add camera position to get world space position
    vec2 world_pos = ndc*camera_zoom + camera_position*vec2(1,-1);
    // Apply aspect ratio correction
    world_pos.x*=screen_aspect;
    // World space to canvas texture coords: divide by 2 and add 0.5
    return (world_pos/2.+.5);
}

// Convert canvas texture coordinates to screen UV coordinates
// Inverse of screen_to_canvas_uv
vec2 canvas_uv_to_screen(vec2 canvas_uv) {
    // Canvas texture coords to world space: multiply by 2 and subtract 1
    vec2 world_pos = canvas_uv * 2.0 - 1.0;
    // Remove aspect ratio correction
    world_pos.x /= screen_aspect;
    // Subtract camera position to get NDC (with flipped y)
    vec2 ndc = (world_pos - camera_position*vec2(1,-1)) / camera_zoom;
    // NDC to screen UV coordinates (0 to 1)
    return ndc * 0.5 + 0.5;
}

vec2 safenorm(vec2 n){
    float l = length(n);
    return l>0?n/l:vec2(0);
}
vec3 safenorm(vec3 n){
    float l = length(n);
    return l>0?n/l:vec3(0);
}
// Tiling mode: sample color with edge blending for seamless tiling.
// Handles particles whose sprites hang over the edge of the canonical tile.
vec3 sample_tiled_color(vec2 screen_uv) {
    // Convert screen UV to entity space using tiling_scale
    vec2 ndc = screen_uv * 2.0 - 1.0;
    vec2 world_pos = ndc * camera_zoom + camera_position * vec2(1, -1);
    world_pos *= tiling_scale;

    // Per-axis cell size (area-preserving entity bounds)
    float ca = canvas_resolution.x / canvas_resolution.y;
    vec2 cell_size = vec2(2.0 * sqrt(ca), 2.0 / sqrt(ca));

    // Extract canonical position (which particle lives here?)
    vec2 p = mod(world_pos + cell_size * 0.5, cell_size) - cell_size * 0.5;

    // Compute the SAME n_min the vertex shader used
    vec2 n_min = ceil((view_min - p) / cell_size);
    vec2 n_max = floor((view_max - p) / cell_size);

    // Check if this particle was rendered (with epsilon for floating point precision)
    const float epsilon = 0.0001;
    if (n_min.x > n_max.x + epsilon || n_min.y > n_max.y + epsilon) {
        // This particle was culled
        return vec3(0.0);
    }

    // This particle was rendered - find where
    vec2 rendered_world_pos = p + n_min * cell_size;

    // Convert back to screen UV (reverse of the world_pos calculation above)
    rendered_world_pos /= tiling_scale;
    vec2 rendered_ndc = (rendered_world_pos - camera_position * vec2(1, -1)) / camera_zoom;
    rendered_ndc *= TILING_MARGIN;
    vec2 sample_uv = rendered_ndc * 0.5 + 0.5;

    // Tile size in sample_uv space (how far to offset for opposite edge)
    vec2 tile_size_uv = cell_size * TILING_MARGIN / (tiling_scale * camera_zoom);

    // Sample primary location
    vec3 color = texture(input_frame, sample_uv).rgb;

    // ===== SCREENSPACE SEAM DETECTION =====
    // The screenspace seam is where n_min changes (discontinuity in the p-to-sample_uv mapping).
    vec2 p_seam = mod(view_min + cell_size * 0.5, cell_size) - cell_size * 0.5;

    // Distance from p to the seam (in p-space, wrapped to cell_size)
    vec2 dist_to_seam = p - p_seam;
    dist_to_seam = mod(dist_to_seam + cell_size * 0.5, cell_size) - cell_size * 0.5;

    // Margin threshold: how close to the seam triggers edge blending
    float margin_threshold = 1.0 - TILING_MARGIN;

    // At the seam, crossing from negative to positive dist causes sample_uv to DECREASE.
    // So: if dist > 0, we're at lower sample_uv, need to sample from higher (add tile_size_uv)
    //     if dist < 0, we're at higher sample_uv, need to sample from lower (subtract tile_size_uv)

    // Skip edge blending if tile is larger than screen (seam is offscreen, no tiling visible)
    bool seam_onscreen_x = tile_size_uv.x < 1.0;
    bool seam_onscreen_y = tile_size_uv.y < 1.0;

    bool near_seam_pos_x = seam_onscreen_x && dist_to_seam.x > 0.0 && dist_to_seam.x < margin_threshold;
    bool near_seam_neg_x = seam_onscreen_x && dist_to_seam.x < 0.0 && dist_to_seam.x > -margin_threshold;
    bool near_seam_pos_y = seam_onscreen_y && dist_to_seam.y > 0.0 && dist_to_seam.y < margin_threshold;
    bool near_seam_neg_y = seam_onscreen_y && dist_to_seam.y < 0.0 && dist_to_seam.y > -margin_threshold;

    // X-axis edge blending
    if (near_seam_pos_x) {
        // Right of seam (lower sample_uv): sample from left of seam (higher sample_uv)
        color += texture(input_frame, sample_uv + vec2(tile_size_uv.x, 0.0)).rgb;
    } else if (near_seam_neg_x) {
        // Left of seam (higher sample_uv): sample from right of seam (lower sample_uv)
        color += texture(input_frame, sample_uv - vec2(tile_size_uv.x, 0.0)).rgb;
    }

    // Y-axis edge blending
    if (near_seam_pos_y) {
        color += texture(input_frame, sample_uv + vec2(0.0, tile_size_uv.y)).rgb;
    } else if (near_seam_neg_y) {
        color += texture(input_frame, sample_uv - vec2(0.0, tile_size_uv.y)).rgb;
    }

    // Corner blending: if both x and y are in margin zones, also sample diagonal
    if ((near_seam_pos_x || near_seam_neg_x) && (near_seam_pos_y || near_seam_neg_y)) {
        vec2 corner_offset = vec2(
            near_seam_pos_x ? tile_size_uv.x : -tile_size_uv.x,
            near_seam_pos_y ? tile_size_uv.y : -tile_size_uv.y
        );
        color += texture(input_frame, sample_uv + corner_offset).rgb;
    }

    return color;
}

void main() {
    // Sample the input frame (tiling mode handles edge blending internally)
    vec3 current_color;
    if (tiling_mode_enabled) {
        current_color = sample_tiled_color(uv);
    } else if (view_mode == 4) {
        // Strafe field view: use .zw channels as the vector field (displayed via .xy)
        vec4 field_sample = texture(input_frame, uv);
        current_color = vec3(field_sample.z, field_sample.w, 0.0);
    } else {
        current_color = texture(input_frame, uv).rgb;
    }

    // In watercolor mode, convert from log-space optical density to linear transmission
    if (WATERCOLOR_MODE) {
        // INK_WEIGHT controls optical density - higher = darker/more opaque
        #define INK_CONSTANT 10
        current_color = exp(INK_WEIGHT*INK_CONSTANT * current_color);
    }
    // Divide by number of samples (for averaging)
    current_color /= float(TOTAL_SAMPLES);
    
    // Add to or replace accumulation
    if (is_first_frame) {
        vec3 previous_frame = texture(accumulation_buffer, uv).rgb;
        if (isnan(previous_frame.r) || isinf(previous_frame.r) ||
            isnan(previous_frame.g) || isinf(previous_frame.g) ||
            isnan(previous_frame.b) || isinf(previous_frame.b)) {
            previous_frame = vec3(0.0);
        }
        float previous_len = length(previous_frame);
        float sinh_arg = min(previous_len * TONEMAP_SOFTNESS, 85.0);
        previous_frame = safenorm(previous_frame) * sinh(sinh_arg) / TONEMAP_SOFTNESS;
        previous_frame /= max(BRIGHTNESS_CONSTANT, 1e-4);
        float exp_val = clamp(EXPOSURE, 0.0, 1.0);
        fragColor = vec4(mix(current_color, previous_frame, exp_val), 1.0);
    } else {
        vec3 previous_accumulation = texture(accumulation_buffer, uv).rgb;
        if (isnan(previous_accumulation.r) || isinf(previous_accumulation.r) ||
            isnan(previous_accumulation.g) || isinf(previous_accumulation.g) ||
            isnan(previous_accumulation.b) || isinf(previous_accumulation.b)) {
            previous_accumulation = vec3(0.0);
        }
        float exp_val = clamp(EXPOSURE, 0.0, 1.0);
        fragColor = vec4(previous_accumulation + (1.0 - exp_val) * current_color, 1.0);
    }

    // Apply gamma correction only on final sample (AFTER accumulation)
    if (final_sample) {
        //if we are in canvas, brush, or field view, we must interpret raw texture before gamma correction and display:
        if(view_mode == 0 || view_mode == 3 || view_mode == 4){
            fragColor.xyz = 8*hsv2rgb(vec3(atan(fragColor.y,fragColor.x)/2./3.1415,.75,length(fragColor.xy)));
        }
        // Apply brightness multiplier before gamma correction
        if (isnan(fragColor.r) || isinf(fragColor.r) ||
            isnan(fragColor.g) || isinf(fragColor.g) ||
            isnan(fragColor.b) || isinf(fragColor.b)) {
            fragColor.xyz = vec3(0.0);
        }
        fragColor.xyz *= BRIGHTNESS_CONSTANT;
        float len = length(fragColor.xyz);
        if (len > 0.0) {
            float scaled = len * TONEMAP_SOFTNESS;
            float stretch = (scaled > 1e4) ? log(2.0 * scaled) / (len * TONEMAP_SOFTNESS) : asinh(scaled) / (len * TONEMAP_SOFTNESS);
            fragColor.xyz *= stretch;
        }
        if (isnan(fragColor.r) || isinf(fragColor.r) ||
            isnan(fragColor.g) || isinf(fragColor.g) ||
            isnan(fragColor.b) || isinf(fragColor.b)) {
            fragColor.xyz = vec3(0.0);
        }

        //conditionally draw field overlay
        //CURRENTLY TURNED OFF. MAYBE INCLUDE LATER
        if(advanced_drawing_resources_initialized&& draw_target_overlay_opacity>0.0 && (view_mode==1||view_mode==2)){
            vec2 field_uv = screen_to_canvas_uv(uv);
            vec4 field = vec4(0);
            if(tiling_mode_enabled||clamp(field_uv,vec2(0),vec2(1))==field_uv){
                field = texture(field_texture,field_uv);
            }
            vec3 force_col = 8*hsv2rgb(vec3(atan(field.y,field.x)/2./3.1415,.75,length(field.xy)));
            vec3 strafe_col = 8*hsv2rgb(vec3(atan(field.w,field.z)/2./3.1415,.75,length(field.zw)));
            fragColor.xyz +=draw_target_overlay_opacity*(force_col+strafe_col);
        }
    }
}
