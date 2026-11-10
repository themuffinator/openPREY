# PBR rendering completeness audit

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: in progress. This task audits and completes the authored PBR material
path and proves the result with a purpose-built, reproducible in-engine map.
From 2026-10-04 the remaining production work (complete roughness/AO shading,
per-surface OpenGL PBR in real gameplay, presentation, defaults) is tracked in
the [production-readiness plan](2026-10-04-pbr-production-readiness.md).
It coordinates with the Vulkan gap-closure task; neither task may claim the
other backend is qualified merely because shared material metadata exists.

As of 2026-09-23 the separate PBR task is terminal. The user resumed the
[Vulkan gap-closure task](2026-09-20-vulkan-gap-closure.md), which now owns the
remaining Vulkan/PBR work and build/GPU execution. Its screenshot investigation
found stock HDR washout with PBR disabled; that repair does not close the native
environment/probe and full color-management requirements recorded below.

The v41 follow-up narrows the remaining 125%/8x emissive edge difference to
viewport/rasterization rounding. Uploaded geometry and the shader-produced
positions at the affected edge agree. A deliberately reflected Vulkan
viewport control matches GL exactly after normalizing that reflection.
The renderer source is restored to v40, and the original strict comparison
remains failed. No material, BRDF or shader change is retained from this
investigation. See the [edge evidence](../../../vulkan-hdr.md#125-percent-msaa-edge-investigation).

The v40 follow-up closes the classic 8x color-edge SMAA failure by explicitly
averaging stored RGBA8 samples. All thirteen raw/display pairs pass within one
byte, all 124 independent 4x/8x SMAA controls pass, and 60/62 full-frame pairs
pass; only native HUD anisotropy still fails. All eighty 8x PBR preview controls
pass independently. The separate 125% coverage comparison remains failed,
maximum 49, while the other 39 pairs pass. This change does not extend PBR
admission or establish broader platform/performance qualification. See the
[resolve contract](../../../renderer-image-capture.md#rgba8-multisample-resolve).

The v39 follow-up repairs the 150% HDR-off PBR resolve failure exposed by v38:
explicitly averaging stored float samples produces an exact GL raw-scene match
and a display difference of at most one byte after SMAA. All 160 independent
4x/8x preview/recovery controls pass, as do all 26 image-capture controls, the
Vulkan HDR GPU contract and both staged stock SP/MP runs. Forty paired images
pass at 4x and 39/40 at 8x. A newly added 125%/8x control separately differs
at one scene texel and three display pixels; GL depth/color probes place it
before the final handoff, with GL 3.3 and 4.5 agreeing. This comparison remains
failed and also reproduces with the archived v38 Vulkan module. The classic
8x color-edge SMAA difference is now traced to native resolve
of identical stored samples, and remained open until v40. Capture correctness does
not establish complete PBR parity. See the
[current Vulkan work record](2026-09-20-vulkan-gap-closure.md#work-record).

The v37 follow-up preserves requested MSAA in supersampled OpenGL PBR scenes
and prevents repeated resolution changes from exhausting the render-target
cache. Both GL allocation paths pass 39 lifecycle controls, each recycling
326 targets while restoring the original images exactly. The shared seventeen
linear HDR pairs and eighteen display pairs also match exactly. Native HUD
anisotropy and one 8x classic color-edge SMAA case remain outside the existing
display comparison gate; broader PBR admission is unchanged. See
[target lifetime and presentation evidence](../../../vulkan-hdr.md#supersampling-and-render-target-lifetime).

The v36 follow-up closes the bounded HDR-off fog/blend preview mismatch.
OpenGL now uses its exact authored fog geometry and blend stages before
transparent PBR, retaining encoded classic colors and avoiding a second
clustered/shared contribution. All 111 full-frame GL/Vulkan image pairs at
0x/4x/8x pass the existing two-byte gate with the default lighting-parity
setting. Fourteen separate HDR controls preserve authored radiance and
transparent background composition. Vulkan's v35 binary is unchanged; this
fix corrects the OpenGL reference and does not promote either experimental
path. See [preview scope and retained evidence](../../../vulkan-hdr.md#pbr-previews-with-tone-mapping-off).

The v30 follow-up closes scaled GL/native HDR comparisons for eligible complete
views: all 33 post pairs and sixty composition pairs at 50/75/125% pass within
one byte/channel. It also fixes the game's GL forward/resolve target clipping
emission before tone mapping. Independent radiance, MSAA, animation and staged
SP/MP regressions pass. This bounded result leaves unsupported material,
baked-lighting, portal/capture and post-effect combinations open; see
[HDR scope and retained evidence](../../../vulkan-hdr.md).

Native authored ambient lights now evaluate the PBR diffuse response and take
part in complete transparent admission and replay. All 82 dedicated captures
pass independent radiance, material and alpha/recovery checks at 0x/4x. The GL
mixed classic/ambient reference declines modern ownership, so it is retained
as an invalid comparison rather than a parity pass. The 36 ambient capacity,
88 resource and 136 direct-light integration captures also pass. The full
linear HDR scene contract is still open. See
[native ambient lighting](../../../vulkan-pbr-ambient.md).

The resumed task has since implemented the native analytic environment pass
using the shared filtered source, diffuse convolution and BRDF lookup data.
Local 0x/4x qualification passes 27 Vulkan and 26 OpenGL controls at each sample
count, with all common specimen comparisons passing. The investigation also
fixed zero-direct-light transparency admission, image reload of adopted MSAA
targets, and filtered cutout coverage. Authored probes, baked diffuse composition
and full color management remain separate requirements. Details and retained
failures: [Vulkan PBR environment](../../../vulkan-pbr-environment.md).

The native authored-probe source bridge now reads resident cubemap faces with
explicit color decoding, generation checks and complete-output admission.
Native atlas residency, shared CPU selection and visible probe blending are
now connected. Original LDR sources pass all 172 native/GL captures and 80 paired
comparisons at 0x/4x, including capacity, lifecycle, resource failures and
transformed receivers. Full HDR input/accumulation and broader platforms remain
unqualified. The default-light-grid correction has its own 60-capture,
40-toggle qualification at 0x/4x, preserving environment light where no baked
grid applies. Later direct-light candidates have separate gates.
See [Vulkan probes](../../../vulkan-pbr-probes.md) and the retained
[source-reader qualification](../../../vulkan-probe-sources.md).

Further per-light isolation finds projected-light receiver coverage differences
between clustered GL and native Vulkan. A separate native transparency defect
has been repaired: full-mesh opacity no longer depends on the first light's
triangle subset, and instances of the same model retain separate light records.
The dedicated partial-light regression and remaining qualification scope are
recorded in the same environment ledger.

The native direct-light frontend now preserves normal-mapped PBR triangles
that classic geometric facing rejection would remove. A fully back-facing
plane proves real mapped illumination, classic rollback and light-volume
rejection, including an old-binary negative control. The plane receiver passes
at 0x/4x; classic ceiling MSAA differences and several curved grazing pixels
remain failed comparisons. See [receiver geometry](../../../vulkan-pbr-geometry.md).
Native full-surface material diagnostics are also under qualification so
unlit materials can be inspected independently of direct-light coverage.
The v25 62-capture suites pass semantic checks at both sample counts, and all
seven original unlit views pass. Constant normals and non-mipmapped sampling
match within one byte; independent sample-position oracles reproduce the
opaque sphere's complete 4x coverage. The 44 transparent resource/restart
controls pass again at 0x/4x. A separate 20-image HDR comparison reproduces a
larger native PBR presentation gap: native output still uses the stock tone
curve rather than GL's linear PBR filmic/output transfer. Details:
[material diagnostics](../../../vulkan-pbr-diagnostics.md).

The next capacity investigation reproduces mixed native/classic transparency
above the 256-record limit. Vulkan now counts the complete candidate view before
drawing and declines native transparency when it cannot fit, with observable
admission and draw counters. The capacity regression compares overflow with
the complete classic image and checks restoration at the exact limit.
Shadowing-transparent ownership remains open; subsequent resource preparation
is qualified separately below.

The same change keeps view admission alive through the fog pass's drawing-state
reset. Both seven-control post-fog suites pass the independent authored-alpha
equation at 0x/4x; the old v9 renderer fails it by approximately 112 bytes.
The 18 capacity controls pass at each sample count, while all 50 existing
partial-light captures remain byte-identical to v9. The environment ledger and
`.tmp/vulkan-gap-closure/pbr-capacity/` retain the complete v10 evidence.

Native transparent coverage, lighting and environment resources are now prepared
as one transaction before drawing. Failures release speculative allocations and
retain the complete classic path; committed draws bind retained resources and
geometry offsets. All 44 injected-resource controls pass at both 0x and 4x, with
exact whole-frame fallback and recovery, late failures after earlier light
records, actual descriptor rollback, reload/restart and environment-only views.
The v12 module and evidence are retained under
`.tmp/vulkan-gap-closure/pbr-resources/`. This qualifies the native transparent
preparation path, not arbitrary device exhaustion, other resource consumers,
authored probes or broader hardware/platform support.

## Target and boundaries

The target is the PBR quality expected of the id Tech 6 generation: consistent
metallic/roughness shading, linear lighting and HDR presentation, filtered
environment lighting, stable normal/specular response, and correct interaction
with shadows, transparency and existing content. This is not a claim to
reproduce proprietary id Tech 6 source or its entire renderer.

Reference context: [id Software's SIGGRAPH 2016 presentation](https://advances.realtimerendering.com/s2016/)
and the equations and validation discussion in
[Physically Based Rendering in Filament](https://google.github.io/filament/main/filament.html).
Implementation is authored for openQ4; incorporating external code requires a
separate licence check and attribution.

Stock materials keep their authored classic behavior. PBR remains explicitly
authored and must have a complete, observable fallback. Test assets are original
procedural data generated under `.tmp/`, never a new shipped asset dependency.

## Completion evidence

| Requirement | Proof needed | Status |
|---|---|---|
| Material semantics | Scalar, packed ORM and separate maps agree; color/data transfer functions, normal encodings, factors, emissive, cutout and source alpha behave correctly. | Numerical tests and v60 GL material/HDR/MSAA controls pass; native Vulkan breadth remains open |
| Direct BRDF | Numerically verified GGX/Smith/Schlick, bounded energy, stable grazing/degenerate cases, consistent GL and Vulkan equations. | Shared numerical kernel and v60 GL direct-light/shadow controls pass; Vulkan consumers remain narrower |
| Environment lighting | Roughness-filtered specular, integrated BRDF response and diffuse irradiance; spatially stable probe orientation, blending and fallback. | Replaced with GGX prefilter, diffuse convolution and split-sum LUT; authored-probe negative control passes |
| Image quality | Normal/specular aliasing control and correct normal-space transforms. | Numerical tests and v60 normal-encoding, CPU/GPU deformation and restart controls pass |
| Render ownership | PBR replaces the intended draw exactly once, mixed classic/PBR scenes survive, and shadow/fog/post/transparent ordering is preserved. | Production admission, viewport edges, source alpha and static/dynamic/multiple-light shadows pass for PBR plus strict classic diffuse. Linear fog/blend composition passes on GL 4.5 and GL 3.3, including shared-native ownership, transparency and 4x MSAA controls. Baked PBR/IBL composition, GL 3.3/4.5, reloads, MSAA, normal encodings and combined fog/blend checks pass. Native Vulkan full-map ownership now passes too, including ordered source alpha measured against its own emission control. Broader mixed materials remain |
| HDR/presentation | Highlight range survives composition, exposure/tonemap applies once, UI is unaffected. | v60 GL 3.3/4.5 boundaries, independent filmic/sRGB references, extreme emission, bloom, auto-exposure and exposure-independent HUD controls pass; encoded previews are refused as linear captures |
| Robust proof map | Multiple material stations, curved geometry, colored/projected lights, shadows, normal formats, transparency, emissive and probes with fixed camera captures and negative controls. | Implemented; moving/restored casters, three point lights plus a projector, unoccluded-wall acne and disabled-shadow controls pass |
| Lifecycle/fallback | Reload/restart, disabled features, unsupported input and resource limits retain valid output. | Parser, resource, shader, pixel transfer, reload/restart, and budget/atlas/receiver fallback controls pass; final regression remains |
| Regression | Windowed SP/MP gameplay on retail PK4s; no input injection or OS screenshot capture. | SP save/load, separate demo playback and MP active gameplay pass; performance outliers and final runtime remain unqualified |
| Documentation | Accurate authoring guide, capability notes, release notes, retained reproducible commands and evidence. | Authoring guide, capability/validation matrices and 0.13.2 notes updated; overall qualification remains open |

## Coordination

The PBR task initially owns GL/shared PBR analysis, new PBR-only source files,
the PBR fixture generator/tests and this document. The task **Assess Vulkan
renderer gaps** (`01a0bd4c-edb8-70f3-a01e-89b6723c8f69`) owns its Vulkan/module
changes. Agree shader and shared-document changes before editing overlapping
files. Serialize shared `builddir/` builds and `.install/` staging; use independent
runtime copies and isolated savepaths below `.tmp/` for tests.

The user subsequently paused the Vulkan task and authorized this task to take
over after the PBR phase. After v60's 74-control GL matrix and retail checks,
this task takes over the known Vulkan partial-restart crash and native PBR
parity work. The peer remains inactive; it is not resumed or messaged. Builds,
staging and GPU tests remain serialized.

## Retained evidence (work in progress)

- `.tmp/pbr-audit/proof-v5-channels/report.json`: 18 GL cases pass. Scalar/packed/separate channels agree, AO affects indirect light only, source alpha blends once, probes visibly affect metal, and all three normal encodings agree. Disabling the expression cache leaves the image byte-identical.
- `.tmp/pbr-audit/proof-v8-flows/report.json`: lit, overbright emissive, off-screen post target and SMAA pass, with TGA and linear float PFM captures. The emissive reference is approximately `(0.0520, 2.3125, 4.0)`, without clipping. Static/dynamic shadow cases remain failures.
- `.tmp/pbr-audit/selftests-v8/baseoq4/logs/openq4.log`: material parser, resource table, PBR visibility, GL executor/shader library, compatibility, cluster grid and pass ownership tests pass. Pixel transfers restore 16 deliberately poisoned store settings, two PBOs and the active texture unit.
- `.tmp/pbr-audit/proof-v8-msaa/report.json`: failed qualification. Startup allocates four samples, but modern presentation reports zero effective samples and a GL error. This is not MSAA proof.
- `.tmp/pbr-audit/proof-v15-shadows/report.json`: eight shadow controls pass with synchronous GL diagnostics and linear/display captures. Moving a caster changes fixed receivers; with shadows disabled those receivers stay fixed; restoring the caster reproduces the original image exactly. Manual point comparison and disabled static caching are byte-identical controls. Four unoccluded wall patches reject the acne present in earlier versions.
- `.tmp/pbr-audit/proof-v15-multi/report.json`: three distinct current-frame point maps and one projected map render successfully and visibly differ from the same scene with shadows disabled. Texture-binding and vertex-buffer cache repairs removed the undefined sampler and driver crash found by this test.
- `.tmp/pbr-audit/proof-v16-msaa/report.json`: the modern forward scene uses four-sample color and depth targets and explicitly resolves both. The ownership image contains 2,692 partially covered silhouette pixels and no changed fully covered interior pixels. This supersedes the failed v8 MSAA evidence.
- `.tmp/pbr-audit/proof-v17-display/report.json`: five HDR/post/SMAA cases pass. Emissive display values are `(61,248,253)` at exposure 1 and `(34,236,246)` at exposure 0.5, within one byte of independently evaluated filmic/sRGB references. Float captures preserve the same original radiance at both exposures.
- `.tmp/pbr-audit/proof-v19-fallback-budget/report.json` and `.tmp/pbr-audit/proof-v19-capacity/report.json`: budget rejection and a point map too large for the bounded atlas both fail closed, with byte-identical classic controls. Cached interactions belonging to metadata-only reflection probes no longer leak additive lighting into these fallback frames.
- `.tmp/pbr-audit/proof-v19-local-global-precache/report.json`: mixed LOCAL/GLOBAL receiver semantics retain complete classic ownership with byte-identical output and clean diagnostics. The test explicitly uses a `noSelfShadow` material; an entity flag alone did not exercise this contract.
- `.tmp/pbr-audit/proof-v19-msaa/report.json`: five four-sample controls pass, including current shadows and alpha-to-coverage. Enabling alpha-to-coverage changes 155 pixels along interior cutout boundaries, independently of geometric silhouette antialiasing. The disabled-shadow control differs on 217,138 pixels.
- `.tmp/pbr-audit/proof-v19-lifecycle/report.json` and `.tmp/pbr-audit/proof-v19-map-reload/report.json`: shader/image reload and partial/full video restart are byte-identical to the initial frame. The corrected map-reload run also matches exactly. Its first run froze simulation before new entities could publish their render state; that failed capture remains recorded.
- `.tmp/pbr-audit/proof-v19-msaa-lifecycle/report.json`: partial/full MSAA restarts pass a bounded float/display comparison. There are 71 changed float channels, each one FP16 rounding step, and one changed display channel. The report records the offline reanalysis; it does not claim new captures. Non-MSAA lifecycle comparisons remain byte-exact.
- `.tmp/pbr-audit/proof-v19-gl41/report.json`, `.tmp/pbr-audit/proof-v19-gl43/report.json`, and `.tmp/pbr-audit/proof-v20-gl33/report.json`: four controls each pass for lit, ownership, HDR emissive and shadows. GL 3.3 previously clipped the scene to RGBA8; it now uses its supported RGBA16F target. These are requested tiers on one NVIDIA device, not independent vendor coverage.
- `.tmp/pbr-audit/proof-v21-gl33-msaa/report.json`: GL 3.3 now passes HDR MSAA and shadows. Empty GUI/post views no longer consume cluster-grid headers and starve the world's bounded UBO light list.
- `.tmp/pbr-audit/proof-v21-samplers-offset/report.json` and `.tmp/pbr-audit/proof-v21-gl33-samplers/report.json`: authored nearest/repeat, linear/repeat, clamp and mip filtering all pass on GL 4.5 and 3.3. Nearest is entirely black/white; linear filters 44.6% of the patch and mip filtering 90.8%; clamp samples its independently known black border. The older v20 build produces the same incorrect image for all four controls and fails the earlier negative-control run.
- `.tmp/pbr-audit/selftests-v21/report.json`: current material/resource/visibility, GL executor, compatibility, cluster grid and ownership self-tests pass, including 56 shader permutations and deliberately poisoned pixel-transfer state. Parser warnings in this report belong to intentional rejection tests.
- `.tmp/pbr-audit/proof-v23-skinning/report.json`: ten CPU/GPU pose, restore, normal and ownership controls pass. All five CPU/GPU image pairs are byte-identical; rotating the second joint changes 23,639 pixels and restoring it reproduces the initial image exactly. Earlier controls caught two real defects: frame-temporary GPU vertices expired while an unchanged pose retained the cached model, and CPU culling bounds applied the inverse bind transform twice. GPU output now belongs to the surface cache; CPU position-only skinning uses absolute joint poses with joint-local weighted offsets.
- `.tmp/pbr-audit/proof-v23-skinning-restart/report.json`: partial and full video restart preserve the frozen GPU-skinned reference image byte-for-byte, with GPU preparation and complete current-frame point/projected shadows confirmed.
- `.tmp/pbr-audit/stock-v21-qualified/stock_asset_baseline_report.json`: SP `storage1` gameplay/save/load and MP `q4dm1` server/client gameplay completed using independent copies of 40 retail PK4s and no loose retail overrides. Runtime integrity and render-error checks pass, but the suite **fails performance qualification** on intermittent approximately 500 ms frame outliers. SP demo playback was skipped by that failed gate and remains to be run. These results do not establish release performance or the final v23 runtime.
- `.tmp/pbr-audit/stock-v25-demo/report.json`: the skipped SP render-demo playback was run separately against the v27 renderer (the directory name predates that build). All 55 recorded frames complete, with clean fatal/shader/API error checks and windowed execution. This closes that functional omission without overriding the baseline's failed performance gate.
- `.tmp/pbr-audit/selftests-v27/report.json`: all 15 scene/material/resource/shader/executor/cluster/ownership success markers pass after the scoped material admission changes. The global classic parity mask remains zero.
- `.tmp/pbr-audit/proof-v27-admission/report.json`: eight of nine checks pass. With the parity override at zero, the curved classic diffuse control differs from the native reference by a mean 0.289 bytes and maximum three; an unsupported classic specular material retains a byte-identical complete classic frame. The planar comparison still fails and exposed hard UV clipping and source-edge filtering errors in the light-image atlas. This snapshot is not admission qualification.
- `.tmp/pbr-audit/proof-v30-isolated-lights/report.json`: isolates the failed floor to projected lighting, and catches IBL being blocked when the last direct light is disabled. Offline native-patch analysis passes all four point-light patches but rejects the projector floor. These are useful negative controls, not qualification.
- `.tmp/pbr-audit/proof-v31-admission/report.json`: normal production lighting now passes every planar patch (mean 0.45–0.71 bytes, maximum two) and the curved patch (mean 0.289, maximum three), with `override=0 materialContract=1`. Single-tile screenshots preserve scissors instead of changing native projector behavior. The deliberately disabled-scissor case still fails because native per-interaction triangle culling is not represented by clustered bounds; that diagnostic/tiled mode now retains complete native ownership.
- `.tmp/pbr-audit/proof-v31-isolated-lights/report.json`: point and projected native-patch comparisons pass and both zero-direct-light frames execute PBR. Its remaining emissive failure was an incorrect test assumption: the emissive specimen also reflects environment light. The revised oracle checks its exact emitted radiance with IBL disabled, and keeps the AO-zero invariance control.
- `.tmp/pbr-audit/proof-v32-production-post/report.json`: 22 of 23 checks pass with the harness defaulting to parity override zero. Material channels, source alpha, expression caching, native backdrop parity, forced-parity equivalence and the disabled-scissor byte-exact native fallback pass. Bloom raises 980,316 pixels without darkening; bounded automatic exposure matches manual half exposure byte-for-byte, and asynchronous/synchronous exposure captures match exactly. The HUD control correctly fails: world ambient ownership suppressed its native GUI fallback. The repair and current-source rerun are pending.
- `.tmp/pbr-audit/proof-v33-post-ui/report.json`: all eight post/HUD controls pass after separating fullscreen GUI fallback from world ownership. The HUD affects 29,531 pixels and retains 742 midtone pixels across two scene exposures. Source float captures remain identical across UI, bloom and exposure controls. GPU log-average luminance is 0.394677 versus independently integrated 0.398940 (1.07% difference); exposure converges to 0.456069. Synchronous and asynchronous results match byte-for-byte.
- `.tmp/pbr-audit/selftests-v33/report.json`: all 15 success markers pass, including the new fullscreen-GUI/world ownership distinction. Expected parser-rejection warnings remain explicitly recorded.
- `.tmp/pbr-audit/proof-v33-fog/report.json`: native fog visibly affects the complete frame and its PBR-rejected/native images match, but GL diagnostics reject qualification. The errors are being traced before claiming the fallback flow is sound.
- `.tmp/pbr-audit/proof-v37-fog-scope/report.json`: synchronous pass labels identify the error in discarded modern indirect/diagnostic draws, not the native fog pass. The fog shader shares the transparent-lighting body but omitted its shadow/probe/cluster resource contract, leaving cube and 2D samplers aliased on unit zero. Resource metadata, initial unit assignments and indirect bindings now match the shared shader.
- `.tmp/pbr-audit/selftests-v38/report.json`: all 15 success markers pass with synchronous driver diagnostics. The shader check independently inspects linked uniforms in all 56 programs, rejects a deliberately aliased fog cube sampler, and restores the original binding before any draw.
- `.tmp/pbr-audit/proof-v38-fog/report.json` and `.tmp/pbr-audit/proof-v38-blend/report.json`: five controls each pass with clean GL diagnostics, byte-exact native fallback and exact PBR restoration after removing the light. Visual review found the fog too dense to demonstrate receiver detail; a thinner fixture and a visibility oracle are being qualified before accepting that image as composition proof.
- `.tmp/pbr-audit/proof-v38-fog-transparent/report.json`: all five controls pass with the revised fog density and explicit receiver-visibility requirement. The engine image has been visually checked: room planes, curved receivers, cutout and the post-fog transparent specimen remain visible. Native equivalence and exact PBR restoration still pass, with no GL errors.
- `.tmp/pbr-audit/proof-v38-lightgrid/report.json`: all three baked-lighting controls pass. Four probes capture 24 faces from the original room into the run's isolated save path; disabling the resulting indirect light changes 774,453 pixels. The unsupported modern receiver contract retains the whole native frame, byte-identical to the explicit classic control. This proves fallback, not a modern metallic-aware light-grid consumer. Its log also exposed a stale `si_map` progress label; the label now uses the active-world identity already used for output paths.
- `.tmp/pbr-audit/proof-v38-admission/report.json`: all 12 production/native/forced-parity/shadow/rejection controls pass with synchronous GL diagnostics. The four interior backdrop patches and four viewport-edge strips differ from native by mean 0.13–0.78 bytes, maximum three; the curved classic patch is mean 0.289, maximum three. Inclusive scissor bounds now include the final pixel row/column. Unsupported classic-specular and disabled-scissor modes remain byte-exact native fallbacks.
- `.tmp/pbr-audit/proof-v38-isolated-lighting/report.json`: all six isolated point/projected/native/environment controls pass with synchronous GL diagnostics. PBR remains active without direct lights, the AO-zero reference is unchanged by environment lighting, and the no-environment emissive control retains its independently specified radiance. Point and projected backdrop comparisons include all four viewport edges.

- `.tmp/pbr-audit/stock-v39-perf-hidden/` and the v40 `stock-v40-trace`, `stock-v40-orphaned`, `stock-v40-visible`, and `stock-v40-finish` reports reproduce the stock performance failure with PBR/modern rendering disabled. CPU P99 ranges from 449 to 480 ms; hidden/visible windows, persistent/orphaned uploads and `r_finish=1` all retain the stalls. With persistent uploads disabled, the delay appears inside the swap/presentation phase. That timer includes final post effects and optional `glFinish`, so it does not yet isolate the OS swap call. The optional `rendererBenchmarkCapture "logs/frame-timing.csv"` trace records CPU and delayed GPU frame IDs separately. No performance budget was relaxed.
- `.tmp/pbr-audit/proof-v41-fog-hdr/` is a **rejected prototype**, despite its original telemetry-only report: the offscreen fog pass submitted 26 primitives and claimed ownership, but linear captures were unchanged. Default fixed-function initialization culled both face orientations while its tracker already claimed the front-sided state. The new radiance oracle rejects this result and requires a consistent fog contribution on every opaque specimen before composition can qualify.
- `.tmp/pbr-audit/proof-v42-fog-hdr/` and `proof-v42-blend-hdr/` reject a second prototype: fixed-function projection and the modern depth producer differed by rounding, so equal-depth receivers had visible holes/stripes. The shared phase now uses an invariant GLSL position calculation with the same combined matrix as the modern depth pass, retaining its exact authored texture/blend operations.
- `.tmp/pbr-audit/proof-v43-fog-hdr/report.json` and `proof-v43-blend-hdr/report.json`: four controls each pass. Fog contributes consistently to all 22 opaque specimens (49 pixel samples each); observed alpha spans 0.4066–0.4153 with maximum within-patch variation 0.0033. The constant blend-light control multiplies each linear channel exactly once within FP16 tolerance. Off/restored controls reproduce both display and HDR captures byte-for-byte. The fog image was visually checked for the previous depth holes.
- `.tmp/pbr-audit/proof-v44-fog-hdr/report.json`: seven controls pass, adding byte-exact output with the shared classic fog owner enabled and a transparent-sphere hide/show differential. Fog changes only the background contribution behind source alpha, at the independently authored transmittance `1 - 112/255`.
- The final v44 fog/blend qualification also passes `proof-v44-blend-hdr` (7/7), `proof-v44-fog-gl33` and `proof-v44-blend-gl33` (7/7 each), and the two `*-msaa` reports (4/4 each). Fog/MSAA restoration is exact. Blend/MSAA restoration differs in 40 float channels by one FP16 ULP and in one display byte by one; explicit offline reanalysis applies the **existing** MSAA lifecycle budget, without expanding it. Admission (12/12), native baked-light fallback (3/3), and renderer self-tests (15 markers) pass on that runtime.
- The first baked-PBR candidate, v45, compiled and submitted 25 baked receivers but correctly remained unpublished because its early pass inventory still reserved the nonempty light-grid pass for the native owner. The failed captures remain under `proof-v45-lightgrid`; no PFM was produced for rejected frames. This exposed and repaired a harness exception on missing HDR files. v46 connects the inventory to current-frame receiver preflight. Its initial six numerical controls pass; an extended run remained failed because the test profile disabled its requested shader reload. No renderer error was suppressed.

These are development snapshots, not a claim that the final renderer is qualified. Each report retains runtime hashes, fixture identity, commands, logs and engine render-target captures.

## Implementation findings and changes

- Earlier procedural evidence applied one packed material to `maps/tools/mv2`
  through a material override. The new laboratory uses separately authored
  materials on original geometry, including a two-joint animated specimen and
  explicit changed/unchanged controls.
- The direct BRDF now shares tested GGX/Smith/Schlick equations, the correct
  one-quarter visibility factor, a common perceptual roughness floor, and
  stable degenerate/grazing evaluation. Vulkan uses the same core equations;
  its native material and environment coverage still requires completion.
- Color images use the exact sRGB transfer function and linear-light mip
  filtering. Normal and material-data images remain linear.
- Authored environments now use original GGX importance sampling, diffuse
  irradiance convolution and a split-sum BRDF LUT. Roughness levels retain
  their authored environment rather than fading to an unrelated sky.
- The analytic fallback is anchored in world space and follows the same
  filtered environment path as authored probes.
- GPU-skinned surface cache lifetime and CPU culling bounds now agree with
  cached-pose reuse and the joint spaces of their source vertex data.
- Production lighting admission is scoped to authored PBR and a proven classic
  flat-normal, single-diffuse, black-specular material contract. It does not
  promote arbitrary stock materials or change the global classic parity mask.
  Unsupported classic material, receiver, atlas, budget and disabled-scissor
  cases retain the complete native frame.
- Light-image sampling preserves the authored clamped border and clamps atlas
  reads to source texel centers. CPU bins, probe selection and fragment tile
  lookup use the same bottom-origin screen convention.
- Empty graph interaction nodes no longer block environment-only PBR. Native
  fullscreen GUI fallback is independent of world material/pass ownership.
- Fog shader metadata now declares every resource used by its shared
  transparent-lighting body. Linked-program sampler validation detects type
  aliases independently of that metadata. Synchronous GL diagnostics retain
  the submitting pass name; asynchronous messages do not invent one.
- A qualified single-root, full-viewport linear PBR frame now executes the
  sealed classic fog/blend domain inside its scene target, between pre-fog
  geometry and ordered transparency. It uses the same depth transform as the
  modern producer, preserves arbitrary supported authored blend states and
  texture matrices, and prevents the later native owner from drawing again.
  It does not commit native coverage during offscreen preparation; unsupported
  geometry or resources still retain complete native ownership. Cropped views,
  encoded preview and mixed deferred contributions remain outside this contract.

### Baked irradiance qualification

The modern forward opaque/alpha-test shader now samples each receiver area's
existing irradiance, visibility and relocated-probe atlases. PBR decodes legacy
LDR irradiance to linear space and applies diffuse Fresnel, metalness and AO.
Baked diffuse replaces environment diffuse; authored/analytic reflections keep
their specular contribution. Native non-receivers, including source alpha, do
not inherit a previous surface's grid. Atlas admission validates the real
forward draw and image dimensions before granting the whole view ownership.
The native grid pass is skipped only after complete forward submission.

- `proof-v46-lightgrid/report.json`: 6/6 controls pass. Maximum double-intensity
  error is `0.000389` linear radiance. Pure-metal and zero-AO patches gain zero
  diffuse; dielectric patches gain `0.1785–0.3338` per channel. Disable/restore
  captures are byte-exact. The engine image was visually inspected.
- `proof-v47-grid-lifecycle/report.json`: 13/13 pass with binary/fixture/map
  hashes. Baked/IBL separation, image reload, an actual 56-program shader reload,
  partial video restart and full restart pass; restored display and float
  captures are exact. The new nonmetal normal specimens are original generated
  fixture materials and are precached by the map.
- v47 clears frame-owned grid pointers before every analysis, including disabled
  frames. Sampler bindings and the grid uniform follow reflected program
  generations through both draw plans and submit plans. GL 3.3 (6/6), 4x MSAA (6/6), nonmetal normal encodings (4/4), combined
  fog (4/4), combined blend (4/4) and native fallback (3/3) pass in the
  corresponding `proof-v47-grid-*` reports. Equivalent XYZ/RG normals differ by
  `0.0184` display bytes on average; XYZ/AGB is exact. Disabling normal-map
  perturbation changes the baked-only specimen by `10.38` bytes on average.
  MSAA restoration is exact; zero intensity/off controls differ by at most
  47 float channels at one FP16 ULP, within the existing lifecycle budget.

- The completed v47 set contains **81 passing map controls** and **15 passing
  renderer self-test markers**. The final five reports add master-off/native
  equality plus exact PBR restoration (4/4), GL 3.3 baked/IBL composition (5/5),
  GL 3.3 4x MSAA (6/6), and fog/blend with shared-native ownership and
  hidden-transparent-background controls (7/7 each). The existing admission
  suite remains 12/12. All 56 GLSL programs pass sampler-type validation with
  the three new baked samplers; GL debug output reports no product errors.

This consumes existing LDR bake data; it does **not** introduce an HDR baker.
View-weapon grid blending, cropped/multiple-root views, deferred receivers,
near-portal multi-grid blending and debug overlays still require native
ownership. The existing bake's black-probe validity convention is preserved.

### Presentation timing follow-up

v48 adds five CPU-only timing columns to the optional frame CSV: forced finish,
final post, window-state refresh, context validation and the actual SDL buffer
swap. Rendering behavior and percentile budgets are unchanged. The current
stock `storage1` capture remains clean but fails P99 (`402.823 ms` CPU,
`397.812 ms` GPU). Its slow CPU frames spend only `39–51 us` in swap and stall
outside the measured backend, consistent with deferred upload waits. With
persistent uploads explicitly disabled, the outlier moves into SDL swap:
`477.352 ms` of a `485.032 ms` CPU frame. This latter capture technically passes
P99 (`10.198 ms` CPU, `11.544 ms` GPU) because only one retained sample stalls;
it is **not** evidence that the intermittent hitch was fixed. Final-post,
window-state and context work take microseconds. A no-swap/forced-finish
control is diagnostic only and does not qualify normal presentation.

`stock-v48-no-swap-diagnostic` has no retained CPU sample above `19.202 ms`
(P99 `17.549 ms` CPU, `18.074 ms` GPU), with clean rendering diagnostics. It
uses front-buffer drawing and forced completion, so it remains excluded from
normal presentation acceptance. v49 adds `uploadRetireUs` to the optional CSV
without changing upload or presentation policy. In
`stock-v49-upload-retirement`, persistent uploads are confirmed active, but
the largest waits occur inside SDL swap (`475.924 ms` of a `483.810 ms`
frame); retirement takes only `6–21 us` on the six slowest frames. This run
does **not** support blaming upload retirement for the earlier stalls. CPU
P99 is `399.456 ms`, GPU P99 is `392.036 ms`, and the existing budget still
fails. The traces isolate presentation backpressure without establishing its
underlying cause or a fix.

Reports: `stock-v48-present-phases`,
`stock-v48-present-orphaned-corrected`. The earlier
`stock-v48-present-orphaned` process was stopped after a misspelled launch cvar;
its `invalid-run.txt` explicitly excludes it from evidence.

### Fixed classic lighting in a PBR scene (qualification in progress)

The mixed-material candidate accumulates the original per-light classic
interactions in an encoded floating-point target sharing the modern depth.
The native interaction builder supplies the actual receiver triangle lists,
local light/view origins, texture projections, material matrices and separate
diffuse/specular colors. Its vertex shader preserves per-vertex half-vector
interpolation and the modern depth transform. The fragment shader uses the
engine's actual normalization cube for diffuse lighting and the classic
specular lobe. Each classic forward receiver samples this accumulation, adds
any qualified baked contribution, then performs one linear decode before PBR
fog, transparency and tone mapping. PBR surfaces keep their existing BRDF.

Admission currently requires a single full-size root view, fixed opaque
materials with one bump/diffuse stage and at most one specular stage, no
skinning/deform/depth hack, no shadows, no MSAA and no ambient lights. The
transaction is capped at 4,096 primitives. Missing geometry/images/programs,
unsupported materials and failed submission retain the complete native frame.
This contract passes the expanded lifecycle and regression matrix below;
it does not establish broad classic parity.

- v51's initial inner-patch comparison passed but was found inconclusive during
  wider review: highlights were clipped, and native/PBR use different display
  tone curves. Its report is explicitly marked inconclusive; the initial
  report is retained as `report-initial-patch-only.json`.
- v52 compares 18,219 channels across an interior sphere of radius 44 pixels.
  It encodes the engine's pre-tone-map PFM radiance to sRGB and compares that
  with the native image at low, unclipped lighting. Flat-normal specular and
  perturbed-normal specular pass: mean errors `0.253`/`0.256` bytes and maximum
  errors `0.558`/`0.560` bytes. Native values span `0–100`. This also exercises
  the native light projections without the clustered atlas approximation.
- The v52 diffuse-only reference spans only `0–31`, so the existing useful-range
  gate rejects it despite a `1.397`-byte maximum difference. The next fixture
  raises lighting, rather than weakening the range or error limits, and adds
  colored specular, rollback and resource lifecycle controls.
- The proof harness has negative tests for a missing lighting sample, a no-op
  pass and matching clipped highlights. Reports now also hash the harness.

Evidence: `.tmp/pbr-audit/proof-v51-classic-fixed` and
`.tmp/pbr-audit/proof-v52-classic-fixed`; corrected static fixture tests pass in
`.tmp/pbr-audit/fixture-test-v52b.log`.

- v53's stronger, unclipped reference passes all **14** material and lifecycle
  controls in `proof-v53-classic-lifecycle/report.json`, with no rendering
  diagnostics. Flat, perturbed and colored specular average `0.250–0.252` bytes
  of error and remain below `0.562` maximum. The diffuse-only reference averages
  `0.298` with a `2.426` maximum. All four references have a useful, unclipped
  range. Specular, normal and colored-specular differences are nonzero in the
  linear captures. Rollback matches native exactly; restoration, image/shader
  reload and partial/full restart reproduce display and float captures exactly.
- v54 reuses primitive-list capacity, verifies actual target allocation before
  caching its extent and guards degenerate vertex directions. Its expanded
  GL 3.3 run is **not qualified**: after a full restart and resize, enabling
  shadowed fallback crashes in the native point-shadow caster draw. A fresh
  shadow fallback process passes 2/2, and resize without the full restart passes
  4/4, but the shorter full-restart/resize sequence reproduces the crash. The
  failed reports and debugger evidence remain under `proof-v54-classic-*` and
  `classic-gl33-shadow-fallback-*-v54.txt`.
- The crash exposes a client-index handoff defect: classic index uploads are
  disabled, but the modern renderer can leave an element-buffer binding on the
  legacy VAO. Native CPU index draws now explicitly unbind the EBO regardless
  of that upload preference. v55 still reproduces the crash, so this correction
  alone is not its fix.
- v56 additionally establishes the native depth-fill client-array invariants
  before the early shadow prepass: position enabled, unused UV/color/normal
  arrays disabled. Perforated casters supply and enable their own UVs. The
  surrounding client-state scope restores the caller afterward. This removes
  stale array references left by video restart. The formerly failing reduced
  sequence now passes **5/5**, including exact restored captures and byte-exact
  shadow fallback/native equality, in
  `proof-v56-classic-restart-resize-shadow/report.json`. The expanded matrix
  remains under qualification.
- The expanded v56 GL 3.3 run passes **17/17** material, rollback, reload,
  restart, resize and shadow-fallback controls. Its MSAA boundary run exposes
  inaccurate `gfxInfo` ownership: a rejected modern request reported zero
  effective samples despite the native target's four-sample allocation. v57
  reports the executed frame owner and keeps native AA diagnostics on fallback.
  The updated static AA contract passes. A separate-process v57 comparison
  confirms 23,997 pixels change with native MSAA, but its exact fallback
  comparison fails on two display channels differing by one byte. That report
  stays failed. Same-process GL 4.5 also differs on one channel by one byte.
  The native reference is RGBA8, so floating-point readback cannot establish
  sub-byte equality. Its MSAA comparison now allows at most 16 changed
  channels (the existing MSAA display-count budget), each differing by at most
  one byte. Negative controls reject a two-byte change or 17 changed channels.
  Non-MSAA restoration and shadow-fallback comparisons remain byte-exact.
- v57c passes **44/44** controls: GL 3.3/4.5 native-MSAA fallback pairs (2 each),
  expanded GL 4.5 classic lifecycle (17), classic plus baked irradiance (5),
  production admission (12), and baked-PBR regression (6). Together with v56's
  GL 3.3 matrix, this qualifies the narrow classic lighting contract above.
  Both MSAA pairs require an actual native four-sample allocation. The baked
  classic reference uses the same unclipped float-versus-native oracle and
  requires a nonzero baked contribution plus exact zero/restore controls.
  Reports: `qualification-v57c.json` and `proof-v57c-*/report.json`.

### Final HDR boundary review

The original `screenshot linear` guard accepted a completed modern RGBA16F
target even when `r_hdrToneMap 0` left the classic/PBR preview in mixed transfer
spaces. It now checks the completed frame's recorded linear-HDR state. The
harness explicitly requires refusal for encoded previews instead of labelling
those captures as linear evidence. Previous display proofs remain valid;
non-HDR PFM captures must not be used as scene-wide radiometric proof.

A million-strength emissive control checks finite target storage and preserves
an unclipped red channel while green/blue reach the FP16 ceiling. The initial
v57 run did **not** reproduce Inf on the tested driver; its failure was an
overly strict analytical tolerance that magnified hardware sRGB decoding error.
The corrected test pairs ordinary/extreme emission, bounds both FP16 rounding
steps and retains an independent sRGB sanity check. Shaders now explicitly
bound storage to finite nonnegative FP16 range, after light accumulation.
This is a portability guard, not a demonstrated fix for an observed overflow.
The first v58 candidate failed deferred shader compilation because its helper
was only present in the forward header; v59 moves it to the shared lighting
header. The failed report remains under `proof-v58-hdr-boundaries`.

v59 passes **70/71** expanded controls: both GL tiers' HDR boundaries and
minimal documented settings, classic lighting at ordinary scene brightness,
material channels/normals, HDR/HUD/post, moving shadows, and CPU/GPU skinning.
All 15 renderer self-test success markers also pass, including 56 linked shader
permutations. The remaining MSAA sequence changes 21,002 float channels after
partial restart, exceeding its unchanged rounding allowance. A reduced sequence
without preceding shadow use passes 3/3; a new shadow off/on/off control fails
without any restart (20,976 changed float channels, 380 display channels).

The cause is a diagnostic shadow-binding probe added to fragment radiance.
Creating shadow maps changed that small contribution even after shadows were
disabled. Full restart happened to clear the history. v60 removes the probe
from all lighting outputs and reads readiness directly from resource metadata;
real shadow branches retain their required sampler bindings. The enlarged
regression matrix includes restoration before restart and an HDR off/on/off
control. Failed v59 evidence remains in `proof-v59-msaa` and
`proof-v59-shadow-history-negative`.

v60 passes all **74/74** expanded map controls, plus **15** renderer self-test
success markers. The shadow off/on/off MSAA image and both partial/full restart
images now have **zero changed display or float channels**, without relaxing
the oracle. HDR shadow restoration is also exact. Both tiers' extreme-emission
and minimal-setting controls, four classic controls, 16 material controls,
12 post/HDR controls, eight moving-shadow controls and 12 skinning controls
pass. The fixture's negative tests, material/AA contracts and diff whitespace
check pass. Evidence: `qualification-v60.json`, `proof-v60-*/report.json`,
`selftests-v60/report.json`, and `fixture-test-v60.log` under `.tmp/pbr-audit/`.
The earlier baked-lighting, combined fog/blend and broader classic lifecycle
reports retain their own binary identities; this count does not re-label them
as v60 runs.

### v60 retail regression

The independent staged runtime `.tmp/stock-runtime/pbr-final-v60` contains no
laboratory assets. Retail `game/storage1` passes the renderer budget with CPU
P99 **20.742 ms** and GPU P99 **7.003 ms**. Its 256 retained samples have a
21.692 ms maximum CPU frame and a 0.858 ms maximum swap. The initial MP server
passes, but exits before the separate client finishes startup; the stranded
client was stopped and the combined report remains failed.

An extended server lifetime lets the client enter `mp/q4dm1` and produce its
engine screenshot. The client passes (CPU/GPU P99 **17.764/7.855 ms**). The
server completes gameplay/capture but fails its unchanged CPU P95 budget:
**21.434 ms** versus **20 ms**; CPU/GPU P99 are **26.307/12.429 ms**. Both report
zero tracked rendering diagnostics and no runtime mutations. Engine captures
were inspected and show the SP vehicle scene and an MP player with weapon/HUD
in warmup. This is rendering regression evidence, not combat/soak qualification.
The earlier half-second swap stalls do not recur in these retained samples;
their absence does not establish an intermittent-performance fix.

Reports: `stock-v60-final/renderer_gameplay_benchmark_report.json` and
`stock-v60-mp-repeat/renderer_gameplay_benchmark_report.json` under
`.tmp/pbr-audit/`. The latter remains failed for the measured server CPU budget;
no thresholds were relaxed or reports promoted after capture.

### Vulkan takeover: immediate screenshot/restart lifetime

The current v60 binary reproduces the peer's HDR partial-restart crash in
`vulkan-v60-restart-baseline`. A matching-symbol dump reaches
`VK_Exec_BeginMainRendering` while binding the newly resized game target.
The same binary passes the complete sequence when the diagnostic control adds
one frame between the resized screenshot and partial restart
(`vulkan-v60-restart-wait-control`, unchanged runtime).

Screenshot readback deliberately resumes command recording against the acquired
swapchain image. Partial restart could destroy its views in the same console
batch, before the resumed frame was submitted. The resize seam now submits that
frame before applying window changes, propagates recreation failure, and the
device layer rejects recreation during an open frame. A queue/device idle wait
only covers submitted operations; it does not make a recording command buffer
safe to continue after referenced resources are destroyed
([Vulkan device-idle contract](https://docs.vulkan.org/refpages/latest/refpages/source/vkDeviceWaitIdle.html),
[image-view lifetime](https://docs.vulkan.org/refpages/latest/refpages/source/vkDestroyImageView.html)).
The original immediate sequence is retained as the regression test; the
one-frame delay is diagnostic evidence only. v61 passes the original SP sequence
at 0x and 4x MSAA with no tracked Vulkan diagnostics. Its MP runs no longer
crash, but the unchanged gates reject two real gaps: hidden-window startup
applies the borderless desktop extent after restart, and the backend-owned MP
scene remains single-sample when 4x was requested. MP also rejects the diagnostic
exposure toggle unless the local test server enables cheats. Those failed
results remain in `vulkan-v61-hdr-gameplay`.

The v62 candidate suppresses fullscreen/borderless modes for hidden startup,
allocates multisample backend scene color/depth with a matching single-sample
resolve pair, and propagates depth validity only after a successful resolve.
MSAA alone can now request that backend-owned scene, including after HDR/TAA
are disabled. HDR telemetry reports the exposure readback mode; the harness
checks it and explicitly enables diagnostic changes on its local test server.
Both verified MP 0x/4x runs pass. The first v62 output directory is marked invalid
because a file-sharing failure left the previous DLL in the runtime; it was
stopped, the copy repaired, and its hash verified before rerunning. No evidence
from that directory qualifies the new binary.

v63 additionally requires a current successful depth resolve before spatial
screen-space effects consume depth, and reports actual native scene MSAA in
`gfxInfo`. All four stock HDR runs pass (SP/MP at 0x/4x) with the immediate
screenshot/partial-restart sequence intact, active validation, zero tracked
rendering diagnostics and an unchanged independent runtime. The harness rejects
MP-protected changes that did not take effect and verifies final AA telemetry.
The test server is LAN-only. GPU render-target/MRT tests and all 48 HDR fixture
executions around a full restart also pass. Vulkan module SHA-256:
`e88cafd2611cc8f0089297d43dfbb6e01757d539a09c5ed15dcb2ddfdee1150a`.
Reports are `vulkan-v63-hdr-gameplay/report.json` and
`vulkan-v63-gpu/renderer_validation_report.json` under `.tmp/pbr-audit/`.

The 4x SP/MP capture sheets were inspected. Geometry, weapon/HUD and window
extents survive the tested transitions. SP automatic exposure visibly washes
out the sky/highlights, so this result closes lifecycle/MSAA correctness, not
HDR visual parity or performance/soak qualification. The new HDR gate negative
tests reject single-sample substitution, ineffective exposure toggles, desktop
extent substitution, stale generations and screenshot-induced adaptation.

### Native Vulkan direct-material expansion

The v63 full-map baseline owns only the packed-ORM/XYZ-normal station. The
new isolated direct-light controls use one unchanged sphere transform, camera
and light, with independently equivalent scalar, ORM and separate-map inputs.
They reject the v63 binary: normal/roughness controls have no effect and none
of the additional specimens acquires native ownership. Failed baseline evidence
is retained in `vulkan-v63-pbr-baseline` and `vulkan-v63-direct-negative`.

Native opaque direct lighting now reads scalar, packed and separate
metallic/roughness inputs, optional flat normals, and XYZ, RG or Quake 4 AGB
normals. The otherwise-unused classic specular-table descriptor carries
separate metallic data; the descriptor/push ABI does not grow. The three
interaction shaders share one material-decoding/BRDF source. AGB keeps its
authored bump/RXGB upload path, while XYZ/RG uses linear material-data storage.
AO does not extinguish direct light. Emission, cutout/source alpha and invalid
classic interaction topology retain complete classic material ownership.

v64 initially passes 22/24 controls; the two failures expose its wrong AGB
usage check. v65 corrects that check and passes **34/34** expanded controls:
layout equivalence, all normal encodings, roughness/normal/rollback effects,
ownership, exact unsupported-material fallback, partial/full restart, and
point/projected shadow off/on/restore. The same sphere is visibly occluded by
an original caster; positive map records verify the intended light kind and
complete caster coverage. Stationary casters may reside in the static cache.
The first projected fixture inherited the console camera's yaw; it now fixes
the light angle explicitly. Those earlier failed reports remain unchanged.

Accepted evidence: `.tmp/pbr-audit/vulkan-v65-direct-qualified/report.json`;
Vulkan SHA-256 `aa1d5cc7dcb47d479b6584baee7110a153f9e8644ba609f91c32f09f00540a4a`.
No tracked diagnostics occur with positive native-backend/validation evidence.
The old OpenGL client-array warning now correctly describes Vulkan's CPU cache
as upload staging. The original full-map ownership gate remains unchanged;
these direct-light results do not claim Vulkan emission, transparency, IBL,
authored probes, full scene linearization or complete OpenGL parity.

The expanded check also found two stale shadow source contracts from earlier
GL work: bounded normal-offset upload replaced a hardcoded zero, and filtered
alpha coverage changed the spelling of the discard. Their ordering checks now
verify the current bounded data flow and derivative-before-discard contract;
the complete Vulkan shadow compatibility check passes.

The same v65 binary also passes **34/34 controls at actual 4x MSAA**,
including both restart types and point/projected shadows, without tracked
diagnostics (`vulkan-v65-direct-msaa4/report.json`). Cross-report comparison
pins identical runtime, fixture and compiled-map hashes and validates the
retained engine captures/logs. The flat ownership image gains **232 fractional
silhouette pixels** while all **26,199 interior pixels** remain unchanged.
Proof is `vulkan-v65-direct-msaa-proof.json`; its negative controls reject
changed binaries/maps, failed runs, substituted logs/captures and no-op AA.

v65 also repeats the four stock SP/MP HDR cases and both GPU attachment/HDR
self-tests successfully (`vulkan-v65-hdr-gameplay/report.json` and
`vulkan-v65-gpu/renderer_validation_report.json`). The unchanged full-map gate
remains **2/3**, explicitly failing cutout coverage and emissive ownership
(`vulkan-v65-pbr-scope/report.json`). The direct results remain scoped; the
known complete-scene and HDR visual acceptance gaps are not waived.

v66 admits perforated direct materials only when one active diffuse alpha
stage samples the PBR albedo with matching filtering, addressing and explicit
UVs, neutral alpha, and no private offset. Its EQUAL lighting pass inherits
the depth fill's sample mask. Seven cutout controls pass at 0x and 4x, with
exact lighting restoration across rollback and partial/full restarts. Coverage
is approximately half material/half holes; alpha-to-coverage changes 393
interior channels at 4x and zero at 0x. Inspected engine crops are retained in
`vulkan-v66-cutout0/cutout-controls.png`.

The expanded 39-case script exposed the engine's 64 KiB console insertion
limit. Its failed run remains in `vulkan-v66-direct0`; the harness now chains
scripts below 48 KiB, preserving command order and hashes for every part.
All **39/39** v66 controls pass after this repair in
`vulkan-v66-direct0-chunked/report.json`. Native Vulkan module SHA-256:
`fab20e8656eb33b5b8832c30d43168c76ea7ba3a48eb50ae14cce52fef522c15`.
The v65 retail capture sheets were also inspected: MP geometry/HUD survives
the tested transitions, while the previously recorded SP highlight washout
remains visible.

### Vulkan emission and finite storage

v67 adds native emission through the same surface/material admission as direct
lighting. It replaces the single proven matching classic glow stage in the
ambient walk, uses the typed sRGB image, and evaluates emission once per
surface. The shared classic ambient path yields for these materials, including
views with no direct lights. Mismatched glow images retain complete classic
ownership. Debug 6 isolates emission and debug 7 remains valid without lights.
All **53/53** expanded v67 direct controls pass at 0x
(`vulkan-v67-direct0/report.json`), including independent low-intensity color
references and byte-exact zero/one/many-light emission, rollback and restarts.

Review then identified premature intensity clipping at 65,504. v68 preserves
finite authored intensity and clamps evaluated texture-modulated radiance at
the shader storage boundary. Its GPU attachment tests read actual half-float
values: a faint channel remains exactly 4,096 while overrange channels become
65,504, at both 0x and 4x. Both attachment/HDR cases pass in
`vulkan-v68-gpu/renderer_validation_report.json` with active validation.
This does not qualify arbitrary multi-light FP16 accumulation or a complete
linear scene.

The map's corresponding faint-channel control also passes at 4x, alongside
emission color/scale, shared-ambient fallback, and emissive cutout ownership
(`vulkan-v68-emission4-bounded/report.json`, **7/7**). The first attempt requested
manual exposure below its supported 0.1 minimum and remains failed. The corrected
fixture combines manual 0.1 with fixed auto-exposure 0.01, verifies completed
RGBA16F exposure telemetry, and retains the original pixel oracle.
Vulkan v68 SHA-256:
`ff6e3b5fd33bb596dabf201a9b9bf61b98b1e93082ac9269bc4f5da8384e343b`.

The complete v68 native material sequence passes **55/55 at 0x and 55/55 at
actual 4x MSAA** (`vulkan-v68-direct0/report.json` and
`vulkan-v68-direct4/report.json`). Both report unchanged runtime, compiled-map
and fixture inputs after execution. Cross-report proof requires identical
binaries and maps and verifies retained capture/log hashes: **307 fractional
silhouette pixels, 29,035 interior pixels and zero changed interior pixels**
(`vulkan-v68-direct-msaa-proof.json`). This is material-path qualification, not
full-scene PBR or id Tech 6 parity. Final fixture negative checks and regenerated
shader-header verification also pass (`fixture-test-v68-final.log`,
`shader-pin-static-v68.log`).

The v68 full-map check is **2/3**: lit and master-off pass, and the ownership
frame now proves both native cutouts and emission. Source-alpha ownership still
fails (`vulkan-v68-pbr-scope/report.json`). The inspected engine-capture sheet
is `vulkan-v68-pbr-scope/scope-inspected.png`. This retained failure is required;
the passing isolated classic-alpha fallback pair does not close transparency.

Stock SP and auto-joined MP repeat all four HDR/MSAA transition cases on v68
with active validation and unchanged runtime files
(`vulkan-v68-hdr-gameplay/report.json`). These are correctness/lifecycle checks;
the documented SP exposure highlight loss and performance/platform limits remain.

New reports retain the harness/generator sources and verify runtime libraries,
compiled map and every fixture input again after capture. The full-map ownership
gate now explicitly checks source-alpha ownership on Vulkan, which its earlier
backend-specific inspection omitted. Ordered transparency, environment/probes,
and complete scene/display color composition remain required.

### Vulkan specular antialiasing

v69 applies the shared, numerically tested roughness filter to the final
object-space shading normal in unshadowed, point-shadowed and projected-shadowed
PBR. This includes curvature even with a flat normal map. Derivatives precede
per-fragment lighting rejection. The basis occupies unused components within
locations 0–15, preserving Vulkan's minimum varying-location capacity; see the
[Vulkan interface rules](https://docs.vulkan.org/spec/latest/chapters/interfaces.html).
`r_vkPBRSpecularAA` defaults to 1 and is a non-archived comparison switch.

The first thirteen controls retained three failures because pure-metal
unfiltered surfaces were nearly black away from subpixel highlights. The revised
fixture adds diffuse response and a visibly lit constant-normal specimen; it
does not relax the non-dark/non-clipped gate. All **13/13** then pass at 0x
(`vulkan-v69-aa-visible/report.json`): 445 geometric and 518 normal-mapped
interior pixels materially change, filtering restores exactly, and constant
shading normals plus roughness=1 remain byte-identical. The original failed
report remains in `vulkan-v69-aa0`. This establishes footprint filtering and
invariants, not a quantified temporal-shimmer reduction or an unclipped HDR
highlight reference. The inspected crops are in
`vulkan-v69-aa-visible/aa-inspected.png`.

The expanded sequence now passes **68/68 at 0x and 68/68 at actual 4x MSAA**
(`vulkan-v69-direct0/report.json`, `vulkan-v69-direct4/report.json`). Both retain
unchanged runtime/map/fixture inputs and active validation. Cross-report proof
again finds 307 fractional geometry-edge pixels and zero changes among 29,035
interior ownership pixels (`vulkan-v69-direct-msaa-proof.json`). The command-line
suite `--suite vulkan-direct` reproduces the entire native sequence; empty
selection is allowed only for explicit fixture preparation and cannot print a
passing rendering summary.

Vulkan v69 SHA-256:
`a1cb8bba2ddcb77ac641476d94af8b1eca89a7da14b88b2946543db66052874d`.
Shader regeneration/pinning, material contracts and fixture negative tests pass
in `shader-pin-static-v69.log`, `pbr-static-v69.log` and `fixture-test-v69.log`.
The v69 attachment/HDR GPU suite also passes **2/2**, including FP16 emission
at both sample counts and the restart exposure fixtures
(`vulkan-v69-gpu/renderer_validation_report.json`). The full-map check remains
**2/3**, failing only native source-alpha ownership
(`vulkan-v69-pbr-scope/report.json`).
All four stock SP/MP HDR and restart cases also pass with an unchanged v69
runtime (`vulkan-v69-hdr-gameplay/report.json`). The known SP highlight washout
remains visible, so this does not establish HDR visual parity.

The bounded stock `game/storage1` pre/post comparison has nearly identical GPU
medians (v68 **4.985 ms**, v69 **4.991 ms**) and GPU P99 of 7.307/6.353 ms.
Both reports nevertheless **fail** CPU P99: **424.643/413.892 ms** against the
28 ms budget (`vulkan-v68-stock-timing`, `vulkan-v69-stock-timing`). These single
comparisons do not establish performance parity. A requested buffered-log
control still fails at 403.171 ms; the already-open logger retains its original
unbuffered file mode. More significantly, pacing-only execution disables
periodic renderer diagnostics and still measures **415 ms presentation P99**
(`vulkan-v69-stock-pacing`). The stalls were not an accepted benchmark, nor a demonstrated regression
from the new specular filter; the v70 section below re-measures them on a
quiet machine, where they do not reproduce. All four failure reports and their hashes are retained in
`.tmp/pbr-audit/qualification-v69.json`; the concise human-readable checkpoint is
`.tmp/pbr-audit/qualification-v69.md`.

### v70: native ordered source-alpha transparency

The retained v69 failure was not a missing shader feature. A translucent
surface never reaches the depth fill, so classic ownership splits it across two
passes: the light pass adds its lighting at depth LESS, and the authored
source-alpha stage composites later, in the material walk's sort position. A
native owner has to do both at once -- evaluate the whole BRDF per light and
composite the sum through the authored alpha -- which neither half can express
alone.

The light pass now records an admitted translucent surface's draws instead of
adding them, and the material walk replays them where the classic stage would
have drawn: the first light composites with (SRC_ALPHA, ONE_MINUS_SRC_ALPHA)
and the rest add with (SRC_ALPHA, ONE), so the frame receives
`dst * (1 - a) + a * sum( Li )` -- the classic composite of the summed
radiance. Admission mirrors the existing cutout contract: exactly one
source-alpha blend stage naming the PBR albedo's own image, filter and repeat,
with explicit untransformed coordinates, no vertex tint or alpha test, and a
white colour whose alpha register scales the sampled coverage.

Two findings are worth retaining:

- **The replay inherits the walk's depth state.** Its first version drew
  nothing, because the previous stage had left `DEPTH_COMPARE_OP = EQUAL`, the
  opaque stage contract, which a surface absent from the depth fill can never
  satisfy. The replay now sets the translucent contract (LESS_OR_EQUAL, no
  depth write) itself, exactly as the light pass does for its translucent
  chain.
- **A single capture cannot measure transparency.** The harness asserted an
  absolute `(0, 112, 0)` at the `source_alpha` station, which assumes a black
  background; the OpenGL reference reads `(118.306, 213.367, 108.388)` there.
  The check is now the same oracle OpenGL already used: the ownership marker
  replaces the surface's radiance with constant green and the emission view
  replaces it with black, both composited through the same alpha over the same
  background, so their difference is the coverage alone. Both debug views now
  carry that coverage on Vulkan, and the ownership marker composites once per
  surface rather than once per light -- a constant is not a radiance, and
  adding it per light would saturate the surface it is meant to measure.

Result: the `lit,ownership,emissive,master-off` full-map check passes 4/4 with
the measured difference exactly `(0.0, 112.0, 0.0)`. The native ownership
capture `(118.735, 213.918, 108.347)` matches the OpenGL reference to within
0.6/255, and `master-off` still reproduces the classic composite `(165, 222,
255)` unchanged, so the fallback is intact.

Scope kept deliberately narrow: every recorded draw has to be reproducible
after its light is finished, and stencil shadow coverage is not -- it is
written and reset per light. The view therefore declines native transparency
whenever a shadowing light reaches a translucent receiver, rather than owning a
surface for one light and returning it for the next. Shadow-mapped receivers
are replayed from the persistent atlas and are admitted.

### v70: the stock timing failures do not reproduce

The v68/v69 CPU P99 failures (424.643/413.892 ms against the 28 ms budget)
were re-measured on the current binary. Five runs pass:

| Run | Configuration | frame p50 / p95 / p99 / max (ms) |
|---|---|---:|
| `v70-perf-novalidation` | 240 fps, hidden window | 7 / 8 / 9 / 17 |
| `v70-perf-validation` | 240 fps, hidden window, `r_vkValidation 1` | 11 / 13 / 14 / 14 |
| `v70-perf-v69match` | the exact v68/v69 case, validation on | 12 / 15 / 18 / 22 |
| `v70-perf-trace1` | as above, per-frame CSV retained | CPU p50 12.8, p99 14.9, max 15.5 |
| `v70-perf-trace2` | as above, per-frame CSV retained | CPU p50 12.9, p99 14.2, max 16.4 |

Neither traced repeat has a single frame above 100 ms, and GPU time stays at
4.9-5.2 ms throughout.

The retained failures are not reinterpreted. Their own per-frame traces show
what the percentiles hid: 2-6 isolated frames out of 256, with the time inside
the present/swap call (`swapUs` 461,240 of 469,212 CPU microseconds in
`stock-v49-upload-retirement`) or unattributed to any render phase, while the
GPU reported 1.6-12 ms. The process was waiting, not rendering. What the
machine was doing during those runs cannot be recovered; this box runs
parallel sessions, which makes contention the most plausible explanation, but
that remains a hypothesis. What is established is narrower and sufficient for
the gate: in the same configuration, on a quiet machine, the renderer measures
inside the 20/28 ms budget, repeatably.

One measurement rule follows from the comparison: take performance evidence
with validation **off**. The layer costs about 57% of steady-state CPU frame
time here (7 ms to 11-12 ms p50). It is a correctness instrument, and the
v68/v69 timing runs had it enabled.

### v70: the highlight washout is the shared curve, not a backend gap

The retained observation "SP automatic exposure still loses highlight detail"
is reproducible from the source alone, and it is not a Vulkan parity problem:
`content/baseoq4/pak0/glprogs/bloom.fs` and
`src/renderer/Vulkan/shaders/post_bloom_composite.frag` carry the same curve,
line for line.

That curve is linear up to `shoulderStart = 0.98` and compresses everything
from there to the exposed white point into the remaining 2% of display range.
With the shipped defaults (`r_hdrWhitePoint 6.0`, `r_hdrExposure 1.0`) that is
about 2.6 stops of highlight information mapped into 0.02 of output, which is
a roll-off in form and a clip in effect. It has no toe, so it is not a filmic
S-curve.

Automatic exposure does not lose the detail; it reveals the property. The
target exposure is `r_hdrKeyValue / averageLuminance`, so a dim scene
(L = 0.05) selects exposure 3.6 and pushes everything above 0.27 scene-referred
radiance past the shoulder.

Fixing it means moving the shoulder down and giving the curve a real toe. That
changes the appearance of every HDR frame on **both** backends and invalidates
the byte-exact HDR image controls this audit retains, including the
independently evaluated filmic/sRGB references. It is a visual-design decision
with a re-baselining cost, not a defect fix, so it is recorded here and left
to the owner rather than changed under a parity task.

### v70: the colour gap measured, and what it is

"Vulkan scene/display colour parity is unqualified" was an assumption, never a
number. Both backends capture the same laboratory cameras at frozen time, so
the same captures answer it. Comparing the OpenGL and native Vulkan frames
channel by channel:

| Capture | Environment lighting | mean | p99 | max | channels differing by >1 |
|---|---|---:|---:|---:|---:|
| `master-off` | PBR disabled entirely | 0.920 | 2 | 104 | 7.77% |
| `direct` | `r_pbrIBL 0`, probes off | 1.002 | 24 | 216 | 4.33% |
| `lit` | on (OpenGL consumes it, Vulkan does not) | **8.149** | 126 | 255 | **17.69%** |
| `emissive` | debug view | 0.305 | 2 | 3 | 1.16% |
| `ownership` | debug view | 0.386 | 2 | 255 | 1.19% |

The reading is unambiguous. With environment lighting off, native Vulkan PBR
direct lighting agrees with OpenGL about as closely as the two classic
renderers agree with each other (1.00 against 0.92). Turning it on multiplies
the difference by eight, because OpenGL adds filtered environment specular and
diffuse irradiance that Vulkan has no consumer for. The `ownership` row's max
of 255 is expected: OpenGL paints unowned draws magenta in its modern path and
Vulkan leaves them classic.

So the remaining colour work is not a diffuse "linearization" problem to hunt.
About seven eighths of the measured difference is one missing feature, and the
residual mean of 1.0 is what scene/display composition alone contributes.
Reports: `.tmp/pbr-audit/v70-backend-color-delta.json` and
`v70-backend-color-direct.json`.

### 2026-10-04: two OpenGL controls after the shoulder and PCSS changes

Two GL groups that passed on 09-21 failed on the 10-04 build, with and without
`com_fixedTic 1`. Lean lab runtimes of the 09-24, 09-25, 10-01, 10-02 and
10-04 builds placed both.

The classic oracle above ("unclipped float-versus-native") stopped holding on
09-24/25, when c850233d moved the stock display shoulder from 0.98 to 0.5: the
change the v70 note left to the owner. The ARB2 interaction did not change. The
native capture is a display image, and its 0.782 highlight now displays as
0.686, byte 175, while the modern PFM still encodes to 199.4. With
`r_hdrToneMap 0` the two agree at 0.251 mean, 0.56 maximum, as before. The
comparison now maps the modern radiance through the same stock transfer, which
`stock_display_transfer` models and refuses to extrapolate.

`shadows` broke on 10-02 with the PCSS-lite default. The modern GL receivers
took `ceil( effectiveFilterRadius )` as their fixed PCF radius: 8 texels, the
classic shader's blocker-search bound. The lab projector's grazing left wall
and the ceiling self-shadowed, with patch errors of 22.7 and 4.8 mean. They now
use the contact radius. The radius change also exposed a one-byte,
capture-order-dependent difference in the shadow fallback/native pair: each
rebuild of a projected map went to a new atlas cell. A rebuild now reuses the
light's own cell.

## Unrelated issues observed

The earlier engine/game renderer-interface mismatch is reconciled, and its
temporal, GPU-timing and level-load static checks pass on v61. Stock MP
AAS/precache warnings remain separate from PBR qualification.

The move/restore test also exposed a shared SP/MP console-script bug: every
`script` invocation used the same cached source name, so commands after the
first were silently skipped. Both canonical game modules now bypass the file
include cache for console text. The successful restore control exercises this
fix through real gameplay commands.

## Remaining acceptance gates

Broader mixed classic/PBR materials, portal/view-weapon baked-lighting composition, native Vulkan IBL parity, final stock SP/MP gameplay, and consolidated documentation remain acceptance gates. Native Vulkan material parity now includes ordered source-alpha transparency, and the stock timing gate passes again on a quiet machine, so the open Vulkan work is the environment consumer that the v70 colour measurement sizes at about seven eighths of the remaining visible difference. Scoped production admission, viewport-edge comparisons and HDR/HUD controls now pass without a forced classic-parity mask. Authored fog/blend and baked irradiance now compose inside the qualified HDR PBR path. Unsupported view/material scopes, mixed LOCAL/GLOBAL shadow receivers and atlas/budget limits retain verified complete classic fallback. The user paused the Vulkan task and authorized taking over its remaining work after PBR; do not resume it concurrently.
