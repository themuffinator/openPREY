# Vulkan Phase D — images, vertex cache, 2D/GUI parity (staging plan)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: D1-D5 LANDED (2026-07-18). Main menu renders through the
renderer-vk module on RTX 4060 (Vulkan 1.4.325), validation-clean with
r_vkValidation 1 (samplerAnisotropy device feature enabled to match the
sampler cache). As implemented vs. staged below:
- D2 collapsed to nothing: with ARBVertexBufferObjectAvailable false the
  vertex cache runs virtualMemory=true automatically, so Position()
  returns CPU pointers and the executor copies straight into per-frame
  host-visible vertex/index rings — no VMA buffer table needed at menu
  scope (revisit for world geometry in Phase E).
- D4 shipped as a COMMITTED generated header (gui_shaders_spv.h via
  tools/build/spirv_to_header.py) + tools/tests/vk_shader_header_pin.py
  drift pin that regenerates+compares only when glslangValidator exists;
  no meson custom_target (CI runners have no Vulkan SDK, builds never
  invoke glslang).
- D5 shipped per plan: vulkanValidation + vulkanCallFailed
  WARNING_PATTERNS, renderer-vk-clear-startup + renderer-vk-fallback-drill
  cases (gated on a Windows host with the module staged), hideVkModule +
  preservesConfig levers in run_case (command-line +set cvars archive on
  exit; the config snapshot keeps vk cases from leaking r_renderApi into
  later cases or the user's config). The loader now reports
  disposition=fallback when a module loads for an API other than the one
  requested (RM_TryLoadModuleApi previously always said "module").

Milestone debugging record (the smokes that "passed" were lying):
- Early vk runs exited cleanly (code 0) right after "Vulkan renderer
  initialized" and the log's last line was idRenderSystem::Shutdown() —
  which is exactly what a clean quit looks like, so it read as the user
  closing the window. It was actually idCommonLocal::FatalError:
  FatalError logs NOTHING before calling Shutdown() (which closes the
  log), then hands the text to Sys_Error, which is invisible on windowed
  Windows builds; a recursive error during that Shutdown exits through
  Sys_Quit() with code 0. Fixed for good: FatalError now Printf()s the
  message before Shutdown.
- The fatal itself: SetBackEndRenderer found no usable back end because
  glConfig.allowARB2Path is only ever set in draw_arb2.cpp — a GL TU the
  vk module excludes. It only fires when an archived config marks
  r_renderer modified, which is why config-less Phase C bring-up runs
  never hit it. VK_FillGLConfigFromDevice now sets allowARB2Path (the
  ARB2-shaped front-end path IS what the vk backend consumes).
- Next crash: R_FrameAlloc on NULL frameData in the first BeginFrame —
  vertexCache.Init, SetBackEndRenderer, R_InitFrameData, and
  R_SetColorMappings all live in the GL-only R_InitOpenGL tail. The vk
  InitOpenGL seam now mirrors that tail before ReloadImages.
- Diagnostics kept: SDL_EVENT_QUIT arrival prints and one-shot GUI
  executor begin-frame failure prints.
Parent: [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md) Phase D;
Phase C context: [2026-07-17-vulkan-phase-c.md](2026-07-17-vulkan-phase-c.md).
Milestone: full main menu, console, and ROQ video playback rendered by the
renderer-vk module; assetless-startup probes pass; validation-clean under
r_vkValidation 1.

## Recon ground truth (agents: vk-image / vk-gui / vk-infra)

Image surface (menu scope):
- The GPU half to implement = exactly the Phase C stubs (AllocImage,
  SubImageUpload, SetTexParameters, PurgeImage, Resize) plus real behavior
  behind Bind/SetSamplerState/UploadScratch (mixed-TU orchestration already
  calls them). texnum is `unsigned int` across the interface — a module-side
  image table maps texnum→{VkImage, VmaAllocation, VkImageView, VkSampler,
  layout, mips, layers}; TEXTURE_NOT_LOADED = 0xFFFFFFFF sentinel preserved.
- ALL pixel work is already CPU-side (imagetools BinaryImage): mips arrive
  pre-generated per level via SubImageUpload; colorFormat swizzles are baked
  or expressed as sampler-side component mappings. VK mapping:
  FMT_RGBA8→R8G8B8A8_UNORM; DXT1→BC1_RGBA_UNORM; DXT5→BC3_UNORM; BC7;
  ALPHA/LUM8/INT8→R8_UNORM + view swizzle (A=R / RGB=R,A=1 / RGBA=R);
  L8A8→R8G8_UNORM (RGB=R, A=G); RGBA16F; DEPTH→D32; CFM_GREEN_ALPHA →
  view swizzle (1,1,1,G) — fonts are DXT1+GREEN_ALPHA. FMT_RGB565 is
  gameplay-only (big-endian packed; needs CPU byte-swap when it comes up).
- Menu needs cube maps day one (_normalCubeMap + specular table:
  TT_CUBIC → arrayLayers 6, CUBE_COMPATIBLE, z = face in SubImageUpload).
- Retail DDS replacements make BC1/BC3 mandatory at menu scope
  (image_usePrecompressedTextures defaults 1).
- PurgeImage must also invalidate the executor's bind/descriptor cache
  (GL resets per-TMU trackers; note the SSAO stale-tracker precedent at
  Image_load.cpp:901-914).
- UploadScratch orchestrates per-frame cinematic RGBA8 uploads through
  AllocImage/SubImageUpload/SetSamplerState — falls out of D1 + an
  immediate-upload path.

2D/GUI contract (from GuiModel/RB_STD reference):
- RC_DRAW_VIEW with viewDef->viewEntitys == NULL is the 2D marker. The
  ortho projection is built FRONT-END (GuiModel EmitFullScreen); the
  backend consumes viewDef->projectionMatrix + viewport + scissor.
  drawSurfs are drawn in submission order (never sorted). Shader registers
  are pre-evaluated front-end; the backend only reads
  drawSurf->shaderRegisters.
- Geometry: idDrawVert 64B (xyz@0, color ubyte4@12, st@56 are the live
  fields); verts in frameTemp vertex cache (tri->ambientCache), indexes
  are CPU pointers (uint32) — the vk executor uploads them to a per-frame
  index ring.
- Stage loop contract (RB_STD_T_RenderShaderPasses): skip
  !HasAmbient/IsPortalSky; per-surface scissor = viewport + scissorRect;
  cull from material (2D is fine with none); per stage: skip
  conditionRegister==0, skip lighting != SL_AMBIENT, skip alpha-mask
  blends (ZERO,ONE); stage color = regs[color.registers[0..3]] with
  black-additive/transparent skips; vertexColor SVC_IGNORE/MODULATE/
  INVERSE_MODULATE (multiply in shader); texture via stage image or
  cinematic (UploadScratch); optional texture matrix (menu is almost all
  TG_EXPLICIT); GLS_* drawStateBits → blend factors, depthfunc ALWAYS for
  2D; newStage program stages = unsupported fallback for now.
- Packets are NOT the Phase D input (gated on metrics>=2 + modern pipeline,
  no stage state); walk the viewDef drawSurfs exactly like RB_STD.
- VertexCache: static Alloc = own buffer (offset 0); AllocFrameTemp =
  suballocation {buffer, offset} in the per-frame shared buffer;
  Bind*Buffer are redundant-filtered binds the vk executor replaces with
  handle-table lookups. r_useIndexBuffers defaults 0 (client-side indexes).

Infra:
- glslangValidator present locally (VULKAN_SDK 1.4.313.1) and in WSL; CI
  runners have neither → custom_target glslang pipeline emits an
  embedded-bytes header, with a COMMITTED fallback header so
  find_program(required:false) misses never break builds; optional pin
  test regenerates+compares when the tool exists. No runtime staging: the
  SPIR-V embeds into the DLL (assetless-safe, no pak coupling).
- Validation (C5 debt): WARNING_PATTERNS += vulkanValidation
  (r"Vulkan validation:") [+ r"Vulkan:\s+vk\w+ failed"]; new safe cases
  renderer-vk-clear-startup (assetless; pins module activation + swapchain
  + gfxInfo disposition line, r_vkValidation 1 under the zero-warning
  gate) and renderer-vk-fallback-drill (needs a small `hideVkModule`
  rename lever in run_case).

## Stages

D1. vk_Image.cpp — image table + VkFormat/VkComponentMapping tables +
    sampler cache (filter/repeat/aniso) + staging uploads (immediate-submit
    upload command buffer + fence; deferred per-frame-slot destruction for
    PurgeImage) + cube support + Resize; texnum indexes the table.
D2. vk_VertexCache — implement VertexCache's 4 buffer entry points over
    VMA: per-frame-slot host-visible vertex ring (AllocFrameTemp), static
    buffer table (Alloc/free), executor-side handle resolution; plus a
    per-frame index ring for the CPU index pointers.
D3. vk_GuiExecutor — restructure the frame (begin rendering lazily at
    first 2D view or clear; end at RC_SWAP_BUFFERS present); implement the
    2D drawSurf/stage walk per the contract; pipeline cache keyed on GLS
    blend bits (+alpha-test flag); push constants {mvp, stageColor,
    flags/alphaTestRef, texMatrix}; per-image descriptor sets
    (combined image sampler), lazily allocated, invalidated on purge.
D4. Shader pipeline — src/renderer/Vulkan/shaders/gui.vert/.frag →
    glslang custom_target → bin2header → generated include; committed
    fallback headers; meson wiring per the pak-header precedent.
D5. Validation — WARNING_PATTERNS + the two vk cases + hideVkModule lever;
    assetless startup coverage; full regression (GL default untouched).

Exit: menu/console/video render correctly on Vulkan (visual sign-off +
validation-clean logs), assetless probes pass, matrix + sweeps green on
Windows/Linux, GL default byte-identical behavior.
