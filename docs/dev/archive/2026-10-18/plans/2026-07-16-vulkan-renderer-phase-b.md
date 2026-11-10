# Vulkan Renderer Phase B: Renderer Extraction Stages

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Date: 2026-07-16
Status: B1 landed (73bccf7a); B2-prep/B3 trampoline (a07c9ec1); B2 carve (04128897); B3 bakeLightGrids (79df21e3) — framework/ui/sound hold zero renderer-internal includes; B4 ABI v2 (24f84ae7); B6a dmap -draw retirement (9dbdaa5c); B6 render_geo carve landed — dmap compiles against src/render_geo only, dmap output byte-identical, shared lib is tr/cvar/vertexCache-free with renderer hooks. B7 redesigned per audit (null renderer infeasible; ded keeps the real front-end, GL-free link co-sequenced with B8). B5a landed — engine-owned engineWindowState_t (sys_public.h) carries vid/uiViewport/fullscreen window state with the platform layer dual-writing glConfig until B5b moves the mirror behind the module import; engine readers (ui, framework, sys) repointed. B5b landed — the GL context half lives in renderer/OpenGL/gl_ContextSDL3.cpp (compiled into the SDL3 backend TU until B8) and reaches the engine window layer exclusively through renderWindowServices_t (ABI v3): module-driven candidate negotiation with per-attempt window recreation, split init/screen-parms/teardown, ctx-local window/context statics, hGLRC reverse write deleted, macOS token guards rebound to the seam. B8 F1+F2 landed — renderer-gl_x64 module builds from the shared renderer sources, ABI v4, RendererGLModule glue TU, opt-in `r_renderApi gl-module` first-boot activation; verified rendering mp/q4dm2 gameplay. PHASE B CLOSED (user-directed): capture gate met with sha256-identical static-vs-module captures; F3 landed — SDL3 Windows/Linux clients shed the static renderer entirely (GL-link-free client, `gl` default loads the module, fail-closed FatalError when missing; macOS/legacy/ded keep static); B7 landed — Windows ded drops opengl32 via gated GLEW + stub_gl_win.cpp (Linux ded was already GL-free); bake-info ABI hazard closed with a POD signature (ABI v5, vtable-change batch mirrored to openQ4-game). See the closure record in the B8 section.

Parent plan: [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md). This staging plan was derived from a five-way symbol-level audit of engine/renderer coupling; file:line anchors reflect the tree at the audit commit (8bcdcdbf) and shift as stages land.

---

## 1. Stage sequence (each leaves main green: full build both targets + validation matrix + macOS token sweep)

### B1 — Interface hygiene (engine call sites → public API; no build-system change)
Static linking preserved throughout. Pure call-site conversions.

| Change | Files |
|---|---|
| Promote `DrawStretchPic(idDrawVert*, glIndex_t*, int, int, const idMaterial*, bool clip, min/max)` to a pure virtual on `idRenderSystem` (un-comment RenderSystem.h:310, implement in idRenderSystemLocal); convert `tr.DrawStretchPic` calls | src/ui/DeviceContext.cpp:916,1065; src/renderer/RenderSystem.h; RenderSystem.cpp |
| Move font-atlas DXT self-test (idImage::Bind/GetOpts/idImageOpts use) renderer-side behind new virtual `idRenderSystem::VerifyFontAtlasImage(const idMaterial*)` returning pass/fail+summary | src/ui/DeviceContext.cpp:1990-1997 |
| Drop vestigial internal includes | framework/DeclManager.cpp:33 (tr_local.h), ui/RenderWindow.cpp:33 (tr_local.h → glconfig read only), ui/MarkerWindow.cpp:33+40 (Image.h, unused), renderer/RenderSystem_init.cpp:54 (ui/DeviceContext.h, unused) |
| `com_productionMode.GetInteger()` → `cvarSystem->GetCVarInteger("com_productionMode")` | src/renderer/Image_load.cpp:432 |
| New virtual `idRenderSystem::SetLoadingScreenSwapIntervalBypass(bool)` replacing free-fn call | framework/Session.cpp:6152; RenderSystem_init.cpp |
| Route `GLimp_PreserveWindowOnShutdown`/`GLimp_Shutdown` callers off renderer decls: fwd-decl via a sys-owned header (`sys_public.h`), not tr_local.h | framework/Common.cpp:129,3581,3583; sys/win32/win_main.cpp:909 |

Verify: Windows client+ded build, boot, main menu, GUI rendering (font atlas visible), demo smoke.

### B2 — Shared image-utility library + Session compositing
Create static lib **`imagetools`** (linked by engine AND, later, the module): `Image_files.cpp` (R_LoadImage/R_WriteTGA + format loaders), `Image_process.cpp` (R_ResampleTexture etc.), `DXT/*`, `jpeg-6/*`, `Color/ColorSpace.cpp`, plus `R_StaticAlloc/R_StaticFree` relocated out of tr_trisurf.cpp into it (counter hook optional-null; today they update `tr.pc` — parameterize).
- Audit `Image_files.cpp` for `globalImages`/`tr` refs and sever (parameterize or move offending functions to Image_load.cpp which stays module-side).
- Consumers stop including renderer/Image.h internals: framework/Session.cpp:1530-1871, framework/DeclMatType.cpp:95/112, ui/GameBustOutWindow.cpp:1003 → new `src/imagetools/ImageTools.h`.
- `globalImages->ImageFromFile` at Session.cpp:1908 → new virtual `idRenderSystem::PreloadImage(const char* name)` (or reuse existing FindMaterial precache path).
- meson: new `static_library('imagetools', ...)` linked into engine; remove those TUs from the renderer glob only in B8.

Verify: build; splash/menu background compositing renders; `.hit` matType maps generate; TGA screenshot write.

### B3 — Feature relocation behind interfaces
1. **bakeLightGrids** → move Session.cpp:2272-2694 body into the renderer. New virtuals:
   - `idRenderSystem::BakeCurrentLightGrids(const lightGridBakeOptions_t&, textBuffer* report)` — `lightGridBakeOptions_t` becomes a public POD in RenderSystem.h.
   - `idRenderWorld::LightGridPackMatchesBakeOptions(...) / SetupLightGridForBake(...)` as needed; Session keeps only the command/UI shell. All `tr.primaryWorld`, `idRenderWorldLocal::portalAreas[].lightGrid.*`, `R_*LightGrid*` refs leave Session.cpp.
2. **DECL_MATERIAL allocation**: replace `idDeclAllocator<idMaterial>` at DeclManager.cpp:1352 with an engine-side trampoline `static idDecl* MaterialDeclAllocator() { return renderSystem->AllocMaterialDecl(); }` + new virtual `idRenderSystem::AllocMaterialDecl()`. Allocation only happens on FindMaterial/parse, which post-dates renderer boot (module loads "before platform window creation" per RendererModule.h:57-59), so registration-at-declManager-Init stays put; only the `new` crosses via virtual.
3. `tr.primaryWorld/primaryView` residual reads → new virtuals `idRenderSystem::GetPrimaryRenderWorld()` / `GetPrimaryRenderView()` if anything survives (2).

Verify: bake a lightgrid on a test map, byte-compare pack output vs pre-change; load q4dm map; material hot-reload.

### B4 — renderImport/renderExport completion (RENDER_API_VERSION → 2)
Renderer-side conversions; still statically linked, engine binds pointers to its own statically-linked objects so behavior is identical.

**renderImport_t additions** (RenderModuleAPI.h):
```c
idSession *                sessionInterface;   // demo IO, pacifier, sw/rw, IsMultiplayer
idUserInterfaceManager *   uiManager;
idCollisionModelManager *  collisionModelManager;
rvBSEManager *             bse;
```
`idSession` crosses as-is (virtuals + public data members `readDemo/writeDemo/renderdemoVersion/rw/sw`) — same-compiler ABI, identical to the game-DLL convention; no callback-interface invention needed. Resolves the biggest renderer→engine blocker mechanically: RenderWorld_demo.cpp (~80 refs), RenderSystem.cpp:1250-1517, ModelManager.cpp:309/738/741, ImageManager.cpp:994, RenderSystem_init.cpp:1980/2267/3248/3337/3870/3955/4239-4246, Material.cpp:885, GuiModel.cpp:177, Model_md5.cpp:902-924 all switch from the `session` global to the imported pointer (module-side `static idSession* session` re-bound at GetRenderAPI).

**renderModuleServices_t additions** (Sys_* shims — see §4).

**renderExport_t addition**: `idRenderModelManager* renderModelManager;` — loader publishes both `renderSystem` and `renderModelManager` into engine globals when the module path activates (fixes Common.cpp:5319 gameImport wiring).

**Symbol resolution — revised at implementation (no call-site sweep).** Renderer sources keep calling `Sys_Milliseconds`, `eventLoop->Milliseconds()`, `session->`, `bse->`, `uiManager->`, `collisionModelManager->`, and `RenderDoc_IsInjected` unchanged. Inside the module those names resolve exactly like they do in the game DLLs: the interface globals (`session`, `bse`, `uiManager`, `collisionModelManager`, `eventLoop`) become module-local variables bound from `renderImport_t` in `GetRenderAPI`, and the free functions (`Sys_Milliseconds`, `Sys_Sleep`, `Sys_EnterCriticalSection`, `Sys_LeaveCriticalSection`, `RenderDoc_IsInjected`) are defined by a small module-side forwarder TU over the services table, authored in B8 where the module link makes the required list explicit and linker-enforced. Worker-thread creation (`Sys_CreateThread` in the light-grid bake pool, with its thread-registry/priority/threadInfo_t signature) is also resolved by that B8 forwarder design rather than a premature simplified service. B4 landed the ABI (version 2), the loader import/publish wiring, and the engine-side service bindings.

Verify: build all targets; demo record+playback round-trip; BSE effect map; level load pacifier; MD5R model with collision extraction.

### B5 — Window-services seam + glConfig split (own session; highest design risk)
1. Add `renderWindowServices_t` to RenderModuleAPI.h (§4) implemented by sys/sdl3; engine owns window/display/mode/input, module owns GL context.
2. **Split glconfig_t**: new engine-owned `engineWindowState_t` (defined in a framework/sys header, instance in sys layer): `vidWidth, vidHeight, uiViewportX/Y/W/H, isFullscreen, displayHz`. All engine writers (sdl3_backend.cpp:3503-3572, 3655-3656, 4031/4230/5846; win_wndproc.cpp:274-275) and engine readers (Common.cpp:4811, Session.cpp:1654/1938, Session_menu.cpp:865, DeviceContext.cpp:325/1375, RenderWindow.cpp:82, linux/input.cpp) repoint to it. Module receives a `const engineWindowState_t*` in renderImport_t and mirrors into its glConfig each frame/resize. glConfig keeps context/caps fields (contextRequest, wgl_extensions_string, colorBits, extensions, tiers) module-side only.
3. **Partition sdl3_backend.cpp**: context half (SDL3_SetGLAttributesForCandidate:5479, SDL_GL_CreateContext:5696, MakeCurrent/DestroyContext, SDL3_EnsureGLContextCurrent:5514, GLimp_SwapBuffers:5853, SDL3_ApplySwapInterval:4054, GLimp_ExtensionPointer:5999, SDL3_LoadWGLExtensions:4077 + wgl* globals, GLimp_Activate/Deactivate/EnsureActiveContext:5964-5972) moves to new `src/renderer/OpenGL/gl_ContextSDL3.cpp`; window half stays. Two-phase handshake: module supplies `framebufferDesc` (from RendererContextLadder_Build — already renderer code) → engine sets SDL attrs + creates window → returns populated `renderModuleWindowInfo_t` → module creates context. `win_qgl.cpp`, `win_gamma.cpp` GL parts move module-side (they are missing from LEGACY_WIN32_SOURCES today — fix the glob).
4. **Carve R_InitOpenGL** (RenderSystem_init.cpp:1615-1660): `Sys_InitInput/Sys_ShutdownInput/Sys_GrabMouseCursor/Sys_GetDesktopResolution/R_GetModeInfo` policy moves to the engine window layer (called around window creation via window-services); renderer half keeps GLEW init + context ladder. Move `R_RendererModule_Boot()` call from RenderSystem_init.cpp:1615 to engine init (framework, before window creation).
5. `SDL3_UpdateNativeWindowHandles` (4123): split — window handles engine-side; module reports context handle back via new export call, deleting the `win32.hGLRC` direct write (4127).
6. Engine refs to renderer cvars (r_swapInterval/r_multiSamples/r_glTier/r_glDriver/r_glDebugContext/r_fullscreenDesktop/r_logFile) and `R_GetEffectiveSwapInterval` in remaining engine-side sdl3 code → services CVar_* calls; swap-interval logic itself moves module-side with the context half.
7. SMP: `GLimp_SpawnRenderThread` — module requests thread creation via new `services->SpawnRenderThread(fn, name)`; context current-ness stays wholly module-side (wrapper moves with context half). BackEnd/FrontEndSleep/WakeBackEnd stay with the thread owner (engine services).
8. Retire or identically split legacy win_glimp.cpp / linux/glimp.cpp / macosx_glimp.mm (diagnostic-only per meson.build) — prefer retire-to-unbuilt; keep the m4/logfunc generators with the module.

Verify: vid_restart (both preserve-window and full), fullscreen toggle, multi-display, resize, mouse transform, SMP r_smp path, Linux/macOS CI (macos-debug.yml dispatch), macOS policy token sweep.

### B6 — dmap geometry library (own session)
Create static lib **`render_geo`** linked by engine AND module:
- From tr_trisurf.cpp: R_AllocStaticTriSurf(+Verts/Indexes/SilIndexes), R_FreeStaticTriSurf(+SilIndexes), R_CreateSilIndexes, R_RangeCheckIndexes, R_RemoveDegenerateTriangles, R_CleanupTriangles, R_DeriveTangents.
- tr_lightrun.cpp: R_DeriveLightData, R_FreeLightDefDerivedData, R_LightProjectionMatrix. tr_stencilshadow.cpp: R_CreateShadowVolume. Interaction.cpp: R_FreeInteractionCullInfo.
- Pre-req audit: sever `tr` global / r_* cvar refs in each (parameterize; e.g. tri-surf allocators' `tr.pc` counters become an optional hook, r_useShadow* cvars read via cvarSystem string API or passed in options struct).
- Struct defs dmap embeds by value (`idRenderLightLocal` dmap.h:181, `idRenderEntityLocal` shadowopt3.cpp:1248) move into the lib's public header `src/render_geo/RenderGeometry.h` (shared layout, both sides compile it).
- Redirect dmap.h:29 and shadowopt3.cpp:33 off `../../../renderer/tr_local.h` → RenderGeometry.h; do NOT add src/renderer to dmap include dirs (guard against re-coupling).
- **Delete** gldraw.cpp GL path (RB_SetGL2D + direct GL, gldraw.cpp:42-101, WIN32/`dmap -draw` debug-only) — stub Draw_ClearWindow unconditionally. Removes dmap's only backend symbol.
- Rejected: dmap-on-interfaces (would leak private geometry into idRenderSystem) and dmap-in-module (drags cm/gameEdit/fileSystem into the module).
- No work for editors/debugger/renderbump/roqvq/AAS builder: not in meson globs, gated by never-defined ID_ALLOW_TOOLS, AAS builder has no implementation.

Verify: dmap a stock map, binary-compare .proc/.cm output pre/post.

### B7 — Headless renderer for dedicated targets (own session; can parallel B6)
- New engine-linked `src/framework/RenderSystemNull.cpp`: null `idRenderSystem` (+ null idRenderWorld/idRenderModelManager as needed by framework/Session/ui code paths active under ID_DEDICATED). After B1-B5 no keep-side code touches `tr`/`glConfig`/`R_StaticAlloc` (R_StaticAlloc now in imagetools), so surface is just the virtuals.
- Windows ded: stop `openq4_dedicated_sources = openq4_engine_sources` (meson.build:956); ded = engine sources minus renderer globs plus RenderSystemNull; drop opengl32 from dedicated_deps.
- Linux ded: retire stub_gl.cpp GLimp/gl* nulling (meson_sources.py:114-125) — nothing links gl* anymore.
- Null renderer never loads render modules; material decls: null renderSystem's `AllocMaterialDecl()` returns a minimal idDecl-compatible stub OR ded keeps linking Material.cpp via renderer-core lib (decision point — prefer linking renderer-core static into ded for decl fidelity, GL-free after tr_local split).

Verify: ded server boots, loads map, client connects from a full build.

### B8 — Build partition + module flip (own session; final)

**F1+F2 LANDED — as-implemented record (2026-07-17).** The landed design is
simpler than the sketch below: no tr_local split and no renderer_core static
lib were needed. The engine build is UNCHANGED (still statically links the
renderer); the module is a parallel compilation of the same renderer sources.

- `meson_sources.py --emit renderer_gl` = renderer/*.cpp + renderer/OpenGL/*.cpp
  minus RendererModule.cpp (the loader stays engine-side).
- `renderer-gl_x64` shared_module: engine include dirs/args/PCH plus
  `-DOPENQ4_RENDERER_GL_MODULE -DOPENQ4_SDL3_CONTEXT_IMPL` (the seam TU
  compiles standalone via its preamble), links renderer_idlib (game_idlib
  sources compiled engine-flavor) + imagetools + render_geo + glew_dep
  (+opengl32 on Windows; GLEW's SDL3-loader mode resolves procs through
  OpenQ4_GlewGetProcAddress → window services, so the module links NO SDL).
  Gated by `build_renderer_gl` (off on macOS / non-SDL3 backends).
- `src/renderer/RendererGLModule.cpp` (guarded glue TU): engine-interface
  globals bound from renderImport_t, idLib::Init + RegisterStaticVars +
  idSIMD::InitProcessor (game-DLL idiom — missing idLib::Init was the first
  boot crash), Sys_* forwarders over services (Milliseconds/Sleep/critsect/
  RenderDoc/GetDesktopResolution), Sys_GetProcessorString via the
  sys_cpustring cvar, module-local QGL + wgl pointer definitions (seam TU
  standalone preamble), module-local bake worker-thread primitives
  (win32/pthread, module-local g_threads registry), engine-only diagnostics
  stubs (R_RendererModule_*/UI_FontParity), mirrors of engine cvar objects
  the renderer references (developer/com_purgeAll/com_makingBuild/
  com_SingleDeclFile/r_skipGlowOverlay), GetRenderAPI export.
- ABI v4: renderImport_t.console + renderWindowServices_t Init/Shutdown-
  Input/GrabMouseCursor (renderer init + vid_restart sequencing).
- Cross-DLL call fixes: idDemoFile::Read/WriteHashString virtual,
  idDeclSkin::RemapShaderBySkin virtual (MIRRORED to openQ4-game),
  idDeclManager::GetMaterialTypeArray virtual (MIRRORED; const char* — an
  idStr crossing the module ABI by value is freed on the wrong CRT heap,
  which was the map-load crash), idEventLoop::Milliseconds inlined,
  net_serverDedicated read via cvarSystem, lightgrid CPU count via
  platform API instead of SDL.
- F2 activation: `r_renderApi gl-module` (opt-in soak value; `gl` stays the
  static default). `R_RendererModule_BootEarly()` runs in InitGame AFTER
  AttachBSE and BEFORE declManager->Init() — every decl object must be
  allocated by the renderer instance that will draw it (materials allocated
  pre-publish carry the engine vtable and crash on the engine's never-
  initialized cinematic tables). It peeks the archived r_renderApi out of
  the config file (config exec happens later) and applies command-line
  overrides via StartupVariable. Module activation is restricted to the
  first boot: outside that window candidates are refused BEFORE loading
  (a probe-load would register module static cvars whose ArgCompletion
  pointers dangle after unload). Dedicated coerces to gl until B7.
- Verified: gl-module activates, negotiates GL 3.3 compat + MSAA 8 through
  the window services, loads mp/q4dm2 (267 entities), renders gameplay, and
  shuts down cleanly; static default regression-checked (foundation/tier/
  present matrix cases, SP gameplay smoke, ded boot, macOS sweep).
- Known boundary hazard (deferred with lightgrid-bake scope):
  GetCurrentLightGridBakeInfo writes idStr&/idList<int>& out-params across
  the boundary; resizing on the module side frees engine-heap buffers on
  the module heap in debug builds. Needs a POD signature before bake runs
  under gl-module.
- Still open for F3 (post-soak): engine sheds the static renderer, ded
  GL-free source unification, default flip gated on pixel-identical
  captures + user gameplay soak sign-off.

**PHASE B CLOSURE LANDED — as-implemented record (2026-07-17, user-directed).**

- **Capture gate MET**: `renderer_gameplay_benchmark --profile smoke` with
  launch cvars `g_stopTime=1 r_mode=-1 r_customWidth/Height=1280x720
  r_gamma/brightness=1 r_multiSamples=0 r_borderless=0` produces
  sha256-identical TGA captures for r_renderApi=gl (static) vs gl-module on
  SP storage1 (full lit visual stack, SMAA on). The one divergence found —
  borderless desktop-resize reaching only the engine's glConfig — was the
  known module resize gap, fixed below, not a rendering difference.
- **F3 client shed + default flip**: on SDL3 Windows/Linux clients
  (`renderer_module_only_client` in meson; OPENQ4_RENDERER_MODULE_ONLY)
  the client compiles NO renderer sources (meson_sources `--renderer
  module` keeps only the loader TU), links no GL/GLEW (glew becomes a
  partial_dependency; opengl32/libGL dropped; win_qgl dropped), and
  `r_renderApi gl` (default) loads renderer-gl_<arch> — missing module is
  a FatalError, there is no lower fallback. macOS/legacy backends and all
  ded targets keep the static renderer unchanged.
- **Cross-module completions for the shed**: idMaterial virtuals
  (GetImageWidth/Height, Cinematic*, SetImageClassifications, ReloadImages,
  GetPortalImageName, GetMaterialType(idVec2&), ResolveUse — MIRRORED),
  idRenderModel::SetBounds virtual (MIRRORED) replacing BSE's
  dynamic_cast member write, GetGLConfig() virtual (MIRRORED) replacing
  Session_menu's direct glConfig reads, POD GetCurrentLightGridBakeInfo
  (MIRRORED; closes the idStr&/idList& bake ABI hazard),
  RENDER_API_VERSION 5. Image_program.cpp + BitsForFormat relocated to
  imagetools (CPU image math both sides call). Loader cvars
  (r_renderApi/r_actualRenderApi) plus window/gui cvars referenced by kept
  engine TUs (r_borderless/r_fullscreenDesktop/r_windowWidth/
  r_windowHeight/r_skipGuiShaders) moved to RendererModule.cpp with glue
  mirrors module-side; loader commands (rendererModuleSelfTest,
  rendererVkProbe, uiFontParitySelfTest) register from the loader.
- **Module window-state polling**: the seam TU polls
  RefreshNativeWindowHandles each present (vid size + uiViewport rect —
  renderModuleWindowInfo_t v5 fields), replacing the engine-side glConfig
  mirror writes which are now compiled only into static-renderer shapes.
- **B7 Windows ded GL-free**: glew wglew halves gated behind
  !OPENQ4_GLEW_SDL3_LOADER (both token-pinned glew.c copies;
  linux_sdl3_glew_loader.py pins the gate), glew_dedicated builds on
  Windows, ded deps drop opengl32 (GLAPI=extern strips GLEW's dllimport
  decoration), win_qgl.cpp replaced by sys/stub/stub_gl_win.cpp (GL 1.1
  no-ops + null qwglGetProcAddress + QGL no-ops + GLEW hook). Linux ded
  was already GL-free (stub_gl.cpp).

Original sketch (superseded where it conflicts with the record above):
1. **tr_local.h split** (pre-req for the core/gl lib boundary): extract GL-bearing pieces (glState/backEnd GL members, qgl.h include, GLimp decls) into `tr_gl_local.h`; tr_local.h becomes API-agnostic. Guard `precompiled.h:372` qgl.h include to module builds only (`#ifdef RENDERER_MODULE_BUILD`); interface headers at :373-378 stay.
2. **meson_sources.py**: remove renderer globs (lines 67-71) from ENGINE_SOURCE_GLOBS; add `RENDERER_MODULE_GLOBS` + `--emit={engine,renderer}` (mirroring --include-game). Exclude `RendererModule.cpp` from module list, add to engine list; strip its tr_local.h include (RendererModule.cpp:4) to just RenderModuleAPI.h + sys decls.
3. **Module targets**: `renderer_core` static lib (API-agnostic set) + `shared_module('renderer-gl_'+binary_arch, ...)` mirroring renderer_vk (meson.build:1160-1209): name_prefix '', linux_renderer_module.map, hidden visibility, RENDER_MODULE_EXPORT on GetRenderAPI (VulkanModule.cpp:34-40 pattern), install_root_dir. Deps: glew_dep + opengl32/linux_gl_dep/OpenGL-framework move OFF engine deps[] onto the module; sdl3_dep on BOTH; imagetools + render_geo linked by both.
4. **Module idlib**: new `renderer_idlib` static lib — engine flavor (C++20, define `RENDERER_DLL` analogous to GAME_DLL; renderer code currently compiles under __DOOM_DLL__/C++20, so keep C++20, do not reuse the game's C++17 lib). Module PCH = precompiled.h with RENDERER_MODULE_BUILD (gets qgl.h, excludes game/Game.h + tools/* + AsyncNetwork via the same guard).
5. `-DID_GL_HARDLINK` moves from shared_cpp_args (meson.build:783-786) to module-only args (non-Windows).
6. **Flip**: RM_ExportCanRender (RendererModule.cpp:264) returns true for "gl"; loader publishes renderSystem+renderModelManager; `r_renderApi gl-static` (default initially) keeps the statically-linked path alive until soak completes, then default flips and static path is removed in a follow-up.
7. Optional: module VERSIONINFO via new .rc + compile_resources (pattern openQ4Version.rc, VFT_DLL); otherwise ships unversioned like game/vk modules.

Verify: full matrix — Windows client (module + static fallback), Windows ded, Linux client/ded, macOS, vid_restart, demo, dmap, arm64 validation loop, renderer parity screenshots.

---

### B5b implementation blueprint (refined 2026-07-16 after B5a, from a full read of the live file)

Constraints discovered on the live tree:
- `sdl3_backend.cpp` is not compiled directly: `win_sdl3.cpp` / `linux_sdl3.cpp` / `macosx_sdl3.cpp` `#include` it whole after defining `OPENQ4_SDL3_*_HOST`. The context half must therefore be a standalone renderer TU: `src/renderer/OpenGL/gl_ContextSDL3.cpp`, guarded by a new `OPENQ4_SDL3_BACKEND` define added to engine args when `platform_backend=sdl3`, deriving its host from standard `_WIN32/__linux__/__APPLE__` macros. Legacy/native builds compile the guard file empty and keep their own GLimp_* (win_glimp.cpp etc.).
- `QGL_Init/QGL_Shutdown` are declared locally in the backend (line 344) and defined in win_qgl.cpp (Windows) — the context TU re-declares them; win_qgl moves module-side at B8 as planned.
- `Sys_GetRenderWindowServices()` (declared in RenderModuleAPI.h, engine-implemented) returns the services table; sdl3_backend implements it, and win_glimp.cpp / linux/glimp.cpp / macosx_glimp.mm / stub_gl.cpp each provide a NULL-returning fallback so every build config defines it exactly once. `RM_BuildImport` wires it into `renderImport_t.windowServices` (RENDER_API_VERSION 3).

Services shape (ABI v3; the context half is the only caller pre-B8):
```c
typedef struct renderFramebufferDesc_s {
    int  redBits, greenBits, blueBits, alphaBits, depthBits, stencilBits;
    bool doubleBuffer, stereo;
    int  multiSamples;            // >1 enables MSAA buffers
    bool explicitGLVersion;       // else unversioned request
    int  glMajor, glMinor;
    bool glCoreProfile;           // else compatibility
    bool glDebugContext;
} renderFramebufferDesc_t;

typedef struct renderWindowParms_s {   // ABI-neutral glimpParms_t mirror
    int width, height; bool fullScreen, borderless, hiddenWindow, stereo;
    int displayHz, multiSamples;
} renderWindowParms_t;

typedef struct renderWindowServices_s {
    bool (*PrepareWindowSystem)( void );                    // GLimp_Init 5600-5632: hints, video-subsystem ref, lifecycle watch, driver summaries, diagnostic cmds, display list, InitDesktopMode
    bool (*CreateWindowForFramebuffer)( const renderFramebufferDesc_t *, const renderWindowParms_t *, renderModuleWindowInfo_t *outInfo, bool *outReusedPreservedWindow );
        // maps desc -> SDL_GL_SetAttribute stream byte-identically to the old
        // SDL3_SetGLAttributesForCandidate (5493-5521, incl. SDL_GL_ResetAttributes),
        // then SDL_CreateWindow with the 5647-5650 flags or preserved-window reuse
        // (5652-5655), then initial windowed placement (5684-5707)
    void (*DestroyAttemptWindow)( void );                   // failed-candidate teardown 5725-5728 (only when the attempt created the window; caller holds the reused flag)
    bool (*ApplyScreenParms)( const renderWindowParms_t * );// SDL3_ApplyScreenParms
    void (*RefreshNativeWindowHandles)( renderModuleWindowInfo_t * ); // hWnd/hDC half of SDL3_UpdateNativeWindowHandles; the hGLRC reverse write (POSIX 4127) is deleted
    void (*NotifyWindowReady)( void );                      // 5782-5783 activeApp/focus flags
    void (*BeginWindowTeardown)( void );                    // GLimp_Shutdown 5818-5829: aspect snap, mouse, controllers, fullscreen restore (preserve-aware), text input
    void (*FinishWindowTeardown)( void );                   // 5839-5863: window destroy, video unref/lifecycle unwatch, hWnd/hDC clears, fullscreen state, input queues — all preserve-aware via the engine-side s_preserveWindowOnShutdown flag
    void (*GetDesktopResolution)( int *w, int *h );
} renderWindowServices_t;
```

Context TU contents (verbatim moves unless noted): GLimp_EnableLogging(350), SDL3_ApplySwapInterval(4054, keeps R_GetEffectiveSwapInterval), SDL3_LoadWGLExtensions(4077; wgl* globals stay in win_qgl until B8), GLimp_SetGamma/UseNativeGammaRamps(5406/5412 no-ops), SDL3_MoveCompatibilityFallbacksToFront/BuildGLContextCandidates/NormalizeMSAASampleFallback/BuildMSAASampleFallbacks(5402-5491), desc builder replacing SDL3_SetGLAttributesForCandidate's candidate->values mapping, SDL3_RecordGLContextCandidate(5523, glConfig.contextRequest), SDL3_EnsureGLContextCurrent(5528, s_sdlWindow/s_sdlContext -> ctx-local s_glWindow/s_glContext cached from window info), SDL3_GLProfileMaskName/LogGLContextAttributes(5546-5590), GLimp_Init (rebuilt: PrepareWindowSystem -> candidate x MSAA double loop calling CreateWindowForFramebuffer / SDL_GL_CreateContext / MakeCurrent / DestroyAttemptWindow per 5668-5733 semantics -> r_multiSamples writeback -> QGL_Init -> ApplyScreenParms -> RefreshNativeWindowHandles -> LoadWGLExtensions -> swap interval -> NotifyWindowReady), GLimp_SetScreenParms (5790-5812 with services ApplyScreenParms/RefreshNativeWindowHandles), GLimp_Shutdown (BeginWindowTeardown -> context destroy 5831-5837 -> QGL_Shutdown -> FinishWindowTeardown; note hGLRC clear becomes ctx-local), GLimp_SwapBuffers(5867), the SMP block 5886-5976 (dead code; keep symbols, win32.* event fields via TODO(B8) services), GLimp_Activate/Ensure/DeactivateContext(5978-5995), OpenQ4_GlewGetProcAddress(6000, Linux), GLimp_ExtensionPointer(6013).

Residual renderer->sys global touches allowed pre-B8 with TODO(B8) markers: win32.wglErrors++ (EnsureCurrent/Deactivate), the SMP win32 event fields, win32.hGLRC ownership. Verify list unchanged from B5b step 12 (vid_restart full+partial+windowed-force, fullscreen toggle, preserve-window restart via ReloadGameModule, multi-display, matrix, gameplay smoke, WSL, macOS sweep).

## 2. Blocker → resolution index

| # | Blocker (audit anchor) | Resolution | Stage |
|---|---|---|---|
| 1 | `tr.DrawStretchPic` vert/index overload (DeviceContext.cpp:916,1065) | Promote to idRenderSystem virtual | B1 |
| 2 | idImage::Bind/GetOpts self-test (DeviceContext.cpp:1990) | `VerifyFontAtlasImage` virtual, test moves renderer-side | B1 |
| 3 | R_LoadImage/Resample/WriteTGA/StaticAlloc in Session/DeclMatType/GameBustOut | `imagetools` static lib, linked both sides | B2 |
| 4 | `globalImages->ImageFromFile` (Session.cpp:1908) | `PreloadImage` virtual | B2 |
| 5 | bakeLightGrids reaches idRenderWorldLocal + R_*LightGrid* (Session.cpp:2272-2694) | Feature moves renderer-side behind `BakeCurrentLightGrids` | B3 |
| 6 | `idDeclAllocator<idMaterial>` (DeclManager.cpp:1352) | Engine trampoline → `AllocMaterialDecl()` virtual | B3 |
| 7 | R_SetLoadingScreenSwapIntervalBypass (Session.cpp:6152) | idRenderSystem virtual | B1 |
| 8 | `session` global used pervasively (RenderWorld_demo etc.) | `idSession*` in renderImport_t (game-DLL data-member ABI precedent) | B4 |
| 9 | `bse` global, bidirectional effects (tr_light.cpp:2593) | `rvBSEManager*` in import; rvBSE* stays opaque | B4 |
| 10 | uiManager / collisionModelManager / eventLoop not in import | Add first two to import; eventLoop calls → services->Milliseconds | B4 |
| 11 | renderModelManager not in export (Common.cpp:5319) | Add to renderExport_t; loader publishes | B4 |
| 12 | Sys_Milliseconds ×100+, Sys threading/critsect (lightgrid pool, GLDebugScope) | services table additions (§4); bake pool stays module-side using service threads | B4 |
| 13 | Sys_InitInput/GrabMouse/GetDesktopResolution/R_GetModeInfo inside R_InitOpenGL | Carve out engine-side, window-services handshake | B5 |
| 14 | glConfig written by engine window layer (sdl3:3503+, win_wndproc:274) | Split: engine `engineWindowState_t` vs module glConfig caps | B5 |
| 15 | GLimp_* inverted ownership; window/context API-ordering coupling (SDL attr-before-window, WGL SetPixelFormat, GLX visual) | Two-phase framebufferDesc handshake in window-services | B5 |
| 16 | renderModuleWindowInfo_t never populated; win32.hGLRC reverse write | Engine populates on window create; module reports context handle via export call | B5 |
| 17 | Engine links renderer cvars/fns (r_swapInterval, R_GetEffectiveSwapInterval, ladder) | Logic moves module-side; residual engine reads via services CVar_* | B5 |
| 18 | SMP thread created engine-side, context module-side | services->SpawnRenderThread; context ops all module-side | B5 |
| 19 | dmap links ~15 renderer internals + embeds idRenderLightLocal/idRenderEntityLocal by value | `render_geo` static lib + shared RenderGeometry.h; sever tr/cvar refs first | B6 |
| 20 | gldraw.cpp RB_SetGL2D backend ref | Delete the `dmap -draw` GL path | B6 |
| 21 | Dedicated targets statically link full renderer (stub_gl nulling) | RenderSystemNull + ded source-list split; retire stub_gl | B7 |
| 22 | precompiled.h force-includes qgl.h/glew engine-wide; module can't compile game/Game.h+tools | RENDERER_MODULE_BUILD-guarded PCH | B8 |
| 23 | Renderer globs fused into engine; loader inside the glob; boot call inside renderer | meson_sources partition; RendererModule.cpp → engine list; boot call → framework | B8, B5(boot) |
| 24 | idlib flavor/ABI for module undefined | renderer_idlib: C++20 + RENDERER_DLL | B8 |
| 25 | ID_GL_HARDLINK engine-wide | Module-only define | B8 |
| 26 | RenderDoc_IsInjected, win_local.h include | services->IsRenderDocInjected; win_local.h moves with context half | B4/B5 |
| 27 | AsyncNetwork.cpp:349-356 ShutdownOpenGL from async thread | Interface-clean; add thread-safety note to module Shutdown contract; verify at B8 flip | B8 |
| 28 | BSE includes tr_local.h/Model_local.h (BSE_Segment.cpp:21 etc.) | BSE stays engine-side; repoint at split tr_local.h API-agnostic half (B8.1); if it needs GL half, escalate to its own seam task | B8 |

---

## 3. Disposition table — all of src/renderer

**engine (stays in executables)**
- RendererModule.cpp/.h (loader; decoupled from tr_local.h), RenderModuleAPI.h (shared)
- Public interface headers, compiled both sides via PCH: RenderSystem.h, RenderWorld.h, Material.h, Model.h, ModelManager.h, Cinematic.h
- New: RenderSystemNull.cpp (B7, lives in framework/)

**shared static libs (linked by engine AND module)**
- `imagetools` (B2): Image_files.cpp, Image_process.cpp, Color/ColorSpace.cpp, DXT/DXTDecoder.cpp, DXTEncoder.cpp, jpeg-6/*.c (+ R_StaticAlloc/Free relocated)
- `render_geo` (B6): CPU extracts of tr_trisurf.cpp, tr_lightrun.cpp, tr_stencilshadow.cpp, Interaction.cpp + RenderGeometry.h (idRenderLightLocal/idRenderEntityLocal defs)

**renderer-core (API-agnostic; static lib inside the module, reusable by renderer-vk later; nominal until tr_local.h split in B8.1)**
- Models: Model.cpp, Model_ase/beam/liquid/lwo/ma/md3/md5/md5r/prt/sprite.cpp, Model_local.h, ModelManager.cpp, ModelDecal.cpp, ModelOverlay.cpp
- Frontend: tr_main.cpp, tr_light.cpp, tr_deform.cpp, tr_polytope.cpp, tr_orderIndexes.cpp, tr_shadowbounds.cpp, tr_turboshadow.cpp, tr_subview.cpp, tr_trace.cpp, tr_font.cpp, tr_guisurf.cpp, remainder of tr_trisurf/tr_lightrun/tr_stencilshadow/Interaction after B6 extraction
- World: RenderEntity.cpp, RenderWorld.cpp, RenderWorld_load.cpp, RenderWorld_demo.cpp, RenderWorld_local.h, ScenePackets.cpp/.h
- Materials/decl: Material.cpp, MaterialResourceTable.cpp/.h
- Images (CPU): BinaryImage.cpp/.h/BinaryImageData.h, Image_program.cpp, ImageOpts.h
- Shadow/graph: ShadowMapClassification.cpp/.h, ShadowMapProjected.cpp/.h, ShadowMapArb2Parity.h, RenderGraph.cpp/.h
- Misc: Cinematic.cpp, GuiModel.cpp/.h (GL-lean; verify at split), simplex.h, RendererBenchmarks.cpp/.h, RendererStartupDiagnostics.cpp/.h

**renderer-gl (module-only)**
- Backend: tr_backend.cpp, tr_render.cpp, tr_rendertools.cpp, draw_arb2.cpp, draw_common.cpp, draw_exp_stub.cpp, cg_explicit.cpp/.h
- System: RenderSystem.cpp, RenderSystem_init.cpp, RendererCaps.cpp/.h, RendererMetrics.cpp/.h, RendererUpload.cpp/.h, RendererBootstrap.cpp/.h, GLStateCache.cpp/.h, GLDebugScope.cpp/.h, VertexCache.cpp/.h, GeometryResources.cpp/.h, RenderGraphResources.cpp/.h, RenderTexture.h
- Images (GPU): Image.h, Image_load.cpp, Image_intrinsic.cpp, ImageManager.cpp, OpenGL/gl_Image.cpp, OpenGL/gl_RenderTexture.cpp
- World (GL-touching): RenderWorld_lightgrid.cpp, RenderWorld_portals.cpp
- Modern path: ModernClusteredLighting, ModernGLDrawPlan, ModernGLExecutor, ModernGLShaderLibrary, ModernGLSubmitPlan, ModernShadowPlanner (.cpp/.h)
- GL headers/glue: qgl.h, qgl_linked.h, glext.h, wglext.h, smaa/, tr_local.h GL half (tr_gl_local.h post-split)
- Relocated from sys (B5): gl_ContextSDL3.cpp (context half of sdl3_backend), win_qgl.cpp GL loader, win_gamma.cpp GL parts, glimp generators

**Vulkan/** — already its own module (renderer-vk); untouched.

---

## 4. New boundary surfaces (exact)

**renderModuleServices_t additions (v2):**
```c
// threading (lightgrid bake pool, GLDebugScope, SMP)
uintptr_t (*CreateThread)( void (*fn)(void*), void *parm, const char *name );
void      (*DestroyThread)( uintptr_t handle );
void      (*Sleep)( int msec );
bool      (*IsCurrentThreadStopRequested)( void );
void      (*EnterCriticalSection)( int index );
void      (*LeaveCriticalSection)( int index );
// SMP render thread (engine owns thread, module owns context current-ness)
bool      (*SpawnRenderThread)( void (*fn)(void) );
// misc
bool      (*IsRenderDocInjected)( void );
const char *(*GetProcessorString)( void );
```

**renderWindowServices_t (new, in renderImport_t):**
```c
typedef struct renderFramebufferDesc_s {
    int red, green, blue, alpha, depth, stencil;
    int multiSamples;
    bool stereo;
    int glMajor, glMinor;               // 0 = no GL (vulkan module)
    int glProfileFlags, glContextFlags; // core/compat/debug
} renderFramebufferDesc_t;

typedef struct renderWindowServices_s {
    // two-phase create: attrs set BEFORE SDL_CreateWindow / SetPixelFormat / XCreateWindow
    bool (*CreateWindowForFramebuffer)( const renderFramebufferDesc_t *desc,
                                        const glimpParms_t *parms,        // width/height/fullscreen/displayHz
                                        renderModuleWindowInfo_t *out );
    void (*DestroyWindow)( bool preserveForRestart );
    bool (*SetScreenParms)( const glimpParms_t *parms, renderModuleWindowInfo_t *out );
    void (*GetDesktopResolution)( int *w, int *h );
    bool (*SetGamma)( unsigned short r[256], unsigned short g[256], unsigned short b[256] );
    const engineWindowState_t *windowState;   // engine-owned vid/viewport/fullscreen block
} renderWindowServices_t;
```
Module keeps: context create/destroy/make-current, swap buffers, swap interval, extension-proc lookup (all against `renderModuleWindowInfo_t.sdlWindow`/native handles). Module reports context handle back via new export `void (*GetNativeContextHandle)(void**)` (replaces win32.hGLRC write).

**renderImport_t additions:** `idSession *sessionInterface; idUserInterfaceManager *uiManager; idCollisionModelManager *collisionModelManager; rvBSEManager *bse; const renderWindowServices_t *windowServices;`

**renderExport_t additions:** `idRenderModelManager *renderModelManager; void (*GetNativeContextHandle)(void **);`

**New idRenderSystem virtuals:** `DrawStretchPic(idDrawVert*, glIndex_t*, int, int, const idMaterial*, bool, float min[2], float max[2])`; `AllocMaterialDecl()`; `PreloadImage(const char*)`; `SetLoadingScreenSwapIntervalBypass(bool)`; `BakeCurrentLightGrids(const lightGridBakeOptions_t&)`; `VerifyFontAtlasImage(const idMaterial*, char*, int)`; (`GetPrimaryRenderWorld()` if B3 leaves residual need).

**engineWindowState_t (engine-owned, replaces glConfig window fields):** `vidWidth, vidHeight, uiViewportX, uiViewportY, uiViewportWidth, uiViewportHeight, isFullscreen, displayHz`.

---

## 5. Session scoping and risk

**Current session (in order):**
- **B1** — fully landable now. Low risk; each item independently revertible. Commit per item.
- **B2** — landable this session if Image_files.cpp `tr`/`globalImages` audit comes back clean; otherwise land the Session/DeclMatType/GameBustOut call-site prep and defer the lib carve.
- **B3** — start: material-decl trampoline (small, testable) and swap-bypass are same-session; bakeLightGrids relocation is a large code move — begin only if B1/B2 verify clean, else next session.

**Own sessions:**
- **B4** (import completion + Sys sweep): mechanical but wide (~150 call sites); one session. Risk: demo-file timing semantics (eventLoop vs Sys ms) — verify with demo round-trip; async-thread ShutdownOpenGL noted for B8.
- **B5** (window seam): highest design risk — vid_restart/fullscreen/multi-display/SMP regressions, three platforms. Needs the macOS policy sweep and arm64 loop. One dedicated session minimum, likely two (SDL3 split, then legacy glimp retirement).
- **B6** (dmap): risk concentrated in the tr/cvar severing audit of render_geo functions; verify by binary-comparing dmap output. One session.
- **B7** (ded null renderer): moderate; enumerate which idRenderSystem virtuals ded actually exercises before writing stubs. One session; can run parallel to B6.
- **B8** (partition + flip): depends on all prior; tr_local.h split is the long pole. Land partition with `r_renderApi gl-static` default, soak, then flip default in a follow-up commit. One to two sessions.

**Standing constraints:** never `git add -A` (user works in parallel); commit directly to main per stage only after its verification passes; Windows builds need vcvars64 (VS 18 Insiders); run macOS token sweep after any B5/B8 edits touching macOS-facing files.