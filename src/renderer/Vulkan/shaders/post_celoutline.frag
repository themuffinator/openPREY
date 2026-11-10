#version 450

// Screen-space cel outline over world geometry. A port of
// content/baseoq4/pak0/glprogs/celoutline.fs (RB_STD_CelWorldOutline); see
// that file for how the two depth snapshots divide the work. fragUV is
// OpenGL's texture coordinate; see post_ssao.frag.

layout(set = 0, binding = 0) uniform sampler2D Scene;
layout(set = 1, binding = 0) uniform sampler2D WorldDepthBuffer;
layout(set = 2, binding = 0) uniform sampler2D SceneDepthBuffer;

layout(std140, set = 6, binding = 0) uniform CelOutlineBlock {
    vec4 texInfo;			// xy: invTexSize
    vec4 projection;		// 1/P[0], 1/P[5], P[8], P[9]
    vec4 depthInfo;			// x: P[10], y: P[14]
    vec4 celEdgeParams;		// x: edge radius, y: silhouette sensitivity, z: crease sensitivity, w: debug view
    vec4 celOutlineColor;
} block;

#define invTexSize			block.texInfo.xy
#define projectionInfo		block.projection
#define depthProjection		block.depthInfo.xy
#define celEdgeParams		block.celEdgeParams
#define celOutlineColor		block.celOutlineColor

layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

const float kSkyDepth = 0.99999;

float SampleDepth( vec2 uv ) {
	return texture( WorldDepthBuffer, uv ).x;
}

float SampleSceneDepth( vec2 uv ) {
	return texture( SceneDepthBuffer, uv ).x;
}

float ViewSpaceZFromDepth( float depth ) {
	float ndcDepth = depth * 2.0 - 1.0;
	float denom = ndcDepth + depthProjection.x;
	if ( abs( denom ) < 0.00001 ) {
		denom = ( denom < 0.0 ) ? -0.00001 : 0.00001;
	}
	return ( -depthProjection.y ) / denom;
}

vec3 ReconstructViewPosition( vec2 uv, float depth ) {
	float viewZ = ViewSpaceZFromDepth( depth );
	vec2 ndc = uv * 2.0 - 1.0;

	return vec3(
		-viewZ * ( ndc.x + projectionInfo.z ) * projectionInfo.x,
		-viewZ * ( ndc.y + projectionInfo.w ) * projectionInfo.y,
		viewZ );
}

bool PixelIsForeground( vec2 uv, float worldDepth ) {
	float sceneDepth = SampleSceneDepth( uv );
	if ( sceneDepth >= kSkyDepth || worldDepth >= kSkyDepth ) {
		return false;
	}

	float worldViewDepth = -ViewSpaceZFromDepth( worldDepth );
	float sceneViewDepth = -ViewSpaceZFromDepth( sceneDepth );

	return sceneViewDepth + 1.0 < worldViewDepth;
}

void main() {
	vec2 uv = fragUV;
	vec4 scene = texture( Scene, uv );
	float centerDepth = SampleDepth( uv );

	if ( centerDepth >= kSkyDepth ) {
		outColor = ( celEdgeParams.w > 0.5 ) ? vec4( 0.0, 0.0, 0.0, scene.a ) : scene;
		return;
	}

	if ( PixelIsForeground( uv, centerDepth ) ) {
		outColor = ( celEdgeParams.w > 0.5 ) ? vec4( 0.0, 0.0, 0.0, scene.a ) : scene;
		return;
	}

	vec2 texel = invTexSize * max( celEdgeParams.x, 1.0 );
	vec2 offsetX = vec2( texel.x, 0.0 );
	vec2 offsetY = vec2( 0.0, texel.y );

	float leftDepth = SampleDepth( uv - offsetX );
	float rightDepth = SampleDepth( uv + offsetX );
	float downDepth = SampleDepth( uv - offsetY );
	float upDepth = SampleDepth( uv + offsetY );

	vec3 centerPos = ReconstructViewPosition( uv, centerDepth );
	vec3 leftPos = ReconstructViewPosition( uv - offsetX, leftDepth );
	vec3 rightPos = ReconstructViewPosition( uv + offsetX, rightDepth );
	vec3 downPos = ReconstructViewPosition( uv - offsetY, downDepth );
	vec3 upPos = ReconstructViewPosition( uv + offsetY, upDepth );

	float viewDistance = max( -centerPos.z, 1.0 );

	float skyNeighbour = 0.0;
	skyNeighbour = max( skyNeighbour, step( kSkyDepth, leftDepth ) );
	skyNeighbour = max( skyNeighbour, step( kSkyDepth, rightDepth ) );
	skyNeighbour = max( skyNeighbour, step( kSkyDepth, downDepth ) );
	skyNeighbour = max( skyNeighbour, step( kSkyDepth, upDepth ) );

	float depthEdge = max(
		abs( ( -leftPos.z ) + ( -rightPos.z ) - 2.0 * viewDistance ),
		abs( ( -downPos.z ) + ( -upPos.z ) - 2.0 * viewDistance ) );
	float depthTolerance = max( celEdgeParams.y, 0.00001 ) * viewDistance;
	float silhouette = smoothstep( depthTolerance, depthTolerance * 2.0, depthEdge );
	silhouette = max( silhouette, skyNeighbour );

	float crease = 0.0;
	if ( celEdgeParams.z > 0.0 ) {
		vec2 diagonal = offsetX + offsetY;
		vec2 antiDiagonal = offsetX - offsetY;
		vec3 upperRight = ReconstructViewPosition( uv + diagonal, SampleDepth( uv + diagonal ) );
		vec3 lowerLeft = ReconstructViewPosition( uv - diagonal, SampleDepth( uv - diagonal ) );
		vec3 lowerRight = ReconstructViewPosition( uv + antiDiagonal, SampleDepth( uv + antiDiagonal ) );
		vec3 upperLeft = ReconstructViewPosition( uv - antiDiagonal, SampleDepth( uv - antiDiagonal ) );

		vec3 planeNormal = cross( upperRight - lowerLeft, upperLeft - lowerRight );
		float planeLength = length( planeNormal );
		if ( planeLength > 0.000001 ) {
			planeNormal /= planeLength;

			float deviation = max(
				max( abs( dot( planeNormal, leftPos - centerPos ) ), abs( dot( planeNormal, rightPos - centerPos ) ) ),
				max( abs( dot( planeNormal, downPos - centerPos ) ), abs( dot( planeNormal, upPos - centerPos ) ) ) );

			float span = max( length( rightPos - leftPos ), 0.0001 );
			float creaseTolerance = max( 1.0 - celEdgeParams.z, 0.02 ) * 0.5;
			crease = smoothstep( creaseTolerance * 0.5, creaseTolerance, deviation / span );
		}

		crease *= 1.0 - silhouette;
	}

	float edge = clamp( max( silhouette, crease ), 0.0, 1.0 ) * celOutlineColor.a;

	if ( celEdgeParams.w > 0.5 ) {
		outColor = vec4( vec3( edge ), scene.a );
		return;
	}

	outColor = vec4( mix( scene.rgb, celOutlineColor.rgb, edge ), scene.a );
}
