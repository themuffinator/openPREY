/*
===========================================================================

openQ4 learned level-load manifest and generated-cache coordinator

Copyright (C) 2026 openQ4 contributors

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

===========================================================================
*/

#ifndef __LEVEL_LOAD_CACHE_MANAGER_H__
#define __LEVEL_LOAD_CACHE_MANAGER_H__

#include "FileSystem.h"

#include <memory>

class idFile;

class idLevelLoadCacheManager {
public:
	explicit idLevelLoadCacheManager( idFileSystem *fileSystem );
	~idLevelLoadCacheManager();

	idLevelLoadCacheManager( const idLevelLoadCacheManager & ) = delete;
	idLevelLoadCacheManager &operator=( const idLevelLoadCacheManager & ) = delete;

	void Begin( const char *mapKey, const char *gameMode,
		const char *entityFilter, const char *contentKey,
		const char *settingsKey );
	void Finish( bool successful );
	// Finish joins the generation but deliberately retains immutable replay
	// bytes while the resource owners complete EndLevelLoad(). Release drops
	// that bounded staging storage once those main-thread consumers are done.
	void Release();
	void Cancel();

	void RecordSemantic( levelLoadResourceType_t type, const char *name,
		const char *options, unsigned int flags, unsigned int priority );
	void RecordOpenedSource( const char *normalizedPath, idFile *source );
	// The caller has already resolved and authorized authoritativeSource through
	// normal VFS/pure rules. Returns an immutable scheduled view only when its
	// complete source identity matches; otherwise returns NULL.
	idFile *OpenPreloadedSource( const char *normalizedPath, idFile *authoritativeSource );

	// The gates OpenGeneratedCacheRead and WriteGeneratedCache apply before any
	// source or cache I/O, exposed so owners can skip building a payload.
	bool GeneratedCacheReadsEnabled( generatedCacheKind_t kind ) const;
	bool GeneratedCacheWritesEnabled( generatedCacheKind_t kind ) const;

	idFile *OpenGeneratedCacheRead( generatedCacheKind_t kind,
		const char *sourcePath, unsigned int parserVersion,
		const char *settingsKey, const char *contentKey );
	bool WriteGeneratedCache( generatedCacheKind_t kind,
		const char *sourcePath, unsigned int parserVersion,
		const char *settingsKey, const void *payload,
		unsigned int payloadBytes, const char *contentKey );
	void DiscardGeneratedCache( generatedCacheKind_t kind,
		const char *sourcePath, unsigned int parserVersion,
		const char *settingsKey, const char *contentKey );

private:
	struct Impl;
	std::unique_ptr<Impl> impl;
};

#endif /* !__LEVEL_LOAD_CACHE_MANAGER_H__ */
