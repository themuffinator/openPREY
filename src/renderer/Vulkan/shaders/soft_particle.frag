#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"

// Soft particles: a BSE sprite fades out where it meets the opaque scene
// behind it. A port of content/baseoq4/pak0/glprogs/soft_particle.fs, which
// RB_TryDrawSoftParticleStage draws on the OpenGL backend. gui.vert supplies
// the texture coordinate and tex-independent colour (vertex colour factor
// times the stage colour), so particle = texture * fragColor is OpenGL's
// texture2D( ParticleTexture ) * stageColor * VertexColorFactor().
//
// SceneDepth is the _currentDepth capture, stored bottom-up like an OpenGL
// texture, and the Vulkan clip-z fixup keeps depth values identical to
// OpenGL's. Vulkan's gl_FragCoord has a top-left origin, so its y is flipped
// into OpenGL's window space before it indexes the capture.

layout(set = 0, binding = 0) uniform sampler2D ParticleTexture;
layout(set = 1, binding = 0) uniform sampler2D SceneDepth;

layout(std140, set = 6, binding = 0) uniform SoftParticleBlock {
    vec4 depthInfo;			// xy: depthProjection (P[10], P[14]), z: fade distance, w: additive blend
    vec4 viewInfo;			// xy: viewport origin (OpenGL window space), zw: 1 / depth texture size
    vec4 framebuffer;		// x: framebuffer height
} block;

#define depthProjection		block.depthInfo.xy
#define fadeDistance		block.depthInfo.z
#define additiveBlend		block.depthInfo.w
#define viewportOrigin		block.viewInfo.xy
#define invDepthTexSize		block.viewInfo.zw

layout(location = 0) in vec2 fragTexCoord;
layout(location = 1) in vec4 fragColor;
layout(location = 0) out vec4 outColor;

const float COVERAGE_EPSILON = 0.00001;

float ViewSpaceZFromDepth( float depth ) {
	float ndcDepth = depth * 2.0 - 1.0;
	float denom = ndcDepth + depthProjection.x;
	if ( abs( denom ) < 0.00001 ) {
		denom = ( denom < 0.0 ) ? -0.00001 : 0.00001;
	}
	return ( -depthProjection.y ) / denom;
}

void main() {
	vec4 particle = texture( ParticleTexture, fragTexCoord ) * fragColor;
	float particleCoverage = max( particle.a, max( max( particle.r, particle.g ), particle.b ) );
	if ( particleCoverage <= COVERAGE_EPSILON ) {
		discard;
	}

	vec2 fragCoordGL = vec2( gl_FragCoord.x, CanonicalWindowY(block.framebuffer.x) );
	vec2 depthUv = ( fragCoordGL - viewportOrigin ) * invDepthTexSize;
	float fade = 1.0;

	if ( depthUv.x >= 0.0 && depthUv.y >= 0.0 && depthUv.x <= 1.0 && depthUv.y <= 1.0 ) {
		float sceneDepth = texture( SceneDepth, depthUv ).r;
		float rawDepthSeparation = sceneDepth - gl_FragCoord.z;
		// Only soften fragments in front of scene depth; sky/background depth should not erase smoke.
		if ( sceneDepth < 0.99999 && rawDepthSeparation > 0.0 ) {
			float sceneViewDepth = abs( ViewSpaceZFromDepth( sceneDepth ) );
			float particleViewDepth = abs( ViewSpaceZFromDepth( gl_FragCoord.z ) );
			float separation = max( sceneViewDepth - particleViewDepth, 0.0 );
			if ( separation <= 0.0001 && rawDepthSeparation > 0.0 ) {
				float depthToWorldScale = ( 2.0 * particleViewDepth * particleViewDepth ) / max( abs( depthProjection.y ), 0.0001 );
				separation = rawDepthSeparation * max( depthToWorldScale, 1.0 );
			}
			float softFade = smoothstep( 0.0, max( fadeDistance, 1.0 ), separation );
			fade = softFade;
		}
	}

	if ( additiveBlend > 0.5 ) {
		particle.rgb *= fade;
		particle.a *= fade;
	} else {
		particle.a *= fade;
	}

	outColor = particle;
}
