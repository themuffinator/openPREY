# Savegame Reliability

This document describes openPREY's save/load compatibility checks, the upstream
failure recorded in [OpenQ4 issue #84](https://github.com/themuffinator/openQ4/issues/84),
and the defensive checks expected when the save format changes.

## Upstream issue #84

The reported `idMoveState::Restore: invalid path length` values were not valid path
lengths and did not, by themselves, prove that the restore cursor had drifted. In
the affected GameLib version, `idMoveState` did not initialize `pathLen`,
`pathArea`, `pathTime`, or its path entries before the first save. A fresh save
could therefore serialize an indeterminate `pathLen`, and the restore-side range
check correctly rejected it.

The Q4-specific move-state implementation from that report is not part of Prey's
unified game module. openPREY retains the broadly applicable outcome: serialized
counts, indices, strings, object references, script state, animation state, and
articulated-physics state are range-checked before they can allocate or index
runtime storage. Saves produced by incompatible builds are not repaired in place.

## Save Pipeline

The engine owns the session header, screenshot and description sidecars, staged
file commit, menu discovery, and the transition into a loaded map. The single
unified Prey GameLib owns the positional gameplay payload for both SP and MP.

New gameplay payloads contain:

- a format marker and payload version 5;
- the engine build number;
- a generated GameLib source-snapshot stamp and source-file count;
- the wire-ABI stamp of the build that wrote the payload;
- class-boundary sync markers;
- a footer containing the final payload offset and object/script bookkeeping
  counts;
- the session's 16-byte integrity trailer (marker, version, protected length
  and CRC-32), appended after the footer.

The payload version is one number shared by the engine and the game library.
The session frames the payload by it: from version 3 on it expects the wire-ABI
stamp in the header and its own trailer after the footer, and the engine's GUI
and sound records inside the payload use the encodings of that version. The
session always writes the current framing, so the game library must stamp the
version the session writes (`SESSION_OPENQ4_SAVEGAME_COMPATIBILITY_VERSION` in
`src/framework/Session.cpp`, `OPENQ4_SAVEGAME_COMPATIBILITY_VERSION` in
`src/game/gamesys/SaveGame.h`). When the two disagree, every staged save fails
validation and none reaches disk: between the engine merge that brought in
version 5 and the game library's move to it, the library still stamped
version 2, and each save was rejected with `has invalid payload footer marker`.
An upstream merge that raises the session's version needs the same change in
the game library.

Prey's game records are not portable. Bitfields, script storage and several
structures are written as the compiler laid them out, so openPREY's version 5
payload carries the exact stamp of the build that wrote it
(`<os>-<compiler-abi>-<architecture>-<endian>-raw1`, for example
`windows-msvcabi-x64-le-raw1`) instead of upstream's `le64-portable1`
(`OPENQ4_SAVEGAME_GAME_RECORDS_ARE_PORTABLE` in
`src/framework/SaveGameReleases.h`). A save loads only on the operating system,
compiler ABI and architecture that wrote it. The engine and the game library
each derive the stamp for themselves; if they ever disagreed on a platform,
saves there would fail staged validation instead of being written unloadable.

Save files are written to temporary paths and validated before the old save is
backed up and the new group is committed. Loading performs the same payload
preflight before `ExecuteMapChange`, so a truncated or damaged payload, or one
from another platform, cannot destroy the currently running map merely to
report the error later.

Two layers decide whether a payload loads:

- The engine preflight, before map teardown, checks the payload version range,
  the wire-ABI stamp, the trailer's length and CRC, and the footer. It records
  build and source-snapshot differences but does not refuse on them.
- The game library, once the saved map has loaded, requires its own payload
  version, wire ABI, build number, source stamp and source-file count to match
  exactly. On a mismatch it logs `Savegame payload is not compatible with this
  openPREY build` and declines the restore, and the session starts the saved
  map from its beginning with the save's persistent player data. A payload in
  the earlier version 2 framing takes this path too: on Windows x64 it still
  passes the engine preflight, which keeps upstream's version 2 reader, and the
  game library then declines it.

Checked on 10 November 2026 (Windows x64, build 2435) with variants of one
fresh save: another platform's stamp, upstream's `le64-portable1` stamp and a
flipped payload byte were each refused by the preflight with the running map
left in place; the version 2 framing and a different build number each loaded
the saved map and started it afresh.

Unstamped payloads are accepted only when their build number exactly matches the
running engine. The source generator normalizes line endings before hashing, so
equivalent Windows and Unix checkouts produce the same compatibility stamp.

[Savegame Compatibility Policy](savegame-compatibility-policy.md) is upstream
openQ4's policy for its own save history. Its preflight mechanics apply here;
its statements about portable version 5 saves and about reading versions 2 to 4
describe openQ4's game libraries, not Prey's.

## Save Transaction and Crash Recovery

The old slot is not replaced while a new payload is still being constructed.
Saving uses same-directory `.tmp` staging paths and `.prev` backups:

1. Recover or roll back any interrupted earlier transaction for the slot.
2. Write and sync the `.save` header and GameLib payload. The description is
   prepared in memory beforehand; checkpoint previews are captured first.
3. Calculate and append the integrity trailer, sync it, reopen the staged
   `.save`, and validate the complete header, compatibility block, CRC, and
   footer.
4. Write and sync the description, then validate its bounded fields and slot
   identity.
5. Validate and sync the preview. If the slot must have no preview, stage a
   synced `OQ4D` preview-deletion marker instead of leaving the old preview
   ambiguous.
6. Back up existing final files to `.prev`, commit description and preview state,
   and rename the payload last. The final payload rename is the commit point.
7. Remove backups; if a deletion marker was committed, remove it so the final
   slot has no `.tga`.

Failure before the commit point removes staging files and restores backups.
Recovery runs before both save and load. A valid final payload with no payload
temporary proves that the payload commit occurred, so recovery finishes cleanup.
Otherwise it restores `.prev` files, removes components created by the interrupted
attempt, and clears temporary files. The preview-deletion marker lets recovery
distinguish “the new slot intentionally has no preview” from “preview capture did
not finish,” preventing a stale image from being resurrected.

A commit begins only once all three components are staged, and it backs up
every existing final before publishing anything. Recovery uses that to tell a
crash while staging from one during the commit: with no backups, a payload
final beside its own temporary proves no commit began, so nothing in the
previous slot is touched. Before 2 November 2026 upstream recovery treated a sidecar
temporary that had not yet been written as already published, so a crash while
the payload was being staged deleted the previous save's description.

### Durability guarantee

Defined upstream in OpenQ4 on 2 November 2026. File contents are synced with
`fflush` plus `_commit` on Windows or `fsync` on POSIX before promotion. Every slot rename
then goes through `DurableMoveExact`, which never replaces an occupied name and
returns only once the rename is on disk: Windows uses `MoveFileExW` with
`MOVEFILE_WRITE_THROUGH`; Linux renames with `RENAME_NOREPLACE` where the
filesystem supports it and macOS with `RENAME_EXCL`, falling back to a checked
rename, and both then sync the parent directory (macOS also issues
`F_FULLFSYNC`). The guarantee is:

- At any interruption, the slot is either the previous save or the new one
  after recovery, never a mixture, and the previous save survives every failure
  before the commit point.
- Once a save reports success, its payload commit is on disk as far as the
  operating system and storage device acknowledge write-through or directory
  sync. Hardware that acknowledges writes it has not stored can still lose it.
- Each step is ordered on disk, so backups precede publication and the payload
  rename comes last even on filesystems that do not order metadata updates.

Backup removal after the commit is not synced; recovery finishes it if a crash
interrupts it. If a filesystem renames the file but cannot confirm the barrier,
the save continues with the weaker guarantee and logs one warning per session
rather than rolling back a completed move. Rollback after a failed rename is
best effort and leaves recovery evidence when it cannot finish. This is not
database-style ACID, and no power-cut test has been performed.

`tools/tests/savegame_durability.py` compiles the production commit, recovery
and CRC-32 against real files. It kills a child process after every namespace
step of a commit, for each combination of existing slot components, and at five
staging points including half-written payloads, then requires recovery to leave
one whole save. On Windows it also holds the old payload open without delete
sharing so the backup rename fails and the commit rolls back.
`tools/tests/durable_file.py` exercises `DurableMoveExact` with fault injection on each
platform and rejects three move mutations: replacing an occupied name, skipping
the namespace sync, and hiding a completed rename.

## Load Preflight Before Map Teardown

Loading first recovers an interrupted slot, then reads into temporary state. Before
`ExecuteMapChange` tears down the running map, the engine validates:

- the supported outer game name and outer header version;
- bounded map/entity-filter strings and persistent-player dictionaries;
- the CRC/trailer/footer, or the exact approved older-payload policy;
- the payload version and wire ABI;
- a non-empty, normalized, safe map path; and
- that the referenced map/entity-filter combination is available.

Only after those checks pass are persistent-player data, savegame state, and the
target map committed to the session. A truncated save, failed CRC, unsupported
version/ABI, unsafe path, or missing map therefore leaves the current map intact.

This preflight does not simulate every later object restore. Class construction,
object-specific semantic validation, and cross-object attachment still occur as
the new map initializes. Those checks now fail close to the offending field, but
there is not yet a general staged-world rollback after `RestoreObjects` begins.
That remaining boundary must not be described as full preflight of every gameplay
semantic.

The load menu deliberately performs only bounded outer-header discovery so it
does not checksum every save on each refresh. A header-valid slot can remain
visible even if payload preflight later rejects it; selection then fails before
map teardown with the compatibility or integrity diagnostic.

## Additional Hardening

- Sound-world serialization now checks every write and validates all serialized
  counts, strings, emitters, channels, shaders, and sound classes. Restore creates
  emitters at their serialized indices instead of passing through the allocator's
  reusable-emitter path, which could alias two saved indices. Trailing reusable
  empty emitters are omitted from new saves.
- Game object references use a pointer hash index during save construction and
  lookup. This removes repeated linear scans from object discovery and reference
  serialization without changing the on-disk indices.
- Gameplay restore code retains explicit bounds checks for variable-sized data and
  class sync markers for diagnosing the first mismatched object boundary.

## Compatibility and Residual Risk

The gameplay payload remains a positional binary format. Sync markers and the
footer make structural failures easier to reject and diagnose, and the trailer's
CRC-32 catches accidental damage; none of them is a cryptographic integrity
check. Source- or build-incompatible saves are intentionally not restored rather
than guessed through; compatibility across arbitrary revisions is not promised.

Menu discovery validates the session header and aggregates saves from the active
game directory, `basepr`, and the retail `base` directory. A save can therefore
remain visible even when its gameplay payload cannot be restored. Selecting one
that fails the engine preflight produces a precise warning while the current map
continues running. Selecting one from another build of openPREY on the same
platform passes the preflight, and the game library then starts its map afresh
as described under [Save Pipeline](#save-pipeline).

## Validation

The regression contract is exercised with:

```text
python tools/tests/savegame_corruption_contract.py
python tools/tests/savegame_pointer_width_safety.py
python tools/tests/savegame_durability.py
```

Runtime validation should load the unified `game_<arch>` module, enter a real Prey
map such as `game/roadhouse`, save, and load the newly written save. Confirm
`Game Map Init SaveGame` without restore errors or sound assertions. A save with a
damaged payload or another platform's stamp should be rejected during engine
preflight, before game-map initialization; one stamped with another build should
start its map afresh.
