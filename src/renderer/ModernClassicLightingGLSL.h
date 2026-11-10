// Copyright (C) 2026 DarkMatter Productions
// Fixed classic interactions accumulated before the PBR scene's linear decode.
#ifndef __MODERN_CLASSIC_LIGHTING_GLSL_H__
#define __MODERN_CLASSIC_LIGHTING_GLSL_H__

static const char *modernClassicLightingVertex = R"GLSL(#version 330
layout(location = 0) in vec3 attr_Position;
layout(location = 3) in vec4 attr_Color;
layout(location = 8) in vec2 attr_TexCoord0;
layout(location = 9) in vec3 attr_Tangent0;
layout(location = 10) in vec3 attr_Tangent1;
layout(location = 11) in vec3 attr_Normal;
uniform mat4 uModelViewProjection;
uniform vec4 uFrameJitter;
uniform vec4 uClassicParams[15];
out vec2 vBumpUV;
out vec2 vDiffuseUV;
out vec2 vSpecularUV;
out vec4 vProjection;
out float vFalloff;
out vec3 vLight;
out vec3 vHalf;
out vec3 vColor;
invariant gl_Position;
vec3 TangentVector(vec3 v) {
    return vec3(dot(attr_Tangent0, v), dot(attr_Tangent1, v), dot(attr_Normal, v));
}
void main() {
    vec4 p = vec4(attr_Position, 1.0);
    vec4 uv = vec4(attr_TexCoord0, 0.0, 1.0);
    vec3 l = uClassicParams[0].xyz - p.xyz;
    vec3 v = uClassicParams[1].xyz - p.xyz;
    vLight = TangentVector(l);
    vHalf = TangentVector(l * inversesqrt(max(dot(l, l), 1e-8)) + v * inversesqrt(max(dot(v, v), 1e-8)));
    vBumpUV = vec2(dot(uv, uClassicParams[6]), dot(uv, uClassicParams[7]));
    vDiffuseUV = vec2(dot(uv, uClassicParams[8]), dot(uv, uClassicParams[9]));
    vSpecularUV = vec2(dot(uv, uClassicParams[10]), dot(uv, uClassicParams[11]));
    vProjection = vec4(dot(p, uClassicParams[2]), dot(p, uClassicParams[3]), 0.0, dot(p, uClassicParams[4]));
    vFalloff = dot(p, uClassicParams[5]);
    vColor = attr_Color.rgb * uClassicParams[14].x + vec3(uClassicParams[14].y);
    gl_Position = uModelViewProjection * vec4(attr_Position, 1.0) + uFrameJitter;
}
)GLSL";

static const char *modernClassicLightingFragment = R"GLSL(#version 330
uniform vec4 uClassicParams[15];
uniform sampler2D uBump;
uniform sampler2D uFalloff;
uniform sampler2D uProjection;
uniform sampler2D uDiffuse;
uniform sampler2D uSpecular;
uniform samplerCube uNormalizationCube;
in vec2 vBumpUV;
in vec2 vDiffuseUV;
in vec2 vSpecularUV;
in vec4 vProjection;
in float vFalloff;
in vec3 vLight;
in vec3 vHalf;
in vec3 vColor;
layout(location = 0) out vec4 out_Color;
vec3 SafeNormalize(vec3 v) { return v * inversesqrt(max(dot(v, v), 1e-8)); }
void main() {
    vec4 bump = texture(uBump, vBumpUV);
    vec3 n = vec3(bump.a, bump.g, bump.b) * 2.0 - 1.0;
    float lambert = max(dot(texture(uNormalizationCube, vLight).rgb * 2.0 - 1.0, n), 0.0);
    float specular = clamp(dot(SafeNormalize(vHalf), n) * 4.0 - 3.0, 0.0, 1.0);
    specular = specular * specular * 2.0;
    vec3 lighting = textureProj(uProjection, vProjection).rgb * texture(uFalloff, vec2(vFalloff, 0.5)).rgb * lambert;
    vec3 diffuse = texture(uDiffuse, vDiffuseUV).rgb * uClassicParams[12].rgb;
    vec3 highlight = texture(uSpecular, vSpecularUV).rgb * uClassicParams[13].rgb * specular;
    out_Color = vec4((diffuse + highlight) * lighting * vColor, 0.0);
}
)GLSL";

#endif
