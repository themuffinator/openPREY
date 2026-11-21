/*
===========================================================================

Doom 3 GPL Source Code
Copyright (C) 1999-2011 id Software LLC, a ZeniMax Media company.

This file is part of the Doom 3 GPL Source Code (?Doom 3 Source Code?).

Doom 3 Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Doom 3 Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Doom 3 Source Code.  If not, see <http://www.gnu.org/licenses/>.

In addition, the Doom 3 Source Code is also subject to certain additional terms. You should have received a copy of these additional terms immediately following the terms and conditions of the GNU General Public License which accompanied the Doom 3 Source Code.  If not, please request a copy in writing from id Software at the address below.

If you have questions concerning this license or the applicable additional terms, you may contact in writing id Software LLC, c/o ZeniMax Media Inc., Suite 120, Rockville, Maryland 20850 USA.

===========================================================================
*/

#include "DeviceContext.h"
#include "Window.h"
#include "UserInterfaceLocal.h"
#include "RenderWindow.h"

namespace {

static idMat3 RenderWindowRotationToAxis( const idWinVec4 &rotation ) {
	return idAngles( rotation.x(), rotation.y(), rotation.z() ).ToMat3();
}

template <typename T>
static int RenderWindowGetSurfaceMask( const T *model, const char *surfaceName ) {
	if constexpr ( requires( const T &renderModel ) { renderModel.GetSurfaceMask( surfaceName ); } ) {
		return ( model != NULL ) ? model->GetSurfaceMask( surfaceName ) : 0;
	}

	return 0;
}

static void RenderWindowInitShaderParms( renderEntity_t &renderEntity ) {
	renderEntity.shaderParms[0] = 1.0f;
	renderEntity.shaderParms[1] = 1.0f;
	renderEntity.shaderParms[2] = 1.0f;
	renderEntity.shaderParms[3] = 1.0f;
}

static bool RenderWindowResolveViewport( idDeviceContext *dc, const idRectangle &drawRect, int &x, int &y, int &width, int &height, float &fovY ) {
	float viewportX = drawRect.x;
	float viewportY = drawRect.y;
	float viewportW = drawRect.w;
	float viewportH = drawRect.h;

	if ( viewportW <= 0.0f || viewportH <= 0.0f ) {
		return false;
	}

	// Match normal GUI drawing: clip in authored GUI space, then apply the menu's aspect correction.
	if ( dc != NULL && dc->ClippedCoords( &viewportX, &viewportY, &viewportW, &viewportH, NULL, NULL, NULL, NULL ) ) {
		return false;
	}

	if ( viewportW <= 0.0f || viewportH <= 0.0f ) {
		return false;
	}

	const float authoredAspect = viewportH / viewportW;
	fovY = 2.0f * atan( authoredAspect ) * idMath::M_RAD2DEG;

	if ( dc != NULL ) {
		dc->AdjustCoords( &viewportX, &viewportY, &viewportW, &viewportH );

		const float uiViewportWidth = static_cast<float>( engineWindowState.uiViewportWidth );
		const float uiViewportHeight = static_cast<float>( engineWindowState.uiViewportHeight );
		const float framebufferWidth = static_cast<float>( engineWindowState.vidWidth );
		const float framebufferHeight = static_cast<float>( engineWindowState.vidHeight );
		if ( uiViewportWidth > 0.0f && uiViewportHeight > 0.0f && framebufferWidth > 0.0f && framebufferHeight > 0.0f ) {
			const float uiScaleX = uiViewportWidth / static_cast<float>( VIRTUAL_WIDTH );
			const float uiScaleY = uiViewportHeight / static_cast<float>( VIRTUAL_HEIGHT );

			const float physicalX = static_cast<float>( engineWindowState.uiViewportX ) + ( viewportX * uiScaleX );
			const float physicalY = static_cast<float>( engineWindowState.uiViewportY ) + ( viewportY * uiScaleY );
			const float physicalW = viewportW * uiScaleX;
			const float physicalH = viewportH * uiScaleY;

			viewportX = physicalX * ( static_cast<float>( VIRTUAL_WIDTH ) / framebufferWidth );
			viewportY = physicalY * ( static_cast<float>( VIRTUAL_HEIGHT ) / framebufferHeight );
			viewportW = physicalW * ( static_cast<float>( VIRTUAL_WIDTH ) / framebufferWidth );
			viewportH = physicalH * ( static_cast<float>( VIRTUAL_HEIGHT ) / framebufferHeight );
		}
	}

	width = Max( 1, idMath::Ftoi( viewportW + 0.5f ) );
	height = Max( 1, idMath::Ftoi( viewportH + 0.5f ) );
	x = idMath::Ftoi( viewportX );
	y = idMath::Ftoi( viewportY );
	return true;
}

/*
================
RenderWindowResolveCanvasView

"canvasfill 1". The scene keeps the projection its rect defines, centred on
the rect with the 90 degree horizontal field every renderDef uses, but is drawn
across the whole canvas, aspect expansion included, through an off-axis
frustum. The main menu pins its portal rim to the leading screen edge; drawn
inside its rect, the portal's view, and the shimmer it lays over the backdrop,
would stop at the rect's trailing edge.

Returns false, and the caller draws the rect alone, when the rect is too small
for the canvas to stay inside the renderer's tangent limit: the portal opening
grows from a point.
================
*/
static bool RenderWindowResolveCanvasView( idDeviceContext *dc, const idRectangle &drawRect,
		float forceAspectWidth, float forceAspectHeight, renderView_t &view, float fovY = 0.0f ) {
	if ( dc == NULL || drawRect.w <= 0.0f || drawRect.h <= 0.0f ) {
		return false;
	}

	float xExpand = 0.0f;
	float yExpand = 0.0f;
	dc->GetVirtualScreenExpansion( forceAspectWidth, forceAspectHeight, xExpand, yExpand );
	const idRectangle canvas( -xExpand, -yExpand, VIRTUAL_WIDTH + 2.0f * xExpand, VIRTUAL_HEIGHT + 2.0f * yExpand );

	// The frustum has to describe the viewport as it will be clipped.
	float clipX = canvas.x;
	float clipY = canvas.y;
	float clipW = canvas.w;
	float clipH = canvas.h;
	if ( dc->ClippedCoords( &clipX, &clipY, &clipW, &clipH, NULL, NULL, NULL, NULL ) || clipW <= 0.0f || clipH <= 0.0f ) {
		return false;
	}

	// A 90 degree horizontal field puts a tangent of 1 at the rect's sides;
	// GUI y runs down, a frustum's up. openPREY: "fovY" puts tan( fovY / 2 )
	// at the rect's top and bottom instead.
	const float unitsPerTangent = fovY > 0.0f ? drawRect.h * 0.5f / idMath::Tan( DEG2RAD( fovY ) * 0.5f ) : drawRect.w * 0.5f;
	const float centreX = drawRect.x + drawRect.w * 0.5f;
	const float centreY = drawRect.y + drawRect.h * 0.5f;
	const float tanLeft = ( clipX - centreX ) / unitsPerTangent;
	const float tanRight = ( clipX + clipW - centreX ) / unitsPerTangent;
	const float tanUp = ( centreY - clipY ) / unitsPerTangent;
	const float tanDown = ( centreY - ( clipY + clipH ) ) / unitsPerTangent;

	// The renderer drops an off-axis frustum with a tangent past 30
	// (R_ViewFovTangentsValid); keep clear of that limit.
	const float tangentLimit = 25.0f;
	if ( tanLeft >= tanRight || tanDown >= tanUp ||
			idMath::Fabs( tanLeft ) > tangentLimit || idMath::Fabs( tanRight ) > tangentLimit ||
			idMath::Fabs( tanUp ) > tangentLimit || idMath::Fabs( tanDown ) > tangentLimit ) {
		return false;
	}

	float canvasFovY = 0.0f;
	if ( !RenderWindowResolveViewport( dc, canvas, view.x, view.y, view.width, view.height, canvasFovY ) ) {
		return false;
	}

	view.asymmetricFov = true;
	view.fovTanLeft = tanLeft;
	view.fovTanRight = tanRight;
	view.fovTanUp = tanUp;
	view.fovTanDown = tanDown;
	// fov_x and fov_y hold the enclosing field for consumers that only estimate.
	view.fov_x = 2.0f * RAD2DEG( idMath::ATan( Max( -tanLeft, tanRight ) ) );
	view.fov_y = 2.0f * RAD2DEG( idMath::ATan( Max( tanUp, -tanDown ) ) );
	return true;
}

static bool RenderWindowNeedsPreviewBounds( const idBounds &bounds ) {
	if ( bounds.IsCleared() ) {
		return true;
	}

	return bounds[0].Compare( bounds[1] );
}

static void RenderWindowEnsurePreviewBounds( renderEntity_t &renderEntity ) {
	if ( renderEntity.hModel == NULL || !RenderWindowNeedsPreviewBounds( renderEntity.bounds ) ) {
		return;
	}

	renderEntity.bounds = idBounds( idVec3( -128.0f, -128.0f, -128.0f ), idVec3( 128.0f, 128.0f, 128.0f ) );
}

static idVec4 RenderWindowVec4( const idWinVec4 &value ) {
	return idVec4( value.x(), value.y(), value.z(), value.w() );
}

static void RenderWindowApplyPreviewEffects( renderEntity_t &renderEntity, const idVec4 &outline, const float width, const idVec4 &rimlight, const idVec4 &brightSkin ) {
	renderEntity.outlineColor = outline;
	renderEntity.rimlightColor = rimlight;
	renderEntity.brightSkinColor = brightSkin;
	renderEntity.outlineWidth = idMath::ClampFloat( 0.0f, 6.0f, width );
	renderEntity.outlineFlags = 0;
}

/*
================
The scene camera (openPREY)

The main menu's 3D backdrop (docs/dev/prey-ui-visual-design.md, section 12.2)
draws the Sphere and Earth under one camera that opens close on the Sphere and
swings round it as it pulls back to the rest frame. A renderDef describes the
curve with these keys, in its world's units:

	orbitCenter		the body the camera circles
	orbitFrom/To	the camera's direction from it (xyz) and distance (w) at the
					start and at rest
	orbitAimFrom/To	the point it looks at, at the start and at rest
	orbitShape		the body's radius, the move's length in ms, and the stock
					interpolator's acceleration and deceleration fractions
	orbitPlay		set nonzero to start the move; orbitSkip to end it at once

One eased progress e drives it. The direction swings along the great arc,
the body's apparent radius falls geometrically (so sqrt( d * d - R * R )
does), and the aim moves in a straight line; world up stays up, so the camera
never rolls. Before a move, after it, and under reduced motion the camera is
at rest.

"sceneKey" names the GUI state the window keeps: <key>_ok (the scene can
draw), <key>_motion (motion is allowed), <key>_moving, and <key>_x and
<key>_y, the shift in canvas units of a point at infinity since the rest
frame, which slides the 2D star layers with the camera's heading.
================
*/
idCVar ui_menuScene( "ui_menuScene", "1", CVAR_GUI | CVAR_BOOL | CVAR_ARCHIVE,
	"the main menu's backdrop: 1 the 3D Sphere and Earth, 0 the stock painting (takes effect when the menu loads)" );
idCVar ui_menuSceneProbe( "ui_menuSceneProbe", "-1", CVAR_GUI | CVAR_INTEGER | CVAR_NOCHEAT,
	"diagnostic: hold the main menu's 3D backdrop camera this many ms into its entrance, for screenshots; -1 off", -1, 100000 );

static bool RenderWindowReducedMotion() {
	return cvarSystem->GetCVarBool( "ui_retainedReducedMotion" );
}

// The stock GUI interpolator's acceleration and deceleration as a progress map.
static float RenderWindowAccelDecel( float p, float accel, float decel ) {
	p = idMath::ClampFloat( 0.0f, 1.0f, p );
	accel = idMath::ClampFloat( 0.0f, 1.0f, accel );
	decel = idMath::ClampFloat( 0.0f, 1.0f - accel, decel );
	const float v = 1.0f / ( 1.0f - ( accel + decel ) * 0.5f );
	if ( accel > 0.0f && p < accel ) {
		return v * p * p / ( 2.0f * accel );
	}
	if ( decel > 0.0f && p > 1.0f - decel ) {
		return 1.0f - v * ( 1.0f - p ) * ( 1.0f - p ) / ( 2.0f * decel );
	}
	return v * ( p - accel * 0.5f );
}

// Rows forward, left and up, looking along `forward` with world z up.
static idMat3 RenderWindowLookAxis( const idVec3 &forward ) {
	idVec3 f = forward;
	if ( f.Normalize() <= 0.0f ) {
		return mat3_identity;
	}
	idVec3 left = idVec3( 0.0f, 0.0f, 1.0f ).Cross( f );
	if ( left.Normalize() <= 1e-6f ) {
		left.Set( 0.0f, 1.0f, 0.0f );
	}
	const idVec3 up = f.Cross( left );
	return idMat3( f, left, up );
}

}

idRenderWindow::idRenderWindow( idDeviceContext *d, idUserInterfaceLocal *g ) : idWindow( d, g ) {
	dc = d;
	gui = g;
	CommonInit();
}

idRenderWindow::idRenderWindow( idUserInterfaceLocal *g ) : idWindow( g ) {
	gui = g;
	CommonInit();
}

idRenderWindow::~idRenderWindow() {
	FreeModelJoints();
	if (renderSystem) renderSystem->FreeRenderWorld( world );
}

void idRenderWindow::FreeModelJoints() {
	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		if ( worldEntity[i].joints ) {
			Mem_Free16( worldEntity[i].joints );
			worldEntity[i].joints = NULL;
		}
	}
}

void idRenderWindow::CommonInit() {
	world = renderSystem->AllocRenderWorld();
	needsRender = true;

	for ( int i = 0; i < MAX_RENDERWINDOW_LIGHTS; ++i ) {
		lightOrigin[i] = idVec4( -128.0f, 0.0f, 0.0f, 1.0f );
		lightColor[i] = idVec4( 1.0f, 1.0f, 1.0f, 1.0f );
		lightRadius[i].Zero();
		lightDefs[i] = -1;
		useLight[i] = false;
		memset( &rLights[i], 0, sizeof( rLights[i] ) );
	}
	useLight[0] = true;

	modelOrigin.Zero();
	// RenderWindowRotationToAxis reads this every frame and nothing else
	// initialized it, so a .gui that never sets modelRotate oriented its model
	// from whatever the allocation happened to contain.
	modelRotate.Zero();
	viewOffset = idVec4( -128.0f, 0.0f, 0.0f, 1.0f );
	outlineColor.Zero();
	rimlightColor.Zero();
	brightSkinColor.Zero();
	outlineWidth = 2.0f;
	for ( auto &skin : customSkin ) skin = "";
	customShader = "NONE";
	needUpdate.Clear();

	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		modelAnim[i] = NULL;
		animLength[i] = 0;
		animEndTime[i] = -1;
		modelDef[i] = -1;
		memset( &worldEntity[i], 0, sizeof( worldEntity[i] ) );
	}

	updateAnimation = true;
	canvasFill = false;

	fovY = 0.0f;
	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		modelRotateN[i].Zero();
		modelSpin[i].Zero();
		modelFacing[i].Zero();
		modelOwnRotate[i] = false;
	}
	sceneOrigin.Zero();
	sceneAxis.Identity();
	orbitCenter.Zero();
	orbitFrom.Zero();
	orbitTo.Zero();
	orbitAimFrom.Zero();
	orbitAimTo.Zero();
	orbitShape = idVec4( 1.0f, 1000.0f, 0.0f, 0.0f );
	orbitPlay = 0.0f;
	orbitSkip = 0.0f;
	sceneKey = "";
	orbitEnabled = false;
	orbitStarted = false;
	orbitArmed = false;
	orbitStart = 0;
	restTime = -1;
}

void idRenderWindow::BuildAnimation( int time ) {
	if ( !updateAnimation ) {
		return;
	}

	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		renderEntity_t &renderEntity = worldEntity[i];
		renderEntity.suppressSurfaceMask = 0;

		if ( !renderEntity.hModel || !animName[i].Length() || !animClass[i].Length() ) {
			continue;
		}

		renderEntity.numJoints = renderEntity.hModel->NumJoints();
		if ( renderEntity.numJoints <= 0 ) {
			continue;
		}

		renderEntity.joints = static_cast<idJointMat *>( Mem_Alloc16( renderEntity.numJoints * sizeof( *renderEntity.joints ) ) );

		const idDict *animDef = gameEdit->FindEntityDefDict( animClass[i].c_str(), false );
		if ( animDef ) {
			for ( const idKeyValue *kv = animDef->MatchPrefix( "hidesurface", NULL ); kv; kv = animDef->MatchPrefix( "hidesurface", kv ) ) {
				if ( kv->GetValue().Length() ) {
					renderEntity.suppressSurfaceMask |= RenderWindowGetSurfaceMask( renderEntity.hModel, kv->GetValue().c_str() );
				}
			}
		}

		modelAnim[i] = gameEdit->ANIM_GetAnimFromEntityDef( animClass[i].c_str(), animName[i].c_str() );
		if ( modelAnim[i] ) {
			animLength[i] = gameEdit->ANIM_GetLength( modelAnim[i] );
			animEndTime[i] = time + animLength[i];
		}
	}

	updateAnimation = false;
}

void idRenderWindow::UpdateRenderVars() {
	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		modelName[i].Update();
		jointName[i].Update();
		animName[i].Update();
		animClass[i].Update();
		customSkin[i].Update();
	}

	for ( int i = 0; i < MAX_RENDERWINDOW_LIGHTS; ++i ) {
		lightOrigin[i].Update();
		lightColor[i].Update();
		lightRadius[i].Update();
	}

	modelOrigin.Update();
	modelRotate.Update();
	viewOffset.Update();
	outlineColor.Update();
	rimlightColor.Update();
	brightSkinColor.Update();
	outlineWidth.Update();
	customShader.Update();

	fovY.Update();
	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		modelRotateN[i].Update();
		modelSpin[i].Update();
		modelFacing[i].Update();
	}
	orbitCenter.Update();
	orbitFrom.Update();
	orbitTo.Update();
	orbitAimFrom.Update();
	orbitAimTo.Update();
	orbitShape.Update();
	orbitPlay.Update();
	orbitSkip.Update();
	sceneKey.Update();
}

void idRenderWindow::PreRender() {
	if ( !needsRender ) {
		return;
	}

	world->InitFromMap( NULL );

	idDict spawnArgs;
	for ( int i = 0; i < MAX_RENDERWINDOW_LIGHTS; ++i ) {
		lightDefs[i] = -1;
		if ( !useLight[i] ) {
			continue;
		}

		spawnArgs.Clear();
		spawnArgs.Set( "classname", "light" );
		spawnArgs.Set( "name", va( "light_%d", i ) );
		spawnArgs.Set( "origin", lightOrigin[i].ToVec3().ToString() );
		spawnArgs.Set( "_color", lightColor[i].ToVec3().ToString() );
		if ( lightRadius[i].ToVec3() != vec3_origin ) {
			spawnArgs.Set( "light_radius", lightRadius[i].ToVec3().ToString() );
		}
		gameEdit->ParseSpawnArgsToRenderLight( &spawnArgs, &rLights[i] );
		lightDefs[i] = world->AddLightDef( &rLights[i] );
	}

	if ( !modelName[0].Length() ) {
		common->Warning( "Window '%s' in gui '%s': no model set", GetName(), GetGui()->GetSourceFile() );
	}

	FreeModelJoints();
	memset( worldEntity, 0, sizeof( worldEntity ) );

	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		modelAnim[i] = NULL;
		animLength[i] = 0;
		animEndTime[i] = -1;
		modelDef[i] = -1;
	}

	const idMat3 baseAxis = RenderWindowRotationToAxis( modelRotate );

	spawnArgs.Clear();
	spawnArgs.Set( "classname", "func_static" );
	spawnArgs.Set( "model", modelName[0].c_str() );
	spawnArgs.Set( "skin", customSkin[0].c_str() );
	spawnArgs.Set( "origin", modelOrigin.c_str() );
	gameEdit->ParseSpawnArgsToRenderEntity( &spawnArgs, &worldEntity[0] );
	if ( worldEntity[0].hModel ) {
		RenderWindowEnsurePreviewBounds( worldEntity[0] );
		worldEntity[0].axis = baseAxis;
		RenderWindowInitShaderParms( worldEntity[0] );
		RenderWindowApplyPreviewEffects( worldEntity[0], RenderWindowVec4( outlineColor ), outlineWidth, RenderWindowVec4( rimlightColor ), RenderWindowVec4( brightSkinColor ) );
		if ( customShader.Length() && idStr::Icmp( customShader.c_str(), "NONE" ) != 0 ) {
			worldEntity[0].customShader = declManager->FindMaterial( customShader.c_str() );
		}
		modelDef[0] = world->AddEntityDef( &worldEntity[0] );
	}

	for ( int i = 1; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		if ( !modelName[i].Length() ) {
			continue;
		}

		spawnArgs.Clear();
		spawnArgs.Set( "classname", "func_static" );
		spawnArgs.Set( "model", modelName[i].c_str() );
		spawnArgs.Set( "skin", customSkin[i].c_str() );
		spawnArgs.Set( "origin", "0 0 0" );
		gameEdit->ParseSpawnArgsToRenderEntity( &spawnArgs, &worldEntity[i] );
		if ( !worldEntity[i].hModel ) {
			continue;
		}

		RenderWindowEnsurePreviewBounds( worldEntity[i] );
		worldEntity[i].axis = modelOwnRotate[i] ? ModelAxis( i, 0 ) : baseAxis;
		RenderWindowInitShaderParms( worldEntity[i] );
		RenderWindowApplyPreviewEffects( worldEntity[i], RenderWindowVec4( outlineColor ), outlineWidth, RenderWindowVec4( rimlightColor ), RenderWindowVec4( brightSkinColor ) );
		if ( customShader.Length() && idStr::Icmp( customShader.c_str(), "NONE" ) != 0 ) {
			worldEntity[i].customShader = declManager->FindMaterial( customShader.c_str() );
		}
		modelDef[i] = world->AddEntityDef( &worldEntity[i] );
	}

	world->PushMarkedDefs();
	needsRender = false;
}

void idRenderWindow::Render( int time ) {
	for ( int i = 0; i < MAX_RENDERWINDOW_LIGHTS; ++i ) {
		if ( !useLight[i] || lightDefs[i] == -1 ) {
			continue;
		}

		rLights[i].origin = lightOrigin[i].ToVec3();
		rLights[i].shaderParms[SHADERPARM_RED] = lightColor[i].x();
		rLights[i].shaderParms[SHADERPARM_GREEN] = lightColor[i].y();
		rLights[i].shaderParms[SHADERPARM_BLUE] = lightColor[i].z();
		world->UpdateLightDef( lightDefs[i], &rLights[i] );
	}

	if ( !worldEntity[0].hModel ) {
		return;
	}

	if ( updateAnimation ) {
		BuildAnimation( time );
	}

	if ( modelAnim[0] && worldEntity[0].joints ) {
		if ( time > animEndTime[0] ) {
			animEndTime[0] = time + animLength[0];
		}
		gameEdit->ANIM_CreateAnimFrame(
			worldEntity[0].hModel,
			modelAnim[0],
			worldEntity[0].numJoints,
			worldEntity[0].joints,
			time + animLength[0] - animEndTime[0],
			vec3_origin,
			false );
	}

	worldEntity[0].origin = modelOrigin.ToVec3();
	worldEntity[0].axis = RenderWindowRotationToAxis( modelRotate );
	RenderWindowApplyPreviewEffects( worldEntity[0], RenderWindowVec4( outlineColor ), outlineWidth, RenderWindowVec4( rimlightColor ), RenderWindowVec4( brightSkinColor ) );
	if ( modelDef[0] != -1 ) {
		world->UpdateEntityDef( modelDef[0], &worldEntity[0] );
	}

	for ( int i = 1; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		if ( !worldEntity[i].hModel ) {
			continue;
		}

		if ( modelAnim[i] && worldEntity[i].joints ) {
			if ( time > animEndTime[i] ) {
				animEndTime[i] = time + animLength[i];
			}
			gameEdit->ANIM_CreateAnimFrame(
				worldEntity[i].hModel,
				modelAnim[i],
				worldEntity[i].numJoints,
				worldEntity[i].joints,
				time + animLength[i] - animEndTime[i],
				vec3_origin,
				false );
		}

		if ( worldEntity[0].joints && jointName[i].Length() ) {
			const jointHandle_t joint = worldEntity[0].hModel->GetJointHandle( jointName[i].c_str() );
			if ( joint != INVALID_JOINT ) {
				const idJointMat &jointTransform = worldEntity[0].joints[joint];
				worldEntity[i].origin = worldEntity[0].origin + jointTransform.ToVec3() * worldEntity[0].axis;
				worldEntity[i].axis = jointTransform.ToMat3();
				worldEntity[i].axis *= worldEntity[0].axis;
			}
		}

		if ( modelOwnRotate[i] && ( !worldEntity[0].joints || !jointName[i].Length() ) ) {
			worldEntity[i].axis = ModelAxis( i, time );
			if ( modelFacing[i].y() > 0.0f ) {
				// A billboard on the orbited body's camera side, sized against
				// the body's apparent radius: tan = size * R / sqrt( d * d - R * R ).
				const idVec3 centre = orbitCenter.ToVec3();
				idVec3 toCamera = sceneOrigin - centre;
				const float d = toCamera.Normalize();
				const float radius = Max( 1e-3f, orbitShape.x() );
				const float lift = modelFacing[i].x();
				if ( d > radius && d > lift ) {
					const float half = modelFacing[i].y() * radius * ( d - lift ) / idMath::Sqrt( d * d - radius * radius );
					worldEntity[i].origin = centre + toCamera * lift;
					worldEntity[i].axis = sceneAxis * half;
				}
			}
		}

		RenderWindowApplyPreviewEffects( worldEntity[i], RenderWindowVec4( outlineColor ), outlineWidth, RenderWindowVec4( rimlightColor ), RenderWindowVec4( brightSkinColor ) );
		if ( modelDef[i] != -1 ) {
			world->UpdateEntityDef( modelDef[i], &worldEntity[i] );
		}
	}

	world->PushMarkedDefs();
}

void idRenderWindow::Draw( int time, float x, float y ) {
	if ( needUpdate.Length() && gui->GetStateBool( needUpdate.c_str(), "0" ) ) {
		needsRender = true;
		updateAnimation = true;
		gui->SetStateBool( needUpdate.c_str(), false );
	}

	UpdateRenderVars();
	if ( orbitEnabled ) {
		// The move starts, or ends, on the frame its key is set.
		const int length = Max( 1, idMath::Ftoi( orbitShape.y() ) );
		// The first frame of a move pays for the scene's first draw (its images
		// and the menu's own first frame), which took a third of a second; the
		// clock starts on the frame after, and the GUI hears <key>_start then
		// so its own timeline keeps step with the camera.
		bool startEvent = false;
		if ( orbitPlay != 0.0f ) {
			if ( cvarSystem->GetCVarBool( "ui_retainedTrace" ) ) {
				common->Printf( "MENU_SCENE play at=%d\n", time );
			}
			orbitPlay = 0.0f;
			orbitStarted = true;
			orbitArmed = true;
			orbitStart = time;
			restTime = time + length;
		} else if ( orbitArmed ) {
			orbitArmed = false;
			orbitStart = time;
			restTime = time + length;
			startEvent = true;
		}
		if ( orbitSkip != 0.0f ) {
			if ( cvarSystem->GetCVarBool( "ui_retainedTrace" ) ) {
				common->Printf( "MENU_SCENE skip at=%d armed=%d started=%d\n", time, orbitArmed ? 1 : 0, orbitStarted ? 1 : 0 );
			}
			orbitSkip = 0.0f;
			orbitArmed = false;
			startEvent = false;
			if ( orbitStarted && time < orbitStart + length ) {
				orbitStart = time - length;
				restTime = time;
			}
		}
		if ( startEvent && sceneKey.Length() && gui != NULL ) {
			gui->HandleNamedEvent( va( "%s_start", sceneKey.c_str() ) );
		}
	}
	if ( restTime < 0 ) {
		restTime = time;
	}
	PreRender();
	sceneOrigin = viewOffset.ToVec3();
	sceneAxis.Identity();
	if ( orbitEnabled ) {
		ResolveOrbitView( time, sceneOrigin, sceneAxis );
	}
	// Reduced motion holds the scene: no turn, and its materials' time stands.
	const bool still = orbitEnabled && RenderWindowReducedMotion();
	Render( still ? 0 : time );

	memset( &refdef, 0, sizeof( refdef ) );
	refdef.vieworg = sceneOrigin;
	refdef.viewaxis = sceneAxis;
	refdef.shaderParms[0] = 1.0f;
	refdef.shaderParms[1] = 1.0f;
	refdef.shaderParms[2] = 1.0f;
	refdef.shaderParms[3] = 1.0f;
	const float sceneFovY = fovY;
	if ( !canvasFill || !RenderWindowResolveCanvasView( dc, drawRect, forceAspectWidth, forceAspectHeight, refdef, sceneFovY ) ) {
		if ( !RenderWindowResolveViewport( dc, drawRect, refdef.x, refdef.y, refdef.width, refdef.height, refdef.fov_y ) ) {
			return;
		}
		if ( sceneFovY > 0.0f ) {
			refdef.fov_y = sceneFovY;
			refdef.fov_x = 2.0f * RAD2DEG( idMath::ATan( idMath::Tan( DEG2RAD( sceneFovY ) * 0.5f ) * drawRect.w / Max( 1.0f, drawRect.h ) ) );
		} else {
			refdef.fov_x = 90.0f;
		}
	}
	refdef.time = still ? 0 : time;
	PublishSceneState( time, orbitEnabled ? &refdef.viewaxis : NULL );
	if ( orbitEnabled && orbitStarted && time <= orbitStart + idMath::Ftoi( orbitShape.y() ) + 100 &&
			cvarSystem->GetCVarBool( "ui_retainedTrace" ) ) {
		common->Printf( "MENU_SCENE t=%d e=%.3f cam=%.1f %.1f %.1f\n", time - orbitStart, OrbitProgress( time ),
			refdef.vieworg.x, refdef.vieworg.y, refdef.vieworg.z );
	}
	world->RenderScene( &refdef );
}

/*
================
idRenderWindow::ModelAxis

A model with its own rotation (modelRotateN), turned about its local spin
axis once in modelSpinN's w seconds from when the camera rests.
================
*/
idMat3 idRenderWindow::ModelAxis( int model, int time ) const {
	const idMat3 base = RenderWindowRotationToAxis( modelRotateN[model] );
	const idVec4 &spin = modelSpin[model];
	if ( spin.w <= 0.0f || restTime < 0 || time <= restTime || RenderWindowReducedMotion() || ui_menuSceneProbe.GetInteger() >= 0 ) {
		return base;
	}
	idVec3 spinAxis = spin.ToVec3();
	if ( spinAxis.Normalize() <= 0.0f ) {
		return base;
	}
	const float seconds = static_cast<float>( time - restTime ) * 0.001f;
	const float degrees = idMath::AngleNormalize360( seconds / spin.w * 360.0f );
	return idRotation( vec3_origin, spinAxis, degrees ).ToMat3() * base;
}

float idRenderWindow::OrbitProgress( int time ) const {
	const float length = Max( 1.0f, orbitShape.y() );
	if ( ui_menuSceneProbe.GetInteger() >= 0 ) {
		return RenderWindowAccelDecel( static_cast<float>( ui_menuSceneProbe.GetInteger() ) / length, orbitShape.z(), orbitShape.w() );
	}
	if ( !orbitStarted || RenderWindowReducedMotion() ) {
		return 1.0f;
	}
	const float p = static_cast<float>( time - orbitStart ) / length;
	return RenderWindowAccelDecel( p, orbitShape.z(), orbitShape.w() );
}

bool idRenderWindow::ResolveOrbitView( int time, idVec3 &origin, idMat3 &axis ) const {
	const float e = OrbitProgress( time );
	const idVec3 centre = orbitCenter.ToVec3();
	idVec3 from = orbitFrom.ToVec3();
	idVec3 to = orbitTo.ToVec3();
	if ( from.Normalize() <= 0.0f || to.Normalize() <= 0.0f ) {
		return false;
	}
	const float radius = Max( 1e-3f, orbitShape.x() );
	const float q0 = idMath::Sqrt( Max( 1e-6f, orbitFrom.w() * orbitFrom.w() / ( radius * radius ) - 1.0f ) );
	const float q1 = idMath::Sqrt( Max( 1e-6f, orbitTo.w() * orbitTo.w() / ( radius * radius ) - 1.0f ) );
	const float q = q0 * idMath::Pow( q1 / q0, e );
	const float distance = radius * idMath::Sqrt( 1.0f + q * q );

	const float arc = idMath::ACos( idMath::ClampFloat( -1.0f, 1.0f, from * to ) );
	idVec3 direction = to;
	if ( arc > 1e-4f ) {
		const float k = idMath::Sin( arc );
		direction = from * ( idMath::Sin( ( 1.0f - e ) * arc ) / k ) + to * ( idMath::Sin( e * arc ) / k );
	}
	origin = centre + direction * distance;
	const idVec3 aim = orbitAimFrom.ToVec3() + ( orbitAimTo.ToVec3() - orbitAimFrom.ToVec3() ) * e;
	axis = RenderWindowLookAxis( aim - origin );
	return true;
}

bool idRenderWindow::SceneAvailable() {
	if ( !ui_menuScene.GetBool() || renderModelManager == NULL ) {
		return false;
	}
	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		if ( !modelName[i].Length() ) {
			continue;
		}
		idRenderModel *model = renderModelManager->CheckModel( modelName[i].c_str() );
		if ( model == NULL || model->IsDefaultModel() ) {
			return false;
		}
	}
	return modelName[0].Length() > 0;
}

void idRenderWindow::PublishSceneState( int time, const idMat3 *viewAxis ) {
	if ( !sceneKey.Length() || gui == NULL ) {
		return;
	}
	const char *key = sceneKey.c_str();
	gui->SetStateBool( va( "%s_motion", key ), !RenderWindowReducedMotion() );
	gui->SetStateBool( va( "%s_moving", key ), orbitEnabled && OrbitProgress( time ) < 1.0f );
	float shiftX = 0.0f;
	float shiftY = 0.0f;
	if ( viewAxis != NULL && fovY > 0.0f ) {
		// The rest camera's axes, and this frame's heading in them.
		idVec3 restDirection = orbitTo.ToVec3();
		restDirection.Normalize();
		const idVec3 restOrigin = orbitCenter.ToVec3() + restDirection * orbitTo.w();
		const idMat3 rest = RenderWindowLookAxis( orbitAimTo.ToVec3() - restOrigin );
		const idVec3 &forward = ( *viewAxis )[0];
		const float right = -( forward * rest[1] );
		const float up = forward * rest[2];
		const float ahead = forward * rest[0];
		const float yaw = idMath::ATan( right, ahead );
		const float pitch = idMath::ATan( up, idMath::Sqrt( right * right + ahead * ahead ) );
		// Canvas units per unit of tangent: the 480 u canvas spans fovY.
		const float focal = 240.0f / idMath::Tan( DEG2RAD( fovY ) * 0.5f );
		shiftX = -focal * idMath::Tan( yaw );
		shiftY = focal * idMath::Tan( pitch );
	}
	gui->SetStateFloat( va( "%s_x", key ), shiftX );
	gui->SetStateFloat( va( "%s_y", key ), shiftY );
}

void idRenderWindow::RefreshForLevelLoad() {
    idWindow::RefreshForLevelLoad();
    const bool hadModel = modelDef[0] != -1;
    needsRender = true;
    updateAnimation = true;
    if (hadModel && gameEdit) {
        UpdateRenderVars();
        PreRender();
        BuildAnimation(gui->GetTime());
    }
}

void idRenderWindow::ConfigureModelScene( const openq4::ui::ModelScene &scene ) {
	const bool rebuild = !sceneConfigured || configuredScene.parts != scene.parts || configuredScene.lights.size() != scene.lights.size();
	for ( int i = 0; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		const auto part = i < scene.parts.size() ? scene.parts[i] : openq4::ui::ModelPart{};
		modelName[i] = part.model.c_str(); customSkin[i] = part.skin.c_str();
		animName[i] = part.animation.c_str(); animClass[i] = part.animationClass.c_str(); jointName[i] = part.joint.c_str();
	}
	const auto vector = [](const auto &value) { return idVec4(float(value[0]),float(value[1]),float(value[2]),1); };
	for ( int i = 0; i < MAX_RENDERWINDOW_LIGHTS; ++i ) {
		useLight[i] = i < scene.lights.size();
		if ( useLight[i] ) { lightOrigin[i] = vector(scene.lights[i].origin); lightColor[i] = vector(scene.lights[i].colour); }
	}
	modelOrigin = vector(scene.origin); modelRotate = vector(scene.rotation); viewOffset = vector(scene.camera);
	outlineColor = idVec4(float(scene.outline[0]),float(scene.outline[1]),float(scene.outline[2]),float(scene.outline[3]));
	rimlightColor = idVec4(float(scene.rimlight[0]),float(scene.rimlight[1]),float(scene.rimlight[2]),float(scene.rimlight[3]));
	brightSkinColor = idVec4(float(scene.brightSkin[0]),float(scene.brightSkin[1]),float(scene.brightSkin[2]),float(scene.brightSkin[3]));
	outlineWidth = float(scene.outlineWidth);
	if ( rebuild ) { needsRender = true; updateAnimation = true; }
	configuredScene = scene; sceneConfigured = true;
}

bool idRenderWindow::PrepareModelScene( int time, std::string &error ) {
	// The retained caller validates its typed scene before configuration. Keep
	// this legacy renderDef implementation independent of the retained library,
	// which is intentionally absent from dedicated-server links.
	if ( !gameEdit || !world || !sceneConfigured || configuredScene.parts.empty() || configuredScene.parts[0].model.empty() ) {
		if ( error.empty() ) error = "No game renderer or root model is available for the preview";
		return false;
	}
	PreRender();
	BuildAnimation(time);
	for ( size_t i = 0; i < configuredScene.parts.size(); ++i ) {
		const auto &part = configuredScene.parts[i];
		if ( part.model.empty() ) continue;
		if ( !worldEntity[i].hModel || worldEntity[i].hModel->IsDefaultModel() ) { error = "Preview model could not be loaded: " + part.model; return false; }
		if ( !part.skin.empty() ) {
			const auto *skin = declManager->FindSkin(part.skin.c_str(),false);
			if (!skin || skin->GetState()==DS_DEFAULTED) { error = "Preview skin could not be loaded: " + part.skin; return false; }
		}
		if ( !part.animation.empty() && (!modelAnim[i] || !worldEntity[i].joints) ) { error = "Preview animation could not be loaded: " + part.animation; return false; }
		if ( i && !part.joint.empty() && (!worldEntity[0].joints || worldEntity[0].hModel->GetJointHandle(part.joint.c_str()) == INVALID_JOINT) ) {
			error = "Preview attachment joint could not be found: " + part.joint; return false;
		}
	}
	return true;
}

void idRenderWindow::DrawModelScene( int time, float fov, int width, int height ) {
	Render(time);
	memset(&refdef,0,sizeof(refdef));
	refdef.vieworg = viewOffset.ToVec3(); refdef.viewaxis.Identity();
	for ( int i = 0; i < 4; ++i ) refdef.shaderParms[i] = 1;
	refdef.width = VIRTUAL_WIDTH; refdef.height = VIRTUAL_HEIGHT;
	refdef.fov_x = fov;
	refdef.fov_y = 2.0f * atan(tan(fov * idMath::M_DEG2RAD * .5f) * float(height) / float(width)) * idMath::M_RAD2DEG;
	refdef.time = time;
	world->RenderScene(&refdef,RF_NO_GUI | RF_INDEPENDENT_VIEW);
}

void idRenderWindow::PostParse() {
	idWindow::PostParse();
	sceneKey.Update();
	if ( sceneKey.Length() && gui != NULL ) {
		// Whether the menu draws this scene or its stock painting is decided as
		// it loads: a hidden renderDef never draws to find out.
		gui->SetStateBool( va( "%s_ok", sceneKey.c_str() ), SceneAvailable() );
		gui->SetStateBool( va( "%s_motion", sceneKey.c_str() ), !RenderWindowReducedMotion() );
		gui->SetStateFloat( va( "%s_x", sceneKey.c_str() ), 0.0f );
		gui->SetStateFloat( va( "%s_y", sceneKey.c_str() ), 0.0f );
	}
}

idWinVar *idRenderWindow::GetWinVarByName( const char *_name, bool fixup, drawWin_t **owner ) {
	if ( idStr::Icmp( _name, "model" ) == 0 ) {
		return &modelName[0];
	}
	if ( idStr::Icmp( _name, "anim" ) == 0 ) {
		return &animName[0];
	}
	if ( idStr::Icmp( _name, "animClass" ) == 0 ) {
		return &animClass[0];
	}

	for ( int i = 1; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		if ( idStr::Icmp( _name, va( "model%d", i ) ) == 0 ) {
			return &modelName[i];
		}
		if ( idStr::Icmp( _name, va( "joint%d", i ) ) == 0 ) {
			return &jointName[i];
		}
		if ( idStr::Icmp( _name, va( "anim%d", i ) ) == 0 ) {
			return &animName[i];
		}
		if ( idStr::Icmp( _name, va( "animClass%d", i ) ) == 0 ) {
			return &animClass[i];
		}
		if ( idStr::Icmp( _name, va( "skin%d", i ) ) == 0 ) {
			return &customSkin[i];
		}
	}

	if ( idStr::Icmp( _name, "lightOrigin" ) == 0 ) {
		useLight[0] = true;
		return &lightOrigin[0];
	}
	if ( idStr::Icmp( _name, "lightColor" ) == 0 ) {
		useLight[0] = true;
		return &lightColor[0];
	}

	for ( int i = 0; i < MAX_RENDERWINDOW_LIGHTS; ++i ) {
		if ( idStr::Icmp( _name, va( "lightOrigin%d", i ) ) == 0 ) {
			useLight[i] = true;
			return &lightOrigin[i];
		}
		if ( idStr::Icmp( _name, va( "lightColor%d", i ) ) == 0 ) {
			useLight[i] = true;
			return &lightColor[i];
		}
		if ( idStr::Icmp( _name, va( "lightRadius%d", i ) ) == 0 ) {
			useLight[i] = true;
			return &lightRadius[i];
		}
	}

	if ( idStr::Icmp( _name, "modelOrigin" ) == 0 ) {
		return &modelOrigin;
	}
	for ( int i = 1; i < MAX_RENDERWINDOW_MODELS; ++i ) {
		if ( idStr::Icmp( _name, va( "modelRotate%d", i ) ) == 0 ) {
			modelOwnRotate[i] = true;
			return &modelRotateN[i];
		}
		if ( idStr::Icmp( _name, va( "modelSpin%d", i ) ) == 0 ) {
			modelOwnRotate[i] = true;
			return &modelSpin[i];
		}
		if ( idStr::Icmp( _name, va( "modelFacing%d", i ) ) == 0 ) {
			modelOwnRotate[i] = true;
			return &modelFacing[i];
		}
	}
	if ( idStr::Icmp( _name, "fovY" ) == 0 ) {
		return &fovY;
	}
	if ( idStr::Icmp( _name, "sceneKey" ) == 0 ) {
		return &sceneKey;
	}
	if ( idStr::Icmpn( _name, "orbit", 5 ) == 0 ) {
		idWinVar *orbitVars[] = { &orbitCenter, &orbitFrom, &orbitTo, &orbitAimFrom, &orbitAimTo, &orbitShape, &orbitPlay, &orbitSkip };
		const char *orbitNames[] = { "orbitCenter", "orbitFrom", "orbitTo", "orbitAimFrom", "orbitAimTo", "orbitShape", "orbitPlay", "orbitSkip" };
		for ( int i = 0; i < 8; ++i ) {
			if ( idStr::Icmp( _name, orbitNames[i] ) == 0 ) {
				if ( i == 2 ) {
					orbitEnabled = true;
				}
				return orbitVars[i];
			}
		}
	}
	if ( idStr::Icmp( _name, "modelRotate" ) == 0 ) {
		return &modelRotate;
	}
	if ( idStr::Icmp( _name, "viewOffset" ) == 0 ) {
		return &viewOffset;
	}
	if ( idStr::Icmp( _name, "outlineColor" ) == 0 ) {
		return &outlineColor;
	}
	if ( idStr::Icmp( _name, "rimlightColor" ) == 0 ) {
		return &rimlightColor;
	}
	if ( idStr::Icmp( _name, "brightSkinColor" ) == 0 ) {
		return &brightSkinColor;
	}
	if ( idStr::Icmp( _name, "outlineWidth" ) == 0 ) {
		return &outlineWidth;
	}
	if ( idStr::Icmp( _name, "customShader" ) == 0 ) {
		return &customShader;
	}
	if ( idStr::Icmp( _name, "skin" ) == 0 ) {
		return &customSkin[0];
	}
	if ( idStr::Icmp( _name, "needsRender" ) == 0 ) {
		return &needsRender;
	}

	return idWindow::GetWinVarByName( _name, fixup, owner );
}

bool idRenderWindow::ParseInternalVar( const char *_name, idParser *src ) {
	if ( idStr::Icmp( _name, "needUpdate" ) == 0 ) {
		ParseString( src, needUpdate );
		return true;
	}
	if ( idStr::Icmp( _name, "canvasfill" ) == 0 ) {
		canvasFill = src->ParseBool();
		// The scene is meant to reach past the rect, which a renderDef otherwise
		// pushes as its own clip before it draws.
		if ( canvasFill ) {
			flags |= WIN_NOCLIP;
		}
		return true;
	}
	return idWindow::ParseInternalVar( _name, src );
}
