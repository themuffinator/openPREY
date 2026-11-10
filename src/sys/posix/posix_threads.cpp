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
#include <sys/types.h>
#include <sys/stat.h>
#include <errno.h>
#include <stdio.h>
#include <dirent.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/time.h>
#include <pwd.h>
#include <pthread.h>
#include <string.h>

#include "../../idlib/precompiled.h"
#include "posix_public.h"

#if defined(_DEBUG)
// #define ID_VERBOSE_PTHREADS 
#endif

/*
======================================================
locks
======================================================
*/

// we use an extra lock for the local stuff
const int MAX_LOCAL_CRITICAL_SECTIONS = MAX_CRITICAL_SECTIONS + 1;
static pthread_mutex_t global_lock[ MAX_LOCAL_CRITICAL_SECTIONS ];
static bool global_lock_initialized[ MAX_LOCAL_CRITICAL_SECTIONS ];

static bool Sys_IsValidCriticalSectionIndex( int index ) {
	if ( index >= 0 && index < MAX_LOCAL_CRITICAL_SECTIONS ) {
		return true;
	}
	Sys_Printf( "Sys_Enter/LeaveCriticalSection: invalid index %d\n", index );
	return false;
}

static bool Sys_IsValidTriggerEventIndex( int index ) {
	if ( index >= 0 && index < MAX_TRIGGER_EVENTS ) {
		return true;
	}
	Sys_Printf( "Sys_Wait/TriggerEvent: invalid index %d\n", index );
	return false;
}

static bool Sys_IsCriticalSectionReady( int index, const char *operation ) {
	if ( !Sys_IsValidCriticalSectionIndex( index ) ) {
		return false;
	}
	if ( !global_lock_initialized[ index ] ) {
		Sys_Printf( "%s: critical section %d is not initialized\n", operation != NULL ? operation : "pthread", index );
		return false;
	}
	return true;
}

static bool Sys_LockCriticalSection( int index, const char *operation ) {
	if ( !Sys_IsCriticalSectionReady( index, operation ) ) {
		return false;
	}

#ifdef ID_VERBOSE_PTHREADS
	const int tryResult = pthread_mutex_trylock( &global_lock[index] );
	if ( tryResult == EBUSY ) {
		Sys_Printf( "busy lock %d in thread '%s'\n", index, Sys_GetThreadName() );
		const int lockResult = pthread_mutex_lock( &global_lock[index] );
		if ( lockResult == EDEADLK ) {
			Sys_Printf( "FATAL: DEADLOCK %d, in thread '%s'\n", index, Sys_GetThreadName() );
		}
		if ( lockResult != 0 ) {
			Sys_Printf( "%s: pthread_mutex_lock failed for %d: %s\n", operation != NULL ? operation : "pthread", index, strerror( lockResult ) );
			return false;
		}
		return true;
	}
	if ( tryResult != 0 ) {
		Sys_Printf( "%s: pthread_mutex_trylock failed for %d: %s\n", operation != NULL ? operation : "pthread", index, strerror( tryResult ) );
		return false;
	}
	return true;
#else
	const int result = pthread_mutex_lock( &global_lock[index] );
	if ( result != 0 ) {
		Sys_Printf( "%s: pthread_mutex_lock failed for %d: %s\n", operation != NULL ? operation : "pthread", index, strerror( result ) );
		return false;
	}
	return true;
#endif
}

static bool Sys_UnlockCriticalSection( int index, const char *operation ) {
	if ( !Sys_IsCriticalSectionReady( index, operation ) ) {
		return false;
	}

	const int result = pthread_mutex_unlock( &global_lock[index] );
	if ( result != 0 ) {
		Sys_Printf( "%s: pthread_mutex_unlock failed for %d: %s\n", operation != NULL ? operation : "pthread", index, strerror( result ) );
		return false;
	}
	return true;
}

/*
==================
Sys_EnterCriticalSection
==================
*/
void Sys_EnterCriticalSection( int index ) {
	assert( index >= 0 && index < MAX_LOCAL_CRITICAL_SECTIONS );
	(void)Sys_LockCriticalSection( index, "Sys_EnterCriticalSection" );
}

/*
==================
Sys_LeaveCriticalSection
==================
*/
void Sys_LeaveCriticalSection( int index ) {
	assert( index >= 0 && index < MAX_LOCAL_CRITICAL_SECTIONS );
	(void)Sys_UnlockCriticalSection( index, "Sys_LeaveCriticalSection" );
}

/*
======================================================
wait and trigger events
we use a single lock to manipulate the conditions, MAX_LOCAL_CRITICAL_SECTIONS-1

the semantics match the win32 version. signals raised while no one is waiting stay raised until a wait happens (which then does a simple pass-through)

NOTE: we use the same mutex for all the events. I don't think this would become much of a problem
cond_wait unlocks atomically with setting the wait condition, and locks it back before exiting the function
the potential for time wasting lock waits is very low
======================================================
*/

pthread_cond_t	event_cond[ MAX_TRIGGER_EVENTS ];
bool			signaled[ MAX_TRIGGER_EVENTS ];
bool			waiting[ MAX_TRIGGER_EVENTS ];
static bool		event_cond_initialized[ MAX_TRIGGER_EVENTS ];

static bool Sys_IsTriggerEventReady( int index, const char *operation ) {
	if ( !Sys_IsValidTriggerEventIndex( index ) ) {
		return false;
	}
	if ( !event_cond_initialized[ index ] ) {
		Sys_Printf( "%s: trigger event %d is not initialized\n", operation != NULL ? operation : "pthread", index );
		return false;
	}
	return true;
}

/*
==================
Sys_WaitForEvent
==================
*/
void Sys_WaitForEvent( int index ) {
	assert( index >= 0 && index < MAX_TRIGGER_EVENTS );
	if ( !Sys_IsTriggerEventReady( index, "Sys_WaitForEvent" ) ) {
		return;
	}
	if ( !Sys_LockCriticalSection( MAX_LOCAL_CRITICAL_SECTIONS - 1, "Sys_WaitForEvent" ) ) {
		return;
	}
	assert( !waiting[ index ] );	// WaitForEvent from multiple threads? that wouldn't be good
	if ( signaled[ index ] ) {
		// emulate windows behaviour: signal has been raised already. clear and keep going
		signaled[ index ] = false;
	} else {
		waiting[ index ] = true;
		const int result = pthread_cond_wait( &event_cond[ index ], &global_lock[ MAX_LOCAL_CRITICAL_SECTIONS - 1 ] );
		if ( result != 0 ) {
			Sys_Printf( "Sys_WaitForEvent: pthread_cond_wait failed for event %d: %s\n", index, strerror( result ) );
		}
		waiting[ index ] = false;
	}
	(void)Sys_UnlockCriticalSection( MAX_LOCAL_CRITICAL_SECTIONS - 1, "Sys_WaitForEvent" );
}

/*
==================
Sys_TriggerEvent
==================
*/
void Sys_TriggerEvent( int index ) {
	assert( index >= 0 && index < MAX_TRIGGER_EVENTS );
	if ( !Sys_IsTriggerEventReady( index, "Sys_TriggerEvent" ) ) {
		return;
	}
	if ( !Sys_LockCriticalSection( MAX_LOCAL_CRITICAL_SECTIONS - 1, "Sys_TriggerEvent" ) ) {
		return;
	}
	if ( waiting[ index ] ) {		
		const int result = pthread_cond_signal( &event_cond[ index ] );
		if ( result != 0 ) {
			Sys_Printf( "Sys_TriggerEvent: pthread_cond_signal failed for event %d: %s\n", index, strerror( result ) );
		}
	} else {
		// emulate windows behaviour: if no thread is waiting, leave the signal on so next wait keeps going
		signaled[ index ] = true;
	}
	(void)Sys_UnlockCriticalSection( MAX_LOCAL_CRITICAL_SECTIONS - 1, "Sys_TriggerEvent" );
}

/*
======================================================
thread create and destroy
======================================================
*/

// not a hard limit, just what we keep track of for debugging
#define MAX_THREADS 10
xthreadInfo *g_threads[MAX_THREADS];

int g_thread_count = 0;

typedef void *(*pthread_function_t) (void *);

static_assert( sizeof( pthread_t ) <= sizeof( uintptr_t ),
	"xthreadInfo::threadHandle cannot represent pthread_t on this platform" );

static uintptr_t Sys_PThreadToHandle( pthread_t thread ) {
	uintptr_t handle = 0;
	memcpy( &handle, &thread, sizeof( thread ) );
	return handle;
}

static pthread_t Sys_HandleToPThread( uintptr_t handle ) {
	pthread_t thread;
	memset( &thread, 0, sizeof( thread ) );
	memcpy( &thread, &handle, sizeof( thread ) );
	return thread;
}

static void Sys_RemoveThreadInfo( xthreadInfo& info ) {
	Sys_EnterCriticalSection( );
	for( int i = 0 ; i < g_thread_count ; i++ ) {
		if ( &info == g_threads[ i ] ) {
			g_threads[ i ] = NULL;
			int j;
			for( j = i+1 ; j < g_thread_count ; j++ ) {
				g_threads[ j-1 ] = g_threads[ j ];
			}
			g_threads[ j-1 ] = NULL;
			g_thread_count--;
			break;
		}
	}
	Sys_LeaveCriticalSection( );
}

/*
==================
Sys_CreateThread
==================
*/
void Sys_CreateThread( xthread_t function, void *parms, xthreadPriority priority, xthreadInfo& info, const char *name, xthreadInfo **threads, int *thread_count ) {
	const char *threadName = name != NULL && name[0] != '\0' ? name : "unnamed";
	(void)priority;

	info.threadHandle = 0;
	info.threadId = 0;
	info.stopRequested = false;
	info.name = threadName;

	if ( function == NULL || threads == NULL || thread_count == NULL ) {
		common->Printf( "Sys_CreateThread: invalid arguments for %s\n", threadName );
		return;
	}
	if ( *thread_count < 0 ) {
		common->Printf( "Sys_CreateThread: resetting invalid thread count %d for %s\n", *thread_count, threadName );
		*thread_count = 0;
	}

	Sys_EnterCriticalSection( );		
	pthread_attr_t attr;
	int result = pthread_attr_init( &attr );
	if ( result != 0 ) {
		Sys_LeaveCriticalSection( );
		common->Error( "ERROR: pthread_attr_init %s failed: %s\n", threadName, strerror( result ) );
	}
	result = pthread_attr_setdetachstate( &attr, PTHREAD_CREATE_JOINABLE );
	if ( result != 0 ) {
		pthread_attr_destroy( &attr );
		Sys_LeaveCriticalSection( );
		common->Error( "ERROR: pthread_attr_setdetachstate %s failed: %s\n", threadName, strerror( result ) );
	}
	// Platform defaults diverge widely (macOS: 512KB, Linux: usually 8MB);
	// raise small defaults to a floor comfortably above what engine worker
	// threads need, without shrinking platforms that already give more.
	const size_t minWorkerStackSize = 4 * 1024 * 1024;
	size_t defaultStackSize = 0;
	if ( pthread_attr_getstacksize( &attr, &defaultStackSize ) == 0 && defaultStackSize < minWorkerStackSize ) {
		result = pthread_attr_setstacksize( &attr, minWorkerStackSize );
		if ( result != 0 ) {
			common->Printf( "Sys_CreateThread: pthread_attr_setstacksize %s failed: %s; using the platform default\n", threadName, strerror( result ) );
		}
	}
	pthread_t thread;
	result = pthread_create( &thread, &attr, ( pthread_function_t )function, parms );
	if ( result != 0 ) {
		pthread_attr_destroy( &attr );
		Sys_LeaveCriticalSection( );
		common->Error( "ERROR: pthread_create %s failed: %s\n", threadName, strerror( result ) );
	}
	pthread_attr_destroy( &attr );
	info.threadHandle = Sys_PThreadToHandle( thread );
	if ( *thread_count < MAX_THREADS ) {
		threads[ ( *thread_count )++ ] = &info;
	} else {
		common->DPrintf( "WARNING: MAX_THREADS reached\n" );
	}
	Sys_LeaveCriticalSection( );
}

/*
==================
Sys_RequestThreadStop
==================
*/
void Sys_RequestThreadStop( xthreadInfo& info ) {
	Sys_EnterCriticalSection( );
	info.stopRequested = true;
	Sys_LeaveCriticalSection( );

	for ( int i = 0; i < MAX_TRIGGER_EVENTS; i++ ) {
		Sys_TriggerEvent( i );
	}
}

/*
==================
Sys_IsThreadStopRequested
==================
*/
bool Sys_IsThreadStopRequested( const xthreadInfo& info ) {
	bool stopRequested;
	Sys_EnterCriticalSection( );
	stopRequested = info.stopRequested;
	Sys_LeaveCriticalSection( );
	return stopRequested;
}

/*
==================
Sys_IsCurrentThreadStopRequested
==================
*/
bool Sys_IsCurrentThreadStopRequested( void ) {
	const pthread_t thread = pthread_self();
	bool stopRequested = false;

	Sys_EnterCriticalSection( );
	for( int i = 0 ; i < g_thread_count ; i++ ) {
		if ( g_threads[ i ] != NULL && pthread_equal( thread, Sys_HandleToPThread( g_threads[ i ]->threadHandle ) ) ) {
			stopRequested = g_threads[ i ]->stopRequested;
			break;
		}
	}
	Sys_LeaveCriticalSection( );
	return stopRequested;
}

/*
==================
Sys_DestroyThread
==================
*/
void Sys_DestroyThread( xthreadInfo& info ) {
	assert( info.threadHandle );
	const pthread_t thread = Sys_HandleToPThread( info.threadHandle );
	if ( pthread_equal( thread, pthread_self() ) ) {
		common->Error( "ERROR: Sys_DestroyThread attempted to join current thread %s\n", info.name );
	}

	Sys_RequestThreadStop( info );
	if ( pthread_join( thread, NULL ) != 0 ) {
		common->Error( "ERROR: pthread_join %s failed\n", info.name );
	}
	info.threadHandle = 0;
	info.threadId = 0;
	info.stopRequested = false;
	Sys_RemoveThreadInfo( info );
}

/*
==================
Sys_GetThreadName
find the name of the calling thread
==================
*/
const char* Sys_GetThreadName( int *index ) {
	Sys_EnterCriticalSection( );
	pthread_t thread = pthread_self();
	for( int i = 0 ; i < g_thread_count ; i++ ) {
		if ( g_threads[ i ] != NULL && pthread_equal( thread, Sys_HandleToPThread( g_threads[ i ]->threadHandle ) ) ) {
			if ( index ) {
				*index = i;
			}
			Sys_LeaveCriticalSection( );
			return g_threads[ i ]->name;
		}
	}
	if ( index ) {
		*index = -1;
	}
	Sys_LeaveCriticalSection( );
	return "main";
}

/*
=========================================================
Async Thread
=========================================================
*/

xthreadInfo asyncThread;

/*
=================
Posix_StartAsyncThread
=================
*/
void Posix_StartAsyncThread() {
	if ( asyncThread.threadHandle == 0 ) {
		Sys_CreateThread( (xthread_t)Sys_AsyncThread, NULL, THREAD_NORMAL, asyncThread, "Async", g_threads, &g_thread_count );
	} else {
		common->Printf( "Async thread already running\n" );
	}
	common->Printf( "Async thread started\n" );
}

/*
==================
Posix_InitPThreads
==================
*/
void Posix_InitPThreads( ) {
	int i;

	// init critical sections
	for ( i = 0; i < MAX_LOCAL_CRITICAL_SECTIONS; i++ ) {
		pthread_mutexattr_t attr;
		pthread_mutexattr_t *attrPtr = NULL;
		bool attrInitialized = false;
		int result = pthread_mutexattr_init( &attr );
		if ( result == 0 ) {
			attrInitialized = true;
			result = pthread_mutexattr_settype( &attr, PTHREAD_MUTEX_ERRORCHECK );
			if ( result != 0 ) {
				Sys_Printf( "pthread_mutexattr_settype failed for lock %d: %s; critical section disabled\n", i, strerror( result ) );
			} else {
				attrPtr = &attr;
			}
		} else {
			Sys_Printf( "pthread_mutexattr_init failed for lock %d: %s\n", i, strerror( result ) );
		}

		if ( attrPtr != NULL ) {
			result = pthread_mutex_init( &global_lock[i], attrPtr );
			if ( result != 0 ) {
				Sys_Printf( "pthread_mutex_init failed for lock %d: %s\n", i, strerror( result ) );
				global_lock_initialized[i] = false;
			} else {
				global_lock_initialized[i] = true;
			}
		} else {
			global_lock_initialized[i] = false;
		}
		if ( attrInitialized ) {
			pthread_mutexattr_destroy( &attr );
		}
	}

	// init event sleep/triggers
	for ( i = 0; i < MAX_TRIGGER_EVENTS; i++ ) {
		const int result = pthread_cond_init( &event_cond[ i ], NULL );
		if ( result != 0 ) {
			Sys_Printf( "pthread_cond_init failed for event %d: %s\n", i, strerror( result ) );
			event_cond_initialized[i] = false;
		} else {
			event_cond_initialized[i] = true;
		}
		signaled[i] = false;
		waiting[i] = false;
	}

	// init threads table
	for ( i = 0; i < MAX_THREADS; i++ ) {
		g_threads[ i ] = NULL;
	}	
}

