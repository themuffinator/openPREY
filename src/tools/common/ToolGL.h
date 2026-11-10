#ifndef __TOOLGL_H__
#define __TOOLGL_H__

#include "../../sys/win32/win_local.h"
#include "../../renderer/tr_local.h"

ID_INLINE PIXELFORMATDESCRIPTOR ToolGL_DefaultPixelFormatDescriptor( bool zbuffer ) {
	PIXELFORMATDESCRIPTOR pfd = {
		sizeof( PIXELFORMATDESCRIPTOR ),
		1,
		PFD_DRAW_TO_WINDOW |
		PFD_SUPPORT_OPENGL |
		PFD_DOUBLEBUFFER,
		PFD_TYPE_RGBA,
		32,
		0, 0, 0, 0, 0, 0,
		8,
		0,
		0,
		0, 0, 0, 0,
		24,
		8,
		0,
		PFD_MAIN_PLANE,
		0,
		0, 0, 0
	};

	if ( !zbuffer ) {
		pfd.cDepthBits = 0;
	}

	return pfd;
}

ID_INLINE bool ToolGL_SetupPixelFormat( HDC hDC, bool zbuffer, int *selectedPixelFormat = NULL ) {
	const int existingPixelFormat = GetPixelFormat( hDC );
	if ( existingPixelFormat > 0 ) {
		if ( selectedPixelFormat != NULL ) {
			*selectedPixelFormat = existingPixelFormat;
		}
		return true;
	}

	PIXELFORMATDESCRIPTOR pfd;
	int pixelFormat = 0;

	if ( win32.pixelformat > 0 && win32.pfd.nSize == sizeof( PIXELFORMATDESCRIPTOR ) ) {
		pfd = win32.pfd;
		pixelFormat = win32.pixelformat;
	} else {
		pfd = ToolGL_DefaultPixelFormatDescriptor( zbuffer );
		pixelFormat = ChoosePixelFormat( hDC, &pfd );
		if ( pixelFormat <= 0 ) {
			return false;
		}

		DescribePixelFormat( hDC, pixelFormat, sizeof( pfd ), &pfd );
	}

	if ( !SetPixelFormat( hDC, pixelFormat, &pfd ) ) {
		return false;
	}

	if ( selectedPixelFormat != NULL ) {
		*selectedPixelFormat = pixelFormat;
	}

	return true;
}

ID_INLINE GLboolean ToolGL_DisableMultisampleForEditor( void ) {
	if ( !( GLEW_ARB_multisample || GLEW_VERSION_1_3 ) ) {
		return GL_FALSE;
	}

	const GLboolean multisampleWasEnabled = glIsEnabled( GL_MULTISAMPLE );
	if ( multisampleWasEnabled ) {
		qglDisable( GL_MULTISAMPLE );
	}

	return multisampleWasEnabled;
}

ID_INLINE void ToolGL_RestoreMultisampleForEditor( GLboolean multisampleWasEnabled ) {
	if ( multisampleWasEnabled ) {
		qglEnable( GL_MULTISAMPLE );
	}
}

#endif
