# macOS MoltenVK Renderer Decision

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Updated: 2026-07-25

This is the separate renderer design plan required by the "Native Metal Decision
Gate" in [macos-renderer-backend-policy.md](../../macos-renderer-backend-policy.md)
and by the "Native Metal Boundary" in
[macos-native-backend-containment-policy.md](../../macos-native-backend-containment-policy.md).
It covers exactly one thing: allowing openQ4's existing Vulkan renderer module
to run on macOS through MoltenVK, a Vulkan-on-Metal translation layer.

It does **not** propose a native Metal renderer, and it does not change the
macOS default renderer. Both macOS package variants keep the stock-compatible
openQ4 OpenGL renderer as their default and recommended path.

The staged implementation record for this decision is
[plans/2026-07-25-macos-moltenvk.md](plans/2026-07-25-macos-moltenvk.md).

## Decision Summary

| Question | Decision |
|---|---|
| New macOS rendering API | Vulkan through MoltenVK, a Vulkan-on-Metal translation layer |
| Native Metal renderer | **Not selected.** Still out of scope; the gate above stays closed for native Metal |
| macOS default renderer | **OpenGL**, unchanged, in both package variants |
| How Vulkan is selected on macOS | Opt-in only: `r_renderApi vulkan`, applied at the next engine start |
| `r_renderApi best` on macOS | Resolves to `gl`, unchanged |
| New package variant | **None.** The existing `OpenGL` and `Metal bridge` packages both carry the module; there is no third download |
| macOS support claim | Unchanged by this decision: **experimental** Apple Silicon/arm64 at the time. The platform became a preview on 2026-09-18 (see [platform-support.md](../../platform-support.md#support-tiers)); macOS Vulkan stayed experimental |
| Rollback if it goes wrong | Ship-time: drop the module and dylib from staging. Run-time: the fail-closed ladder, which probes the Vulkan device before activating the module, falls back to OpenGL by itself; a window or surface failure after activation stops that launch and leaves the next one on OpenGL |

## Why A Translation Layer And Not Native Metal

The gate exists because a second macOS rendering API is expensive. MoltenVK is
admitted and native Metal is not, for reasons that are about cost and coverage,
not about preference:

- **The renderer already exists.** `renderer-vk_<arch>` is a full renderer
  behind the module ABI described in
  [plans/2026-07-16-vulkan-renderer.md](plans/2026-07-16-vulkan-renderer.md).
  Admitting macOS is a build/packaging/loader change plus portability
  negotiation. A native Metal renderer would be a second complete renderer with
  its own shader pipeline, resource model, capture story, and parity debt.
- **The shader corpus is already SPIR-V.** The Vulkan module consumes offline
  GLSL to SPIR-V built from the same shader-kind and permutation keys the modern
  GL shader library uses. MoltenVK re-translates that SPIR-V to MSL at pipeline
  creation. A native Metal renderer would need a third authored shader family.
- **Parity work is shared, not duplicated.** Every stock-content fix landed for
  Windows/Linux Vulkan applies unchanged to macOS. Native Metal would fork the
  parity effort permanently.
- **Apple hardware is not available to this project.** A rendering path that
  only exists on macOS could not be developed or regression-tested at all.
  MoltenVK-backed Vulkan is developed and regression-tested on Windows/Linux and
  differs on macOS only by the translation layer and the portability subset.
- **It is reversible.** MoltenVK is a bundled dependency behind an opt-in cvar.
  Withdrawing it is a packaging change. Withdrawing a native Metal renderer
  would mean deleting a renderer.

MoltenVK is a translation layer. It is not native Metal, it is not a Metal
renderer, and it is not a native Vulkan driver. Shipping it does not make openQ4
on macOS OpenGL-free either. Docs, package names, release notes, and commit
messages must all keep that distinction;
`tools/tests/macos_native_backend_containment.py` and
`tools/tests/macos_moltenvk_policy.py` enforce it.

## Decision-Gate Answers

The eight bullets below are the gate template from
[macos-renderer-backend-policy.md](../../macos-renderer-backend-policy.md), answered
for the MoltenVK-backed Vulkan renderer.

### Stock Quake 4 material, shader, interaction, and lighting parity

Parity is the Vulkan renderer's parity, inherited whole. macOS adds no separate
content path, no macOS-only material handling, and no replacement assets.

What that inherits today, per the phase records under `docs/dev/plans/`:

- World geometry, depth prepass, ambient and flat materials, portals, and
  skybox (Phase E).
- Interaction lighting and shadow maps, including the clustered light binning
  and the shared shadow planner (Phase F).
- Stencil shadows and fog and blend lights (Phase G; its light-grid pass was
  deferred, and Vulkan still has none), with the 2026-07-24 stock shadow-path
  closure covering point,
  projected, parallel, and global lights across static, animated, packed MD5R,
  two-sided, and perforated/hashed-alpha casters.
- The stock material-program families: the environment, monochrome, and
  heat-haze ARB families; the displacement, depth/blur, ghost, sniper, multiply,
  MedLabs, and AL GLSL families; and guide-driven parallax, custom lighting,
  water, and refractive glass.
- Render-texture commands, captures, readback, MSAA resolve, and SMAA
  (Phase H). The gamma pass, the classic post chain, and MSAA
  alpha-to-coverage have no Vulkan version yet (corrected 2026-09-18).

What is still open is also inherited, not macOS-specific: Phase I long-tail
coverage and the Phase J optimization and promotion evidence. Vulkan remains
experimental on every platform, so macOS gains an experimental renderer inside
an experimental platform. That double-experimental status is why the default
does not move.

The macOS-specific parity risk is **not** content: it is translation. Two
classes matter and are guarded statically because they cannot be reproduced from
Windows:

- Shadow-sampler LOD forms. SPIRV-Cross gates `textureGrad` and bias arguments
  on shadow samplers by MSL version rather than GPU family, so those forms emit
  MSL that Metal rejects on Intel/AMD Macs. That is a pipeline-creation failure
  at run time and invisible at build time.
- `early_fragment_tests` combined with a `gl_FragDepth` write, which is a hard
  MSL compile error, and conditional depth layout qualifiers, whose behavior
  under Metal is not predictable.

`tools/tests/macos_moltenvk_policy.py` rejects both classes in
`src/renderer/Vulkan/shaders/`, so a future shader edit cannot silently break
macOS from a Windows workstation.

### BSE effect rendering and lifetime behavior

BSE is not a backend feature and does not change here.

`rvBSEManager` and `RenderWorld` own effect spawning, update, expiry, and the
`renderEffect_t` lifetime contract in the API-neutral engine core. Effects reach
any renderer as ordinary draw surfaces carrying `DSF_BSE_EFFECT`, with
soft-particle eligibility expressed through `STF_SOFT_PARTICLE_CANDIDATE` and
ordering constraints (additive BSE layers held until after fog) applied in the
shared frontend. The Vulkan backend consumes that same surface stream and
implements the soft-particle stage check in `src/renderer/Vulkan/vk_Backend.cpp`.

Consequences for this decision:

- MoltenVK sees only pipelines and draws. It has no BSE-specific surface.
- A BSE regression under Vulkan on macOS is either a Vulkan-renderer regression
  (reproducible on Windows/Linux) or a translation defect in the material
  program a given effect stage uses. Triage starts by reproducing on Windows.
- No macOS-only BSE lifetime, budgeting, or expiry behavior is introduced. Any
  proposal to add one must come back through this gate.

### Shader translation or replacement strategy

**Translation, in two stages, with no macOS-authored shaders.**

1. Offline, at build time: the shared GLSL sources under
   `src/renderer/Vulkan/shaders/` compile to SPIR-V through glslang, keyed by
   the same shader-kind and permutation key the modern GL shader library uses.
   The shipped `.spv` payload is identical on Windows, Linux, and macOS.
2. At run time on macOS: MoltenVK translates that SPIR-V to MSL through
   SPIRV-Cross during `vkCreateGraphicsPipelines`, and Metal compiles the MSL.

No macOS-specific shader source, no hand-written MSL, and no replacement content
are introduced or permitted by this decision. The single macOS-facing rule is
the authoring restriction described above: shared shader sources must stay
inside the subset SPIRV-Cross can translate to MSL that every Metal family
accepts, and the static guard enforces it.

Two second-order consequences are accepted:

- **Pipeline-creation cost.** Translation plus MSL compilation happens on the
  first use of each pipeline. The existing `VkPipelineCache` persistence and
  level-load warm-up already exist for this reason and are the mitigation.
- **Late failure.** A shader that translates badly fails at
  `vkCreateGraphicsPipelines`, not at build time. That failure surfaces as a
  Vulkan validation/creation error; the draw then reuses another cached
  pipeline or is skipped, and nothing falls back to OpenGL at that point.

Replacement — authoring MSL or a Metal-specific shader family — is explicitly
rejected. It would recreate the native-Metal cost this decision exists to avoid.

### Screenshot, readback, video, and diagnostic capture behavior

Unchanged from the Vulkan renderer; no macOS-specific capture path is added.

- Screenshots, tiled readback, `envshot`, crop/capture-to-image, and scene
  feedback captures (`_currentRender`, `_currentDepth`, SSAO depth, subview RTT)
  are explicit copy/blit operations at the same pass-order points the GL
  renderer uses, with readbacks through host-visible buffers and frame-deferred
  maps. Phase H made the swapchain transfer-source-capable so readback produces
  real images rather than the earlier stub.
- Save-game preview capture does not present its temporary cropped frame.
- ROQ cinematic streaming upload uses the ordinary image-upload path.

MoltenVK does not change the ordering or the API surface of any of these; it
translates the copy and blit commands. The macOS-specific consideration is
format support, not behavior: Metal-backed devices do not expose every
`VkFormat`, so format selection must probe rather than assume. That is why
`VulkanDevice.cpp` carries an R5G6B5 fallback probe instead of a hardcoded
format assumption.

Video recording is unchanged and remains outside the renderer module.

### RenderDoc or Xcode GPU capture workflow

This is the weakest square of the plan and is documented as such rather than
overstated.

- **RenderDoc does not support Metal.** A MoltenVK-backed run on macOS cannot be
  captured with RenderDoc. The existing
  [RenderDoc workflow](../../renderdoc-workflow.md) and the `renderDocCapture` console
  command remain Windows/Linux tools.
- **Primary capture strategy is off-macOS.** The SPIR-V payload, the pipeline
  keys, the descriptor layout, and the command stream are the same on every
  platform. Capture on Windows or Linux Vulkan, where RenderDoc works fully,
  and treat macOS as the translation delta only.
- **Xcode Metal frame capture** is the only macOS-side option, and it captures
  the *translated* Metal command stream, not the Vulkan stream: buffers,
  pipelines, and shaders appear as Metal objects and MSL. It requires launching
  the app with Metal capture enabled and is therefore a developer-build activity
  on a Mac with Xcode, not something a packaged release run can do.
- **The project has no Apple hardware.** Neither an Xcode capture workflow nor a
  MoltenVK-specific capture has been performed or validated by this project.
  This plan does not claim one. Establishing a working Xcode capture recipe is
  an open item that requires a contributor with a Mac; until then, macOS-only
  visual defects are triaged from logs, `gfxInfo`, screenshots, and support
  archives.
- **MoltenVK's own diagnostics** (its configuration and logging surface) are the
  practical substitute for a capture on a user's machine, because they can be
  requested through a bug report instead of requiring hardware access.

### Performance counters, renderer metrics, and failure diagnostics

Inherited from the Vulkan renderer, with macOS-specific caveats recorded rather
than papered over.

Available:

- GPU pass timings through `vkCmdWriteTimestamp2` pools per frame slot behind
  the existing metrics interface, and `VK_EXT_debug_utils` labels/scopes behind
  the shared RAII debug-scope API.
- Vulkan validation behind `r_vkValidation`, with error signatures recognized by
  the renderer validation matrix runner.
- `gfxInfo` reports the requested API, the actual API, the resolved module path,
  the load/fallback disposition, and the fallback reason.
- `rendererVkProbe` loads the module on demand, prints the instance, device,
  queue, and caps report, and unloads without committing the renderer. It
  refuses while Vulkan is the active renderer: loading the module then returns
  the live instance, which the probe's shutdown would tear down.
- `rendererModuleSelfTest` and the `rendererVk*SelfTest` family run in the safe
  validation matrix and need no device for the selection/ladder cases.
- The MoltenVK loader path prints the dylib it actually adopted
  (`Vulkan: loader <path>`), which is the single most useful line when
  diagnosing a mismatched or missing translation layer.

macOS caveats:

- Validation layers are not bundled. `r_vkValidation` is only meaningful when a
  developer supplies a Vulkan SDK loader through `SDL_VULKAN_LIBRARY`, which
  both halves of the engine then follow (see the loader agreement below).
- Timestamp period and queue-timestamp support are device-reported and pass
  through the translation layer. Treat Vulkan GPU timings on MoltenVK as
  relative indicators, not as absolute Metal-level measurements, and never as
  cross-platform performance evidence.
- No performance claim, comparison, or promotion evidence for macOS may be made
  from hosted CI. Phase J promotion measurement policy (5-run p50/p95/p99 A/B
  per scene and preset) applies to macOS exactly as it does elsewhere, and macOS
  has none of it.

### Fallback and rollback behavior when the renderer cannot initialize

The fail-closed ladder in `src/renderer/RendererModule.cpp` is the mechanism,
and it is the same one Windows and Linux use. `R_RendererModule_BuildFallbackLadder`
places the requested API first and always terminates on GL, so every failure
the ladder sees lands on the proven OpenGL renderer with its own safe-mode
retry loop. Before a module activates, the ladder runs the module's own device
probe (`RunDeviceSelfTest`, the quiet form of `rendererVkProbe`). The probe
resolves the Vulkan library through `VK_Device_InitLoader`, as the renderer
does, then creates an instance and a device without touching a window, so a
probe failure is one more fallback class. It destroys the device at once but
keeps the instance until the renderer has created its own, so the Vulkan
drivers stay loaded in between, and it stops at the first device that meets
the requirements. The ladder ends once a module is active. Device bring-up
that fails after that point, in window, surface, or swapchain creation, calls
`FatalError( "Vulkan renderer device initialization failed; ..." )`. Before
that it appends `seta r_renderApi "gl"` to the saved config, so the next
launch starts on OpenGL. Until 2026-09-18 there was no probe: every device
failure took the fatal path and left `vulkan` archived, so each relaunch
failed the same way (issue #96).

Failure classes, each of which warns, records a fallback reason, and continues:

| Failure | Recorded reason |
|---|---|
| Selection changed while the engine is running | `renderer module activation requires an engine restart` |
| Module not found in any trusted root | `module path resolution failed` |
| `dlopen` of the module failed | `module load failed` |
| No `GetRenderAPI` entry point | `missing GetRenderAPI entry point` |
| Export rejected, or diagnostics-only bring-up export | logged with `falling back to OpenGL. Use rendererVkProbe to inspect it.` |
| Device probe failed: no Vulkan library, no driver or GPU, a device below the requirements, or device creation | `device probe failed: <probe summary>`, for example `device probe failed: no Vulkan loader` |

macOS-specific failure classes. The device probe catches the first three
before the module activates, so each falls back to OpenGL with its reason
recorded.

- `libMoltenVK.dylib` missing from the bundle, so `VK_Device_InitLoader` finds no
  loader and `volkInitialize()` fails.
- `vkCreateInstance` returning `VK_ERROR_INCOMPATIBLE_DRIVER` because portability
  enumeration was not negotiated (guarded by the presence-gated flag pairing).
- A device below the Vulkan 1.3 floor, or below
  `VK_REQUIRED_BOUND_DESCRIPTOR_SETS = 8`, which is exactly the Metal-backed
  ceiling. Both fail closed with a readable message rather than faulting on a
  null volk pointer during the first frame.
- A pipeline that fails MSL translation or Metal compilation at creation time.
  This one is not a startup failure: pipeline creation logs
  `Vulkan: pipeline creation failed`, and the draw then reuses another
  cached pipeline or is skipped.

Module search is restricted to trusted roots — the executable directory, the
platform module root (`openQ4.app/Contents/Frameworks` on macOS), and the
package root. Renderer modules are never loaded from pak files, `fs_savepath`,
or mod content.

Rollback:

- **User rollback:** set `r_renderApi gl` and restart the engine. Because the
  cvar is `CVAR_ARCHIVE`, this persists. A start that fails the device probe
  renders with OpenGL and keeps the `vulkan` selection, so the next launch tries
  again. A start that fails after activation stops the engine, but first
  appends `seta r_renderApi "gl"` to the saved config, so the next launch uses
  OpenGL; only a `+set r_renderApi vulkan` launch option can select Vulkan
  again then.
- **Project rollback:** configure macOS packages with
  `-Dbuild_renderer_vk=false`. The module is not built or staged, module path
  resolution fails, and the ladder returns to OpenGL. The module and the
  translation layer must travel together — packaging fails rather than shipping
  a module whose library is missing — so this is the single supported way to
  withdraw the option. It is a configure-flag change: no source change, no
  default change, no user action.
- **Damaged user copy:** if a user's package loses `libMoltenVK.dylib` (a
  partial copy, a stripped archive), `r_renderApi vulkan` fails the device
  probe at loader init, logs the reason, and falls back to OpenGL. Before
  2026-09-18 it stopped with `Vulkan renderer device initialization failed`
  instead (issue #96).
- **No rollback is needed for the default renderer**, because the default never
  moved. That is the core safety property of this decision.

### Package naming, release notes, and signoff evidence

**Package naming.** No new package variant, no new package name, no new
`macos_graphics_bridge` value, and no third download. The existing two macOS
package variants — `OpenGL` and `Metal bridge` — each carry the renderer module
and the bundled translation layer, and each defaults to OpenGL. Artifact names
in [macos-support-matrix-policy.md](../../macos-support-matrix-policy.md) are
unchanged. Inside the bundle, the additions are:

```text
openQ4.app/Contents/Frameworks/renderer-vk_<arch>.dylib
openQ4.app/Contents/Frameworks/libMoltenVK.dylib
```

Both live in `Contents/Frameworks`, which Apple treats as a nested-code
location, alongside the existing signed `game-sp_<arch>.dylib` and
`game-mp_<arch>.dylib` modules, per
[macos-package-layout-and-release-policy.md](../../macos-package-layout-and-release-policy.md).
The renderer module is built as a `shared_library` with
`-Wl,-install_name,@loader_path/renderer-vk_<arch>.dylib`, hidden symbol
visibility, dead stripping, `-headerpad_max_install_names`, and an export list
(`tools/build/macos_renderer_module.exp`) that exports only `_GetRenderAPI` —
necessary because the macOS client still links a full second copy of the
renderer statically, and any additional exported symbol would interpose at
`dlopen` time.

**Release notes.** Wording rules are in "Release Wording Rules" below.

**Signoff evidence.** The existing macOS evidence contract in
[macos-support-matrix-policy.md](../../macos-support-matrix-policy.md) and
[macos-signoff-evidence.md](../../macos-signoff-evidence.md) applies unchanged, and
Vulkan adds fields rather than replacing any:

- The bundled MoltenVK version and the SHA-256 of the exact archive consumed.
- The `Vulkan: loader <path>` line proving which dylib was adopted.
- `r_actualRenderApi` and the `gfxInfo` disposition/fallback block.
- The `rendererVkProbe` device/caps report from the machine under test.
- Whether the run is OpenGL-default (the release-relevant case) or an explicit
  `r_renderApi vulkan` opt-in run.
- Signing and notarization status of `libMoltenVK.dylib` and
  `renderer-vk_<arch>.dylib` as nested code inside the signed app.

A macOS Vulkan signoff never substitutes for the macOS OpenGL signoff. The
OpenGL and Metal bridge package evidence required before macOS can move to
first-class is unchanged by this decision.

## The Vulkan Portability Contract

macOS has no Vulkan driver of its own; MoltenVK is a portability
implementation, and Vulkan requires that to be negotiated explicitly. The
contract, implemented in `src/renderer/Vulkan/VulkanDevice.cpp` and pinned by
`tools/tests/macos_moltenvk_policy.py`:

- **Instance.** `VK_KHR_portability_enumeration` is a *loader* extension. The
  Khronos loader advertises it and requires both the extension and
  `VK_INSTANCE_CREATE_ENUMERATE_PORTABILITY_BIT_KHR` before it will enumerate a
  portability ICD; otherwise `vkCreateInstance` fails with
  `VK_ERROR_INCOMPATIBLE_DRIVER`. A directly loaded `libMoltenVK.dylib` does not
  advertise it at all, and requesting it there fails with
  `VK_ERROR_EXTENSION_NOT_PRESENT`. Only a presence check is correct for both
  shapes, so the extension is probed and the flag is set if and only if the
  extension is present. This is a no-op on native Windows and Linux drivers.
- **Device.** `VK_KHR_portability_subset` must be enabled when the physical
  device advertises it (VUID-VkDeviceCreateInfo-pProperties-04451), and must not
  be requested when it does not. Enabling it without chaining
  `VkPhysicalDevicePortabilitySubsetFeaturesKHR` into `vkCreateDevice` would
  leave every optional portability behavior disabled, so the queried feature
  struct is the one handed to device creation.
- **Version floor.** Vulkan 1.3 is a hard floor because roughly 135 core-1.3
  entry points are called unconditionally. MoltenVK has supported Vulkan 1.3
  since 1.3.0 and advertises 1.4 in the 1.4.x line, so the floor is satisfied by
  the pinned provider; the check exists so an under-spec device fails closed
  with a readable message.
- **Descriptor sets.** `maxBoundDescriptorSets >= 8` is required. Eight is
  exactly the ceiling on Metal-backed devices, so this is a real gate rather
  than a formality.
- **Formats.** Format support is probed, not assumed. The R5G6B5 fallback probe
  exists because Metal-backed devices do not expose the same `VkFormat` set as a
  desktop Vulkan driver.

### Loader agreement (the single most dangerous macOS-only bug class)

The engine creates the presentation surface through SDL, and the renderer module
creates the `VkInstance` through volk. If those two resolve *different* Vulkan
libraries, one `VkInstance` is shared across two images, which is undefined
behavior — and it is invisible on Windows and Linux because there is only ever
one loader there.

volk's Apple branch `dlopen`s bare leaf names, which dyld resolves against DYLD
paths and `/usr/local/lib` but never against the app bundle, so a MoltenVK
shipped inside `openQ4.app/Contents/Frameworks` would be invisible to it. SDL,
meanwhile, starts its search at `@executable_path/../Frameworks/libMoltenVK.dylib`.
Left alone, the two halves would disagree on a normal package.

Both halves therefore follow the same precedence:

1. `SDL_VULKAN_LIBRARY` (the environment backing of `SDL_HINT_VULKAN_LIBRARY`).
2. The bundled MoltenVK, bundle-relative (`../Frameworks/libMoltenVK.dylib`),
   then in a `Frameworks/` directory beneath a loose package root, then
   adjacent to the executable (`libMoltenVK.dylib`).
3. Whatever the system loader provides (`volkInitialize()`).

`SDL3_PinBundledMoltenVKLibrary()` in `src/sys/sdl3/sdl3_backend.cpp` pins
`SDL_HINT_VULKAN_LIBRARY` to the same bundled path before the Vulkan window is
created and defers to an existing pin, and `VK_Device_InitLoader()` adopts the
resolved library through `volkInitializeCustom`. A developer who points
`SDL_VULKAN_LIBRARY` at a Vulkan SDK loader — to get validation layers — moves
both halves together.

## Renderer Selection On macOS

`r_renderApi` is `CVAR_RENDERER | CVAR_ARCHIVE` and takes effect at the next
engine start, not on `vid_restart`. The complete legal value set is:

| Value | Meaning |
|---|---|
| `best` | Platform default. Resolves to `gl` on every platform, including macOS, until Vulkan promotion evidence and explicit sign-off land |
| `gl` (alias `opengl`) | The OpenGL renderer — the default, and the recommended renderer on macOS |
| `vulkan` (alias `vk`) | The Vulkan renderer module. On macOS this runs through MoltenVK |
| `gl-module` | Alias that always selects the OpenGL renderer module rather than a statically linked GL renderer |

`r_actualRenderApi` is `CVAR_ROM` and reports what actually initialized, so a
silent fallback is always visible.

On macOS specifically:

- OpenGL is the default in both package variants. Nothing about a default
  install changes.
- Vulkan is opt-in and experimental, on top of a platform that is itself
  only a preview.
- `best` stays `gl`. Promotion of `best` on macOS would require its own
  evidence and sign-off, exactly as it does on Windows and Linux, plus the macOS
  hardware evidence this project does not have.
- The user-facing description lives in
  [../user/display-settings.md](../../../user/display-settings.md).

## Sourcing, Bundling, And Signing

The full provider policy — pinned version, archive digest, acquisition script,
and refresh procedure — is recorded in
[macos-moltenvk-provider-policy.md](../../macos-moltenvk-provider-policy.md). The
load-bearing constraints this decision depends on:

- **Pin MoltenVK v1.4.1.** v1.4.1 requires macOS 11.0. v1.4.2 raised the runtime
  floor to macOS 12.0, which is above openQ4's documented macOS 11 floor and
  `MACOS_MIN_SYSTEM_VERSION`. Upgrading past 1.4.1 without also moving the
  project's macOS floor — through the full multi-file floor change listed in
  [macos-support-matrix-policy.md](../../macos-support-matrix-policy.md) — would ship
  a package that fails to launch on the floor the project advertises. This is
  the single most likely way to break the release, and it looks like routine
  dependency maintenance.
- **Use the official Khronos release asset** `MoltenVK-macos.tar` for the pinned
  tag, verified by SHA-256. The usable library is inside it at
  `MoltenVK/MoltenVK/dynamic/dylib/macOS/libMoltenVK.dylib`.
- **Do not use `brew install molten-vk`.** It is architecture-thin and installs
  with an unpinned Cellar install name, so it is neither reproducible nor
  universal.
- **Do not ship the `MoltenVK-macos-privateapi.tar` variant.** It links Apple
  private API and is unsuitable for a distributed package.
- **License.** MoltenVK is Apache-2.0. Redistribution is allowed with
  attribution, which must appear in the package documentation and license
  collateral.
- **Binary shape.** The release dylib is genuinely universal (arm64 and
  x86_64), its published install name is `@rpath/libMoltenVK.dylib`, it has no
  `LC_RPATH` entries and no rpath-based dependencies of its own, and it links
  only `/System/Library/*` and `/usr/lib/*`. Staging rewrites the install name
  to `@executable_path/../Frameworks/libMoltenVK.dylib` so the bundle location
  is explicit rather than rpath-dependent, and validates the architecture set,
  the macOS 11.0 minimum, and the dependency allowlist. A dependency outside
  `/System/Library/` and `/usr/lib/` — a Homebrew, MacPorts, `/opt`, `@rpath`,
  or absolute developer path — is a ship blocker.
- **Signing.** The published dylib is **ad-hoc signed only**. Credentialed
  release runs must re-sign it with the Developer ID Application identity as
  nested code, inside-out, before the outer app is signed and notarized, exactly
  like the SP/MP game modules. An ad-hoc signature surviving into a notarized
  package is a signing defect, not an acceptable state.

## Validation Contract Without Apple Hardware

This project has no Apple hardware and no local macOS access. That constraint is
already recorded in
[plans/2026-06-30-apple-support-no-macos-access.md](plans/2026-06-30-apple-support-no-macos-access.md)
and [macos-local-validation-track.md](../../macos-local-validation-track.md), and it
shapes what this decision may claim.

What **is** validated, off-macOS:

- Static policy: `tools/tests/macos_moltenvk_policy.py` pins the portability
  negotiation, the loader agreement between SDL and volk, the module export
  contract, and the MSL-hostile shader constructs. Every one of those is
  invisible from a Windows or Linux build.
- The existing macOS policy sweep (`tools/tests/macos_*.py`) continues to run
  after every build-system and documentation change.
- Vulkan renderer behavior itself: the renderer validation matrix, the
  `renderer*SelfTest` family, and SP gameplay on Windows/Linux. The SPIR-V,
  pipeline keys, descriptor layout, and command stream are shared, so the
  overwhelming majority of Vulkan defects are reproducible without a Mac.
- Hosted `macos-15` CI proves configure, build, staging, packaging, signing,
  notarization, and static validation of the added binaries.

What is **not** validated and must not be claimed:

- Any assertion that MoltenVK-backed Vulkan renders correctly on a real Mac.
- Any macOS performance number or comparison.
- Any Intel Mac or AMD/Intel-GPU Metal behavior, including the shadow-sampler
  translation class the static guard protects against.
- Any Gatekeeper, notarization-at-first-launch, or Finder behavior of the added
  nested code beyond what packaging validation already checks.

The gap-closing plan, in order of increasing value:

1. A hosted-runner capability probe: run `rendererVkProbe` on the GitHub-hosted
   macOS runner and record whether MoltenVK initializes and what it reports.
   Hosted macOS runners are virtualized, so a pass proves the loader/packaging
   contract only, and a failure may be a virtualization artifact. This is
   diagnostic plumbing, not gameplay evidence, and must be labeled as such.
2. A contributor-run opt-in check on real Apple hardware: launch with
   `r_renderApi vulkan`, capture `openq4.log`, `gfxInfo`, and
   `rendererVkProbe` output, and file it as a support archive.
3. Full SP and MP gameplay signoff on the macOS floor and the latest public
   macOS, per the existing evidence requirements, before any wording changes.

Until step 3 exists, macOS Vulkan is described as an experimental option that
may not work, never as a supported renderer.

## Release Wording Rules

These rules bind release notes, `README.md`, `BUILDING.md`, user docs, package
documentation, and store/download text.

Required:

- Call it "MoltenVK, a Vulkan-on-Metal translation layer", or "the Vulkan
  renderer running through MoltenVK on macOS". The first mention in any
  user-facing document must include the words "translation layer".
- Say that OpenGL remains the default and recommended renderer on macOS.
- Say that Vulkan on macOS is opt-in and experimental, and that macOS support
  itself is a preview for Apple Silicon/arm64.
- Say what happens when Vulkan cannot start: a missing module, a missing
  translation layer, or an unsuitable GPU falls back to OpenGL, and a window or
  surface failure later in startup stops openQ4 with an error after setting
  `r_renderApi` back to `gl` for the next launch.
- Keep the two existing macOS package variants named `OpenGL` and `Metal
  bridge`, and keep the Metal bridge described as a bridge around the OpenGL
  renderer, not a native Metal renderer.

Forbidden:

- "native Metal", "Metal renderer", "Metal backend", or any phrasing that
  implies openQ4 renders through Metal directly.
- Calling the macOS path "native Vulkan", or any phrasing that implies a Vulkan
  driver exists there.
- "OpenGL-free renderer" for any macOS package.
- Any suggestion that this adds a third macOS download, a new package variant,
  or a new `macos_graphics_bridge` value.
- Any macOS promotion phrasing — first-class, fully supported, production-ready,
  stable, no longer a preview — without the completed evidence the macOS
  support claim guard in [release-completion.md](../../release-completion.md)
  requires.

## Gate Disposition

This plan clears the decision gate for **the MoltenVK-backed Vulkan renderer
module on macOS, opt-in, with OpenGL remaining the default**, and for nothing
else.

The gate stays closed for:

- A native Metal renderer.
- Making Vulkan the macOS default, or resolving `best` to `vulkan` on macOS.
- A third macOS package variant or a new `macos_graphics_bridge` value.
- Any first-class macOS support claim.

Each of those requires its own plan, its own tests, and — for the last two —
real Apple-hardware evidence.
