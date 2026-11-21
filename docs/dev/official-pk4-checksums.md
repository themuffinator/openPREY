# Official Prey (2006) PK4 Checksums

This document tracks the official PK4 checksum baseline used by openPREY startup validation.

## Status

openPREY now tracks two known official Prey base pack layouts:

1. Classic retail CD/DVD naming (`pak000` ... `pak004`).
2. Consolidated naming seen in legacy digital distributions (`pak_data`, `pak_sound`, `pak_en_v`, `pak_en_t`).

Both required sets are checked against the checksums below. The optional packs
remain presence-only (see "Additional Official PK4s" below).

## Capture Method

1. Launch openPREY against a clean Prey installation.
2. Enable startup logging (`logFile 2`) and inspect `logs/openprey.log` under `fs_savepath`.
3. Record `Loaded pk4 ... with checksum ...` lines.
4. Populate required and optional PK4 tables below.

The checksum is `idFileSystemLocal::LoadZipFile`'s: `MD4_BlockChecksum` over
`LittleLong( crc )` of every central-directory entry with a non-zero
uncompressed size.

## Required Baseline: Classic Naming

| PK4 | Checksum | Entries (non-empty) | Size (bytes) | MD5 |
|---|---|---|---|---|
| `base/pak000.pk4` | `0x7dc00ede` | 3318 (2948) | 310998499 | `4bff754ac14a4d9037b05b68189c0a78` |
| `base/pak001.pk4` | `0xd06647b1` | 6270 (5300) | 302809611 | `84c9ba4c9004810d7809d319f88fc48f` |
| `base/pak002.pk4` | `0x57dce443` | 5337 (4900) | 476183237 | `f224cf553d1d5d3c052588b231201951` |
| `base/pak003.pk4` | `0x263006fe` | 4111 (3943) | 307817095 | `e0616223c004d1168630eb72f0001f3d` |
| `base/pak004.pk4` | `0xcc075380` | 3739 (3692) | 286719959 | `4bfc3535f9716884f0d2035669804611` |

Sources, which agree on every value:

- Retail PC 3-CD set, five languages (ISO labels `PREY_DISC1` to `PREY_DISC3`,
  mastered 2006-06-13), read from the discs' `Setup/Data/Base` and again after
  installing and patching to 1.4: the 1.4 patch does not touch these packs
  (openPREY issue #37, with the capture harness and SHA-256 values).
- A Steam install (`steamapps/common/Prey 2006/base`), from its startup log
  (openPREY issue #36).

## Required Baseline: Consolidated Naming

| PK4 | Checksum |
|---|---|
| `base/pak_data.pk4` | `0xbe295ead` |
| `base/pak_sound.pk4` | `0xe0c27ee2` |
| `base/pak_en_v.pk4` | `0x952b910e` |
| `base/pak_en_t.pk4` | `0x6625f12d` |

## Additional Official PK4s (Optional)

Samples from the 3-CD install patched to 1.4; the Steam install logs the same
values.

| PK4 | Checksum | Entries (non-empty) | Size (bytes) | MD5 |
|---|---|---|---|---|
| `base/pak005.pk4` | `0xead35190` | 10 (7) | 235058 | `a7ab4b767f24d355bac5f03aa22f45d8` |
| `base/pak006.pk4` | `0xed8ce397` | 108 (70) | 18855657 | `bb180f9df643de2a70fe233366dcb864` |
| `base/pak020.pk4` | `0x39191193` | 23 (16) | 19746 | `8da7fc40a507fdecbb8ea290c49f04f6` |
| `base/pak040.pk4` | `0x40dd9bb5` | 468 (453) | 6850847 | `a88e4eeb00634c9893e2ba06b195fd8f` |
| `base/game00.pk4` | `0xff851bf2` | 2 (2) | 1697374 | `885d7117d55f2242cdba3b2e665842b7` |
| `base/game01.pk4` | `0xa208af14` | 2 (2) | 2722496 | `e60bd8170112a6546aeb24d14f0bc098` |
| `base/game02.pk4` | `0xaa46eb08` | 10 (6) | 5885875 | `4dc3de25f17507e84b946d67f328d574` |
| `base/game03.pk4` | `0x39a5ed9c` | 2 (2) | 1683408 | `62b243839cbeabec70285617ddb824bc` |

Known variant: the disc's own `game00.pk4`, before an official update replaces
it, is `0xe0be2928` (2 entries, 1685372 bytes, MD5
`8e0e97222c7bc932f2fd7aef9ccd6235`).

## Notes

- Checksum format is the engine PK4 checksum generated in `src/framework/FileSystem.cpp`.
- The consolidated checksums were captured from an installed retail-media layout via openPREY runtime logging (`Loaded pk4 ... checksum ...`).
- The optional packs stay presence-only (`0` in `officialPk4s[]`): patches
  replace some of them (`game00.pk4` above), and installs at patch levels
  before 1.4 have not been catalogued. A pinned value would refuse those.
- Keep this list synchronized with any strict validation policy changes.
