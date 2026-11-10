# Vulkan device admission

Automatic selection now checks a candidate's required capabilities before
publishing it to the renderer. Previously, the first graphics/present-capable
adapter could be chosen and then rejected for its API version or descriptor
limit, sending the entire launch back to OpenGL even when a later GPU was usable.

The renderer requires Vulkan 1.3, eight bound descriptor sets, dynamic rendering,
synchronization2 and the swapchain extension. It also checks for a nonempty
graphics/present queue with a successful surface-support query, color-attachment
surface usage, a compatible SDR surface format and a depth/stencil attachment
format. Optional features such as depth clamp, BC compression and programmable
sample locations retain their existing negotiation and fallbacks.

`r_vkDevice -1` takes the first admitted candidate in driver enumeration order.
An explicit index is checked alone; an unavailable or incompatible selection
fails without silently choosing another GPU. Rejected devices are logged with
their index, name, API version, descriptor limit and the failing check. This
does not rank GPUs by speed or change the default renderer.

The production selector uses instance query function pointers and does not
create a logical device or mutate renderer globals. Its native tests use the
same compiled library with fake driver responses. Device, extension and surface
format lists retry incomplete enumeration up to four times; failed or partial
results cannot become a successful selection. Admission and swapchain creation
share the SDR format selector, including the legacy undefined-format fallback.
An sRGB attachment is never substituted for display-coded UNORM output.

## Preliminary capability probe

The startup gate and `rendererVkProbe` now use the same compiled selection
library for their physical-device inventory. They read complete device and
device-extension lists with bounded retries, allocate queue-family storage
from the reported count, and ignore empty queues. The probe shares the
renderer's API-version and descriptor-set limits. It keeps its existing
logical-device, memory-allocation and optional timeline-semaphore checks.

Quiet startup stops at the first suitable candidate. Verbose diagnostics
inspect the full inventory and rank only suitable candidates by the existing
device-type, memory and transfer-queue preferences. A forced index queries
that device alone in either mode; an unavailable or incompatible choice fails
without switching GPUs. Optional capabilities remain optional, portability
support comes from the same extension inventory, and diagnostic core feature
queries respect the adapter's advertised API version.

This probe creates no window or surface, so presentation admission remains
the responsibility of the later renderer selector. Its preference score is
diagnostic and does not change automatic renderer selection order.

## Validation

The v61 Windows build passes all 43 renderer-selection cases and 31 new probe
cases through the production library. Probe cases include failed and changing
lists, bounded incomplete-enumeration retries, entries beyond the old caps,
empty queues, explicit choices, optional capabilities, older API versions and
an unsuitable high-memory device that must never win the diagnostic score.
The four related source contracts also pass. Current-round evidence is under
`.tmp/vulkan-gap-closure/probe-admission/`.

All eight staged startup/GPU/recovery cases pass again in v61. Six additional
local controls exercise the real capability probe: full verbose inventory,
forced NVIDIA quiet and Intel verbose probes, rejection of a Vulkan 1.2
translation adapter, an unavailable explicit index, and same-process OpenGL
startup recovery for that unavailable choice. The forced verbose probes query
only the requested device. Runtime hashes stay unchanged, and no Vulkan
validation or tracked renderer warnings appear in those six controls. The
Intel control takes 101 seconds including application startup and shutdown;
this is functional evidence, not a startup-performance pass.

The v61 stock Air Defense 1 and Q4DM1 runs at 0x MSAA also pass HDR on/off,
exposure, temporal scaling, resize and full/partial video-restart checks.
All 16 engine captures have the expected dimensions and nonblank contents;
representative initial and final views are inspected. Neither run reports
tracked renderer warnings, and the complete staged package stays unchanged.
These are hidden, windowed, input-disabled functional runs. Existing stock
MP asset/navigation warnings remain, and full visible parity is still open.

The v60 Windows build passes 43 native selection cases. They cover incompatible
devices before a valid device, explicit choices, unsupported features and
formats, failed queries, changing/incomplete enumeration, queues and formats
beyond the old fixed arrays, and clearing stale results after failure. The
eight staged startup, GPU self-test and recovery cases also pass; the explicit
driver-failure drill contains its expected injected failure diagnostic.

Four stock SP/MP gameplay profiles at 0x/4x MSAA pass capture, HDR, resize and
video-restart checks, producing 32 engine screenshots with no tracked renderer
warnings. Two more stock gameplay runs successfully recover to OpenGL after an
injected mandatory-resource failure, with one capture each. Both harnesses
verify unchanged runtime files during testing. These hidden, windowed runs
have input disabled; they establish local functional evidence, not visible
AA/PBR parity or performance qualification. Representative captures are also
inspected for complete gameplay views. Existing stock MP asset/AAS warnings
remain separate from the renderer warning checks.

Evidence is retained under `.tmp/vulkan-gap-closure/device-admission/`.
The native test is registered as `openq4-vulkan-device-selection` with Meson
when Vulkan and `build_native_tests` are enabled, so normal native-test runs
include it without a GPU or Vulkan loader.

## Complete inventories and adapter retry (23 October 2026, VK-03)

Every list the probe and renderer read is now complete or reported as failed.
The probe's instance-layer and instance-extension queries, the renderer's
instance-extension query and the surface present-mode list go through the same
bounded-retry enumeration as the device lists (`VK_FindInstanceLayers`,
`VK_FindInstanceExtensions`, `VK_QuerySurfacePresentModes`). A failed or
persistently changing list returns its error and reports nothing found,
instead of a truncated subset or an uninitialized one. A failed
instance-extension inventory stops both the startup gate and the renderer, so it
can never read as "no portability enumeration" and hide MoltenVK. A failed
layer inventory only disables validation, with a warning when it was requested.

The renderer no longer runs a second, separately capped device-extension lookup.
Admission records `VK_KHR_portability_subset` and `VK_EXT_sample_locations`
from the same complete list in which it finds the swapchain extension, and
device creation uses those flags. The window system's instance extensions are
read at the size SDL reports rather than truncated at twenty. Debug utils is
requested only when the loader or the validation layer provides it, and the
retry without the layer drops it when only the layer did. The swapchain image
arrays hold sixteen images, up from eight; a driver that creates more still fails
closed rather than indexing past them.

When an **automatic** start (`r_vkDevice -1`) admits an adapter that then fails
logical-device, swapchain or renderer-resource creation, the renderer tears
that adapter down without writing its pipeline cache and resumes selection at
the next enumeration index. Incompatible adapters are skipped by admission and
do not count; at most four adapters are tried. Screen parameters are applied
once, and a failed resize rebuild after them belongs to the window, so it does
not trigger a retry. An explicit `r_vkDevice` choice is never substituted: a
failure there still falls back to OpenGL. The override now accepts indices up
to 255 to match enumeration, which has no fixed device cap.

`r_vkStartupFailureDevice <index>` limits a swapchain (3) or renderer-resources
(4) `r_vkStartupFailure` drill to the admitted device with that index, so the
retry can be shown on real hardware. The log names each step:

```text
Vulkan startup failure injected: renderer resources on device 0
WARNING: Vulkan: device 0 'NVIDIA GeForce RTX 4060 Laptop GPU' failed during renderer resources; trying the next compatible device
Vulkan: skipping device 1 'Microsoft Direct3D12 (NVIDIA GeForce RTX 4060 Laptop GPU)' (API 1.2.359, descriptor sets 8): this renderer requires Vulkan 1.3 (-9)
Vulkan: started on device 2 'Intel(R) Iris(R) Xe Graphics' after 1 failed adapter attempt
```

### Evidence

- The native selection suite passes 107 cases: 51 renderer, 31 probe and 25
  instance/presentation cases. New cases cover resuming after a failed
  adapter, skipping an unsuitable next adapter, resuming past the last device,
  explicit choices that must not resume, explicit indices beyond the old cap,
  optional extensions beyond the old 1,024-entry cap, and layer, instance
  extension and present-mode lists beyond their old fixed arrays, with count,
  data, missing-layer, growing and persistently incomplete responses.
- `tools/tests/renderer_vid_restart_route.py` runs the production
  `VK_PrepareRenderDevice` against adapter doubles: retry after a resource or
  logical-device failure, skipped incompatible adapters, no substitution for an
  explicit choice, no further adapter, the four-attempt bound, and no retry for
  a failed resize rebuild.
- `tools/tests/renderer_display_presentation.py` now runs the production
  present-mode query against its stub driver list.
- On the Windows laptop (RTX 4060, Dozen, Iris Xe), hidden, input-free runs of
  the staged debug engine with debug builds of these modules: the
  renderer-resources and swapchain drills on device 0 both started on the Iris
  Xe; the same drill with `r_vkDevice 0` fell back to OpenGL. All Vulkan
  render-target, HDR and temporal GPU self-tests passed with the validation layer
  on and no validation messages. In airdefense1, three repeated `vid_restart`s
  held device-local memory at 1,004.5 MiB in 60 blocks and 2,032 allocations
  after the first restart. A validation-enabled session reported no validation
  messages or warnings and quit cleanly.
- A module swapped into a staged package must match the engine's buildtype:
  `builddir` and `.install` are debug builds with the static debug CRT, and a
  release-CRT module faults at quit freeing an engine-allocated material array.

## Remaining scope

Native fake-driver tests and one hybrid laptop do not establish AMD, physical
Linux or MoltenVK qualification (VK-01). Ranking adapters by speed or changing
the default renderer remain out of scope.

This startup correction does not resolve the observed cross-adapter frame
stalls, remaining PBR/material/shadow comparisons, or the broader
[Vulkan qualification requirements](archive/2026-10-18/plans/2026-09-20-vulkan-gap-closure.md).
