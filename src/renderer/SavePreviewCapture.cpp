#include "tr_local.h"
#include "SavePreviewCapture.h"

#ifndef OPENQ4_RENDERER_VK_MODULE
static GLuint savePreviewBuffer = 0;
static GLsync savePreviewFence = NULL;
static int savePreviewState = 0; // idle, requested, submitted, mapped; -1 failed
static int savePreviewWidth = 0;
static int savePreviewHeight = 0;

bool RB_RequestSavePreview() {
	if ( savePreviewState != 0 || !glConfig.isInitialized || r_frontBuffer.GetBool() ||
		glFenceSync == NULL || glClientWaitSync == NULL || glDeleteSync == NULL ||
		glMapBufferRange == NULL || glUnmapBufferARB == NULL || glGetBufferParameterivARB == NULL ) return false;
	savePreviewState = 1;
	return true;
}

void RB_QueueSavePreview() {
	if ( savePreviewState != 1 || tr.takingScreenshot ) return;
	savePreviewState = -1;
	savePreviewWidth = glConfig.vidWidth;
	savePreviewHeight = glConfig.vidHeight;
	const int64 pixels = (int64)savePreviewWidth * savePreviewHeight;
	if ( savePreviewWidth <= 0 || savePreviewHeight <= 0 || pixels > 33554432 ) return;
	GLint oldBuffer = 0, oldReadBuffer = 0;
	const GLenum packNames[] = { GL_PACK_ALIGNMENT, GL_PACK_ROW_LENGTH, GL_PACK_SKIP_PIXELS, GL_PACK_SKIP_ROWS };
	GLint oldPack[4];
	for ( int i = 0; i < 4; ++i ) glGetIntegerv( packNames[i], &oldPack[i] );
	glGetIntegerv( GL_PIXEL_PACK_BUFFER_BINDING, &oldBuffer );
	glGetIntegerv( GL_READ_BUFFER, &oldReadBuffer );
	glGenBuffersARB( 1, &savePreviewBuffer );
	if ( savePreviewBuffer == 0 ) return;
	glBindBufferARB( GL_PIXEL_PACK_BUFFER_ARB, savePreviewBuffer );
	glBufferDataARB( GL_PIXEL_PACK_BUFFER_ARB, (GLsizeiptrARB)( pixels * 4 ), NULL, GL_STREAM_READ_ARB );
	GLint allocated = 0;
	glGetBufferParameterivARB( GL_PIXEL_PACK_BUFFER_ARB, GL_BUFFER_SIZE, &allocated );
	if ( allocated != pixels * 4 ) {
		glBindBufferARB( GL_PIXEL_PACK_BUFFER_ARB, oldBuffer );
		return;
	}
	for ( int i = 0; i < 4; ++i ) glPixelStorei( packNames[i], i == 0 ? 1 : 0 );
	glReadBuffer( GL_BACK );
	glReadPixels( 0, 0, savePreviewWidth, savePreviewHeight, GL_RGBA, GL_UNSIGNED_BYTE, NULL );
	savePreviewFence = glFenceSync( GL_SYNC_GPU_COMMANDS_COMPLETE, 0 );
	glReadBuffer( oldReadBuffer );
	glBindBufferARB( GL_PIXEL_PACK_BUFFER_ARB, oldBuffer );
	for ( int i = 0; i < 4; ++i ) glPixelStorei( packNames[i], oldPack[i] );
	if ( savePreviewFence != NULL ) savePreviewState = 2;
}

int RB_PollSavePreview( const byte *&pixels, int &width, int &height, bool &topDown, bool &bgra ) {
	if ( savePreviewState <= 0 ) return -1;
	if ( savePreviewState == 1 ) return 0;
	const GLenum result = glClientWaitSync( savePreviewFence, 0, 0 );
	if ( result == GL_TIMEOUT_EXPIRED ) return 0;
	if ( result != GL_ALREADY_SIGNALED && result != GL_CONDITION_SATISFIED ) return -1;
	GLint oldBuffer = 0;
	glGetIntegerv( GL_PIXEL_PACK_BUFFER_BINDING, &oldBuffer );
	glBindBufferARB( GL_PIXEL_PACK_BUFFER_ARB, savePreviewBuffer );
	pixels = static_cast<const byte *>( glMapBufferRange( GL_PIXEL_PACK_BUFFER_ARB, 0,
		(GLsizeiptrARB)( (int64)savePreviewWidth * savePreviewHeight * 4 ), GL_MAP_READ_BIT ) );
	glBindBufferARB( GL_PIXEL_PACK_BUFFER_ARB, oldBuffer );
	if ( pixels == NULL ) return -1;
	savePreviewState = 3;
	width = savePreviewWidth;
	height = savePreviewHeight;
	topDown = bgra = false;
	return 1;
}

void RB_ReleaseSavePreview() {
	if ( savePreviewBuffer != 0 ) {
		if ( savePreviewState == 3 ) {
			GLint oldBuffer = 0;
			glGetIntegerv( GL_PIXEL_PACK_BUFFER_BINDING, &oldBuffer );
			glBindBufferARB( GL_PIXEL_PACK_BUFFER_ARB, savePreviewBuffer );
			glUnmapBufferARB( GL_PIXEL_PACK_BUFFER_ARB );
			glBindBufferARB( GL_PIXEL_PACK_BUFFER_ARB, oldBuffer );
		}
		glDeleteBuffersARB( 1, &savePreviewBuffer );
	}
	if ( savePreviewFence != NULL ) glDeleteSync( savePreviewFence );
	savePreviewBuffer = 0;
	savePreviewFence = NULL;
	savePreviewState = 0;
}
#endif
