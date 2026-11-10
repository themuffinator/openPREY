# Vulkan Phase E — world geometry: depth prepass + ambient/flat (staging plan)

> Archived 18 October 2026. Historical plan and evidence; the [development roadmap](../../../roadmap.md) is the single active plan. Old priorities, checkboxes and support claims are not current status. Technical requirements incorporated by the roadmap remain traceable here.

Status: LANDED (2026-07-18/19) — core in 834bdaa8, cube-texgen skies in
a7e79d35. mp/q4dm2 runs on Vulkan validation-clean: depth prepass + both
ambient walks + TG_SKYBOX/WOBBLESKY/DIFFUSE_CUBE stages drawing (one-shot
bring-up logs pin the evidence: "first world view drew N surfaces",
"first cube-texgen stage drew"). An adversarial review confirmed and
fixed four defects pre-landing: vkCmdClearAttachments rect clamped to
the render area, fail-closed swapchain-recreate error paths (+ BeginFrame
retry), decal surfaces push white stage color (regs color is baked into
vertex colors), per-stage privatePolygonOffset as dynamic depth bias.
Deviations from the staging plan: no vertex-cache VBO path was needed at
all (deferred to Phase J per the recon); D24S8/D32S8 carries stencil now;
newStage program stages remain skipped (flat-render gap, Phase F+);
in-engine screenshots still read 0xCD garbage under vk (glReadPixels is
a stub — real readback lands with the Phase H/I capture work). Visual
soak sign-off by the user is pending; E2's ARBFragmentProgramAvailable
material-parse decision stays conservative-false until then.
Parent: [2026-07-16-vulkan-renderer.md](2026-07-16-vulkan-renderer.md) Phase E;
Phase D record: [2026-07-18-vulkan-phase-d.md](2026-07-18-vulkan-phase-d.md).
Milestone: q4dm2 level geometry visible on Vulkan — depth prepass + the two
ambient shader-pass walks (flat/unlit world, skybox, in-world GUIs occluded
correctly); interactions/shadows/fog stay GL-only until Phases F/G.

## Recon ground truth (agents: vertex-cache / world-walk / device-caps)

Vertex path (decision: stay CPU-backed for E):
- The cache is always virtualMemory under vk (ARBVertexBufferObjectAvailable
  false; Init at VertexCache.cpp:300-315 also forces r_useIndexBuffers=0), so
  Position() returns real CPU pointers and tri->indexes are CPU pointers
  everywhere. The backend runs synchronously inside R_IssueRenderCommands
  before vertexCache.EndFrame (RenderSystem.cpp:1465/1495), so record-time
  ring copies are lifetime-safe. Phase E keeps the vk_GuiExecutor model:
  copy verts/indexes into per-frame host-visible rings at record time.
- Ring budget: 8 MB vertex / 2 MB index per slot ≈ 131k idDrawVerts; world
  views + double-walk (depth fill, ambient) will overflow — grow rings AND
  add a per-frame ambientCache→ring-offset memo so each surface uploads once
  per frame, not once per pass. Overflow currently warn+drops the draw.
- The VBO path (option b) is real future work with a designed hook surface
  (the R_RendererUpload_* stubs in vk_Backend.cpp:702-746 — VertexCache
  prefers the bridge at every call site) but has hard constraints: alloc
  hooks must never fail (NULL glGenBuffersARB behind the fallback), Position
  becomes offset-returning (vk_GuiExecutor's CPU-pointer assumption breaks),
  and ReclaimAllHeaders leaks handles on vid_restart. Defer to Phase J
  (optimization) unless E profiling forces it. THIRD HAZARD: implementing
  only the dynamic-frame bridge flips Position into the offset branch even
  with virtualMemory true (AllocFrameTemp consults the bridge first,
  VertexCache.cpp:565-598).

RB_STD 3D walk (the exact Phase E consumer contract):
- Pass order inside RB_STD_DrawView (draw_common.cpp:9663): Phase E =
  RB_BeginDrawingView (viewport/scissor + depth[+stencil] clear; color NOT
  cleared — the depth fill's black draw is the color clear) →
  RB_STD_FillDepthBuffer (9717) → processed = first sort >= SS_POST_PROCESS
  (9755) → RB_STD_DrawShaderPasses(pre-fog filter: decals + sort<SS_MEDIUM)
  (9774) → RB_STD_DrawShaderPasses(post-fog filter: SS_MEDIUM..<POST_PROCESS)
  (9818). Everything else (interactions 9732, fog 9806, SSAO/bloom, post-
  process surfaces beyond `processed`, BSE, portal fades, scene-render-
  target) defers to F/G/H. drawSurfs arrive pre-sorted; paint order = array
  order.
- Depth fill (RB_T_FillDepthBuffer draw_common.cpp:5896-6087): state
  GLS_DEPTHFUNC_LESS + depth write ON; skip !IsDrawn / MC_TRANSLUCENT /
  numIndexes==0 / all-conditions-off; SuppressInSubview is NOT checked here;
  MC_OPAQUE draws solid black (whiteImage); MC_PERFORATED walks alpha-test
  stages (stage texture + texmatrix + register alpha ref via glAlphaFunc —
  the push-constant ATEST ref must be register-driven, not just the GLS
  enum); SS_SUBVIEW surfaces blend DST_COLOR/ZERO with color 1/overBright
  (overBright can be pinned 1.0 for E); MF_POLYGONOFFSET → depth bias
  (r_offsetFactor→slopeFactor, r_offsetUnits*GetPolygonOffset→constant);
  clip-plane/mirror path deferred; prim-batch (MD5R) surfaces skipped.
- Ambient walk deltas vs the 2D walk vk_GuiExecutor already implements:
  per-entity matrix reload keyed on backEnd.currentSpace (deferred until a
  surface draws) — push MVP becomes proj × space->modelViewMatrix
  (myGlMultMatrix(space->modelViewMatrix, viewDef->projectionMatrix, mvp));
  stage depth state comes from drawStateBits (opaque/perforated stages:
  DEPTHFUNC_EQUAL + no depth write; translucent: LESS + no write;
  Material.cpp:3202-3216) OR'd with backEnd.depthFunc; cull from
  shader->GetCullType() with isMirror swap; r_skipAmbient, SuppressInSubview
  (7136), sort>=SS_POST_PROCESS && !currentRenderCopied break (7159);
  newStage program stages stay skipped (visual gaps, not crashes); texgen:
  minimum TG_SKYBOX_CUBE (cube sampler + surf->dynamicTexCoords 3-comp
  st) for the q4dm2 sky; decal color arrays (decalColorCache) can start
  deferred.
- Depth hacks: tr_render.cpp is excluded — reimplement
  R_GetDepthHackProjectionMatrix (tr_render.cpp:277-310 reference) +
  viewport minDepth/maxDepth 0..0.5 for weaponDepthHack spaces (viewport is
  already dynamic). q4dm2 view weapon needs it.
- In-world GUIs arrive as ordinary translucent ambient drawSurfs with their
  own guiSpace per surface (front-end generated) — no special backend code
  beyond correct per-space MVP + translucent depth state; full-screen menus
  keep the existing 2D path (2D pipelines stay depthTest=false).
- Per-view depth clear: every 3D RC_DRAW_VIEW re-clears depth (subviews are
  separate earlier commands) — use vkCmdClearAttachments at 3D-view start
  (or depth loadOp CLEAR for the first + ClearAttachments after).

Device/pipeline plan:
- Depth attachment: none exists today. Add per-frame-slot (2) depth images
  (VK_FRAMES_IN_FLIGHT=2; a single shared image would race overlapping
  frames), format probed D24S8/D32S8 (stencil now avoids Phase G churn),
  transient (loadOp CLEAR, storeOp DONT_CARE), transitioned alongside the
  color barrier, created/destroyed inside VK_Device_CreateSwapchain (all
  recreate paths funnel there; vkDeviceWaitIdle precedes).
- Frame shape: keep ONE dynamic-rendering scope per frame with depth always
  attached; rebuild existing GUI pipelines with depthAttachmentFormat set
  and depth test disabled dynamically (option a — avoids the loadOp
  CLEAR→LOAD trap of split scopes wiping the world before the HUD).
- Pipeline key stays small via core-1.3 dynamic state (no feature enables
  needed): add DEPTH_TEST_ENABLE, DEPTH_WRITE_ENABLE, DEPTH_COMPARE_OP,
  CULL_MODE, FRONT_FACE, DEPTH_BIAS_ENABLE, DEPTH_BIAS to the dynamic list;
  static key grows only by the depth-format presence. One executor TU
  (extend vk_GuiExecutor or carve vk_Executor) — extended-dynamic-state
  collapses the explosion, so extending in place is lower friction.
- Push constants: 128B still fits (mvp premultiplied CPU-side + stageColor +
  texMatrix + params). Skybox texgen needs a local view origin — either +16B
  (gate on maxPushConstantsSize, NVIDIA has 256 but 128 is the portable
  floor) or spill to a tiny per-frame UBO ring. Portable pattern: keep 128B,
  add the origin into params if a slot is free, else UBO.
- CLIP-SPACE Z (also a latent Phase D bug): R_SetupProjection emits GL NDC
  z∈[-1,1]; the 2D ortho even puts gui z at NDC -1 — outside Vulkan's
  [0,w] clip volume, rendering today only by NVIDIA clip leniency. Fix at
  the single MVP assembly point CPU-side: row2 = 0.5*(row2+row3) (z_vk =
  (z_gl+w)/2), applied to BOTH 2D and 3D MVPs. Depth compare stays LESS,
  window depth matches GL glDepthRange(0,1) parity for later phases.
- glConfig pins for E (VK_FillGLConfigFromDevice):
  textureNonPowerOfTwoAvailable=true (kills TG_POT_CORRECTION),
  textureCompressionAvailable=true + bptcTextureCompressionAvailable=true
  (generated .bimage DXT/BC7 are REJECTED today by
  R_BinaryImageHeaderSupportedByRenderer — the menu only worked via direct
  DDS; also gates q4dm2 lightgrid chunk accept), cubeMapAvailable=true
  (vk_Image already does cubes; also un-gates tr_light shadow-map checks for
  F). ARBFragmentProgramAvailable is folded into MATERIAL PARSE TIME
  (Material.cpp:861 'fragmentPrograms' expression constant) — GL parity
  argues true, flag for decision; flipping later needs material reparse.
  depthBounds/twoSidedStencil stay false (excluded-TU readers only).

## Stages

E1. Device depth: per-slot depth images + format probe + barriers + clears;
    frame scope gains the depth attachment; GUI pipelines rebuilt with
    depthAttachmentFormat + dynamic depth-test-off; clip-space z fixup at
    MVP assembly (2D + 3D); regression: menu + matrix vk case stay green.
E2. glConfig pins (NPOT/DXT/BPTC/cubeMap [+ fragmentPrograms decision]) +
    bimage acceptance verification (generated compressed images load).
E3. Executor growth: dynamic-state pipelines (depth/cull/bias), ring
    growth + per-frame ambientCache upload memo, per-space MVP + depth
    hacks, RC_DRAW_VIEW 3D branch: BeginDrawingView analog (viewport/
    scissor/depth clear) + RB_T_FillDepthBuffer port (opaque/perforated/
    subview-blend/polygon-offset).
E4. Ambient walks: pre/post-fog filtered RB_STD_DrawShaderPasses port with
    per-space matrices, stage depth bits, cull, SS_POST_PROCESS cutoff,
    TG_SKYBOX_CUBE, in-world GUI surfaces.
E5. Validation: q4dm2 devmap smoke on vk (geometry visible, no validation
    errors), matrix case renderer-vk-world-startup (assetless engine-level
    checks) if pinnable, full GL regression, Linux leg, docs/memory,
    commit+push.

Exit: q4dm2 renders recognizable flat-lit geometry + sky + HUD on Vulkan,
validation-clean; GL default untouched; menu path unregressed.
