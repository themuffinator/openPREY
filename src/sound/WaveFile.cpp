/*
===========================================================================

Doom 3 BFG Edition GPL Source Code
Copyright (C) 1993-2012 id Software LLC, a ZeniMax Media company.

This file is part of the Doom 3 BFG Edition GPL Source Code ("Doom 3 BFG Edition Source Code").

Doom 3 BFG Edition Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Doom 3 BFG Edition Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Doom 3 BFG Edition Source Code.  If not, see <http://www.gnu.org/licenses/>.

In addition, the Doom 3 BFG Edition Source Code is also subject to certain additional terms. You should have received a copy of these additional terms immediately following the terms and conditions of the GNU General Public License which accompanied the Doom 3 BFG Edition Source Code.  If not, please request a copy in writing from id Software at the address below.

If you have questions concerning this license or the applicable additional terms, you may contact in writing id Software LLC, c/o ZeniMax Media Inc., Suite 120, Rockville, Maryland 20850 USA.

===========================================================================
*/

/*
================================================================================================
Contains the WaveFile implementation.
================================================================================================
*/

#include "WaveFile.h"

/*
========================
idWaveFile::Open

Returns true if the Open was successful and the file matches the expected format. If this
returns false, there is no need to call Close.
========================
*/
bool idWaveFile::Open( const char* filename )
{
	Close();

	if( filename == NULL || filename[0] == 0 )
	{
		return false;
	}

	if( file == NULL )
	{
		file = fileSystem->OpenFileRead( filename );
		if( file == NULL )
		{
			return false;
		}
	}

	struct header_t
	{
		uint32 id;
		uint32 size;
		uint32 format;
	} header;

	const int fileLengthInt = file->Length();
	if( fileLengthInt < (int)sizeof( header_t ) )
	{
		Close();
		return false;
	}

	if( file->Read( &header, sizeof( header ) ) != sizeof( header ) )
	{
		Close();
		return false;
	}
	idSwap::Big( header.id );
	idSwap::Little( header.size );
	idSwap::Big( header.format );

	if( header.id != 'RIFF' || header.format != 'WAVE' || header.size < 4 )
	{
		Close();
		idLib::Warning( "Header is not RIFF WAVE in %s", filename );
		return false;
	}

	const uint32 fileLength = (uint32)fileLengthInt;
	if( header.size > fileLength - 8 )
	{
		Close();
		idLib::Warning( "RIFF chunk size exceeds file length in %s", filename );
		return false;
	}

	uint32 riffSize = header.size + 8;
	uint32 offset = sizeof( header );

	// Scan the file collecting chunks
	while( offset < riffSize )
	{
		struct chuckHeader_t
		{
			uint32 id;
			uint32 size;
		} chunkHeader;
		if( file->Read( &chunkHeader, sizeof( chunkHeader ) ) != sizeof( chunkHeader ) )
		{
			// It seems like some tools have extra data after the last chunk for no apparent reason
			// so don't treat this as an error
			return true;
		}
		idSwap::Big( chunkHeader.id );
		idSwap::Little( chunkHeader.size );
		offset += sizeof( chunkHeader );

		if( chunks.Num() >= chunks.Max() )
		{
			Close();
			idLib::Warning( "More than %d chunks in %s", chunks.Max(), filename );
			return false;
		}

		const uint64 chunkEnd = (uint64)offset + chunkHeader.size;
		const uint64 paddedChunkEnd = chunkEnd + ( chunkHeader.size & 1 );
		if( chunkEnd > riffSize || paddedChunkEnd > riffSize || paddedChunkEnd > fileLength )
		{
			Close();
			idLib::Warning( "Chunk extends beyond RIFF data in %s", filename );
			return false;
		}

		chunk_t* chunk = chunks.Alloc();
		chunk->id = chunkHeader.id;
		chunk->size = chunkHeader.size;
		chunk->offset = offset;
		offset = (uint32)paddedChunkEnd;

		if( file->Seek( offset, FS_SEEK_SET ) < 0 )
		{
			Close();
			idLib::Warning( "Could not seek past chunk in %s", filename );
			return false;
		}
	}

	return true;
}

/*
========================
idWaveFile::SeekToChunk

Seeks to the specified chunk and returns the size of the chunk or 0 if the chunk wasn't found.
========================
*/
uint32 idWaveFile::SeekToChunk( uint32 id )
{
	if( file == NULL )
	{
		return 0;
	}
	for( int i = 0; i < chunks.Num(); i++ )
	{
		if( chunks[i].id == id )
		{
			if( file->Seek( chunks[i].offset, FS_SEEK_SET ) < 0 )
			{
				return 0;
			}
			return chunks[i].size;
		}
	}
	return 0;
}

/*
========================
idWaveFile::GetChunkOffset

Seeks to the specified chunk and returns the size of the chunk or 0 if the chunk wasn't found.
========================
*/
uint32 idWaveFile::GetChunkOffset( uint32 id )
{
	if( file == NULL )
	{
		return 0;
	}
	for( int i = 0; i < chunks.Num(); i++ )
	{
		if( chunks[i].id == id )
		{
			return chunks[i].offset;
		}
	}
	return 0;
}

// Used in XMA2WAVEFORMAT for per-stream data
typedef struct XMA2STREAMFORMAT
{
	byte Channels;			// Number of channels in the stream (1 or 2)
	byte RESERVED;			// Reserved for future use
	uint16 ChannelMask;		// Spatial positions of the channels in the stream
} XMA2STREAMFORMAT;

// Legacy XMA2 format structure (big-endian byte ordering)
typedef struct XMA2WAVEFORMAT
{
	byte Version;			// XMA encoder version that generated the file.
	// Always 3 or higher for XMA2 files.
	byte NumStreams;		// Number of interleaved audio streams
	byte RESERVED;			// Reserved for future use
	byte LoopCount;			// Number of loop repetitions; 255 = infinite
	uint32 LoopBegin;		// Loop begin point, in samples
	uint32 LoopEnd;			// Loop end point, in samples
	uint32 SampleRate;		// The file's decoded sample rate
	uint32 EncodeOptions;		// Options for the XMA encoder/decoder
	uint32 PsuedoBytesPerSec;	// Used internally by the XMA encoder
	uint32 BlockSizeInBytes;	// Size in bytes of this file's XMA blocks (except
	// possibly the last one).  Always a multiple of
	// 2Kb, since XMA blocks are arrays of 2Kb packets.
	uint32 SamplesEncoded;		// Total number of PCM samples encoded in this file
	uint32 SamplesInSource;		// Actual number of PCM samples in the source
	// material used to generate this file
	uint32 BlockCount;			// Number of XMA blocks in this file (and hence
	// also the number of entries in its seek table)
} XMA2WAVEFORMAT;

/*
========================
idWaveFile::ReadWaveFormat

Reads a wave format header, returns NULL if it found one and read it.
otherwise, returns a human-readable error message.
========================
*/
const char* idWaveFile::ReadWaveFormat( waveFmt_t& format )
{
	memset( &format, 0, sizeof( format ) );

	uint32 formatSize = SeekToChunk( waveFmt_t::id );
	if( formatSize == 0 )
	{
		return "No format chunk";
	}
	if( formatSize < sizeof( format.basic ) )
	{
		return "Format chunk too small";
	}

	if( Read( &format.basic, sizeof( format.basic ) ) != sizeof( format.basic ) )
	{
		return "Truncated format chunk";
	}

	idSwapClass<waveFmt_t::basic_t> swap;
	swap.Little( format.basic.formatTag );
	swap.Little( format.basic.numChannels );
	swap.Little( format.basic.samplesPerSec );
	swap.Little( format.basic.avgBytesPerSec );
	swap.Little( format.basic.blockSize );
	swap.Little( format.basic.bitsPerSample );
	if( format.basic.numChannels == 0 || format.basic.samplesPerSec == 0 )
	{
		return "Invalid wave format";
	}

	if( format.basic.formatTag == FORMAT_PCM )
	{
	}
	else if( format.basic.formatTag == FORMAT_ADPCM )
	{
		if( formatSize < sizeof( format.basic ) + sizeof( format.extraSize ) + sizeof( waveFmt_t::extra_t::adpcm_t ) )
		{
			return "ADPCM format chunk too small";
		}
		if( Read( &format.extraSize, sizeof( format.extraSize ) ) != sizeof( format.extraSize ) )
		{
			return "Truncated ADPCM format";
		}
		idSwap::Little( format.extraSize );
		if( format.extraSize != sizeof( waveFmt_t::extra_t::adpcm_t ) )
		{
			return "Incorrect number of coefficients in ADPCM file";
		}
		if( Read( &format.extra.adpcm, sizeof( format.extra.adpcm ) ) != sizeof( format.extra.adpcm ) )
		{
			return "Truncated ADPCM coefficients";
		}
		idSwapClass<waveFmt_t::extra_t::adpcm_t> swap;
		swap.Little( format.extra.adpcm.samplesPerBlock );
		swap.Little( format.extra.adpcm.numCoef );
		if( format.extra.adpcm.numCoef > 7 )
		{
			return "Too many ADPCM coefficients";
		}
		for( int i = 0; i < format.extra.adpcm.numCoef; i++ )
		{
			swap.Little( format.extra.adpcm.aCoef[ i ].coef1 );
			swap.Little( format.extra.adpcm.aCoef[ i ].coef2 );
		}
	}
	else if( format.basic.formatTag == FORMAT_XMA2 )
	{
		if( formatSize < sizeof( format.basic ) + sizeof( format.extraSize ) + sizeof( waveFmt_t::extra_t::xma2_t ) )
		{
			return "XMA2 format chunk too small";
		}
		if( Read( &format.extraSize, sizeof( format.extraSize ) ) != sizeof( format.extraSize ) )
		{
			return "Truncated XMA2 format";
		}
		idSwap::Little( format.extraSize );
		if( format.extraSize != sizeof( waveFmt_t::extra_t::xma2_t ) )
		{
			return "Incorrect chunk size in XMA2 file";
		}
		if( Read( &format.extra.xma2, sizeof( format.extra.xma2 ) ) != sizeof( format.extra.xma2 ) )
		{
			return "Truncated XMA2 data";
		}
		idSwapClass<waveFmt_t::extra_t::xma2_t> swap;
		swap.Little( format.extra.xma2.numStreams );
		swap.Little( format.extra.xma2.channelMask );
		swap.Little( format.extra.xma2.samplesEncoded );
		swap.Little( format.extra.xma2.bytesPerBlock );
		swap.Little( format.extra.xma2.playBegin );
		swap.Little( format.extra.xma2.playLength );
		swap.Little( format.extra.xma2.loopBegin );
		swap.Little( format.extra.xma2.loopLength );
		swap.Little( format.extra.xma2.loopCount );
		swap.Little( format.extra.xma2.encoderVersion );
		swap.Little( format.extra.xma2.blockCount );
	}
	else if( format.basic.formatTag == FORMAT_EXTENSIBLE )
	{
		if( formatSize < sizeof( format.basic ) + sizeof( format.extraSize ) + sizeof( waveFmt_t::extra_t::extensible_t ) )
		{
			return "Extensible format chunk too small";
		}
		if( Read( &format.extraSize, sizeof( format.extraSize ) ) != sizeof( format.extraSize ) )
		{
			return "Truncated extensible format";
		}
		idSwap::Little( format.extraSize );
		if( format.extraSize != sizeof( waveFmt_t::extra_t::extensible_t ) )
		{
			return "Incorrect chunk size in extensible wave file";
		}
		if( Read( &format.extra.extensible, sizeof( format.extra.extensible ) ) != sizeof( format.extra.extensible ) )
		{
			return "Truncated extensible data";
		}
		idSwapClass<waveFmt_t::extra_t::extensible_t> swap;
		swap.Little( format.extra.extensible.validBitsPerSample );
		swap.Little( format.extra.extensible.channelMask );
		swap.Little( format.extra.extensible.subFormat.data1 );
		swap.Little( format.extra.extensible.subFormat.data2 );
		swap.Little( format.extra.extensible.subFormat.data3 );
		swap.Little( format.extra.extensible.subFormat.data4 );
		swap.LittleArray( format.extra.extensible.subFormat.data5, 6 );
		waveFmt_t::extra_t::extensible_t::guid_t pcmGuid =
		{
			FORMAT_PCM,
			0x0000,
			0x0010,
			0x8000,
			{ 0x00, 0xaa, 0x00, 0x38, 0x9b, 0x71 }
		};
		if( memcmp( &pcmGuid, &format.extra.extensible.subFormat, sizeof( pcmGuid ) ) != 0 )
		{
			return "Unsupported Extensible format";
		}
	}
	else
	{
		return "Unknown wave format tag";
	}

	return NULL;
}

/*
========================
idWaveFile::ReadWaveFormatDirect

Reads a wave format header from a file ptr,
========================
*/
bool idWaveFile::ReadWaveFormatDirect( waveFmt_t& format, idFile* file )
{
	memset( &format, 0, sizeof( format ) );
	if( file == NULL )
	{
		return false;
	}

	if( file->Read( &format.basic, sizeof( format.basic ) ) != sizeof( format.basic ) )
	{
		return false;
	}
	idSwapClass<waveFmt_t::basic_t> swap;
	swap.Little( format.basic.formatTag );
	swap.Little( format.basic.numChannels );
	swap.Little( format.basic.samplesPerSec );
	swap.Little( format.basic.avgBytesPerSec );
	swap.Little( format.basic.blockSize );
	swap.Little( format.basic.bitsPerSample );
	if( format.basic.numChannels == 0 || format.basic.samplesPerSec == 0 )
	{
		return false;
	}

	if( format.basic.formatTag == FORMAT_PCM )
	{
	}
	else if( format.basic.formatTag == FORMAT_ADPCM )
	{
		if( file->Read( &format.extraSize, sizeof( format.extraSize ) ) != sizeof( format.extraSize ) )
		{
			return false;
		}
		idSwap::Little( format.extraSize );
		if( format.extraSize != sizeof( waveFmt_t::extra_t::adpcm_t ) )
		{
			return false;
		}
		if( file->Read( &format.extra.adpcm, sizeof( format.extra.adpcm ) ) != sizeof( format.extra.adpcm ) )
		{
			return false;
		}
		idSwapClass<waveFmt_t::extra_t::adpcm_t> swap;
		swap.Little( format.extra.adpcm.samplesPerBlock );
		swap.Little( format.extra.adpcm.numCoef );
		if( format.extra.adpcm.numCoef > 7 )
		{
			return false;
		}
		for( int i = 0; i < format.extra.adpcm.numCoef; i++ )
		{
			swap.Little( format.extra.adpcm.aCoef[ i ].coef1 );
			swap.Little( format.extra.adpcm.aCoef[ i ].coef2 );
		}
	}
	else if( format.basic.formatTag == FORMAT_XMA2 )
	{
		if( file->Read( &format.extraSize, sizeof( format.extraSize ) ) != sizeof( format.extraSize ) )
		{
			return false;
		}
		idSwap::Little( format.extraSize );
		if( format.extraSize != sizeof( waveFmt_t::extra_t::xma2_t ) )
		{
			return false;
		}
		if( file->Read( &format.extra.xma2, sizeof( format.extra.xma2 ) ) != sizeof( format.extra.xma2 ) )
		{
			return false;
		}
		idSwapClass<waveFmt_t::extra_t::xma2_t> swap;
		swap.Little( format.extra.xma2.numStreams );
		swap.Little( format.extra.xma2.channelMask );
		swap.Little( format.extra.xma2.samplesEncoded );
		swap.Little( format.extra.xma2.bytesPerBlock );
		swap.Little( format.extra.xma2.playBegin );
		swap.Little( format.extra.xma2.playLength );
		swap.Little( format.extra.xma2.loopBegin );
		swap.Little( format.extra.xma2.loopLength );
		swap.Little( format.extra.xma2.loopCount );
		swap.Little( format.extra.xma2.encoderVersion );
		swap.Little( format.extra.xma2.blockCount );
	}
	else if( format.basic.formatTag == FORMAT_EXTENSIBLE )
	{
		if( file->Read( &format.extraSize, sizeof( format.extraSize ) ) != sizeof( format.extraSize ) )
		{
			return false;
		}
		idSwap::Little( format.extraSize );
		if( format.extraSize != sizeof( waveFmt_t::extra_t::extensible_t ) )
		{
			return false;
		}
		if( file->Read( &format.extra.extensible, sizeof( format.extra.extensible ) ) != sizeof( format.extra.extensible ) )
		{
			return false;
		}
		idSwapClass<waveFmt_t::extra_t::extensible_t> swap;
		swap.Little( format.extra.extensible.validBitsPerSample );
		swap.Little( format.extra.extensible.channelMask );
		swap.Little( format.extra.extensible.subFormat.data1 );
		swap.Little( format.extra.extensible.subFormat.data2 );
		swap.Little( format.extra.extensible.subFormat.data3 );
		swap.Little( format.extra.extensible.subFormat.data4 );
		swap.LittleArray( format.extra.extensible.subFormat.data5, 6 );
		waveFmt_t::extra_t::extensible_t::guid_t pcmGuid =
		{
			FORMAT_PCM,
			0x0000,
			0x0010,
			0x8000,
			{ 0x00, 0xaa, 0x00, 0x38, 0x9b, 0x71 }
		};
		if( memcmp( &pcmGuid, &format.extra.extensible.subFormat, sizeof( pcmGuid ) ) != 0 )
		{
			return false;
		}
	}
	else
	{
		return false;
	}

	return true;
}

/*
========================
idWaveFile::WriteWaveFormatDirect

Writes a wave format header to a file ptr,
========================
*/
bool idWaveFile::WriteWaveFormatDirect( waveFmt_t& format, idFile* file )
{
	//idSwapClass<waveFmt_t::basic_t> swap;
	//swap.Little( format.basic.formatTag );
	//swap.Little( format.basic.numChannels );
	//swap.Little( format.basic.samplesPerSec );
	//swap.Little( format.basic.avgBytesPerSec );
	//swap.Little( format.basic.blockSize );
	//swap.Little( format.basic.bitsPerSample );
	file->Write( &format.basic, sizeof( format.basic ) );
	if( format.basic.formatTag == FORMAT_PCM )
	{
		//file->Write( &format.basic, sizeof( format.basic ) );
	}
	else if( format.basic.formatTag == FORMAT_ADPCM )
	{
		//file->Write( &format.basic, sizeof( format.basic ) );
		file->Write( &format.extraSize, sizeof( format.extraSize ) );
		file->Write( &format.extra.adpcm, sizeof( format.extra.adpcm ) );
	}
	else if( format.basic.formatTag == FORMAT_XMA2 )
	{
		//file->Write( &format.basic, sizeof( format.basic ) );
		file->Write( &format.extraSize, sizeof( format.extraSize ) );
		file->Write( &format.extra.xma2, sizeof( format.extra.xma2 ) );
	}
	else if( format.basic.formatTag == FORMAT_EXTENSIBLE )
	{
		//file->Write( &format.basic, sizeof( format.basic ) );
		file->Write( &format.extraSize, sizeof( format.extraSize ) );
		file->Write( &format.extra.extensible, sizeof( format.extra.extensible ) );
	}
	else
	{
		return false;
	}
	return true;
}

/*
========================
idWaveFile::WriteWaveFormatDirect

Writes a wave format header to a file ptr,
========================
*/

bool idWaveFile::WriteSampleDataDirect( idList< sampleData_t >& sampleData, idFile* file )
{
	static const uint32 sample = 'smpl';
	file->WriteBig( sample );
	uint32 samplerData = sampleData.Num() * 24;
	uint32 chunkSize = 36 + samplerData;
	uint32 zero = 0;
	uint32 numSamples = sampleData.Num();

	file->Write( &chunkSize, sizeof( uint32 ) );
	file->Write( &zero, sizeof( uint32 ) );
	file->Write( &zero, sizeof( uint32 ) );
	file->Write( &zero, sizeof( uint32 ) );
	file->Write( &zero, sizeof( uint32 ) );
	file->Write( &zero, sizeof( uint32 ) );
	file->Write( &zero, sizeof( uint32 ) );
	file->Write( &zero, sizeof( uint32 ) );
	file->Write( &numSamples, sizeof( uint32 ) );
	file->Write( &samplerData, sizeof( uint32 ) );

	for( int i = 0; i < sampleData.Num(); ++i )
	{
		file->Write( &zero, sizeof( uint32 ) );
		file->Write( &zero, sizeof( uint32 ) );
		file->Write( &sampleData[ i ].start, sizeof( uint32 ) );
		file->Write( &sampleData[ i ].end, sizeof( uint32 ) );
		file->Write( &zero, sizeof( uint32 ) );
		file->Write( &zero, sizeof( uint32 ) );
	}
	return true;
}

/*
========================
idWaveFile::WriteWaveFormatDirect

Writes a data chunk to a file ptr
========================
*/

bool idWaveFile::WriteDataDirect( char* _data, uint32 size, idFile* file )
{
	static const uint32 data = 'data';
	file->WriteBig( data );
	file->Write( &size, sizeof( uint32 ) );
	file->WriteBigArray( _data, size );
	return true;
}

/*
========================
idWaveFile::WriteWaveFormatDirect

Writes a wave header to a file ptr,
========================
*/

bool idWaveFile::WriteHeaderDirect( uint32 fileSize, idFile* file )
{
	static const uint32 riff = 'RIFF';
	static const uint32 wave = 'WAVE';
	file->WriteBig( riff );
	file->WriteBig( fileSize );
	file->WriteBig( wave );
	return true;
}

/*
========================
idWaveFile::ReadLoopPoint

Reads a loop point from a 'smpl' chunk in a wave file, returns 0 if none are found.
========================
*/
bool idWaveFile::ReadLoopData( int& start, int& end )
{
	uint32 chunkSize = SeekToChunk( samplerChunk_t::id );
	if( chunkSize < sizeof( samplerChunk_t ) )
	{
		return false;
	}

	samplerChunk_t smpl;
	if( Read( &smpl, sizeof( smpl ) ) != sizeof( smpl ) )
	{
		return false;
	}
	idSwap::Little( smpl.numSampleLoops );

	if( smpl.numSampleLoops < 1 )
	{
		return false; // this is possible returning false lets us know there are more then 1 sample look in the file and is not appropriate for traditional looping
	}
	if( chunkSize < sizeof( samplerChunk_t ) + sizeof( sampleData_t ) )
	{
		return false;
	}

	sampleData_t smplData;
	if( Read( &smplData, sizeof( smplData ) ) != sizeof( smplData ) )
	{
		return false;
	}
	idSwap::Little( smplData.type );
	idSwap::Little( smplData.start );
	idSwap::Little( smplData.end );

	if( smplData.type != 0 )
	{
		idLib::Warning( "Invalid loop type in %s", file->GetName() );
		return false;
	}
	if( smplData.end < smplData.start )
	{
		idLib::Warning( "Invalid loop range in %s", file->GetName() );
		return false;
	}

	start = smplData.start;
	end = smplData.end;
	return true;
}

/*
========================
idWaveFile::Close

Closes the file and frees resources.
========================
*/
void idWaveFile::Close()
{
	if( file != NULL )
	{
		delete file;
		file = NULL;
	}
	chunks.SetNum( 0 );
}
