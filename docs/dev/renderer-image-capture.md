# Raw render-image captures

OpenGL and Vulkan expose the same console command for inspecting an existing
RGBA8 image without drawing it through a material:

```text
screenshot image _postProcessAlbedo2 screenshots/smaa-input.tga
screenshot image _postProcessAlbedo0 screenshots/smaa-output.tga
```

These examples require an active game view with SMAA enabled. The first image
contains the scene entering SMAA; the second contains its final output. The
intermediate `_postProcessAlbedo1` target is reused, so its end-of-frame contents
are the blended image, not the earlier edge mask.

The command reads mip zero of a loaded, single-sample, two-dimensional
`FMT_RGBA8` image, up to 8192 pixels per dimension. It preserves all four stored
channels and the image's dimensions, with no material sampling, rescaling,
exposure or color transfer. Vulkan's render-target row orientation is normalized
to the common image convention before writing the TGA. Files go under the
current game save path, normally `baseoq4/screenshots/`.

This captures the image's current contents; it does not render a new view or
populate an unused target. Unknown or defaulted images, multisampled targets,
depth, floating-point and compressed formats are rejected. The output must be a
`.tga` beneath `screenshots/`, without parent traversal or an absolute path.
Use `screenshot linear screenshots/scene.pfm` for the existing completed HDR
scene capture; that command retains its separate radiance/admission checks.

Readback deliberately waits for the GPU. OpenGL restores texture bindings and
pixel-transfer state. Vulkan submits, waits and resumes the acquired frame
without presenting a partial scene, and invalidates the interrupted GPU timing
sample. In a hidden window (`r_hiddenWindow 1`) the Vulkan frame is an
offscreen image rather than a swapchain image, and captures read it the same
way; see [Vulkan frame pacing](vulkan-frame-pacing.md#hidden-windows-and-a-sleeping-display-2026-10-06).
Ordinary rendering does not perform these transfers.

## Runtime validation

`tools/tests/renderer_image_capture.py` uses the existing procedural PBR
laboratory with hidden windowed rendering, engine commands and input disabled.
Its thirteen controls check repeated and interleaved reads, unchanged displayed
frames, orientation, scene/window resizing, image reload, both video-restart
paths, PBR/HDR switches and rejection of invalid images, formats and paths.
The report retains raw-image hashes alongside the laboratory's runtime, fixture,
configuration, log and harness provenance.

The v38 Windows captures exposed two rendering differences independently of
the capture checks: a one-byte classic resolve discrepancy amplified by SMAA,
and darker supersampled PBR preview edges. The retained negative evidence is
under `.tmp/vulkan-gap-closure/smaa-color-parity/`. v39 fixed the PBR float
resolve; v40 addresses the classic normalized-color resolve as described below.

## RGBA8 multisample resolve

The classic 8x investigation found identical stored sample values on both
APIs, but different native resolves. Five blue samples of 255 and three of zero
average to 159.375. OpenGL stored 159; Vulkan stored 160. SMAA's subsequent
contrast decision amplified that one-byte difference to 59 in the display.

For sampled, two-dimensional RGBA8 multisample images with an attachment-capable
destination, Vulkan now averages the stored samples in a float shader before
the final normalized-byte conversion. Each attachment uses a separate scope,
so mixed RGBA8/FP16 targets retain their existing formats. Other formats,
layered resolves and single-sample copies retain their existing paths.
All shader and descriptor preparation happens before the first attachment is
written. The copied extent remains the source/destination intersection, with
destination pixels outside it preserved. Depth validity and active-target
restoration continue through the existing shared resolve boundary.

The GPU target self-test checks every coverage count at supported 2x/4x/8x,
all four channels, repeated resolves, larger/smaller/equal destinations and
unchanged pixels outside the copy. Non-halfway results must be exact; halfway
ties can use either adjacent byte. The 159.375 case must therefore produce 159.
These checks supplement the existing mixed-attachment, depth, alias-rejection,
resize and retirement tests. Shader sources and the embedded header are pinned
by `vk_shader_header_pin.py`.

```powershell
python -B tools/tests/renderer_image_capture.py --backend vk --samples 8 `
  --runtime-root .tmp/runtime/candidate --output-dir .tmp/image-capture-vk `
  --basepath "E:\SteamLibrary\steamapps\common\Quake 4"
```

Use `--backend gl` with a separate output directory for the OpenGL reference.
The runtime must already contain the compiled laboratory and matching staged
engine, game and renderer modules.
