// Copyright (C) 2026 DarkMatter Productions
// SPDX-License-Identifier: GPL-3.0-or-later
#ifndef __CVAR_COMPLETION_SNAPSHOT_H__
#define __CVAR_COMPLETION_SNAPSHOT_H__

/*
===============================================================================

	CVar value-completion snapshots, engine only. CVarSystem.h is mirrored into
	the game modules, so this stays out of it.

	The idCmdSystem::ArgCompletion_* helpers are inline, so every binary has
	its own copy, and registering a static cvar points its value completion at
	the declaring binary's copy. That includes the cvars a module shares with
	the engine or another module, so a renderer module's GetRenderAPI and a
	game module's GetGameAPI take over every callback they declare. Once the
	module is unloaded they point at unmapped code, and the console calls a
	cvar's completion while its name and a space are typed.

	Capture before a module registers its cvars and Restore before it is
	unloaded. Restore gives every cvar the callback it had at Capture, and
	clears it on cvars that had none then, the module's own among them. A
	snapshot that was never captured restores nothing, rather than clearing
	every callback.

	Restore puts back callbacks that point into every module that was loaded
	at Capture, so those have to outlive it: unload modules in the reverse
	order they were loaded. The game module loads after the renderer module
	and is unloaded while it is still loaded, and rendererVkProbe restores
	its own snapshot before it returns.

===============================================================================
*/

class idCVarCompletionSnapshot {
public:
							idCVarCompletionSnapshot( void ) : captured( false ) {}
							// idHashIndex has no copy constructor
							idCVarCompletionSnapshot( const idCVarCompletionSnapshot & ) = delete;
	idCVarCompletionSnapshot &	operator=( const idCVarCompletionSnapshot & ) = delete;

	void					Capture( void );
							// returns how many callbacks it changed
	int						Restore( void ) const;
	void					Clear( void );

private:
	typedef struct savedCompletion_s {
		const idCVar *		cvar;
		argCompletion_t		completion;
	} savedCompletion_t;

	idList<savedCompletion_t>	saved;
	idHashIndex				savedHash;		// keyed on the cvar's address
	bool					captured;
};

#endif /* !__CVAR_COMPLETION_SNAPSHOT_H__ */
