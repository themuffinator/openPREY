// Copyright (C) 2026 DarkMatter Productions
//

#include "tr_local.h"

static volatile sig_atomic_t r_lastRendererStartupPhase = RENDERER_STARTUP_PHASE_IDLE;

static rendererStartupPhase_t R_NormalizeRendererStartupPhase( sig_atomic_t phase ) {
	if ( phase < RENDERER_STARTUP_PHASE_IDLE || phase >= RENDERER_STARTUP_PHASE_COUNT ) {
		return RENDERER_STARTUP_PHASE_IDLE;
	}
	return static_cast<rendererStartupPhase_t>( phase );
}

const char *R_RendererStartupPhaseName( rendererStartupPhase_t phase ) {
	switch ( phase ) {
	case RENDERER_STARTUP_PHASE_IDLE:
		return "idle";
	case RENDERER_STARTUP_PHASE_R_INIT_OPENGL:
		return "R_InitOpenGL";
	case RENDERER_STARTUP_PHASE_R_CHECK_PORTABLE_EXTENSIONS:
		return "R_CheckPortableExtensions";
	case RENDERER_STARTUP_PHASE_R_ARB2_INIT:
		return "R_ARB2_Init";
	case RENDERER_STARTUP_PHASE_R_RELOAD_ARB_PROGRAMS:
		return "R_ReloadARBPrograms_f";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_FULL_UPLOAD:
		return "R_ReloadARBPrograms_f: full interaction upload";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_SIMPLE_UPLOAD:
		return "R_ReloadARBPrograms_f: simple interaction upload";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_SKIP_FULL_UPLOAD:
		return "R_ReloadARBPrograms_f: skipped full interaction upload";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_COLOR_MODE:
		return "R_ReloadARBPrograms_f: interaction color mode";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_FULL_SELECTION:
		return "R_ReloadARBPrograms_f: selected full interaction";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_SIMPLE_SELECTION:
		return "R_ReloadARBPrograms_f: selected simple interaction";
	case RENDERER_STARTUP_PHASE_R_RENDERER_UPLOAD_INIT:
		return "R_RendererUpload_Init";
	case RENDERER_STARTUP_PHASE_VERTEX_CACHE_INIT:
		return "vertexCache.Init";
	case RENDERER_STARTUP_PHASE_SET_BACK_END_RENDERER:
		return "tr.SetBackEndRenderer";
	case RENDERER_STARTUP_PHASE_READY:
		return "renderer startup complete";
	case RENDERER_STARTUP_PHASE_FIRST_ARB2_INTERACTION_HANDOFF:
		return "first ARB2 interaction handoff";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_DRIVER_BYPASS:
		return "ARB2 interaction driver bypass";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_BYPASS_STATE_RESTORED:
		return "ARB2 interaction bypass state restored";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_BYPASS_LIGHT_SCALE:
		return "ARB2 interaction bypass light scale";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_BYPASS_LIGHT_SCALE_SKIPPED:
		return "ARB2 interaction bypass light scale skipped";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_BYPASS_AMBIENT_RESCUE:
		return "ARB2 interaction bypass ambient rescue";
	case RENDERER_STARTUP_PHASE_ARB2_INTERACTION_BYPASS_FRAME_TAIL:
		return "ARB2 interaction bypass frame tail";
	default:
		return "unknown renderer startup phase";
	}
}

void R_SetRendererStartupPhase( rendererStartupPhase_t phase ) {
	r_lastRendererStartupPhase = static_cast<sig_atomic_t>( R_NormalizeRendererStartupPhase( phase ) );
}

void R_RecordRendererStartupPhase( rendererStartupPhase_t phase ) {
	R_SetRendererStartupPhase( phase );
	common->Printf( "renderer startup phase: %s\n", R_RendererStartupPhaseName( phase ) );
}

rendererStartupPhase_t R_GetRendererStartupPhase( void ) {
	return R_NormalizeRendererStartupPhase( r_lastRendererStartupPhase );
}

const char *R_RendererStartupPhaseSignalName( void ) {
	return R_RendererStartupPhaseName( R_NormalizeRendererStartupPhase( r_lastRendererStartupPhase ) );
}
