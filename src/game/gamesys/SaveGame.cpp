// Copyright (C) 2004 Id Software, Inc.
//

#include "../../idlib/precompiled.h"
#pragma hdrstop

#include "../Game_local.h"

#include "TypeInfo.h"
#include "../../framework/BuildVersion.h" // HUMANHEAD mdl

/*
Save game related helper classes.

Save games are implemented in two classes, idSaveGame and idRestoreGame, that implement write/read functions for 
common types.  They're passed in to each entity and object for them to archive themselves.  Each class
implements save/restore functions for it's own data.  When restoring, all the objects are instantiated,
then the restore function is called on each, superclass first, then subclasses.

Pointers are restored by saving out an object index for each unique object pointer and adding them to a list of
objects that are to be saved.  Restore instantiates all the objects in the list before calling the Restore function
on each object so that the pointers returned are valid.  No object's restore function should rely on any other objects
being fully instantiated until after the restore process is complete.  Post restore fixup should be done by posting
events with 0 delay.

The savegame header will have the Game Name, Version, Map Name, and Player Persistent Info.

Changes in version make savegames incompatible, and the game will start from the beginning of the level with
the player's persistent info.

Changes to classes that don't need to break compatibilty can use the build number as the savegame version.
Later versions are responsible for restoring from previous versions by ignoring any unused data and initializing
variables that weren't in previous versions with safe information.

At the head of the save game is enough information to restore the player to the beginning of the level should the
file be unloadable in some way (for example, due to script changes).
*/

static const int MAX_SAVEGAME_OBJECTS = MAX_GENTITIES + MAX_CENTITIES + 4096;
static const int MAX_SAVEGAME_DICT_ENTRIES = 16384;
static const int MAX_SAVEGAME_STRING_CHARS = 4096;

static int SaveGame_ObjectHashKey( const idClass *obj ) {
	const size_t value = reinterpret_cast<size_t>( obj );
	return static_cast<int>( value ^ ( value >> 4 ) ^ ( value >> ( sizeof( value ) * 4 ) ) );
}

static int SaveGame_FindObjectIndex( const idList<const idClass *> &objects, const idHashIndex &objectHash, const idClass *obj ) {
	if ( obj == NULL ) {
		return 0;
	}

	const int key = SaveGame_ObjectHashKey( obj );
	for ( int index = objectHash.First( key ); index >= 0; index = objectHash.Next( index ) ) {
		if ( index < objects.Num() && objects[index] == obj ) {
			return index;
		}
	}

	return -1;
}

static bool SaveGame_IsValidRenderBounds( const idBounds &bounds ) {
	for ( int i = 0; i < 3; i++ ) {
		const float boundsMin = bounds[0][i];
		const float boundsMax = bounds[1][i];
		if ( FLOAT_IS_NAN( boundsMin ) || FLOAT_IS_NAN( boundsMax ) ) {
			return false;
		}
		if ( boundsMin > boundsMax ) {
			return false;
		}
		if ( boundsMax - boundsMin >= MAX_BOUND_SIZE ) {
			return false;
		}
	}
	return true;
}

/*
================
SaveGame_NativeWireABI

The wire-ABI stamp of this build: <os>-<compiler abi>-<architecture>-<byte
order>-raw1. Prey's game records still hold native-layout blocks (bitfields,
script storage, structures written whole), so a payload is only read back by
the build family that wrote it. The engine session derives the same name for
itself and compares it during preflight, before the running map is torn down;
if the two ever disagree on a platform, every save there fails its staged
validation instead of being written with a stamp nothing can load.
================
*/
static const char *SaveGame_NativeWireABI( void ) {
	static char stamp[64];

	if ( stamp[0] == '\0' ) {
#if defined( _WIN32 )
		const char *platform = "windows-msvcabi";
#elif defined( __APPLE__ )
		const char *platform = "macos-itaniumabi";
#elif defined( __linux__ )
		const char *platform = "linux-itaniumabi";
#else
		const char *platform = "unknownos-unknownabi";
#endif

#if defined( _M_X64 ) || defined( __x86_64__ )
		const char *architecture = "x64";
#elif defined( _M_ARM64 ) || defined( __aarch64__ )
		const char *architecture = "arm64";
#elif defined( _M_IX86 ) || defined( __i386__ )
		const char *architecture = "x86";
#elif defined( _M_ARM ) || defined( __arm__ )
		const char *architecture = "arm32";
#else
		const char *architecture = "unknownarch";
#endif

		const int one = 1;
		const bool littleEndian = *reinterpret_cast<const byte *>( &one ) == 1;

		idStr::snPrintf( stamp, sizeof( stamp ), "%s-%s-%s-raw1", platform, architecture, littleEndian ? "le" : "be" );
	}
	return stamp;
}

/*
================
idSaveGame::idSaveGame()
================
*/
idSaveGame::idSaveGame( idFile *savefile ) {

	file = savefile;
	openQ4SaveGameNextSyncId = 0;
	openQ4SaveGameSyncMarkersEnabled = false;

	// Put NULL at the start of the list so we can skip over it.
	objects.Clear();
	objects.Append( NULL );
	objectHash.Clear();
}

/*
================
idSaveGame::WriteChecked
================
*/
void idSaveGame::WriteChecked( int bytesWritten, int expected, const char *detail, int offset ) {
	if ( expected < 0 ) {
		common->Error( "idSaveGame: invalid negative write length %d while writing %s",
			expected, detail ? detail : "data" );
	}
	if ( bytesWritten != expected ) {
		common->Error( "idSaveGame: failed to write %s at offset %d (wrote %d of %d)",
			detail ? detail : "data", offset, bytesWritten, expected );
	}
}

/*
================
idSaveGame::~idSaveGame()
================
*/
idSaveGame::~idSaveGame() {
	if ( objects.Num() ) {
		Close();
	}
}

/*
================
idSaveGame::Close
================
*/
void idSaveGame::Close( void ) {
	int i;
	const int numObjects = objects.Num() - 1;

	WriteSoundCommands();

	// read trace models
	idClipModel::SaveTraceModels( this );

	for( i = 1; i < objects.Num(); i++ ) {
		WriteSyncId();
		CallSave_r( objects[ i ]->GetType(), objects[ i ] );
		WRITE_SAVEDEBUG_MARKER( this, 0xD00F00AA ); // HUMANHEAD mdl
	}

	WriteSaveGameFooter( numObjects );

	objects.Clear();
	objectHash.Clear();

#ifdef ID_DEBUG_MEMORY
	idStr gameState = file->GetName();
	gameState.StripFileExtension();
	WriteGameState_f( idCmdArgs( va( "test %s_save", gameState.c_str() ), false ) );
#endif
}

/*
================
idSaveGame::WriteObjectList
================
*/
void idSaveGame::WriteObjectList( void ) {
	int i;

	if ( objects.Num() - 1 > MAX_SAVEGAME_OBJECTS ) {
		common->Error( "idSaveGame::WriteObjectList: invalid object count %d (max %d)", objects.Num() - 1, MAX_SAVEGAME_OBJECTS );
	}
	WriteInt( objects.Num() - 1 );
	for( i = 1; i < objects.Num(); i++ ) {
		if ( objects[ i ] == NULL ) {
			common->Error( "idSaveGame::WriteObjectList: NULL object at index %d", i );
		}
		WriteString( objects[ i ]->GetClassname() );
	}
}

/*
================
idSaveGame::CallSave_r
================
*/
void idSaveGame::CallSave_r( const idTypeInfo *cls, const idClass *obj ) {
	if ( cls->super ) {
		CallSave_r( cls->super, obj );
		if ( cls->super->Save == cls->Save ) {
			// don't call save on this inheritance level since the function was called in the super class
			return;
		}
	}
	
	WriteSyncId();
	WRITE_SAVEDEBUG_MARKER( this, 0xD00F00BB ); // HUMANHEAD mdl
	( obj->*cls->Save )( this );
	WRITE_SAVEDEBUG_MARKER( this, 0xD00F00CC ); // HUMANHEAD mdl
	WriteSyncId();
}

/*
================
idSaveGame::AddObject
================
*/
void idSaveGame::AddObject( const idClass *obj ) {
	if ( obj == NULL || SaveGame_FindObjectIndex( objects, objectHash, obj ) >= 0 ) {
		return;
	}
	const int index = objects.Append( obj );
	objectHash.Add( SaveGame_ObjectHashKey( obj ), index );
	if ( objects.Num() - 1 > MAX_SAVEGAME_OBJECTS ) {
		common->Error( "idSaveGame::AddObject: too many savegame objects (%d, max %d)", objects.Num() - 1, MAX_SAVEGAME_OBJECTS );
	}
}

/*
================
idSaveGame::WriteSyncId
================
*/
void idSaveGame::WriteSyncId( void ) {
	if ( !openQ4SaveGameSyncMarkersEnabled ) {
		return;
	}

	WriteInt( OPENQ4_SAVEGAME_SYNC_MAGIC );
	WriteInt( openQ4SaveGameNextSyncId++ );
}

/*
================
idSaveGame::Write
================
*/
void idSaveGame::Write( const void *buffer, int len ) {
	if ( len < 0 ) {
		common->Error( "idSaveGame::Write: invalid negative write length %d", len );
	}
	if ( len == 0 ) {
		return;
	}
	if ( buffer == NULL ) {
		common->Error( "idSaveGame::Write: null source for %d byte write", len );
	}
	const int offset = file->Tell();
	WriteChecked( file->Write( buffer, len ), len, "raw data", offset );
}

/*
================
idSaveGame::WriteInt
================
*/
void idSaveGame::WriteInt( const int value ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteInt( value ), static_cast<int>( sizeof( value ) ), "int", offset );
}

/*
================
idSaveGame::WriteJoint
================
*/
void idSaveGame::WriteJoint( const jointHandle_t value ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteInt( value ), static_cast<int>( sizeof( int ) ), "joint", offset );
}

/*
================
idSaveGame::WriteShort
================
*/
void idSaveGame::WriteShort( const short value ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteShort( value ), static_cast<int>( sizeof( value ) ), "short", offset );
}

/*
================
idSaveGame::WriteByte
================
*/
void idSaveGame::WriteByte( const byte value ) {
	const int offset = file->Tell();
	WriteChecked( file->Write( &value, sizeof( value ) ), static_cast<int>( sizeof( value ) ), "byte", offset );
}

/*
================
idSaveGame::WriteSignedChar
================
*/
void idSaveGame::WriteSignedChar( const signed char value ) {
	const int offset = file->Tell();
	WriteChecked( file->Write( &value, sizeof( value ) ), static_cast<int>( sizeof( value ) ), "signed char", offset );
}

/*
================
idSaveGame::WriteFloat
================
*/
void idSaveGame::WriteFloat( const float value ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteFloat( value ), static_cast<int>( sizeof( value ) ), "float", offset );
}

/*
================
idSaveGame::WriteBool
================
*/
void idSaveGame::WriteBool( const bool value ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteBool( value ), static_cast<int>( sizeof( byte ) ), "bool", offset );
}

/*
================
idSaveGame::WriteString
================
*/  
void idSaveGame::WriteString( const char *string ) {
	int len;

	if ( string == NULL ) {
		string = "";
	}
	len = strlen( string );
	if ( len < 0 || len >= MAX_SAVEGAME_STRING_CHARS ) {
		common->Error( "idSaveGame::WriteString invalid string length (%d)", len );
	}
	WriteInt( len );
	if ( len > 0 ) {
		const int offset = file->Tell();
		WriteChecked( file->Write( string, len ), len, "string", offset );
	}
}

/*
================
idSaveGame::WriteVec2
================
*/
void idSaveGame::WriteVec2( const idVec2 &vec ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteVec2( vec ), static_cast<int>( sizeof( vec ) ), "vec2", offset );
}

/*
================
idSaveGame::WriteVec3
================
*/
void idSaveGame::WriteVec3( const idVec3 &vec ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteVec3( vec ), static_cast<int>( sizeof( vec ) ), "vec3", offset );
}

/*
================
idSaveGame::WriteVec4
================
*/
void idSaveGame::WriteVec4( const idVec4 &vec ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteVec4( vec ), static_cast<int>( sizeof( vec ) ), "vec4", offset );
}

/*
================
idSaveGame::WriteVec6
================
*/
void idSaveGame::WriteVec6( const idVec6 &vec ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteVec6( vec ), static_cast<int>( sizeof( vec ) ), "vec6", offset );
}

/*
================
idSaveGame::WriteBounds
================
*/
void idSaveGame::WriteBounds( const idBounds &bounds ) {
	idBounds b = bounds;
	LittleRevBytes( &b, sizeof(float), sizeof(b)/sizeof(float) );
	const int offset = file->Tell();
	WriteChecked( file->Write( &b, sizeof( b ) ), static_cast<int>( sizeof( b ) ), "bounds", offset );
}

/*
================
idSaveGame::WriteBounds
================
*/
void idSaveGame::WriteWinding( const idWinding &w )
{
	int i, num;
	num = w.GetNumPoints();
	if ( num < 0 || num > MAX_POINTS_ON_WINDING ) {
		common->Error( "idSaveGame::WriteWinding: invalid point count %d", num );
	}
	WriteInt( num );
	for ( i = 0; i < num; i++ ) {
		idVec5 v = w[i];
		LittleRevBytes(&v, sizeof(float), sizeof(v)/sizeof(float) );
		const int offset = file->Tell();
		WriteChecked( file->Write( &v, sizeof( v ) ), static_cast<int>( sizeof( v ) ), "winding point", offset );
	}
}


/*
================
idSaveGame::WriteMat3
================
*/
void idSaveGame::WriteMat3( const idMat3 &mat ) {
	const int offset = file->Tell();
	WriteChecked( file->WriteMat3( mat ), static_cast<int>( sizeof( mat ) ), "mat3", offset );
}

/*
================
idSaveGame::WriteAngles
================
*/
void idSaveGame::WriteAngles( const idAngles &angles ) {
	idAngles v = angles;
	LittleRevBytes(&v, sizeof(float), sizeof(v)/sizeof(float) );
	const int offset = file->Tell();
	WriteChecked( file->Write( &v, sizeof( v ) ), static_cast<int>( sizeof( v ) ), "angles", offset );
}

/*
================
idSaveGame::WriteObject
================
*/
void idSaveGame::WriteObject( const idClass *obj ) {
	int index;

	index = SaveGame_FindObjectIndex( objects, objectHash, obj );
	if ( index < 0 ) {
		gameLocal.DPrintf( "idSaveGame::WriteObject - WriteObject FindIndex failed\n" );

		// Use the NULL index
		index = 0;
	}

	WriteInt( index );
}

/*
================
idSaveGame::WriteStaticObject
================
*/
void idSaveGame::WriteStaticObject( const idClass &obj ) {
	CallSave_r( obj.GetType(), &obj );
}

/*
================
idSaveGame::WriteDict
================
*/
void idSaveGame::WriteDict( const idDict *dict ) {
	int num;
	int i;
	const idKeyValue *kv;

	if ( !dict ) {
		WriteInt( -1 );
	} else {
		num = dict->GetNumKeyVals();
		if ( num < 0 || num > MAX_SAVEGAME_DICT_ENTRIES ) {
			common->Error( "idSaveGame::WriteDict: invalid key/value count %d (max %d)", num, MAX_SAVEGAME_DICT_ENTRIES );
		}
		WriteInt( num );
		for( i = 0; i < num; i++ ) {
			kv = dict->GetKeyVal( i );
			WriteString( kv->GetKey() );
			WriteString( kv->GetValue() );
		}
	}
}

/*
================
idSaveGame::WriteMaterial
================
*/
void idSaveGame::WriteMaterial( const idMaterial *material ) {
	if ( !material ) {
		WriteString( "" );
	} else {
		WriteString( material->GetName() );
	}
}

/*
================
idSaveGame::WriteSkin
================
*/
void idSaveGame::WriteSkin( const idDeclSkin *skin ) {
	if ( !skin ) {
		WriteString( "" );
	} else {
		WriteString( skin->GetName() );
	}
}

/*
================
idSaveGame::WriteParticle
================
*/
void idSaveGame::WriteParticle( const idDeclParticle *particle ) {
	if ( !particle ) {
		WriteString( "" );
	} else {
		WriteString( particle->GetName() );
	}
}

/*
================
idSaveGame::WriteFX
================
*/
void idSaveGame::WriteFX( const idDeclFX *fx ) {
	if ( !fx ) {
		WriteString( "" );
	} else {
		WriteString( fx->GetName() );
	}
}

/*
================
idSaveGame::WriteModelDef
================
*/
void idSaveGame::WriteModelDef( const idDeclModelDef *modelDef ) {
	if ( !modelDef ) {
		WriteString( "" );
	} else {
		WriteString( modelDef->GetName() );
	}
}

/*
================
idSaveGame::WriteSoundShader
================
*/
void idSaveGame::WriteSoundShader( const idSoundShader *shader ) {
	const char *name;

	if ( !shader ) {
		WriteString( "" );
	} else {
		name = shader->GetName();
		WriteString( name );
	}
}

/*
================
idSaveGame::WriteModel
================
*/
void idSaveGame::WriteModel( const idRenderModel *model ) {
	const char *name;

	if ( !model ) {
		WriteString( "" );
	} else {
		name = model->Name();
		WriteString( name );
	}
}

/*
================
idSaveGame::WriteUserInterface
================
*/
void idSaveGame::WriteUserInterface( const idUserInterface *ui, bool unique ) {
	const char *name;

	if ( !ui ) {
		WriteString( "" );
	} else {
		name = ui->Name();
		WriteString( name );
		WriteBool( unique );
		if ( ui->WriteToSaveGame( file ) == false ) {
			gameLocal.Error( "idSaveGame::WriteUserInterface: ui failed to write properly\n" );
		}
	}
}

/*
================
idSaveGame::WriteRenderEntity
================
*/
void idSaveGame::WriteRenderEntity( const renderEntity_t &renderEntity ) {
	int i;

	WriteModel( renderEntity.hModel );

	WriteInt( renderEntity.entityNum );
	WriteInt( renderEntity.bodyId );

	WriteBounds( renderEntity.bounds );

	// callback is set by class's Restore function

	WriteInt( renderEntity.suppressSurfaceInViewID );
	WriteInt( renderEntity.suppressShadowInViewID );
	WriteInt( renderEntity.suppressShadowInLightID );
	WriteInt( renderEntity.allowSurfaceInViewID );

	WriteVec3( renderEntity.origin );
	WriteMat3( renderEntity.axis );

	WriteMaterial( renderEntity.customShader );
	WriteMaterial( renderEntity.referenceShader );
	WriteSkin( renderEntity.customSkin );

	if ( renderEntity.referenceSound != NULL ) {
		WriteInt( renderEntity.referenceSound->Index() );
	} else {
		WriteInt( 0 );
	}

	for( i = 0; i < MAX_ENTITY_SHADER_PARMS; i++ ) {
		WriteFloat( renderEntity.shaderParms[ i ] );
	}

	for( i = 0; i < MAX_RENDERENTITY_GUI; i++ ) {
		WriteUserInterface( renderEntity.gui[ i ], renderEntity.gui[ i ] ? renderEntity.gui[ i ]->IsUniqued() : false );
	}

	WriteFloat( renderEntity.modelDepthHack );

	WriteBool( renderEntity.noSelfShadow );
	WriteBool( renderEntity.noShadow );
	WriteBool( renderEntity.noDynamicInteractions );
	WriteBool( renderEntity.weaponDepthHack );

	WriteBool( renderEntity.forceUpdate );

	// HUMANHEAD mdl
	if( renderEntity.declBeam ) {
		WriteBool( true );
		WriteString( renderEntity.declBeam->GetName() );
	} else {
		WriteBool( false );
	}

	if( renderEntity.beamNodes ) {
		WriteBool( true );
		for( i = 0; i < MAX_BEAM_NODES; i++ ) {
			WriteVec3( renderEntity.beamNodes->nodes[i] );
		}
	} else {
		WriteBool( false );
	}

	WriteBool( renderEntity.onlyVisibleInSpirit );
	WriteBool( renderEntity.onlyInvisibleInSpirit );
	WriteBool( renderEntity.lowSkippable );		//HUMANHEAD bjk
	WriteFloat( renderEntity.eyeDistance );
	// HUMANHEAD END
}

/*
================
idSaveGame::WriteRenderLight
================
*/
void idSaveGame::WriteRenderLight( const renderLight_t &renderLight ) {
	int i;

	WriteMat3( renderLight.axis );
	WriteVec3( renderLight.origin );

	WriteInt( renderLight.suppressLightInViewID );
	WriteInt( renderLight.allowLightInViewID );
	WriteBool( renderLight.noShadows );
	WriteBool( renderLight.noSpecular );
	WriteBool( renderLight.lowSkippable );		//HUMANHEAD bjk
	WriteBool( renderLight.pointLight );
	WriteBool( renderLight.parallel );

	WriteVec3( renderLight.lightRadius );
	WriteVec3( renderLight.lightCenter );

	WriteVec3( renderLight.target );
	WriteVec3( renderLight.right );
	WriteVec3( renderLight.up );
	WriteVec3( renderLight.start );
	WriteVec3( renderLight.end );

	// only idLight has a prelightModel and it's always based on the entityname, so we'll restore it there
	// WriteModel( renderLight.prelightModel );

	WriteInt( renderLight.lightId );

	WriteMaterial( renderLight.shader );

	for( i = 0; i < MAX_ENTITY_SHADER_PARMS; i++ ) {
		WriteFloat( renderLight.shaderParms[ i ] );
	}

	if ( renderLight.referenceSound != NULL ) {
		WriteInt( renderLight.referenceSound->Index() );
	} else {
		WriteInt( 0 );
	}
}

/*
================
idSaveGame::WriteRefSound
================
*/
void idSaveGame::WriteRefSound( const refSound_t &refSound ) {
	if ( refSound.referenceSound ) {
		WriteInt( refSound.referenceSound->Index() );
	} else {
		WriteInt( 0 );
	}
	WriteVec3( refSound.origin );
	WriteInt( refSound.listenerId );
	WriteSoundShader( refSound.shader );
	WriteFloat( refSound.diversity );
	WriteBool( refSound.waitfortrigger );

	WriteFloat( refSound.parms.minDistance );
	WriteFloat( refSound.parms.maxDistance );
	WriteFloat( refSound.parms.volume );
	WriteFloat( refSound.parms.shakes );
	WriteInt( refSound.parms.soundShaderFlags );
	WriteInt( refSound.parms.soundClass );
	WriteInt( refSound.parms.subIndex );
	WriteInt( refSound.parms.profanityIndex );
	WriteFloat( refSound.parms.profanityDelay );
	WriteFloat( refSound.parms.profanityDuration );
}

/*
================
idSaveGame::WriteRenderView
================
*/
void idSaveGame::WriteRenderView( const renderView_t &view ) {
	int i;

	WriteInt( view.viewID );
	WriteInt( view.x );
	WriteInt( view.y );
	WriteInt( view.width );
	WriteInt( view.height );

	WriteFloat( view.fov_x );
	WriteFloat( view.fov_y );
	WriteVec3( view.vieworg );
	WriteMat3( view.viewaxis );

	WriteBool( view.cramZNear );
	// HUMANHEAD mdl
	WriteBool( view.forceUpdate );
	WriteBool( view.viewSpiritEntities );
	// HUMANHEAD END

	WriteInt( view.time );

	for( i = 0; i < MAX_GLOBAL_SHADER_PARMS; i++ ) {
		WriteFloat( view.shaderParms[ i ] );
	}
}

/*
===================
idSaveGame::WriteUsercmd
===================
*/
void idSaveGame::WriteUsercmd( const usercmd_t &usercmd ) {
	WriteInt( usercmd.gameFrame );
	WriteInt( usercmd.gameTime );
	WriteInt( usercmd.duplicateCount );
	WriteShort( usercmd.buttons );
	WriteSignedChar( usercmd.forwardmove );
	WriteSignedChar( usercmd.rightmove );
	WriteSignedChar( usercmd.upmove );
	WriteShort( usercmd.angles[0] );
	WriteShort( usercmd.angles[1] );
	WriteShort( usercmd.angles[2] );
	WriteShort( usercmd.mx );
	WriteShort( usercmd.my );
	WriteSignedChar( usercmd.impulse );
	WriteByte( usercmd.flags );
	WriteInt( usercmd.sequence );
}

/*
===================
idSaveGame::WriteContactInfo
===================
*/
void idSaveGame::WriteContactInfo( const contactInfo_t &contactInfo ) {
	WriteInt( (int)contactInfo.type );
	WriteVec3( contactInfo.point );
	WriteVec3( contactInfo.normal );
	WriteFloat( contactInfo.dist );
	WriteInt( contactInfo.contents );
	WriteMaterial( contactInfo.material );
	WriteInt( contactInfo.modelFeature );
	WriteInt( contactInfo.trmFeature );
	WriteInt( contactInfo.entityNum );
	WriteInt( contactInfo.id );
}

/*
===================
idSaveGame::WriteTrace
===================
*/
void idSaveGame::WriteTrace( const trace_t &trace ) {
	WriteFloat( trace.fraction );
	WriteVec3( trace.endpos );
	WriteMat3( trace.endAxis );
	WriteContactInfo( trace.c );
}

/*
 ===================
 idRestoreGame::WriteTraceModel
 ===================
 */
void idSaveGame::WriteTraceModel( const idTraceModel &trace ) {
	int j, k;
	
	WriteInt( (int&)trace.type );
	WriteInt( trace.numVerts );
	for ( j = 0; j < MAX_TRACEMODEL_VERTS; j++ ) {
		WriteVec3( trace.verts[j] );
	}
	WriteInt( trace.numEdges );
	for ( j = 0; j < (MAX_TRACEMODEL_EDGES+1); j++ ) {
		WriteInt( trace.edges[j].v[0] );
		WriteInt( trace.edges[j].v[1] );
		WriteVec3( trace.edges[j].normal );
	}
	WriteInt( trace.numPolys );
	for ( j = 0; j < MAX_TRACEMODEL_POLYS; j++ ) {
		WriteVec3( trace.polys[j].normal );
		WriteFloat( trace.polys[j].dist );
		WriteBounds( trace.polys[j].bounds );
		WriteInt( trace.polys[j].numEdges );
		for ( k = 0; k < MAX_TRACEMODEL_POLYEDGES; k++ ) {
			WriteInt( trace.polys[j].edges[k] );
		}
	}
	WriteVec3( trace.offset );
	WriteBounds( trace.bounds );
	WriteBool( trace.isConvex );
	// padding win32 native structs
	char tmp[3];
	memset( tmp, 0, sizeof( tmp ) );
	file->Write( tmp, 3 );
}

/*
===================
idSaveGame::WriteClipModel
===================
*/
void idSaveGame::WriteClipModel( const idClipModel *clipModel ) {
	if ( clipModel != NULL ) {
		WriteBool( true );
		clipModel->Save( this );
	} else {
		WriteBool( false );
	}
}

/*
===================
idSaveGame::WriteSoundCommands
===================
*/
void idSaveGame::WriteSoundCommands( void ) {
	gameSoundWorld->WriteToSaveGame( file );
}

/*
======================
idSaveGame::WriteBuildNumber
======================
*/
void idSaveGame::WriteBuildNumber( const int value ) {
	openQ4SaveGameSyncMarkersEnabled = true;
	openQ4SaveGameNextSyncId = 0;

	WriteInt( OPENQ4_SAVEGAME_COMPATIBILITY_MAGIC );
	WriteInt( OPENQ4_SAVEGAME_COMPATIBILITY_VERSION );
	WriteInt( value );
	WriteString( OPENQ4_SAVEGAME_COMPAT_SOURCE_HASH );
	WriteInt( OPENQ4_SAVEGAME_COMPAT_SOURCE_FILE_COUNT );
	WriteString( SaveGame_NativeWireABI() );
}

/*
======================
idSaveGame::WriteSaveGameFooter
======================
*/
void idSaveGame::WriteSaveGameFooter( int numObjects ) {
	if ( !openQ4SaveGameSyncMarkersEnabled ) {
		return;
	}

	const int footerOffset = file->Tell();
	WriteInt( OPENQ4_SAVEGAME_FOOTER_MAGIC );
	WriteInt( OPENQ4_SAVEGAME_FOOTER_VERSION );
	WriteInt( footerOffset );
	WriteInt( numObjects );
	WriteInt( openQ4SaveGameNextSyncId );
}

/***********************************************************************

	idRestoreGame
	
***********************************************************************/

/*
================
idRestoreGame::RestoreGame
================
*/
idRestoreGame::idRestoreGame( idFile *savefile ) {
	file = savefile;
	buildNumber = 0;
	openQ4SaveGameCompatibilityVersion = 0;
	openQ4SaveGameCompatibilitySourceFileCount = 0;
	openQ4SaveGameNextSyncId = 0;
	openQ4SaveGameCompatible = false;
	openQ4SaveGameSyncMarkersEnabled = false;
	openQ4SaveGameCompatibilityStamp.Clear();
	openQ4SaveGameCompatibilityError = "savegame compatibility header has not been read";
}

/*
================
idRestoreGame::~idRestoreGame()
================
*/
idRestoreGame::~idRestoreGame() {
}

/*
================
idRestoreGame::ReadChecked
================
*/
void idRestoreGame::ReadChecked( void *buffer, int len, const char *detail ) {
	if ( len < 0 ) {
		Error( "idRestoreGame: invalid negative read length %d while reading %s", len, detail ? detail : "data" );
	}
	if ( len == 0 ) {
		return;
	}
	if ( buffer == NULL ) {
		Error( "idRestoreGame: null destination while reading %s", detail ? detail : "data" );
	}
	const int offset = file->Tell();
	const int bytesRead = file->Read( buffer, len );
	if ( bytesRead != len ) {
		Error( "idRestoreGame: unexpected end of savegame while reading %s at offset %d (read %d of %d)",
			detail ? detail : "data", offset, bytesRead, len );
	}
}

/*
================
void idRestoreGame::CreateObjects
================
*/
void idRestoreGame::CreateObjects( void ) {
	int i, num;
	idStr classname;
	idTypeInfo *type;

	ReadInt( num );
	if ( num < 0 || num > MAX_SAVEGAME_OBJECTS ) {
		Error( "idRestoreGame::CreateObjects: invalid object count %d at offset %d", num, file->Tell() );
	}

	// create all the objects
	objects.SetNum( num + 1 );
	memset( objects.Ptr(), 0, sizeof( objects[ 0 ] ) * objects.Num() );

	for( i = 1; i < objects.Num(); i++ ) {
		ReadString( classname );
		if ( classname.IsEmpty() ) {
			Error( "idRestoreGame::CreateObjects: empty class name for object %d", i );
		}
		type = idClass::GetClass( classname );
		if ( !type ) {
			Error( "idRestoreGame::CreateObjects: Unknown class '%s'", classname.c_str() );
		}
		objects[ i ] = type->CreateInstance();
		if ( objects[ i ] == NULL ) {
			Error( "idRestoreGame::CreateObjects: failed to create class '%s'", classname.c_str() );
		}

#ifdef ID_DEBUG_MEMORY
		InitTypeVariables( objects[i], type->classname, 0xce );
#endif
	}
}

/*
================
void idRestoreGame::RestoreObjects
================
*/
void idRestoreGame::RestoreObjects( void ) {
	int i;

	ReadSoundCommands();

	// read trace models
	idClipModel::RestoreTraceModels( this );

	// restore all the objects
	for( i = 1; i < objects.Num(); i++ ) {
		ReadSyncId( "Restore objects", objects[ i ]->GetClassname() );
		CallRestore_r( objects[ i ]->GetType(), objects[ i ] );
		READ_SAVEDEBUG_MARKER( this, 0xD00F00AA ); // HUMANHEAD mdl
	}

	ReadSaveGameFooter();

	// regenerate render entities and render lights because are not saved
	for( i = 1; i < objects.Num(); i++ ) {
		if ( objects[ i ]->IsType( idEntity::Type ) ) {
			idEntity *ent = static_cast<idEntity *>( objects[ i ] );
			ent->UpdateVisuals();
			ent->Present();
		}
	}

#ifdef ID_DEBUG_MEMORY
	idStr gameState = file->GetName();
	gameState.StripFileExtension();
	WriteGameState_f( idCmdArgs( va( "test %s_restore", gameState.c_str() ), false ) );
	//CompareGameState_f( idCmdArgs( va( "test %s_save", gameState.c_str() ) ) );
	gameLocal.Error( "dumped game states" );
#endif
}

/*
====================
void idRestoreGame::DeleteObjects
====================
*/
void idRestoreGame::DeleteObjects( void ) {

	// Remove the NULL object before deleting
	objects.RemoveIndex( 0 );

	objects.DeleteContents( true );
}

/*
================
idRestoreGame::Error
================
*/
void idRestoreGame::Error( const char *fmt, ... ) {
	va_list	argptr;
	char	text[ 1024 ];

	va_start( argptr, fmt );
	idStr::vsnPrintf( text, sizeof( text ), fmt, argptr );
	va_end( argptr );
	text[ sizeof( text ) - 1 ] = '\0';

	gameLocal.Error( "%s", text );
}

/*
================
idRestoreGame::CallRestore_r
================
*/
void idRestoreGame::CallRestore_r( const idTypeInfo *cls, idClass *obj ) {
	if ( cls->super ) {
		CallRestore_r( cls->super, obj );
		if ( cls->super->Restore == cls->Restore ) {
			// don't call save on this inheritance level since the function was called in the super class
			return;
		}
	}
	
	ReadSyncId( "CallRestore_r start", cls->classname );
	READ_SAVEDEBUG_MARKER( this, 0xD00F00BB ); // HUMANHEAD mdl

	( obj->*cls->Restore )( this );

	READ_SAVEDEBUG_MARKER( this, 0xD00F00CC ); // HUMANHEAD mdl
	ReadSyncId( "CallRestore_r end", cls->classname );
}

/*
================
idRestoreGame::ReadSyncId
================
*/
void idRestoreGame::ReadSyncId( const char *detail, const char *classname ) {
	if ( !openQ4SaveGameSyncMarkersEnabled ) {
		return;
	}

	const int offset = file->Tell();
	int marker;
	int syncId;
	ReadInt( marker );
	ReadInt( syncId );

	if ( marker != OPENQ4_SAVEGAME_SYNC_MAGIC ) {
		Error( "idRestoreGame::ReadSyncId: marker mismatch while reading %s%s%s at offset %d (got 0x%08x, expected 0x%08x)",
			detail ? detail : "data", classname ? " for " : "", classname ? classname : "", offset, marker, OPENQ4_SAVEGAME_SYNC_MAGIC );
	}
	if ( syncId != openQ4SaveGameNextSyncId ) {
		Error( "idRestoreGame::ReadSyncId: sequence mismatch while reading %s%s%s at offset %d (got %d, expected %d)",
			detail ? detail : "data", classname ? " for " : "", classname ? classname : "", offset, syncId, openQ4SaveGameNextSyncId );
	}

	openQ4SaveGameNextSyncId++;
}

/*
================
idRestoreGame::Read
================
*/
void idRestoreGame::Read( void *buffer, int len ) {
	ReadChecked( buffer, len, "raw data" );
}

/*
================
idRestoreGame::ReadInt
================
*/
void idRestoreGame::ReadInt( int &value ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadInt( value );
	if ( bytesRead != sizeof( value ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading int at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( value ) ) );
	}
}

/*
================
idRestoreGame::ReadJoint
================
*/
void idRestoreGame::ReadJoint( jointHandle_t &value ) {
	int joint;
	ReadInt( joint );
	value = static_cast<jointHandle_t>( joint );
}

/*
================
idRestoreGame::ReadShort
================
*/
void idRestoreGame::ReadShort( short &value ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadShort( value );
	if ( bytesRead != sizeof( value ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading short at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( value ) ) );
	}
}

/*
================
idRestoreGame::ReadByte
================
*/
void idRestoreGame::ReadByte( byte &value ) {
	ReadChecked( &value, sizeof( value ), "byte" );
}

/*
================
idRestoreGame::ReadSignedChar
================
*/
void idRestoreGame::ReadSignedChar( signed char &value ) {
	ReadChecked( &value, sizeof( value ), "signed char" );
}

/*
================
idRestoreGame::ReadFloat
================
*/
void idRestoreGame::ReadFloat( float &value ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadFloat( value );
	if ( bytesRead != sizeof( value ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading float at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( value ) ) );
	}
}

/*
================
idRestoreGame::ReadBool
================
*/
void idRestoreGame::ReadBool( bool &value ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadBool( value );
	if ( bytesRead != sizeof( byte ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading bool at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( byte ) ) );
	}
}

/*
================
idRestoreGame::ReadString
================
*/
void idRestoreGame::ReadString( idStr &string ) {
	int len;

	ReadInt( len );
	if ( len < 0 || len >= MAX_SAVEGAME_STRING_CHARS ) {
		Error( "idRestoreGame::ReadString: invalid length (%d)", len );
	}

	const int stringOffset = file->Tell();
	const int fileLength = file->Length();
	if ( fileLength > 0 && stringOffset >= 0 && len > fileLength - stringOffset ) {
		Error( "idRestoreGame::ReadString: length %d exceeds remaining savegame bytes %d at offset %d",
			len, fileLength - stringOffset, stringOffset );
	}

	string.Fill( ' ', len );
	if ( len > 0 ) {
		ReadChecked( &string[0], len, "string" );
	}
}

/*
================
idRestoreGame::ReadVec2
================
*/
void idRestoreGame::ReadVec2( idVec2 &vec ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadVec2( vec );
	if ( bytesRead != sizeof( vec ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading vec2 at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( vec ) ) );
	}
}

/*
================
idRestoreGame::ReadVec3
================
*/
void idRestoreGame::ReadVec3( idVec3 &vec ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadVec3( vec );
	if ( bytesRead != sizeof( vec ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading vec3 at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( vec ) ) );
	}
}

/*
================
idRestoreGame::ReadVec4
================
*/
void idRestoreGame::ReadVec4( idVec4 &vec ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadVec4( vec );
	if ( bytesRead != sizeof( vec ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading vec4 at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( vec ) ) );
	}
}

/*
================
idRestoreGame::ReadVec6
================
*/
void idRestoreGame::ReadVec6( idVec6 &vec ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadVec6( vec );
	if ( bytesRead != sizeof( vec ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading vec6 at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( vec ) ) );
	}
}

/*
================
idRestoreGame::ReadBounds
================
*/
void idRestoreGame::ReadBounds( idBounds &bounds ) {
	ReadChecked( &bounds, sizeof( bounds ), "bounds" );
	LittleRevBytes( &bounds, sizeof(float), sizeof(bounds)/sizeof(float) );
}

/*
================
idRestoreGame::ReadWinding
================
*/
void idRestoreGame::ReadWinding( idWinding &w )
{
	int i, num;
	ReadInt( num );
	if ( num < 0 || num > MAX_POINTS_ON_WINDING ) {
		Error( "idRestoreGame::ReadWinding: invalid point count %d", num );
	}
	w.SetNumPoints( num );
	for ( i = 0; i < num; i++ ) {
		ReadChecked( &w[i], sizeof( idVec5 ), "winding point" );
		LittleRevBytes(&w[i], sizeof(float), sizeof(idVec5)/sizeof(float) );
	}
}

/*
================
idRestoreGame::ReadMat3
================
*/
void idRestoreGame::ReadMat3( idMat3 &mat ) {
	const int offset = file->Tell();
	const int bytesRead = file->ReadMat3( mat );
	if ( bytesRead != sizeof( mat ) ) {
		Error( "idRestoreGame: unexpected end of savegame while reading mat3 at offset %d (read %d of %d)",
			offset, bytesRead, static_cast<int>( sizeof( mat ) ) );
	}
}

/*
================
idRestoreGame::ReadAngles
================
*/
void idRestoreGame::ReadAngles( idAngles &angles ) {
	ReadChecked( &angles, sizeof( angles ), "angles" );
	LittleRevBytes(&angles, sizeof(float), sizeof(idAngles)/sizeof(float) );
}

/*
================
idRestoreGame::ReadObject
================
*/
void idRestoreGame::ReadObject( idClass *&obj ) {
	int index;

	ReadInt( index );
	if ( ( index < 0 ) || ( index >= objects.Num() ) ) {
		Error( "idRestoreGame::ReadObject: invalid object index" );
	}
	obj = objects[ index ];
}

/*
================
idRestoreGame::ReadStaticObject
================
*/
void idRestoreGame::ReadStaticObject( idClass &obj ) {
	CallRestore_r( obj.GetType(), &obj );
}

/*
================
idRestoreGame::ReadDict
================
*/
void idRestoreGame::ReadDict( idDict *dict ) {
	int num;
	int i;
	idStr key;
	idStr value;

	ReadInt( num );

	if ( num < 0 ) {
		dict = NULL;
	} else {
		if ( num > MAX_SAVEGAME_DICT_ENTRIES ) {
			Error( "idRestoreGame::ReadDict: invalid key/value count %d (max %d)", num, MAX_SAVEGAME_DICT_ENTRIES );
		}
		dict->Clear();
		for( i = 0; i < num; i++ ) {
			ReadString( key );
			ReadString( value );
			dict->Set( key, value );
		}
	}
}

/*
================
idRestoreGame::ReadMaterial
================
*/
void idRestoreGame::ReadMaterial( const idMaterial *&material ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		material = NULL;
	} else {
		material = declManager->FindMaterial( name );
	}
}

/*
================
idRestoreGame::ReadSkin
================
*/
void idRestoreGame::ReadSkin( const idDeclSkin *&skin ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		skin = NULL;
	} else {
		skin = declManager->FindSkin( name );
	}
}

/*
================
idRestoreGame::ReadParticle
================
*/
void idRestoreGame::ReadParticle( const idDeclParticle *&particle ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		particle = NULL;
	} else {
		particle = static_cast<const idDeclParticle *>( declManager->FindType( DECL_PARTICLE, name ) );
	}
}

/*
================
idRestoreGame::ReadFX
================
*/
void idRestoreGame::ReadFX( const idDeclFX *&fx ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		fx = NULL;
	} else {
		fx = static_cast<const idDeclFX *>( declManager->FindType( DECL_FX, name ) );
	}
}

/*
================
idRestoreGame::ReadSoundShader
================
*/
void idRestoreGame::ReadSoundShader( const idSoundShader *&shader ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		shader = NULL;
	} else {
		shader = declManager->FindSound( name );
	}
}

/*
================
idRestoreGame::ReadModelDef
================
*/
void idRestoreGame::ReadModelDef( const idDeclModelDef *&modelDef ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		modelDef = NULL;
	} else {
		modelDef = static_cast<const idDeclModelDef *>( declManager->FindType( DECL_MODELDEF, name, false ) );
	}
}

/*
================
idRestoreGame::ReadModel
================
*/
void idRestoreGame::ReadModel( idRenderModel *&model ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		model = NULL;
	} else {
		model = renderModelManager->FindModel( name );
	}
}

/*
================
idRestoreGame::ReadUserInterface
================
*/
void idRestoreGame::ReadUserInterface( idUserInterface *&ui ) {
	idStr name;

	ReadString( name );
	if ( !name.Length() ) {
		ui = NULL;
	} else {
		bool unique;
		ReadBool( unique );
		ui = uiManager->FindGui( name, true, unique );
		if ( ui ) {
			if ( ui->ReadFromSaveGame( file ) == false ) {
				Error( "idSaveGame::ReadUserInterface: ui failed to read properly\n" );
			} else {
				ui->StateChanged( gameLocal.time );
			}
		}
	}
}

/*
================
idRestoreGame::ReadRenderEntity
================
*/
void idRestoreGame::ReadRenderEntity( renderEntity_t &renderEntity ) {
	int i;
	int index;

	// Fields the save does not carry (suppressSurfaceMask, overlayShader,
	// referenceSoundHandle, weaponDepthHackInViewID, the LOD, outline and
	// flat-diffuse parms) must restore to the zero state construction gives
	// them. Callers such as the inlined static render entities and FX actions
	// read into storage that was never cleared.
	renderEntity = renderEntity_t();

	ReadModel( renderEntity.hModel );

	ReadInt( renderEntity.entityNum );
	ReadInt( renderEntity.bodyId );

	ReadBounds( renderEntity.bounds );
	if ( !SaveGame_IsValidRenderBounds( renderEntity.bounds ) ) {
		Error( "idRestoreGame::ReadRenderEntity: invalid render bounds" );
	}

	// callback is set by class's Restore function
	renderEntity.callback = NULL;
	renderEntity.callbackData = NULL;

	ReadInt( renderEntity.suppressSurfaceInViewID );
	ReadInt( renderEntity.suppressShadowInViewID );
	ReadInt( renderEntity.suppressShadowInLightID );
	ReadInt( renderEntity.allowSurfaceInViewID );

	ReadVec3( renderEntity.origin );
	ReadMat3( renderEntity.axis );

	ReadMaterial( renderEntity.customShader );
	ReadMaterial( renderEntity.referenceShader );
	ReadSkin( renderEntity.customSkin );

	ReadInt( index );
	renderEntity.referenceSound = gameSoundWorld->EmitterForIndex( index );

	for( i = 0; i < MAX_ENTITY_SHADER_PARMS; i++ ) {
		ReadFloat( renderEntity.shaderParms[ i ] );
	}

	for( i = 0; i < MAX_RENDERENTITY_GUI; i++ ) {
		ReadUserInterface( renderEntity.gui[ i ] );
	}

	// idEntity will restore "cameraTarget", which will be used in idEntity::Present to restore the remoteRenderView
	renderEntity.remoteRenderView = NULL;

	renderEntity.joints = NULL;
	renderEntity.numJoints = 0;

	ReadFloat( renderEntity.modelDepthHack );

	ReadBool( renderEntity.noSelfShadow );
	ReadBool( renderEntity.noShadow );
	ReadBool( renderEntity.noDynamicInteractions );
	ReadBool( renderEntity.weaponDepthHack );

	ReadBool( renderEntity.forceUpdate );

	// HUMANHEAD mdl
	bool bTmp;
	idStr strTmp;
	ReadBool( bTmp );
	if( bTmp ) {
		ReadString( strTmp );
		renderEntity.declBeam = declManager->FindBeam( strTmp );
	} else {
		renderEntity.declBeam = NULL;
	}

	ReadBool( bTmp );
	if( bTmp ) {
		renderEntity.beamNodes = (hhBeamNodes_t *)Mem_ClearedAlloc(sizeof(hhBeamNodes_t) * renderEntity.declBeam->numBeams);

		for( i = 0; i < MAX_BEAM_NODES; i++ ) {
			ReadVec3( renderEntity.beamNodes->nodes[i] );
		}
	} else {
		renderEntity.beamNodes = NULL;
	}

	ReadBool( renderEntity.onlyVisibleInSpirit );
	ReadBool( renderEntity.onlyInvisibleInSpirit );
	ReadBool( renderEntity.lowSkippable );	//HUMANHEAD bjk
	ReadFloat( renderEntity.eyeDistance );

#if _HH_RENDERDEMO_HACKS
	renderEntity.notInRenderDemos = 0;
#endif
	renderEntity.timeGroup = 0;
//	renderEntity.xrayIndex = 0;
	// HUMANHEAD END
}

/*
================
idRestoreGame::ReadRenderLight
================
*/
void idRestoreGame::ReadRenderLight( renderLight_t &renderLight ) {
	int index;
	int i;

	ReadMat3( renderLight.axis );
	ReadVec3( renderLight.origin );

	ReadInt( renderLight.suppressLightInViewID );
	ReadInt( renderLight.allowLightInViewID );
	ReadBool( renderLight.noShadows );
	ReadBool( renderLight.noSpecular );
	ReadBool( renderLight.lowSkippable );	//HUMANHEAD bjk
	ReadBool( renderLight.pointLight );
	ReadBool( renderLight.parallel );

	ReadVec3( renderLight.lightRadius );
	ReadVec3( renderLight.lightCenter );

	ReadVec3( renderLight.target );
	ReadVec3( renderLight.right );
	ReadVec3( renderLight.up );
	ReadVec3( renderLight.start );
	ReadVec3( renderLight.end );

	// only idLight has a prelightModel and it's always based on the entityname, so we'll restore it there
	// ReadModel( renderLight.prelightModel );
	renderLight.prelightModel = NULL;

	ReadInt( renderLight.lightId );

	ReadMaterial( renderLight.shader );

	for( i = 0; i < MAX_ENTITY_SHADER_PARMS; i++ ) {
		ReadFloat( renderLight.shaderParms[ i ] );
	}

	ReadInt( index );
	renderLight.referenceSound = gameSoundWorld->EmitterForIndex( index );
}

/*
================
idRestoreGame::ReadRefSound
================
*/
void idRestoreGame::ReadRefSound( refSound_t &refSound ) {
	int		index;
	ReadInt( index );

	refSound.referenceSound = gameSoundWorld->EmitterForIndex( index );
	ReadVec3( refSound.origin );
	ReadInt( refSound.listenerId );
	ReadSoundShader( refSound.shader );
	ReadFloat( refSound.diversity );
	ReadBool( refSound.waitfortrigger );

	ReadFloat( refSound.parms.minDistance );
	ReadFloat( refSound.parms.maxDistance );
	ReadFloat( refSound.parms.volume );
	ReadFloat( refSound.parms.shakes );
	ReadInt( refSound.parms.soundShaderFlags );
	ReadInt( refSound.parms.soundClass );
	ReadInt( refSound.parms.subIndex );
	ReadInt( refSound.parms.profanityIndex );
	ReadFloat( refSound.parms.profanityDelay );
	ReadFloat( refSound.parms.profanityDuration );
}

/*
================
idRestoreGame::ReadRenderView
================
*/
void idRestoreGame::ReadRenderView( renderView_t &view ) {
	int i;

	ReadInt( view.viewID );
	ReadInt( view.x );
	ReadInt( view.y );
	ReadInt( view.width );
	ReadInt( view.height );

	ReadFloat( view.fov_x );
	ReadFloat( view.fov_y );
	ReadVec3( view.vieworg );
	ReadMat3( view.viewaxis );

	ReadBool( view.cramZNear );
	// HUMANHEAD mdl
	ReadBool( view.forceUpdate );
	ReadBool( view.viewSpiritEntities );
	// HUMANHEAD END

	ReadInt( view.time );

	for( i = 0; i < MAX_GLOBAL_SHADER_PARMS; i++ ) {
		ReadFloat( view.shaderParms[ i ] );
	}
}

/*
=================
idRestoreGame::ReadUsercmd
=================
*/
void idRestoreGame::ReadUsercmd( usercmd_t &usercmd ) {
	ReadInt( usercmd.gameFrame );
	ReadInt( usercmd.gameTime );
	ReadInt( usercmd.duplicateCount );
	ReadShort( usercmd.buttons );
	ReadSignedChar( usercmd.forwardmove );
	ReadSignedChar( usercmd.rightmove );
	ReadSignedChar( usercmd.upmove );
	ReadShort( usercmd.angles[0] );
	ReadShort( usercmd.angles[1] );
	ReadShort( usercmd.angles[2] );
	ReadShort( usercmd.mx );
	ReadShort( usercmd.my );
	ReadSignedChar( usercmd.impulse );
	ReadByte( usercmd.flags );
	ReadInt( usercmd.sequence );
}

/*
===================
idRestoreGame::ReadContactInfo
===================
*/
void idRestoreGame::ReadContactInfo( contactInfo_t &contactInfo ) {
	ReadInt( (int &)contactInfo.type );
	ReadVec3( contactInfo.point );
	ReadVec3( contactInfo.normal );
	ReadFloat( contactInfo.dist );
	ReadInt( contactInfo.contents );
	ReadMaterial( contactInfo.material );
	ReadInt( contactInfo.modelFeature );
	ReadInt( contactInfo.trmFeature );
	ReadInt( contactInfo.entityNum );
	ReadInt( contactInfo.id );
}

/*
===================
idRestoreGame::ReadTrace
===================
*/
void idRestoreGame::ReadTrace( trace_t &trace ) {
	ReadFloat( trace.fraction );
	ReadVec3( trace.endpos );
	ReadMat3( trace.endAxis );
	ReadContactInfo( trace.c );
}

/*
 ===================
 idRestoreGame::ReadTraceModel
 ===================
 */
void idRestoreGame::ReadTraceModel( idTraceModel &trace ) {
	int j, k;
	
	ReadInt( (int&)trace.type );
	ReadInt( trace.numVerts );
	for ( j = 0; j < MAX_TRACEMODEL_VERTS; j++ ) {
		ReadVec3( trace.verts[j] );
	}
	ReadInt( trace.numEdges );
	for ( j = 0; j < (MAX_TRACEMODEL_EDGES+1); j++ ) {
		ReadInt( trace.edges[j].v[0] );
		ReadInt( trace.edges[j].v[1] );
		ReadVec3( trace.edges[j].normal );
	}
	ReadInt( trace.numPolys );
	for ( j = 0; j < MAX_TRACEMODEL_POLYS; j++ ) {
		ReadVec3( trace.polys[j].normal );
		ReadFloat( trace.polys[j].dist );
		ReadBounds( trace.polys[j].bounds );
		ReadInt( trace.polys[j].numEdges );
		for ( k = 0; k < MAX_TRACEMODEL_POLYEDGES; k++ ) {
			ReadInt( trace.polys[j].edges[k] );
		}
	}
	ReadVec3( trace.offset );
	ReadBounds( trace.bounds );
	ReadBool( trace.isConvex );
	// padding win32 native structs
	char tmp[3];
	file->Read( tmp, 3 );
}

/*
=====================
idRestoreGame::ReadClipModel
=====================
*/
void idRestoreGame::ReadClipModel( idClipModel *&clipModel ) {
	bool restoreClipModel;

	ReadBool( restoreClipModel );
	if ( restoreClipModel ) {
		clipModel = new idClipModel();
		clipModel->Restore( this );
	} else {
		clipModel = NULL;
	}
}

/*
=====================
idRestoreGame::ReadSoundCommands
=====================
*/
void idRestoreGame::ReadSoundCommands( void ) {
	gameSoundWorld->StopAllSounds();
	gameSoundWorld->ReadFromSaveGame( file );
}

/*
=====================
idRestoreGame::ReadBuildNumber
=====================
*/
void idRestoreGame::ReadBuildNumber( void ) {
	int marker;
	ReadInt( marker );

	openQ4SaveGameCompatibilityVersion = 0;
	openQ4SaveGameCompatibilitySourceFileCount = 0;
	openQ4SaveGameNextSyncId = 0;
	openQ4SaveGameCompatible = false;
	openQ4SaveGameSyncMarkersEnabled = false;
	openQ4SaveGameCompatibilityStamp.Clear();
	openQ4SaveGameCompatibilityError.Clear();

	if ( marker != OPENQ4_SAVEGAME_COMPATIBILITY_MAGIC ) {
		buildNumber = marker;
		if ( buildNumber == BUILD_NUMBER ) {
			openQ4SaveGameCompatible = true;
		} else {
			openQ4SaveGameCompatibilityError = va(
				"legacy save payload build %d does not match current build %d", buildNumber, BUILD_NUMBER );
		}
		return;
	}

	ReadInt( openQ4SaveGameCompatibilityVersion );
	ReadInt( buildNumber );
	ReadString( openQ4SaveGameCompatibilityStamp );
	ReadInt( openQ4SaveGameCompatibilitySourceFileCount );

	if ( openQ4SaveGameCompatibilityVersion != OPENQ4_SAVEGAME_COMPATIBILITY_VERSION ) {
		openQ4SaveGameCompatibilityError = va(
			"payload format version %d does not match current version %d",
			openQ4SaveGameCompatibilityVersion, OPENQ4_SAVEGAME_COMPATIBILITY_VERSION );
		return;
	}

	// The version 5 header ends with the wire ABI of the build that wrote it.
	idStr savedWireABI;
	ReadString( savedWireABI );
	if ( savedWireABI.Icmp( SaveGame_NativeWireABI() ) != 0 ) {
		openQ4SaveGameCompatibilityError = va(
			"wire ABI %s does not match this build's %s",
			savedWireABI.c_str(), SaveGame_NativeWireABI() );
		return;
	}
	if ( buildNumber != BUILD_NUMBER ) {
		openQ4SaveGameCompatibilityError = va(
			"payload build %d does not match current build %d", buildNumber, BUILD_NUMBER );
		return;
	}
	if ( openQ4SaveGameCompatibilityStamp.Icmp( OPENQ4_SAVEGAME_COMPAT_SOURCE_HASH ) != 0 ) {
		openQ4SaveGameCompatibilityError = va(
			"source snapshot %s does not match current snapshot %s",
			openQ4SaveGameCompatibilityStamp.c_str(), OPENQ4_SAVEGAME_COMPAT_SOURCE_HASH );
		return;
	}
	if ( openQ4SaveGameCompatibilitySourceFileCount != OPENQ4_SAVEGAME_COMPAT_SOURCE_FILE_COUNT ) {
		openQ4SaveGameCompatibilityError = va(
			"source snapshot file count %d does not match current count %d",
			openQ4SaveGameCompatibilitySourceFileCount, OPENQ4_SAVEGAME_COMPAT_SOURCE_FILE_COUNT );
		return;
	}

	openQ4SaveGameCompatible = true;
	openQ4SaveGameSyncMarkersEnabled = true;
	openQ4SaveGameNextSyncId = 0;
}

/*
=====================
idRestoreGame::ReadSaveGameFooter
=====================
*/
void idRestoreGame::ReadSaveGameFooter( void ) {
	if ( !openQ4SaveGameSyncMarkersEnabled ) {
		return;
	}

	const int footerOffset = file->Tell();
	int marker;
	int footerVersion;
	int savedFooterOffset;
	int savedObjectCount;
	int savedSyncCount;

	ReadInt( marker );
	ReadInt( footerVersion );
	ReadInt( savedFooterOffset );
	ReadInt( savedObjectCount );
	ReadInt( savedSyncCount );

	if ( marker != OPENQ4_SAVEGAME_FOOTER_MAGIC ) {
		Error( "idRestoreGame::ReadSaveGameFooter: marker mismatch at offset %d (got 0x%08x, expected 0x%08x)",
			footerOffset, marker, OPENQ4_SAVEGAME_FOOTER_MAGIC );
	}
	if ( footerVersion != OPENQ4_SAVEGAME_FOOTER_VERSION ) {
		Error( "idRestoreGame::ReadSaveGameFooter: footer version %d does not match current version %d",
			footerVersion, OPENQ4_SAVEGAME_FOOTER_VERSION );
	}
	if ( savedFooterOffset != footerOffset ) {
		Error( "idRestoreGame::ReadSaveGameFooter: saved footer offset %d does not match actual offset %d",
			savedFooterOffset, footerOffset );
	}
	if ( savedObjectCount != objects.Num() - 1 ) {
		Error( "idRestoreGame::ReadSaveGameFooter: saved object count %d does not match restored object count %d",
			savedObjectCount, objects.Num() - 1 );
	}
	if ( savedSyncCount != openQ4SaveGameNextSyncId ) {
		Error( "idRestoreGame::ReadSaveGameFooter: saved sync marker count %d does not match restored count %d",
			savedSyncCount, openQ4SaveGameNextSyncId );
	}

	// The session appends its integrity trailer directly after the footer and
	// verifies the checksum during preflight. Here it only has to be the last
	// thing in the file and to cover everything up to this point.
	const int integrityOffset = file->Tell();
	int integrityMarker;
	int integrityVersion;
	int protectedLength;
	int checksum;

	ReadInt( integrityMarker );
	ReadInt( integrityVersion );
	ReadInt( protectedLength );
	ReadInt( checksum );

	if ( integrityMarker != OPENQ4_SAVEGAME_INTEGRITY_MAGIC ) {
		Error( "idRestoreGame::ReadSaveGameFooter: integrity marker mismatch at offset %d (got 0x%08x, expected 0x%08x)",
			integrityOffset, integrityMarker, OPENQ4_SAVEGAME_INTEGRITY_MAGIC );
	}
	if ( integrityVersion != OPENQ4_SAVEGAME_INTEGRITY_VERSION ) {
		Error( "idRestoreGame::ReadSaveGameFooter: integrity version %d does not match current version %d",
			integrityVersion, OPENQ4_SAVEGAME_INTEGRITY_VERSION );
	}
	if ( protectedLength != integrityOffset ) {
		Error( "idRestoreGame::ReadSaveGameFooter: integrity length %d does not match its offset %d",
			protectedLength, integrityOffset );
	}

	const int fileLength = file->Length();
	const int endOffset = file->Tell();
	if ( fileLength > 0 && endOffset >= 0 && endOffset != fileLength ) {
		Error( "idRestoreGame::ReadSaveGameFooter: %d unexpected trailing bytes after savegame payload", fileLength - endOffset );
	}
}

/*
=====================
idRestoreGame::GetBuildNumber
=====================
*/
int idRestoreGame::GetBuildNumber( void ) {
	return buildNumber;
}

bool idRestoreGame::IsOpenQ4SaveGameCompatible( void ) const {
	return openQ4SaveGameCompatible;
}

const char *idRestoreGame::GetOpenQ4SaveGameCompatibilityError( void ) const {
	return openQ4SaveGameCompatibilityError.c_str();
}



// HUMANHEAD ADDITIONS

void idSaveGame::WriteEventDef( const idEventDef *event ) {
	int value = -1;
	if (event != NULL) {
		value = event->GetEventNum();
	}
	WriteInt( value );
}

void idRestoreGame::ReadEventDef( const idEventDef *&event ) {
	int value;
	ReadInt( value );
	if (value == -1) {
		event = NULL;
	}
	else {
		event = idEventDef::FindEvent(value);
	}
}

void idSaveGame::WriteQuat( const idQuat &quat ) {
	WriteFloat( quat.x );
	WriteFloat( quat.y );
	WriteFloat( quat.z );
	WriteFloat( quat.w );
}

void idRestoreGame::ReadQuat( idQuat &quat ) {
	ReadFloat( quat.x );
	ReadFloat( quat.y );
	ReadFloat( quat.z );
	ReadFloat( quat.w );
}

void idSaveGame::WriteStringList( const idList<idStr> &list ) {
	int num = list.Num();
	WriteInt( num );
	for( int i = 0; i < num; i++ ) {
		WriteString( list[i] );
	}
}

void idRestoreGame::ReadStringList( idList<idStr> &list ) {
	int num;
	idStr tmp;
	ReadInt( num );
	list.Clear();
	for( int i = 0; i < num; i++ ) {
		ReadString( tmp );
		list.Append( tmp );
	}
}

