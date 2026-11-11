// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#ifndef OPENQ4_LEGACY_GUI_LAYOUT_H
#define OPENQ4_LEGACY_GUI_LAYOUT_H

// Retail msg.gui supplies a 4:3 dimming rectangle. Expand only that backing;
// the dialog furniture stays centered, and custom rectangles keep their size.
// Both script windows and their simple-window optimization use this rule.
inline void OpenQ4_ExpandLegacyMessageBackdrop( const char *source, const char *name,
		float xExpand, float yExpand, idRectangle &rect ) {
	if ( source == NULL || name == NULL || idStr::Icmp( source, "guis/msg.gui" ) ||
			idStr::Icmp( name, "msg_black" ) || rect.x != 0.0f || rect.y != 0.0f ||
			rect.w != 640.0f || rect.h != 480.0f ) {
		return;
	}
	rect.x -= xExpand;
	rect.y -= yExpand;
	rect.w += 2.0f * xExpand;
	rect.h += 2.0f * yExpand;
}

// A colour fill over exactly the 4:3 canvas is a screen fill: the scrims under
// dialogs, the fades to and from black, Prey's msg.gui dimming its whole
// desktop. Under aspect expansion it covers the expanded canvas, so the extra
// screen dims and fades with the rest. Any other rectangle keeps its size, and
// only the fill widens: the window and its children stay where they are.
inline idRectangle OpenQ4_LegacyScreenFillRect( const idRectangle &rect, float xExpand, float yExpand ) {
	if ( ( xExpand <= 0.0f && yExpand <= 0.0f ) || rect.x != 0.0f || rect.y != 0.0f ||
			rect.w != 640.0f || rect.h != 480.0f ) {
		return rect;
	}
	return idRectangle( -xExpand, -yExpand, rect.w + 2.0f * xExpand, rect.h + 2.0f * yExpand );
}

#endif
