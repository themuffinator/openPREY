#ifndef __LEVELSHOTDEPTH_H__
#define __LEVELSHOTDEPTH_H__

/*
===============================================================================

	levelshotProbe depth readback. While linearDepth is set, the GL backend copies
	the main view's depth buffer (never a subview or the portal sky) into it as
	distances along the view axis, top row first. Pixels with no geometry read
	back as -1. Defined in tr_main.cpp so every renderer module links it; only
	the GL backend fills it.

===============================================================================
*/

typedef struct levelshotDepthCapture_s {
	float *		linearDepth;
	int			width;
	int			height;
	bool		captured;
} levelshotDepthCapture_t;

extern levelshotDepthCapture_t tr_levelshotDepthCapture;

#endif /* !__LEVELSHOTDEPTH_H__ */
