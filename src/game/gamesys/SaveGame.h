// Copyright (C) 2004 Id Software, Inc.
//

#ifndef __SAVEGAME_H__
#define __SAVEGAME_H__

/*

Save game related helper classes.

*/

const int INITIAL_RELEASE_BUILD_NUMBER = 1262;
const int OPENQ4_SAVEGAME_COMPATIBILITY_MAGIC = 'O' | ( 'Q' << 8 ) | ( '4' << 16 ) | ( 'S' << 24 );
// The payload version is shared with the engine session, which frames the
// payload and writes the GUI and sound records inside it. Version 5 is the one
// the session writes: its header ends with a wire-ABI stamp, the session appends
// an integrity trailer after the footer, and the engine's own records use that
// version's encodings. Prey's game records keep their native layout, so the
// stamp names the build family that wrote them (see SaveGame.cpp).
const int OPENQ4_SAVEGAME_COMPATIBILITY_VERSION = 5;
const int OPENQ4_SAVEGAME_SYNC_MAGIC = 'O' | ( 'Q' << 8 ) | ( '4' << 16 ) | ( 'Y' << 24 );
const int OPENQ4_SAVEGAME_FOOTER_MAGIC = 'O' | ( 'Q' << 8 ) | ( '4' << 16 ) | ( 'F' << 24 );
const int OPENQ4_SAVEGAME_FOOTER_VERSION = 1;
const int OPENQ4_SAVEGAME_INTEGRITY_MAGIC = 'O' | ( 'Q' << 8 ) | ( '4' << 16 ) | ( 'I' << 24 );
const int OPENQ4_SAVEGAME_INTEGRITY_VERSION = 1;

#if defined( __has_include )
#if __has_include( "openq4_savegame_compat_generated.h" )
#include "openq4_savegame_compat_generated.h"
#endif
#endif

#ifndef OPENQ4_SAVEGAME_COMPAT_SOURCE_HASH
#define OPENQ4_SAVEGAME_COMPAT_SOURCE_HASH "standalone-openprey-game"
#endif

#ifndef OPENQ4_SAVEGAME_COMPAT_SOURCE_FILE_COUNT
#define OPENQ4_SAVEGAME_COMPAT_SOURCE_FILE_COUNT 0
#endif

class idSaveGame {
public:
							idSaveGame( idFile *savefile );
							~idSaveGame();

	void					Close( void );

	void					AddObject( const idClass *obj );
	void					WriteObjectList( void );

	void					Write( const void *buffer, int len );
	void					WriteInt( const int value );
	void					WriteJoint( const jointHandle_t value );
	void					WriteShort( const short value );
	void					WriteByte( const byte value );
	void					WriteSignedChar( const signed char value );
	void					WriteFloat( const float value );
	void					WriteBool( const bool value );
	void					WriteString( const char *string );
	void					WriteVec2( const idVec2 &vec );
	void					WriteVec3( const idVec3 &vec );
	void					WriteVec4( const idVec4 &vec );
	void					WriteVec6( const idVec6 &vec );
	void					WriteWinding( const idWinding &winding );
	void					WriteBounds( const idBounds &bounds );
	void					WriteMat3( const idMat3 &mat );
	void					WriteAngles( const idAngles &angles );
	void					WriteObject( const idClass *obj );
	void					WriteStaticObject( const idClass &obj );
	void					WriteDict( const idDict *dict );
	void					WriteMaterial( const idMaterial *material );
	void					WriteSkin( const idDeclSkin *skin );
	void					WriteParticle( const idDeclParticle *particle );
	void					WriteFX( const idDeclFX *fx );
	void					WriteSoundShader( const idSoundShader *shader );
	void					WriteModelDef( const class idDeclModelDef *modelDef );
	void					WriteModel( const idRenderModel *model );
	void					WriteUserInterface( const idUserInterface *ui, bool unique );
	void					WriteRenderEntity( const renderEntity_t &renderEntity );
	void					WriteRenderLight( const renderLight_t &renderLight );
	void					WriteRefSound( const refSound_t &refSound );
	void					WriteRenderView( const renderView_t &view );
	void					WriteUsercmd( const usercmd_t &usercmd );
	void					WriteContactInfo( const contactInfo_t &contactInfo );
	void					WriteTrace( const trace_t &trace );
	void					WriteTraceModel( const idTraceModel &trace );
	void					WriteClipModel( const class idClipModel *clipModel );
	void					WriteSoundCommands( void );

	// HUMANHEAD pdm: additions
	void					WriteEventDef( const idEventDef *event );
	void					WriteQuat( const idQuat &vec ); // HUMANHEAD mdl
	void					WriteStringList( const idList<idStr> &list ); // HUMANHEAD mdl
	// HUMANHEAD END

	void					WriteBuildNumber( const int value );

private:
	idFile *				file;

	idList<const idClass *>	objects;
	idHashIndex				objectHash;
	int						openQ4SaveGameNextSyncId;
	bool					openQ4SaveGameSyncMarkersEnabled;

	void					WriteChecked( int bytesWritten, int expected, const char *detail, int offset );
	void					WriteSyncId( void );
	void					CallSave_r( const idTypeInfo *cls, const idClass *obj );
	void					WriteSaveGameFooter( int numObjects );
};

class idRestoreGame {
public:
							idRestoreGame( idFile *savefile );
							~idRestoreGame();

	void					CreateObjects( void );
	void					RestoreObjects( void );
	void					DeleteObjects( void );

	void					Error( const char *fmt, ... ) id_attribute((format(printf,2,3)));

	void					Read( void *buffer, int len );
	void					ReadInt( int &value );
	void					ReadJoint( jointHandle_t &value );
	void					ReadShort( short &value );
	void					ReadByte( byte &value );
	void					ReadSignedChar( signed char &value );
	void					ReadFloat( float &value );
	void					ReadBool( bool &value );
	void					ReadString( idStr &string );
	void					ReadVec2( idVec2 &vec );
	void					ReadVec3( idVec3 &vec );
	void					ReadVec4( idVec4 &vec );
	void					ReadVec6( idVec6 &vec );
	void					ReadWinding( idWinding &winding );
	void					ReadBounds( idBounds &bounds );
	void					ReadMat3( idMat3 &mat );
	void					ReadAngles( idAngles &angles );
	void					ReadObject( idClass *&obj );
	void					ReadStaticObject( idClass &obj );
	void					ReadDict( idDict *dict );
	void					ReadMaterial( const idMaterial *&material );
	void					ReadSkin( const idDeclSkin *&skin );
	void					ReadParticle( const idDeclParticle *&particle );
	void					ReadFX( const idDeclFX *&fx );
	void					ReadSoundShader( const idSoundShader *&shader );
	void					ReadModelDef( const idDeclModelDef *&modelDef );
	void					ReadModel( idRenderModel *&model );
	void					ReadUserInterface( idUserInterface *&ui );
	void					ReadRenderEntity( renderEntity_t &renderEntity );
	void					ReadRenderLight( renderLight_t &renderLight );
	void					ReadRefSound( refSound_t &refSound );
	void					ReadRenderView( renderView_t &view );
	void					ReadUsercmd( usercmd_t &usercmd );
	void					ReadContactInfo( contactInfo_t &contactInfo );
	void					ReadTrace( trace_t &trace );
	void					ReadTraceModel( idTraceModel &trace );
	void					ReadClipModel( idClipModel *&clipModel );
	void					ReadSoundCommands( void );

	// HUMANHEAD pdm: additions
	void					ReadEventDef( const idEventDef *&event );
	void					ReadQuat( idQuat &vec ); // HUMANHEAD mdl
	void					ReadStringList( idList<idStr> &list ); // HUMANHEAD mdl
	// HUMANHEAD END

	void					ReadBuildNumber( void );
	void					ReadSyncId( const char *detail = "unspecified", const char *classname = NULL );
	void					ReadSaveGameFooter( void );

	//						Used to retrieve the saved game buildNumber from within class Restore methods
	int						GetBuildNumber( void );
	bool					IsOpenQ4SaveGameCompatible( void ) const;
	const char *			GetOpenQ4SaveGameCompatibilityError( void ) const;

private:
	int						buildNumber;
	int						openQ4SaveGameCompatibilityVersion;
	int						openQ4SaveGameCompatibilitySourceFileCount;
	int						openQ4SaveGameNextSyncId;
	bool					openQ4SaveGameCompatible;
	bool					openQ4SaveGameSyncMarkersEnabled;
	idStr					openQ4SaveGameCompatibilityStamp;
	idStr					openQ4SaveGameCompatibilityError;

	idFile *				file;

	idList<idClass *>		objects;

	void					ReadChecked( void *buffer, int len, const char *detail );
	void					CallRestore_r( const idTypeInfo *cls, idClass *obj );
};

// HUMANHEAD mdl:  Savefile debugging macros

#ifdef HUMANHEAD_SAVEDEBUG

#define WRITE_SAVEDEBUG_MARKER( savefile, value ) savefile->WriteInt( value )
#define READ_SAVEDEBUG_MARKER( savefile, value ) { int tmp; savefile->ReadInt( tmp ); assert( tmp == value ); }

#else

#define WRITE_SAVEDEBUG_MARKER( savefile, value )
#define READ_SAVEDEBUG_MARKER( savefile, value )

#endif

// HUMANHEAD END

#endif /* !__SAVEGAME_H__*/
