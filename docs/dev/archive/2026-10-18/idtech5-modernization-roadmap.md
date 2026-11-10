# idTech 5-Level Modernization Roadmap

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

This document turns the project's modernization goal into an implementation
order that preserves the shipped Quake 4 asset and gameplay contracts. It is
based on the official Doom 3 BFG Edition source snapshot (`1caba197`) pinned in
the [source-provenance inventory](../../source-provenance.md), the current openQ4
[capability matrix](../../engine-capability-matrix.md), and the stock-asset acceptance
harness.

Doom 3 BFG is not the full idTech 5 or idTech 6 source tree. It is a late
idTech 4 branch containing several idTech 5-era architectural ideas: a parallel
job manager, jobbed renderer front end, GPU skinning, explicit GPU buffers,
binary/generated resources, preload manifests, GPU timing, automatic resolution
scaling, a refined front-end/back-end render command stream, and a newer
session/network stack. Those subsystems are useful references, but importing the
whole engine would replace Quake 4 contracts rather than modernize them.

## Non-negotiable compatibility boundary

Modernization is acceptable only when all of these remain true:

- Retail Quake 4 PK4s remain the source of truth. Players are not required to
  convert, unpack, or patch them.
- Classic material, decl, GUI, map, MD5/MD5R, BSE, sound, save, demo, and
  protocol behavior remains available as the fallback and comparison path.
- Generated data is a disposable, versioned cache under `fs_savepath`, keyed to
  its source identity (including the containing PK4 checksum where relevant).
  Missing or invalid cache data falls back to the retail source. A cache never
  becomes downloadable content or part of the pure-package authority set.
- New material features use namespaced, opt-in syntax. A stock material is not
  silently reinterpreted as PBR content.
- Wire, save, and demo format changes are explicitly versioned. Protocol 2.41
  compatibility is not changed by an internal refactor.
- Dedicated builds do not acquire renderer, presentation, or client-only job
  dependencies.
- Every promoted default passes the four-role stock baseline and a human review
  of engine-written screenshots. MP validation explicitly uses
  `+set ui_autoJoin 1`, `+set si_pure 1`, and
  `+set net_serverAllowServerMod 0` unless the test is specifically for the join
  menu or non-pure behavior.

## What openQ4 already uses from the BFG lineage

The most directly reusable BFG work is not hypothetical. openQ4 already carries
audited BFG-lineage code in these areas:

- binary image loading/writing, image options, image programs, color-space
  conversion, and DXT encode/decode;
- renderer image management and intrinsic-image support;
- the newer sound world/emitter/voice/sample architecture, with the OpenAL
  implementation arriving through the documented RBDOOM lineage;
- small idlib utilities such as static strings, swapping, and sorting.

The authoritative inventory currently records 37 BFG-headered files. Any
additional incorporation must retain the upstream notices, update that inventory
and the applicable Additional Terms coverage, and record any intermediate
lineage. This roadmap is technical guidance, not a legal conclusion.

"Readily available" below means that the named implementation is present in the
audited official snapshot and can be studied or adapted without reverse
engineering. It does not mean drop-in: several paths assume Win32, PS3/SPU,
trusted pre-generated data, 32-bit offsets, or assert-only validation. New code
must use openQ4's portable interfaces and fail-closed input rules.

## Current implementation state (2026-08-24)

This table is the dated delivery snapshot for this roadmap. **Implemented**
means the compatibility-safe foundation is present and covered by the cited
project evidence and may still be default-off while release promotion is
pending; **Experimental** means the scoped implementation remains incomplete,
trial-grade, or below its stated evidence floor; **Partial** means only part of the required
contract exists; and **Planned** means the roadmap is still design guidance.
The [engine capability matrix](../../engine-capability-matrix.md) remains authoritative
when a status differs or a narrower qualification is needed.

| Workstream | State | Current boundary and next work |
|---|---|---|
| Stock-compatibility and security foundation | **Implemented** | Protocol 2.41 preservation, pure-MP game-module containment, bounded malformed-input handling with immediate session teardown, challenge entropy, rcon2, private-CVar redaction/remote authority, HTTP(S)-only transfer policy, source-provenance auditing, archived MP auto-join test policy, and the four-role retail-PK4 evidence harness are present. Release promotion still requires a clean source pair, final-package capture, and retained human review. |
| Audited BFG-lineage image, sound, and idlib work | **Implemented** | The existing 37-file BFG inventory is tracked with source lineage and Additional Terms. Further imports must update the same manifest and notices. |
| PBR material authoring and advanced-lighting path | **PBR materials implemented and default-on; probe, decal and other advanced-lighting leaves default-off** | Since the [production-readiness plan](plans/2026-10-04-pbr-production-readiness.md) the classic OpenGL light loop (`draw_pbr.cpp`) and native Vulkan own every admitted PBR surface in ordinary gameplay, every light keeping its shadows; stock materials are never PBR and a frame without a PBR material skips all PBR preparation. Roughness, metalness and AO reach every term (multiple-scattering energy compensation, specular, horizon and multi-bounce occlusion); irradiance is calibrated to the classic light term and each draw composes into the display-referred frame. Authored ambient lights act as uniform environments, baked light grids and opt-in authored probes (`r_rendererReflectionProbes`) light PBR on both backends, and SSAO occludes only indirect light. Paired OpenGL/Vulkan laboratory suites qualify every channel and term on Windows (NVIDIA; Vulkan also on Intel) and on Linux Mesa (llvmpipe and lavapipe). Animated and MD5R-converted models are PBR on both backends; probes can be box-projected (`boxParallax`) and captured in the engine (`bakeReflectionProbes`); an OpenGL context without GLSL 1.30, such as macOS's GL 2.1, keeps PBR materials classic. Review on Mac hardware is pending. |
| GPU measurement and dynamic resolution | **Implemented measurement; experimental default-off controller** | OpenGL and Vulkan publish the same delayed, non-blocking whole-frame microsecond result through renderer ABI v11, including frame/generation identity and availability/drop/reset counters. The Milestone E controller binds each retired sample to its source scale, rejects stale identity, drops quickly above budget, raises only after an under-budget streak, and keeps bounded aligned scene dimensions. Captures freeze or deliberately force native scale without feeding their timing into control. Current-build required-profile captures exercise both timing backends and forced controller drops; clean committed-package and platform/driver qualification remain open. |
| General job system | **Implemented foundation** | The engine-owned [portable bounded job service](../../parallel-job-system.md) provides sleepable workers and waits, bounded list/job/dependency admission, low/normal/high priority aging, dependency ordering, cooperative cancellation, deterministic inline execution, metrics, and dedicated-safe lifecycle ownership. Threaded and synchronous native coverage passes. Its first production consumer is the learned level-load read/PK4-inflate and framing/integrity pipeline; live asset parsing, renderer/audio upload, and renderer-front-end work remain with their established owners. Current-build stock validation also produced identical jobs-on/off storage1 screenshots and game state, completed jobs-on/off OpenGL plus jobs-on Vulkan repeated-map campaigns with clean shutdown markers, and recorded five deterministic synchronous dedicated-server exits. Clean final-package recapture remains a separate release-promotion gate. |
| Generated caches, streaming, and learned preload manifests | **Implemented and locally validated; release promotion pending** | Successful loads produce exact map/mode/entity-filter/search/PK4/settings manifests. Matching loads use bounded cancellable read/PK4 inflation followed by worker-safe typed framing and integrity validation, publish an immutable generation/source-identity DTO, and let the established main owner parse, adopt, and upload. Transactional static/MD5/MD5R model, classic-proc world, collision, and animation-v3 caches are private to `fs_savepath` and fall back to authoritative VFS sources. This is learned level-load preparation, not general asynchronous asset decode/upload streaming or portal-aware live reprioritization. Separately and by default since 2026-10-06, every level load reads and fingerprints its precompressed DDS images on worker threads while the main thread uploads (`image_prefetchLevelImages`). Local Windows runtime evidence is recorded; clean committed-package performance, broader cancellation/failure campaigns, and release-platform evidence remain open. |
| Shared renderer contracts and GPU skinning | **Implemented; opt-in (not beneficial for stock content, 2026-10-06)** | Ordered material/pass, clip-space, semantic vertex-layout, typed buffer-slice, exact four-weight, and joint-palette contracts are shared by OpenGL and Vulkan. `r_gpuSkinning` remains default-off; admitted MD5/MD5R surfaces produce the ordinary `idDrawVert` stream through backend compute while CPU positions and complete fallback remain authoritative for gameplay consumers and stencil volumes. Vulkan no longer pays the CPU basis derivation the compute pass replaces, and sidecar validation is O(1) per use. Stock maps skin only about 1,500 vertices per frame, so promotion is deferred to animation-heavy content, after batched OpenGL dispatches and persistent per-mesh source buffers ([evidence](../../gpu-skinning-modernization.md#2026-10-06-promotion-attempt-not-beneficial-for-stock-content)). |
| Modern classic-frame ownership | **Implemented; default-off; controlled nested GL/Vulkan fixture passed; release promotion pending** | Fixed-function root 2D GUI, eligible ambient-only 3D world, fixed-classic interaction, complete eligible fog/blend phases, provenance-tagged in-world GUI output, special subviews, cinematic/authored-post ranges, render-demo/Raven special frames, and their material-deform dependency have separate sealed GL/Vulkan corridors with complete classic rollback. Eligible authored-post tails inside a sealed special view bind to its exact root and depth; their executed work remains unpublished until the complete special-view transaction succeeds, and either domain can roll back the whole tree. Final R6 runtime acceptance proves one capture-backed color-2D mirror with a nested cinematic plus `_currentRender` tail on Windows GL/Vulkan. This is scoped ownership, not a claim that the aggregate modern-visible renderer owns every stock frame or that root cinematic/post, `_currentDepth`, broad subview, in-world-GUI, special-frame, final-package, platform, or driver breadth is qualified. |
| Temporal presentation | **Implemented; automatic below native resolution by default (2026-10-06)** | OpenGL and Vulkan share native-resolution history ownership, TAA/TAAU, camera/depth reprojection, camera/capture resets, and native-resolution UI composition. The velocity pass owns every moving surface per pixel: exact vectors for rigid entities, skinned surfaces (previous model-space positions captured before each pose) and the depth-hacked weapon; per-pixel reactive coverage for particles, effects, GUIs, subviews and translucent moving geometry. The resolve uses YCoCg variance clipping, nearest-depth velocity, Catmull-Rom history and present-only CAS sharpening. `r_temporalAA 2` (default) engages only below native resolution; SMAA remains the rollback. Clean package, platform, driver, and retained human-review promotion remain open. |
| Modern PBR quality and idTech 6-like follow-ons | **Implemented for the scoped roadmap; default-off; local Windows gate passed; release promotion pending** | Guarded direct metallic/roughness lighting, analytic fallback IBL, authored bounded OpenGL specular probes, atomic bounded OpenGL clustered decals, and three independent GL/Vulkan screen-space leaves now cover the scoped quality plan. The shared native presentation tail provides bounded 16-slice view-aligned froxel integration, bounded 16-step depth-normal SSR, and fixed eight-tap depth-derived SSGI. The effects deliberately do not claim shadowed light-injected volumetrics, material-roughness reflections, or world-space GI. This does not establish broad authored scene coverage or whole-frame lighting promotion: `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` remains `0`, while complete GPU-driven visible ownership and optional sparse residency remain later follow-ons. |

### 2026-10-06 gap review

Each remaining idTech 5/6 renderer item was either finished by default, measured
and found not to pay for stock content, or deferred for a stated reason:

| Item | Outcome |
|---|---|
| Temporal AA / upscaling (idTech 6 TSSAA) | **Done, default.** Complete per-pixel motion ownership; `r_temporalAA 2` upscales whenever the scene renders below native resolution ([temporal presentation](../../temporal-presentation.md)). |
| Level-load streaming | **Done for images, default.** Worker-thread DDS reads, hardware SHA-256, immutable OpenGL texture storage and the loose-file memo: warm OpenGL Air Defense 1 about 14 s to about 9 s ([evidence](../../airdefense1-optimization-evidence.md)). General asset streaming stays open. |
| Shader/pipeline caches | **Done; no background compilation needed.** Vulkan's pipeline cache is written atomically per level; a whole stock session creates 33 pipelines (49 ms cold, 4 ms warm). |
| GPU skinning | **Not beneficial for stock content.** Vulkan no longer pays the CPU work it replaces, but stock maps skin about 1,500 vertices per frame (about 15 microseconds of CPU); `r_gpuSkinning` stays opt-in ([evidence](../../gpu-skinning-modernization.md#2026-10-06-promotion-attempt-not-beneficial-for-stock-content)). |
| True HDR display output | **Deferred:** needs HDR display hardware to verify. |
| Shadowed light-injected volumetrics | **Deferred to an authored opt-in:** shadow maps exist only inside each backend's light loop, and stock maps stage their shafts with beams and fog lights. |
| `com_levelLoadModernization` default | **Deferred:** now 3.4 s slower on a first visit (was 6.6 s) and 1.1-1.5 s faster warm; the per-file `Sync()` and cache-key audit decide promotion. |

Milestones A, B, and C have completed their implementation and local integration
gates. **Milestone D scoped implementation is complete.** Its default-off
corridors cover four complete fixed-classic domains, a bounded in-world GUI
subset transaction, special-subview trees, cinematic/authored-post ranges,
render-demo/Raven special frames, and their shared material-deform dependency:
eligible
fixed-function root 2D GUI views, eligible ambient-only 3D world views,
fixed-classic interaction, and complete eligible fog/blend phases use
backend-neutral sealed records on both backends, with independent settings and
complete classic rollback. Interaction accepts eligible unshadowed and
shadow-coupled views with explicit light, receiver, shadow, map, material,
resource, and fallback accounting. Fog/blend preserves complete light,
GLOBAL-to-LOCAL receiver, ordered stage, fog-cap, texgen/state/resource, and
backend accounting without mixing shared and classic phase draws. All four
domains have retained local runtime qualification; fog/blend's controlled
stock-declaration profile passes exact parity, effect-delta, ownership, and
rollback gates on both backends. The controlled shipped-material deform profile
also passes exact parity, visible effect-delta, completed ownership, and
zero-commit skipped rollback gates on both backends. Completed/empty finalized
material deforms and the classic source-geometry receiver roles now have an
explicit sealed contract, while particle/particle2 remain named fallback. The
special-subview corridor seals direct `SS_SUBVIEW` mirror camera/clip semantics
and the child scene/copy edge for remote-camera, mirror, reflection, refraction,
and x-ray views, including exact 2D/cubemap color/depth target type, aspect,
and face. Nested special views now seal exact parent records, depth-first
child-before-parent packet order, bounded root/depth metadata, and all-member
backend completion before publishing ownership; any member rejection restores
the complete tree to the classic owner.
In-world GUI output from `R_RenderGuiSurf` now has independently
sealed, depth-aware ownership with complete tagged-subset fallback. The new
cinematic/authored-post transaction seals complete eligible root video/audio
views and post tails while retaining the mature decoder and feedback-stage
executors. An eligible post tail inside a sealed special view records the exact
special root/depth, defers ownership publication, and co-publishes or rolls back
atomically with the complete tree. The shared special-frame transaction seals active-session
render-demo views and exact Raven special-effect controller masks while keeping
their complete established backend executors. **Milestone E temporal
presentation is now implemented and locally validated as a default-off
capability.** Native histories, explicit motion/reactive ownership, TAAU,
capture/cut isolation, native UI, and delayed GPU-time resolution control share
one GL/Vulkan contract with SMAA rollback. Milestone F now has a guarded
implementation for direct PBR, authored bounded OpenGL specular probes,
atomic bounded OpenGL clustered decals, and independent bounded GL/Vulkan
froxel-volumetric, SSR, and SSGI leaves. Its leaf controls remain default-off,
`r_rendererModernQuality 0` is the one-setting rollback, and the local
current-source Windows implementation exit gate has passed. Final
committed-package, platform/driver, and release-review promotion remains open.
This work is separate from frame-ownership promotion:
`MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` remains
`0`.
The final controlled R6 nested acceptance ran six sequential cases per backend
with the fixed input-disabled capture script in actual windowed mode `-1` at
1280x720, using 1280x720 engine TGAs. All 12 cases passed; all four exact
comparisons per API reported RMS `0`, maximum delta `0`, and zero differing
channels, with expected owned/fallback accounting and named atomic rollback.
Normal versus skip remained non-vacuous at RMS `2.0073`, maximum delta `72`,
and 46,359 changed channels on OpenGL and RMS `0.2506`, maximum delta `18`, and
3,329 channels on Vulkan. The authoritative report SHA-256 is
`b49031c48267fbfa86c295082707525a390d6090c24f600d00644237a67b252a`,
bound to fixture manifest SHA-256
`24a2a4926f4b1263e311ad762bf40d391b33de225732d12154ebd7625705282d`
and runtime manifest SHA-256
`dbece44597ec5e0686eed215f6ae99c5d6ba4cdd959c1efa7c4acaf1bc2ca673`.
The unchanged 3,884-file / 7,281,560,043-byte stock dependency seal is
`13abad18f70eb8b4bf6ea0e9697b317718bb065ee76f86070787005b045dda7a`;
the unchanged eight-file / 25,330,583-byte fixture evidence inventory seal is
`0572fb8d9c132f7e97060345464f97750e59e69819871fce90eed13d1348d8ae`.
This evidence is deliberately limited to one nested cinematic-plus-
`_currentRender` mirror transaction; its `currentDepth` count is zero.
Release qualification remains a separate track: repeat and retain the
Milestone A-D acceptance sets from clean committed source and a freshly staged
final package, with the required platform and driver coverage. The PBR path
does not bypass those complete-frame ownership requirements.

## Best official Doom 3 BFG candidates

The paths below are relative to official `DOOM-3-BFG/neo/` at the pinned
snapshot.

| Candidate | Readily available BFG code | openQ4 use | Reuse level | Priority |
|---|---|---|---|---|
| Parallel job substrate | `idlib/ParallelJobList.*`, `idlib/Thread.*`, renderer consumers in `tr_frontend_addmodels.cpp` and `tr_frontend_addlights.cpp` | A bounded, dependency-aware worker pool for renderer front-end work, archive/decode jobs, animation work, and cache generation | Adapt architecture; replace platform primitives and spin waits with SDL3/portable C++, and retain deterministic single-thread fallback | **P1** |
| GPU skeletal skinning | `renderer/BufferObject.*`, `VertexCache.*`, `Model_md5.cpp`, `tr_frontend_addmodels.cpp`, `tr_backend_draw.cpp`, `RenderProgs*` | Joint-buffer uploads and optional four-weight GPU deformation for rendered MD5/MD5R draw surfaces and shadow-map casters while preserving CPU consumers | Port the algorithm into dedicated backend-neutral skin attributes and buffers; do not import BFG's GL backend or blindly reuse its vertex-color packing | **P1** |
| GPU timing and automatic resolution scaling | `renderer/ResolutionScale.*`, the timer query in `RenderSystem.cpp`, CPU profiling blocks in `RenderLog.*` | Feed openQ4's implemented backend-neutral, non-blocking GL/Vulkan whole-frame timing result into a bounded controller | Reuse the controller logic, not BFG's single-query blocking readback | **P1** |
| Generated model, render-world, and collision caches | `renderer/Model.cpp`, `Model_md5.cpp`, `ModelManager.cpp`, `RenderWorld_load.cpp`, `cm/CollisionModel_files.cpp` | Cache parsed static/MD5 geometry, `.proc` world data, and collision data after first trusted-source load | Design a hardened openQ4 format; follow the generated-animation cache contract and include Quake 4 MD5R/source-PK4 identity | **P1** |
| Preload manifests | `framework/File_Manifest.*` and resource-type discovery in `FileSystem.cpp` | Record actual per-map image/model/animation/sample/collision use and replay it through a cancellable preload queue | Reuse the manifest concept, not BFG's retail manifest contents | **P1** |
| Resource containers | `framework/File_Resource.*` | Optional developer-generated, sequential cache containers for derived data | Reuse the access-order concept only; BFG uses 32-bit offsets and trusted tables, so prefer individual cache files or a new bounded 64-bit format and never require a BFG `.resources` package | **P2** |
| Parallel renderer front end | `renderer/tr_frontend_*`, `renderer/jobs/ShadowShared.*`, atomic frame allocation in `tr_frontend_main.cpp` | Parallel entity/light visibility, interaction preparation, and shadow-caster work after ownership is made immutable for a frame | Architectural port with substantial Quake 4/BSE and modern-renderer adaptation | **P1/P2** |
| Explicit transient/static GPU buffers | `renderer/BufferObject.*`, `VertexCache.*` | Complete the current upload manager with backend-neutral vertex/index/joint handles, frame rings, fences, budgets, and overflow diagnostics | Mine lifecycle and handle ideas; current openQ4 GL/Vulkan ownership must remain authoritative | **P1** |
| Render-matrix and culling utilities | `idlib/geometry/RenderMatrix.*` | Shared, tested MVP/frustum/depth-bounds math for scene packets, shadow planning, Hi-Z, and GL/Vulkan clip-space variants | Selectively adapt algorithms and tests; do not force BFG's matrix or vertex ABI onto Quake 4 data | **P2** |
| Render-program parameter model | `renderer/RenderProgs.*`, `RenderProgs_GLSL.cpp` | Common parameter names/layouts for optional skinning and shared passes | Selective reference only; build a backend-neutral material/pass IR rather than another GL-specific shader manager | **P2** |
| Stereo presentation | `renderer/RenderContext.h`, stereo portions of `GuiModel.cpp`, `RenderSystem.*`, and `OpenGL/gl_backend.cpp` | Optional side-by-side/top-bottom rendering and stereo-aware full-screen GUI depth | Adapt only after ordinary presentation is stable; use SDL/OpenXR-era platform interfaces instead of old WGL assumptions | **P3** |
| Lightweight compression | `sys/LightweightCompression.*` | Potential LZW/zero-run compression for new cache payloads where profiling proves a benefit | Reuse only behind a new bounded, fuzzed decoder and versioned container; do not insert it into protocol 2.41 | **P3** |

### 1. Parallel jobs: the highest-leverage import

BFG's `idParallelJobList` provides job lists, priorities, synchronization
points, list dependencies, bounded parallelism, timing, and a deterministic wait
boundary. Its real BFG renderer users are deliberately coarse: add visible
models, add lights, and build shadow work. That is a better starting point than
spawning ad-hoc threads throughout openQ4.

The landed openQ4 service adapts that architecture rather than copying it:

- portable C++ threads and condition variables provide bounded workers and
  blocking waits instead of BFG's spinning `Wait()` behavior and fixed
  processing-unit assumptions;
- cancellation, shutdown, payload ownership, and lifetime are explicit in the
  service contract;
- deterministic synchronous mode is available for dedicated builds, tests,
  and debugging;
- list, job, and dependency admission is bounded, and saturation is reported
  instead of growing or dropping work silently;
- queue, execution, wait, high-water, rejection, and starvation-aging metrics
  are observable; dependency critical-path aggregation remains for real
  consumer graphs;
- arbitrary worker-side renderer calls remain prohibited unless a future
  backend-owned queue defines that boundary.

The production contract, controls, saturation behavior, native coverage, and
remaining consumer/promotion boundary are documented in the
[portable job-system guide](../../parallel-job-system.md).

The first production consumer is now the learned level-load read/PK4-inflate and
source-framing pipeline. Further consumers should still require a clean join
point and detached output: asset-specific image/audio/model decode or transcode,
generated-cache preparation, and only then renderer model/light preparation.
PK4 archive mutation and game-state mutation remain outside the worker contract.

### 2. GPU skinning: a concrete idTech 5-class capability

BFG converts MD5 vertices to four normalized byte weights and four joint
indices, uploads joint matrices through an aligned joint buffer, and keeps a CPU
path for unsupported or special surfaces. openQ4 now adapts that architecture
through its own full-precision, backend-neutral and fail-closed contract rather
than adopting BFG's packed vertex ABI.

The packed layout is not itself a safe compatibility contract. BFG asserts that
a model has fewer than 256 joints, stores joint indices in `color`, stores
weights in `color2`, and sorts, truncates, then renormalizes vertices with more
than four influences. Its own source notes residual weights above 25 percent in
some assets. Quake 4's packed MD5R path can also carry diffuse vertex colors, so
openQ4 must not silently repurpose those channels.

The landed corridor applies the required compatibility rules:

- validate joint and influence counts and retain the CPU path rather than
  truncating any MD5 vertex with more than four meaningful influences;
- use dedicated `uint32[4]` joint indices and `float32[4]` weights so packed
  MD5R diffuse colors and signed implicit residual-weight behavior remain intact;
- preserve CPU deformation for collision, traces, deforms, software-only debug
  tools, decals/overlays that need current positions, stencil shadow-volume
  construction, and any shader/material path lacking the skinning contract;
- carry joint data through ambient surfaces, light interactions, shadow-map
  casters, subviews, and view models, while explicitly routing incompatible
  surfaces to CPU deformation;
- use one typed, generational joint-buffer/slice contract represented
  consistently in GL and Vulkan;
- keep the capability default-off while clean-package bounds, vertex,
  silhouette, screenshot, and performance promotion evidence is accumulated.

This should land as capability and parity infrastructure first. It should not be
coupled to PBR, TAA, or a renderer-default switch.

### 3. Generated assets and learned preloading

BFG assumes generated BFG resources exist. Stock Quake 4 installations do not,
so its packaged manifests and resource containers cannot be required. The landed
Milestone B adaptation extends openQ4's generated-animation and binary-image
pattern:

1. Load the original PK4 asset normally.
2. Record the resolved source path, containing PK4 checksum, parser/build
   version, platform-independent format version, and relevant quality settings.
3. Write derived data under `fs_savepath/baseoq4/generated/` using an atomic
   temporary-file replacement.
4. On the next run, validate every bound before allocation and every source key
   before use.
5. Delete or ignore an invalid cache and fall back to the original asset.

Parsed static/MD5/MD5R render models, classic `.proc` render-world data,
collision models, animation v3, and an exact learned per-map preload manifest
now follow that contract. BFG's serializers remain useful field inventories,
but their timestamp checks and trusted-data assumptions are not sufficient for
a PK4-backed, fail-closed runtime. The openQ4 manifest schedules a bounded
deterministic subset and never overrides VFS resolution or becomes a second
source of asset truth. Asset-specific asynchronous owner decode/upload and
portal-aware live reprioritization remain future work. The exact format,
ownership, limits, rollback, and promotion-evidence boundary are documented in
[Level-Load Cache Modernization](../../loading-cache-modernization.md).

### 4. Dynamic resolution from real GPU time

BFG's resolution controller is compact and readily adaptable. It lowers
resolution quickly when GPU time exceeds a threshold and raises it more slowly
after several under-budget frames, avoiding constant oscillation. openQ4 already
has render scaling, renderer metrics, high-refresh presentation, and a
four-slot, non-blocking GL timestamp ring. Milestone A exposes that ring
as a backend-neutral whole-frame result and provides the equivalent Vulkan
timestamp-query path. Both backends resolve only retired/available slots, reset
their generation at workload discontinuities, and feed high-resolution CPU plus
de-duplicated GPU samples into `OPENQ4_FRAME_TIMING_V1`. What remains is the
feedback controller and complete promotion evidence.

The future controller should build on this implemented timing foundation:

- preserve the non-blocking GL/Vulkan timestamp contract and never wait on a
  current-frame result;
- target a user/display frame budget and account for VRR;
- quantize dimensions to backend-friendly alignments;
- expose minimum scale, response rate, and a conservative default-off rollout;
- reset history on map load, teleport, video restart, backend switch, and other
  discontinuities;
- keep GUI/HUD composition at native output resolution;
- integrate with future TAAU, while remaining useful with SMAA/bilinear scaling.

## BFG systems to study but not transplant

| BFG subsystem | Why it is not a direct openQ4 import | Safer direction |
|---|---|---|
| `sys/PacketProcessor.*`, `Snapshot*`, lobby/session code | Different wire model, object snapshots, lobby assumptions, platform services, and game semantics; replacing it would break protocol 2.41 and existing Quake 4 networking | Keep the hardened Quake 4 path. If a new transport is justified, negotiate an explicit openQ4 protocol while retaining 2.41 as a separate path |
| Depth-fail stencil-shadow back end | The official BFG release expressly omits the code that enables Carmack's Reverse; the included shadow jobs and shared geometry helpers are not a complete replacement renderer | Keep openQ4's existing Quake 4-compatible stencil path authoritative. Study the BFG job boundaries independently of the omitted back-end operation |
| SWF UI runtime | Quake 4 ships idTech 4 GUI scripts, not BFG SWFs; replacing the UI runtime would strand stock menus and in-world GUIs | Modernize the existing GUI renderer/parser and add optional new UI surfaces without removing the stock path |
| XAudio2 backend | Windows-specific and redundant with openQ4's cross-platform OpenAL voice/HRTF/EFX work | Continue improving the current backend and SDL/platform device lifecycle |
| Doom 3 `d3xp` gameplay, aim, inventory, achievements, and save/session code | Different game rules, class layouts, scripts, maps, and save data | Port isolated engine-agnostic ideas only; implement Quake 4 gameplay changes canonically in `openQ4-game` |
| BFG render backend as a whole | Assumes BFG vertex formats, shaders, material behavior, generated resources, and GL/platform interfaces | Extract contracts and algorithms into the current backend-neutral GL/Vulkan architecture |
| BFG resource packages as shipped data | No corresponding generated packages exist in a retail Quake 4 installation | Generate disposable caches locally and retain source-PK4 fallback |
| Doom Classic integration and platform storefront code | Unrelated content and unavailable proprietary service pieces | Keep out of the runtime |

## Capabilities beyond the official BFG drop

Reaching an idTech 6-like standard requires work that the 2012 BFG source does
not provide. These should build on the BFG-derived foundations rather than be
treated as code-import tasks.

The highest-leverage renderer step is to finish coherent ownership, not add one
more isolated experimental pass. openQ4 already has experimental scene packets,
a render graph, clustered/MDI submission, shadow maps, and Vulkan coverage, but
the capability matrix records no proven modern visible-lighting domain yet.
Classic ambient/material, interaction, and fog/blend semantics now have
independent shared contracts alongside root 2D GUI, and their material-deform
dependency is explicit. The direct-mirror and eligible color-capture subview
edges and the provenance-tagged in-world GUI subset are also explicit; cinematic
and remaining post/fallback semantics must still become explicit before temporal
or PBR work multiplies the parity surface.

### Backend and submission

- A backend-neutral material/pass intermediate representation shared by GL and
  Vulkan.
- Complete modern visible-lighting ownership before promoting GPU-driven
  submission.
- Persistent resource descriptors, pipeline/shader caches, indirect draws,
  Hi-Z culling, and a safe CPU rollback.
- Explicit resource state/lifetime tracking and asynchronous upload budgets.

### Image quality

- **Implemented 2026-10-06:** complete motion ownership. Rigid, skinned and
  view-model surfaces get exact vectors; particle, deform, subview and GUI
  surfaces get per-pixel reactive coverage instead of screen regions.
- **Implemented:** TAA/TAAU with per-pixel reactive masks, disocclusion
  handling, camera-cut resets, and SMAA fallback; automatic below native
  resolution by default.
- Dynamic resolution driven by backend timestamps.
- Namespaced PBR material extensions, GGX lighting, IBL/specular probes, and
  stock-material defaults that preserve the classic look.
- **Implemented as independent default-off leaves:** bounded view-aligned
  froxel fog/volumetrics, depth-normal SSR, and fixed-tap screen-space GI now
  consume the reliable scene-colour/depth presentation tail on GL and Vulkan.
  Their documented screen-space limitations remain explicit.
- True HDR output (scRGB/HDR10 negotiation, paper-white GUI composition, and HDR
  screenshot policy), distinct from the existing internal HDR scene chain.
  **Deferred 2026-10-06:** the only development machine exposes no HDR surface
  format (Intel Xe: `SRGB_NONLINEAR` only), so swapchain negotiation and PQ/scRGB
  encoding could not be seen working; Quake 4's SDR-authored content also gains
  little without the internal tone-mapping chain being on by default. Revisit on
  HDR display hardware.
- Shadowed, light-injected volumetrics. **Deferred 2026-10-06:** a light's
  shadow map exists only while that light draws (the OpenGL loop renders one
  shadow map at a time), so injection needs a hook inside each backend's light
  loop, and stock maps already stage their light shafts with authored beam
  meshes and fog lights. Global scattering would restage every stock scene;
  the useful form is an authored per-light or per-material opt-in for new
  content.

### Streaming and CPU scalability

- Extend the implemented bounded read/PK4-inflate -> framing/integrity DTO ->
  main-owner adoption corridor into asset-specific decode/transcode/upload only
  where detached results and per-stage budgets make ownership safe.
  **2026-10-06, by default:** level images now read and fingerprint their
  precompressed DDS on worker threads while the main thread uploads, content
  hashing uses the CPU's SHA instructions, OpenGL compressed textures take
  immutable storage, and a level load stops failing loose-file opens; together
  about 14 s to about 9 s for a warm OpenGL Air Defense 1 load on the test
  machine ([evidence](../../airdefense1-optimization-evidence.md)).
- Add portal-aware live priority changes to the current exact-match learned
  manifest. The implemented replay is a bounded, deterministically ordered
  subset rather than an unconditional whole-level preload, but it does not
  reprioritize dynamically from portal visibility.
- Optional virtual-texture/sparse-residency support for high-resolution community
  content, after ordinary streaming is reliable. The official BFG drop does not
  provide idTech 5's virtual-texturing implementation, and stock Quake 4 assets
  must never depend on this path.
- GPU skinning plus jobbed animation/model preparation. **Measured 2026-10-06:**
  stock maps skin about 1,500 vertices per frame, so GPU skinning stays opt-in
  until animation-heavy content justifies batched dispatch and persistent
  per-mesh buffers ([evidence](../../gpu-skinning-modernization.md#2026-10-06-promotion-attempt-not-beneficial-for-stock-content)).
- Background shader/pipeline compilation with deterministic cache keys and an
  always-available synchronous fallback. **Measured 2026-10-06, not needed for
  stock content:** a whole Vulkan airdefense1 session with a full camera sweep
  creates 33 pipelines (49 ms in total and one 11 ms creation from an empty
  cache; 4 ms in total from a restored one), and stock materials need no
  runtime SPIR-V compilation. Vulkan now times every pipeline creation
  (`gfxInfo`), logs what each map created, and writes the driver's pipeline
  cache atomically before every level load as well as at shutdown, so a
  session that crashes keeps what earlier maps compiled.

### Networking and operations

- Keep protocol 2.41 for compatibility, but consider a separately negotiated
  openQ4 transport for larger sequence spaces, stronger session authentication,
  modern congestion/fragmentation behavior, and optional traffic protection.
- Continue bounded parser work, fuzzable decode APIs, rate limits, structured
  diagnostics, and headless dedicated-server soak tests independently of any
  future protocol.

## Recommended implementation order

| Milestone | Current state | Dependency that prevents promotion |
|---|---|---|
| A. Foundation and measurement | **Implemented and locally validated; release promotion pending** | The portable bounded job substrate, backend-neutral delayed GL/Vulkan whole-frame timing, and versioned, replay-verifiable per-map CPU/GPU budget tooling are implemented. Current-build jobs-on/off parity, repeated map-change shutdown, deterministic dedicated exits, schema-10 stock capture/replay, and complete replay-verified 8/8 OpenGL plus 8/8 Vulkan required profiles have passed. Promotion still requires the same evidence retained from clean committed source and a freshly staged final package, plus release platform/driver qualification. |
| B. Loading and cache modernization | **Implemented but default-off; performance requalification required** | Exact learned manifests, bounded cancellable read/PK4-inflate and framing/integrity stages, immutable source DTOs, and transactional model/world/collision plus animation-v3 caches are integrated with source fallback. A 2026-08-20 regression audit found that the prior default-on experiment could materially lengthen stock map loads, so `com_levelLoadModernization 0` now restores the classic baseline and gates every framework/animation cache read and write. Promotion requires a clean committed-package campaign that beats or matches classic cold and warm loads without rewrite churn, plus release-platform qualification. |
| C. Shared renderer contracts and GPU animation | **Implemented; promotion pending** | Ordered pass semantics, clip/viewport conversion, semantic layouts, typed buffer slices, exact four-weight MD5/MD5R sidecars, bounded joint palettes, and GL/Vulkan deformation paths are present with full-surface CPU rollback. Dependency-light and module self-tests cover the common contract; clean-package SP/MP image, collision/hit, animation-heavy performance, and platform/driver evidence remains the promotion gate. |
| D. Modern classic-frame ownership | **Implemented; default-off; controlled nested GL/Vulkan fixture passed; release promotion pending** | The scoped GL/Vulkan ownership corridors are complete for eligible fixed-classic GUI, world ambient, interaction, fog/blend, in-world GUI, special-subview, cinematic/authored-post, special-frame, and material-deform work. Authored-post/video/current-render/depth tails nested in a sealed special-view tree share its root transaction: no member publishes until every child draw, dynamic tail, and capture/direct edge completes, and any failure restores the whole tree to classic execution. Final R6 evidence proves one nested cinematic-plus-`_currentRender` color-2D mirror transaction; root cinematic/post, `_currentDepth`, broad subview forms, in-world GUI, special frame, authored-stock breadth, clean-package, retained-review, and target-platform/driver qualification remain open as applicable. |
| E. Temporal presentation | **Implemented; default-off; local Windows gate passed; release promotion pending** | Native game-owned and backend-owned histories, exact frame/depth/generation admission, camera reprojection, OpenGL rigid velocity, conservative reactive ownership for every unsupported motion stream, capture/cut isolation, native UI, TAAU, delayed dynamic resolution, and SMAA rollback are integrated across GL/Vulkan. Dependency-light/static coverage and windowed stock SP/MP gameplay close the local implementation gate; clean-package, target-platform/driver, and retained-review qualification remain open. |
| F. Modern materials and advanced lighting | **Implemented; default-off; local Windows exit gate passed; release promotion pending** | Guarded direct PBR and analytic fallback IBL are joined by authored OpenGL specular probes bounded to eight cubemaps, 32 records, and the top two probes per cluster; an atomic OpenGL clustered-decal transaction bounded to 1,024 records and 65,536 cluster references; and independent GL/Vulkan froxel-volumetric, SSR, and SSGI leaves. The screen-space tail is bounded to 16 depth slices, 16 reflection steps, and eight GI taps, shares scene colour/depth without expanding Vulkan's 256-byte resolve block, and keeps captures plus effect-only/TAA presentation explicit. All leaves default off and `r_rendererModernQuality 0` publishes an exact zero-feature packet. Current-source static/native checks, retail gameplay, individual and combined windowed OpenGL gameplay, combined validation-clean Vulkan gameplay, visible image deltas, and master rollback close the scoped local implementation gate. Final committed-package, platform/driver, retained-review, and release qualification remain open; no RenderDoc, broad authored probe/decal scene, light-injected volumetric, material-roughness SSR, or world-space GI coverage is claimed. `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS = 0`. |

### Milestone A: foundation and measurement

1. **Implemented:** the engine-owned portable bounded job manager provides
   synchronous mode, starvation-safe priorities, dependency tests,
   shutdown/cancellation tests, and timing counters.
2. **Implemented:** the delayed GL timestamp result is exposed through a
   backend-neutral whole-frame timing contract, and the equivalent Vulkan
   timestamp path is integrated; both are generation-aware and never wait for a
   current-frame result.
3. **Implemented and locally validated; release promotion pending:** enforce versioned,
   configurable map/backend/profile CPU and GPU percentile budgets in the
   gameplay benchmark and stock baseline; bind contract/runtime/artifact
   provenance and replay measurements fail-closed. The initial repeated 20/28
   ms rows are target ceilings until complete GL/Vulkan captures calibrate and,
   where justified, tighten each explicit identity.

The 2026-08-19 current-build evidence snapshot closes the local job lifecycle
portion of this gate:

- jobs-on and jobs-off `game/storage1` runs produced identical engine TGA bytes
  and matching game-state evidence;
- jobs-on and jobs-off OpenGL campaigns, plus a jobs-on Vulkan campaign, crossed
  `game/mcc_2` -> `game/storage1` -> `game/storage2` -> `game/storage1` ->
  `game/tram1` and ended with
  `jobsShutdown PASS v1 initialized=0 queued=0 running=0`;
- five dedicated-server runs exited normally with one synchronous self-test and
  one clean shutdown marker each;
- the schema-10 four-role retail-PK4 baseline passed capture and immediate
  replay under the canonical display/budget contract, and its engine screenshots
  and save preview passed local human review;
- storage and repeated-map runs exercised nonblocking OpenGL and Vulkan timing;
  the final immutable development runtime then passed and replay-verified all
  eight OpenGL and all eight Vulkan required-profile cases. The earlier
  `game/medlabs` failure was fixed by ordering and clamping depth bounds before
  the OpenGL call; its debug-context rerun records zero GL errors.

This evidence set culminated in the immutable development runtime
`milestone-a-20260819-final3`; its complete required-profile reports are
`ma-a-gl3` and `ma-a-vk3`. It came from an uncommitted current source tree and is
not a retained release artifact. It does not replace clean-source provenance, a
freshly staged final package, platform/driver qualification, or retained release
review.

Exit gate: replay-valid exact bordered-window 1280x720 GL/Vulkan captures for
the required budget identities; identical stock screenshots and game state with
jobs on/off; repeated map changes ending in
`jobsShutdown PASS v1 initialized=0 queued=0 running=0`; deterministic
dedicated-server exit; and the general four-role retail-PK4 and human-review
promotion evidence. The current-build job, lifecycle, timing-path, required-map,
and stock-baseline checks above satisfy the local implementation gate. Only the
general clean-source, final-package, retained-review, and platform/driver gates
keep release promotion open.

### Milestone B: loading and cache modernization

1. **Implemented:** a learned manifest is keyed to the exact normalized map,
   full SHA-256 runtime-role and entity-filter identities, ordered VFS/search and
   pure-PK4 state, individual source identities, and load-affecting settings.
2. **Implemented:** bounded cancellable workers read independently opened
   sources, perform the PK4 inflation reached by those reads, validate supported
   source framing and whole-buffer integrity, and publish a sealed immutable DTO.
   The ordinary VFS lookup runs again before substitution; format-specific asset
   parsing, adoption, and renderer/audio upload remain with the main owner.
3. **Implemented:** versioned binary render-model, classic render-world, and
   collision caches under `fs_savepath`, plus the companion SP/MP animation-v3
   cache, validate detached state and publish atomically or fall back to source.
4. **Corrected after regression audit:** all Milestone B cache, preload, and
   animation-cache paths now require the default-off
   `com_levelLoadModernization` master gate. Archived individual controls from
   earlier builds cannot silently retain the slower path.

Exit gate: cold and warm load measurements, bounded memory, cancellation during
map/restart/disconnect, corrupt-cache fallback, and zero required loose assets.
Focused native/static tests, Windows integration builds, and current-build
stock compatibility checks satisfy the implementation/safety gate, but not the
performance gate. Local development cold/warm and bounded-memory measurements, focused
corruption/rollback, dedicated teardown, and engine-screenshot review are now
recorded; the staged stock report remains failed on its unchanged MP CPU budget.
Exact committed source/package identity, a clean-package budget pass, broader
cancellation/failure campaigns, and release-platform coverage remain required
for promotion. Requalification must also demonstrate that both cold and warm
opt-in loads are no slower than the classic default before any default change.
Their authoritative status is recorded in
[Level-Load Cache Modernization](../../loading-cache-modernization.md).

### Milestone C: shared renderer contracts and GPU animation

1. **Implemented:** define the minimum backend-neutral material/pass,
   clip-space, vertex-layout, and typed buffer-slice contracts needed by both GL
   and Vulkan.
2. **Implemented:** add bounded backend joint-buffer rings and dedicated
   full-precision four-weight vertex data.
3. **Implemented:** establish the rigid/MD5/MD5R CPU-vs-GPU parity corridor,
   including preserved diffuse vertex colors, signed MD5R residual weights,
   exact-only MD5 admission, and joint/data/capability fallbacks.
4. **Implemented:** feed an ordinary deformed `idDrawVert` stream to depth,
   ambient, interaction, subview, shadow-map, and view-model consumers while
   decals/overlays keep CPU positions and stencil volumes remain explicitly CPU.

Exit gate: stock SP/MP visual equivalence, CPU fallback parity, no collision or
hit-detection changes, and measured CPU-frame reduction in animation-heavy maps.
The implementation and deterministic contract gate is complete. Clean committed
package screenshots, pure-MP collision/hit digests, repeated animation-heavy
measurements, and target-platform/driver coverage remain required before the
default-off capability can be promoted; the exact procedure is recorded in
[Shared Renderer Contracts and GPU Animation](../../gpu-skinning-modernization.md).

### Milestone D: modern classic-frame ownership

1. **Implemented:** fixed-function root 2D GUI, world ambient/material,
   unshadowed plus shadow-coupled fixed-classic interaction, and fog/blend
   conditions, colors, repeated order, matrices/texgen, images, samplers,
   light/receiver/shadow/cap identity, and render state are expressed through
   shared contracts. Their CPU material-deform dependency is also sealed. The
   capture-backed and direct special-subview edges are sealed.
2. **Implemented across the scoped domains:** GL and Vulkan consume the
   same per-draw evaluated semantic records, with backend-specific execution and
   an untouched complete-domain classic rollback.
3. **Implemented across the scoped domains:** scene packets and the
   material resource table promote a GUI, eligible ambient-only world view, or
   eligible unshadowed/shadow-coupled fixed-classic interaction view, while the
   fog/blend transaction promotes only a complete eligible phase, after
   transactional preparation and complete backend preflight; all other domains
   retain their established owner.
4. **Implemented for world ambient/material:** opaque and perforated draws must
   match an established depth packet, translucent draws retain their classic
   depth behavior, and ordered material work is split into pre-fog and post-fog
   phases without taking ownership of depth or fog.
5. **Implemented for fixed-classic interaction:** every accepted
   light, local/global/translucent receiver, light stage, decomposed primitive,
   no-op, and resource is sealed and reconciled together.
6. **Implemented for shadow-coupled fixed-classic interaction:** classic stencil
   volumes, projected single-map and CSM/parallel shadows, point cubes, mixed
   mapped/stencil lights, complete hybrid supplements, dynamic casters, and
   perforated casters are sealed and reconciled by both backends. Translucent
   moment casters and any incomplete/custom/unsupported/backend condition reject
   the whole interaction view before visible ownership.
7. **Implemented for fog/blend:** every fog/blend light, GLOBAL-to-LOCAL receiver,
   ordered active/inactive blend stage, fog receiver/cap, evaluated texgen/state,
   and resource is sealed and reconciled together. Any source, geometry,
   resource, capacity, target, or backend blocker rejects the complete phase
   before the first shared main-target draw.
8. **Implemented for classic material deforms:** finalized root GUI, world
   ambient, and mapped-shadow draws seal source/result material and geometry,
   evaluated inputs, frame/cache lifetime, outcome, and semantic hash around the
   authoritative CPU deform. Interaction and fog receivers seal the classic
   not-applicable/source-geometry role. Completed and intentional-empty results
   are admissible only behind `r_rendererSharedDeform`; particle/particle2,
   skipped, failed, stale, or mismatched records reject the complete owning
   transaction before backend work.
9. **Implemented for special subviews:** a direct `SS_SUBVIEW` mirror record
   seals its exact child-view camera, clip-plane, culling, viewport, and scissor
   semantics before OpenGL or Vulkan invokes the established whole-view executor.
   Remote-camera, mirror, reflection, refraction, and x-ray forms reconcile a
   child scene packet, parent source surface, exact full-viewport 2D/cubemap
   color/depth `RC_COPY_RENDER`, destination image type/aspect, and cube face.
   Both backends report ownership only after the sealed child executor or
   transfer returns. Nested children additionally seal exact parent/root/depth
   records and depth-first packet order; their entire tree publishes only after
   its outermost special view completes. Eligible cinematic/post work inside
   that tree is admitted by its dedicated domain and joins the same atomic
   publication/rollback boundary; unsupported special forms retain their
   untouched classic owners.
10. **Implemented for in-world GUI:** only GUI quads emitted under
    `R_RenderGuiSurf` receive front-end provenance. Their complete tagged subset
    uses a world-category GUI packet stream and depth-aware world pass records;
    GL and Vulkan preflight and commit before the ambient walks, then suppress
    only a successfully owned subset from their matching classic walker. Any
    source, packet, material, resource, target, capacity, or backend blocker
    retains every tagged source on the untouched classic path.
11. **Implemented for cinematics and authored post:** a root 2D video/audio
    view or a complete ordered `SS_POST_PROCESS` tail is admitted only after
    scene-packet/source identity and ordering reconcile. The sealed record
    carries the original render-view cinematic clock plus current-render/depth
    stage diagnostics. OpenGL and Vulkan keep their mature dynamic stage
    executors for decode, scratch upload, feedback capture, and custom program
    behavior. An eligible authored-post range inside a sealed special view binds
    to the exact special root and depth, completes without early publication,
    and co-publishes only when the complete special-view tree succeeds. An
    invalid source, packet, time, capture, target, or backend condition rolls the
    complete tree back to the classic path.
12. **Implemented for render demos and Raven special frames:** scene packets
    distinguish an active session render-demo stream from portal-sky negative
    view ids, seal complete root-view source coverage and the demo version, and
    preserve exact `RC_DRAW_SPECIAL_EFFECTS` blur/AL controller masks. OpenGL
    and Vulkan deliberately execute their mature full-view, resource, resolve,
    blur, and projected-light paths, reporting ownership only after the sealed
    coverage completes; any incomplete record retains the classic path.

Exit gate: every scoped Milestone D corridor has a sealed GL/Vulkan owner,
no visible light or surface is silently dropped, and rejection restores the
complete applicable domain or cross-domain tree to the classic result. The
implementation gate is complete while all corridors remain default-off; their exact contract, validation
procedure, and remaining boundaries are recorded in
[Shared Classic 2D GUI Domain](../../classic-gui-domain-modernization.md). This is not
a claim that the aggregate modern-visible renderer owns every stock frame. Local
Windows stock `game/storage1` engine captures passed with the corridor both off
and on for GL and Vulkan; enabled diagnostics recorded complete owned views and
explicit whole-view fallbacks on both backends. The second complete-domain
implementation is documented in
[Shared Classic World Ambient/Material Domain](../../classic-world-ambient-domain-modernization.md);
its bordered 1280x720 stock `maps/tools/mv2` option-off/on engine captures match
exactly on GL and Vulkan, enabled diagnostics report one owned pre-fog draw with
domain hash `dc18ed8c0539bbfc`, and the stock `shaderDemos/move` deform override
reports a named zero-draw whole-view fallback on both backends. These are local
development-worktree results, not clean-package or platform promotion. The
third complete-domain implementation and its shadow-coupled expansion are documented in
[Shared Classic Interaction-Lighting Domain](../../classic-interaction-domain-modernization.md);
its unshadowed controlled GL/Vulkan captures retain exact classic image parity,
and its expanded native/static gates cover the completed stencil, mapped,
mixed, dynamic/perforated, hybrid, and atomic-fallback contract. The documented
controlled and stock shadow profile is the runtime release-acceptance set.
Clean committed-package and target-platform/driver recapture remain promotion
requirements. The fourth complete-domain implementation is documented in
[Shared Classic Fog/Blend Domain](../../classic-fog-blend-domain-modernization.md).
Its native/static gate and controlled GL/Vulkan profile now pass exact
shared/classic engine-image parity, nonempty reconciled ownership, material
fog/blend deltas, and named
zero-commit atomic rollback. Authored-stock fog plus clean-package and
target-platform/driver promotion remain open.
The material-deform dependency is documented in
[Shared Classic Material-Deform Contract](../../classic-deform-domain-modernization.md).
The direct and capture-backed special-subview implementation is documented in
[Shared Special-Subview Transaction](../../classic-subview-domain-modernization.md).
The in-world GUI implementation is documented in
[Shared Classic In-World GUI Domain](../../classic-inworld-gui-domain-modernization.md).
The cinematic/authored-post implementation is documented in
[Shared Classic Cinematic and Authored-Post Transaction](../../classic-cinematic-post-domain-modernization.md).
The render-demo/Raven special-frame implementation is documented in
[Shared Render-Demo and Raven Special-Frame Transaction](../../classic-special-frame-domain-modernization.md).
The scoped Milestone D implementation is complete. The final controlled R6
cinematic-plus-`_currentRender` mirror transaction closes its narrow Windows
GL/Vulkan runtime gate with exact engine-TGA parity and named rollback; it does
not close the root, `_currentDepth`, broad subview, in-world-GUI, special-frame,
final-package, human-review, or platform/driver gates. Those remaining
qualifications stay on the separate Milestone D release-promotion track;
Milestone E no longer depends on expanding Milestone D's promotion scope.

### Milestone E: temporal presentation

1. **Implemented:** promote delayed backend GPU timing into a bounded,
   generation-aware, default-off dynamic-resolution controller.
2. **Implemented:** assign every visible motion domain to exact history,
   camera/depth reprojection, or explicit conservative reactive rejection.
3. **Implemented:** provide native-history TAA/TAAU with camera/capture resets,
   native-resolution UI, current-frame spatial fallback, and SMAA rollback.

**Local implementation exit gate passed on Windows:** dependency-light and
cross-repository contracts cover history, controller, motion-domain, depth,
capture, and ABI invariants. Windowed engine-TGA gameplay covers SP and MP,
stable motion, particles, the weapon view, portals/subviews, screenshots, and
both GL/Vulkan paths; targeted camera-cut, menu/native-UI, fixed-scale,
save-preview, and SMAA rollback cases complete the gate. Clean staged-package,
additional platform/driver, and retained human-review evidence remain release
promotion work rather than implementation blockers.

### Milestone F: modern materials and advanced lighting

1. **Implemented and locally validated; release promotion pending:** keep direct PBR explicitly
   authored and default-off. Unsupported materials retain their complete classic
   owner, retail content is never inferred as PBR, and the original procedural
   `.tmp` fixture provides deterministic albedo/normal/ORM inputs without
   incorporating external assets.
2. **Implemented and locally contract-validated; broader authored-scene evidence pending:** authored OpenGL specular probes
   use a fixed eight-cubemap atlas, at most 32 frame records, and deterministic
   top-two selection per cluster. Sampling now uses GGX-filtered specular,
   diffuse irradiance and box-projected parallax (`boxParallax`) with analytic
   fallback, probes can be captured in the engine (`bakeReflectionProbes`), and
   Vulkan has a native consumer.
3. **Implemented and locally contract-validated; broader authored-scene evidence pending:** eligible OpenGL clustered decals
   transfer ownership only through one prepare/seal transaction bounded to
   1,024 records and 65,536 cluster references. Any malformed, stale,
   incomplete, or overflowing input publishes no ownership for the affected
   transaction.
4. **Safeguard retained:** clustered/GPU-driven visible-lighting submission is
   not promoted. `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` remains `0` until
   visible-lighting parity is proven independently.
5. **Implemented and locally validated; release promotion pending:** froxel
   volumetrics, SSR, and SSGI are independent default-off GL/Vulkan leaves in
   the native scene-presentation tail. Shared admission clamps work to 16
   depth slices, 16 reflection steps, and eight GI taps; missing resources keep
   the current/classic presentation owner, and `r_rendererModernQuality 0`
   publishes an exact zero-feature packet. The implementation is deliberately
   screen-space: it does not claim shadowed per-light volumetric injection,
   roughness-aware G-buffer reflections, or world-space/multi-bounce GI.

**Local implementation exit gate passed on Windows:** the 2026-08-23 evidence
under `.tmp/milestone-f-evidence/20260823-final/` uses a current-source debug
x64 build. Static PBR/advanced-lighting checks passed, the final native suite
passed 10/10, the final focused engine rerun passed 2/2 after the earlier 8/8
safe set, and the four-role retail baseline passed against 40 PK4s with zero
loose retail files. Controlled OpenGL GL 3.3/4.1/4.3/4.5 and Vulkan fixture
runs prove visible PBR execution, a non-vacuous enabled/disabled image delta,
and exact `r_rendererModernQuality 0` rollback. This gate does not claim
RenderDoc evidence or broad authored probe/decal scene coverage. The leaf
controls remain default-off, `MODERN_LIGHTING_PARITY_PROVEN_DOMAINS` remains
`0`, and final committed-package, platform/driver, retained-review, and release
promotion remain pending.

**2026-08-24 advanced screen-space gate:** the dependency-light
`AdvancedScreenSpaceCoreTest` and the static advanced-lighting contract pass,
and the pinned Vulkan temporal-resolve shader matches the checked-in GLSL.
Windowed `game/airdefense1` gameplay passes with all three leaves together on
OpenGL and Vulkan, with zero shader/FBO/GL/Vulkan-validation/VUID/call/fatal or
engine-error counters. OpenGL also passes each leaf independently. The combined
OpenGL engine-TGA capture differs non-vacuously from the same-build default
control; the live BSE/actor scene is not an exact-hash fixture, so exact master
rollback is enforced by the zeroed shared packet and supplemented by a clean
master-off gameplay run. Two post-audit captures observed OpenGL at
102.9--117.3 Hz (final hardened P95/P99 11/11 ms) and Vulkan at
114.1--125.8 Hz (final hardened P95/P99 10/11 ms) on this development system.
The same staged package passed default
`game/airdefense2` gameplay and pure auto-joined `mp/q4dm1` on both backends,
the complete 11/11 native suite, and a fresh four-role compatibility run
against 40 verified retail PK4s with zero loose retail files.
See the [user guide](../../../user/advanced-screen-space-lighting.md) and retained
[`airdefense1` optimization evidence](../../airdefense1-optimization-evidence.md).

## Promotion evidence for every milestone

Each milestone should record:

- source provenance and retained notices for incorporated code;
- focused unit/static tests and malformed-cache/input tests;
- Windows x64 builds plus Linux/macOS compile-policy coverage appropriate to the
  changed subsystem;
- stock-only SP load/save/reload/demo evidence;
- pure MP listen-server and auto-joined client gameplay evidence;
- engine-render-target screenshots and human visual review;
- before/after CPU frame, GPU frame, load time, memory, and cache-size metrics;
- rollback results with the new feature disabled;
- confirmation that no new loose content is required.

The [engine capability matrix](../../engine-capability-matrix.md) remains the current
truth. This roadmap describes sequence and acceptance gates; it does not mark a
capability implemented merely because BFG source exists or a prototype compiles.
