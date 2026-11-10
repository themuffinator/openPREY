# Level-Load Cache

> [!NOTE]
> This page documents inherited engine/tooling capability. Retail Prey behavior remains
> runtime-validation pending unless the rebase status ledger records specific evidence.

openPREY learns which source files a map actually uses and can prepare those
bytes during a later matching load. Worker jobs read or inflate the selected
source, validate supported container framing and whole-buffer integrity, then
hand immutable bytes back to the normal owner. openPREY also keeps validated local
binary caches for parsed models, classic map worlds, and collision data, and the
unified Prey game module keeps compact binary caches for MD5 animations.

The experimental engine cache is disabled by default because current stock-map
measurements do not yet prove a reliable improvement over classic loading. If
enabled, the first visit still uses the installed Prey (2006) or mod sources and
may take longer while private cache files are written. A later visit can reuse work
only when the map, game mode, entity filter, active search/PK4 set, source
identity, and load-affecting settings still match.

The game module's animation cache is enabled by default and is built as MD5
animations are first encountered. Later launches can load the final animation data
directly instead of decompressing and parsing the much larger text source again, so
the first visit to animation-heavy maps can take slightly longer while cache files
are written. Upstream reference testing generated 820 cache entries using about
27 MiB and reduced an animation-heavy model-definition phase from roughly 2.7–2.8
seconds to about 1.0 second on the tested Windows x64 system; Prey-specific
performance remains validation-pending.

## Safety and compatibility

The retail or mod file selected by the normal virtual filesystem always remains
authoritative. openPREY resolves that file through the usual search and pure-PK4
rules before it may substitute already prepared, immutable bytes. Parsing,
validation, and renderer/audio upload stay with the normal resource owner.
The worker framing step recognizes RIFF/WAVE, Ogg, PNG, and JPEG sources; DDS
and other formats remain opaque until their ordinary owner parses them.

Generated model, world, collision, and animation readers build private state
first and publish it only after the whole payload is valid. A stale, truncated,
corrupt, oversized, wrong-version, or otherwise mismatched cache is ignored;
the affected private file is removed where appropriate and openPREY loads the
original source instead. Packed MD5RProc map worlds remain on their source path
rather than being flattened into an incompatible world cache.

These files are disposable runtime data. They are not replacement assets, do
not change pure-server package negotiation, and must not be copied into retail
Prey (2006) PK4s.

## Location

Caches are written below the active game directory under `fs_savepath`, normally
`<fs_savepath>/basepr/`:

```text
generated/manifests/       learned per-map source lists
generated/models/          parsed render-model data
generated/worlds/          finalized classic .proc world data
generated/collision/       parsed/generated collision data
generated/animations/      parsed MD5 animation data
```

With the standard unified game directory, the full animation root is
`<fs_savepath>/basepr/generated/animations/`.

Manifest and model/world/collision filenames are opaque hashes of their
validated keys. Animation files retain the normalized source path and add a
`.banim` suffix. Moving cache files between installations is neither necessary
nor recommended; a different source package or setting can intentionally cause
a clean miss and rebuild.

Each animation cache records the source path, source size, timestamp, and
containing PK4 checksum where applicable. It stores fixed-width values and
floating-point arrays in a portable byte order; x64 and ARM64 builds use the same
format. A stale, truncated, corrupt, or mismatched cache is ignored and rebuilt
from the installed source animation. Loaded cache data becomes the normal runtime
animation data; openPREY does not retain a second permanent copy in memory.
Animation memory reporting also includes base-frame storage.

Learned preload identity for a loose file uses its normalized path, size, and
timestamp. A tool that deliberately preserves both size and timestamp while
rewriting a loose file can evade that preparation check; close openPREY and remove
the generated data, or disable `com_levelLoadCache`, when testing such edits.
PK4 members remain tied to the containing archive checksum.

## Controls

The engine master switch defaults off. The individual controls retain their
enabled defaults so an intentional experiment needs only the master switch:

```text
com_levelLoadModernization 0
com_levelLoadCache 1
com_levelLoadCacheWrite 1
com_levelLoadPreload 1
com_levelLoadCacheReport 0
```

- Set `com_levelLoadModernization 1` before loading a map to opt into all
  individually enabled engine cache paths.
- Set `com_levelLoadModernization 0` for the classic loading path. This master
  rollback overrides archived values from builds that previously enabled the
  individual controls by default.
- Set `com_levelLoadPreload 0` before loading a map to disable learned source
  preparation while retaining valid generated model/world/collision caches.
- Set `com_levelLoadCacheWrite 0` to stop new manifests and generated
  model/world/collision files from being written while valid existing files can
  still be read.
- Set `com_levelLoadCache 0` before loading a map to bypass learned manifests
  and generated model/world/collision caches completely.
- Set `com_levelLoadCacheReport 1` for per-map hit, miss, replay, byte,
  framing/integrity decode, cancellation, and staging/decoded-memory diagnostics
  in the log.

Advanced staging limits are available as
`com_levelLoadPreloadMaxEntries`, `com_levelLoadPreloadMaxFileMB`,
`com_levelLoadPreloadMaxStagingMB`, `com_levelLoadPreloadMaxDecodeMB`,
`com_levelLoadPreloadReadChunkKB`, and
`com_levelLoadPreloadDecodeChunkKB`. Their defaults are deliberately bounded;
increasing them can raise transient memory use and is not normally needed. The
normal owner can allocate its parsed representation in addition to the retained
source bytes, so these controls are pipeline limits rather than a cap on total
level-load memory.

Animation caches are owned by the unified game module. Both controls default to
enabled:

```text
g_useGeneratedAnimCache 1
g_writeGeneratedAnimCache 1
```

- Set `g_useGeneratedAnimCache 0` to bypass existing `.banim` files.
- Set `g_writeGeneratedAnimCache 0` to prevent new `.banim` files.
- Disable both for a source-parse benchmark.

## Clean rebuild and rollback

To force a clean rebuild, close openPREY and delete one or more of the
`generated/` subdirectories listed above under the active `fs_savepath`. openPREY
will recreate needed private data from the installed sources.

For a complete engine source-path comparison, leave `com_levelLoadModernization 0`
and disable both animation-cache controls.

Never delete the original `.proc`, `.cm`, model, image, sound, or
`models/**/*.md5anim` files from the Prey (2006) installation. If a map still fails
with all generated caches disabled, the problem is not caused by this cache
layer; include the active `fs_savepath` and `logs/openprey.log` when reporting it.

Developers and testers can find the exact key, ownership, validation, and
pending evidence contract in
[Level-Load Cache Modernization](../dev/loading-cache-modernization.md).
