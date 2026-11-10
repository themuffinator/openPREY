# Vulkan Phase C — clear + present (staging plan)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: C1-C4 LANDED (2026-07-18) — r_renderApi vulkan boots the real game
loop to the animated clear on NVIDIA RTX 4060 (Vulkan 1.4.325); swapchain
resize/recreation live; vulkan->gl module-break fallback drill green. C5
(vk matrix cases + validation-layer signatures in the matrix runner) is the
remaining stage before Phase D.
Parent roadmap: [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md) Phase C.
Prereq: Phase B closed — the renderer-module seam hosts full renderers; the
SDL3 Windows/Linux clients are module-only ('gl' loads renderer-gl_<arch>).

## Goal

`r_renderApi vulkan` boots the real game loop — menu, map load, SP gameplay —
to an animated clear at correct resolution/vsync/fullscreen across mode
changes. The renderer-vk module becomes a full module (real idRenderSystem)
by compiling the SHARED renderer front-end (exactly like renderer-gl) with
the GL backend replaced by a minimal Vulkan backend.

## Recon ground truth (agents: frontend-split / vk-minimal / vk-build)

- Of the 73 renderer TUs: 40 are pure front-end (reusable unchanged), 15 are
  GL-backend (excluded from the vk module), 13 are mixed (front-end logic
  with embedded GL call sites; linked via GL stubs in Phase C, split behind
  backend interfaces in Phase D+). The classification with per-file GL call
  sites is recorded in the recon transcript (phase-c workflow).
- Backend command chain: BeginFrame emits RC_SET_BUFFER, EndFrame emits
  RC_SWAP_BUFFERS then synchronously calls RB_ExecuteBackEndCommands.
  A VK clear backend must handle RC_SET_BUFFER (clear-color choice) and
  RC_SWAP_BUFFERS (acquire → dynamic-rendering clear pass → submit →
  present) and accept-and-skip RC_DRAW_VIEW (arrives every frame from
  FlushGui) and RC_COPY_RENDER (arrives at first map wipe; the GL impl
  dereferences image->CopyFramebuffer — must not fall through).
- Window services need a Vulkan extension (ABI v6):
  1. window kind in renderFramebufferDesc_t so the engine creates the SDL
     window with SDL_WINDOW_VULKAN and skips the SDL_GL_* attribute plumbing
  2. CreateVulkanSurface(VkInstance, VkSurfaceKHR*) wrapping
     SDL_Vulkan_CreateSurface
  3. GetVulkanInstanceExtensions wrapping SDL_Vulkan_GetInstanceExtensions
  (Windows could ride the HWND via VK_KHR_win32_surface, but POSIX window
  info carries no native handles by design — the SDL-mediated callbacks are
  the portable shape, mirroring the GL context primitives.)
- VulkanBringup has instance/device/VMA/timeline probing but everything is
  probe-scoped; Phase C adds a persistent device context, surface+swapchain
  (create/recreate on OUT_OF_DATE/resize; r_swapInterval → FIFO/MAILBOX/
  IMMEDIATE), N frames-in-flight sync, debug messenger, and the frame loop.
- Minimal idRenderSystem surface that must genuinely work (the shared
  front-end provides nearly all of it): Init, InitOpenGL (device bring-up
  entry), Shutdown/ShutdownOpenGL, IsOpenGLRunning, IsFullScreen,
  GetScreenWidth/Height, GetVideoRestartCount, AllocRenderWorld/Free,
  BeginLevelLoad/EndLevelLoad, AllocMaterialDecl, RegisterFont,
  SetColor*/DrawStretchPic*/FlushGui, SetFrameShaderTime, BeginFrame/
  EndFrame, GetGLConfig, Get/SetUseUIViewportFor2D.
- Build shape: meson_sources `--emit renderer_vk` = renderer_gl set minus
  OpenGL/* minus the 15 GL-backend TUs plus renderer/Vulkan/* + volk;
  engine-flavor args + PCH + renderer_idlib/imagetools/render_geo (hoist
  renderer_idlib out of the build_renderer_gl guard); module define
  OPENQ4_RENDERER_VK_MODULE. RendererGLModule.cpp generalizes into a shared
  glue (OPENQ4_RENDERER_MODULE + backend-name define) — it is ~90%
  backend-agnostic; the QGL section and backendName strings are the GL tail.
- Mixed-TU linking in Phase C: a module-local vk_GLStubs TU satisfies the
  GL references of the 13 mixed TUs (they never execute in the clear
  milestone); the excluded backend TUs are replaced by vk equivalents that
  provide the symbols the front-end actually calls (RB_ExecuteBackEndCommands
  and friends — enumerated by link cycles, the proven F1 method).
- Validation: new matrix cases pin the loader tokens
  (`Renderer API: requested=vulkan active=vulkan disposition=module`),
  rendererVkSwapchainSelfTest with ["passed","skipped"] alternatives for
  driverless hosts; Vulkan validation-layer error signatures join
  WARNING_PATTERNS so warnings=0 is meaningful; deliberate module-break
  drill pins the fallback ladder tokens.

## Stages

C1. ABI v6 window services (engine + seam): window-kind flag,
    CreateVulkanSurface, GetVulkanInstanceExtensions; SDL3 backend impls;
    version history note. Engine-only change, GL path unaffected.
C2. Glue generalization: split RendererGLModule.cpp into shared module glue
    + per-backend tails (gl keeps QGL; vk supplies volk/device bootstrap).
C3. meson: --emit renderer_vk + GL-backend exclusion list; renderer_idlib
    hoist; renderer-vk full-module target (engine flavor); keep the Phase A
    probe module semantics for `rendererVkProbe` (loads on demand).
C4. VK backend bring-up: persistent VulkanDevice (instance/surface/device/
    queues/VMA/swapchain/frames-in-flight), vk_Backend.cpp implementing the
    command-chain executor (clear+present, skip draws), vk GLimp_* context
    entry points driving the services, GL stubs TU.
C5. Self-tests + matrix cases + validation-layer signatures; deliberate
    module-break drill; A/B mode-change coverage (windowed/borderless/
    fullscreen, vsync 0/1, resolution changes via vid_restart).

Exit: animated clear at correct resolution across mode changes on Windows +
Linux; fallback ladder proven by the break drill; matrix + sweeps green;
GL default behavior byte-identical (it shares no code path with the vk
module beyond the seam).
