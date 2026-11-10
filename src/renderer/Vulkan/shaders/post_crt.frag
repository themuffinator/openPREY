#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"

// CRT monitor effect over the finished frame. A port of
// content/baseoq4/pak0/glprogs/crt.fs, which RB_ApplyCRTToBackBuffer draws on
// the OpenGL backend.
//
// The back-buffer copy is stored bottom-up like an OpenGL texture, so uv uses
// OpenGL's orientation (0,0 = bottom-left). Vulkan's gl_FragCoord has a
// top-left origin; fragCoordGL converts it so the scanline and phosphor-slot
// row parity and the shimmer phase match OpenGL pixel for pixel.

layout(set = 0, binding = 0) uniform sampler2D Scene;

layout(std140, set = 6, binding = 0) uniform CRTBlock {
    vec4 texel;		// x: 1/width, y: 1/height, z: framebuffer height, w: timeSeconds
    vec4 crt;		// x: amount, y: scanline strength, z: mask strength, w: curvature
    vec4 chroma;	// x: chromatic aberration
} block;

layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

vec2 fragCoordGL;

vec2 WarpUV( vec2 uv ) {
    float curvature = block.crt.w;
    vec2 centered = uv * 2.0 - 1.0;
    vec2 squared = centered * centered;
    centered *= 1.0 + squared.yx * ( curvature * 1.6 );
    centered.x *= 1.0 + squared.y * ( curvature * 0.25 );
    centered.y *= 1.0 + squared.x * ( curvature * 0.20 );
    return centered * 0.5 + 0.5;
}

float ScreenMask( vec2 uv ) {
    vec2 edge = min( uv, 1.0 - uv );
    float maskX = smoothstep( 0.0, 0.018, edge.x );
    float maskY = smoothstep( 0.0, 0.018, edge.y );
    return maskX * maskY;
}

vec3 SampleHorizontalBeam( vec2 uv ) {
    vec2 texel = vec2( block.texel.x, 0.0 );
    vec3 sample0 = texture( Scene, uv - texel * 2.0 ).rgb;
    vec3 sample1 = texture( Scene, uv - texel ).rgb;
    vec3 sample2 = texture( Scene, uv ).rgb;
    vec3 sample3 = texture( Scene, uv + texel ).rgb;
    vec3 sample4 = texture( Scene, uv + texel * 2.0 ).rgb;
    return sample0 * 0.08 + sample1 * 0.22 + sample2 * 0.40 + sample3 * 0.22 + sample4 * 0.08;
}

vec3 SampleCRTColor( vec2 uv ) {
    float chromaticAberration = block.chroma.x;
    vec3 beam = SampleHorizontalBeam( uv );
    vec2 radial = uv - 0.5;
    float spread = 1.0 + length( radial ) * 2.25;
    vec2 chroma = vec2(
        chromaticAberration * block.texel.x * spread,
        chromaticAberration * block.texel.y * 0.35 * spread );

    vec3 chromaColor;
    chromaColor.r = texture( Scene, uv + chroma ).r;
    chromaColor.g = beam.g;
    chromaColor.b = texture( Scene, uv - chroma ).b;

    float mixFactor = clamp( chromaticAberration * 0.35, 0.0, 0.35 );
    return mix( beam, chromaColor, mixFactor );
}

float ScanlineFactor( float luma ) {
    float phase = fragCoordGL.y * 3.14159265 + sin( block.texel.w * 7.0 ) * 0.35;
    float wave = 0.5 + 0.5 * cos( phase );
    wave *= wave;

    float darkFloor = 0.22 + luma * 0.35;
    float lineValue = mix( darkFloor, 1.0, wave );
    return mix( 1.0, lineValue, block.crt.y );
}

vec3 PhosphorMask( void ) {
    float column = mod( floor( fragCoordGL.x ), 3.0 );
    vec3 triad;
    if ( column < 0.5 ) {
        triad = vec3( 1.18, 0.80, 0.80 );
    } else if ( column < 1.5 ) {
        triad = vec3( 0.80, 1.18, 0.80 );
    } else {
        triad = vec3( 0.80, 0.80, 1.18 );
    }

    float slot = ( mod( floor( fragCoordGL.y ), 2.0 ) < 0.5 ) ? 1.0 : 0.94;
    return mix( vec3( 1.0 ), triad * slot, block.crt.z );
}

void main() {
    fragCoordGL = vec2( gl_FragCoord.x, CanonicalWindowY(block.texel.z) );

    vec2 baseUV = vec2( fragUV.x, 1.0 - fragUV.y );
    vec4 originalSample = texture( Scene, baseUV );
    vec2 warpedUV = WarpUV( baseUV );
    float screenMask = ScreenMask( warpedUV );

    if ( screenMask <= 0.0 ) {
        outColor = vec4( 0.0, 0.0, 0.0, originalSample.a );
        return;
    }

    vec3 crtColor = SampleCRTColor( warpedUV );
    float luma = dot( crtColor, vec3( 0.2126, 0.7152, 0.0722 ) );
    crtColor *= ScanlineFactor( luma );
    crtColor *= PhosphorMask();

    float edge = dot( warpedUV * 2.0 - 1.0, warpedUV * 2.0 - 1.0 );
    float vignette = clamp( 1.0 - edge * 0.22, 0.0, 1.0 );
    float shimmer = 0.985 + 0.015 * sin( fragCoordGL.y * 0.35 + block.texel.w * 11.0 );
    crtColor *= mix( 1.0, vignette * shimmer, 0.85 );
    crtColor *= screenMask;

    vec3 finalColor = mix( originalSample.rgb, crtColor, block.crt.x );
    outColor = vec4( clamp( finalColor, 0.0, 1.0 ), originalSample.a );
}
