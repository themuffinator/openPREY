// Copyright (C) 2026 DarkMatter Productions
// SPDX-License-Identifier: GPL-3.0-or-later
#include "src/tools/leveleditor/MapWorkspace.h"

#include <cstdio>
#include <chrono>
#include <fstream>
#include <iterator>
#include <map>
#include <random>
#include <string>

using namespace oq4editor;
static int failures = 0;
static int checks = 0;
static void Expect( bool value, const char *label ) {
	++checks;
	if ( !value ) { std::fprintf( stderr, "editor test failed: %s\n", label ); ++failures; }
}

static const std::string fixture =
	"\xEF\xBB\xBF// author comment { ignored\r\nVersion 3\r\n"
	"{\r\n\"classname\" \"worldspawn\"\r\n\"editor_note\" \"literal \\path { }\"\r\n"
	"// a compiler directive must stay in authoring state\r\n\"removeEntities\" \"light\"\r\n"
	"{ brushDef3 {\r\n( 1 0 0 -64 ) ( ( 0.015625 0 0 ) ( 0 0.015625 0 ) ) \"textures/common/caulk\"\r\n} }\r\n}\r\n"
	"/* entity separator } */\r\n{\r\n\"classname\" \"light\"\r\n\"name\" \"light_1\"\r\n"
	"\"origin\" \"0 0 128\"\r\n\"light_radius\" \"256 256 256\"\r\n}\r\n// tail comment\r\n";

class MemoryStorage : public MapStorage {
public:
	std::map<std::string, std::string> files;
	std::string failRead, failWrite, failPromote;
	int writes = 0;
	bool Read( const std::string &path, std::string &text, bool &exists, std::string &error ) override {
		if ( path == failRead ) { error = "injected read failure"; return false; }
		const auto it = files.find( path ); exists = it != files.end(); text = exists ? it->second : ""; return true;
	}
	bool WriteAndSync( const std::string &path, const std::string &text, std::string &error ) override {
		++writes;
		if ( path == failWrite ) { files[path] = text.substr( 0, text.size() / 2 ); error = "injected short write / sync failure"; return false; }
		files[path] = text; return true;
	}
	bool Promote( const std::string &from, const std::string &to, std::string &error ) override {
		if ( to == failPromote ) { error = "injected promotion failure"; return false; }
		files[to] = files.at( from ); files.erase( from ); return true;
	}
	void Remove( const std::string &path ) override { files.erase( path ); }
};

static void Documents() {
	MapDocument document;
	std::string error;
	for ( int version = 1; version <= 3; ++version ) {
		const std::string source = "Version " + std::to_string( version ) + "\n{\"classname\" \"worldspawn\"}\n";
		Expect( document.OpenText( source, error ) && document.Version() == version, "source version reaches geometry adapters" );
	}
	Expect( document.OpenText( "{\"classname\" \"worldspawn\"}", error ) && document.Version() == 1, "headerless maps use legacy geometry version" );
	Expect( document.OpenText( fixture, error ), "load source" );
	Expect( document.Serialize() == fixture, "BOM, CRLF, comments, primitive numbers and paths round trip byte for byte" );
	Expect( document.Entities().size() == 2 && document.Entities()[0].primitiveCount == 1, "source is not runtime-resolved" );
	const EntityId world = document.Entities()[0].id, light = document.Entities()[1].id;
	Expect( document.SetProperty( light, "light_radius", "512 512 512", error ), "edit point property" );
	const std::string edited = document.Serialize();
	Expect( document.IsDirty(), "edit marks dirty" );
	Expect( document.Undo( error ) && document.Serialize() == fixture && !document.IsDirty(), "undo to original savepoint" );
	Expect( document.Redo( error ) && document.Serialize() == edited && document.IsDirty(), "redo exact edit" );
	document.MarkSaved();
	Expect( document.Undo( error ) && document.IsDirty(), "undo away from newer savepoint remains dirty" );
	Expect( document.Redo( error ) && !document.IsDirty(), "redo to newer savepoint becomes clean" );
	Expect( document.Undo( error ) && document.SetProperty( light, "light_radius", "64 64 64", error ), "branch from undo" );
	Expect( !document.CanRedo() && document.IsDirty(), "branch invalidates redo and does not reuse saved revision" );
	const auto revision = document.Revision();
	Expect( document.SetProperty( light, "light_radius", "64 64 64", error ) && document.Revision() == revision, "no-op edit creates no transaction" );
	Expect( !document.DeleteEntity( world, error ), "worldspawn protected" );
	Expect( !document.SetProperty( world, "classname", "light", error ), "worldspawn identity protected" );
	Expect( !document.SetProperty( world, "classname ", "light", error ), "trimmed keys cannot bypass worldspawn protection" );
	Expect( !document.SetProperty( light, "classname", "worldspawn ", error ), "trimmed values cannot create a second worldspawn" );
	Expect( !document.RemoveProperty( light, "classname", error ), "classname cannot be removed" );
	Expect( !document.SetProperty( world, "origin", "1 2 3", error ), "geometry origin is not a raw property edit" );
	Expect( !document.SetProperty( light, "bad", "quote\"injection", error ), "quote injection rejected" );
	Expect( !document.SetProperty( light, "bad", std::string( "x\0y", 3 ), error ), "NUL injection rejected" );
	Expect( document.SetProperty( world, "message", "test", error ), "insert property before geometry" );
	const std::string text = document.Serialize();
	Expect( text.find( "\"message\" \"test\"\r\n" ) < text.find( "brushDef3" ), "new world property precedes primitives and uses CRLF" );
	Expect( document.HistoryBytes() < 4096, "property history stores changed ranges, not a map per edit" );
	EntityId added = 0;
	Expect( document.AddEntity( "info_player_start", "start", added, error ), "create entity" );
	Expect( !document.AddEntity( "light", "START", added, error ), "new entity names are unique without case" );
	Expect( !document.AddEntity( "light", "start ", added, error ), "trimmed names stay unique" );
	Expect( !document.AddEntity( "worldspawn ", "second_world", added, error ), "trimmed creation classname cannot bypass worldspawn protection" );
	Expect( document.DeleteEntity( light, error ) && !document.Find( light ), "delete entity" );
	Expect( document.Find( added ) != nullptr, "unrelated stable handle survives deletion" );
	Expect( document.Undo( error ) && document.Find( light ) != nullptr, "undo deletion restores the handle" );
	Expect( document.Redo( error ) && !document.Find( light ), "redo deletion" );
	const auto beforeBadLoad = document.Serialize();
	const auto beforeBadRevision = document.Revision();
	for ( const std::string bad : {
		"", "Version 99\n{}", "Version 3\n{\"classname\" \"light\"}",
		"Version 3\n{\"classname\" \"worldspawn\"", "Version 3\n{\"classname\"}",
		"Version 3\n{\"classname\" \"worldspawn\"} /* unterminated",
		"Version 3\n{\"classname\" \"worldspawn\" { brushDef3 { ( } } }",
		"Version 3\n{\"classname\" \"worldspawn\"}\n{\"classname\" \"worldspawn\"}"
	} ) {
		Expect( !document.OpenText( bad, error ), "malformed document rejected" );
		Expect( document.Serialize() == beforeBadLoad && document.Revision() == beforeBadRevision, "failed load preserves document and history" );
	}
	Expect( !document.OpenText( std::string( "Version 3\0{}", 12 ), error ), "embedded NUL source rejected" );
	Expect( document.OpenText( fixture, error ) && !document.Find( world ), "handles from previous documents stay invalid" );
	MapDocument duplicate;
	const std::string dup = "Version 3\n{\"classname\" \"worldspawn\" \"key\" \"first\" /* keep */ \"KEY\" \"last\"}\n";
	Expect( duplicate.OpenText( dup, error ), "duplicate property source loads losslessly" );
	const auto dupId = duplicate.Entities().front().id;
	Expect( duplicate.Entities().front().Value( "key" ) == "last", "effective last property matches engine dictionary" );
	Expect( duplicate.RemoveProperty( dupId, "key", error ) && duplicate.Entities().front().Value( "key" ).empty(), "unset removes all duplicate definitions" );
	Expect( duplicate.Serialize().find( "/* keep */" ) != std::string::npos, "unset preserves intervening comments" );
	Expect( duplicate.Undo( error ) && duplicate.Serialize() == dup, "duplicate-key removal is one undo transaction" );
	MapDocument trailing;
	Expect( trailing.OpenText( "{\"classname \" \"worldspawn \"}", error ) && trailing.Entities().front().Value( "classname" ) == "worldspawn", "effective property trimming matches engine" );
	Expect( !trailing.OpenText( "{\"classname\"\n\"worldspawn\"}", error ), "property value must be on the key's line" );
	// Duplicate keys on opposite sides of a primitive require a wider text
	// splice. Geometry caches must fall back to parsing without changing bytes.
	MapDocument interleaved;
	const std::string unusual = "{\"classname\" \"worldspawn\" \"key\" \"a\" {brushDef3 {}} \"key\" \"b\"}";
	Expect( interleaved.OpenText( unusual, error ), "interleaved property fixture" );
	const auto interId = interleaved.Entities().front().id;
	Expect( interleaved.RemoveProperty( interId, "key", error ) && interleaved.Entities().front().primitiveCount == 1, "overlapping source edit refreshes primitive ranges" );
	Expect( interleaved.Undo( error ) && interleaved.Serialize() == unusual, "interleaved undo is lossless" );
	Expect( interleaved.SetProperty( interId, "note", "new", error ) && interleaved.Entities().front().primitiveRanges.size() == 1, "subsequent property edit reuses refreshed geometry" );
}

static void HistoryStress() {
	std::string error;
	MapDocument document;
	document.New();
	const auto world = document.Entities().front().id;
	for ( int i = 0; i < 400; ++i ) { Expect( document.SetProperty( world, "iteration", std::to_string( i ), error ), "bounded history accepts edit" ); }
	int undone = 0;
	while ( document.Undo( error ) ) { ++undone; }
	Expect( undone == static_cast<int>( MapDocument::MaxHistoryEntries ), "history keeps exactly its configured entry limit" );
	Expect( document.Entities().front().Value( "iteration" ) == "143", "eviction keeps correct oldest retained state" );
	while ( document.Redo( error ) ) {}
	Expect( document.Entities().front().Value( "iteration" ) == "399", "all retained edits replay" );
	// Every generated edit must round-trip through source parsing and reversible
	// application; this exercises shifting offsets and empty/literal values.
	std::mt19937 random( 934 );
	for ( int i = 0; i < 600; ++i ) {
		const std::string before = document.Serialize();
		const std::string key = "field" + std::to_string( random() % 20 );
		const std::string value = std::to_string( random() ) + " { \\ // /* literal";
		Expect( document.SetProperty( world, key, value, error ), "random edit accepted" );
		const std::string after = document.Serialize();
		MapDocument reload;
		Expect( reload.OpenText( after, error ) && reload.Serialize() == after, "edited document reparses losslessly" );
		Expect( document.Undo( error ) && document.Serialize() == before, "random undo exact" );
		Expect( document.Redo( error ) && document.Serialize() == after, "random redo exact" );
	}
}

static void Persistence() {
	for ( int failure = 0; failure < 5; ++failure ) {
		MemoryStorage storage;
		storage.files["maps/test.map"] = fixture;
		MapWorkspace workspace( storage );
		std::string error;
		Expect( workspace.Open( "test", error ), "open effective asset" );
		const auto id = workspace.Document().Entities()[1].id;
		Expect( workspace.Document().SetProperty( id, "light_radius", "100 100 100", error ), "prepare save edit" );
		if ( failure == 0 ) { storage.failWrite = "maps/test.map.editor-tmp"; }
		if ( failure == 1 ) { storage.failPromote = "maps/test.map"; }
		if ( failure == 2 ) { storage.failWrite = "maps/test.map.bak.editor-tmp"; }
		if ( failure == 3 ) { storage.failPromote = "maps/test.map.bak"; }
		if ( failure == 4 ) { storage.failRead = "maps/test.map"; }
		Expect( !workspace.Save( "", false, error ), "injected I/O failure reaches caller" );
		Expect( workspace.Document().IsDirty() && workspace.Path() == "maps/test.map", "failed save preserves document identity and dirty state" );
		Expect( storage.files["maps/test.map"] == fixture, "failed publication preserves original bytes" );
		Expect( storage.files.count( "maps/test.map.editor-tmp" ) == 0 && storage.files.count( "maps/test.map.bak.editor-tmp" ) == 0, "failed staging is cleaned" );
		storage.failRead.clear(); storage.failWrite.clear(); storage.failPromote.clear();
		Expect( workspace.Save( "", false, error ) && !workspace.Document().IsDirty(), "retry successful save marks clean" );
		Expect( storage.files["maps/test.map.bak"] == fixture, "backup contains previous on-disk version" );
	}
	MemoryStorage storage;
	storage.files["maps/test.map"] = fixture;
	MapWorkspace workspace( storage );
	std::string error;
	Expect( workspace.Open( "test", error ), "open for external conflict" );
	const auto id = workspace.Document().Entities()[1].id;
	workspace.Document().SetProperty( id, "_color", "1 0 0", error );
	storage.files["maps/test.map"] = fixture + "// external edit\n";
	Expect( !workspace.Save( "", false, error ) && storage.writes == 0, "external edit conflict detected before any write" );
	Expect( !workspace.New( error ) && !workspace.Open( "other", error ) && !workspace.Close( false, error ), "dirty document protected from replacement" );
	Expect( workspace.Save( "copy", true, error ) && workspace.Document().IsDirty() && workspace.Path() == "maps/test.map", "save-copy keeps dirty flag and current path" );
	Expect( !workspace.Save( "copy", true, error ), "save-copy refuses unrelated existing output" );
	Expect( workspace.AutoSave( error ) && workspace.Document().IsDirty(), "recovery never marks document saved" );
	const int writes = storage.writes;
	Expect( workspace.AutoSave( error ) && storage.writes == writes, "unchanged revision avoids redundant recovery I/O" );
	const auto recovery = workspace.RecoveryPath();
	Expect( storage.files[recovery] == workspace.Document().Serialize(), "recovery contains complete document" );
	Expect( workspace.Close( true, error ) && workspace.Recover( "test", error ) && workspace.Document().IsDirty(), "restore recovery as dirty document" );
	Expect( workspace.Path().empty() && !workspace.Save( "", false, error ), "recovery requires a new destination" );
	Expect( workspace.Save( "recovered", false, error ), "save restored work to new path" );
	const auto savedPath = workspace.Path();
	storage.files["maps/bad.map"] = "Version 3\n{ broken }";
	Expect( !workspace.Open( "bad", error ) && workspace.Path() == savedPath, "bad file does not change identity" );
	const auto dirtyId = workspace.Document().Entities()[1].id;
	Expect( workspace.Document().SetProperty( dirtyId, "_confirmed_open", "keep", error ), "edit before confirmed replacement" );
	const auto unsaved = workspace.Document().Serialize();
	Expect( !workspace.Open( "bad", error, true ) && !workspace.Open( "missing", error, true ), "confirmed replacement still validates before discarding" );
	Expect( workspace.Document().Serialize() == unsaved && workspace.Document().IsDirty() && workspace.Path() == savedPath, "failed confirmed open preserves dirty document and identity" );
	Expect( workspace.Document().Undo( error ) && !workspace.Document().IsDirty(), "failed confirmed open preserves history and savepoint" );
	Expect( workspace.Document().Redo( error ) && workspace.Open( "test", error, true ) && !workspace.Document().Find( dirtyId ), "successful confirmed open replaces document and invalidates handles" );
	Expect( workspace.Document().SetProperty( workspace.Document().Entities()[0].id, "_note", "discard", error ) && workspace.New( error, true ), "confirmed new replaces dirty document" );
	for ( const char *unsafe : { "../escape", "/absolute", "C:/outside", "a//b", "a/../b", "a/./b", "a/", "nul", "con.map", "a/b ", "a/quote\"", "a;quit" } ) {
		std::string normalized;
		Expect( !MapWorkspace::MapPath( unsafe, normalized, error ), "unsafe/nonportable map path rejected" );
	}
	std::string normalized;
	Expect( MapWorkspace::MapPath( "maps\\my map\\test", normalized, error ) && normalized == "maps/my map/test.map", "portable paths with spaces and separators" );
}

int main( int argc, char **argv ) {
	Documents(); HistoryStress(); Persistence();
	for ( int i = 1; i < argc; ++i ) {
		std::ifstream input( argv[i], std::ios::binary );
		Expect( input.good(), "open supplied stock map" );
		const std::string text( ( std::istreambuf_iterator<char>( input ) ), std::istreambuf_iterator<char>() );
		MapDocument stock;
		std::string error;
		const bool loaded = stock.OpenText( text, error );
		Expect( loaded, argv[i] );
		if ( !loaded ) { std::fprintf( stderr, "%s: %s\n", argv[i], error.c_str() ); continue; }
		Expect( stock.Serialize() == text, "stock map byte-exact round trip" );
		const auto world = stock.Entities().front().id;
		const auto start = std::chrono::steady_clock::now();
		Expect( stock.SetProperty( world, "_openq4_editor_test", "roundtrip", error ), "stock world property edit" );
		const auto end = std::chrono::steady_clock::now();
		Expect( stock.Undo( error ) && stock.Serialize() == text, "stock undo byte-exact round trip" );
		std::printf( "stock map: %s, %zu bytes, %zu entities, property edit %.3f ms\n", argv[i], text.size(), stock.Entities().size(),
			std::chrono::duration<double, std::milli>( end - start ).count() );
		std::fflush( stdout );
	}
	std::printf( "editor document: %d checks, %d failures\n", checks, failures );
	return failures == 0 ? 0 : 1;
}
