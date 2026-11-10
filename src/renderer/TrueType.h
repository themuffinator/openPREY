/*
===========================================================================

openQ4 Source Code
Copyright (C) 2026 DarkMatter Productions

This file is part of the openQ4 Source Code.

openQ4 Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

openQ4 Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with openQ4 Source Code.  If not, see <http://www.gnu.org/licenses/>.

===========================================================================
*/

#ifndef __TRUETYPE_H__
#define __TRUETYPE_H__

/*
===============================================================================

	Self-contained TrueType outline reader and rasteriser.

	openQ4 ships its own font files, so this only has to understand the subset
	of the format those files use: 'glyf' outlines (simple and composite),
	format 4 and 12 character maps, horizontal metrics and legacy 'kern'
	pairs.  Deliberately no third-party dependency - the project keeps its
	dependency surface small, and a font file is untrusted input that is
	easier to bounds-check here than to audit elsewhere.

	The rasteriser accumulates exact per-pixel signed area for every edge and
	then integrates along each scanline, so coverage is analytically correct
	without supersampling.

===============================================================================
*/

const int TT_MAX_COMPOSITE_DEPTH = 5;

// One glyph's horizontal metrics and bounding box, in font design units.
typedef struct ttGlyphMetrics_s {
	int					advance;
	int					leftSideBearing;
	int					xMin;
	int					yMin;
	int					xMax;
	int					yMax;
} ttGlyphMetrics_t;

// An 8-bit coverage bitmap plus where it sits relative to the pen position.
// 'left' and 'top' are in pixels, with +y pointing down the screen.
typedef struct ttGlyphBitmap_s {
	byte *				pixels;
	int					width;
	int					height;
	int					left;
	int					top;
} ttGlyphBitmap_t;

class idTrueTypeFont {
public:
						idTrueTypeFont();
						~idTrueTypeFont();

	// Takes a copy of the file data; safe to free the caller's buffer after.
	bool				Load( const byte *data, int length );
	void				Free();
	bool				IsLoaded() const { return fileData != NULL; }

	int					UnitsPerEm() const { return unitsPerEm; }
	int					Ascender() const { return ascender; }
	int					Descender() const { return descender; }
	int					LineGap() const { return lineGap; }
	int					NumGlyphs() const { return numGlyphs; }

	// Returns 0 (the .notdef glyph) when the codepoint is not covered.
	int					GlyphForCodepoint( int codepoint ) const;
	bool				HasCodepoint( int codepoint ) const { return GlyphForCodepoint( codepoint ) != 0; }

	bool				GetGlyphMetrics( int glyphIndex, ttGlyphMetrics_t &metrics ) const;

	// Rasterises at 'scale' font-units-to-pixels.  The caller owns
	// bitmap.pixels and must release it with FreeGlyphBitmap().
	bool				RasterizeGlyph( int glyphIndex, float scale, ttGlyphBitmap_t &bitmap ) const;
	static void			FreeGlyphBitmap( ttGlyphBitmap_t &bitmap );

	// Scale that maps this font's em square onto the given pixel height.
	float				ScaleForPixelHeight( float pixels ) const;

	int					KernAdvance( int firstGlyph, int secondGlyph ) const;

private:
	// A bounds-checked view over the file; every read is validated, so a
	// truncated or hostile font yields zeroes rather than reading past the end.
	class ttReader {
	public:
						ttReader( const byte *base, int size ) : data( base ), length( size ), valid( true ) {}
		bool			InRange( int offset, int count ) const { return offset >= 0 && count >= 0 && offset + count <= length; }
		byte			U8( int offset ) const;
		unsigned short	U16( int offset ) const;
		short			S16( int offset ) const;
		unsigned int	U32( int offset ) const;
		bool			IsValid() const { return valid; }
		void			Invalidate() const { valid = false; }

	private:
		const byte *	data;
		int				length;
		mutable bool	valid;
	};

	struct ttOutline_t {
		idList<idVec2>	points;			// flattened contour points, pixel space
		idList<int>		contourStarts;	// index of each contour's first point
	};

	bool				ParseTables();
	int					TableOffset( const char *tag, int *size = NULL ) const;
	bool				GlyphDataRange( int glyphIndex, int &offset, int &size ) const;
	bool				AppendGlyphOutline( int glyphIndex, float scale, float offsetX, float offsetY,
											float xx, float xy, float yx, float yy, int depth, ttOutline_t &outline ) const;
	bool				AppendSimpleGlyph( int glyphOffset, int glyphSize, float scale, float offsetX, float offsetY,
											float xx, float xy, float yx, float yy, ttOutline_t &outline ) const;
	int					CodepointFromFormat4( int tableOffset, int codepoint ) const;
	int					CodepointFromFormat12( int tableOffset, int codepoint ) const;

	byte *				fileData;
	int					fileLength;

	int					headOffset;
	int					glyfOffset;
	int					locaOffset;
	int					locaLength;
	int					hmtxOffset;
	int					hmtxLength;
	int					cmapSubtable;
	int					cmapFormat;
	int					kernOffset;
	int					kernLength;

	int					unitsPerEm;
	int					indexToLocFormat;
	int					numGlyphs;
	int					numHMetrics;
	int					ascender;
	int					descender;
	int					lineGap;
};

#endif /* !__TRUETYPE_H__ */
