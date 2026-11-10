# macOS Runtime And Renderer Closure Plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Updated: 2026-07-11

## Evidence Reviewed

This pass correlates two different tester outcomes instead of treating them as
one crash:

- The supplied console screenshot reaches game-module/script initialization,
  clamps `_forwardRenderAlbedo` and `_forwardRenderDepth` from 8x to 4x MSAA,
  and then terminates at `idRenderTexture::InitRenderTexture`. This is an
  offscreen RGBA8 + packed depth/stencil framebuffer failure, not a failure of
  the SDL Metal system-console window.
- [Issue #73 comment 4939117217](https://github.com/themuffinator/openQ4/issues/73#issuecomment-4939117217)
  reaches gameplay but shows a flat gray scene. The then-default Apple quirk
  deliberately skipped every ARB2 light interaction and applied a 20% ambient
  rescue, so the reported image matches the implemented workaround.
- Earlier issue #73 results already used the simple ARB preference before the
  first-frame crash was bypassed. Restoring that path unchanged is therefore
  not an adequate fix; the automatic path must avoid the fragile program for
  ordinary stock geometry and harden the remaining client-memory fallback.

## Gap Register And Resolution

| Priority | Gap | Resolution in this pass |
| --- | --- | --- |
| P0 | Offscreen MSAA support was inferred from the window framebuffer and generic `GL_MAX_SAMPLES`; an incomplete FBO caused a generic fatal. | Render-target creation is nonfatal and diagnostic. The game retries effective samples down to `0`, records requested/effective values, and uses direct rendering if every attempt fails. |
| P0 | Apple GL 2.1 defaulted to no interaction lighting. | Mode `0` routes eligible stock surfaces through neutral GLSL 1.10 interactions and uses a guarded simple-ARB fallback per surface. Mode `3` retains emergency bypass only. |
| P0 | CPU vertex pointers could be interpreted as VBO offsets after another pass left an array/index buffer bound. | CPU-backed `Position` calls and frame boundaries establish zero buffer bindings; simple compatibility mode avoids packed MD5R interaction programs and prepares caches defensively. |
| P0 | Finder/LaunchServices CWD could hide the openQ4 runtime when retail assets were discovered elsewhere. | App-bundle launch derives and validates embedded `Contents/Resources` as `fs_cdpath`; retail auto-discovery remains `fs_basepath`, and older complete adjacent packages retain a compatibility fallback. |
| P1 | Script includes passed already-relative qpaths into an OS-path converter, producing a warning storm. | Engine and canonical GameLibs parsers recognize `baseoq4`, `q4base`, `fs_game`, `fs_game_base`, PK4 paths, and absolute paths explicitly. |
| P1 | Routine macOS jobs compiled and packaged but did not require a launch. | Both hosted bridge jobs run an assetless renderer smoke; release jobs launch the app executable from a Finder-style unrelated CWD and verify its package root. |
| P1 | Failure reports omitted the decisive FBO/MSAA/path/module lines. | The support collector preserves those diagnostics in `logs/renderer-summary.txt`. |
| P2 | Dependency builds could miss the advertised deployment floor outside release jobs. | The Bash Meson wrapper supplies and validates `MACOSX_DEPLOYMENT_TARGET`, defaulting to `11.0` on Darwin. |
| P2 | The Metal artifact could be mistaken for an alternate game renderer. | Policy and release notes continue to state that both variants use the OpenGL game renderer. |

## Validation Plan

Automated completion requires:

- Static macOS policy, renderer-corridor, package, support-intake, workflow, and
  qpath/MSAA regression tests.
- Windows engine plus canonical SP/MP GameLibs compilation to catch shared API
  and cross-platform regressions.
- A Windows SP map smoke with offscreen MSAA enabled, because main-menu startup
  is not sufficient renderer validation.
- Hosted macOS assetless launches for both bridge variants and packaged-app
  package-root smoke on the next CI/release run.

Real Apple completion remains evidence-gated and cannot be inferred from a
Windows checkout. Before closing issue #73 or promoting macOS beyond
experimental, record:

- OpenGL and Metal bridge SP map gameplay with visible dynamic lighting,
  characters, fog/blend lights, BSE effects, resize/fullscreen, Retina, and
  `vid_restart`.
- MP `mp/q4dm1` listen/client gameplay and module switching.
- `r_multiSamples 0`, `2`, `4`, `8`, and `16`, recording requested/effective
  target samples and any fallback status.
- Automatic mode `0`, diagnostic modes `1`/`2`, and emergency mode `3`.
- Mounted-DMG, copied-whole-package, Finder, Terminal, Gatekeeper, input,
  controller, audio-device, and display-mode checks.
- Separate signoff on the documented macOS floor and latest public macOS in
  `docs/dev/macos-signoff-evidence.md`.

## Deliberately Unchanged Scope

- The release remains Apple Silicon/arm64 only.
- The renderer work itself did not require a package migration; the later
  self-contained-app change now supports app-only `/Applications` installation
  with data under `Contents/Resources` and modules under `Contents/Frameworks`.
- Native Metal and the comparison-only native Cocoa/OpenGL backend are not
  promoted by this work. A native Metal renderer still requires a separate
  material/BSE/render-capture design and implementation plan.
