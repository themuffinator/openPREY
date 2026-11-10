// Canonical geometric passes use GL window coordinates. The swapchain keeps
// top-down rows; lower-origin image attachments keep GL's framebuffer Y.
// Raw texel-copy/resolve passes must continue to use gl_FragCoord directly.
layout(constant_id = 15) const bool framebufferLowerOrigin = false;
float CanonicalWindowY(float framebufferHeight) {
    return framebufferLowerOrigin ? gl_FragCoord.y : framebufferHeight - gl_FragCoord.y;
}
