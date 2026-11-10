// Copyright (C) 2026 DarkMatter Productions
#ifndef OPENQ4_PBR_NATIVE_CONTRACT_H
#define OPENQ4_PBR_NATIVE_CONTRACT_H

// Per-surface admission for the native PBR owners: the OpenGL classic light
// loop and the native Vulkan interaction renderer. A native owner replaces
// the final classic interaction submit of each light and adds one environment
// draw per surface, so it may only take a surface whose classic interaction
// topology, coverage contract and PBR resources are all proven. Everything
// here is backend-neutral: image readiness uses the public device handle.

class idImage;
class idMaterial;
struct drawSurf_s;
typedef struct drawSurf_s drawSurf_t;

typedef struct pbrNativeMaterial_s {
	idImage *	normalImage;	// PBR normal, or _flat when the material has none
	idImage *	albedoImage;	// sRGB color with linear coverage alpha
	idImage *	dataImage;		// packed ORM, else separate roughness, else _white
	idImage *	metallicImage;	// separate metallic, NULL otherwise
	idImage *	aoImage;		// separate AO, NULL with ORM or scalar AO
	idImage *	emissiveImage;	// sRGB emission, NULL without emission
	int			dataFlags;		// 1 packed ORM, 2 separate metallic, 4 separate roughness
	int			normalFormat;	// 0 flat; otherwise pbrNormalFormat_t + 1
	float		metallic;
	float		roughness;
	float		normalScale;
	float		ao;
	float		emissiveColor[3];
} pbrNativeMaterial_t;

float	R_PBRNative_RegisterValue( const drawSurf_t *surf, int registerIndex, float fallback );
bool	R_PBRNative_ImageReady( const idImage *image, int expectedUsage );

// Exactly one active classic bump -> diffuse -> specular sequence, so the
// classic decomposition submits once per light stage and the PBR draw can
// replace that submit. Declared duplicates are rejected even when inactive.
bool	R_PBRNative_HasSingleClassicInteractionTopology( const drawSurf_t *surf );

// A perforated material's depth fill owns its coverage. The single alpha-test
// stage must sample the PBR albedo itself with untransformed coordinates.
bool	R_PBRNative_PerforatedCoverageMatches( const drawSurf_t *surf );

// The one authored source-alpha blend stage of a translucent PBR material,
// provably sampling the PBR albedo; its alpha register scales the coverage.
bool	R_PBRNative_TransparentStage( const drawSurf_t *surf, int *stageIndexOut, float *alphaScaleOut );

// Complete material admission. translucentAdmitted is the owner's own view
// decision for ordered transparency; owners without it pass false.
bool	R_PBRNative_Material( const drawSurf_t *surf, bool translucentAdmitted, pbrNativeMaterial_t &out );

// True when stageIndex is the classic additive glow stage the native owner
// replaces with typed linear emission.
bool	R_PBRNative_IsReplacedEmissionStage( const drawSurf_t *surf, int stageIndex );

#endif
