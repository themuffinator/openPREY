# Display Settings and Multi-Screen Guide

> [!NOTE]
> Inherited from openQ4 and not yet checked against PREY. This page describes what the engine code does; PREY behavior stays validation-pending until the [rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence for it.

This guide covers openPREY's display and window settings: the renderer, performance presets, fullscreen and windowed modes, anti-aliasing, scaling and multi-monitor behavior.

## Where the Settings Live

openPREY starts with PREY's own menus (`ui_retained 0`), which openPREY extends. **Options -> Video** has these tabs:

- The first tab sets the resolution (`r_mode`, from PREY's fixed list), fullscreen, brightness and gamma, and has the **Low / Medium / High** quality choices and **Recommended** (Auto-Detect).
- The two advanced tabs set shader detail, shadows, specular and bump maps, vertical sync, anti-aliasing (`r_multiSamples`), glow overlays, particle detail, fast skinning and anisotropy.
- openPREY's **Post FX** tab adds MSAA samples, post anti-aliasing, SSAO, bloom, the CRT filter, HDR tone mapping and exposure.
- openPREY's **Advanced FX** tab tunes them: MSAA alpha coverage, SSAO radius and intensity, bloom radius, HDR white point, saturation and contrast, and CRT strength and chromatic aberration.

Everything else on this page is a console setting. The `Settings -> System` page that openQ4 players know, with Rendering Backend, Rendering Device, Performance Preset and display sizing controls, belongs to the retained interface (`ui_retained 1`). That interface is inherited from openQ4 and hasn't been checked with PREY.

## Quick Start

- Press `Alt+Enter` to toggle between fullscreen and windowed mode. It uses the fast `vid_restart partial` path.
- Run `listDisplays` in the console to list monitor indices for `r_screen`.
- Run `listDisplayModes [displayIndex]` to list the exclusive fullscreen modes SDL3 reports, with content scale, pixel density and refresh details where available.
- After changing video cvars, run `vid_restart`, or `vid_restart partial` for quick window/fullscreen transitions.

## Video Options in the PREY Menu

PREY's own menu holds these settings under **Options -> Video**, on six side
tabs. The `Settings -> System` page described in the rest of this guide is the
upstream retained interface; the cvars and behaviour are the same.

| Tab | Rows |
|---|---|
| **Video** | Auto Detect, Quality Preset, Video Resolution, Full Screen, Render Scale, Vertical Sync, Brightness, Gamma |
| **Display** | Rendering API, Monitor, Fullscreen Mode, Borderless Window, Refresh Rate, Frame Rate Limit, Span All Monitors, Window Size, Custom Resolution |
| **Advanced 1** | Use Shader Programs, Shader Detail, Enable Shadows, Shadow Maps, Enable Specular, Enable Bump Maps, High Quality Specular, Sharpen Bumpmaps |
| **Advanced 2** | Use Glow, High Quality Skinning, Image Anisotropy |
| **Post FX** | MSAA Samples, Post Anti-Aliasing, SSAO, Bloom, Bloom Intensity, HDR Tone Mapping, HDR Exposure, CRT Monitor, Motion Blur |
| **Advanced FX** | Tuning sliders for MSAA alpha coverage, SSAO, bloom, HDR and CRT |

- **Quality Preset** offers all nine presets, and **Detect** picks one for the
  machine. Either one also sets the rows on the other tabs, so a preset is a
  starting point you can adjust.
- **Video Resolution** lists Desktop Native, every mode the selected monitor
  reports, and Custom. Typing a size into **Custom Resolution** selects Custom.
- Display changes, multisampling and presets light **Apply Changes**; pressing
  it, or leaving Options, restarts video once. The other rows take effect at once.
- **Rendering API** is read when the engine starts, so the menu asks for a
  restart of the game.
- **Shader Detail** (`r_shaderLevel`) selects PREY's skin, cloth, liquid and
  organic-wall shaders. It applies immediately; retail asked for a restart.
  Presets set it: Highest from Performance up, High for Low, Medium for Low
  Power and Low for Minimum, which also turn off glow overlays, high quality
  specular and bumpmap sharpening and use fast skinning. The Vulkan backend
  cannot run these shaders yet and always draws the Low versions; the row is
  greyed there.
- High Particle Detail is not offered: nothing in the engine reads
  `r_lowParticleDetail` yet.

## Rendering Backend and Device

OpenGL is the default. `r_renderApi` defaults to `best`, which picks OpenGL on desktop. OpenGL is the only renderer that runs PREY's own ARB interaction stages. The Vulkan renderer is opt-in: it reaches gameplay in focused tests, but it isn't at full parity with PREY yet (see [What Vulkan does not do yet](#what-vulkan-does-not-do-yet)).

| Setting | Default | What it does |
|---|---:|---|
| `r_renderApi` | `best` | Renderer backend. `best` selects OpenGL on desktop. Takes effect on **engine restart**, not `vid_restart`. |
| `r_renderDevice` | `auto` | GPU preference: `auto` prefers a compatible high-performance GPU, or a 32-character lowercase Vulkan device ID. A named device needs `r_renderApi vulkan`. Applied on engine restart. |
| `r_actualRenderApi` | (read-only) | Reports the backend that actually initialized. If Vulkan fails at startup, the engine **falls back to OpenGL** and this reports `gl`. |

### All `r_renderApi` values

| Value | Aliases | What it selects |
|---|---|---|
| `best` | - | OpenGL on desktop. With [VR](vr.md) enabled it also stays on OpenGL. |
| `gl` | `opengl` | OpenGL, with operating-system/driver GPU routing. |
| `vulkan` | `vk` | The Vulkan renderer module. Opt-in, and not at PREY parity yet. |
| `gl-module` | - | Always loads the OpenGL renderer as a module instead of using a statically linked copy. A diagnostic option that renders identically to `gl`. |
| `gles` | `es` | The OpenGL ES renderer module, inherited from openQ4's Android work. openPREY's desktop builds don't use it. |

Anything else is rejected with a warning, and openPREY uses the platform default.

### Choosing a GPU

`rendererDevices` lists the detected devices and their IDs. To use a specific GPU, set `r_renderDevice "<id>"` and `r_renderApi vulkan`, then restart the engine. `r_renderDevice auto` restores automatic selection. Device IDs are persistent Vulkan IDs, so a change in driver enumeration order doesn't select a different GPU. OpenGL uses the operating system's and driver's GPU routing. `r_vkDevice` remains a temporary diagnostic index override for launch command lines.

### Trying Vulkan

- Set `r_renderApi vulkan` and restart openPREY fully (not just `vid_restart`). The setting is archived to your config.
- Before switching, openPREY loads the Vulkan renderer module and tries to create a device with it. If the module is missing, there's no Vulkan driver, no GPU meets the renderer's Vulkan 1.3 feature floor, or the device can't be created, openPREY logs a warning and renders with OpenGL. `gfxInfo` gives the reason on its `Renderer API fallback reason` line, and `r_actualRenderApi` reports `gl`. Your `vulkan` selection is kept, so the next launch tries Vulkan again.
- Startup failures while creating the window, Vulkan surface, swapchain or mandatory renderer resources also recover to OpenGL in the same launch, and the failure reason stays in the log.
- If the GPU or driver resets during play (Vulkan reports a lost device), openPREY restarts the renderer and carries on with the same game, up to `r_vkPresentationRecoveries` times a session (default `3`). If presentation keeps failing after that, openPREY stops with an error and saves `r_renderApi gl` for the next launch. A window whose surface is lost, for example after a display change, gets a new surface without a restart.
- A device failure during a later full `vid_restart` also stops openPREY and saves `r_renderApi gl`. If you launched with `+set r_renderApi vulkan`, remove that option to return to OpenGL.
- To go back, run `r_renderApi gl` and restart.
- Vulkan reports are welcome. Check the list below first, then include `openprey.log`, `gfxInfo`, and your GPU and driver version.

### What Vulkan does not do yet

- **PREY's ARB interaction stages.** Vulkan has no executor for the custom ARB interaction programs in PREY's materials. It skips them and logs `Vulkan: custom Prey ARB interaction stages are unsupported; use renderer-gl` once, so affected surfaces don't light the way they do on OpenGL. PREY parity for Vulkan is tracked as TODO-RENDER-BACKENDS in the [rebase status ledger](../dev/prey-rebase/status-ledger.md#explicit-deferral-register).
- **Some other material programs.** A program that relies on state a material stage doesn't have is skipped and logged once: fixed-function lighting, fog or texture-generation state, program environment values the engine never sets for material stages, ARB `RECT`, `1D` or `3D` textures, the `ARB_fog_*` options, or NVIDIA program options.
- **Clustered decal routing.** `r_rendererClusteredDecals` only changes how OpenGL's modern path routes decals, so it does nothing on Vulkan.
- **Pixel readbacks in the debug views.** A Vulkan frame can't stop halfway to read pixels back, so the overdraw averages that `r_showLightCount 3` and `r_showShadowCount 2` to `4` print arrive a frame or two late, and `r_showIntensity` and `r_showDepth` recolour a copy of the view instead.

## Performance Presets

The `com_performancePreset` cvar stores the selected preset. Run `applyPerformancePreset [name]` from the console to apply one. Without a name it reapplies the stored `com_performancePreset`; if that value is invalid, openPREY falls back to `balanced`. Unknown names are rejected without changing the current preset.

The quality choices on the first **Options -> Video** tab use the same recipes: **Low** applies `low`, **Medium** applies `performance` and **High** applies `balanced`. **Recommended** runs `autoDetectPerformancePreset`. These keep your display mode and VSync preference. `execMachineSpec` also maps the legacy `com_machineSpec` classes onto these presets.

| Preset | Display and AA | Texture and audio profile | Intended use |
|---|---|---|---|
| `minimum` | 50% scale, no AA, no shadows, 30 FPS cap | Aggressive texture downsizing, 1x anisotropy, one sound sample per shader, automatic speaker layout, room reverb, lower emitter budget | The floor: software or limited renderers, and systems below the minimum requirements. |
| `lowpower` | 75% scale, no AA, no shadows, 30 FPS cap | Texture downsizing, 1x anisotropy, one sound sample per shader, automatic speaker layout, room reverb, lower emitter budget | Battery saving and very limited GPUs. |
| `low` | 75% scale, no AA, stencil shadows, 60 FPS cap | Texture downsizing, 2x anisotropy, one sound sample per shader, automatic speaker layout, room reverb, lower emitter budget | PCs at the [minimum requirements](getting-started.md#system-requirements). |
| `performance` | 85% scale, SMAA medium, 60 FPS cap | Full-size textures, 2x anisotropy, automatic speaker layout, room reverb, moderate emitter budget | Modest desktops and handhelds aiming for smoother frame pacing. |
| `balanced` | 100% scale, 2x MSAA, SMAA medium, 120 FPS cap | Full-size textures, 4x anisotropy, automatic speaker layout, room reverb, full emitter budget | General desktop default. |
| `enhanced` | 100% scale, SMAA high (no MSAA), 144 FPS cap, 1024 projected shadow maps and 512 point-light cubes | 16x anisotropy, full-size textures, automatic speaker layout, room reverb | High-refresh play with modern effects: holds 144 FPS on the reference laptop. |
| `quality` | 100% scale, 2x MSAA, SMAA high, 144 FPS cap, 2048 projected / 512 point shadows | 16x anisotropy, DDS replacements enabled, larger upload budget, automatic speaker layout, room reverb | Every light shadow-mapped; holds 100 FPS on the reference laptop. |
| `ultra` | 100% scale, 4x MSAA, SMAA Ultra, 240 FPS cap, 4096 projected / 512 point shadows | 16x anisotropy, full-size textures and DDS replacements enabled, high-end benchmark tag, automatic speaker layout, room reverb | The best image that holds 75 FPS on the reference laptop. Manual choice. |
| `maximum` | 100% scale, 16x MSAA request, SMAA Ultra, 240 FPS cap, 4096 projected / 2048 point shadows | As Ultra | Everything on. No frame-rate target. Manual choice. |

`enhanced`, `quality`, `ultra` and `maximum` enable [shadow maps](shadow-mapping.md), bloom, SSAO and tone mapping. Enhanced shadow-maps every light with 5-tap fixed filtering: 1024 projected maps in a 4096 atlas and 512 point cubes, with 12 SSAO samples. (The shared preset table leaves point lights on stencil shadows at this tier; openPREY maps them, because PREY lights its levels almost entirely with point lights and the tier would otherwise map nothing.) Quality shadow-maps every light: 2048 projected maps with 9-tap PCSS, 512 point cubes, a 4096 atlas and 20 SSAO samples. Ultra raises projected maps to 4096 with 13-tap PCSS in an 8192 atlas and uses 32 SSAO samples; its point cubes stay at 512 because larger cubes cost more than every other upgrade together. None of these three uses cascades or motion blur. Maximum requests every supported maximum: 2048 point cubes, 13-tap projected and point filtering, four stabilized cascades, a 16384 shadow atlas, 32 SSAO samples and 16-sample motion blur with object vectors. All modern-effects tiers keep unlimited shadow updates and five bloom levels; reducing the level count changes the glow's appearance, not just sampling quality. Low, Performance and Balanced retain the original stencil shadows and leave these post effects and the HDR scene target off. Minimum and Low Power draw no shadows at all, so that the two presets below the minimum requirements remove rendering work rather than only resolution. On Intel Iris Xe graphics that took 12 to 16 percent off each frame in the hub and combat scenes upstream openQ4 measured, about as much as lowering the scene from 75% to 50%. Changing down from Maximum restores the lower tier's sample counts and shadow sizes, including settings for effects currently disabled.

### Frame-rate targets

Enhanced, Quality and Ultra were built upstream to hold a frame-rate class on openQ4's reference machine (an RTX 4060 Laptop GPU with an i7-13700H at 2560x1440) in its Quake 4 performance suite: Enhanced 144 FPS average, Quality 100 FPS and Ultra 75 FPS. PREY scenes haven't been measured against them, so treat the targets as a rough guide. The upstream results are in the [performance report](../dev/performance-report.md).

MSAA is clamped to the highest sample count the active device and render-target formats support; `gfxInfo` shows requested and effective counts. Every preset from Balanced up renders at native resolution. Brightness, exposure, effect strength and experimental renderer modes are separate controls, and CRT filtering stays off. Presets restore full material detail and clear any diffuse `image_picmip` reduction; every preset from Low up also turns shadows back on.

Storing `com_performancePreset` alone doesn't reapply a profile. Select the preset again, or run `applyPerformancePreset <name>`.

Performance presets write video, texture-allocation, texture-sampling and audio backend cvars. Anisotropy is capped to what the active GPU supports. Run `vid_restart` after applying one so renderer, texture and sampler changes take effect, and `s_restart` if you want speaker, EAX and emitter-budget changes to rebuild the sound backend immediately.

In the retained interface (`ui_retained 1`), choose the preset on **Settings > Display** and press **Apply Changes**. That restarts the renderer once and, when the speaker layout or reverb setting changed, the sound device. A preset that changes anti-aliasing asks you to keep or revert. High-quality texture flags and the per-sound sample limit fully change when the game next starts; the page tells you when your changes include one of them.

### Auto-Detect

`autoDetectPerformancePreset` takes no arguments. It recommends and applies a starting point from the **active renderer and GPU**, system RAM, CPU concurrency, platform power hints and the current drawable resolution. It doesn't run a benchmark or promise a frame rate, and it never picks Maximum.

- Software rendering, insufficient classic material/texture capabilities and systems with at most 2 GiB RAM select Minimum. A PC at the minimum requirements, with at most 4 GiB RAM or a discrete GPU with at most 1 GiB of verified dedicated memory, selects Low. `OPENPREY_LOWPOWER=1` selects Low Power unless the Minimum constraint applies. Discrete GPUs with at most 512 MiB of verified dedicated memory select Minimum.
- The Steam Deck profile selects Performance. Shared-memory GPUs can select Balanced at up to the 1080p class with enough RAM and classic-rendering capability.
- Discrete GPUs are placed by their **verified active-device dedicated memory**, with 16 GiB RAM and modern effects; each resolution class above 1440p costs one preset:

  | Dedicated memory | Up to 1440p | Up to 4K | Above 4K |
  |---|---|---|---|
  | 8 GB | Enhanced | Balanced | Performance |
  | 12 GB | Quality | Enhanced | Balanced |
  | 16 GB | Ultra | Quality | Enhanced |
  | 24 GB or more | Ultra | Ultra | Quality |

  A class starts at 15/16 of its nominal size, because drivers report slightly less than the card's label. Quality and Ultra also need eight logical CPUs. Smaller budgets select Performance or Balanced, and fewer than four logical CPUs lower any recommendation to Performance.
- A resolution class is named by its 16:9 size and includes the taller shapes beside it, so 1920x1200 counts as 1080p and 2560x1600 as 1440p. A 3440x1440 ultrawide counts as the 4K class.
- Unknown or implausible observations never manufacture extra VRAM. Drivers without active-device memory reporting conservatively select Performance. Shared RAM isn't counted as dedicated VRAM, and another adapter's memory isn't used on hybrid systems.
- Detection before renderer initialization leaves settings unchanged. Resolution, fullscreen policy, refresh, VSync, backend selection, input and interface preferences stay yours.
- An automatic recommendation caps the frame rate at the refresh rate of the display the window is on, in whole hertz (a 59.94 Hz display caps at 60). When the refresh rate is unknown or outside 30-1000 Hz, the preset's own cap applies. A power-limited device never caps above its preset. Selecting a preset by name always uses its table cap.

Auto-Detect can also lower the **scene render scale** below the preset's table value on large displays; for example, shared-memory graphics at 4K use Performance at 50% (a 1080p scene). The window and UI keep their native resolution, and a named preset restores its table values. VR headset scale is a separate [VR setting](vr.md).

On a fresh installation, openPREY starts with a small bootstrap profile, observes the initialized GPU and applies the automatic recommendation before entering gameplay. The console's `Quality profile:` line reports the bootstrap preset on first launch, then the detected profile once detection has applied it. A preset supplied at launch takes precedence, and existing saved settings are kept.

`performancePresetSelfTest` checks the preset commands, cvar mappings, auto-detect and backup/restore, then restores every cvar it touched. It's meant for package and platform validation.

## Core Display Settings

| Setting | Default | What it does |
|---|---:|---|
| `r_fullscreen` | `1` | `1` = fullscreen, `0` = windowed. |
| `r_fullscreenDesktop` | `1` | `1` = native desktop fullscreen (recommended). `0` = exclusive fullscreen using `r_mode`/`r_custom*`. |
| `r_borderless` | `0` (`1` on Windows) | Borderless window when `r_fullscreen 0`. Windows configurations are switched to borderless once (see below). |
| `r_windowWidth` | `1280` | Windowed width. |
| `r_windowHeight` | `720` | Windowed height. |
| `win_xpos` | (auto) | Outer window-frame X position, updated when you move the window. |
| `win_ypos` | (auto) | Outer window-frame Y position, updated when you move the window. |
| `r_mode` | `-2` | Fullscreen sizing selector: `-2` = desktop native, `-1` = custom, `0+` = legacy preset index. |
| `r_customWidth` | `1920` | Custom exclusive-fullscreen width used with `r_mode -1`. |
| `r_customHeight` | `1080` | Custom exclusive-fullscreen height used with `r_mode -1`. |
| `r_displayRefresh` | `0` | Exclusive fullscreen refresh rate in whole hertz. `0` (Auto) keeps your desktop's refresh rate when the resolution offers it, otherwise the nearest rate it does offer. |
| `r_screen` | `-1` | Monitor target: `-1` = auto/current, `0..N` = explicit index from `listDisplays`. |

## Texture Quality (Picmip and Downsizing)

openPREY has two independent ways to spend less memory and bandwidth on textures.

**`image_downSize*`** is the idTech 4 ceiling PREY already had: no texture of that kind may exceed a given size. Performance presets drive these.

**`image_picmip`** is a relative reduction in the style of Quake 3's r_picmip: it drops whole mip levels, so every step halves a texture however large it started. openPREY applies it **only to the diffuse layer of materials**, the colour texture of a `diffusemap` stage. Normal maps, specular maps, lighting, skies, decals, fonts and every 2D/HUD surface keep their authored resolution, so surfaces stay correctly lit and the interface stays sharp.

| Setting | Default | What it does |
|---|---:|---|
| `image_picmip` | `0` | Mip levels to drop from diffuse textures. `0` = full resolution. Each step halves the texture. |
| `image_picmipFilter` | `1` | Which image paths `image_picmip` may reduce. `0` = every diffuse texture, `1` = `textures/*` (world surfaces), `2` = `models/*` (characters, weapons, props), `4` = any other namespace. Add values to combine. |
| `image_picmipMinSize` | `32` | Reduction stops once a texture's longest axis reaches this size, so small textures never turn to mush. |
| `image_useHighRes` | `1` | Loads textures that PREY materials mark `highres` at full size. `0` halves them, as the original game did below its highest quality setting. |
| `image_downSize` | `0` | Enables the general texture size ceiling. |
| `image_downSizeLimit` | `0` | That ceiling, in pixels. `0` = no limit. |
| `image_downSizeBump` / `image_downSizeBumpLimit` | `0` / `256` | Separate ceiling for normal maps. |
| `image_downSizeSpecular` / `image_downSizeSpecularLimit` | `0` / `64` | Separate ceiling for specular maps. |

The ceiling is applied first and `image_picmip` reduces from there. A material that declares `nopicmip` opts out of both.

These settings change the pixels a texture is built from, so openPREY reloads images automatically when you change one; no `vid_restart` is needed. The generated texture cache is keyed by the active reduction, so switching back and forth doesn't leave stale sizes behind.

DDS replacement packs have one limitation. Compressed data can only be reduced by discarding mip levels the file already contains, so a `.dds` exported without a full mip chain stays larger than the same texture would on the normal path. Set `image_showPrecompressedTextures 1` to have openPREY name any replacement that couldn't reach the requested size.

```
image_picmip 2
image_picmipFilter 3
```

That halves world and model diffuse textures twice while leaving lighting detail, the HUD and menus untouched.

## Texture Sampling

`image_filter` controls how ordinary material textures are sampled. It's saved in your configuration and updates loaded textures immediately, without a `vid_restart`. Material stages that explicitly request linear or nearest sampling keep their authored behavior, which protects explicitly filtered fonts, HUD elements, shadow data and renderer-internal textures.

| Value | Texels | Mip levels | Typical use |
|---|---|---|---|
| `GL_LINEAR_MIPMAP_LINEAR` | Linear | Smooth blend | Default, smoothest general-purpose sampling. |
| `GL_LINEAR_MIPMAP_NEAREST` | Linear | Nearest level | Smooth texels with sharper mip transitions. |
| `GL_NEAREST_MIPMAP_NEAREST` | Nearest | Nearest level | Pixelated textures with stable distance scaling. |
| `GL_NEAREST_MIPMAP_LINEAR` | Nearest | Smooth blend | Pixelated texels with softer distance transitions. |
| `GL_NEAREST` | Nearest | Disabled | Fully point-sampled; may shimmer in the distance. |
| `GL_LINEAR` | Linear | Disabled | Bilinear sampling without mip levels. |

For a pixelated texture style, enter:

```
seta image_filter GL_NEAREST_MIPMAP_NEAREST
```

Nearest-texel modes automatically avoid anisotropic filtering, so `image_anisotropy` can't blur the pixel edges. The same values work with the OpenGL and Vulkan renderers.

## Frame Cap

| Setting | Default | What it does |
|---|---:|---|
| `com_maxfps` | `240` | Presentation frame cap (`0` = uncapped). |
| `com_steamDeckAutoFrameCap` | `1` | While the Steam Deck profile is active, applies a Deck-friendly cap only while `com_maxfps` is still `240`. |
| `com_steamDeckFrameCap` | `0` | Steam Deck cap override (`0` = the detected display refresh, clamped to a Deck-oriented range). |
| `com_preciseFrameWait` | `1` | `1` waits out the cap on a high-resolution timer and busy-waits only as long as that timer needs; `0` restores the older whole-millisecond wait. |
| `com_showFramePacing` | `0` | `1` shows frame times (to 0.01 ms), the display's refresh rate and what limits the frame rate; `2` also logs them. |
| `com_latencyFlash` | `0` | **Latency measurement aid.** Draws a white bar down the left edge on the first frame after you press fire, for click-to-photon sensors such as NVIDIA LDAT or OSLTT. Leave it off for normal play. |

The Steam Deck auto cap preserves custom `com_maxfps` values. Set `com_steamDeckAutoFrameCap 0` to opt out, or set `com_maxfps` directly for a fixed cap.

A minimized or hidden window draws at most 60 frames a second, whatever the cap. With vsync on and a variable-refresh display (G-Sync, FreeSync), cap a few frames under the refresh rate (for example `com_maxfps 237` on a 240 Hz display) so frames never wait for the next refresh.

## Anti-Aliasing Settings

In the stock menu, **Options -> Video -> Post FX** sets MSAA samples (off, 2x, 4x or 8x) and post anti-aliasing, and **Advanced FX** sets MSAA alpha coverage. The advanced video tab's anti-aliasing choice also writes `r_multiSamples`.

| Setting | Default | What it does |
|---|---:|---|
| `r_multiSamples` | `0` | MSAA sample count for the main scene render target (`0`, `2`, `4`, `8`, `16`; `0` = off). |
| `r_postAA` | `0` | Post AA mode (`0` = off, `1` = SMAA medium, `2` = SMAA high, `3` = SMAA ultra, `4` = colour-edge prototype). |
| `r_msaaAlphaToCoverage` | `1` | Alpha-to-coverage for perforated/alpha-tested materials when MSAA is active. Helps foliage and fences look cleaner. |
| `r_msaaResolveDepth` | `0` | Also resolves depth during the MSAA resolve. Leave it off unless you're debugging a depth-dependent edge case. |

`r_multiSamples` value guide:
- `0`: disabled (fastest, most aliasing).
- `2`: low-cost MSAA uplift for modest GPUs.
- `4`: a good quality/performance balance.
- `8`: high quality, noticeably higher GPU cost.
- `16`: enthusiast setting where supported.
- `1` gives no meaningful benefit and is normalized to off.

`r_postAA` value guide:
- `0`: disabled.
- `1`: SMAA medium; luma-edge detection with a `0.10` threshold and 8-step search.
- `2`: SMAA high; the same `0.10` threshold and a 16-step search.
- `3`: SMAA ultra; a lower `0.05` threshold and a 32-step search.
- `4`: colour-edge prototype; colour-edge detection with a `0.10` threshold and a 16-step search, for comparison captures.

Notes:
- `r_multiSamples` is hardware-limited and may be clamped by the driver or GPU.
- Unsupported `r_multiSamples` values are normalized before video startup: `1` becomes off, and odd or intermediate values step up to `2`, `4`, `8` or `16`.
- Video startup retries lower MSAA requests if the window or GL context rejects the requested sample count (`16 -> 8 -> 4 -> 2 -> off`) and logs the requested, selected and driver-reported attributes.
- The game scene target is validated separately from the window framebuffer. If a driver rejects the offscreen target at the selected sample count, openPREY retries lower counts down to `0`; if even the single-sample target is unavailable, it keeps running through the direct-render fallback and logs the framebuffer status.
- `gfxInfo` reports the active AA summary: requested/effective MSAA, `GL_MAX_SAMPLES`, alpha-to-coverage, post AA mode, screen fraction and supersampling. Once a map is drawing, the effective MSAA count is the one the 3D scene rendered with, so after an `r_multiSamples` change it shows the old count until `vid_restart` or the next map load.
- On Vulkan, MSAA applies to the 3D scene, not the window, and stops at 8x.
- Follow an `r_multiSamples` change with `vid_restart`. `r_postAA`, `r_msaaAlphaToCoverage` and `r_msaaResolveDepth` can change at runtime.

## Motion Blur

Motion blur (`r_motionBlur 1`, on in the `maximum` preset) smears the scene along its own motion: the camera turning or moving, and moving characters and objects. It keeps its own short history of the camera, so it works with or without temporal AA, resolution scaling, supersampling, MSAA, bloom, tone mapping and SSAO, on OpenGL and Vulkan.

- **The same blur at any frame rate.** The blur length follows how fast things move, not how many frames you draw: by default it matches the motion of one 60 Hz frame (`r_motionBlurShutterMsec 16.667`). `r_motionBlurShutterMsec 0` restores the original behavior, where blur shrinks as the frame rate rises.
- **Your weapon stays sharp.** The view weapon only blurs with its own animation, never because you turn. `r_motionBlurObjectVectors 0` blurs by camera motion alone.
- **No blur across cuts and pauses.** Camera cuts, map loads, `vid_restart`, resizing and teleports start a fresh history instead of smearing between unrelated views. Pausing stops the blur.
- **Below 10 FPS it switches off.** A frame that takes longer than 100 ms is treated as a discontinuity.
- `r_motionBlurStrength` (0.45), `r_motionBlurMaxPixels` (10) and `r_motionBlurSamples` (8, 16 on `maximum`) tune the length multiplier, the longest smear and its quality. `r_motionBlurDebug 1` shows the motion vectors instead of the blur.
- `rendererMotionBlurStatus` prints what motion blur actually did: how many views it drew, why any were skipped, and the strength, length and sample count in use. `rendererMotionBlurStatus reset` clears the counters.

## Resolution Scale

| Setting | Default | What it does |
|---|---:|---|
| `r_screenFraction` | `100` | Main-scene resolution scale percentage (`10..200`). Values below `100` reduce scene resolution for performance; values above `100` supersample the scene before resolving it back to the native back buffer. |
| `r_resolutionScaleMode` | `1` | How a scene below `100%` is stretched to your screen: `1` smooth (bilinear), `2` sharpened, `3` nearest-neighbour (crisp and pixelated), or `0` the legacy cropped viewport for fill-rate testing. The HUD and menus stay at native resolution in every mode. |
| `r_resolutionScaleSharpness` | `0.4` | Sharpening strength for mode `2` (`0..1.5`). |

With modes `1` and `2`, a scene below `100%` is upscaled by temporal anti-aliasing by default (`r_temporalAA 2`), which keeps edges smooth and recovers detail a plain stretch loses; see [Temporal AA](temporal-presentation.md). Modes `0` and `3` keep their own look.

## Fullscreen Policy (Desktop vs Exclusive)

- The default is **desktop-native fullscreen** (`r_fullscreenDesktop 1`): fullscreen matches your current desktop resolution and doesn't change the display mode.
- For **exclusive fullscreen**, set `r_fullscreenDesktop 0`. `r_mode`/`r_customWidth`/`r_customHeight` then control the requested fullscreen resolution. The resolution list on the first **Options -> Video** tab writes `r_mode` from PREY's fixed list.
- `listModes` shows the expanded legacy `r_mode` preset catalog, covering common desktop, laptop, ultrawide, HiDPI, 4K, 5K, 6K and 8K resolutions. `listDisplayModes` shows what your monitor actually supports in exclusive mode.
- `r_displayRefresh 0` (Auto) keeps your desktop's refresh rate, or the nearest rate the resolution offers, and openPREY picks the same rate for the same resolution at startup, after `vid_restart` and after Alt+Enter. Leave it on Auto unless you need a specific exclusive-mode refresh rate.
- On Windows, fullscreen windows minimize on focus loss so Alt+Tab and the Snipping Tool overlay can take the foreground cleanly.
- On Windows, `PrintScreen` goes to the system snipping UI by default (`win_printScreenToSystemTool 1`). Bind the in-engine `screenshot` command to another key, or set that cvar to `0` to make `PrintScreen` available for in-engine binds again.

With `r_fullscreenDesktop 1`, `r_mode` and `r_custom*` are ignored for fullscreen sizing. Use `r_screenFraction` for below-native scaling or supersampling while staying in desktop-native fullscreen. On Wayland, the display diagnostics also report scale, orientation, pixel density and refresh details that help diagnose compositor scaling.

## Windowed Sizing and Placement

- The first time openPREY starts on Windows, it switches the window to borderless presentation (`r_borderless 1`) to avoid OpenGL bordered-window frame-pacing stalls. Set `r_borderless 0` and run `vid_restart` if you want a resizable bordered window.
- In bordered windowed mode (`r_fullscreen 0`, `r_borderless 0`), resizing updates `r_windowWidth`/`r_windowHeight` from the client area. Maximizing or minimizing doesn't overwrite the remembered normal size.
- Moving the window updates `win_xpos`/`win_ypos` from the outer frame, while `r_windowWidth`/`r_windowHeight` describe the drawable client area. Borderless and fullscreen placement don't overwrite the remembered normal position.
- Switching from fullscreen to windowed restores the last remembered windowed size and position.
- If you unplug or rearrange monitors and the saved position ends up off-screen, openPREY clamps or recentres the window onto a valid display.
- With an explicit `r_screen` index (`0..N`), the whole window frame is constrained to that display's usable area, and the client area shrinks if needed so the title bar and borders fit. With `r_screen -1`, your placement is respected unless it becomes invalid.
- Native Wayland compositors own absolute placement. openPREY requests the selected display and client size there and accepts the compositor's placement.
- Hold `Shift` while resizing to snap the window to common aspect ratios (4:3, 16:9, 16:10, 21:9 and so on).

## Aspect Ratio and FOV

There's no aspect-ratio setting. The game derives the horizontal field of view from the current render size (keeping PREY's 4:3 vertical view and widening it), so any aspect ratio works without manual selection.

## View Weapon FOV and Placement

These renderer settings control how the first-person weapon is projected. They're client-side and don't affect gameplay or the network.

| Setting | Default | What it does |
|---|---:|---|
| `cl_gunfov` | `0` | View-weapon FOV override (`0` = follow the current view FOV). Values above `0` are clamped to a safe range. |
| `cl_gunfov_adjust` | `1` | Aspect policy for `cl_gunfov`: `1` keeps classic 4:3-style weapon framing across screen ratios, `0` uses direct viewport-based FOV conversion. |

PREY's own `g_gunX`, `g_gunY` and `g_gunZ` cvars offset the weapon model; they default to `0`.

## UI Aspect Correction

This controls 2D UI layout: menus, HUD, console and loading screens.

| Setting | Default | What it does |
|---|---:|---|
| `ui_aspectCorrection` | `1` | `1` keeps classic 4:3-style correction for all 2D UI. `0` stretches 2D UI to the full 2D draw region. |

## Television Viewing (Couch Profile)

openPREY keeps openQ4's Couch platform profile for television play. It's selected when the `SteamTenfoot` environment variable that Steam's Big Picture mode sets is present (a Steam Deck keeps its own profile), when you set `OPENPREY_COUCH=1`, or when you start the game with `+set com_platformProfile couch`. `OPENPREY_COUCH=0` stops Big Picture from selecting it.

A profile applies its settings from `openprey_profile_<name>.cfg`. openPREY ships only `openprey_profile_steamdeck.cfg` so far, so the Couch profile has no settings of its own yet. The size controls openQ4's version raised (`ui_retainedScale`, `ui_retainedTextScale` and `ui_hudScale`) belong to the retained interface and its HUD.

## Text Rendering

PREY's bitmap fonts are the default (`r_useTrueTypeFonts 0`). openPREY also ships TrueType versions of the game's fonts in `pak0`. With `r_useTrueTypeFonts 1`, menu and HUD text is drawn from those and rasterised at your display's resolution instead of magnifying the original fixed-size atlases, so text stays sharp at 1440p and 4K. The TrueType path doesn't draw PREY's spline text effect yet (TODO-D10 in the [rebase status ledger](../dev/prey-rebase/status-ledger.md#explicit-deferral-register)), which is why it's off by default.

| Setting | Default | What it does |
|---|---:|---|
| `r_useTrueTypeFonts` | `0` | `1` draws text from the scalable fonts. `0` uses the original bitmap fonts. |
| `r_ttfFontResolution` | `1.0` | Multiplies the resolution the glyphs are rasterised at (`0.25..4`). Raise for slightly sharper text at the cost of texture memory. |

Changing either takes effect the next time fonts load, so restart the game or run `vid_restart`. Raising `r_ttfFontResolution` costs texture memory quadratically. If the font files are missing, the game falls back to the bitmap fonts.

## Text Background (Accessibility)

PREY draws much of its text straight over the world and over busy panel artwork, which can leave very little contrast. This draws a solid black backing behind each line of menu and HUD text.

| Setting | Default | What it does |
|---|---:|---|
| `gui_textBackground` | `0` | How opaque the backing is. `0` is off, `1` is fully opaque black. `0.6` to `0.8` is usually enough to read comfortably while still showing the artwork. |
| `gui_textBackgroundPadding` | `2` | How far the backing extends past the text, in 640x480 virtual units. |

Both apply immediately and work with either font path.

```
seta gui_textBackground 0.75
seta gui_textBackgroundPadding 2
```

The backing covers text drawn by the menus, HUD and in-game GUIs. The developer console draws on its own path and isn't affected.

## Multi-Monitor Behavior

When the render surface spans multiple monitors:

- 2D elements (console, HUD, menus, loading screens) are constrained to the selected display region. With `r_screen -1`, that's the primary display.
- 2D aspect behavior inside that region follows `ui_aspectCorrection`.
- Menu cursor mapping follows the same region, so mouse interaction stays aligned.

3D world rendering isn't affected by these UI cvars.

## Useful Console Examples

### Recommended Modern Defaults

```cfg
seta r_screen -1
seta r_fullscreenDesktop 1
seta r_fullscreen 1
seta r_multiSamples 4
seta r_postAA 1
seta r_msaaAlphaToCoverage 1
seta ui_aspectCorrection 1
vid_restart
```

### Borderless Window on a Specific Monitor

```cfg
seta r_fullscreen 0
seta r_borderless 1
seta r_screen 1
vid_restart
```

### Custom Fullscreen Resolution

```cfg
seta r_fullscreen 1
seta r_fullscreenDesktop 0
seta r_mode -1
seta r_customWidth 2560
seta r_customHeight 1440
vid_restart
```

### Stretch Menu and HUD (No 4:3 Correction)

```cfg
seta ui_aspectCorrection 0
```

### View Weapon: Classic Framing

```cfg
seta cl_gunfov 90
seta cl_gunfov_adjust 1
```

### Performance-Focused AA

```cfg
seta r_multiSamples 2
seta r_postAA 1
seta r_msaaAlphaToCoverage 1
vid_restart
```

### Maximum Clarity (Higher GPU Cost)

```cfg
seta r_multiSamples 8
seta r_postAA 1
seta r_msaaAlphaToCoverage 1
vid_restart
```

## Experimental Vulkan Overlap

The Vulkan renderer has three `r_vkRenderThread` modes:

| Value | Behavior |
| --- | --- |
| `0` | Default: render on the main thread. |
| `1` | Draw the previous frame while running the next game tic. |
| `2` | Also prepare the next frame while drawing the previous one. |

Use `r_vkRenderThread 2` in the console to try full overlap, and `r_vkRenderThread 0` to return to the default. `renderThreadStats` reports submitted and completed frames and how often front ends started or finished while the backend was busy.

Mode 2 is experimental: its geometry copies add CPU and memory cost, and no performance improvement has been qualified. Use engine and renderer modules from the same build. OpenGL stays synchronous. See the upstream [qualification record](../dev/presentation-owners.md#full-front-end-overlap-4-november-2026).

## Troubleshooting

- If a display change doesn't apply, run `vid_restart`.
- If monitor targeting looks wrong, run `listDisplays`, set `r_screen` to the right index and restart video.
- If the UI looks too centred or boxed on a wide display, set `ui_aspectCorrection 0`.
- If the window opens off-screen after a monitor change, set `r_screen` to the target monitor and restart video; openPREY also tries to recover on its own.
- If AA settings seem unchanged, check `r_multiSamples`, `r_postAA` and `r_msaaAlphaToCoverage`, then run `vid_restart`.
- If the 3D view turns black with `r_postAA` on, set `r_postAA 0`, run `vid_restart`, and attach `openprey.log` plus the output of `gfxInfo` to your report.
- If surfaces look unlit or wrong on Vulkan, switch back with `r_renderApi gl` and restart; PREY's ARB interaction stages only run on OpenGL.
