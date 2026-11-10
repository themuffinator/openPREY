# Game source provenance

The canonical Prey game library now lives in this repository's `src/game/`,
`src/Prey/` and `src/preyengine/`. Its licence and authorship are unchanged by
the move. [LICENSING.md](../../LICENSING.md) distinguishes the SDK-derived game
code from the engine's GPL-covered code and dependencies.

## Import

- Source: [OpenPrey-GameLibs at `d224b083`](https://github.com/themuffinator/OpenPrey-GameLibs/tree/d224b083d70dddae1b8ba00081b4d72dedd8bc03),
  the published `main` merge of the `new-prey` branch tip `1ba2a0a`.
- The `src/game/`, `src/Prey/` and `src/preyengine/` trees were imported at
  their existing paths without source edits, so their relative includes still
  resolve against this repository's engine headers.
- The companion repository's copies of SDK engine headers (`src/idLib/`,
  `src/framework/`, `src/renderer/` and similar), its Visual Studio 2005
  projects and its `docs-user/` tree were never compiled by openPREY and are not
  imported. They remain available in the imported history.
- The complete companion history is a merge parent of the import commit and
  remains reachable from openPREY's history, so `git log --follow` traces each
  game file back to the original SDK import.
- The original `EULA.Development Kit.rtf` is retained byte-for-byte at
  [`LICENSES/PREY-SDK-EULA.rtf`](../../LICENSES/PREY-SDK-EULA.rtf).

Subsequent modifications are identified by openPREY's commit history. Source
relocation does not grant an alternative licence or remove original notices.
The SDK-derived game implementation is credited to Human Head Studios,
id Software and the openPREY contributors.

## Content boundary

No retail Prey game data is committed or distributed with the game-source move.
Runtime discovery reads user-supplied content.
