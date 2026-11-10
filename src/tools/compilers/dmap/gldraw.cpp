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




#include "dmap.h"

/*
===============================================================================

	The Windows-only 'dmap -draw' immediate-mode GL visualization (and its
	winsock glserv companion) was retired with the renderer-module seam
	(docs/dev/archive/2026-10-18/plans/2026-07-16-vulkan-renderer-phase-b.md, B6): the engine
	executables no longer carry an OpenGL surface for it to draw into. The
	entry points remain as no-ops so the optimizer's instrumentation call
	sites stay in place.

===============================================================================
*/

void Draw_ClearWindow( void ) {
}

void Draw_SetRed( void ) {
}

void Draw_SetGrey( void ) {
}

void Draw_SetBlack( void ) {
}

void DrawWinding( const idWinding *w ) {
}

void DrawAuxWinding( const idWinding *w ) {
}

void DrawLine( idVec3 v1, idVec3 v2, int color ) {
}

void GLS_BeginScene( void ) {
}

void GLS_Winding( const idWinding *w, int code ) {
}

void GLS_Triangle( const mapTri_t *tri, int code ) {
}

void GLS_EndScene( void ) {
}
