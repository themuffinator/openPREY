#version 450
#extension GL_GOOGLE_include_directive : require
#include "framebuffer_coords.glsl"

// Baked light-grid indirect diffuse. A port of
// content/baseoq4/pak0/glprogs/lightgrid_indirect.fs: the body below is that
// file with its uniforms packed into LightGridBlock (256 bytes, the uniform
// ring's slice size) and the macros restoring the OpenGL names.
//
// uSceneDepth is the _currentDepth capture, stored bottom-up like an OpenGL
// texture; Vulkan's gl_FragCoord has a top-left origin, so its y is flipped
// into OpenGL's window space before it indexes the capture.

layout(set = 0, binding = 0) uniform sampler2D uBumpMap;
layout(set = 1, binding = 0) uniform sampler2D uDiffuseMap;
layout(set = 2, binding = 0) uniform sampler2D uLightGridAtlas;
layout(set = 3, binding = 0) uniform sampler2D uLightGridVisibilityAtlas;
layout(set = 4, binding = 0) uniform sampler2D uLightGridProbeAtlas;
layout(set = 5, binding = 0) uniform sampler2D uSceneDepth;

layout(std140, set = 6, binding = 0) uniform LightGridBlock {
    vec4 modelRow0;
    vec4 modelRow1;
    vec4 modelRow2;
    vec4 gridOrigin;		// xyz: grid origin, w: r_lightGridDebug
    vec4 gridSize;			// xyz: cell size, w: probe relocation distance
    vec4 gridBounds;		// xyz: cell counts, w: probe atlas bound
    vec4 atlasInfo;
    vec4 visibilityInfo;
    vec4 blendInfo;			// xyz: intensity, portal side, portal distance; w: irradiance gamma
    vec4 portalPlane;
    vec4 portalBoundsMin;	// xyz: bounds, w: max contribution
    vec4 portalBoundsMax;	// xyz: bounds, w: vertex colour scale
    vec4 depthInfo;
    vec4 depthViewport;		// xy: view origin (OpenGL window space), z: vertex colour bias, w: framebuffer height
    vec4 diffuseColor;
    vec4 flatDiffuseParams;
} block;

#define uLightGridOrigin	block.gridOrigin
#define uLightGridSize		block.gridSize
#define uLightGridBounds	block.gridBounds
#define uAtlasInfo			block.atlasInfo
#define uVisibilityInfo		block.visibilityInfo
#define uProbeInfo			vec4( block.gridSize.w, block.gridBounds.w, 0.0, 0.0 )
#define uBlendInfo			block.blendInfo
#define uPortalPlane		block.portalPlane
#define uPortalBoundsMin	block.portalBoundsMin
#define uPortalBoundsMax	block.portalBoundsMax
#define uDebugInfo			vec4( block.gridOrigin.w, 0.18, 0.18, 0.18 )
#define uDepthInfo			block.depthInfo
#define uDepthViewport		block.depthViewport
#define uColorInfo			vec4( block.blendInfo.w, block.portalBoundsMin.w, 0.0, 0.0 )
#define uDiffuseColor		block.diffuseColor
#define uFlatDiffuseParams	block.flatDiffuseParams

layout(location = 0) in vec2 vBumpTexCoord;
layout(location = 1) in vec2 vDiffuseTexCoord;
layout(location = 2) in vec3 vWorldTangent;
layout(location = 3) in vec3 vWorldBitangent;
layout(location = 4) in vec3 vWorldNormal;
layout(location = 5) in vec3 vWorldPosition;
layout(location = 6) in vec3 vVertexColor;
layout(location = 7) in float vLocalZ;

layout(location = 0) out vec4 outColor;

vec2 SignNotZero( vec2 value ) {
	return vec2( value.x >= 0.0 ? 1.0 : -1.0, value.y >= 0.0 ? 1.0 : -1.0 );
}

vec3 SafeNormalize( vec3 value ) {
	return value * inversesqrt( max( dot( value, value ), 1.0e-8 ) );
}

vec3 DecodeBakedIrradiance( vec3 value ) {
	float gamma = max( uColorInfo.x, 0.001 );
	return pow( max( value, vec3( 0.0 ) ), vec3( gamma ) );
}

vec3 ShapeLightGridContribution( vec3 value ) {
	float maxContribution = uColorInfo.y;
	if ( maxContribution > 0.0 ) {
		value = min( value, vec3( maxContribution ) );
	}
	return max( value, vec3( 0.0 ) );
}

vec3 ApplyFlatDiffuseSweep( vec3 diffuse, float localZ ) {
	if ( uFlatDiffuseParams.x <= 0.0 ) {
		return diffuse;
	}
	float height = clamp( ( localZ - uFlatDiffuseParams.y ) * uFlatDiffuseParams.z, 0.0, 1.0 );
	float distanceToBand = abs( height - fract( uFlatDiffuseParams.w ) );
	distanceToBand = min( distanceToBand, 1.0 - distanceToBand );
	float band = 1.0 - smoothstep( 0.045, 0.16, distanceToBand );
	return mix( diffuse, vec3( 1.0 ), uFlatDiffuseParams.x * band );
}

vec3 DecodeLocalNormal( vec4 bumpSample ) {
	vec2 localNormalXY = vec2( bumpSample.a, bumpSample.g ) * 2.0 - 1.0;
	float xyLengthSq = dot( localNormalXY, localNormalXY );
	if ( xyLengthSq > 1.0 ) {
		localNormalXY *= inversesqrt( xyLengthSq );
		xyLengthSq = 1.0;
	}

	float encodedZ = max( bumpSample.b * 2.0 - 1.0, 0.0 );
	float reconstructedZ = sqrt( max( 1.0 - xyLengthSq, 0.0 ) );
	return SafeNormalize( vec3( localNormalXY, mix( encodedZ, reconstructedZ, 0.75 ) ) );
}

vec2 OctEncode( vec3 normal ) {
	float invLength = 1.0 / max( abs( normal.x ) + abs( normal.y ) + abs( normal.z ), 1.0e-4 );
	vec3 n = normal * invLength;
	vec2 oct = n.xy;
	if ( n.z < 0.0 ) {
		oct = ( vec2( 1.0 ) - abs( oct.yx ) ) * SignNotZero( oct );
	}
	return oct;
}

void ComputeGridAxis( float lightOrigin, float cellSize, float bound, out float gridCoord, out float fracCoord ) {
	if ( bound <= 1.0 || cellSize <= 0.0 ) {
		gridCoord = 0.0;
		fracCoord = 0.0;
		return;
	}

	float position = max( 0.0, lightOrigin / cellSize );
	gridCoord = floor( position );
	fracCoord = position - gridCoord;

	if ( gridCoord < 0.0 ) {
		gridCoord = 0.0;
		fracCoord = 0.0;
	} else if ( gridCoord >= bound - 1.0 ) {
		gridCoord = bound - 1.0;
		fracCoord = 0.0;
	}
}

vec2 ProbeAtlasCoord( vec3 sampleCoord, vec2 octCoord ) {
	float tileSize = max( uAtlasInfo.z, 1.0 );
	float borderSize = max( uAtlasInfo.w, 0.0 );
	float activeSize = max( tileSize - borderSize, 1.0 );
	float cellIndex = sampleCoord.x + sampleCoord.z * uLightGridBounds.x;
	vec2 probeOriginPixels = vec2( cellIndex * tileSize, sampleCoord.y * tileSize );
	vec2 samplePixels = probeOriginPixels + vec2( borderSize * 0.5 ) + octCoord * activeSize;
	return samplePixels * uAtlasInfo.xy;
}

vec2 ProbeGridCoord( vec3 sampleCoord ) {
	float invCellsX = 1.0 / max( uLightGridBounds.x * uLightGridBounds.z, 1.0 );
	float invCellsY = 1.0 / max( uLightGridBounds.y, 1.0 );
	float cellIndex = sampleCoord.x + sampleCoord.z * uLightGridBounds.x;
	return vec2( ( cellIndex + 0.5 ) * invCellsX, ( sampleCoord.y + 0.5 ) * invCellsY );
}

vec3 ProbeWorldPosition( vec3 sampleCoord ) {
	vec3 idealPosition = uLightGridOrigin.xyz + sampleCoord * uLightGridSize.xyz;
	if ( uProbeInfo.y <= 0.0 ) {
		return idealPosition;
	}

	vec3 encodedRelocation = texture( uLightGridProbeAtlas, ProbeGridCoord( sampleCoord ) ).rgb * 255.0;
	vec3 relocation = ( encodedRelocation - vec3( 128.0 ) ) * ( uProbeInfo.x / 127.0 );
	return idealPosition + relocation;
}

float VisibilityWeight( vec4 moments, float receiverDistance, vec3 worldNormal, vec3 probeToReceiverDir ) {
	if ( moments.b <= 0.001 ) {
		return 1.0;
	}

	float maxDistance = max( uVisibilityInfo.x, 1.0 );
	float meanDistance = moments.r * maxDistance;
	float meanDistanceSq = moments.g * maxDistance * maxDistance;
	float normalBias = uVisibilityInfo.y * ( 0.25 + 0.75 * max( dot( worldNormal, -probeToReceiverDir ), 0.0 ) );
	float biasedDistance = max( receiverDistance - normalBias, 0.0 );
	if ( biasedDistance <= meanDistance ) {
		return 1.0;
	}

	float variance = max( meanDistanceSq - meanDistance * meanDistance, maxDistance * maxDistance * 0.000025 );
	float delta = biasedDistance - meanDistance;
	float chebyshev = variance / ( variance + delta * delta );
	chebyshev = clamp( chebyshev, 0.0, 1.0 );
	return clamp( pow( chebyshev, max( uVisibilityInfo.w, 1.0 ) ), uVisibilityInfo.z, 1.0 );
}

float LightGridContributionScale() {
	if ( abs( uBlendInfo.y ) <= 0.001 || uBlendInfo.z <= 0.0 ) {
		return uBlendInfo.x;
	}

	float portalDistance = abs( dot( vWorldPosition, uPortalPlane.xyz ) + uPortalPlane.w );
	vec3 nearestPortalBoundsPoint = clamp( vWorldPosition, uPortalBoundsMin.xyz, uPortalBoundsMax.xyz );
	float apertureDistance = length( vWorldPosition - nearestPortalBoundsPoint );
	float portalFade =
		( 1.0 - smoothstep( 0.0, uBlendInfo.z, portalDistance ) ) *
		( 1.0 - smoothstep( 0.0, uBlendInfo.z, apertureDistance ) );
	float neighborWeight = 0.5 * portalFade;
	float blendWeight = uBlendInfo.y > 0.0 ? neighborWeight : 1.0 - neighborWeight;
	return uBlendInfo.x * blendWeight;
}

vec2 LightGridDepthCoord() {
	vec2 fragCoordGL = vec2( gl_FragCoord.x, CanonicalWindowY(uDepthViewport.w) );
	return ( fragCoordGL - uDepthViewport.xy ) * uDepthInfo.xy;
}

bool LightGridDepthCoordValid( vec2 depthCoord ) {
	return depthCoord.x >= 0.0 && depthCoord.y >= 0.0 && depthCoord.x <= 1.0 && depthCoord.y <= 1.0;
}

float LightGridSceneDepth( vec2 depthCoord ) {
	return texture( uSceneDepth, depthCoord ).r;
}

bool LightGridDepthAccepted() {
	if ( uDepthInfo.w <= 0.5 ) {
		return true;
	}

	vec2 depthCoord = LightGridDepthCoord();
	if ( !LightGridDepthCoordValid( depthCoord ) ) {
		return false;
	}

	float sceneDepth = LightGridSceneDepth( depthCoord );
	return gl_FragCoord.z <= sceneDepth + uDepthInfo.z;
}

void main() {
	if ( uDebugInfo.x > 5.5 && uDebugInfo.x < 6.5 ) {
		if ( uDepthInfo.w <= 0.5 ) {
			outColor = vec4( 0.0, 0.0, 0.6, 1.0 );
			return;
		}
		vec2 depthCoord = LightGridDepthCoord();
		if ( !LightGridDepthCoordValid( depthCoord ) ) {
			outColor = vec4( 0.8, 0.0, 0.8, 1.0 );
			return;
		}
		float sceneDepth = LightGridSceneDepth( depthCoord );
		bool accepted = gl_FragCoord.z <= sceneDepth + uDepthInfo.z;
		outColor = accepted ? vec4( 0.0, 0.6, 0.0, 1.0 ) : vec4( 0.7, 0.0, 0.0, 1.0 );
		return;
	}
	if ( uDebugInfo.x > 6.5 && uDebugInfo.x < 7.5 ) {
		if ( uDepthInfo.w <= 0.5 ) {
			outColor = vec4( 0.0, 0.0, 0.6, 1.0 );
			return;
		}
		vec2 depthCoord = LightGridDepthCoord();
		if ( !LightGridDepthCoordValid( depthCoord ) ) {
			outColor = vec4( 0.8, 0.0, 0.8, 1.0 );
			return;
		}
		float sceneDepth = LightGridSceneDepth( depthCoord );
		outColor = vec4( vec3( sceneDepth ), 1.0 );
		return;
	}

	if ( ( uDebugInfo.x > 0.5 && uDebugInfo.x < 1.5 ) || ( uDebugInfo.x > 2.5 && uDebugInfo.x < 3.5 ) ) {
		if ( uDebugInfo.x < 2.5 && !LightGridDepthAccepted() ) {
			discard;
		}
		outColor = vec4( uDebugInfo.yzw, 1.0 );
		return;
	}

	if ( !LightGridDepthAccepted() ) {
		discard;
	}

	vec4 bumpSample = texture( uBumpMap, vBumpTexCoord );
	vec3 localNormal = DecodeLocalNormal( bumpSample );
	vec3 worldNormal = SafeNormalize(
		vWorldTangent * localNormal.x +
		vWorldBitangent * localNormal.y +
		vWorldNormal * localNormal.z );

	vec2 octCoord = ( OctEncode( worldNormal ) + vec2( 1.0 ) ) * 0.5;

	float gridCoordX;
	float gridCoordY;
	float gridCoordZ;
	float fracX;
	float fracY;
	float fracZ;
	vec3 lightOrigin = vWorldPosition - uLightGridOrigin.xyz;
	ComputeGridAxis( lightOrigin.x, uLightGridSize.x, uLightGridBounds.x, gridCoordX, fracX );
	ComputeGridAxis( lightOrigin.y, uLightGridSize.y, uLightGridBounds.y, gridCoordY, fracY );
	ComputeGridAxis( lightOrigin.z, uLightGridSize.z, uLightGridBounds.z, gridCoordZ, fracZ );

	vec3 irradiance = vec3( 0.0 );
	float validFactor = 0.0;

	for ( int i = 0; i < 8; i++ ) {
		float fi = float( i );
		vec3 corner = vec3(
			mod( fi, 2.0 ),
			mod( floor( fi * 0.5 ), 2.0 ),
			floor( fi * 0.25 ) );
		float factor =
			( corner.x > 0.0 ? fracX : 1.0 - fracX ) *
			( corner.y > 0.0 ? fracY : 1.0 - fracY ) *
			( corner.z > 0.0 ? fracZ : 1.0 - fracZ );
		if ( factor <= 0.0 ) {
			continue;
		}

		vec3 sampleCoord = vec3( gridCoordX, gridCoordY, gridCoordZ ) + corner;
		vec2 atlasCoord = ProbeAtlasCoord( sampleCoord, octCoord );

		vec3 sampleColor = DecodeBakedIrradiance( texture( uLightGridAtlas, atlasCoord ).rgb );
		if ( dot( sampleColor, vec3( 1.0 ) ) < 0.0001 ) {
			continue;
		}

		vec3 probePosition = ProbeWorldPosition( sampleCoord );
		vec3 probeToReceiver = vWorldPosition - probePosition;
		float receiverDistance = length( probeToReceiver );
		vec3 probeToReceiverDir = receiverDistance > 0.001 ? probeToReceiver / receiverDistance : worldNormal;
		vec2 visibilityOctCoord = ( OctEncode( probeToReceiverDir ) + vec2( 1.0 ) ) * 0.5;
		vec4 visibilityMoments = texture( uLightGridVisibilityAtlas, ProbeAtlasCoord( sampleCoord, visibilityOctCoord ) );
		float visibility = VisibilityWeight( visibilityMoments, receiverDistance, worldNormal, probeToReceiverDir );

		irradiance += sampleColor * factor * visibility;
		validFactor += factor;
	}

	if ( validFactor > 0.0 && validFactor < 0.9999 ) {
		irradiance *= 1.0 / validFactor;
	}

	vec3 diffuseSample = texture( uDiffuseMap, vDiffuseTexCoord ).rgb;
	diffuseSample = ApplyFlatDiffuseSweep( diffuseSample, vLocalZ );
	if ( uDebugInfo.x > 1.5 && uDebugInfo.x < 2.5 ) {
		outColor = vec4( ShapeLightGridContribution( irradiance * LightGridContributionScale() ), 1.0 );
		return;
	}
	if ( uDebugInfo.x > 3.5 && uDebugInfo.x < 4.5 ) {
		outColor = vec4( diffuseSample * uDiffuseColor.rgb * vVertexColor, 1.0 );
		return;
	}

	vec3 diffuseLighting = ShapeLightGridContribution( irradiance * diffuseSample * uDiffuseColor.rgb * vVertexColor * LightGridContributionScale() );
	if ( uDebugInfo.x > 4.5 && uDebugInfo.x < 5.5 ) {
		outColor = vec4( diffuseLighting, 1.0 );
		return;
	}
	outColor = vec4( diffuseLighting, 1.0 );
}
