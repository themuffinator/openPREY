// Copyright (C) 2026 DarkMatter Productions
#include "../idlib/precompiled.h"
#pragma hdrstop

#include "tr_local.h"
#include "MaterialResourceTable.h"
#include "PBRNativeContract.h"

#include <cmath>

float R_PBRNative_RegisterValue( const drawSurf_t *surf, int registerIndex, float fallback ) {
	if ( surf == NULL || surf->material == NULL || surf->shaderRegisters == NULL
			|| registerIndex < 0 || registerIndex >= surf->material->GetNumRegisters() ) {
		return fallback;
	}
	const float value = surf->shaderRegisters[ registerIndex ];
	return std::isfinite( value ) ? value : fallback;
}

bool R_PBRNative_ImageReady( const idImage *image, int expectedUsage ) {
	idImage *mutableImage = const_cast<idImage *>( image );
	return image != NULL && image->GetUsage() == expectedUsage
		&& image->IsLoaded() && !image->IsDefaulted()
		&& mutableImage->GetDeviceHandle() != 0;
}

/*
====================
R_PBRNative_HasSingleClassicInteractionTopology

The classic decomposition flushes an interaction whenever it encounters a
second bump, diffuse, or specular stage. A PBR draw evaluates the whole BRDF,
so it may only replace the canonical final submit when the material has exactly
one active classic bump -> diffuse -> specular sequence. Declared duplicates
are rejected even when their current condition is false: changing registers
must never change which decomposition draw owns the complete BRDF.
====================
*/
bool R_PBRNative_HasSingleClassicInteractionTopology( const drawSurf_t *surf ) {
	if ( surf == NULL || surf->material == NULL || surf->shaderRegisters == NULL ) {
		return false;
	}

	const idMaterial *material = surf->material;
	const float *registers = surf->shaderRegisters;
	const int registerCount = material->GetNumRegisters();
	int bumpStage = -1;
	int diffuseStage = -1;
	int specularStage = -1;

	for ( int stageIndex = 0; stageIndex < material->GetNumStages(); stageIndex++ ) {
		const shaderStage_t *surfaceStage = material->GetStage( stageIndex );
		if ( surfaceStage == NULL ) {
			return false;
		}

		// A custom-lighting stage is another complete per-light owner. Keep
		// mixed custom/classic materials entirely on their authored path.
		if ( surfaceStage->newStage != NULL && surfaceStage->newStage->customLighting ) {
			return false;
		}

		int *ownerStage = NULL;
		switch ( surfaceStage->lighting ) {
			case SL_BUMP:
				ownerStage = &bumpStage;
				break;
			case SL_DIFFUSE:
				ownerStage = &diffuseStage;
				break;
			case SL_SPECULAR:
				ownerStage = &specularStage;
				break;
			default:
				continue;
		}

		if ( *ownerStage >= 0 || surfaceStage->newStage != NULL
				|| surfaceStage->texture.image == NULL
				|| surfaceStage->conditionRegister < 0
				|| surfaceStage->conditionRegister >= registerCount ) {
			return false;
		}
		const float condition = registers[ surfaceStage->conditionRegister ];
		if ( !std::isfinite( condition ) || condition == 0.0f ) {
			return false;
		}
		*ownerStage = stageIndex;
	}

	return bumpStage >= 0 && diffuseStage > bumpStage && specularStage > diffuseStage;
}

bool R_PBRNative_PerforatedCoverageMatches( const drawSurf_t *surf ) {
	if ( surf == NULL || surf->material == NULL ) {
		return false;
	}
	const idMaterial *material = surf->material;
	// The depth fill owns alpha testing and per-sample coverage, and native
	// direct draws use EQUAL against that same depth. Only admit a single alpha
	// stage with the PBR albedo's image, sampler and UVs; otherwise a different
	// classic mask would silently change PBR coverage.
	const idImage *albedo = material->GetPBRInfo().albedo.image;
	if ( albedo == NULL ) {
		return false;
	}
	int alphaStages = 0;
	for ( int i = 0; i < material->GetNumStages(); ++i ) {
		const shaderStage_t *stage = material->GetStage( i );
		if ( !stage->hasAlphaTest ) {
			continue;
		}
		const idImage *image = stage->texture.image;
		if ( ++alphaStages != 1 || stage->lighting != SL_DIFFUSE
				|| stage->newStage != NULL || image == NULL
				|| idStr::Icmp( image->GetName(), albedo->GetName() ) != 0
				|| image->GetFilter() != albedo->GetFilter()
				|| image->GetRepeat() != albedo->GetRepeat()
				|| stage->texture.texgen != TG_EXPLICIT || stage->texture.hasMatrix
				|| stage->vertexColor != SVC_IGNORE || stage->privatePolygonOffset != 0.0f
				|| R_PBRNative_RegisterValue( surf, stage->conditionRegister, 0.0f ) == 0.0f
				|| R_PBRNative_RegisterValue( surf, stage->color.registers[3], 0.0f ) != 1.0f ) {
			return false;
		}
		const float reference = R_PBRNative_RegisterValue( surf, stage->alphaTestRegister, -1.0f );
		if ( reference < 0.0f || reference > 1.0f ) {
			return false;
		}
	}
	return alphaStages == 1;
}

/*
====================
R_PBRNative_TransparentStage

Source alpha is the one coverage mode the depth fill never resolves, so a
native owner may replace the authored stage only when that stage is provably
the PBR albedo itself: exactly one source-alpha blend stage, the same image,
filter and repeat as the albedo, untransformed explicit coordinates, no vertex
tint or alpha test, and an untinted white color whose alpha register supplies
the coverage scale. Any other ambient stage would compose beside the owner, so
its presence returns the whole material to the classic path.
====================
*/
bool R_PBRNative_TransparentStage( const drawSurf_t *surf, int *stageIndexOut, float *alphaScaleOut ) {
	if ( surf == NULL || surf->material == NULL || surf->shaderRegisters == NULL ) {
		return false;
	}
	const idMaterial *material = surf->material;
	if ( material->Coverage() != MC_TRANSLUCENT ) {
		return false;
	}
	const idImage *albedo = material->GetPBRInfo().albedo.image;
	if ( albedo == NULL ) {
		return false;
	}

	int found = -1;
	float alphaScale = 0.0f;
	for ( int i = 0 ; i < material->GetNumStages() ; i++ ) {
		const shaderStage_t *stage = material->GetStage( i );
		if ( stage->lighting != SL_AMBIENT ) {
			continue;	// the bump/diffuse/specular sequence the BRDF replaces
		}
		const int blendBits = stage->drawStateBits
				& ( GLS_SRCBLEND_BITS | GLS_DSTBLEND_BITS );
		const idImage *image = stage->texture.image;
		if ( found >= 0
				|| blendBits != ( GLS_SRCBLEND_SRC_ALPHA | GLS_DSTBLEND_ONE_MINUS_SRC_ALPHA )
				|| stage->newStage != NULL || image == NULL
				|| idStr::Icmp( image->GetName(), albedo->GetName() ) != 0
				|| image->GetFilter() != albedo->GetFilter()
				|| image->GetRepeat() != albedo->GetRepeat()
				|| stage->texture.texgen != TG_EXPLICIT || stage->texture.hasMatrix
				|| stage->vertexColor != SVC_IGNORE || stage->hasAlphaTest
				|| stage->privatePolygonOffset != 0.0f
				|| R_PBRNative_RegisterValue( surf, stage->conditionRegister, 0.0f ) == 0.0f ) {
			return false;
		}
		for ( int c = 0 ; c < 3 ; c++ ) {
			if ( R_PBRNative_RegisterValue( surf, stage->color.registers[ c ], 0.0f ) != 1.0f ) {
				return false;
			}
		}
		alphaScale = R_PBRNative_RegisterValue( surf, stage->color.registers[ 3 ], -1.0f );
		if ( !( alphaScale > 0.0f ) || alphaScale > 1.0f ) {
			return false;
		}
		found = i;
	}
	if ( found < 0 ) {
		return false;
	}
	if ( stageIndexOut != NULL ) {
		*stageIndexOut = found;
	}
	if ( alphaScaleOut != NULL ) {
		*alphaScaleOut = alphaScale;
	}
	return true;
}

bool R_PBRNative_Material( const drawSurf_t *surf, bool translucentAdmitted, pbrNativeMaterial_t &out ) {
	memset( &out, 0, sizeof( out ) );
	if ( !r_rendererModernQuality.GetBool() || !r_pbrMaterials.GetBool() || r_skipBump.GetBool()
			|| r_skipDiffuse.GetBool() || r_skipSpecular.GetBool()
			|| surf == NULL || surf->material == NULL
			|| !R_PBRNative_HasSingleClassicInteractionTopology( surf ) ) {
		return false;
	}

	const idMaterial *material = surf->material;
	if ( !material->HasPBR() ) {
		return false;
	}
	switch ( material->Coverage() ) {
		case MC_OPAQUE:
			break;
		case MC_PERFORATED:
			if ( !R_PBRNative_PerforatedCoverageMatches( surf ) ) {
				return false;
			}
			break;
		case MC_TRANSLUCENT:
			// A translucent surface is absent from the depth fill, so its draws
			// composite in the material walk instead of adding in the light pass.
			// An owner that cannot own that composite must not take the BRDF
			// either, or the surface would be lit natively and composited classically.
			if ( !translucentAdmitted || !R_PBRNative_TransparentStage( surf, NULL, NULL ) ) {
				return false;
			}
			break;
		default:
			return false;
	}
	const materialResourceTableRecord_t *resourceRecord =
		R_MaterialResourceTable_FindRecordForMaterial( material );
	if ( resourceRecord == NULL
			|| !R_MaterialResourceTable_PBRModernPathEligible( *resourceRecord ) ) {
		return false;
	}
	const pbrMaterialInfo_t &info = material->GetPBRInfo();
	// Quake 4 AGB normals deliberately retain the bump/RXGB upload path.
	// RGB/RG normals bypass that swizzle through material-data storage.
	const int normalUsage =
		info.normalFormat == PBR_NORMAL_QUAKE4_AGB ? TD_BUMP : TD_MATERIAL_DATA;
	if ( !info.enabled || info.workflow != PBR_WORKFLOW_METALLIC_ROUGHNESS
			|| !info.albedo.present
			|| ( info.emissive.present
				&& ( !R_MaterialResourceTable_PBREmissivePathEligible( *resourceRecord )
					|| !R_PBRNative_ImageReady( info.emissive.image, TD_PBR_COLOR ) ) )
			|| !R_PBRNative_ImageReady( info.albedo.image, TD_PBR_COLOR )
			|| ( info.normal.present && ( info.normalFormat < PBR_NORMAL_QUAKE4_AGB
				|| info.normalFormat > PBR_NORMAL_TANGENT_XYZ
				|| !R_PBRNative_ImageReady( info.normal.image, normalUsage ) ) )
			|| ( info.orm.present && !R_PBRNative_ImageReady( info.orm.image, TD_MATERIAL_DATA ) )
			|| ( info.metallic.present && !R_PBRNative_ImageReady( info.metallic.image, TD_MATERIAL_DATA ) )
			|| ( info.roughness.present && !R_PBRNative_ImageReady( info.roughness.image, TD_MATERIAL_DATA ) )
			|| ( info.ao.present && !R_PBRNative_ImageReady( info.ao.image, TD_MATERIAL_DATA ) ) ) {
		return false;
	}

	// Unused slots still need valid images. The flags keep their placeholder
	// images out of the material evaluation.
	out.normalImage = info.normal.present ? info.normal.image : globalImages->flatNormalMap;
	out.albedoImage = info.albedo.image;
	out.dataImage = info.orm.present ? info.orm.image : ( info.roughness.present ? info.roughness.image : globalImages->whiteImage );
	out.metallicImage = info.metallic.present ? info.metallic.image : NULL;
	out.aoImage = info.ao.present ? info.ao.image : NULL;
	out.emissiveImage = info.emissive.present ? info.emissive.image : NULL;
	out.dataFlags = ( info.orm.present ? 1 : 0 ) | ( info.metallic.present ? 2 : 0 ) | ( info.roughness.present ? 4 : 0 );
	out.normalFormat = info.normal.present ? (int)info.normalFormat + 1 : 0;
	out.metallic = idMath::ClampFloat( 0.0f, 1.0f,
		R_PBRNative_RegisterValue( surf, info.metallicRegister, 0.0f ) );
	out.roughness = idMath::ClampFloat( 0.0f, 1.0f,
		R_PBRNative_RegisterValue( surf, info.roughnessRegister, 0.5f ) );
	out.normalScale = idMath::ClampFloat( 0.0f, 4.0f,
		R_PBRNative_RegisterValue( surf, info.normalScaleRegister, 1.0f ) );
	out.ao = idMath::ClampFloat( 0.0f, 1.0f,
		R_PBRNative_RegisterValue( surf, info.aoRegister, 1.0f ) );
	for ( int component = 0; component < 3; ++component ) {
		out.emissiveColor[component] = Max( 0.0f,
			R_PBRNative_RegisterValue( surf, info.emissiveColorRegisters[component], 0.0f ) );
	}
	return true;
}

bool R_PBRNative_IsReplacedEmissionStage( const drawSurf_t *surf, int stageIndex ) {
	if ( surf == NULL || surf->material == NULL || !surf->material->GetPBRInfo().emissive.present ) {
		return false;
	}
	const materialResourceTableRecord_t *record =
		R_MaterialResourceTable_FindRecordForMaterial( surf->material );
	if ( record == NULL ) {
		return false;
	}
	const materialResourceTextureBinding_t *fallback =
		R_MaterialResourceTable_TextureBindingForSemantic( *record, MATERIAL_RESOURCE_TEXTURE_EMISSIVE );
	return fallback != NULL && fallback->stageIndex == stageIndex;
}
