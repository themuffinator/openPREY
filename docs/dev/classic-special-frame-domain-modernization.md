# Shared Render-Demo and Raven Special-Frame Transaction

## Status

This Milestone D corridor is **Implemented (default-off; native/static
implementation evidence recorded; runtime, final-package, and platform release
qualification pending)**.
`r_rendererSharedSpecialFrame 1` gives OpenGL and Vulkan the same sealed
ownership boundary for two otherwise exceptional classic-frame paths:

- a complete 3D frame being played from the active render-demo session stream;
  and
- an exact `RC_DRAW_SPECIAL_EFFECTS` Raven controller command, including its
  later blur composite and projected AL-light work.

The implementation is original openQ4 work. It incorporates no external source
code and changes no stock Quake 4 asset.

## Transaction boundary

A negative `viewID` is not sufficient evidence of render-demo playback: the
portal-sky camera uses that convention too. Front-end scene packets therefore
mark a render-demo view only when the live `session->readDemo` stream owns the
same render world. The record then seals the ordinary root-view identity,
demo-version state, full source surface count, exact packet associations, and
depth, interaction, and ambient pass presence.

Raven special effects are command-only work. Their packet preserves the exact
controller view and the admitted `SPECIAL_EFFECT_BLUR` / `SPECIAL_EFFECT_AL`
mask from `RC_DRAW_SPECIAL_EFFECTS`. The visible work can finish later: OpenGL
reports the blur composite and actual AL lights after their established paths
complete; Vulkan reports its normal or resolve-backed completion after its
pending controller is consumed. Both bits must complete before the record is
owned.

Neither route replaces any mature rendering behavior. A render-demo record
dispatches the complete normal 3D view executor. Special effects retain their
normal renderer-resource preparation, depth/color/resolve handling, blur, and
projected-light paths. The shared transaction seals provenance and completion;
it is not a second demo decoder or a replacement BSE/effect renderer.

## Eligibility and fallback

Render-demo ownership accepts only a complete ordinary root 3D view from the
active session stream. Portal-sky, subview, mirror, x-ray, editor, clip-plane,
and malformed/partial packet cases are rejected. Special-frame ownership accepts
only the exact normal-root Raven controller command with a nonempty admitted
mask. Packet overflow, source mismatch, stale/missing session state,
unsupported view shape, incomplete effect output, resolve/capture state, or a
backend rejection leaves the whole item on the classic fallback path.

Ownership is reported only after complete coverage: a demo must reconcile its
entire source-surface count, while Raven blur and AL coverage are accumulated
until they match the sealed mask. An unreported record is finalized as a named
classic fallback, so a partial shared report can never silently hide an
unfinished special effect.

## Control and diagnostics

`r_rendererSharedSpecialFrame` is independent of GUI, cinematic/post, world
ambient, interaction, fog/blend, subview, and deform ownership:

- `0` (default): render-demo and Raven special-frame work use their normal
  backend paths;
- `1`: an eligible sealed transaction may report OpenGL/Vulkan ownership after
  the same complete executor finishes; all other work remains classic-owned.

`gfxInfo` reports source scenes, demo/effect records, admitted effect mask,
ready/fallback views, semantic hash, and per-backend ownership, fallback,
coverage-mismatch, and duplicate-report totals. Focused dependency-light
validation is:

```text
rendererScenePacketSelfTest
rendererClassicSpecialFrameDomainSelfTest
gfxInfo
```

`tools/tests/renderer_classic_special_frame_domain.py` guards exact session
provenance, portal-sky exclusion, controller-mask capture, source validation,
OpenGL/Vulkan completion handoff, conservative defaults, release-harness
isolation, diagnostics, and CI registration.

## Release-qualification boundary

Before promotion, retain engine-written `screenshot` captures—not OS
captures—for a stock render-demo and a stock Raven blur/AL scene with the
setting off and on, separately on OpenGL and Vulkan. Require nonzero reconciled
ownership where the content is eligible, exact same-settings output, an
incomplete-mask zero-commit fallback, clean backend diagnostics, and fresh
staged-package and target-platform/driver evidence.

The special-subview transaction now covers direct mirror/clip-plane and
dynamic mirror/reflection/x-ray handoffs; see [Shared Special-Subview
Transaction](classic-subview-domain-modernization.md). Its eligible nested trees
also couple separately sealed authored-post tails to the same atomic root
completion and rollback decision.

Together with the other independently guarded shared corridors, this completes
Milestone D's scoped implementation. It does not make every classic-frame
category or the aggregate modern-visible renderer shared-owned. Runtime,
clean-package, human-review, and target-platform/driver evidence remain
release-promotion gates; temporal presentation is the next roadmap milestone.
