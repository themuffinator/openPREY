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

#include "../../idlib/precompiled.h"
#define GL_GLEXT_LEGACY // AppKit.h include pulls in gl.h already
#import <AppKit/AppKit.h>
#import <Foundation/Foundation.h>
#import <crt_externs.h>
#import <errno.h>
#import <ctype.h>
#import <limits.h>
#import <spawn.h>
#import <stdlib.h>
#import <string.h>
#import <sys/stat.h>
#import <unistd.h>
#include "../sys_local.h"
#include "../URLPolicy.h"

#if defined(USE_SDL3)
#include <SDL3/SDL.h>
#include <cmath>
#include "macos_common.h"
#endif

static const int MAX_OSX_PROCESS_ARGS = 32;
static const int MAX_OSX_PROCESS_COMMAND = 4096;

#if defined(USE_SDL3)
static int OSX_WindowBorderExtent( CGFloat extent ) {
	if ( !std::isfinite( extent ) || extent <= 0.0 ) {
		return 0;
	}
	return static_cast<int>( std::ceil( extent ) );
}

bool Sys_SDL_GetNativeWindowBorders( SDL_Window *window, int *top, int *left, int *bottom, int *right ) {
	if ( top != NULL ) {
		*top = 0;
	}
	if ( left != NULL ) {
		*left = 0;
	}
	if ( bottom != NULL ) {
		*bottom = 0;
	}
	if ( right != NULL ) {
		*right = 0;
	}
	if ( window == NULL ) {
		return false;
	}

	@autoreleasepool {
		const SDL_PropertiesID properties = SDL_GetWindowProperties( window );
		NSWindow *nativeWindow = (__bridge NSWindow *)SDL_GetPointerProperty(
			properties, SDL_PROP_WINDOW_COCOA_WINDOW_POINTER, NULL );
		if ( nativeWindow == nil ) {
			return false;
		}

		const NSRect frameRect = [nativeWindow frame];
		const NSRect contentRect = [nativeWindow contentRectForFrameRect:frameRect];
		if ( top != NULL ) {
			*top = OSX_WindowBorderExtent( NSMaxY( frameRect ) - NSMaxY( contentRect ) );
		}
		if ( left != NULL ) {
			*left = OSX_WindowBorderExtent( NSMinX( contentRect ) - NSMinX( frameRect ) );
		}
		if ( bottom != NULL ) {
			*bottom = OSX_WindowBorderExtent( NSMinY( contentRect ) - NSMinY( frameRect ) );
		}
		if ( right != NULL ) {
			*right = OSX_WindowBorderExtent( NSMaxX( frameRect ) - NSMaxX( contentRect ) );
		}
	}

	return true;
}
#endif

static bool OSX_StringHasControlCharacters( const char *text ) {
	if ( text == NULL ) {
		return true;
	}

	for ( const unsigned char *scan = reinterpret_cast<const unsigned char *>( text ); *scan != '\0'; ++scan ) {
		if ( iscntrl( *scan ) ) {
			return true;
		}
	}
	return false;
}

static bool OSX_IsRegularFile( const char *path ) {
	struct stat st;
	return path != NULL && path[0] != '\0' && stat( path, &st ) == 0 && S_ISREG( st.st_mode );
}

static bool OSX_IsAbsolutePath( const char *path ) {
	return path != NULL && path[0] == '/';
}

static bool OSX_EnsureOwnerExecutable( const char *path ) {
	struct stat st;
	if ( path == NULL || path[0] == '\0' || stat( path, &st ) == -1 || !S_ISREG( st.st_mode ) ) {
		return false;
	}
	if ( ( st.st_mode & S_IXUSR ) != 0 ) {
		return true;
	}
	if ( chmod( path, st.st_mode | S_IXUSR ) == -1 ) {
		common->Printf( "chmod +x %s failed: %s\n", path, strerror( errno ) );
		return false;
	}
	if ( stat( path, &st ) == -1 || !S_ISREG( st.st_mode ) ) {
		return false;
	}
	return ( st.st_mode & S_IXUSR ) != 0;
}

static bool OSX_ParseProcessCommandLine( const char *command, char *buffer, size_t bufferSize, char **argv, int maxArgv ) {
	if ( command == NULL || command[0] == '\0' || buffer == NULL || bufferSize == 0 || argv == NULL || maxArgv < 2 ) {
		return false;
	}
	if ( strlen( command ) >= bufferSize || OSX_StringHasControlCharacters( command ) ) {
		return false;
	}

	const char *read = command;
	char *write = buffer;
	char *end = buffer + bufferSize - 1;
	int argc = 0;

	while ( *read != '\0' ) {
		while ( *read != '\0' && isspace( static_cast<unsigned char>( *read ) ) ) {
			++read;
		}
		if ( *read == '\0' ) {
			break;
		}
		if ( argc >= maxArgv - 1 ) {
			return false;
		}

		argv[argc++] = write;
		char quote = '\0';
		while ( *read != '\0' ) {
			const char ch = *read;
			if ( quote == '\0' && isspace( static_cast<unsigned char>( ch ) ) ) {
				break;
			}
			if ( ch == '"' || ch == '\'' ) {
				if ( quote == '\0' ) {
					quote = ch;
					++read;
					continue;
				}
				if ( quote == ch ) {
					quote = '\0';
					++read;
					continue;
				}
			}
			if ( ch == '\\' && read[1] != '\0' ) {
				++read;
			}
			if ( write >= end ) {
				return false;
			}
			*write++ = *read++;
		}

		if ( quote != '\0' || write >= end ) {
			return false;
		}
		*write++ = '\0';
	}

	argv[argc] = NULL;
	return argc > 0 && argv[0][0] != '\0';
}

static bool OSX_IsAllowedURL( NSURL *url ) {
	if ( url == nil ) {
		return false;
	}

	NSString *scheme = [url scheme];
	if ( scheme == nil ) {
		return false;
	}
	if ( [scheme caseInsensitiveCompare:@"https"] == NSOrderedSame || [scheme caseInsensitiveCompare:@"http"] == NSOrderedSame ) {
		NSString *host = [url host];
		return host != nil && [host length] > 0;
	}
	return false;
}

static bool OSX_EnvironmentEntryHasName( const char *entry, const char *name ) {
	if ( entry == NULL || name == NULL || name[0] == '\0' ) {
		return false;
	}
	const size_t nameLength = strlen( name );
	return idStr::Cmpn( entry, name, static_cast<int>( nameLength ) ) == 0 && entry[nameLength] == '=';
}

static bool OSX_ShouldDropProcessEnvironmentEntry( const char *entry ) {
	if ( entry == NULL ) {
		return true;
	}
	if ( idStr::Cmpn( entry, "DYLD_", 5 ) == 0 ) {
		return true;
	}
	return OSX_EnvironmentEntryHasName( entry, "LD_PRELOAD" ) ||
		OSX_EnvironmentEntryHasName( entry, "LD_LIBRARY_PATH" ) ||
		OSX_EnvironmentEntryHasName( entry, "LD_AUDIT" );
}

static char **OSX_CreateFilteredProcessEnvironment() {
	char ***environmentPointer = _NSGetEnviron();
	char *const *sourceEnvironment = ( environmentPointer != NULL && *environmentPointer != NULL ) ? *environmentPointer : NULL;

	size_t sourceCount = 0;
	size_t keepCount = 0;
	if ( sourceEnvironment != NULL ) {
		for ( ; sourceEnvironment[sourceCount] != NULL; ++sourceCount ) {
			if ( !OSX_ShouldDropProcessEnvironmentEntry( sourceEnvironment[sourceCount] ) ) {
				++keepCount;
			}
		}
	}

	char **filteredEnvironment = static_cast<char **>( calloc( keepCount + 1, sizeof( char * ) ) );
	if ( filteredEnvironment == NULL ) {
		return NULL;
	}

	size_t writeIndex = 0;
	for ( size_t sourceIndex = 0; sourceIndex < sourceCount; ++sourceIndex ) {
		if ( !OSX_ShouldDropProcessEnvironmentEntry( sourceEnvironment[sourceIndex] ) ) {
			filteredEnvironment[writeIndex++] = sourceEnvironment[sourceIndex];
		}
	}
	filteredEnvironment[writeIndex] = NULL;
	return filteredEnvironment;
}

static bool OSX_StartProcessArgs( char *const argv[], bool dofork ) {
	if ( argv == NULL || argv[0] == NULL || argv[0][0] == '\0' ) {
		return false;
	}
	if ( OSX_StringHasControlCharacters( argv[0] ) || !OSX_IsAbsolutePath( argv[0] ) || !OSX_IsRegularFile( argv[0] ) ) {
		common->Printf( "Sys_StartProcess '%s' rejected: expected an absolute executable file path\n", argv[0] );
		return false;
	}

	if ( !OSX_EnsureOwnerExecutable( argv[0] ) ) {
		common->Printf( "Sys_StartProcess '%s' rejected: executable bit is not set and could not be applied\n", argv[0] );
		return false;
	}

	char **environment = OSX_CreateFilteredProcessEnvironment();
	if ( environment == NULL ) {
		common->Printf( "Sys_StartProcess '%s' rejected: process environment allocation failed\n", argv[0] );
		return false;
	}

	if ( !dofork ) {
		common->Printf( "exec %s\n", argv[0] );
		execve( argv[0], argv, environment );
		const int savedErrno = errno;
		free( environment );
		common->Printf( "exec %s failed: %s\n", argv[0], strerror( savedErrno ) );
		_exit( 127 );
	}

	pid_t childPid = 0;
	const int result = posix_spawn( &childPid, argv[0], NULL, NULL, argv, environment );
	free( environment );
	if ( result != 0 ) {
		common->Printf( "posix_spawn %s failed: %s\n", argv[0], strerror( result ) );
		return false;
	}
	(void)childPid;

	return true;
}

/*
==================
idSysLocal::OpenURL
==================
*/
void idSysLocal::OpenURL( const char *url, bool doexit ) {
	static bool	quit_spamguard = false;

	if ( !idURLPolicy::IsAllowedHTTPURL( url ) ) {
		common->Printf( "OpenURL rejected: expected a bounded HTTP or HTTPS URL with a host\n" );
		return;
	}

	if ( quit_spamguard ) {
		common->DPrintf( "Sys_OpenURL: already in a doexit sequence, ignoring request\n" );
		return;
	}

	NSString *urlString = [ NSString stringWithUTF8String: url ];
	if ( urlString == nil ) {
		common->Printf( "OpenURL rejected: URL is not valid UTF-8\n" );
		return;
	}

	NSURL *nsURL = [ NSURL URLWithString: urlString ];
	if ( nsURL == nil || [ nsURL scheme ] == nil ) {
		common->Printf( "OpenURL rejected: Foundation could not parse URL\n" );
		return;
	}
	if ( !OSX_IsAllowedURL( nsURL ) ) {
		common->Printf( "OpenURL rejected: Foundation did not preserve the required HTTP(S) host\n" );
		return;
	}

	common->Printf( "Open URL: %s\n", url );
	if ( ![[ NSWorkspace sharedWorkspace ] openURL: nsURL ] ) {
		common->Printf( "OpenURL failed after validation\n" );
		return;
	}

	if ( doexit ) {
		quit_spamguard = true;
		cmdSystem->BufferCommandText( CMD_EXEC_APPEND, "quit\n" );
	}
}

/*
==================
Sys_DoStartProcess
==================
*/
void Sys_DoStartProcess( const char *exeName, bool dofork ) {
	if ( exeName == NULL || exeName[0] == '\0' ) {
		common->Printf( "Sys_DoStartProcess: empty command\n" );
		return;
	}

	if ( OSX_IsRegularFile( exeName ) && !OSX_StringHasControlCharacters( exeName ) ) {
		char *argv[2];
		argv[0] = const_cast<char *>( exeName );
		argv[1] = NULL;
		(void)OSX_StartProcessArgs( argv, dofork );
		return;
	}

	char commandBuffer[MAX_OSX_PROCESS_COMMAND];
	char *argv[MAX_OSX_PROCESS_ARGS];
	if ( !OSX_ParseProcessCommandLine( exeName, commandBuffer, sizeof( commandBuffer ), argv, MAX_OSX_PROCESS_ARGS ) ) {
		common->Printf( "Sys_DoStartProcess: invalid command line\n" );
		return;
	}

	(void)OSX_StartProcessArgs( argv, dofork );
}

/*
==================
OSX_GetLocalizedString
==================
*/
const char* OSX_GetLocalizedString( const char* key )
{
	static idStr localizedStrings[8];
	static int localizedStringIndex = 0;
	localizedStringIndex = ( localizedStringIndex + 1 ) & 7;
	idStr &localizedString = localizedStrings[localizedStringIndex];

	if ( key == NULL ) {
		localizedString.Clear();
		return localizedString.c_str();
	}

	NSString *lookupKey = [ NSString stringWithUTF8String: key ];
	if ( lookupKey == nil ) {
		localizedString = key;
		return localizedString.c_str();
	}

	// With an empty fallback value, Foundation returns the key itself when
	// the lookup misses (and the guard below additionally maps any empty
	// result to the key), so missing translations surface as the raw key
	// name instead of the literal "No translation" as a key-binding label.
	NSString *string = [ [ NSBundle mainBundle ] localizedStringForKey:lookupKey
													 value:@"" table:nil];
	const char *localizedText = string != nil ? [string UTF8String] : NULL;
	localizedString = ( localizedText != NULL && localizedText[0] != '\0' ) ? localizedText : key;
	return localizedString.c_str();
}
