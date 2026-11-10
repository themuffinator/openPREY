// Copyright (C) 2004 Id Software, Inc.
//

#include "tr_local.h"
#include "GLDebugScope.h"
#include "GLStateCache.h"

static bool R_GLDebug_HasDebugOutput( void ) {
	return glConfig.backendCaps.hasDebugOutput;
}

static bool rg_glDebugOutputRegistered = false;
static bool rg_glDebugOutputUsesCoreCallback = false;
static bool rg_glDebugOutputSynchronous = false;
static thread_local const char *rg_glDebugCurrentScope = NULL;

static const int RENDERER_GL_DEBUG_MESSAGE_CAPACITY = 64;
static const int RENDERER_GL_DEBUG_MESSAGE_TEXT = 512;
static const int RENDERER_GL_DEBUG_CRITICAL_SECTION = CRITICAL_SECTION_THREE;

typedef struct glDebugQueuedMessage_s {
	GLenum source;
	GLenum type;
	GLuint id;
	GLenum severity;
	char message[RENDERER_GL_DEBUG_MESSAGE_TEXT];
	char scope[256];
} glDebugQueuedMessage_t;

static glDebugQueuedMessage_t rg_glDebugOutputMessages[RENDERER_GL_DEBUG_MESSAGE_CAPACITY];
static int rg_glDebugOutputMessageStart = 0;
static int rg_glDebugOutputMessageCount = 0;
static int rg_glDebugOutputDroppedMessages = 0;

static const char *R_GLDebug_SourceName( GLenum source ) {
	switch ( source ) {
	case GL_DEBUG_SOURCE_API: return "api";
	case GL_DEBUG_SOURCE_WINDOW_SYSTEM: return "window";
	case GL_DEBUG_SOURCE_SHADER_COMPILER: return "shader";
	case GL_DEBUG_SOURCE_THIRD_PARTY: return "third-party";
	case GL_DEBUG_SOURCE_APPLICATION: return "app";
	case GL_DEBUG_SOURCE_OTHER:
	default: return "other";
	}
}

static const char *R_GLDebug_TypeName( GLenum type ) {
	switch ( type ) {
	case GL_DEBUG_TYPE_ERROR: return "error";
	case GL_DEBUG_TYPE_DEPRECATED_BEHAVIOR: return "deprecated";
	case GL_DEBUG_TYPE_UNDEFINED_BEHAVIOR: return "undefined";
	case GL_DEBUG_TYPE_PORTABILITY: return "portability";
	case GL_DEBUG_TYPE_PERFORMANCE: return "performance";
	case GL_DEBUG_TYPE_MARKER: return "marker";
	case GL_DEBUG_TYPE_PUSH_GROUP: return "push";
	case GL_DEBUG_TYPE_POP_GROUP: return "pop";
	case GL_DEBUG_TYPE_OTHER:
	default: return "other";
	}
}

static const char *R_GLDebug_SeverityName( GLenum severity ) {
	switch ( severity ) {
	case GL_DEBUG_SEVERITY_HIGH: return "high";
	case GL_DEBUG_SEVERITY_MEDIUM: return "medium";
	case GL_DEBUG_SEVERITY_LOW: return "low";
	case GL_DEBUG_SEVERITY_NOTIFICATION: return "notification";
	default: return "unknown";
	}
}

static void R_GLDebug_CopyMessageText( char *dest, int destSize, GLsizei length, const GLchar *message ) {
	if ( dest == NULL || destSize <= 0 ) {
		return;
	}
	dest[0] = '\0';
	if ( message == NULL ) {
		return;
	}
	if ( length > 0 ) {
		const int copyLength = Min( static_cast<int>( length ), destSize - 1 );
		memcpy( dest, message, copyLength );
		dest[copyLength] = '\0';
		return;
	}
	idStr::Copynz( dest, message, destSize );
}

static void R_GLDebug_QueueMessage( GLenum source, GLenum type, GLuint id, GLenum severity, GLsizei length, const GLchar *message ) {
	if ( severity == GL_DEBUG_SEVERITY_NOTIFICATION ) {
		return;
	}

	Sys_EnterCriticalSection( RENDERER_GL_DEBUG_CRITICAL_SECTION );
	if ( rg_glDebugOutputMessageCount < RENDERER_GL_DEBUG_MESSAGE_CAPACITY ) {
		const int index = ( rg_glDebugOutputMessageStart + rg_glDebugOutputMessageCount ) % RENDERER_GL_DEBUG_MESSAGE_CAPACITY;
		glDebugQueuedMessage_t &queued = rg_glDebugOutputMessages[index];
		queued.source = source;
		queued.type = type;
		queued.id = id;
		queued.severity = severity;
		R_GLDebug_CopyMessageText( queued.message, sizeof( queued.message ), length, message );
		// Only synchronous callbacks have a reliable submitting scope. Driver
		// worker callbacks must not report whichever pass happens to run later.
		idStr::Copynz( queued.scope, rg_glDebugOutputSynchronous && rg_glDebugCurrentScope
			? rg_glDebugCurrentScope : "", sizeof( queued.scope ) );
		rg_glDebugOutputMessageCount++;
	} else {
		rg_glDebugOutputDroppedMessages++;
	}
	Sys_LeaveCriticalSection( RENDERER_GL_DEBUG_CRITICAL_SECTION );
}

static void GLAPIENTRY R_GLDebug_Callback( GLenum source, GLenum type, GLuint id, GLenum severity, GLsizei length, const GLchar *message, const void *userParam ) {
	(void)userParam;
	R_GLDebug_QueueMessage( source, type, id, severity, length, message );
}

static void GLAPIENTRY R_GLDebug_CallbackARB( GLenum source, GLenum type, GLuint id, GLenum severity, GLsizei length, const GLchar *message, const void *userParam ) {
	(void)userParam;
	R_GLDebug_QueueMessage( source, type, id, severity, length, message );
}

bool R_GLDebugOutput_Available( void ) {
	return R_GLDebug_HasDebugOutput()
		&& ( ( glDebugMessageCallback != NULL && glDebugMessageControl != NULL )
			|| ( glDebugMessageCallbackARB != NULL && glDebugMessageControlARB != NULL ) );
}

bool R_GLDebugOutput_Registered( void ) {
	return rg_glDebugOutputRegistered;
}

void R_GLDebugOutput_Init( void ) {
	R_GLDebugOutput_Shutdown();
	if ( !r_glDebugOutput.GetBool() || !R_GLDebugOutput_Available() ) {
		return;
	}
	if ( !glConfig.backendCaps.debugContext ) {
		if ( glConfig.contextRequest.debugContext ) {
			common->Printf( "OpenGL debug output callback unavailable: selected context is not a debug context\n" );
		}
		return;
	}

	const bool synchronous = r_glDebugSynchronous.GetBool();
	if ( glDebugMessageCallback != NULL && glDebugMessageControl != NULL ) {
		glEnable( GL_DEBUG_OUTPUT );
		if ( synchronous ) {
			glEnable( GL_DEBUG_OUTPUT_SYNCHRONOUS );
		}
		glDebugMessageCallback( R_GLDebug_Callback, NULL );
		glDebugMessageControl( GL_DONT_CARE, GL_DONT_CARE, GL_DEBUG_SEVERITY_NOTIFICATION, 0, NULL, GL_FALSE );
		rg_glDebugOutputUsesCoreCallback = true;
	} else {
		glDebugMessageCallbackARB( R_GLDebug_CallbackARB, NULL );
		glDebugMessageControlARB( GL_DONT_CARE, GL_DONT_CARE, GL_DONT_CARE, 0, NULL, GL_TRUE );
		if ( synchronous ) {
			glEnable( GL_DEBUG_OUTPUT_SYNCHRONOUS_ARB );
		}
		rg_glDebugOutputUsesCoreCallback = false;
	}
	rg_glDebugOutputSynchronous = synchronous;
	rg_glDebugOutputRegistered = true;
	common->Printf( "OpenGL debug output callback enabled%s\n", synchronous ? " (synchronous)" : "" );
}

void R_GLDebugOutput_FlushMessages( void ) {
	// Production contexts do not register the callback. Avoid adding a
	// critical-section round trip to every backend frame in that common case.
	if ( !rg_glDebugOutputRegistered ) {
		return;
	}

	glDebugQueuedMessage_t messages[RENDERER_GL_DEBUG_MESSAGE_CAPACITY];
	int messageCount = 0;
	int droppedMessages = 0;

	Sys_EnterCriticalSection( RENDERER_GL_DEBUG_CRITICAL_SECTION );
	messageCount = rg_glDebugOutputMessageCount;
	for ( int i = 0; i < messageCount; ++i ) {
		const int index = ( rg_glDebugOutputMessageStart + i ) % RENDERER_GL_DEBUG_MESSAGE_CAPACITY;
		messages[i] = rg_glDebugOutputMessages[index];
	}
	rg_glDebugOutputMessageStart = 0;
	rg_glDebugOutputMessageCount = 0;
	droppedMessages = rg_glDebugOutputDroppedMessages;
	rg_glDebugOutputDroppedMessages = 0;
	Sys_LeaveCriticalSection( RENDERER_GL_DEBUG_CRITICAL_SECTION );

	for ( int i = 0; i < messageCount; ++i ) {
		const glDebugQueuedMessage_t &queued = messages[i];
		common->Printf(
			"GL debug callback [source=%s type=%s severity=%s id=%u scope='%s'] %s\n",
			R_GLDebug_SourceName( queued.source ),
			R_GLDebug_TypeName( queued.type ),
			R_GLDebug_SeverityName( queued.severity ),
			queued.id,
			queued.scope,
			queued.message );
	}
	if ( droppedMessages > 0 ) {
		common->Printf( "GL debug output dropped %d queued messages\n", droppedMessages );
	}
}

void R_GLDebugOutput_Shutdown( void ) {
	if ( rg_glDebugOutputRegistered ) {
		if ( rg_glDebugOutputUsesCoreCallback && glDebugMessageCallback != NULL ) {
			glDebugMessageCallback( NULL, NULL );
			if ( rg_glDebugOutputSynchronous ) {
				glDisable( GL_DEBUG_OUTPUT_SYNCHRONOUS );
			}
			glDisable( GL_DEBUG_OUTPUT );
		} else if ( glDebugMessageCallbackARB != NULL ) {
			glDebugMessageCallbackARB( NULL, NULL );
			if ( rg_glDebugOutputSynchronous ) {
				glDisable( GL_DEBUG_OUTPUT_SYNCHRONOUS_ARB );
			}
		}
	}
	R_GLDebugOutput_FlushMessages();
	rg_glDebugOutputRegistered = false;
	rg_glDebugOutputUsesCoreCallback = false;
	rg_glDebugOutputSynchronous = false;
}

bool R_GLDebugScope_Available( void ) {
	return R_GLDebug_HasDebugOutput() && glPushDebugGroup != NULL && glPopDebugGroup != NULL;
}

bool R_GLDebugObjectLabels_Available( void ) {
	return R_GLDebug_HasDebugOutput() && glObjectLabel != NULL;
}

void R_GLDebug_LabelObject( GLenum identifier, GLuint name, const char *label ) {
	if ( name == 0 || label == NULL || label[0] == '\0' || !R_GLDebugObjectLabels_Available() ) {
		return;
	}
	// KHR_debug guarantees at least 256 bytes.  Keep labels inside that floor
	// without adding a synchronous GL_MAX_LABEL_LENGTH query to every object.
	const GLsizei length = static_cast<GLsizei>( Min( idStr::Length( label ), 255 ) );
	glObjectLabel( identifier, name, length, label );
}

void R_GLDebug_LabelBuffer( GLuint name, const char *label ) {
	if ( glIsBuffer != NULL && glIsBuffer( name ) != GL_TRUE ) {
		return;
	}
	R_GLDebug_LabelObject( GL_BUFFER, name, label );
}

void R_GLDebug_LabelTexture( GLuint name, const char *label ) {
	if ( glIsTexture( name ) != GL_TRUE ) {
		return;
	}
	R_GLDebug_LabelObject( GL_TEXTURE, name, label );
}

void R_GLDebug_LabelFramebuffer( GLuint name, const char *label ) {
	if ( name == 0 || label == NULL || label[0] == '\0' || !R_GLDebugObjectLabels_Available() ) {
		return;
	}
	if ( glIsFramebuffer != NULL && glIsFramebuffer( name ) != GL_TRUE ) {
		if ( glBindFramebuffer == NULL ) {
			return;
		}
		GLint previousReadFramebuffer = 0;
		GLint previousDrawFramebuffer = 0;
		glGetIntegerv( GL_READ_FRAMEBUFFER_BINDING, &previousReadFramebuffer );
		glGetIntegerv( GL_DRAW_FRAMEBUFFER_BINDING, &previousDrawFramebuffer );
		R_GLStateCache().BindFramebuffer( GL_FRAMEBUFFER, name );
		R_GLDebug_LabelObject( GL_FRAMEBUFFER, name, label );
		R_GLStateCache().BindFramebuffer( GL_READ_FRAMEBUFFER, static_cast<GLuint>( previousReadFramebuffer ) );
		R_GLStateCache().BindFramebuffer( GL_DRAW_FRAMEBUFFER, static_cast<GLuint>( previousDrawFramebuffer ) );
		return;
	}
	R_GLDebug_LabelObject( GL_FRAMEBUFFER, name, label );
}

void R_GLDebug_LabelProgram( GLuint name, const char *label ) {
	if ( glIsProgram != NULL && glIsProgram( name ) != GL_TRUE ) {
		return;
	}
	R_GLDebug_LabelObject( GL_PROGRAM, name, label );
}

void R_GLDebug_LabelVertexArray( GLuint name, const char *label ) {
	if ( name == 0 || label == NULL || label[0] == '\0' || !R_GLDebugObjectLabels_Available() || glBindVertexArray == NULL ) {
		return;
	}
	if ( glIsVertexArray != NULL && glIsVertexArray( name ) != GL_TRUE ) {
		GLint previousVertexArray = 0;
		glGetIntegerv( GL_VERTEX_ARRAY_BINDING, &previousVertexArray );
		R_GLStateCache().BindVertexArray( name );
		R_GLDebug_LabelObject( GL_VERTEX_ARRAY, name, label );
		R_GLStateCache().BindVertexArray( static_cast<GLuint>( previousVertexArray ) );
		return;
	}
	R_GLDebug_LabelObject( GL_VERTEX_ARRAY, name, label );
}

void R_GLDebug_LabelSampler( GLuint name, const char *label ) {
	if ( glIsSampler != NULL && glIsSampler( name ) != GL_TRUE ) {
		return;
	}
	R_GLDebug_LabelObject( GL_SAMPLER, name, label );
}

idGLDebugScope::idGLDebugScope( const char *name, unsigned int id ) {
	active = false;
	previousScope = rg_glDebugCurrentScope;
	if ( name == NULL || name[0] == '\0' || !R_GLDebugScope_Available() ) {
		return;
	}
	if ( rg_glDebugOutputSynchronous ) {
		idStr::Copynz( scopeName, name, sizeof( scopeName ) );
		rg_glDebugCurrentScope = scopeName;
	}
	glPushDebugGroup( GL_DEBUG_SOURCE_APPLICATION, static_cast<GLuint>( id ), static_cast<GLsizei>( idStr::Length( name ) ), name );
	active = true;
}

idGLDebugScope::~idGLDebugScope() {
	if ( active && glPopDebugGroup != NULL ) {
		glPopDebugGroup();
	}
	rg_glDebugCurrentScope = previousScope;
}
