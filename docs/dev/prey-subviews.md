# Prey subviews: skybox portals, direct portals and mirrors

How openPREY draws the views that Prey materials nest inside another view, what
retail `PREY.exe` does, and what each backend has to guarantee. Front-end code
is in `src/renderer/tr_subview.cpp`; the retail reference is
`references/PREY.exe_disassembly.txt` (`sub_4f14e0` is `R_GenerateSubViews`,
`sub_4f1100` is `R_GenerateSurfaceSubview`, `sub_4f02d0` builds the skybox view,
`sub_4f05d0` the direct portal view).

## The kinds of subview

| Kind | Authored as | Where it draws |
|---|---|---|
| Skybox portal | `skyboxportal` material keyword (`textures/editor/skyboxportal` on `func_skybox_portal` brushes) | Straight into the parent view, under everything else |
| Direct portal | `directportal <distance>` material keyword (`textures/portals/portal`, the glow portal models) | Straight into the parent view, inside the surface's scissor rectangle |
| Mirror | `mirror` material keyword | Straight into the parent view, inside the surface's scissor rectangle |
| Render map | A stage with `remoteRenderMap`, `mirrorRenderMap`, `portalRenderMap`, `skyboxRenderMap` and so on | A cropped corner of the frame, captured to an image the stage then samples |

The first three have sort `SS_SUBVIEW` and are called direct subviews below. The
parent's depth fill does not paint a direct subview surface black as it does
every other opaque surface: it multiplies the colour already there by one and
writes depth, so the subview's image survives and the parent's own geometry
draws around it.

## What the front end does

`R_GenerateSubViews` walks the view's surfaces three times, as retail does. The
order is the order the views reach the framebuffer.

1. **Render-map stages.** A stage whose condition register is zero is skipped,
   so a screen that is switched off does not pay for its camera view.
2. **The skybox.** The first `skyboxportal` surface that yields a view, and no
   other. One skybox view serves every such surface the parent can see.
3. **Direct portals and mirrors**, each inside its own scissor rectangle.

Rules that follow from retail and are easy to break:

- **The skybox view takes the parent's whole scissor**, not the rectangle of the
  surface that requested it. A map caps its open sky with many skybox portal
  brushes (63 faces in `game/lotab`), and the view is generated once.
- **A skybox portal is not dropped when its own rectangle is empty.** It still
  has to pass the precise per-triangle cull.
- **There is one skybox view per view, not per frame.** A portal or mirror that
  looks onto open sky gets a skybox view of its own, nested inside it.
- **The sky goes first.** It covers the whole view, so drawing it after a portal
  would wipe that portal out.

Two deliberate differences from retail:

- A portal or skybox view inherits `isMirror` from its parent. Both keep the
  parent's axes or rotate them rigidly, so a view nested in a mirror is still
  mirrored. Retail clears the flag, which culls the wrong faces in that case.
- Mirrors and portals stay unclipped (`numClipPlanes = 0`). The retail clip-side
  maths has not been reconstructed.

## What each backend guarantees

**Direct subviews draw into the target their root view draws into.** When
post-processing gives the root a scene target, every direct subview in the
chain has to follow it there, however deeply it is nested.

- OpenGL: `RB_InlineSubviewSceneRoot` (`draw_common.cpp`) walks the whole
  `superView` chain.
- Vulkan: `VK_TemporalPresentation_RootForView` (`vk_GuiExecutor.cpp`) does the
  same.

**Gaps in a subview are black.** A sky scene does not cover its view: nothing
lies below its horizon. The window is cleared as each frame starts (`r_clear`)
and Vulkan clears its scene target for each root. OpenGL's scene target was
never cleared, so `RB_ClearSceneRenderTargetForInlineSubviews` clears the root's
part of it before the first direct subview of that root draws.

**Nothing may paint over a subview's image before the subview surface's depth
protects it.** The classic depth fill gets this from sort order alone:
`SS_SUBVIEW` sorts first, so a wall behind a portal fails the depth test before
it can fill black. Any pass that draws world surfaces ahead of the subview
surfaces breaks it.

- OpenGL takes its SSAO and cel-ink depth snapshots in a separate depth-only
  fill and clears depth again, so the real prepass keeps its order.
- Vulkan takes those snapshots by ordering the prepass: snapshot surfaces first,
  then the rest. When the view has an `SS_SUBVIEW` surface, the snapshot phases
  now write depth only, and a final phase redraws their surfaces for the black
  fill once the subview surfaces are in place (`VK_GuiExecutor_Draw3DView`).
  A view without such a surface keeps the single-draw prepass.

## Checking a change

Captures come from the engine's `screenshot` command in a windowed run from
`.install/`, once with `+set r_renderApi gl` and once with `vulkan`, and are
compared side by side. Leave post-processing at its defaults: the scene-target
and SSAO paths are where the two backends differ. Use `noclip` and
`setviewpos <x> <y> <z> <yaw>`.

| Case | Map | How |
|---|---|---|
| Sky through many skybox portal faces | `game/lotab` | The spawn view; `setviewpos 400 800 560 0` above the canyon |
| Sky scene gaps | `game/lotab` | `setviewpos 552 -912 -500 90`, looking below the sky's horizon: black on both backends |
| Mirror | `game/roadhouse` | `setviewpos -282 -340 72 180` |
| Direct portal | `game/feedingtowera` | `setviewpos 3398 3044 -2576 0` and `3320 2990 -2502 270` |
| Glow portal opened at runtime | `game/shuttlea` | `trigger object_glowportal_totower`, then `setviewpos -70640 14042 9554 0` |
| Portal with world geometry behind it | `game/lotab` | `setviewpos -447 791 341 180`, then `spawn object_portal startActive 1 cameraTarget info_player_start_5 origin "-527 791 330"` |
| Sky inside a portal, sky around it | `game/lotab` | `setviewpos 400 800 760 90`, then the same `spawn` with `origin "400 880 760"` |

Do not launch these runs with `s_noSound 1`. Several map scripts wait on a
sound's length, and a zero length turns the wait into a runaway loop that drops
the map (`game/feedingtowera`) or a cinematic that never ends
(`game/roadhouse`). Mute with `+set s_volume 0` instead.

All seven cases matched between OpenGL and Vulkan on 11 November 2026.

## Known gaps

- Glow stages are far brighter on OpenGL than on Vulkan (portal rings, lamps,
  Talon). This is the glow overlay, not the subview paths, and is not addressed
  here.
- With `r_skipPostProcess 1`, a sky drawn as the main view (camera inside the sky
  scene) is brighter on OpenGL than on Vulkan for the same reason.
- Mirror and portal clip planes remain disabled, as above.
