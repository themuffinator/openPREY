# macOS MoltenVK Vulkan Renderer — staged plan

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Updated: 2026-07-25

Status: M0-M3 landed; M4-M8 staged. Defaults-neutral throughout — OpenGL
remains the macOS default renderer in both package variants at every stage, and
`r_renderApi best` resolves to `gl` on macOS at every stage.

Decision gate cleared by this work:
[../macos-moltenvk-decision.md](../macos-moltenvk-decision.md).
Parent renderer plan: [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md)
(this plan resolves that plan's macOS carve-out, risk 4).

## Goal

Let openQ4's existing Vulkan renderer module run on macOS through MoltenVK, a
Vulkan-on-Metal translation layer, as an opt-in `r_renderApi vulkan` selection
bundled inside the two existing macOS packages.

Non-goals, restated so they cannot drift:

- No native Metal renderer. The native-Metal decision gate stays closed.
- No change to the macOS default renderer.
- No third macOS package variant and no new `macos_graphics_bridge` value.
- No macOS support-claim promotion. macOS stays experimental Apple
  Silicon/arm64.

## Constraints That Shaped Every Stage

- **No Apple hardware and no local macOS access.** Everything below is
  developed and regression-tested from Windows against static guards and hosted
  CI. See [2026-06-30-apple-support-no-macos-access.md](2026-06-30-apple-support-no-macos-access.md).
- **macOS 11.0 floor.** This is what pins MoltenVK to v1.4.1 and makes a
  routine-looking dependency bump a ship-breaking change.
- **The macOS client still links a full second copy of the renderer
  statically.** A loaded renderer module therefore carries duplicate
  renderer/idlib symbols, so its export surface must be exactly one symbol or
  the two copies interpose at `dlopen` time.
- **Two halves must agree on one Vulkan library.** The engine creates the
  surface through SDL; the module creates the instance through volk. On Windows
  and Linux there is only one loader and the problem does not exist; on macOS it
  does, and it is undefined behavior when they disagree.
- **Token-pinned docs.** Many exact sentences across `docs/`, `README.md`, and
  `BUILDING.md` are asserted by `tools/tests/macos_*.py`. Documentation changes
  in this plan are additive; existing sentences stay byte-identical.

## Stages

### M0 — green the pre-existing macOS policy sweep — LANDED

The macOS sweep had red tests on `main` before any MoltenVK work started, which
made "the sweep is green" useless as an acceptance signal. M0 restored a known
baseline so every later stage could be judged against it.

Exit: `for t in tools/tests/macos_*.py; do python "$t"; done` green, except
`tools/tests/macos_dedicated_server_smoke.py`, which fails off-macOS by design.

### M1 — Vulkan portability correctness (all platforms) — LANDED

`src/renderer/Vulkan/VulkanDevice.cpp`:

- Presence-gated `VK_KHR_portability_enumeration` paired with
  `VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR`. The Khronos loader
  requires both before it will enumerate a portability ICD; a directly loaded
  `libMoltenVK.dylib` does not advertise the extension at all and fails instance
  creation if it is requested. Only a probe is correct for both shapes.
- Device-extension enumeration enabling `VK_KHR_portability_subset` when
  advertised, with `VkPhysicalDevicePortabilitySubsetFeaturesKHR` chained into
  `vkCreateDevice` so the enabled extension actually carries its features.
- A hard Vulkan 1.3 floor check with a readable diagnostic, because ~135
  core-1.3 entry points are called unconditionally.
- `maxBoundDescriptorSets >= 8`, which is exactly the Metal-backed ceiling.
- An R5G6B5 fallback probe instead of a hardcoded format assumption.

All of this is correct on Windows and Linux too — the probes are no-ops against
native drivers — so M1 is a portability-correctness fix that happens to unblock
macOS rather than a macOS special case.

### M2 — build the module on darwin — LANDED

`meson.build`, `meson_options.txt`, `subprojects/glew/meson.build`,
`tools/build/meson_setup.sh`, `tools/build/macos_renderer_module.exp`:

- The `build_renderer_vk` darwin carve-out is removed. The remaining gate is
  `platform_backend != 'sdl3'`, matching every other host.
- `glew_dedicated_dep` now exists on darwin: the Vulkan module links no GL but
  shares front-end translation units that reference GLEW symbols.
- darwin uses `shared_library()` with `name_suffix: 'dylib'`,
  `-Wl,-install_name,@loader_path/renderer-vk_<arch>.dylib`,
  `-Wl,-exported_symbols_list,tools/build/macos_renderer_module.exp`,
  `-Wl,-dead_strip`, `-Wl,-headerpad_max_install_names`, and
  `gnu_symbol_visibility: 'hidden'`.
- The export list contains only `_GetRenderAPI`.

Built artifact: `renderer-vk_arm64.dylib` / `renderer-vk_x64.dylib`.

### M3 — runtime discovery — LANDED

Two independent resolution problems, both invisible from Windows.

`src/renderer/RendererModule.cpp` — *finding the module*. `RM_ResolveModulePath`
now searches the executable directory, the platform's trusted module root, and
the package root. On macOS the executable lives in `openQ4.app/Contents/MacOS`
while signed Mach-O modules are staged flat in `Contents/Frameworks`, so the
executable directory alone never finds it. Search stays restricted to trusted
roots; renderer modules are never loaded from pak files, `fs_savepath`, or mod
content.

`src/renderer/Vulkan/VulkanDevice.cpp` and `src/sys/sdl3/sdl3_backend.cpp` —
*finding the same MoltenVK*. volk's Apple branch `dlopen`s bare leaf names,
which dyld resolves against DYLD paths and `/usr/local/lib` but never against
the app bundle, so a bundled MoltenVK is invisible to it; SDL, meanwhile, starts
at `@executable_path/../Frameworks/libMoltenVK.dylib`. `VK_Device_InitLoader()`
now mirrors SDL's precedence exactly — `SDL_VULKAN_LIBRARY`, then the bundled
dylib bundle-relative, in a loose package's `Frameworks/` child, or adjacent to
the executable, then `volkInitialize()` — and
`SDL3_PinBundledMoltenVKLibrary()` pins `SDL_HINT_VULKAN_LIBRARY` to the same
bundled path before the Vulkan window is created, deferring to any existing
pin. The adopted library is logged as `Vulkan: loader <path>`.

### M4 — MoltenVK acquisition and provider policy — IN PROGRESS

`tools/build/prepare_macos_moltenvk.sh` and
[../macos-moltenvk-provider-policy.md](../../../macos-moltenvk-provider-policy.md).

Pinned constants: MoltenVK `v1.4.1`, official Khronos `MoltenVK-macos.tar`
release asset, member
`MoltenVK/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib`, expected
architectures `arm64 x86_64`, minimum-OS ceiling `11.0`, dependency allowlist
`/System/Library/` and `/usr/lib/`, staged install name
`@executable_path/../Frameworks/libMoltenVK.dylib`.

Deliberately rejected sources: Homebrew `molten-vk` (architecture-thin, unpinned
Cellar install name) and the `MoltenVK-macos-privateapi.tar` variant.

The version pin is the ship-critical constant: v1.4.1 requires macOS 11.0, and
v1.4.2 raised the runtime floor to macOS 12.0, above openQ4's documented floor.
Bumping the pin without also executing the full floor change listed in
[../macos-support-matrix-policy.md](../../../macos-support-matrix-policy.md) would
silently drop macOS 11 users.

Outstanding, user-gated: the `MOLTENVK_TAR_SHA256` constant is a deliberate
placeholder. Every script mode except `--print-sha256` fails closed while it is
in place. Filling it in requires downloading the pinned asset and recording its
digest — see "Open Items" below.

### M5 — macOS packaging — IN PROGRESS

`tools/build/package_nightly.py` and `tools/build/assemble_macos_universal2.py`
stage `renderer-vk_<arch>.dylib` and `libMoltenVK.dylib` into
`openQ4.app/Contents/Frameworks`, alongside the existing signed
`game-sp_<arch>.dylib` and `game-mp_<arch>.dylib`, per
[../macos-package-layout-and-release-policy.md](../../../macos-package-layout-and-release-policy.md).

Both additions are nested code and must be signed inside-out with the Developer
ID Application identity before the outer app is signed and notarized. The
published MoltenVK dylib is ad-hoc signed only; an ad-hoc signature surviving
into a notarized package is a signing defect.

`renderer-vk` is merged by `lipo` for a future universal2 artifact like the
other code items. `libMoltenVK.dylib` is already universal and is compared for
identity across slices rather than merged, because merging two different
MoltenVK builds is not meaningful.

Both existing package variants receive the same payload. There is no third
download.

### M6 — policy decision gate and documentation — THIS STAGE

`docs/dev/archive/2026-10-18/macos-moltenvk-decision.md` is the design plan the "Native Metal
Decision Gate" in
[../macos-renderer-backend-policy.md](../../../macos-renderer-backend-policy.md)
requires. It answers all eight gate bullets for the MoltenVK-backed Vulkan
renderer, records the portability contract and the loader-agreement contract,
states the selection and rollback behavior, points at the provider policy, and
defines the release wording rules.

Additive documentation updates land with it:

- Additive sections in the four macOS policy documents, none of which rewrite an
  existing sentence.
- `docs/dev/platform-support.md` and `docs/dev/release-completion.md`.
- `README.md`, which previously described the Vulkan backend as native with no
  platform caveat — the clearest accidental policy violation in the tree.
- `BUILDING.md`, `docs/user/getting-started.md`,
  `docs/user/display-settings.md` (the canonical `r_renderApi` page, now
  documenting the complete legal value set), `docs/user/shadow-mapping.md`
  (an added platform-matrix row; the Apple legacy GL2.1 row is unchanged), and
  `assets/release/README.html`.
- The macOS carve-out paragraph in
  [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md) risk 4.

### M7 — policy tests and CI wiring — STAGED

`tools/tests/macos_moltenvk_policy.py` pins what no Windows or Linux build can
observe:

- Portability negotiation stays presence-gated on both the instance flag and the
  device subset extension.
- SDL and volk resolve the same Vulkan library in the same order.
- The macOS module exports only its entry point.
- Shadow-map and depth-writing shaders avoid the two GLSL constructs whose
  SPIRV-Cross to MSL translation Metal rejects: LOD/bias forms on shadow
  samplers, and `early_fragment_tests` with a `gl_FragDepth` write.
- The translation layer is never described as native Metal or native Vulkan in
  the release-facing documents.

Wiring: `tools/validation/openq4_validate.py`,
`.github/workflows/commit-validation.yml`,
`.github/workflows/push-verification.yml`, and
`.github/workflows/macos-debug.yml`.

### M8 — capability probe evidence and signoff plumbing — STAGED

Add the Vulkan-specific evidence fields to the macOS signoff record: bundled
MoltenVK version and archive digest, the `Vulkan: loader <path>` line,
`r_actualRenderApi`, the `gfxInfo` disposition and fallback block, the
`rendererVkProbe` device/caps report, and the signing status of both added
nested binaries.

A hosted-runner `rendererVkProbe` capability probe may be added as diagnostic
plumbing. Hosted macOS runners are virtualized, so a pass proves only the
loader/packaging contract and a failure may be a virtualization artifact. It
must be labeled diagnostic and must never be recorded as gameplay evidence.

## Standing Gate Per Stage

Every stage ends with:

- The macOS policy sweep green: `for t in tools/tests/macos_*.py; do python "$t"; done`
  with `OPENQ4_GAMELIBS_REPO` set, accepting the by-design off-macOS failure of
  `tools/tests/macos_dedicated_server_smoke.py`.
- `python tools/tests/renderer_validation_matrix.py` safe set N/N.
- A clean Windows Meson wrapper build.
- Unchanged default behavior. `r_renderApi gl` is the default everywhere and
  `best` resolves to `gl`; a stage that changes default rendering behavior is
  out of scope for this plan.

## Open Items (user-gated)

These are not oversights. Each needs something this project does not have.

1. **Fill in `MOLTENVK_TAR_SHA256`.** The pin is a deliberate fail-closed
   placeholder. Run `tools/build/prepare_macos_moltenvk.sh --print-sha256`
   (needs only `curl` and `shasum`, so it can run anywhere with network access)
   and paste the digest into the constant. Until then, macOS packaging cannot
   stage MoltenVK.
2. **Real Apple-hardware signoff for the opt-in path.** Nobody on the project
   has run MoltenVK-backed Vulkan on a Mac. There is no evidence that it renders
   correctly, and this plan does not claim there is. Required before any wording
   moves beyond "experimental, opt-in, may not work".
3. **Intel/AMD Mac coverage.** The MSL shadow-sampler translation restriction
   the static guard protects against only *manifests* on non-Apple GPUs. The
   guard prevents introducing the construct; it does not prove the existing
   shaders render correctly there.
4. **An Xcode GPU capture recipe.** RenderDoc cannot capture Metal, so macOS has
   no validated frame-capture workflow. Establishing one needs a Mac with Xcode.
5. **macOS Vulkan performance data.** None exists, and none may be claimed.
   Phase J promotion measurement policy applies to macOS unchanged.

## Rollback

- **Withdraw the option:** configure macOS packages with
  `-Dbuild_renderer_vk=false`. The module is not built or staged, path
  resolution fails, and the fail-closed ladder returns the user to OpenGL. The
  module and the translation layer travel together — packaging fails rather
  than shipping a module whose library is missing — so this is the single
  supported withdrawal path. Configure flag only: no source change, no default
  change, no user action.
- **Damaged user copy:** a package that loses `libMoltenVK.dylib` fails at
  loader init and falls back to OpenGL with a logged reason rather than failing
  to start.
- **Not needed for the default renderer**, because the default never moved.
