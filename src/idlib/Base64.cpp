



/*
Copyright (c) 1996 Lars Wirzenius.  All rights reserved.

June 14 2003: TTimo <ttimo@idsoftware.com>
	modified + endian bug fixes
	http://bugs.debian.org/cgi-bin/bugreport.cgi?bug=197039

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:

1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT,
INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.
*/

/*
============
idBase64::Encode
============
*/
static const char sixtet_to_base64[] = 
	"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static bool Base64_IsWhiteSpace( const byte c ) {
	return c == ' ' || c == '\n' || c == '\r' || c == '\t';
}

static int Base64_DecodeSixtet( const byte c ) {
	if ( c >= 'A' && c <= 'Z' ) {
		return c - 'A';
	}
	if ( c >= 'a' && c <= 'z' ) {
		return c - 'a' + 26;
	}
	if ( c >= '0' && c <= '9' ) {
		return c - '0' + 52;
	}
	if ( c == '+' ) {
		return 62;
	}
	if ( c == '/' ) {
		return 63;
	}
	return -1;
}

void idBase64::Encode( const byte *from, int size ) {
	int i, j;
	uint32_t w;
	byte *to;

	if ( from == NULL || size <= 0 ) {
		EnsureAlloced( 1 );
		if ( data != NULL ) {
			data[0] = '\0';
		}
		len = 0;
		return;
	}

	uint64 encodedSize = 4ULL * ( ( (uint64)size + 2ULL ) / 3ULL ) + 1ULL;
	if ( encodedSize > (uint64)idMath::INT_MAX ) {
		EnsureAlloced( 1 );
		if ( data != NULL ) {
			data[0] = '\0';
		}
		len = 0;
		return;
	}
	
	EnsureAlloced( (int)encodedSize ); // ratio and padding + trailing \0
	if ( data == NULL ) {
		len = 0;
		return;
	}
	to = data;
	
	w = 0;
	i = 0;
	while (size > 0) {
		w |= static_cast<uint32_t>( *from ) << ( i * 8 );
		++from;
		--size;
		++i;
		if (size == 0 || i == 3) {
			byte out[4];
			SixtetsForInt( out, w );
			for (j = 0; j*6 < i*8; ++j) {
				*to++ = sixtet_to_base64[ out[j] ];
			}
			if (size == 0) {
				for (j = i; j < 3; ++j) {
					*to++ = '=';
				}
			}
			w = 0;
			i = 0;
		}
	}
	
	*to++ = '\0';
	len = (int)( to - data - 1 );
}

/*
============
idBase64::DecodeLength
returns the minimum size in bytes of the target buffer for decoding
4 base64 digits <-> 3 bytes
============
*/
int idBase64::DecodeLength( void ) const {
	if ( data == NULL || len <= 0 ) {
		return 0;
	}

	int digits = 0;
	for ( const byte *from = data; *from != '\0'; ++from ) {
		if ( Base64_IsWhiteSpace( *from ) ) {
			continue;
		}
		if ( *from == '=' ) {
			break;
		}
		if ( Base64_DecodeSixtet( *from ) < 0 ) {
			break;
		}
		digits++;
	}

	uint64 decodedLength = ( (uint64)digits * 6ULL ) / 8ULL;
	if ( decodedLength > (uint64)idMath::INT_MAX ) {
		return idMath::INT_MAX;
	}
	return (int)decodedLength;
}

/*
============
idBase64::Decode
============
*/
int idBase64::Decode( byte *to ) const {
	uint32_t w;
	int i, j;
	size_t n;
	byte *from = data;
	
	if ( to == NULL || from == NULL ) {
		return 0;
	}

	i = 0;
	n = 0;
	byte in[4] = {0,0,0,0};
	while (*from != '\0' && *from != '=' ) {
		if ( Base64_IsWhiteSpace( *from ) ) {
			++from;
			continue;
		}
		int sixtet = Base64_DecodeSixtet( *from );
		if ( sixtet < 0 ) {
			return idLib::SizeToInt( n, "idBase64::Decode" );
		}
		in[i] = (byte)sixtet;
		++i;
		++from;
		if ( i == 4 ) {
			w = IntForSixtets( in );
			for (j = 0; j < 3; ++j) {
				*to++ = w & 0xff;
				++n;
				w >>= 8;
			}
			i = 0;
			memset( in, 0, sizeof( in ) );
		}
	}
	if ( i > 1 ) {
		w = IntForSixtets( in );
		int outBytes = ( i * 6 ) / 8;
		for ( j = 0; j < outBytes; ++j ) {
			*to++ = w & 0xff;
			++n;
			w >>= 8;
		}
	}
	return idLib::SizeToInt( n, "idBase64::Decode" );
}

/*
============
idBase64::Encode
============
*/
void idBase64::Encode( const idStr &src ) {
	Encode( (const byte *)src.c_str(), src.Length() );
}

/*
============
idBase64::Decode
============
*/
void idBase64::Decode( idStr &dest ) const {
	int decodedLength = DecodeLength();
	byte *buf = new byte[ decodedLength + 1 ]; // +1 for trailing \0
	int out = Decode( buf );
	buf[out] = '\0';
	dest = (const char *)buf;
	delete[] buf;
}

/*
============
idBase64::Decode
============
*/
void idBase64::Decode( idFile *dest ) const {	
	if ( dest == NULL ) {
		return;
	}
	int decodedLength = DecodeLength();
	byte *buf = new byte[ decodedLength + 1 ]; // +1 for trailing \0
	int out = Decode( buf );
	if ( out > 0 ) {
		dest->Write( buf, out );
	}
	delete[] buf;
}

#if 0

void idBase64_TestBase64() {
		
	idStr src;
	idBase64 dest;
	src = "Encode me in base64";
	dest.Encode( src );
	idLib::common->Printf( "%s -> %s\n", src.c_str(), dest.c_str() );
	dest.Decode( src );
	idLib::common->Printf( "%s -> %s\n", dest.c_str(), src.c_str() );

	idDict src_dict;
	src_dict.SetFloat("float", 0.5f);
	src_dict.SetBool("bool", true);
	src_dict.Set("value", "foo");
	idFile_Memory src_fmem("serialize_dict");	
	src_dict.WriteToFileHandle( &src_fmem );
	dest.Encode( (const byte *)src_fmem.GetDataPtr(), src_fmem.Length() );
	idLib::common->Printf( "idDict encoded to %s\n", dest.c_str());
	
	// now decode to another stream and build back
	idFile_Memory dest_fmem( "build_back" );
	dest.Decode( &dest_fmem );
	dest_fmem.MakeReadOnly();
	idDict dest_dict;
	dest_dict.ReadFromFileHandle( &dest_fmem );
	idLib::common->Printf( "idDict reconstructed after base64 decode\n");
	dest_dict.Print();
	
	// test idDict read from file - from python generated files, see idDict.py
	idFile *file = idLib::fileSystem->OpenFileRead("idDict.test");
	if (file) {
		idDict test_dict;
		test_dict.ReadFromFileHandle( file );
		//
		idLib::common->Printf( "read idDict.test:\n");
		test_dict.Print();
		idLib::fileSystem->CloseFile(file);
		file = NULL;
	} else {
		idLib::common->Printf( "idDict.test not found\n" );
	}

	idBase64 base64_src;
	void *buffer;
	if ( idLib::fileSystem->ReadFile( "idDict.base64.test", &buffer ) != -1 ) {
		idFile_Memory mem_src( "dict" );
		idLib::common->Printf( "read: %d %s\n", idStr::Length( (char*)buffer ), buffer );
		base64_src = (char *)buffer;
		base64_src.Decode( &mem_src );
		mem_src.MakeReadOnly();
		idDict test_dict;
		test_dict.ReadFromFileHandle( &mem_src );
		idLib::common->Printf( "read idDict.base64.test:\n");
		test_dict.Print();
		idLib::fileSystem->FreeFile( buffer );
	} else {
		idLib::common->Printf( "idDict.base64.test not found\n" );
	}
}

#endif
