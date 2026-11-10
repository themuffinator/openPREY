// Composite half of the Raven special-effect blur controller
// (SPECIAL_EFFECT_BLUR).  Its parameter contract is shared with the native
// Vulkan pass in src/renderer/Vulkan/shaders/material_depth_aware_blur.frag,
// so the two backends have to read the controller the same way:
//
//   parm 0-3  approachColor; rgb is the colour the blurred scene tints
//             towards and a is how much of it to apply
//   parm 4    effect range - the distance past the focus point over which the
//             image reaches full blur, in the controller's own units
//   parm 5    focus, normalized 0..1 against parm 7
//   parm 6    effect strength; 0 means the controller is off, not "blur at
//             some fixed default"
//   parm 7    distance scale, already consumed when Depth was written
//
// Depth here is linear view distance normalized by parm 7, so the range is
// converted the same way the Vulkan pass converts it (parm 4 * 0.125) and both
// ends measure the circle of confusion against the same normalized distance.

uniform sampler2D Depth;
uniform sampler2D Blur1;
uniform float effectRange;
uniform float focus;
uniform float scroll;
uniform vec4 approachColor;
uniform float approachPercent;

void main() {
	vec2 uv = gl_TexCoord[0].st;
	float depth = texture2D( Depth, uv ).r;
	vec3 blurredScene = texture2D( Blur1, uv ).rgb;

	float strength = clamp( approachPercent, 0.0, 1.0 );
	float blurRange = max( effectRange * 0.125, 0.002 );
	float circleOfConfusion = smoothstep( 0.0, 1.0,
		clamp( abs( depth - clamp( focus, 0.0, 1.0 ) ) / blurRange, 0.0, 1.0 ) );
	float blurAmount = circleOfConfusion * strength;

	float tintAmount = blurAmount * clamp( approachColor.a, 0.0, 1.0 ) * 0.04;
	vec3 overlayColor = mix( blurredScene, approachColor.rgb, tintAmount );

	gl_FragColor = vec4( overlayColor, blurAmount );
}
