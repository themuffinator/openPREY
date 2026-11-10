# Retained runtime integration checkpoint

8 September 2026. Stage 2 is in progress. This checkpoint establishes an engine
rendering path and tests for the layout-library candidate. It does not replace a
GUI or constitute a finished menu. The subsequent
[document/timeline checkpoint](document-format.md) now establishes the first
implemented canonical source subset; its limits remain explicit.
Later [native vector](vector-paths.md), [coverage](coverage-antialiasing.md),
[isolated composition](composition.md), [masks](masks.md) and
[semantic controls](interaction.md) checkpoints supersede the corresponding
initial limitations below. [SDL/session input ownership](input-routing.md) now
connects these controls to the platform adapter; the game action bridge and
broader device/platform qualification remain open.
The [complete plan](../archive/2026-10-18/plans/idtech5-ui.md) and [visual specification](../ui-visual-design.md)
continue to define completion.

## Dependency and ownership

RmlUi **6.3** is pinned by the [Meson wrap](../../../subprojects/rmlui.wrap).
The release archive SHA-256 is
`d977298bb6147610e5984d5db85ddf284020d655a8713913f6982074f1dbdede`.
Its [MIT licence](../../../LICENSES/RmlUi.txt) permits this GPLv3 integration; the
notice is retained in source, credited in README and installed into the runtime
package's `licenses/` directory. The native Meson overlay compiles 184 core,
element and layout sources from that archive. It does not invoke CMake or add a
second dependency workflow.

FreeType, Lua, SVG/LunaSVG, Lottie, debugger, samples, profiling and third-party
containers are disabled. The enabled core has no new external runtime library
dependency. In particular, no SVG rasterizer is being substituted for editable
vector furniture. The upstream sources and headers remain in the downloaded
subproject with their notices. No upstream sample implementation was copied.

The core lives in `src/ui/retained/`, without engine precompiled headers or
platform/graphics includes. `Host` supplies VFS reads, translation, font metrics,
glyphs, image materials and indexed drawing. `RetainedUI.cpp` provides the engine
implementation. The client links the retained library; dedicated code uses
empty engine entry points and does not link RmlUi.

## Current capabilities

- Shared RmlUi services with [independent document instances](instances.md).
  Each context owns state, input, layout and playback; idle render backends are
  reused. Concurrent contexts must share the same host.
- Retained layout, source-element IDs, runtime style/text changes and bounds
  queries. Text mutation escapes markup. These APIs are integration tools, not
  a promise that raw RML is the editor's canonical serialization.
- Context dimensions use physical UI viewport pixels. `dp` is multiplied by
  SDL display scale and the independent player scale once. Window coordinates
  use pixel density and viewport origin separately. Engine triangle positions
  convert to its submission space only at the drawing boundary.
- Full-width aspect expansion and anchors, instead of a stretched 640x480 layout.
- Cached indexed geometry, two-dimensional transforms, rectangular clipping
  with interpolated UVs and premultiplied vertex colours, and native horizontal/
  vertical geometry gradients. The existing engine renderer consumes the result.
- Untextured vector triangles retain premultiplied blending through composition.
  Generated font images use straight coverage and a uniform text tint converted
  at the final boundary. The original materials are not modified. Intrinsic
  retained materials are implicit, process-local declarations.
- Existing scalable Quake 4 font pages and language-table lookups. Font/material
  geometry is recreated after a renderer restart or language-generation change.
- A steady presentation clock and CSS animation sampling between simulation
  ticks. This is not yet the specified timeline system; see the limit below.

## Evidence

`openq4-retained-ui-test` runs the same RmlUi core and adapter used by the client,
with an in-memory host. It checks 100%/200% density, player scale arithmetic,
window/pixel coordinate separation, 16:9 and ultrawide anchors, mutation,
triangle indices, overflow clipping of a gradient, lifetime ownership/restart,
and transform samples at 144 Hz. These are synthetic presentation samples,
not a measurement of a running game's display refresh rate.

Windows client, OpenGL module, Vulkan module and dedicated builds use the normal
Meson wrapper. The existing Linux high-DPI mouse contract and both platform
branches of the background-cursor test are also checked. The latter execute
production functions against stubs, without touching the host pointer.

The diagnostic fixture is `tools/ui/fixtures/runtime-smoke.rml`. Its rectangular
test rows exercise layout, text, colour and a gradient; they are not proposed
Quake 4 component artwork and do not satisfy the chamfered component gate.
It uses existing localization keys. It is not staged as shipped content.

Capture through `tools/ui/capture_legacy_baseline.py`, adding
`--retained-document tools/ui/fixtures/runtime-smoke.rml` and an optional
`--density` override. The script copies it into an isolated savepath, invokes
`ui_retainedPreview "retained-smoke.rml"` after active gameplay begins, settles
30 frames, then calls the engine's registered `screenshot` command. The window
is hidden and windowed, with mouse/controller input disabled. Capture reports
retain binary/fixture/image hashes. Visual review is still required.

Reviewed captures at 1280x720, all in actual `airdefense1` gameplay:

| Evidence directory under `.tmp/ui/retained/` | Check | Result |
| --- | --- | --- |
| `sp-gl-100-03` | OpenGL, 100% density | All fixture elements visible; exit 0, zero warnings/errors |
| `sp-vulkan-200-02` | Vulkan, 200% density | Correct doubled geometry/text and anchors; exit 0, two non-UI warnings |
| `sp-gl-200-restart` | OpenGL, 200%, full `vid_restart windowed` | Font pages and geometry return correctly; exit 0, zero warnings/errors |

The engine's `gfxInfo` confirms the requested backend is active, not a fallback.
The UI's 200% geometry and typography agree visually between these GL/Vulkan
captures. Different game frames/backgrounds prevent a whole-image pixel equality
claim. The Vulkan log reports `vertex array range in virtual memory (SLOW)` and
`post-process surfaces skipped because feedback capture failed` before the
retained preview loads; these renderer issues remain open. Previous MP reference
warnings are recorded in the [inventory report](inventory-report.md).

Screenshot SHA-256, in table order:

```text
c614460dfdbc2e584de3bd8459e21cf21a6325563a86c9e1dc850855dfbcdcc9
8dcb3ee575f6e5474fdbc35ec7d664462bb4cfdb3745645a5cbd5f8142bf6dcf
acfbd591759a7cb413211e99becfb225511b872529c2e902aadb02bfb73b6ff4
```

The tested client SHA-256 is
`811642e2d228b3ed2337815aced5a6b6d00943ff78b35be5604c7b72c99b3480`.
The companion source revision remains
`9a2d8715fc40d4f5b1ca1cfd7f90230baf3192f2`; this checkpoint does not change the
game bridge or ABI. Raw screenshots and logs stay out of Git.

Earlier capture attempts are retained as failures: the first did not load its
unquoted hyphenated filename; the next exposed native triangle culling. Both
were corrected. A simultaneous Vulkan launch exited before initialization under
the engine's single-instance protection; successful captures ran sequentially.
UI intrinsic materials are now two-sided, including mirrored transforms. Only
implicit, generated retained solid/font resources bypass the asset-precache
warning; ordinary or explicitly authored materials keep that diagnostic.

## Open requirements and selection findings

- RmlUi supplies no browser user-agent stylesheet. The fixture explicitly makes
  `div` a block and the body fill its viewport. Generated layout styles must
  establish these defaults deliberately.
- RCSS is not browser CSS. For example, its linear tween spelling is `linear-in`.
  A raw `linear` token can be interpreted as a keyframe name instead. The editor
  compiler must validate generated style/motion references.
- RmlUi's `ElementAnimation::UpdateAndGetProperty` clamps each time step to
  **100 ms**. Its default CSS clock therefore loses elapsed motion time after a
  stall. The canonical timeline must own timing, interruption, easing, pause,
  cancellation and reduced-motion behavior instead of adopting that policy.
  The first-party evaluator now implements those presentation operations for
  canonical documents; raw RML CSS animations retain the upstream behavior.
- Shader-based linear/radial/conic gradients, clip masks, layers, filters and
  generated RGBA textures were not implemented at this checkpoint. Generated
  images are superseded by the October integration below. Horizontal/
  vertical geometry gradients are supported. Unsupported features remain
  qualification failures, not silent claims of approximate equivalence.
- Native curved paths, holes, stroke joins/caps, editable path sources and
  density-dependent subdivision now have a [separate checkpoint](vector-paths.md).
  Coverage antialiasing, masks/layers and complete paint/artwork qualification remain.
- The text adapter uses the existing 48-point engine metrics/pages. It does not
  yet provide arbitrary-size rasterization, shaping, kerning, font effects,
  inline game colour/icon escapes, IME or a separate player text scale. Textured
  vertex gradients with varying alpha need the full premultiplied texture path.
- Direct image/font-page lookup is supported; multi-stage game materials,
  cinematics, model previews and world-surface instances require their own
  behavior-preserving operations. Live DPI font-density invalidation needs the
  new font backend, beyond the restart/language invalidation already present.
- Input/focus/navigation, game semantic events and commands, save restoration,
  remaining path/component/state schemas, the editor and translation of all 271
  inventory entries remain open.
  The preview does not capture or route user input and its rows are not controls.
- Actual mixed-DPI monitor transitions, high-refresh playback, all renderer
  modes and Linux/macOS/Android runtime checks remain unqualified.

An unrelated build issue was observed: rebuilding byte-identical `pak1.pk4`
preserves an old output timestamp, so newer input timestamps can trigger the
same expensive packing step on subsequent builds. The content was verified by
the normal pack build; only the ignored build-output timestamps were refreshed
locally for this investigation. No packaging implementation change is included.

## Generated-image integration, 18 October 2026

The RmlUi `GenerateTexture` callback now accepts bounded RGBA8 pixels and asks
the engine host to upload an immutable image. Both pixels and vertex tint remain
premultiplied through the generated material's source-over blend. File-backed
images retain their existing straight-alpha path; generated image release cannot
release those materials or another context's lease. This is UI-09/RES-004
implementation evidence, not acceptance of the whole resource/toolkit contract.

`GeneratedImagePool` shares 64 slots and a 64 MiB active/retired pixel budget
across all views of one host. Dimensions are positive, at most 4096 per axis and
within the active renderer's limit; byte length must exactly match RGBA8.
Invalid input or unavailable resources returns failure before publishing a
handle. Failed allocation/upload/material admission remains charged until safe
cleanup, including a failed shrink. Image/decl names are reused within those
64 slots, so repeated document closure cannot grow those registries indefinitely.

Releasing an image invalidates its context's recorded frame and cached plates.
The host retires the slot without changing queued draws' pixels, then shrinks its
allocation on a later submission frame. Each idle named image retains only a
1x1 placeholder, at most 256 additional pixel bytes across the pool. Resource
generation teardown releases all contexts before resetting the host. Generated
images are reproducible from the calling operation's pixels; this callback does
not add serialized image data to GUI save snapshots or implement the remaining
movie/model/world-surface operations.

The renderer's named upload path now sends explicitly allocated, matching-size,
single-level RGBA8 2D images directly to their existing storage. In particular,
a 1:6 image keeps its specified 2D type instead of taking the cinematic uploader's
cube-map heuristic. Other legacy uploads retain their sampler-preserving path.

Verification uses production methods and the staged Windows x64 runtime based
on `cbe967f2b61935da283a873a731fe975926cf214` plus the command-copy and generated-
image changes. Runtime reports record actual executable/module hashes. Native
and rendered checks have separate scopes:

- `openq4-ui-generated-texture` drives the actual Rml callback/render manager:
  exact pixels, invalid input, upload failure/recovery, independent views,
  replacement, shutdown and 1,000 close/reopen cycles.
- `openq4-ui-generated-adapter` compiles the real engine host and named-upload
  methods with counted renderer/decl boundaries: renderer limits, 1:6 uploads,
  create/upload/material failure, frame retirement and bounded registries over
  1,000 cycles. The existing layer/draw fixture verifies generated tint remains
  premultiplied. Adapter/layer checks also pass under Linux in WSL.
- The full Windows native suite passes 187/187. After adding the engine probe,
  the three affected native tests and retained-view lifecycle contract pass
  again; full compilation and staging pass.
- `ui_generated_image_runtime.py` runs Storage1 with hidden 640x480 windows and
  input disabled. `ui_retainedImageProbe` draws two alpha test panels through the
  production engine host. Initial, reopened and post-`vid_restart` engine
  screenshots on GL and Vulkan each pass eight predetermined RGB samples with
  a tolerance of three byte values. Both processes exit cleanly, and inspected
  captures include the in-game world and weapon. The Vulkan log identifies an
  RTX 4060 Laptop GPU and NVIDIA 591.74; the GL log records its 4.6 context.
- The same probe with `--mode MP` passes GL and Vulkan on Q4DM1, with the local
  player reported in gameplay before and after the sequence. Inspected engine
  captures show the world, weapon and HUD behind the generated panels. These
  runs reuse the same staged binary hashes and do not qualify physical input.

| Retained evidence | SHA-256 |
| --- | --- |
| `.tmp/stage-two/generated-image-source.json` (runtime source-file hashes) | `9eb637cdf3734d4e48c902c2d1a4b3d8baefc378cb8032ee29fea8973a5833e3` |
| `.tmp/s2image-gl/report.json` | `50e53cb5e4cc40d7c62eb0e45928ce50b4e146f6756a6857044e68c36a4b86bd` |
| `.tmp/s2image-vk/report.json` | `37140dfe4e18484083522b08c6a0a2918197b10f4255b9f3cdd8f7eff5459b62` |
| `.tmp/s2image-mp-gl/report.json` | `d199cd3a9bfb32dd2c0f28cfa1bce3dc4ecf41f2696158d84ee329848015abcc` |
| `.tmp/s2image-mp-vk/report.json` | `c0677d51d62dd48c142b4dd6d5085a6c215e9a638b692d1e109708cd14553ba6` |
| `.tmp/stage-two/generated-texture-native-testlog.json` | `9735dcb238604fc0ec0ffc2716fdc9d597af5b1036ad60de35d063e705caaf62` |

The logs and engine-written TGAs are under each run's `save/baseoq4/`; decoded
PNGs are alongside the reports. This does not establish generated font shaping,
all backend/device support, MP multi-context GPU behavior, end-to-end editor
authoring, or a performance budget. Those remain in the roadmap and requirement
register, whose acceptance states are unchanged.
