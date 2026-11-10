#ifndef OPENQ4_MODERN_SHADOW_MAPS_H
#define OPENQ4_MODERN_SHADOW_MAPS_H

// Current-frame receiver maps. The classic caster rasterizer is shared, but
// these copies have a separate lifetime from its per-light scratch/cache state.
// A failed or partial render never publishes a sampleable rectangle.
struct viewDef_s;
struct viewLight_s;
struct modernShadowLightDescriptor_s;
struct rendererShadowTextureBindings_s;

const int MODERN_CURRENT_POINT_SHADOW_TEXTURE_UNIT = 22;

bool RB_ModernShadowMapsBegin( const viewDef_s *view, int pointSize,
    int pointFaces, int projectedSize, int projectedTiles );
bool RB_ModernShadowMapRender( const viewDef_s *view,
    modernShadowLightDescriptor_s &descriptor );
bool RB_ModernShadowMapBindings( rendererShadowTextureBindings_s &bindings );
void RB_ModernShadowMapsShutdown();

#endif
