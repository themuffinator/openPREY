// Native Cocoa/NSOpenGL/CGL state for the legacy comparison-only backend
// (platform_backend=native). This header must never be imported from SDL3
// release-path sources; the containment policy tests reject NSOpenGL/CGL
// tokens outside the native fallback boundary
// (docs/dev/macos-native-backend-containment-policy.md).

#import "macos_sys.h"

#import <OpenGL/CGLTypes.h>

@class NSOpenGLContext, NSWindow;

typedef struct {
    CGDirectDisplayID     display;
    uint32_t              tableSize;
    CGGammaValue	 *red;
    CGGammaValue	 *blue;
    CGGammaValue	 *green;
} glwgamma_t;

typedef struct
{
    CGDirectDisplayID	display;
    NSDictionary		*desktopMode;
    NSDictionary		*gameMode;

    CGDisplayCount		displayCount;
    glwgamma_t			*originalDisplayGammaTables;
    glwgamma_t			inGameTable;
    glwgamma_t			tempTable;

    NSOpenGLContext		*_ctx;
    CGLContextObj		_cgl_ctx;
    bool				_ctx_is_current;
    NSWindow			*window;

    FILE				*log_fp;

    unsigned int		bufferSwapCount;
    unsigned int		glPauseCount;
} glwstate_t;

extern glwstate_t glw_state;

#define OSX_SetGLContext(context) \
do { \
    NSOpenGLContext *_context = (context); \
    glw_state._ctx = _context; \
    glw_state._cgl_ctx = [_context cglContext]; \
    glw_state._ctx_is_current = NO; \
} while (0)

#define OSX_GetNSGLContext() glw_state._ctx
#define OSX_GetCGLContext() glw_state._cgl_ctx

#define OSX_GLContextIsCurrent() glw_state._ctx_is_current
#define OSX_GLContextSetCurrent() \
do { \
  [glw_state._ctx makeCurrentContext]; \
  glw_state._ctx_is_current = (glw_state._ctx != nil); \
} while (0)

#define OSX_GLContextClearCurrent() \
do { \
  [NSOpenGLContext clearCurrentContext]; \
  glw_state._ctx_is_current = NO; \
} while (0)
