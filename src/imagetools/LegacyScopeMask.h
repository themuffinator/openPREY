// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#ifndef OPENQ4_LEGACY_SCOPE_MASK_H
#define OPENQ4_LEGACY_SCOPE_MASK_H

// This is a scalar distortion field, not colour art. Retail's DXT replacement
// quantizes its almost-black aperture into 4x4 blocks which become visible when
// the scope shader applies its tint. Keep the authored TGA's precision when it
// is available; explicit DDS requests and custom dds/ replacements remain valid.
inline bool R_IsLegacyScopeDistortionMask( const char *name ) {
	if ( name == NULL || idStr::Icmpn( name, "gfx", 3 ) ) {
		return false;
	}
	idStr path = name;
	path.BackSlashesToSlashes();
	idStr extension;
	path.ExtractFileExtension( extension );
	if ( extension.Length() && extension.Icmp( "tga" ) ) {
		return false;
	}
	path.StripFileExtension();
	return !path.Icmp( "gfx/guis/hud/reticles/mgun_scope_distort" )
		|| !path.Icmp( "gfx/guis/hud/reticles/mgun_scope_distort_left" )
		|| !path.Icmp( "gfx/guis/hud/reticles/mgun_scope_distort_right" )
		|| !path.Icmp( "gfx/guis/hud/reticles/mgun_scope_distort_top" )
		|| !path.Icmp( "gfx/guis/hud/reticles/mgun_scope_distort_bottom" );
}

#endif
