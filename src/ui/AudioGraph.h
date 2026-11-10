// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

// Transitional stock HUD adapter: a stock radio/voice display drawn under the
// Remastered layout (a HUD without its own Remastered document yet) plots
// playback history. Diegetic monitor waveforms keep their artwork, and Classic
// keeps the stock texture and canned table (ui-visual-design.md 14.8).
static bool DrawPlaybackGraph( idDeviceContext *dc, const idUserInterfaceLocal *gui,
	const char *windowName, const idMaterial *background, const idRectangle &rect, const idVec4 &color ) {
	if ( !cvarSystem->GetCVarBool( "ui_retained" ) || cvarSystem->GetCVarInteger( "ui_hudLayout" ) == 0 ||
		dc == NULL || rect.w <= 0 || rect.h <= 0 ) {
		return false;
	}
	const char *source = gui->GetSourceFile();
	const bool radio = idStr::Icmp( windowName, "waveform" ) == 0 &&
		( idStr::Icmp( source, "guis/hud.gui" ) == 0 || idStr::Icmp( source, "guis/hud_strogg.gui" ) == 0 ||
		  idStr::Icmp( source, "guis/vehicles/hud.gui" ) == 0 || idStr::Icmp( source, "guis/q4xhud.gui" ) == 0 ||
		  idStr::Icmp( source, "guis/q4xhud_strogg.gui" ) == 0 || idStr::Icmp( source, "guis/q4x_cannon_hud.gui" ) == 0 ||
		  idStr::Icmp( source, "guis/vehicles/speederplayerhud.gui" ) == 0 || idStr::Icmp( source, "guis/vehicles/gev_hud.gui" ) == 0 ||
		  idStr::Icmp( source, "guis/vehicles/airassault/turretplayerhud.gui" ) == 0 );
	const bool outgoing = idStr::Icmp( source, "guis/mphud.gui" ) == 0 && idStr::Icmp( windowName, "aud1_wave" ) == 0;
	const bool incoming = idStr::Icmp( source, "guis/mphud.gui" ) == 0 && idStr::Icmp( windowName, "aud2_wave" ) == 0;
	if ( !radio && !outgoing && !incoming ) {
		return false;
	}
	const bool strogg = idStr::Icmp( background->GetName(), "gfx/guis/hud/s_waveform" ) == 0;
	const char *prefix = radio ? "radio_audio" : outgoing ? "voice_self_audio" : "voice_audio";
	const int emitterIndex = gui->State().GetInt( va( "%s_emitter", prefix ) );
	const int channel = gui->State().GetInt( va( "%s_channel", prefix ) );
	const int count = radio ? 40 : 24;
	float peaks[40] = {};
	idSoundWorld *world = soundSystem->GetSoundWorldFromId( SOUNDWORLD_GAME );
	idSoundEmitter *emitter = world != NULL && emitterIndex > 0 ? world->EmitterForIndex( emitterIndex ) : NULL;
	if ( emitter != NULL && channel > SCHANNEL_ANY ) {
		emitter->AmplitudeHistory( channel, peaks, count );
	}
	if ( cvarSystem->GetCVarBool( "ui_retainedReducedMotion" ) ) {
		for ( int i = 0; i < count - 1; ++i ) {
			peaks[i] = peaks[count - 1];
		}
	}
	// Normalized bounds preserve the stock trapezoid, including Strogg's
	// opposite slant. Clip each vector bar to it before virtual-screen projection.
	const float left = radio ? ( strogg ? 7.0f : 9.61f ) / 41.0f : 0.0f;
	const float right = radio ? ( strogg ? 33.3f : 32.67f ) / 41.0f : 1.0f;
	const float top = radio ? 1.56f / 25.0f : 0.0f;
	const float bottom = 1.0f - top;
	const float step = ( right - left ) / count;
	for ( int i = 0; i < count; ++i ) {
		const float x = left + ( i + 0.5f ) * step;
		float y0 = top, y1 = bottom;
		if ( radio && strogg ) {
			y1 = Min( y1, top + ( x * 41.0f - 7.0f ) / 3.9f * ( bottom - top ) );
			y0 = Max( y0, top + ( x * 41.0f - 29.5f ) / 3.8f * ( bottom - top ) );
		} else if ( radio ) {
			y0 = Max( y0, top + ( 13.45f - x * 41.0f ) / 3.84f * ( bottom - top ) );
		}
		const float peak = idMath::ClampFloat( 0.0f, 1.0f, peaks[i] );
		const float halfHeight = Max( 0.012f, 0.5f / rect.h ) + 0.32f * peak * peak;
		y0 = Max( y0, 0.5f - halfHeight );
		y1 = Min( y1, 0.5f + halfHeight );
		if ( y1 > y0 ) {
			dc->DrawFilledRect( rect.x + ( x - step * 0.5f ) * rect.w, rect.y + y0 * rect.h,
				step * rect.w, ( y1 - y0 ) * rect.h, color );
		}
	}
	return true;
}

