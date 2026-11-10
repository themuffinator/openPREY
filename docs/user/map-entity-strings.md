# Map Entity Strings

> **Development documentation:** This page follows the current source tree and may describe changes newer than the public download. See [release status and released-version guides](release-status.md) before using it with a release package.

openQ4 can replace or extend the entities spawned by a retail map without
editing, recompiling, or redistributing that map. This is intended for mods,
server packages, compatibility fixes, and alternate gameplay layouts.

For a map named `maps/mp/q4dm1.map`, place either or both companion files at:

- `maps/mp/q4dm1.ent`
- `maps/mp/q4dm1.entx`

The files use the normal virtual filesystem, so they may be loose development
files or members of a PK4. Normal filesystem/package priority determines which
file with each extension is selected.

## Replacement and extension order

`.ent` is a complete replacement for the map's runtime entity string. It must
contain worldspawn and every other map entity that should still spawn.

`.entx` appends point entities to whichever entity string is active: the
original map entities when there is no `.ent`, or the complete `.ent`
replacement when both files exist. The fixed load order is therefore:

1. Load and resolve the original `.map` or `.reg`.
2. Build the original map's collision data.
3. Replace the entity string with `.ent`, when present.
4. Append the entities from `.entx`, when present.
5. Spawn the resulting entity list normally.

This timing lets a replacement change runtime entity behavior without making
the original map's compiled geometry or collision unavailable. It also means
these files cannot add, remove, or reshape map brushes and patches.

The feature does not rewrite the original `.map`. Runtime-only entities are
also excluded from map/export writes, and an editor write is refused while a
complete `.ent` replacement is active. Map tools such as dmap continue to use
the original map source rather than applying runtime companion files.

## File syntax

Both files are text entity dictionaries. An optional `Version 1` header is
accepted. Quote keys and values for predictable parsing; `//` comments are
allowed.

An additive `.entx` example:

```text
Version 1

{
    "classname" "info_player_deathmatch"
    "name" "custom_spawn_north"
    "origin" "128 256 64"
    "angle" "90"
}
```

A complete `.ent` replacement example:

```text
Version 1

{
    "classname" "worldspawn"
    "name" "world"
    "gravity" "1066"
}

{
    "classname" "info_player_start"
    "name" "replacement_player_start"
    "origin" "128 256 64"
    "angle" "90"
}
```

The example replacement is deliberately small. A real replacement must retain
all lights, scripts, triggers, movers, spawn points, and other entities needed
by that map and game mode.

## Validation and limits

Entity-string files are parsed into temporary storage and applied only after
both files validate. A malformed file stops the map load with a specific
warning instead of leaving a partially modified entity list.

The following rules are enforced:

- A `.ent` must be nonempty, begin with exactly one `worldspawn`, and contain no
  later worldspawn.
- An `.entx` must not contain worldspawn.
- Every entity needs a nonempty `classname`.
- Each entity key may appear only once, ignoring case.
- Nonempty entity names must be unique within a file, ignoring case. An
  `.entx` name also may not collide with the active original or replacement
  entity string.
- `spawn_entnum` is reserved for the game and cannot be authored in either
  file.
- Only entity key/value dictionaries are accepted. Nested brush and patch
  blocks are rejected.
- Each file is limited to 16 MiB, 4,096 entities, and 4,096 keys per entity.
- The final runtime entity string must fit the game entity table. On normal
  desktop builds, the initial map limit is 4,062 entities; leave additional
  room for entities created during play.

The parser also rejects incomplete reads and embedded NUL bytes, accepts a
UTF-8 byte-order mark, and tracks the selected `.ent` and `.entx` timestamps so
a subsequent map reload notices files that were added, removed, or changed.

## Multiplayer packaging

Package the same entity-string files for the server and every client. These
files are runtime map content; they are not transferred to clients as console
commands and should not be treated as a server-local configuration override.
Using one PK4 for the map-specific `.ent`/`.entx` files is the simplest way to
keep every participant on the same layout.
