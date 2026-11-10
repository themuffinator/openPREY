# Licensing

openPREY contains components under different licences. Source availability does
not make every component GPL-licensed or permit relicensing SDK-derived code.

| Component | Terms |
| --- | --- |
| Engine and engine-authored support code (everything under `src/` outside the game trees below) | [GNU GPL version 3](LICENSE), retained per-file notices and the applicable [Doom 3](LICENSES/DOOM-3-ADDITIONAL-TERMS.txt) or [Doom 3 BFG](LICENSES/DOOM-3-BFG-ADDITIONAL-TERMS.txt) Additional Terms |
| SDK-derived game library in `src/game/`, `src/Prey/` and `src/preyengine/`, including openPREY's additions to it such as the multiplayer bots | [Prey Software Development Kit Limited Use License Agreement](LICENSES/PREY-SDK-EULA.rtf), with original notices and any explicit per-file third-party terms preserved |
| Third-party dependencies | Their own retained licences; see [dependency notices](LICENSES/), the individual source trees and the Meson wraps |
| Retail Prey content | Not included or relicensed; users supply their own content |

The game library requires the full version of Prey. The SDK agreement restricts
commercial use and distribution and must accompany copies covered by it. Read
the complete agreement, rather than treating this overview as a grant of
additional rights.

The engine is open source; the SDK-derived game library is source available
under the SDK EULA. Neither licence is applied as an alternative to the other,
and the EULA is not imposed on independently GPL-covered engine source.

The engine is derived from [openQ4](https://github.com/themuffinator/openQ4),
whose engine history is merged into this repository's history. Quake 4
SDK-derived game code from openQ4 (`src/mpgame/` and openQ4's `src/game/`) and
the Quake 4 SDK agreement are deliberately not part of openPREY.

The [source provenance inventory](docs/dev/source-provenance.md) and the
[game import record](docs/dev/game-source-provenance.md) identify the sources
and accompanying notices. Consolidating the repositories does not settle the
compatibility of a linked binary distribution. No SDK linking exception,
rights-holder approval or legal compatibility opinion is asserted by this
documentation. Applicable distribution permissions remain a separate question.
