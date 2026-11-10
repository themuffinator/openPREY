# Licensing

openPREY contains components under different licences. Source availability does
not make every component GPL-licensed or permit relicensing SDK-derived code.

| Component | Terms |
| --- | --- |
| Engine and engine-authored support code (everything under `src/` outside the game trees below) | [GNU GPL version 3](LICENSE), with retained per-file notices |
| SDK-derived game library in `src/game/`, `src/Prey/` and `src/preyengine/`, including openPREY's additions to it such as the multiplayer bots | [Prey Software Development Kit Limited Use License Agreement](LICENSES/PREY-SDK-EULA.rtf), with original notices and any explicit per-file third-party terms preserved |
| Third-party dependencies | Their own retained licences; see the individual source trees and Meson wraps |
| Retail Prey content | Not included or relicensed; users supply their own content |

The game library requires the full version of Prey. The SDK agreement restricts
commercial use and distribution and must accompany copies covered by it. Read
the complete agreement, rather than treating this overview as a grant of
additional rights.

The engine is open source; the SDK-derived game library is source available
under the SDK EULA. Neither licence is applied as an alternative to the other,
and the EULA is not imposed on independently GPL-covered engine source.

The [game import record](docs/dev/game-source-provenance.md) identifies the
imported sources and their accompanying notices. Consolidating the repositories
does not settle the compatibility of a linked binary distribution. No SDK
linking exception, rights-holder approval or legal compatibility opinion is
asserted by this documentation. Applicable distribution permissions remain a
separate question.
