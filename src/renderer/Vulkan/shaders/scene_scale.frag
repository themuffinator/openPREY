#version 450

// r_resolutionScaleMode 2 and 3 for a scaled scene presented at native
// resolution (OpenGL glprogs/resolutionscale.fs and its nearest filter):
// mode 2 reconstructs the low-resolution scene bilinearly and applies a 3x3
// unsharp mask of r_resolutionScaleSharpness; mode 3 shows the nearest scene
// texel. Like temporal_resolve, this procedural pass writes top-down rows.

layout(set = 0, binding = 0) uniform sampler2D currentScene;

layout(std140, set = 6, binding = 0) uniform SceneScaleBlock {
    // xy = inverse scene extent; z = sharpen amount; w = mode (2 or 3).
    vec4 scale;
    // x = the scene image stores bottom-up (OpenGL) rows.
    vec4 flags;
} params;

layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

vec2 StoredUV(vec2 uv) {
    return params.flags.x > 0.5 ? vec2(uv.x, 1.0 - uv.y) : uv;
}

vec3 SampleLowRes(vec2 uv) {
    return texture(currentScene, StoredUV(clamp(uv, vec2(0.0), vec2(1.0)))).rgb;
}

void main() {
    vec2 uv = fragUV;
    if (params.scale.w > 2.5) {
        ivec2 size = textureSize(currentScene, 0);
        ivec2 texel = clamp(ivec2(StoredUV(uv) * vec2(size)), ivec2(0), size - 1);
        outColor = texelFetch(currentScene, texel, 0);
        return;
    }

    vec4 scene = texture(currentScene, StoredUV(uv));
    float sharpenAmount = params.scale.z;
    if (sharpenAmount <= 0.0001) {
        outColor = scene;
        return;
    }

    vec2 texel = params.scale.xy;
    vec3 center = scene.rgb;
    vec3 north = SampleLowRes(uv + vec2(0.0, texel.y));
    vec3 south = SampleLowRes(uv - vec2(0.0, texel.y));
    vec3 east = SampleLowRes(uv + vec2(texel.x, 0.0));
    vec3 west = SampleLowRes(uv - vec2(texel.x, 0.0));
    vec3 northEast = SampleLowRes(uv + vec2(texel.x, texel.y));
    vec3 northWest = SampleLowRes(uv + vec2(-texel.x, texel.y));
    vec3 southEast = SampleLowRes(uv + vec2(texel.x, -texel.y));
    vec3 southWest = SampleLowRes(uv + vec2(-texel.x, -texel.y));

    vec3 blur = (center * 4.0
        + (north + south + east + west) * 2.0
        + (northEast + northWest + southEast + southWest)) * (1.0 / 16.0);

    vec3 sharpened = clamp(center + (center - blur) * sharpenAmount, 0.0, 1.0);
    outColor = vec4(sharpened, scene.a);
}
