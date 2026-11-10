/*
===========================================================================

openPREY GPL Source Code
Copyright (C) 2026 DarkMatter Productions

This file is part of the openPREY GPL Source Code.

openPREY Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

openPREY Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with openPREY Source Code.  If not, see <http://www.gnu.org/licenses/>.

===========================================================================
*/

#ifndef __PREY_GAME_COMPAT_H__
#define __PREY_GAME_COMPAT_H__

/*
===============================================================================

	Engine-side answers for idGame/idGameEdit services that upstream openQ4's
	engine calls but Prey's v7 game API (src/game/Game.h) does not export.

	The retained screens, the multiplayer ban list and the background-save
	guard ask the Quake 4 game module for state Prey's game never publishes.
	These shims keep upstream's call sites intact and answer as an
	unextended Prey game would: no retained-menu state, no ban list, and no
	cinematic veto beyond the game's own save checks. Re-enabling any of them
	is game API design work, not a runtime option (docs/dev/prey-rebase/plan.md,
	decision D9).

===============================================================================
*/

class idUserInterface;

// OPENPREY-GATED(D9): retained-screen state queries are Quake 4 game services.
static ID_INLINE void PreyGame_HandleMainMenuCommands( const char *menuCommand, idUserInterface *gui ) {
	(void)menuCommand;
	(void)gui;
}

// Prey's v7 idGame does not report cinematics; its own SaveGame refuses them.
static ID_INLINE bool PreyGame_InCinematic( void ) {
	return false;
}

// OPENPREY-GATED(D9): the multiplayer ban list is a Quake 4 game service.
static ID_INLINE void PreyGame_PopulateBanList( idUserInterface *gui ) {
	(void)gui;
}

static ID_INLINE void PreyGame_RemoveGuidFromBanList( const char *guid ) {
	(void)guid;
}

// Prey's v7 idGameEdit has no game clock query; diagnostics report -1.
static ID_INLINE int PreyGameEdit_GetGameTime( void ) {
	return -1;
}

#endif /* !__PREY_GAME_COMPAT_H__ */
