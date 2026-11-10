#version 450

// Bloom composite, HDR tone map and colour grade in one pass. A port of
// content/baseoq4/pak0/glprogs/bloom.fs (RB_STD_Bloom). The scene owner must
// explicitly select the numeric domain; an FP16 target alone is not proof of
// linear lighting. Native mixed scenes retain the stock branch.
// fragUV is OpenGL's texture coordinate; see post_ssao.frag.

layout(set = 0, binding = 0) uniform sampler2D Scene;
layout(set = 1, binding = 0) uniform sampler2D BloomTex0;
layout(set = 2, binding = 0) uniform sampler2D BloomTex1;
layout(set = 3, binding = 0) uniform sampler2D BloomTex2;
layout(set = 4, binding = 0) uniform sampler2D BloomTex3;
layout(set = 5, binding = 0) uniform sampler2D BloomTex4;

layout(std140, set = 6, binding = 0) uniform BloomCompositeBlock {
    vec4 bloom;				// x: intensity, y: enabled, z: tone map enabled, w: debug view
    vec4 exposure;			// x: exposure, y: white point, z: lift, w: post gamma
    vec4 grade;				// x: gain, y: vibrance, z: saturation, w: contrast
    vec4 highlight;			// x: highlight desaturation, y: gamut compression
    vec4 weights;			// bloom level weights 0-3
    vec4 weights2;			// x: bloom level weight 4, y: committed linear scene
} block;

#define bloomIntensity				block.bloom.x
#define bloomEnabled				block.bloom.y
#define toneMapEnabled				block.bloom.z
#define hdrDebugView				block.bloom.w
#define hdrExposure					block.exposure.x
#define hdrWhitePoint				block.exposure.y
#define hdrLift						block.exposure.z
#define hdrPostGamma				block.exposure.w
#define hdrGain						block.grade.x
#define hdrVibrance					block.grade.y
#define hdrSaturation				block.grade.z
#define hdrContrast					block.grade.w
#define hdrHighlightDesaturation	block.highlight.x
#define hdrGamutCompression			block.highlight.y
#define bloomWeight0				block.weights.x
#define bloomWeight1				block.weights.y
#define bloomWeight2				block.weights.z
#define bloomWeight3				block.weights.w
#define bloomWeight4				block.weights2.x
#define hdrLinearScene				block.weights2.y

layout(location = 0) in vec2 fragUV;
layout(location = 0) out vec4 outColor;

vec3 SampleBloom( vec2 uv ) {
	vec3 bloom = vec3( 0.0 );
	bloom += max( texture( BloomTex0, uv ).rgb, vec3( 0.0 ) ) * bloomWeight0;
	bloom += max( texture( BloomTex1, uv ).rgb, vec3( 0.0 ) ) * bloomWeight1;
	bloom += max( texture( BloomTex2, uv ).rgb, vec3( 0.0 ) ) * bloomWeight2;
	bloom += max( texture( BloomTex3, uv ).rgb, vec3( 0.0 ) ) * bloomWeight3;
	bloom += max( texture( BloomTex4, uv ).rgb, vec3( 0.0 ) ) * bloomWeight4;
	return max( bloom, vec3( 0.0 ) );
}

vec3 SceneReferredHDRColor( vec3 color ) {
	return max( color, vec3( 0.0 ) );
}

vec3 HighlightCompress( vec3 color ) {
	float luma = dot( color, vec3( 0.2126, 0.7152, 0.0722 ) );
	float peak = max( max( color.r, color.g ), color.b );
	float highlight = smoothstep( 0.98, 1.0, peak );

	color = mix( color, vec3( luma ), clamp( highlight * hdrHighlightDesaturation, 0.0, 1.0 ) );

	peak = max( max( color.r, color.g ), color.b );
	if ( peak > 1.0 && hdrGamutCompression > 0.0 ) {
		float compressedPeak = 1.0 + ( peak - 1.0 ) / ( 1.0 + hdrGamutCompression * ( peak - 1.0 ) );
		color *= compressedPeak / peak;
	}

	return color;
}

vec3 ToneMapHDR( vec3 color ) {
	color = SceneReferredHDRColor( color );
	float safeExposure = max( hdrExposure, 0.001 );
	vec3 exposedColor = color * safeExposure;
	float safeWhitePoint = max( hdrWhitePoint, 1.0 );
	if ( hdrLinearScene > 0.5 ) {
		// Match the admitted GL linear scene. Exposure changes the radiance,
		// not the reference white, and display encoding happens exactly once.
		vec3 mapped = ( exposedColor * ( 2.51 * exposedColor + 0.03 ) )
			/ ( exposedColor * ( 2.43 * exposedColor + 0.59 ) + 0.14 );
		float white = ( safeWhitePoint * ( 2.51 * safeWhitePoint + 0.03 ) )
			/ ( safeWhitePoint * ( 2.43 * safeWhitePoint + 0.59 ) + 0.14 );
		mapped = clamp( HighlightCompress( mapped / max( white, 0.0001 ) ), 0.0, 1.0 );
		return mix( mapped * 12.92, 1.055 * pow( mapped, vec3( 1.0 / 2.4 ) ) - 0.055,
			step( vec3( 0.0031308 ), mapped ) );
	}
	// Reserve real display range for highlights. Starting at .98 collapsed
	// sunlit textures to about five output codes whenever exposure rose.
	// This rational shoulder joins the unchanged midrange with slope one and
	// reaches display white at the exposed reference white. No extra sRGB
	// encoding belongs here: these stock scene values are already perceptual.
	float shoulderStart = 0.5;
	float exposedWhitePoint = max( safeWhitePoint * safeExposure, 1.0 );
	float shoulderRange = exposedWhitePoint - shoulderStart;
	float curvature = 1.0 / ( 1.0 - shoulderStart ) - 1.0 / shoulderRange;
	vec3 shoulderT = max( exposedColor - vec3( shoulderStart ), vec3( 0.0 ) );
	vec3 shoulderColor = vec3( shoulderStart ) + shoulderT / ( vec3( 1.0 ) + curvature * shoulderT );
	vec3 mappedColor = mix( exposedColor, shoulderColor, step( vec3( shoulderStart ), exposedColor ) );
	return clamp( HighlightCompress( mappedColor ), 0.0, 1.0 );
}

vec3 ApplyLiftGammaGain( vec3 color ) {
	color = max( color + vec3( hdrLift ), vec3( 0.0 ) );
	color = pow( color, vec3( 1.0 / max( hdrPostGamma, 0.001 ) ) );
	color *= hdrGain;
	return color;
}

vec3 ApplyVibrance( vec3 color ) {
	float luma = dot( color, vec3( 0.2126, 0.7152, 0.0722 ) );
	float maxChannel = max( max( color.r, color.g ), color.b );
	float minChannel = min( min( color.r, color.g ), color.b );
	float saturation = maxChannel - minChannel;
	float vibranceMix = clamp( 1.0 + hdrVibrance * ( 1.0 - saturation ), 0.0, 2.0 );
	return mix( vec3( luma ), color, vibranceMix );
}

vec3 ApplyColorAdjustments( vec3 color ) {
	color = ApplyLiftGammaGain( color );
	color = ApplyVibrance( color );

	float luma = dot( color, vec3( 0.2126, 0.7152, 0.0722 ) );
	color = mix( vec3( luma ), color, hdrSaturation );
	color = ( color - 0.5 ) * hdrContrast + 0.5;
	return clamp( color, 0.0, 1.0 );
}

vec3 DebugHeatmap( float scenePeak ) {
	float mapped = clamp( ( log2( max( scenePeak, 0.0001 ) ) + 8.0 ) / 8.0, 0.0, 1.0 );

	vec3 c0 = vec3( 0.02, 0.05, 0.16 );
	vec3 c1 = vec3( 0.00, 0.55, 0.95 );
	vec3 c2 = vec3( 0.18, 0.84, 0.18 );
	vec3 c3 = vec3( 0.98, 0.78, 0.08 );
	vec3 c4 = vec3( 0.95, 0.14, 0.05 );

	if ( mapped < 0.25 ) {
		return mix( c0, c1, mapped / 0.25 );
	}
	if ( mapped < 0.5 ) {
		return mix( c1, c2, ( mapped - 0.25 ) / 0.25 );
	}
	if ( mapped < 0.75 ) {
		return mix( c2, c3, ( mapped - 0.5 ) / 0.25 );
	}
	return mix( c3, c4, ( mapped - 0.75 ) / 0.25 );
}

void main() {
	vec2 uv = fragUV;
	vec4 sceneSample = texture( Scene, uv );
	vec3 sceneColor = SceneReferredHDRColor( sceneSample.rgb );
	vec3 color = sceneColor;

	if ( bloomEnabled > 0.5 && bloomIntensity > 0.0001 ) {
		color += SampleBloom( uv ) * bloomIntensity;
	}

	if ( hdrDebugView > 0.5 ) {
		float scenePeak = max( max( sceneColor.r, sceneColor.g ), sceneColor.b );
		if ( hdrDebugView > 1.5 ) {
			float grayscale = clamp( ( log2( max( scenePeak, 0.0001 ) ) + 10.0 ) / 10.0, 0.0, 1.0 );
			outColor = vec4( vec3( grayscale ), sceneSample.a );
		} else {
			outColor = vec4( DebugHeatmap( scenePeak ), sceneSample.a );
		}
		return;
	}

	if ( toneMapEnabled > 0.5 ) {
		color = ToneMapHDR( color );
		color = ApplyColorAdjustments( color );
	}

	outColor = vec4( color, sceneSample.a );
}
