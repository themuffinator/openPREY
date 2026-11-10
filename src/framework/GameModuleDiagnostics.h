// Copyright (C) 2026 DarkMatter Productions
//

#ifndef __GAME_MODULE_DIAGNOSTICS_H__
#define __GAME_MODULE_DIAGNOSTICS_H__

#include <signal.h>

// Peer of renderer/RendererStartupDiagnostics.h for the game-module boundary.
//
// A game module dies inside somebody else's binary: a bad static initializer, a
// mismatched engine/game interface, or a cross-module allocation shows up as a
// bare signal with nothing between "Selected game module:" and
// "------------- Initializing Game -------------" in the log. Issue #90 is
// exactly that -- a malloc abort on an Intel Mac with no way for the reporter
// to say which of dlopen, GetGameAPI or idGameLocal::Init was running. These
// phases are recorded before each step and printed by the fatal-signal handler.
typedef enum gameModuleLoadPhase_e {
	GAME_MODULE_PHASE_IDLE = 0,
	GAME_MODULE_PHASE_LOCATE,
	GAME_MODULE_PHASE_BINARY_LOAD,
	GAME_MODULE_PHASE_RESOLVE_ENTRY_POINT,
	GAME_MODULE_PHASE_CALL_GET_GAME_API,
	GAME_MODULE_PHASE_VERIFY_API_VERSION,
	GAME_MODULE_PHASE_GAME_INIT,
	GAME_MODULE_PHASE_READY,
	GAME_MODULE_PHASE_GAME_SHUTDOWN,
	GAME_MODULE_PHASE_GAME_FINALIZE,
	GAME_MODULE_PHASE_BINARY_UNLOAD,
	GAME_MODULE_PHASE_COUNT
} gameModuleLoadPhase_t;

void Com_SetGameModuleLoadPhase( gameModuleLoadPhase_t phase );
void Com_RecordGameModuleLoadPhase( gameModuleLoadPhase_t phase );
gameModuleLoadPhase_t Com_GetGameModuleLoadPhase( void );
const char *Com_GameModuleLoadPhaseName( gameModuleLoadPhase_t phase );
const char *Com_GameModuleLoadPhaseSignalName( void );

#endif
