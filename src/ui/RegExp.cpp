/*
===========================================================================

Doom 3 GPL Source Code
Copyright (C) 1999-2011 id Software LLC, a ZeniMax Media company. 

This file is part of the Doom 3 GPL Source Code (?Doom 3 Source Code?).  

Doom 3 Source Code is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Doom 3 Source Code is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Doom 3 Source Code.  If not, see <http://www.gnu.org/licenses/>.

In addition, the Doom 3 Source Code is also subject to certain additional terms. You should have received a copy of these additional terms immediately following the terms and conditions of the GNU General Public License which accompanied the Doom 3 Source Code.  If not, please request a copy in writing from id Software at the address below.

If you have questions concerning this license or the applicable additional terms, you may contact in writing id Software LLC, c/o ZeniMax Media Inc., Suite 120, Rockville, Maryland 20850 USA.

===========================================================================
*/




#include "RegExp.h"
#include "DeviceContext.h"
#include "Window.h"
#include "UserInterfaceLocal.h"

int idRegister::REGCOUNT[NUMTYPES] = {4, 1, 1, 1, 0, 2, 3, 4};

static const int REGEXP_MAX_SAVEGAME_STRING_LENGTH = 64 * 1024;

static void RegExp_CheckSaveGameTransfer( int actualBytes, int expectedBytes, int offset, const char *operation, const char *detail ) {
	if ( actualBytes != expectedBytes ) {
		common->Error( "idRegister savegame: failed to %s %s at offset %d (%d of %d bytes)",
			operation ? operation : "transfer", detail ? detail : "data", offset, actualBytes, expectedBytes );
	}
}

static void RegExp_WriteSaveGameUnsignedChar( idFile *savefile, unsigned char value, const char *detail ) {
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->WriteUnsignedChar( value ), static_cast<int>( sizeof( value ) ), offset, "write", detail );
}

static void RegExp_WriteSaveGameShort( idFile *savefile, short value, const char *detail ) {
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->WriteShort( value ), static_cast<int>( sizeof( value ) ), offset, "write", detail );
}

static void RegExp_WriteSaveGameInt( idFile *savefile, int value, const char *detail ) {
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->WriteInt( value ), static_cast<int>( sizeof( value ) ), offset, "write", detail );
}

static void RegExp_WriteSaveGameUnsignedShort( idFile *savefile, unsigned short value, const char *detail ) {
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->WriteUnsignedShort( value ), static_cast<int>( sizeof( value ) ), offset, "write", detail );
}

static void RegExp_WriteSaveGameBytes( idFile *savefile, const void *buffer, int len, const char *detail ) {
	if ( len <= 0 ) {
		return;
	}
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->Write( buffer, len ), len, offset, "write", detail );
}

static void RegExp_ReadSaveGameBytes( idFile *savefile, void *buffer, int len, const char *detail ) {
	const int offset = savefile->Tell();
	const int bytesRead = savefile->Read( buffer, len );
	RegExp_CheckSaveGameTransfer( bytesRead, len, offset, "read", detail );
}

static unsigned char RegExp_ReadSaveGameUnsignedChar( idFile *savefile, const char *detail ) {
	unsigned char value = 0;
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->ReadUnsignedChar( value ), static_cast<int>( sizeof( value ) ), offset, "read", detail );
	return value;
}

static short RegExp_ReadSaveGameShort( idFile *savefile, const char *detail ) {
	short value = 0;
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->ReadShort( value ), static_cast<int>( sizeof( value ) ), offset, "read", detail );
	return value;
}

static int RegExp_ReadSaveGameInt( idFile *savefile, const char *detail ) {
	int value = 0;
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->ReadInt( value ), static_cast<int>( sizeof( value ) ), offset, "read", detail );
	return value;
}

static unsigned short RegExp_ReadSaveGameUnsignedShort( idFile *savefile, const char *detail ) {
	unsigned short value = 0;
	const int offset = savefile->Tell();
	RegExp_CheckSaveGameTransfer( savefile->ReadUnsignedShort( value ), static_cast<int>( sizeof( value ) ), offset, "read", detail );
	return value;
}

static void RegExp_WriteSaveGameString( idFile *savefile, const idStr &string, const char *detail ) {
	const int len = string.Length();
	if ( len < 0 || len > REGEXP_MAX_SAVEGAME_STRING_LENGTH ) {
		common->Error( "idRegister::WriteToSaveGame: invalid %s length %d (max %d)",
			detail ? detail : "string", len, REGEXP_MAX_SAVEGAME_STRING_LENGTH );
	}
	RegExp_WriteSaveGameInt( savefile, len, detail );
	RegExp_WriteSaveGameBytes( savefile, string.c_str(), len, detail );
}

static void RegExp_ReadSaveGameString( idFile *savefile, idStr &string, const char *detail ) {
	const int offset = savefile->Tell();
	const int len = RegExp_ReadSaveGameInt( savefile, detail );
	const int remainingBytes = Max( 0, savefile->Length() - savefile->Tell() );
	if ( len < 0 || len > REGEXP_MAX_SAVEGAME_STRING_LENGTH || len > remainingBytes ) {
		common->Error( "idRegister::ReadFromSaveGame: invalid %s length %d at offset %d (remaining %d, max %d)",
			detail ? detail : "string", len, offset, remainingBytes, REGEXP_MAX_SAVEGAME_STRING_LENGTH );
	}
	string.Fill( ' ', len );
	if ( len > 0 ) {
		RegExp_ReadSaveGameBytes( savefile, &string[0], len, detail );
	}
}

/*
====================
idRegister::SetToRegs
====================
*/
void idRegister::SetToRegs( float *registers ) {
	int i;
	idVec4 v;
	idVec2 v2;
	idVec3 v3;
	idRectangle rect;

	if ( !enabled || var == NULL || ( var && ( var->GetDict() || !var->GetEval() ) ) ) {
		return;
	}

	switch( type ) {
		case VEC4: {
			v = *static_cast<idWinVec4*>(var);
			break;
		}
		case RECTANGLE: {
			rect = *static_cast<idWinRectangle*>(var);
			v = rect.ToVec4();
			break;
		}
		case VEC2: {
			v2 = *static_cast<idWinVec2*>(var);
			v[0] = v2[0];
			v[1] = v2[1];
			break;
		}
		case VEC3: {
			v3 = *static_cast<idWinVec3*>(var);
			v[0] = v3[0];
			v[1] = v3[1];
			v[2] = v3[2];
			break;
		}
		case FLOAT: {
			v[0] = *static_cast<idWinFloat*>(var);
			break;
		}
		case INT: {
			v[0] = *static_cast<idWinInt*>(var);
			break;
		}
		case BOOL: {
			v[0] = *static_cast<idWinBool*>(var);
			break;
		}
		default: {
			common->FatalError( "idRegister::SetToRegs: bad reg type" );
			break;
		}
	}
	for ( i = 0; i < regCount; i++ ) {
		registers[ regs[ i ] ] = v[i];
	}
}

/*
=================
idRegister::GetFromRegs
=================
*/
void idRegister::GetFromRegs( float *registers ) {
	idVec4 v;
	idRectangle rect;

	if (!enabled || var == NULL || (var && (var->GetDict() || !var->GetEval()))) {
		return;
	}

	for ( int i = 0; i < regCount; i++ ) {
		v[i] = registers[regs[i]];
	}
	
	switch( type ) {
		case VEC4: {
			*dynamic_cast<idWinVec4*>(var) = v;
			break;
		}
		case RECTANGLE: {
			rect.x = v.x;
			rect.y = v.y;
			rect.w = v.z;
			rect.h = v.w;
			*static_cast<idWinRectangle*>(var) = rect;
			break;
		}
		case VEC2: {
			*static_cast<idWinVec2*>(var) = v.ToVec2();
			break;
		}
		case VEC3: {
			*static_cast<idWinVec3*>(var) = v.ToVec3();
			break;
		}
		case FLOAT: {
			*static_cast<idWinFloat*>(var) = v[0];
			break;
		}
		case INT: {
			*static_cast<idWinInt*>(var) = v[0];
			break;
		}
		case BOOL: {
			*static_cast<idWinBool*>(var) = ( v[0] != 0.0f );
			break;
		}
		default: {
			common->FatalError( "idRegister::GetFromRegs: bad reg type" );
			break;
		}
	}
}

/*
=================
idRegister::ReadFromDemoFile
=================
*/
void idRegister::ReadFromDemoFile(idDemoFile *f) {
	f->ReadBool( enabled );
	f->ReadShort( type );
	f->ReadInt( regCount );
	for ( int i = 0; i < 4; i++ )
		f->ReadUnsignedShort( regs[i] );
	name = f->ReadHashString();
}

/*
=================
idRegister::WriteToDemoFile
=================
*/
void idRegister::WriteToDemoFile( idDemoFile *f ) {
	f->WriteBool( enabled );
	f->WriteShort( type );
	f->WriteInt( regCount );
	for (int i = 0; i < 4; i++)
		f->WriteUnsignedShort( regs[i] );
	f->WriteHashString( name );
}

/*
=================
idRegister::WriteToSaveGame
=================
*/
void idRegister::WriteToSaveGame( idFile *savefile ) {
	if ( savefile == NULL ) {
		common->Error( "idRegister::WriteToSaveGame: NULL output file" );
	}
	if ( type < 0 || type >= NUMTYPES ) {
		common->Error( "idRegister::WriteToSaveGame: invalid live register type %d for '%s'", type, name.c_str() );
	}
	const int expectedRegCount = REGCOUNT[type];
	if ( regCount < 0 || regCount > 4 || regCount != expectedRegCount ) {
		common->Error( "idRegister::WriteToSaveGame: invalid live register count %d for '%s' type %d (expected %d)",
			regCount, name.c_str(), type, expectedRegCount );
	}
	if ( type == STRING && enabled ) {
		common->Error( "idRegister::WriteToSaveGame: string register '%s' cannot be enabled", name.c_str() );
	}
	if ( var == NULL ) {
		common->Error( "idRegister::WriteToSaveGame: register '%s' has no variable", name.c_str() );
	}

	RegExp_WriteSaveGameUnsignedChar( savefile, static_cast<unsigned char>( enabled ? 1 : 0 ), "enabled flag" );
	RegExp_WriteSaveGameShort( savefile, type, "type" );
	RegExp_WriteSaveGameInt( savefile, regCount, "register count" );
	for ( int i = 0; i < 4; i++ ) {
		const unsigned short savedReg = ( i < regCount ) ? regs[i] : 0;
		if ( i < regCount && savedReg >= MAX_EXPRESSION_REGISTERS ) {
			common->Error( "idRegister::WriteToSaveGame: register '%s' has out-of-range expression index %u at slot %d (max %d)",
				name.c_str(), static_cast<unsigned int>( savedReg ), i, MAX_EXPRESSION_REGISTERS - 1 );
		}
		RegExp_WriteSaveGameUnsignedShort( savefile, savedReg, "register index" );
	}
	RegExp_WriteSaveGameString( savefile, name, "name" );

	// The variable itself usually carries no name, so a refusal deeper in could not
	// say which register was at fault. Catch it here, where the name is known, and
	// keep the save: a register holds an evaluated GUI expression, so a zeroed
	// component costs a frame of cosmetic state rather than the whole save and the
	// running map with it.
	if ( !var->IsFinite() ) {
		common->Warning( "idRegister::WriteToSaveGame: register '%s' holds a non-finite value; "
			"saving zero for the affected components", name.c_str() );
		var->SanitizeNonFinite();
	}

	var->WriteToSaveGame( savefile );
}

/*
================
idRegister::ReadFromSaveGame
================
*/
void idRegister::ReadFromSaveGame( idFile *savefile ) {
	if ( savefile == NULL ) {
		common->Error( "idRegister::ReadFromSaveGame: NULL input file" );
	}

	const unsigned char savedEnabled = RegExp_ReadSaveGameUnsignedChar( savefile, "enabled flag" );
	const short savedType = RegExp_ReadSaveGameShort( savefile, "type" );
	const int savedRegCount = RegExp_ReadSaveGameInt( savefile, "register count" );
	unsigned short savedRegs[4] = { 0, 0, 0, 0 };
	for ( int i = 0; i < 4; i++ ) {
		savedRegs[i] = RegExp_ReadSaveGameUnsignedShort( savefile, "register index" );
	}
	idStr savedName;
	RegExp_ReadSaveGameString( savefile, savedName, "name" );

	// The GUI was parsed before restore. Its register schema is authoritative:
	// accepting saved structural metadata would let a corrupt file change casts,
	// loop bounds, or expression-register indexes before the variable is restored.
	if ( savedEnabled > 1 ) {
		common->Error( "idRegister::ReadFromSaveGame: invalid enabled flag %u for parsed register '%s'",
			static_cast<unsigned int>( savedEnabled ), name.c_str() );
	}
	if ( type < 0 || type >= NUMTYPES ) {
		common->Error( "idRegister::ReadFromSaveGame: invalid parsed register type %d for '%s'", type, name.c_str() );
	}
	const int expectedLiveRegCount = REGCOUNT[type];
	if ( regCount < 0 || regCount > 4 || regCount != expectedLiveRegCount ) {
		common->Error( "idRegister::ReadFromSaveGame: invalid parsed register count %d for '%s' type %d (expected %d)",
			regCount, name.c_str(), type, expectedLiveRegCount );
	}
	if ( savedType < 0 || savedType >= NUMTYPES ) {
		common->Error( "idRegister::ReadFromSaveGame: invalid saved register type %d for parsed register '%s'",
			savedType, name.c_str() );
	}
	const int expectedSavedRegCount = REGCOUNT[savedType];
	if ( savedRegCount < 0 || savedRegCount > 4 || savedRegCount != expectedSavedRegCount ) {
		common->Error( "idRegister::ReadFromSaveGame: invalid saved register count %d for '%s' type %d (expected %d)",
			savedRegCount, savedName.c_str(), savedType, expectedSavedRegCount );
	}
	if ( savedType != type || savedRegCount != regCount || savedName.Icmp( name ) != 0 ) {
		common->Error( "idRegister::ReadFromSaveGame: saved register schema '%s' (type %d, count %d) does not match parsed schema '%s' (type %d, count %d)",
			savedName.c_str(), savedType, savedRegCount, name.c_str(), type, regCount );
	}
	if ( savedType == STRING && savedEnabled != 0 ) {
		common->Error( "idRegister::ReadFromSaveGame: string register '%s' cannot be enabled", name.c_str() );
	}
	for ( int i = 0; i < savedRegCount; i++ ) {
		if ( savedRegs[i] >= MAX_EXPRESSION_REGISTERS || regs[i] >= MAX_EXPRESSION_REGISTERS ) {
			common->Error( "idRegister::ReadFromSaveGame: register '%s' has out-of-range expression index at slot %d (saved %u, parsed %u, max %d)",
				name.c_str(), i, static_cast<unsigned int>( savedRegs[i] ), static_cast<unsigned int>( regs[i] ), MAX_EXPRESSION_REGISTERS - 1 );
		}
		if ( savedRegs[i] != regs[i] ) {
			common->Error( "idRegister::ReadFromSaveGame: register '%s' expression index mismatch at slot %d (saved %u, parsed %u)",
				name.c_str(), i, static_cast<unsigned int>( savedRegs[i] ), static_cast<unsigned int>( regs[i] ) );
		}
	}
	if ( var == NULL ) {
		common->Error( "idRegister::ReadFromSaveGame: parsed register '%s' has no variable", name.c_str() );
	}

	enabled = savedEnabled != 0;
	var->ReadFromSaveGame( savefile );
}

/*
====================
idRegisterList::AddReg
====================
*/
void idRegisterList::AddReg( const char *name, int type, idVec4 data, idWindow *win, idWinVar *var ) {
	if ( FindReg( name ) == NULL ) {
		assert( type >= 0 && type < idRegister::NUMTYPES );
		int numRegs = idRegister::REGCOUNT[type];
		idRegister *reg = new idRegister( name, type );
		reg->var = var;
		for ( int i = 0; i < numRegs; i++ ) {
			reg->regs[i] = win->ExpressionConstant(data[i]);
		}
		int hash = regHash.GenerateKey( name, false );
		regHash.Add( hash, regs.Append( reg ) );
	}
}

/*
====================
idRegisterList::AddReg
====================
*/
void idRegisterList::AddReg( const char *name, int type, idParser *src, idWindow *win, idWinVar *var ) {
	idRegister* reg;

	reg = FindReg( name );

	if ( reg == NULL ) {
		assert(type >= 0 && type < idRegister::NUMTYPES);
		int numRegs = idRegister::REGCOUNT[type];
		reg = new idRegister( name, type );
		reg->var = var;
		if ( type == idRegister::STRING ) {
			idToken tok;
			if ( src->ReadToken( &tok ) ) {
				tok = common->GetLanguageDict()->GetString( tok );
				var->Init( tok, win );
			}
		} else {
			for ( int i = 0; i < numRegs; i++ ) {
				reg->regs[i] = win->ParseExpression(src, NULL);
				if ( i < numRegs-1 ) {
					src->ExpectTokenString(",");
				}
			}
		}
		int hash = regHash.GenerateKey( name, false );
		regHash.Add( hash, regs.Append( reg ) );
	} else {
		int numRegs = idRegister::REGCOUNT[type];
		reg->var = var;
		if ( type == idRegister::STRING ) {
			idToken tok;
			if ( src->ReadToken( &tok ) ) {
				var->Init( tok, win );
			}
		} else {
			for ( int i = 0; i < numRegs; i++ ) {
				reg->regs[i] = win->ParseExpression( src, NULL );
				if ( i < numRegs-1 ) {
					src->ExpectTokenString(",");
				}
			}
		}
	}
}

/*
====================
idRegisterList::GetFromRegs
====================
*/
void idRegisterList::GetFromRegs(float *registers) {
	for ( int i = 0; i < regs.Num(); i++ ) {
		regs[i]->GetFromRegs( registers );
	}
}

/*
====================
idRegisterList::SetToRegs
====================
*/

void idRegisterList::SetToRegs( float *registers ) {
	int i;
	for ( i = 0; i < regs.Num(); i++ ) {
		regs[i]->SetToRegs( registers );
	}
}

/*
====================
idRegisterList::FindReg
====================
*/
idRegister *idRegisterList::FindReg( const char *name ) {
	int hash = regHash.GenerateKey( name, false );
	for ( int i = regHash.First( hash ); i != -1; i = regHash.Next( i ) ) {
		if ( regs[i]->name.Icmp( name ) == 0 ) {
			return regs[i];
		}
	}
	return NULL;
}

/*
====================
idRegisterList::Reset
====================
*/
void idRegisterList::Reset() {
	regs.DeleteContents( true );
	regHash.Clear();
}

/*
====================
idRegisterList::ReadFromSaveGame
====================
*/
void idRegisterList::ReadFromDemoFile(idDemoFile *f) {
	int c;

	f->ReadInt( c );
	regs.DeleteContents( true );
	for ( int i = 0; i < c; i++ ) {
		idRegister *reg = new idRegister;
		reg->ReadFromDemoFile( f );
		regs.Append( reg );
	}
}

/*
====================
idRegisterList::ReadFromSaveGame
====================
*/
void idRegisterList::WriteToDemoFile(idDemoFile *f) {
	int c = regs.Num();

	f->WriteInt( c );
	for ( int i = 0 ; i < c; i++ ) {
		regs[i]->WriteToDemoFile(f);
	}
}

/*
=====================
idRegisterList::WriteToSaveGame
=====================
*/
void idRegisterList::WriteToSaveGame( idFile *savefile ) {
	if ( savefile == NULL ) {
		common->Error( "idRegisterList::WriteToSaveGame: NULL output file" );
	}
	const int num = regs.Num();
	RegExp_WriteSaveGameInt( savefile, num, "register list count" );

	for ( int i = 0; i < num; i++ ) {
		regs[i]->WriteToSaveGame( savefile );
	}
}

/*
====================
idRegisterList::ReadFromSaveGame
====================
*/
void idRegisterList::ReadFromSaveGame( idFile *savefile ) {
	if ( savefile == NULL ) {
		common->Error( "idRegisterList::ReadFromSaveGame: NULL input file" );
	}
	const int num = RegExp_ReadSaveGameInt( savefile, "register list count" );
	if ( num < 0 || num != regs.Num() ) {
		common->Error( "idRegisterList::ReadFromSaveGame: saved register count %d does not match parsed count %d",
			num, regs.Num() );
	}
	for ( int i = 0; i < num; i++ ) {
		regs[i]->ReadFromSaveGame( savefile );
	}
}
