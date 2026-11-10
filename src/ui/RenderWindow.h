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
#ifndef __RENDERWINDOW_H
#define __RENDERWINDOW_H

#include "retained/ModelScene.h"

class idUserInterfaceLocal;
class idRenderWindow : public idWindow {
public:
	idRenderWindow( idUserInterfaceLocal *gui );
	idRenderWindow( idDeviceContext *d, idUserInterfaceLocal *gui );
	virtual ~idRenderWindow();

	virtual void PostParse();
	virtual void RefreshForLevelLoad() override;
	virtual void Draw( int time, float x, float y );
	virtual size_t Allocated() { return idWindow::Allocated(); };
	virtual idWinVar *GetWinVarByName( const char *_name, bool winLookup = false, drawWin_t **owner = NULL );

	// Programmatic renderDef, shared with the retained host. No GUI scripts or
	// entity spawning are involved; the caller owns the output target/crop.
	void ConfigureModelScene( const openq4::ui::ModelScene &scene );
	bool PrepareModelScene( int time, std::string &error );
	void DrawModelScene( int time, float fov, int width, int height );

private:
	enum {
		MAX_RENDERWINDOW_MODELS = 3,
		MAX_RENDERWINDOW_LIGHTS = 5
	};

	void CommonInit();
	void FreeModelJoints();
	virtual bool ParseInternalVar( const char *name, idParser *src );
	void Render( int time );
	void UpdateRenderVars();
	void PreRender();
	void BuildAnimation( int time );

	renderView_t refdef;
	idRenderWorld *world;
	renderEntity_t worldEntity[MAX_RENDERWINDOW_MODELS];
	renderLight_t rLights[MAX_RENDERWINDOW_LIGHTS];
	const idMD5Anim *modelAnim[MAX_RENDERWINDOW_MODELS];

	qhandle_t lightDefs[MAX_RENDERWINDOW_LIGHTS];
	qhandle_t modelDef[MAX_RENDERWINDOW_MODELS];
	idWinStr modelName[MAX_RENDERWINDOW_MODELS];
	idWinStr jointName[MAX_RENDERWINDOW_MODELS];
	idWinStr animName[MAX_RENDERWINDOW_MODELS];
	idWinStr animClass[MAX_RENDERWINDOW_MODELS];
	idStr needUpdate;
	idWinVec4 lightOrigin[MAX_RENDERWINDOW_LIGHTS];
	idWinVec4 lightColor[MAX_RENDERWINDOW_LIGHTS];
	idWinVec4 modelOrigin;
	idWinVec4 modelRotate;
	idWinVec4 viewOffset;
	idWinVec4 outlineColor;
	idWinVec4 rimlightColor;
	idWinVec4 brightSkinColor;
	idWinFloat outlineWidth;
	idWinStr customSkin[MAX_RENDERWINDOW_MODELS];
	openq4::ui::ModelScene configuredScene;
	bool sceneConfigured = false;
	idWinStr customShader;
	idWinBool needsRender;
	int animLength[MAX_RENDERWINDOW_MODELS];
	int animEndTime[MAX_RENDERWINDOW_MODELS];
	bool useLight[MAX_RENDERWINDOW_LIGHTS];
	bool updateAnimation;
};

#endif // __RENDERWINDOW_H
