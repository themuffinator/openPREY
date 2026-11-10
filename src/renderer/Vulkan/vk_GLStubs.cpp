// Copyright (C) 2026 DarkMatter Productions
//

/*
===============================================================================

	Vulkan module GL stubs (Phase C,
	docs/dev/archive/2026-10-18/plans/2026-07-17-vulkan-phase-c.md).

	The Vulkan module compiles the shared renderer front-end, whose mixed
	TUs still carry GL call sites (image bind/copy paths, GPU timers, caps
	probes, debug draws). The debug tools (tr_rendertools.cpp) are the one
	exception that runs: the fixed-function entry points they use forward to
	the emulation in vk_DebugTools.cpp, which draws them while
	VK_DebugTools_DrawView is active and ignores them otherwise. Nothing else
	executes under the Vulkan backend — glConfig-driven guards and the
	replaced GL-backend TUs keep those paths cold — but they must link. GLEW
	builds in its hook-resolving dedicated flavor (the hook below returns
	NULL; glewInit is never called), and the GL 1.1 entry points resolve to
	these no-ops. On Windows the module compiles with GLAPI=extern so GLEW's
	GL 1.1 declarations lose their dllimport decoration.

===============================================================================
*/

#ifdef OPENQ4_RENDERER_VK_MODULE

#include "../../idlib/precompiled.h"
#pragma hdrstop

#include "../tr_local.h"

bool VK_GuiExecutor_ReadPixels( int x, int y, int width, int height, void *pixels, int components );

// The debug tools' fixed-function calls (tr_rendertools.cpp, tr_trace.cpp)
// drive a small emulation in vk_DebugTools.cpp. It only records inside
// VK_DebugTools_DrawView; everywhere else these stay the no-ops the rest of
// the shared front end relies on.
void VK_DebugGL_Begin( GLenum mode );
void VK_DebugGL_End( void );
void VK_DebugGL_Vertex3f( float x, float y, float z );
void VK_DebugGL_Color4f( float r, float g, float b, float a );
void VK_DebugGL_TexCoord2f( float s, float t );
void VK_DebugGL_VertexPointer( int size, GLenum type, int stride, const void *pointer );
void VK_DebugGL_ColorPointer( int size, GLenum type, int stride, const void *pointer );
void VK_DebugGL_TexCoordPointer( int size, GLenum type, int stride, const void *pointer );
void VK_DebugGL_ClientState( GLenum array, bool enable );
void VK_DebugGL_ArrayElement( int i );
void VK_DebugGL_DrawElements( GLenum mode, int count, GLenum type, const void *indices );
void VK_DebugGL_Enable( GLenum cap, bool enable );
void VK_DebugGL_PolygonOffset( float factor, float units );
void VK_DebugGL_DepthRange( double zNear, double zFar );
void VK_DebugGL_Scissor( int x, int y, int width, int height );
void VK_DebugGL_LineWidth( float width );
void VK_DebugGL_PointSize( float size );
void VK_DebugGL_DepthMask( bool write );
void VK_DebugGL_ColorMask( bool r, bool g, bool b, bool a );
void VK_DebugGL_StencilFunc( GLenum func, int ref, unsigned int mask );
void VK_DebugGL_StencilOp( GLenum fail, GLenum zfail, GLenum zpass );
void VK_DebugGL_ClearColor( float r, float g, float b, float a );
void VK_DebugGL_ClearStencil( int s );
void VK_DebugGL_Clear( GLbitfield mask );
void VK_DebugGL_MatrixMode( GLenum mode );
void VK_DebugGL_LoadMatrixf( const float *m );
void VK_DebugGL_LoadIdentity( void );
void VK_DebugGL_PushMatrix( void );
void VK_DebugGL_PopMatrix( void );
void VK_DebugGL_Ortho( double left, double right, double bottom, double top, double zNear, double zFar );
void VK_DebugGL_PushAttrib( void );
void VK_DebugGL_PopAttrib( void );
void VK_DebugGL_RasterPos2f( float x, float y );
void VK_DebugGL_DrawPixels( int width, int height, GLenum format, GLenum type, const void *pixels );

void glAccum(GLenum op, GLfloat value){};
void glAlphaFunc(GLenum func, GLclampf ref){};
GLboolean glAreTexturesResident(GLsizei n, const GLuint *textures, GLboolean *residences){return GL_FALSE;};
void glArrayElement(GLint i){ VK_DebugGL_ArrayElement( i ); }
void glBegin(GLenum mode){ VK_DebugGL_Begin( mode ); }
void glBindTexture(GLenum target, GLuint texture){};
void glBitmap(GLsizei width, GLsizei height, GLfloat xorig, GLfloat yorig, GLfloat xmove, GLfloat ymove, const GLubyte *bitmap){};
void glBlendFunc(GLenum sfactor, GLenum dfactor){};
void glCallList(GLuint list){};
void glCallLists(GLsizei n, GLenum type, const GLvoid *lists){};
void glClear(GLbitfield mask){ VK_DebugGL_Clear( mask ); }
void glClearAccum(GLfloat red, GLfloat green, GLfloat blue, GLfloat alpha){};
void glClearColor(GLclampf red, GLclampf green, GLclampf blue, GLclampf alpha){ VK_DebugGL_ClearColor( red, green, blue, alpha ); }
void glClearDepth(GLclampd depth){};
void glClearIndex(GLfloat c){};
void glClearStencil(GLint s){ VK_DebugGL_ClearStencil( s ); }
void glClipPlane(GLenum plane, const GLdouble *equation){};
void glColor3b(GLbyte red, GLbyte green, GLbyte blue){};
void glColor3bv(const GLbyte *v){};
void glColor3d(GLdouble red, GLdouble green, GLdouble blue){};
void glColor3dv(const GLdouble *v){};
void glColor3f(GLfloat red, GLfloat green, GLfloat blue){ VK_DebugGL_Color4f( red, green, blue, 1.0f ); }
void glColor3fv(const GLfloat *v){ VK_DebugGL_Color4f( v[0], v[1], v[2], 1.0f ); }
void glColor3i(GLint red, GLint green, GLint blue){};
void glColor3iv(const GLint *v){};
void glColor3s(GLshort red, GLshort green, GLshort blue){};
void glColor3sv(const GLshort *v){};
void glColor3ub(GLubyte red, GLubyte green, GLubyte blue){ VK_DebugGL_Color4f( red / 255.0f, green / 255.0f, blue / 255.0f, 1.0f ); }
void glColor3ubv(const GLubyte *v){ VK_DebugGL_Color4f( v[0] / 255.0f, v[1] / 255.0f, v[2] / 255.0f, 1.0f ); }
void glColor3ui(GLuint red, GLuint green, GLuint blue){};
void glColor3uiv(const GLuint *v){};
void glColor3us(GLushort red, GLushort green, GLushort blue){};
void glColor3usv(const GLushort *v){};
void glColor4b(GLbyte red, GLbyte green, GLbyte blue, GLbyte alpha){};
void glColor4bv(const GLbyte *v){};
void glColor4d(GLdouble red, GLdouble green, GLdouble blue, GLdouble alpha){};
void glColor4dv(const GLdouble *v){};
void glColor4f(GLfloat red, GLfloat green, GLfloat blue, GLfloat alpha){ VK_DebugGL_Color4f( red, green, blue, alpha ); }
void glColor4fv(const GLfloat *v){ VK_DebugGL_Color4f( v[0], v[1], v[2], v[3] ); }
void glColor4i(GLint red, GLint green, GLint blue, GLint alpha){};
void glColor4iv(const GLint *v){};
void glColor4s(GLshort red, GLshort green, GLshort blue, GLshort alpha){};
void glColor4sv(const GLshort *v){};
void glColor4ub(GLubyte red, GLubyte green, GLubyte blue, GLubyte alpha){ VK_DebugGL_Color4f( red / 255.0f, green / 255.0f, blue / 255.0f, alpha / 255.0f ); }
void glColor4ubv(const GLubyte *v){ VK_DebugGL_Color4f( v[0] / 255.0f, v[1] / 255.0f, v[2] / 255.0f, v[3] / 255.0f ); }
void glColor4ui(GLuint red, GLuint green, GLuint blue, GLuint alpha){};
void glColor4uiv(const GLuint *v){};
void glColor4us(GLushort red, GLushort green, GLushort blue, GLushort alpha){};
void glColor4usv(const GLushort *v){};
void glColorMask(GLboolean red, GLboolean green, GLboolean blue, GLboolean alpha){ VK_DebugGL_ColorMask( red != GL_FALSE, green != GL_FALSE, blue != GL_FALSE, alpha != GL_FALSE ); }
void glColorMaterial(GLenum face, GLenum mode){};
void glColorPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *pointer){ VK_DebugGL_ColorPointer( size, type, stride, pointer ); }
void glCopyPixels(GLint x, GLint y, GLsizei width, GLsizei height, GLenum type){};
void glCopyTexImage1D(GLenum target, GLint level, GLenum internalFormat, GLint x, GLint y, GLsizei width, GLint border){};
void glCopyTexImage2D(GLenum target, GLint level, GLenum internalFormat, GLint x, GLint y, GLsizei width, GLsizei height, GLint border){};
void glCopyTexSubImage1D(GLenum target, GLint level, GLint xoffset, GLint x, GLint y, GLsizei width){};
void glCopyTexSubImage2D(GLenum target, GLint level, GLint xoffset, GLint yoffset, GLint x, GLint y, GLsizei width, GLsizei height){};
void glCullFace(GLenum mode){};
void glDeleteLists(GLuint list, GLsizei range){};
void glDeleteTextures(GLsizei n, const GLuint *textures){};
void glDepthFunc(GLenum func){};
void glDepthMask(GLboolean flag){ VK_DebugGL_DepthMask( flag != GL_FALSE ); }
void glDepthRange(GLclampd zNear, GLclampd zFar){ VK_DebugGL_DepthRange( zNear, zFar ); }
void glDisable(GLenum cap){ VK_DebugGL_Enable( cap, false ); }
void glDisableClientState(GLenum array){ VK_DebugGL_ClientState( array, false ); }
void glDrawArrays(GLenum mode, GLint first, GLsizei count){};
void glDrawBuffer(GLenum mode){};
void glDrawElements(GLenum mode, GLsizei count, GLenum type, const GLvoid *indices){ VK_DebugGL_DrawElements( mode, count, type, indices ); }
void glDrawPixels(GLsizei width, GLsizei height, GLenum format, GLenum type, const GLvoid *pixels){ VK_DebugGL_DrawPixels( width, height, format, type, pixels ); }
void glEdgeFlag(GLboolean flag){};
void glEdgeFlagPointer(GLsizei stride, const GLvoid *pointer){};
void glEdgeFlagv(const GLboolean *flag){};
void glEnable(GLenum cap){ VK_DebugGL_Enable( cap, true ); }
void glEnableClientState(GLenum array){ VK_DebugGL_ClientState( array, true ); }
void glEnd(void){ VK_DebugGL_End(); }
void glEndList(void){};
void glEvalCoord1d(GLdouble u){};
void glEvalCoord1dv(const GLdouble *u){};
void glEvalCoord1f(GLfloat u){};
void glEvalCoord1fv(const GLfloat *u){};
void glEvalCoord2d(GLdouble u, GLdouble v){};
void glEvalCoord2dv(const GLdouble *u){};
void glEvalCoord2f(GLfloat u, GLfloat v){};
void glEvalCoord2fv(const GLfloat *u){};
void glEvalMesh1(GLenum mode, GLint i1, GLint i2){};
void glEvalMesh2(GLenum mode, GLint i1, GLint i2, GLint j1, GLint j2){};
void glEvalPoint1(GLint i){};
void glEvalPoint2(GLint i, GLint j){};
void glFeedbackBuffer(GLsizei size, GLenum type, GLfloat *buffer){};
void glFinish(void){};
void glFlush(void){};
void glFogf(GLenum pname, GLfloat param){};
void glFogfv(GLenum pname, const GLfloat *params){};
void glFogi(GLenum pname, GLint param){};
void glFogiv(GLenum pname, const GLint *params){};
void glFrontFace(GLenum mode){};
void glFrustum(GLdouble left, GLdouble right, GLdouble bottom, GLdouble top, GLdouble zNear, GLdouble zFar){};
GLuint glGenLists(GLsizei range){return 0;};
void glGenTextures(GLsizei n, GLuint *textures){};
void glGetBooleanv(GLenum pname, GLboolean *params){};
void glGetClipPlane(GLenum plane, GLdouble *equation){};
void glGetDoublev(GLenum pname, GLdouble *params){};
GLenum glGetError(void){return 0;};
void glGetFloatv(GLenum pname, GLfloat *params){};
void glGetIntegerv(GLenum pname, GLint *params){
	switch( pname ) {
		case GL_MAX_TEXTURE_SIZE: *params = 1024; break;
		case GL_MAX_TEXTURE_UNITS_ARB: *params = 2; break;
		default: *params = 0; break;
	}
};
void glGetLightfv(GLenum light, GLenum pname, GLfloat *params){};
void glGetLightiv(GLenum light, GLenum pname, GLint *params){};
void glGetMapdv(GLenum target, GLenum query, GLdouble *v){};
void glGetMapfv(GLenum target, GLenum query, GLfloat *v){};
void glGetMapiv(GLenum target, GLenum query, GLint *v){};
void glGetMaterialfv(GLenum face, GLenum pname, GLfloat *params){};
void glGetMaterialiv(GLenum face, GLenum pname, GLint *params){};
void glGetPixelMapfv(GLenum map, GLfloat *values){};
void glGetPixelMapuiv(GLenum map, GLuint *values){};
void glGetPixelMapusv(GLenum map, GLushort *values){};
void glGetPointerv(GLenum pname, GLvoid* *params){};
void glGetPolygonStipple(GLubyte *mask){};
const GLubyte * glGetString(GLenum name){
	switch( name ) {
		case GL_EXTENSIONS: return (GLubyte *)"GL_ARB_multitexture GL_ARB_texture_env_combine GL_ARB_texture_cube_map GL_ARB_texture_env_dot3";
	}
	return (const GLubyte *)"";
};
void glGetTexEnvfv(GLenum target, GLenum pname, GLfloat *params){};
void glGetTexEnviv(GLenum target, GLenum pname, GLint *params){};
void glGetTexGendv(GLenum coord, GLenum pname, GLdouble *params){};
void glGetTexGenfv(GLenum coord, GLenum pname, GLfloat *params){};
void glGetTexGeniv(GLenum coord, GLenum pname, GLint *params){};
void glGetTexImage(GLenum target, GLint level, GLenum format, GLenum type, GLvoid *pixels){};
void glGetTexLevelParameterfv(GLenum target, GLint level, GLenum pname, GLfloat *params){};
void glGetTexLevelParameteriv(GLenum target, GLint level, GLenum pname, GLint *params){};
void glGetTexParameterfv(GLenum target, GLenum pname, GLfloat *params){};
void glGetTexParameteriv(GLenum target, GLenum pname, GLint *params){};
void glHint(GLenum target, GLenum mode){};
void glIndexMask(GLuint mask){};
void glIndexPointer(GLenum type, GLsizei stride, const GLvoid *pointer){};
void glIndexd(GLdouble c){};
void glIndexdv(const GLdouble *c){};
void glIndexf(GLfloat c){};
void glIndexfv(const GLfloat *c){};
void glIndexi(GLint c){};
void glIndexiv(const GLint *c){};
void glIndexs(GLshort c){};
void glIndexsv(const GLshort *c){};
void glIndexub(GLubyte c){};
void glIndexubv(const GLubyte *c){};
void glInitNames(void){};
void glInterleavedArrays(GLenum format, GLsizei stride, const GLvoid *pointer){};
GLboolean glIsEnabled(GLenum cap){return GL_FALSE;};
GLboolean glIsList(GLuint list){return GL_FALSE;};
GLboolean glIsTexture(GLuint texture){return GL_FALSE;};
void glLightModelf(GLenum pname, GLfloat param){};
void glLightModelfv(GLenum pname, const GLfloat *params){};
void glLightModeli(GLenum pname, GLint param){};
void glLightModeliv(GLenum pname, const GLint *params){};
void glLightf(GLenum light, GLenum pname, GLfloat param){};
void glLightfv(GLenum light, GLenum pname, const GLfloat *params){};
void glLighti(GLenum light, GLenum pname, GLint param){};
void glLightiv(GLenum light, GLenum pname, const GLint *params){};
void glLineStipple(GLint factor, GLushort pattern){};
void glLineWidth(GLfloat width){ VK_DebugGL_LineWidth( width ); }
void glListBase(GLuint base){};
void glLoadIdentity(void){ VK_DebugGL_LoadIdentity(); }
void glLoadMatrixd(const GLdouble *m){};
void glLoadMatrixf(const GLfloat *m){ VK_DebugGL_LoadMatrixf( m ); }
void glLoadName(GLuint name){};
void glLogicOp(GLenum opcode){};
void glMap1d(GLenum target, GLdouble u1, GLdouble u2, GLint stride, GLint order, const GLdouble *points){};
void glMap1f(GLenum target, GLfloat u1, GLfloat u2, GLint stride, GLint order, const GLfloat *points){};
void glMap2d(GLenum target, GLdouble u1, GLdouble u2, GLint ustride, GLint uorder, GLdouble v1, GLdouble v2, GLint vstride, GLint vorder, const GLdouble *points){};
void glMap2f(GLenum target, GLfloat u1, GLfloat u2, GLint ustride, GLint uorder, GLfloat v1, GLfloat v2, GLint vstride, GLint vorder, const GLfloat *points){};
void glMapGrid1d(GLint un, GLdouble u1, GLdouble u2){};
void glMapGrid1f(GLint un, GLfloat u1, GLfloat u2){};
void glMapGrid2d(GLint un, GLdouble u1, GLdouble u2, GLint vn, GLdouble v1, GLdouble v2){};
void glMapGrid2f(GLint un, GLfloat u1, GLfloat u2, GLint vn, GLfloat v1, GLfloat v2){};
void glMaterialf(GLenum face, GLenum pname, GLfloat param){};
void glMaterialfv(GLenum face, GLenum pname, const GLfloat *params){};
void glMateriali(GLenum face, GLenum pname, GLint param){};
void glMaterialiv(GLenum face, GLenum pname, const GLint *params){};
void glMatrixMode(GLenum mode){ VK_DebugGL_MatrixMode( mode ); }
void glMultMatrixd(const GLdouble *m){};
void glMultMatrixf(const GLfloat *m){};
void glNewList(GLuint list, GLenum mode){};
void glNormal3b(GLbyte nx, GLbyte ny, GLbyte nz){};
void glNormal3bv(const GLbyte *v){};
void glNormal3d(GLdouble nx, GLdouble ny, GLdouble nz){};
void glNormal3dv(const GLdouble *v){};
void glNormal3f(GLfloat nx, GLfloat ny, GLfloat nz){};
void glNormal3fv(const GLfloat *v){};
void glNormal3i(GLint nx, GLint ny, GLint nz){};
void glNormal3iv(const GLint *v){};
void glNormal3s(GLshort nx, GLshort ny, GLshort nz){};
void glNormal3sv(const GLshort *v){};
void glNormalPointer(GLenum type, GLsizei stride, const GLvoid *pointer){};
void glOrtho(GLdouble left, GLdouble right, GLdouble bottom, GLdouble top, GLdouble zNear, GLdouble zFar){ VK_DebugGL_Ortho( left, right, bottom, top, zNear, zFar ); }
void glPassThrough(GLfloat token){};
void glPixelMapfv(GLenum map, GLsizei mapsize, const GLfloat *values){};
void glPixelMapuiv(GLenum map, GLsizei mapsize, const GLuint *values){};
void glPixelMapusv(GLenum map, GLsizei mapsize, const GLushort *values){};
void glPixelStoref(GLenum pname, GLfloat param){};
void glPixelStorei(GLenum pname, GLint param){};
void glPixelTransferf(GLenum pname, GLfloat param){};
void glPixelTransferi(GLenum pname, GLint param){};
void glPixelZoom(GLfloat xfactor, GLfloat yfactor){};
void glPointSize(GLfloat size){ VK_DebugGL_PointSize( size ); }
void glPolygonMode(GLenum face, GLenum mode){};
void glPolygonOffset(GLfloat factor, GLfloat units){ VK_DebugGL_PolygonOffset( factor, units ); }
void glPolygonStipple(const GLubyte *mask){};
void glPopAttrib(void){ VK_DebugGL_PopAttrib(); }
void glPopClientAttrib(void){};
void glPopMatrix(void){ VK_DebugGL_PopMatrix(); }
void glPopName(void){};
void glPrioritizeTextures(GLsizei n, const GLuint *textures, const GLclampf *priorities){};
void glPushAttrib(GLbitfield mask){ VK_DebugGL_PushAttrib(); }
void glPushClientAttrib(GLbitfield mask){};
void glPushMatrix(void){ VK_DebugGL_PushMatrix(); }
void glPushName(GLuint name){};
void glRasterPos2d(GLdouble x, GLdouble y){};
void glRasterPos2dv(const GLdouble *v){};
void glRasterPos2f(GLfloat x, GLfloat y){ VK_DebugGL_RasterPos2f( x, y ); }
void glRasterPos2fv(const GLfloat *v){};
void glRasterPos2i(GLint x, GLint y){};
void glRasterPos2iv(const GLint *v){};
void glRasterPos2s(GLshort x, GLshort y){};
void glRasterPos2sv(const GLshort *v){};
void glRasterPos3d(GLdouble x, GLdouble y, GLdouble z){};
void glRasterPos3dv(const GLdouble *v){};
void glRasterPos3f(GLfloat x, GLfloat y, GLfloat z){};
void glRasterPos3fv(const GLfloat *v){};
void glRasterPos3i(GLint x, GLint y, GLint z){};
void glRasterPos3iv(const GLint *v){};
void glRasterPos3s(GLshort x, GLshort y, GLshort z){};
void glRasterPos3sv(const GLshort *v){};
void glRasterPos4d(GLdouble x, GLdouble y, GLdouble z, GLdouble w){};
void glRasterPos4dv(const GLdouble *v){};
void glRasterPos4f(GLfloat x, GLfloat y, GLfloat z, GLfloat w){};
void glRasterPos4fv(const GLfloat *v){};
void glRasterPos4i(GLint x, GLint y, GLint z, GLint w){};
void glRasterPos4iv(const GLint *v){};
void glRasterPos4s(GLshort x, GLshort y, GLshort z, GLshort w){};
void glRasterPos4sv(const GLshort *v){};
void glReadBuffer(GLenum mode){};
// glReadPixels returns nothing, so a failure is latched here for the capture
// code (R_ReadTiledPixels) to collect instead of saving what the buffer held.
static bool vkReadPixelsFailed = false;

bool VK_GLStubs_ConsumeReadPixelsFailure( void ) {
	const bool failed = vkReadPixelsFailed;
	vkReadPixelsFailed = false;
	return failed;
}

void glReadPixels(GLint x, GLint y, GLsizei width, GLsizei height, GLenum format, GLenum type, GLvoid *pixels){
	// GL_RGBA is what R_ReadTiledPixels issues since the ES screenshot fix, and
	// is the only format OpenGL ES guarantees for the default framebuffer.
	// GL_RGB is kept for callers that still ask for it.
	if ( ( format == GL_RGB || format == GL_RGBA ) && type == GL_UNSIGNED_BYTE ) {
		if ( !VK_GuiExecutor_ReadPixels( x, y, width, height, pixels,
				format == GL_RGBA ? 4 : 3 ) ) {
			vkReadPixelsFailed = true;
			common->Warning( "Vulkan glReadPixels failed for %d x %d capture", width, height );
		}
		return;
	}
	vkReadPixelsFailed = true;
	common->Warning( "Vulkan glReadPixels does not support format 0x%x/type 0x%x", format, type );
};
void glRectd(GLdouble x1, GLdouble y1, GLdouble x2, GLdouble y2){};
void glRectdv(const GLdouble *v1, const GLdouble *v2){};
void glRectf(GLfloat x1, GLfloat y1, GLfloat x2, GLfloat y2){};
void glRectfv(const GLfloat *v1, const GLfloat *v2){};
void glRecti(GLint x1, GLint y1, GLint x2, GLint y2){};
void glRectiv(const GLint *v1, const GLint *v2){};
void glRects(GLshort x1, GLshort y1, GLshort x2, GLshort y2){};
void glRectsv(const GLshort *v1, const GLshort *v2){};
GLint glRenderMode(GLenum mode){return 0;};
void glRotated(GLdouble angle, GLdouble x, GLdouble y, GLdouble z){};
void glRotatef(GLfloat angle, GLfloat x, GLfloat y, GLfloat z){};
void glScaled(GLdouble x, GLdouble y, GLdouble z){};
void glScalef(GLfloat x, GLfloat y, GLfloat z){};
void glScissor(GLint x, GLint y, GLsizei width, GLsizei height){ VK_DebugGL_Scissor( x, y, width, height ); }
void glSelectBuffer(GLsizei size, GLuint *buffer){};
void glShadeModel(GLenum mode){};
void glStencilFunc(GLenum func, GLint ref, GLuint mask){ VK_DebugGL_StencilFunc( func, ref, mask ); }
void glStencilMask(GLuint mask){};
void glStencilOp(GLenum fail, GLenum zfail, GLenum zpass){ VK_DebugGL_StencilOp( fail, zfail, zpass ); }
void glTexCoord1d(GLdouble s){};
void glTexCoord1dv(const GLdouble *v){};
void glTexCoord1f(GLfloat s){};
void glTexCoord1fv(const GLfloat *v){};
void glTexCoord1i(GLint s){};
void glTexCoord1iv(const GLint *v){};
void glTexCoord1s(GLshort s){};
void glTexCoord1sv(const GLshort *v){};
void glTexCoord2d(GLdouble s, GLdouble t){};
void glTexCoord2dv(const GLdouble *v){};
void glTexCoord2f(GLfloat s, GLfloat t){ VK_DebugGL_TexCoord2f( s, t ); }
void glTexCoord2fv(const GLfloat *v){ VK_DebugGL_TexCoord2f( v[0], v[1] ); }
void glTexCoord2i(GLint s, GLint t){};
void glTexCoord2iv(const GLint *v){};
void glTexCoord2s(GLshort s, GLshort t){};
void glTexCoord2sv(const GLshort *v){};
void glTexCoord3d(GLdouble s, GLdouble t, GLdouble r){};
void glTexCoord3dv(const GLdouble *v){};
void glTexCoord3f(GLfloat s, GLfloat t, GLfloat r){};
void glTexCoord3fv(const GLfloat *v){};
void glTexCoord3i(GLint s, GLint t, GLint r){};
void glTexCoord3iv(const GLint *v){};
void glTexCoord3s(GLshort s, GLshort t, GLshort r){};
void glTexCoord3sv(const GLshort *v){};
void glTexCoord4d(GLdouble s, GLdouble t, GLdouble r, GLdouble q){};
void glTexCoord4dv(const GLdouble *v){};
void glTexCoord4f(GLfloat s, GLfloat t, GLfloat r, GLfloat q){};
void glTexCoord4fv(const GLfloat *v){};
void glTexCoord4i(GLint s, GLint t, GLint r, GLint q){};
void glTexCoord4iv(const GLint *v){};
void glTexCoord4s(GLshort s, GLshort t, GLshort r, GLshort q){};
void glTexCoord4sv(const GLshort *v){};
void glTexCoordPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *pointer){ VK_DebugGL_TexCoordPointer( size, type, stride, pointer ); }
void glTexEnvf(GLenum target, GLenum pname, GLfloat param){};
void glTexEnvfv(GLenum target, GLenum pname, const GLfloat *params){};
void glTexEnvi(GLenum target, GLenum pname, GLint param){};
void glTexEnviv(GLenum target, GLenum pname, const GLint *params){};
void glTexGend(GLenum coord, GLenum pname, GLdouble param){};
void glTexGendv(GLenum coord, GLenum pname, const GLdouble *params){};
void glTexGenf(GLenum coord, GLenum pname, GLfloat param){};
void glTexGenfv(GLenum coord, GLenum pname, const GLfloat *params){};
void glTexGeni(GLenum coord, GLenum pname, GLint param){};
void glTexGeniv(GLenum coord, GLenum pname, const GLint *params){};
void glTexImage1D(GLenum target, GLint level, GLint internalformat, GLsizei width, GLint border, GLenum format, GLenum type, const GLvoid *pixels){};
void glTexImage2D(GLenum target, GLint level, GLint internalformat, GLsizei width, GLsizei height, GLint border, GLenum format, GLenum type, const GLvoid *pixels) {};
void glTexParameterf(GLenum target, GLenum pname, GLfloat param){};
void glTexParameterfv(GLenum target, GLenum pname, const GLfloat *params){};
void glTexParameteri(GLenum target, GLenum pname, GLint param){};
void glTexParameteriv(GLenum target, GLenum pname, const GLint *params){};
void glTexSubImage1D(GLenum target, GLint level, GLint xoffset, GLsizei width, GLenum format, GLenum type, const GLvoid *pixels){};
void glTexSubImage2D(GLenum target, GLint level, GLint xoffset, GLint yoffset, GLsizei width, GLsizei height, GLenum format, GLenum type, const GLvoid *pixels){};
void glTranslated(GLdouble x, GLdouble y, GLdouble z){};
void glTranslatef(GLfloat x, GLfloat y, GLfloat z){};
void glVertex2d(GLdouble x, GLdouble y){};
void glVertex2dv(const GLdouble *v){};
void glVertex2f(GLfloat x, GLfloat y){ VK_DebugGL_Vertex3f( x, y, 0.0f ); }
void glVertex2fv(const GLfloat *v){};
void glVertex2i(GLint x, GLint y){};
void glVertex2iv(const GLint *v){};
void glVertex2s(GLshort x, GLshort y){};
void glVertex2sv(const GLshort *v){};
void glVertex3d(GLdouble x, GLdouble y, GLdouble z){};
void glVertex3dv(const GLdouble *v){};
void glVertex3f(GLfloat x, GLfloat y, GLfloat z){ VK_DebugGL_Vertex3f( x, y, z ); }
void glVertex3fv(const GLfloat *v){ VK_DebugGL_Vertex3f( v[0], v[1], v[2] ); }
void glVertex3i(GLint x, GLint y, GLint z){};
void glVertex3iv(const GLint *v){};
void glVertex3s(GLshort x, GLshort y, GLshort z){};
void glVertex3sv(const GLshort *v){};
void glVertex4d(GLdouble x, GLdouble y, GLdouble z, GLdouble w){};
void glVertex4dv(const GLdouble *v){};
void glVertex4f(GLfloat x, GLfloat y, GLfloat z, GLfloat w){};
void glVertex4fv(const GLfloat *v){};
void glVertex4i(GLint x, GLint y, GLint z, GLint w){};
void glVertex4iv(const GLint *v){};
void glVertex4s(GLshort x, GLshort y, GLshort z, GLshort w){};
void glVertex4sv(const GLshort *v){};
void glVertexPointer(GLint size, GLenum type, GLsizei stride, const GLvoid *pointer){ VK_DebugGL_VertexPointer( size, type, stride, pointer ); }
void glViewport(GLint x, GLint y, GLsizei width, GLsizei height){};

// GLEW SDL3-loader hook: never called (glewInit is not reached under the
// Vulkan backend), present so the dedicated GLEW flavor links
typedef void ( *openQ4GlewProcAddress_t ) (void);
extern "C" openQ4GlewProcAddress_t OpenQ4_GlewGetProcAddress(const unsigned char *name) {
	(void)name;
	return NULL;
}

#if defined( _WIN32 )
// the qgl loader surface the mixed TUs reference on Windows
PROC ( WINAPI *qwglGetProcAddress )( LPCSTR ) = NULL;

// wgl extension pointers RenderSystem_init externs
#include "../wglext.h"
PFNWGLGETEXTENSIONSSTRINGARBPROC wglGetExtensionsStringARB = NULL;
PFNWGLSWAPINTERVALEXTPROC wglSwapIntervalEXT = NULL;
PFNWGLGETPIXELFORMATATTRIBIVARBPROC wglGetPixelFormatAttribivARB = NULL;
PFNWGLGETPIXELFORMATATTRIBFVARBPROC wglGetPixelFormatAttribfvARB = NULL;
PFNWGLCHOOSEPIXELFORMATARBPROC wglChoosePixelFormatARB = NULL;
PFNWGLCREATEPBUFFERARBPROC wglCreatePbufferARB = NULL;
PFNWGLGETPBUFFERDCARBPROC wglGetPbufferDCARB = NULL;
PFNWGLRELEASEPBUFFERDCARBPROC wglReleasePbufferDCARB = NULL;
PFNWGLDESTROYPBUFFERARBPROC wglDestroyPbufferARB = NULL;
PFNWGLQUERYPBUFFERARBPROC wglQueryPbufferARB = NULL;
PFNWGLBINDTEXIMAGEARBPROC wglBindTexImageARB = NULL;
PFNWGLRELEASETEXIMAGEARBPROC wglReleaseTexImageARB = NULL;
PFNWGLSETPBUFFERATTRIBARBPROC wglSetPbufferAttribARB = NULL;
#endif

bool QGL_Init( const char *dllname ) {
	(void)dllname;
	return true;
}

void QGL_Shutdown( void ) {
}

// RB_UnderwaterViewAvailable lives with the Vulkan underwater pass in
// vk_PostProcess.cpp.

#endif /* OPENQ4_RENDERER_VK_MODULE */
