/*
===========================================================================

openQ4 GPL Source Code
Copyright (C) 2025 the openQ4 contributors.

This file is part of the openQ4 Source Code. See docs/legal for details.

===========================================================================
*/

#ifndef __SYS_CONSOLE_THEME_H__
#define __SYS_CONSOLE_THEME_H__

/*
===============================================================================

	Shared system-console presentation contract.

	The Win32 system console (sys/win32/win_syscon.cpp) and the SDL3 system
	console used by Linux and macOS (sys/posix/posix_syscon.cpp) are entirely
	separate implementations drawing entirely different widget stacks. They are
	still the same product surface, so every colour and every measurement they
	disagree on is a visible cross-platform inconsistency.

	Both implementations therefore take their palette and their metrics from
	this header instead of hard-coding literals. Parity becomes structural: a
	metric can only drift on one platform if somebody edits it here, which
	changes it on all three.

	Colours are byte triplets rather than packed values so that Win32's RGB()
	and SDL's SDL_SetRenderDrawColor() can both consume them directly without a
	lossy conversion step in between.

	Metrics are expressed in 96-DPI design units. Win32 scales them by the
	window DPI; the SDL console draws into a logical presentation sized in
	window coordinates, which SDL already keeps DPI-independent.

===============================================================================
*/

// Window chrome behind the panels.
#define SYSCON_WINDOW_R				0x0c
#define SYSCON_WINDOW_G				0x0f
#define SYSCON_WINDOW_B				0x07

// Log and status surface. This is the historical Quake 4 console green-black
// and is deliberately unchanged; it carries the product identity.
#define SYSCON_PANEL_R				0x1b
#define SYSCON_PANEL_G				0x20
#define SYSCON_PANEL_B				0x0a

// Command input surface, sunk one step below the log so the caret line reads
// as an editable field rather than as more log.
#define SYSCON_INPUT_R				0x11
#define SYSCON_INPUT_G				0x15
#define SYSCON_INPUT_B				0x0a

// Button face, hover, and pressed states.
#define SYSCON_BUTTON_R				0x24
#define SYSCON_BUTTON_G				0x2b
#define SYSCON_BUTTON_B				0x12

#define SYSCON_BUTTON_HOT_R			0x32
#define SYSCON_BUTTON_HOT_G			0x3b
#define SYSCON_BUTTON_HOT_B			0x18

#define SYSCON_BUTTON_DOWN_R		0x15
#define SYSCON_BUTTON_DOWN_G		0x1a
#define SYSCON_BUTTON_DOWN_B		0x0a

// Resting and emphasised borders.
#define SYSCON_BORDER_R				0x3a
#define SYSCON_BORDER_G				0x44
#define SYSCON_BORDER_B				0x23

#define SYSCON_BORDER_LIT_R			0x5b
#define SYSCON_BORDER_LIT_G			0x66
#define SYSCON_BORDER_LIT_B			0x36

// Primary text and focus accent: the historical Quake 4 amber.
#define SYSCON_TEXT_R				0xf0
#define SYSCON_TEXT_G				0x9e
#define SYSCON_TEXT_B				0x0d

// Secondary text: prompts, placeholder status, scroll position readout.
#define SYSCON_TEXT_DIM_R			0x9a
#define SYSCON_TEXT_DIM_G			0x83
#define SYSCON_TEXT_DIM_B			0x30

// Fatal-error status strip.
#define SYSCON_ALERT_R				0xff
#define SYSCON_ALERT_G				0x53
#define SYSCON_ALERT_B				0x24

#define SYSCON_ALERT_PANEL_R		0x2b
#define SYSCON_ALERT_PANEL_G		0x0f
#define SYSCON_ALERT_PANEL_B		0x06

// Scrollbar track and thumb.
#define SYSCON_SCROLL_TRACK_R		0x14
#define SYSCON_SCROLL_TRACK_G		0x18
#define SYSCON_SCROLL_TRACK_B		0x09

#define SYSCON_SCROLL_THUMB_R		0x4e
#define SYSCON_SCROLL_THUMB_G		0x5a
#define SYSCON_SCROLL_THUMB_B		0x2c

// Expands a palette name to the byte triplet both platforms consume, e.g.
// SDL_SetRenderDrawColor( renderer, SYSCON_RGB( PANEL ), 0xff ).
//
// Note for Win32 callers: this must not be nested inside a function-like macro
// such as RGB(). MSVC's traditional preprocessor does not expand a macro
// argument into several arguments of an outer function-like macro, so
// RGB( SYSCON_RGB( PANEL ) ) fails to compile there. Pass it to a real function
// instead; ordinary function arguments have no such restriction.
#define SYSCON_RGB( name )			SYSCON_##name##_R, SYSCON_##name##_G, SYSCON_##name##_B

// Default and minimum client size, in design units.
#define SYSCON_METRIC_WINDOW_W		760
#define SYSCON_METRIC_WINDOW_H		520
#define SYSCON_METRIC_MIN_W			420
#define SYSCON_METRIC_MIN_H			300

// Outer margin, and the gap between stacked elements.
#define SYSCON_METRIC_MARGIN		10
#define SYSCON_METRIC_GUTTER		8

// Fixed-height rows. The log pane takes whatever vertical space is left.
#define SYSCON_METRIC_STATUS_H		28
#define SYSCON_METRIC_INPUT_H		26
#define SYSCON_METRIC_BUTTON_H		26
#define SYSCON_METRIC_BUTTON_W		84

// Padding between a panel border and the text inside it.
#define SYSCON_METRIC_TEXT_PAD		6

// Log line pitch. The SDL console draws an 8x8 bitmap glyph on this pitch;
// Win32 picks a point size whose line height lands on the same value, so both
// platforms show the same number of lines in the same space.
#define SYSCON_METRIC_LINE_H		11
#define SYSCON_METRIC_GLYPH_W		8
#define SYSCON_METRIC_GLYPH_H		8

// Log scrollbar gutter.
#define SYSCON_METRIC_SCROLLBAR_W	12

// Monospace point size for the log and the input line, and UI point size for
// the status strip and buttons. Win32 uses these directly; the SDL console
// draws SDL's fixed 8x8 debug font and matches through SYSCON_METRIC_LINE_H.
#define SYSCON_METRIC_MONO_PT		8
#define SYSCON_METRIC_UI_PT			9

// Status strip text when nothing has gone wrong.
#define SYSCON_STATUS_READY_TEXT	"System console ready"

// Button labels, shared so the three consoles cannot drift apart.
#define SYSCON_LABEL_COPY			"Copy"
#define SYSCON_LABEL_CLEAR			"Clear"
#define SYSCON_LABEL_QUIT			"Quit"

#endif /* !__SYS_CONSOLE_THEME_H__ */
