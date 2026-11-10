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

#include "tr_local.h"
#include "TrueType.h"

namespace {

// Simple glyph flag bits.
const int TT_FLAG_ON_CURVE		= 0x01;
const int TT_FLAG_X_SHORT		= 0x02;
const int TT_FLAG_Y_SHORT		= 0x04;
const int TT_FLAG_REPEAT		= 0x08;
const int TT_FLAG_X_SAME		= 0x10;
const int TT_FLAG_Y_SAME		= 0x20;

// Composite glyph component flag bits.
const int TT_COMP_ARG_WORDS			= 0x0001;
const int TT_COMP_ARGS_ARE_XY		= 0x0002;
const int TT_COMP_SCALE				= 0x0008;
const int TT_COMP_MORE				= 0x0020;
const int TT_COMP_XY_SCALE			= 0x0040;
const int TT_COMP_TWO_BY_TWO		= 0x0080;

// A quadratic is split into at most this many chords; well beyond what any
// realistic glyph needs at UI sizes, but it bounds the work on absurd input.
const int TT_MAX_CURVE_STEPS = 32;

const int TT_MAX_RASTER_DIMENSION = 4096;

static unsigned int R_MakeTag( const char *tag ) {
	return ( (unsigned int)(byte)tag[0] << 24 ) | ( (unsigned int)(byte)tag[1] << 16 ) |
		   ( (unsigned int)(byte)tag[2] << 8 ) | (unsigned int)(byte)tag[3];
}

/*
================
R_FlattenQuadratic

Appends the curve as chords, excluding the start point which the caller has
already emitted.  The step count comes from the control point's deviation from
the chord, so shallow curves stay cheap and tight ones stay smooth.
================
*/
static void R_FlattenQuadratic( const idVec2 &start, const idVec2 &control, const idVec2 &end, idList<idVec2> &points ) {
	const float dx = start.x - 2.0f * control.x + end.x;
	const float dy = start.y - 2.0f * control.y + end.y;
	const float deviation = idMath::Sqrt( dx * dx + dy * dy );

	int steps = 1;
	if ( deviation > 1e-6f ) {
		steps = (int)idMath::Ceil( idMath::Sqrt( deviation * 4.0f ) );
		steps = Max( 1, Min( TT_MAX_CURVE_STEPS, steps ) );
	}

	for ( int i = 1; i <= steps; i++ ) {
		const float t = (float)i / (float)steps;
		const float inv = 1.0f - t;
		const float a = inv * inv;
		const float b = 2.0f * inv * t;
		const float c = t * t;
		points.Append( idVec2( a * start.x + b * control.x + c * end.x,
							   a * start.y + b * control.y + c * end.y ) );
	}
}

}

/*
================================================================================
	bounds-checked reads
================================================================================
*/

byte idTrueTypeFont::ttReader::U8( int offset ) const {
	if ( !InRange( offset, 1 ) ) {
		Invalidate();
		return 0;
	}
	return data[offset];
}

unsigned short idTrueTypeFont::ttReader::U16( int offset ) const {
	if ( !InRange( offset, 2 ) ) {
		Invalidate();
		return 0;
	}
	return (unsigned short)( ( data[offset] << 8 ) | data[offset + 1] );
}

short idTrueTypeFont::ttReader::S16( int offset ) const {
	return (short)U16( offset );
}

unsigned int idTrueTypeFont::ttReader::U32( int offset ) const {
	if ( !InRange( offset, 4 ) ) {
		Invalidate();
		return 0;
	}
	return ( (unsigned int)data[offset] << 24 ) | ( (unsigned int)data[offset + 1] << 16 ) |
		   ( (unsigned int)data[offset + 2] << 8 ) | (unsigned int)data[offset + 3];
}

/*
================================================================================
	construction
================================================================================
*/

idTrueTypeFont::idTrueTypeFont() {
	fileData = NULL;
	fileLength = 0;
	Free();
}

idTrueTypeFont::~idTrueTypeFont() {
	Free();
}

void idTrueTypeFont::Free() {
	if ( fileData != NULL ) {
		Mem_Free( fileData );
		fileData = NULL;
	}
	fileLength = 0;
	headOffset = -1;
	glyfOffset = -1;
	locaOffset = -1;
	locaLength = 0;
	hmtxOffset = -1;
	hmtxLength = 0;
	cmapSubtable = -1;
	cmapFormat = 0;
	kernOffset = -1;
	kernLength = 0;
	unitsPerEm = 0;
	indexToLocFormat = 0;
	numGlyphs = 0;
	numHMetrics = 0;
	ascender = 0;
	descender = 0;
	lineGap = 0;
}

bool idTrueTypeFont::Load( const byte *data, int length ) {
	Free();
	if ( data == NULL || length < 12 ) {
		return false;
	}

	fileData = (byte *)Mem_Alloc( length );
	memcpy( fileData, data, length );
	fileLength = length;

	if ( !ParseTables() ) {
		Free();
		return false;
	}
	return true;
}

int idTrueTypeFont::TableOffset( const char *tag, int *size ) const {
	ttReader reader( fileData, fileLength );
	const unsigned int wanted = R_MakeTag( tag );
	const int tableCount = reader.U16( 4 );

	for ( int i = 0; i < tableCount; i++ ) {
		const int entry = 12 + i * 16;
		if ( !reader.InRange( entry, 16 ) ) {
			break;
		}
		if ( reader.U32( entry ) != wanted ) {
			continue;
		}
		const int offset = (int)reader.U32( entry + 8 );
		const int tableSize = (int)reader.U32( entry + 12 );
		if ( offset < 0 || tableSize < 0 || !reader.InRange( offset, tableSize ) ) {
			return -1;
		}
		if ( size != NULL ) {
			*size = tableSize;
		}
		return offset;
	}
	return -1;
}

bool idTrueTypeFont::ParseTables() {
	ttReader reader( fileData, fileLength );

	const unsigned int version = reader.U32( 0 );
	// 0x00010000 is a plain TrueType file; 'true' is the legacy Apple tag.
	// OpenType files with CFF outlines have no 'glyf' and are rejected below.
	if ( version != 0x00010000 && version != R_MakeTag( "true" ) && version != R_MakeTag( "ttcf" ) ) {
		if ( version != R_MakeTag( "OTTO" ) ) {
			return false;
		}
	}

	headOffset = TableOffset( "head" );
	const int maxpOffset = TableOffset( "maxp" );
	const int hheaOffset = TableOffset( "hhea" );
	glyfOffset = TableOffset( "glyf" );
	locaOffset = TableOffset( "loca", &locaLength );
	hmtxOffset = TableOffset( "hmtx", &hmtxLength );
	const int cmapOffset = TableOffset( "cmap" );
	kernOffset = TableOffset( "kern", &kernLength );

	if ( headOffset < 0 || maxpOffset < 0 || hheaOffset < 0 || glyfOffset < 0 || locaOffset < 0 || cmapOffset < 0 ) {
		return false;
	}

	unitsPerEm = reader.U16( headOffset + 18 );
	indexToLocFormat = reader.S16( headOffset + 50 );
	numGlyphs = reader.U16( maxpOffset + 4 );
	ascender = reader.S16( hheaOffset + 4 );
	descender = reader.S16( hheaOffset + 6 );
	lineGap = reader.S16( hheaOffset + 8 );
	numHMetrics = reader.U16( hheaOffset + 34 );

	if ( unitsPerEm <= 0 || numGlyphs <= 0 || ( indexToLocFormat != 0 && indexToLocFormat != 1 ) ) {
		return false;
	}

	// Pick the best character map: a full Unicode format 12 table if present,
	// otherwise the usual BMP format 4.
	const int subtableCount = reader.U16( cmapOffset + 2 );
	int bestOffset = -1;
	int bestFormat = 0;
	for ( int i = 0; i < subtableCount; i++ ) {
		const int record = cmapOffset + 4 + i * 8;
		if ( !reader.InRange( record, 8 ) ) {
			break;
		}
		const int platform = reader.U16( record );
		const int encoding = reader.U16( record + 2 );
		const int subOffset = cmapOffset + (int)reader.U32( record + 4 );
		if ( !reader.InRange( subOffset, 4 ) ) {
			continue;
		}
		const int format = reader.U16( subOffset );

		const bool unicode = ( platform == 0 ) || ( platform == 3 && ( encoding == 1 || encoding == 10 ) );
		if ( !unicode ) {
			continue;
		}
		if ( format == 12 && bestFormat != 12 ) {
			bestOffset = subOffset;
			bestFormat = 12;
		} else if ( format == 4 && bestFormat == 0 ) {
			bestOffset = subOffset;
			bestFormat = 4;
		}
	}

	if ( bestOffset < 0 ) {
		return false;
	}
	cmapSubtable = bestOffset;
	cmapFormat = bestFormat;

	return reader.IsValid();
}

float idTrueTypeFont::ScaleForPixelHeight( float pixels ) const {
	if ( unitsPerEm <= 0 ) {
		return 0.0f;
	}
	return pixels / (float)unitsPerEm;
}

/*
================================================================================
	character map
================================================================================
*/

int idTrueTypeFont::CodepointFromFormat4( int tableOffset, int codepoint ) const {
	if ( codepoint > 0xFFFF ) {
		return 0;
	}
	ttReader reader( fileData, fileLength );

	const int segCountX2 = reader.U16( tableOffset + 6 );
	const int segCount = segCountX2 >> 1;
	if ( segCount <= 0 ) {
		return 0;
	}

	const int endCodes = tableOffset + 14;
	const int startCodes = endCodes + segCountX2 + 2;
	const int idDeltas = startCodes + segCountX2;
	const int idRangeOffsets = idDeltas + segCountX2;

	// Binary search for the first segment whose end code covers the character.
	int low = 0;
	int high = segCount - 1;
	int segment = -1;
	while ( low <= high ) {
		const int mid = ( low + high ) >> 1;
		if ( reader.U16( endCodes + mid * 2 ) >= codepoint ) {
			segment = mid;
			high = mid - 1;
		} else {
			low = mid + 1;
		}
	}
	if ( segment < 0 ) {
		return 0;
	}

	const int startCode = reader.U16( startCodes + segment * 2 );
	if ( codepoint < startCode ) {
		return 0;
	}

	const int rangeOffset = reader.U16( idRangeOffsets + segment * 2 );
	const int delta = reader.S16( idDeltas + segment * 2 );
	if ( rangeOffset == 0 ) {
		return ( codepoint + delta ) & 0xFFFF;
	}

	const int glyphAddress = idRangeOffsets + segment * 2 + rangeOffset + ( codepoint - startCode ) * 2;
	const int glyphIndex = reader.U16( glyphAddress );
	if ( glyphIndex == 0 ) {
		return 0;
	}
	return ( glyphIndex + delta ) & 0xFFFF;
}

int idTrueTypeFont::CodepointFromFormat12( int tableOffset, int codepoint ) const {
	ttReader reader( fileData, fileLength );

	const int groupCount = (int)reader.U32( tableOffset + 12 );
	int low = 0;
	int high = groupCount - 1;
	while ( low <= high ) {
		const int mid = ( low + high ) >> 1;
		const int group = tableOffset + 16 + mid * 12;
		const unsigned int startChar = reader.U32( group );
		const unsigned int endChar = reader.U32( group + 4 );
		if ( (unsigned int)codepoint < startChar ) {
			high = mid - 1;
		} else if ( (unsigned int)codepoint > endChar ) {
			low = mid + 1;
		} else {
			return (int)( reader.U32( group + 8 ) + ( codepoint - startChar ) );
		}
	}
	return 0;
}

int idTrueTypeFont::GlyphForCodepoint( int codepoint ) const {
	if ( !IsLoaded() || codepoint < 0 || cmapSubtable < 0 ) {
		return 0;
	}
	int glyphIndex = 0;
	if ( cmapFormat == 12 ) {
		glyphIndex = CodepointFromFormat12( cmapSubtable, codepoint );
	} else {
		glyphIndex = CodepointFromFormat4( cmapSubtable, codepoint );
	}
	if ( glyphIndex < 0 || glyphIndex >= numGlyphs ) {
		return 0;
	}
	return glyphIndex;
}

/*
================================================================================
	metrics
================================================================================
*/

bool idTrueTypeFont::GlyphDataRange( int glyphIndex, int &offset, int &size ) const {
	if ( glyphIndex < 0 || glyphIndex >= numGlyphs ) {
		return false;
	}
	ttReader reader( fileData, fileLength );

	int start = 0;
	int end = 0;
	if ( indexToLocFormat == 0 ) {
		if ( ( glyphIndex + 2 ) * 2 > locaLength ) {
			return false;
		}
		start = reader.U16( locaOffset + glyphIndex * 2 ) * 2;
		end = reader.U16( locaOffset + glyphIndex * 2 + 2 ) * 2;
	} else {
		if ( ( glyphIndex + 2 ) * 4 > locaLength ) {
			return false;
		}
		start = (int)reader.U32( locaOffset + glyphIndex * 4 );
		end = (int)reader.U32( locaOffset + glyphIndex * 4 + 4 );
	}

	if ( !reader.IsValid() || end <= start ) {
		// An empty range is legal and means a blank glyph such as space.
		offset = -1;
		size = 0;
		return reader.IsValid();
	}

	offset = glyfOffset + start;
	size = end - start;
	return reader.InRange( offset, size );
}

bool idTrueTypeFont::GetGlyphMetrics( int glyphIndex, ttGlyphMetrics_t &metrics ) const {
	memset( &metrics, 0, sizeof( metrics ) );
	if ( !IsLoaded() || glyphIndex < 0 || glyphIndex >= numGlyphs ) {
		return false;
	}

	ttReader reader( fileData, fileLength );

	if ( hmtxOffset >= 0 && numHMetrics > 0 ) {
		const int entry = ( glyphIndex < numHMetrics ) ? glyphIndex : numHMetrics - 1;
		metrics.advance = reader.U16( hmtxOffset + entry * 4 );
		if ( glyphIndex < numHMetrics ) {
			metrics.leftSideBearing = reader.S16( hmtxOffset + entry * 4 + 2 );
		} else {
			// Monospaced tail: the side bearings follow the advance array.
			const int tail = hmtxOffset + numHMetrics * 4 + ( glyphIndex - numHMetrics ) * 2;
			metrics.leftSideBearing = reader.S16( tail );
		}
	}

	int offset = -1;
	int size = 0;
	if ( !GlyphDataRange( glyphIndex, offset, size ) ) {
		return false;
	}
	if ( offset >= 0 && size >= 10 ) {
		metrics.xMin = reader.S16( offset + 2 );
		metrics.yMin = reader.S16( offset + 4 );
		metrics.xMax = reader.S16( offset + 6 );
		metrics.yMax = reader.S16( offset + 8 );
	}
	return reader.IsValid();
}

int idTrueTypeFont::KernAdvance( int firstGlyph, int secondGlyph ) const {
	if ( kernOffset < 0 || kernLength < 18 ) {
		return 0;
	}
	ttReader reader( fileData, fileLength );

	// Only the common format 0 horizontal subtable is honoured.
	if ( reader.U16( kernOffset + 2 ) < 1 ) {
		return 0;
	}
	if ( ( reader.U16( kernOffset + 8 ) & 0x0F ) != 1 ) {
		return 0;
	}

	const int pairCount = reader.U16( kernOffset + 10 );
	const unsigned int wanted = ( (unsigned int)firstGlyph << 16 ) | (unsigned int)secondGlyph;

	int low = 0;
	int high = pairCount - 1;
	while ( low <= high ) {
		const int mid = ( low + high ) >> 1;
		const int entry = kernOffset + 18 + mid * 6;
		const unsigned int key = reader.U32( entry );
		if ( wanted < key ) {
			high = mid - 1;
		} else if ( wanted > key ) {
			low = mid + 1;
		} else {
			return reader.S16( entry + 4 );
		}
	}
	return 0;
}

/*
================================================================================
	outline extraction
================================================================================
*/

bool idTrueTypeFont::AppendSimpleGlyph( int glyphOffset, int glyphSize, float scale, float offsetX, float offsetY,
										float xx, float xy, float yx, float yy, ttOutline_t &outline ) const {
	ttReader reader( fileData, fileLength );

	const int contourCount = reader.S16( glyphOffset );
	if ( contourCount <= 0 ) {
		return reader.IsValid();
	}

	int cursor = glyphOffset + 10;
	const int endPtsOffset = cursor;
	const int pointCount = reader.U16( endPtsOffset + ( contourCount - 1 ) * 2 ) + 1;
	if ( pointCount <= 0 || pointCount > 10000 ) {
		return false;
	}
	cursor += contourCount * 2;

	const int instructionLength = reader.U16( cursor );
	cursor += 2 + instructionLength;
	if ( !reader.InRange( cursor, 0 ) ) {
		return false;
	}

	idList<byte> flags;
	flags.SetNum( pointCount );
	for ( int i = 0; i < pointCount; ) {
		const byte flag = reader.U8( cursor++ );
		flags[i++] = flag;
		if ( flag & TT_FLAG_REPEAT ) {
			int repeat = reader.U8( cursor++ );
			while ( repeat-- > 0 && i < pointCount ) {
				flags[i++] = flag;
			}
		}
		if ( !reader.IsValid() ) {
			return false;
		}
	}

	idList<int> xs;
	idList<int> ys;
	xs.SetNum( pointCount );
	ys.SetNum( pointCount );

	int value = 0;
	for ( int i = 0; i < pointCount; i++ ) {
		const byte flag = flags[i];
		if ( flag & TT_FLAG_X_SHORT ) {
			const int delta = reader.U8( cursor++ );
			value += ( flag & TT_FLAG_X_SAME ) ? delta : -delta;
		} else if ( !( flag & TT_FLAG_X_SAME ) ) {
			value += reader.S16( cursor );
			cursor += 2;
		}
		xs[i] = value;
	}

	value = 0;
	for ( int i = 0; i < pointCount; i++ ) {
		const byte flag = flags[i];
		if ( flag & TT_FLAG_Y_SHORT ) {
			const int delta = reader.U8( cursor++ );
			value += ( flag & TT_FLAG_Y_SAME ) ? delta : -delta;
		} else if ( !( flag & TT_FLAG_Y_SAME ) ) {
			value += reader.S16( cursor );
			cursor += 2;
		}
		ys[i] = value;
	}

	if ( !reader.IsValid() ) {
		return false;
	}

	// Transform a design-unit point into pixel space.  Y is negated because
	// TrueType has +y up and the glyph bitmap has +y down.
	struct localTransform_t {
		float scale, offsetX, offsetY, xx, xy, yx, yy;
		idVec2 Apply( float x, float y ) const {
			const float tx = xx * x + yx * y;
			const float ty = xy * x + yy * y;
			return idVec2( offsetX + tx * scale, offsetY - ty * scale );
		}
	};
	localTransform_t transform = { scale, offsetX, offsetY, xx, xy, yx, yy };

	int first = 0;
	for ( int contour = 0; contour < contourCount; contour++ ) {
		const int last = reader.U16( endPtsOffset + contour * 2 );
		if ( last < first || last >= pointCount ) {
			return false;
		}
		const int count = last - first + 1;
		if ( count < 2 ) {
			first = last + 1;
			continue;
		}

		outline.contourStarts.Append( outline.points.Num() );

		// Find a starting on-curve point; if the contour is made entirely of
		// off-curve points, start from the implied midpoint between two.
		int startIndex = -1;
		for ( int i = 0; i < count; i++ ) {
			if ( flags[first + i] & TT_FLAG_ON_CURVE ) {
				startIndex = i;
				break;
			}
		}

		idVec2 startPoint;
		if ( startIndex < 0 ) {
			const idVec2 a = transform.Apply( (float)xs[first], (float)ys[first] );
			const idVec2 b = transform.Apply( (float)xs[first + count - 1], (float)ys[first + count - 1] );
			startPoint = ( a + b ) * 0.5f;
			startIndex = 0;
		} else {
			startPoint = transform.Apply( (float)xs[first + startIndex], (float)ys[first + startIndex] );
			startIndex += 1;
		}

		idVec2 current = startPoint;
		outline.points.Append( current );

		bool havePendingControl = false;
		idVec2 pendingControl( 0.0f, 0.0f );

		for ( int step = 0; step <= count; step++ ) {
			const int index = first + ( ( startIndex + step ) % count );
			const bool isLast = ( step == count );
			const idVec2 point = isLast ? startPoint : transform.Apply( (float)xs[index], (float)ys[index] );
			const bool onCurve = isLast ? true : ( ( flags[index] & TT_FLAG_ON_CURVE ) != 0 );

			if ( onCurve ) {
				if ( havePendingControl ) {
					R_FlattenQuadratic( current, pendingControl, point, outline.points );
					havePendingControl = false;
				} else {
					outline.points.Append( point );
				}
				current = point;
				if ( isLast ) {
					break;
				}
				continue;
			}

			if ( havePendingControl ) {
				// Two consecutive control points imply an on-curve midpoint.
				const idVec2 implied = ( pendingControl + point ) * 0.5f;
				R_FlattenQuadratic( current, pendingControl, implied, outline.points );
				current = implied;
			}
			pendingControl = point;
			havePendingControl = true;
		}

		if ( havePendingControl ) {
			R_FlattenQuadratic( current, pendingControl, startPoint, outline.points );
		}

		first = last + 1;
	}

	return reader.IsValid();
}

bool idTrueTypeFont::AppendGlyphOutline( int glyphIndex, float scale, float offsetX, float offsetY,
										 float xx, float xy, float yx, float yy, int depth, ttOutline_t &outline ) const {
	if ( depth > TT_MAX_COMPOSITE_DEPTH ) {
		return false;
	}

	int glyphOffset = -1;
	int glyphSize = 0;
	if ( !GlyphDataRange( glyphIndex, glyphOffset, glyphSize ) ) {
		return false;
	}
	if ( glyphOffset < 0 || glyphSize < 10 ) {
		return true;	// blank glyph
	}

	ttReader reader( fileData, fileLength );
	const int contourCount = reader.S16( glyphOffset );
	if ( contourCount >= 0 ) {
		return AppendSimpleGlyph( glyphOffset, glyphSize, scale, offsetX, offsetY, xx, xy, yx, yy, outline );
	}

	// Composite glyph: walk the component records.
	int cursor = glyphOffset + 10;
	for ( int guard = 0; guard < 64; guard++ ) {
		const int flags = reader.U16( cursor );
		const int componentIndex = reader.U16( cursor + 2 );
		cursor += 4;

		float dx = 0.0f;
		float dy = 0.0f;
		if ( flags & TT_COMP_ARG_WORDS ) {
			if ( flags & TT_COMP_ARGS_ARE_XY ) {
				dx = (float)reader.S16( cursor );
				dy = (float)reader.S16( cursor + 2 );
			}
			cursor += 4;
		} else {
			if ( flags & TT_COMP_ARGS_ARE_XY ) {
				dx = (float)(signed char)reader.U8( cursor );
				dy = (float)(signed char)reader.U8( cursor + 1 );
			}
			cursor += 2;
		}

		float cxx = 1.0f, cxy = 0.0f, cyx = 0.0f, cyy = 1.0f;
		if ( flags & TT_COMP_SCALE ) {
			cxx = cyy = reader.S16( cursor ) / 16384.0f;
			cursor += 2;
		} else if ( flags & TT_COMP_XY_SCALE ) {
			cxx = reader.S16( cursor ) / 16384.0f;
			cyy = reader.S16( cursor + 2 ) / 16384.0f;
			cursor += 4;
		} else if ( flags & TT_COMP_TWO_BY_TWO ) {
			cxx = reader.S16( cursor ) / 16384.0f;
			cxy = reader.S16( cursor + 2 ) / 16384.0f;
			cyx = reader.S16( cursor + 4 ) / 16384.0f;
			cyy = reader.S16( cursor + 6 ) / 16384.0f;
			cursor += 8;
		}

		if ( !reader.IsValid() ) {
			return false;
		}

		// Compose the component transform with the one handed down to us.
		const float nxx = xx * cxx + yx * cxy;
		const float nxy = xy * cxx + yy * cxy;
		const float nyx = xx * cyx + yx * cyy;
		const float nyy = xy * cyx + yy * cyy;
		const float shiftX = ( xx * dx + yx * dy ) * scale;
		const float shiftY = ( xy * dx + yy * dy ) * scale;

		if ( componentIndex != glyphIndex ) {
			AppendGlyphOutline( componentIndex, scale, offsetX + shiftX, offsetY - shiftY,
								nxx, nxy, nyx, nyy, depth + 1, outline );
		}

		if ( !( flags & TT_COMP_MORE ) ) {
			break;
		}
	}

	return reader.IsValid();
}

/*
================================================================================
	rasteriser

	Every edge deposits its exact signed area contribution per pixel into an
	accumulation buffer.  Running that buffer along each scanline turns the
	deltas into coverage, which is analytically correct for polygons - no
	supersampling, no ordered edge lists.
================================================================================
*/

namespace {

static void R_AccumulateEdge( float *accumulate, int width, int height, idVec2 from, idVec2 to ) {
	if ( from.y == to.y ) {
		return;
	}

	float direction = 1.0f;
	if ( from.y > to.y ) {
		idVec2 swap = from;
		from = to;
		to = swap;
		direction = -1.0f;
	}

	const float dxdy = ( to.x - from.x ) / ( to.y - from.y );
	int firstRow = (int)idMath::Floor( from.y );
	int lastRow = (int)idMath::Ceil( to.y );
	firstRow = Max( 0, firstRow );
	lastRow = Min( height, lastRow );

	const int stride = width + 2;

	for ( int row = firstRow; row < lastRow; row++ ) {
		const float rowTop = Max( from.y, (float)row );
		const float rowBottom = Min( to.y, (float)( row + 1 ) );
		const float span = rowBottom - rowTop;
		if ( span <= 0.0f ) {
			continue;
		}

		float xStart = from.x + dxdy * ( rowTop - from.y );
		float xEnd = from.x + dxdy * ( rowBottom - from.y );
		if ( xStart > xEnd ) {
			const float swap = xStart;
			xStart = xEnd;
			xEnd = swap;
		}

		const float signedSpan = direction * span;
		float *line = accumulate + row * stride;

		int firstColumn = (int)idMath::Floor( xStart );
		int lastColumn = (int)idMath::Floor( xEnd );

		if ( firstColumn == lastColumn ) {
			const float centre = 0.5f * ( xStart + xEnd );
			int column = firstColumn;
			if ( column < 0 ) {
				line[0] += signedSpan;
				continue;
			}
			if ( column >= width ) {
				continue;
			}
			const float right = 1.0f - ( centre - (float)column );
			line[column] += signedSpan * right;
			line[column + 1] += signedSpan * ( 1.0f - right );
			continue;
		}

		// The sub-span crosses one or more column boundaries; split it by the
		// fraction of vertical travel spent in each column.
		const float inverseWidth = 1.0f / ( xEnd - xStart );
		float previous = 0.0f;
		for ( int column = firstColumn; column <= lastColumn; column++ ) {
			float boundary = Min( (float)( column + 1 ), xEnd );
			float t = ( boundary - xStart ) * inverseWidth;
			t = Max( 0.0f, Min( 1.0f, t ) );
			const float slice = t - previous;
			previous = t;
			if ( slice <= 0.0f ) {
				continue;
			}
			const float segStart = Max( xStart, (float)column );
			const float segEnd = Min( xEnd, (float)( column + 1 ) );
			const float centre = 0.5f * ( segStart + segEnd );
			const float contribution = signedSpan * slice;
			if ( column < 0 ) {
				line[0] += contribution;
				continue;
			}
			if ( column >= width ) {
				continue;
			}
			const float right = 1.0f - ( centre - (float)column );
			line[column] += contribution * right;
			line[column + 1] += contribution * ( 1.0f - right );
		}
	}
}

}

bool idTrueTypeFont::RasterizeGlyph( int glyphIndex, float scale, ttGlyphBitmap_t &bitmap ) const {
	memset( &bitmap, 0, sizeof( bitmap ) );
	if ( !IsLoaded() || scale <= 0.0f ) {
		return false;
	}

	ttGlyphMetrics_t metrics;
	if ( !GetGlyphMetrics( glyphIndex, metrics ) ) {
		return false;
	}
	if ( metrics.xMax <= metrics.xMin || metrics.yMax <= metrics.yMin ) {
		return true;	// blank but valid, e.g. space
	}

	// One texel of slack on each side keeps antialiased edges from clipping.
	const int left = (int)idMath::Floor( metrics.xMin * scale ) - 1;
	const int right = (int)idMath::Ceil( metrics.xMax * scale ) + 1;
	const int top = (int)idMath::Floor( -metrics.yMax * scale ) - 1;
	const int bottom = (int)idMath::Ceil( -metrics.yMin * scale ) + 1;

	const int width = right - left;
	const int height = bottom - top;
	if ( width <= 0 || height <= 0 || width > TT_MAX_RASTER_DIMENSION || height > TT_MAX_RASTER_DIMENSION ) {
		return false;
	}

	ttOutline_t outline;
	if ( !AppendGlyphOutline( glyphIndex, scale, -(float)left, -(float)top, 1.0f, 0.0f, 0.0f, 1.0f, 0, outline ) ) {
		return false;
	}
	if ( outline.contourStarts.Num() == 0 ) {
		return true;
	}

	const int stride = width + 2;
	float *accumulate = (float *)Mem_ClearedAlloc( stride * height * sizeof( float ) );

	for ( int contour = 0; contour < outline.contourStarts.Num(); contour++ ) {
		const int start = outline.contourStarts[contour];
		const int end = ( contour + 1 < outline.contourStarts.Num() ) ? outline.contourStarts[contour + 1] : outline.points.Num();
		const int count = end - start;
		if ( count < 3 ) {
			continue;
		}
		for ( int i = 0; i < count; i++ ) {
			const idVec2 &from = outline.points[start + i];
			const idVec2 &to = outline.points[start + ( ( i + 1 ) % count )];
			R_AccumulateEdge( accumulate, width, height, from, to );
		}
	}

	bitmap.pixels = (byte *)Mem_Alloc( width * height );
	bitmap.width = width;
	bitmap.height = height;
	bitmap.left = left;
	bitmap.top = top;

	for ( int row = 0; row < height; row++ ) {
		const float *line = accumulate + row * stride;
		byte *destination = bitmap.pixels + row * width;
		float running = 0.0f;
		for ( int column = 0; column < width; column++ ) {
			running += line[column];
			float coverage = idMath::Fabs( running );
			if ( coverage > 1.0f ) {
				coverage = 1.0f;
			}
			destination[column] = (byte)( coverage * 255.0f + 0.5f );
		}
	}

	Mem_Free( accumulate );
	return true;
}

void idTrueTypeFont::FreeGlyphBitmap( ttGlyphBitmap_t &bitmap ) {
	if ( bitmap.pixels != NULL ) {
		Mem_Free( bitmap.pixels );
	}
	memset( &bitmap, 0, sizeof( bitmap ) );
}
