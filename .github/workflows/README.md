# openPREY workflows

`openprey-validation.yml` is the active build and validation workflow. Its Windows and
Linux jobs build the engine, dedicated server, GL and Vulkan renderer modules, and the
canonical unified `game_<arch>` module from the in-tree `src/game/`, `src/Prey/` and
`src/preyengine/` sources. It also checks the game source inventory and content pack
table, the `basepr/` runtime layout, the high-risk rebase source contracts, and
openPREY desktop/icon payloads.

The inherited OpenQ4 commit, push, ARM64, macOS, Universal2, and manual-release
workflows are retained only as static-test/reference fixtures. They are manual-only,
clearly named `DISABLED`, and every job has an unconditional false gate because they
still assume openQ4's split `game-sp`/`game-mp` modules and Quake 4 content. Remove those
gates only after rebuilding source pinning, package assertions, signing, and runtime
smoke tests around the in-tree game library, `game_<arch>`, and `basepr/`.
`android-build.yml` came with the upstream engine merge; openPREY does not target
Android, so it is likewise not part of active validation.

`discord-release.yml` only reacts to an already-published release. It does not build or
publish artifacts.
