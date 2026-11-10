# 200 ms reference comparison

The fifth revision follows a visual audit of all **31 checkpoints** from 2:00.00
through 2:06.00 in the [supplied trailer](https://www.youtube.com/watch?v=jHkjMqZJGuU&t=120s).
The purpose of the audit is to identify visible design and animation differences;
a successful render or watertight mesh is not a fidelity score.

## Alignment and evidence

The locally decoded source runs at **30000/1001 fps**. For each requested time,
the audit uses its nearest decoded frame. Blender runs at 30 fps, so the matched
frames are **1, 7, 13, …, 175, 181**. The delivered six-second animation contains
frames 1–180; frame 181 is an additional endpoint check. There is no optical-flow
interpolation or frame stretching in the comparisons.

The reference clip begins at original time 119 seconds. Four previously inspected
stills at 120, 121, 124 and 126 seconds match clip frames 30, 60, 150 and 210
with zero pixel difference. `alignment.json` records the precise sampled times.
The 29.97/30 fps difference places these source samples approximately 1–7 ms
after their requested timestamps, well below one source frame.

Local evidence is under `.tmp/quake4-trailer-logo/`:

- `audit-200ms-baseline/`: the 31 v4 comparisons and initial written findings.
- `audit-200ms-v5/`: current 31 paired comparisons, seven review sheets,
  `alignment.json`, `luminance.csv` and a frame-stepped `index.html` viewer.
  `comparison_200ms.mp4` holds each of the 31 pairs for 200 ms, including the
  endpoint, so that inspection movie runs 6.2 seconds.
- `reference-200ms/`: the 31 decoded reference frames, retained for inspection.
- `parity-v5-frames/`: current full-resolution render frames and queue status.

Reference images are inspection evidence only. They are not packed into the
Blender file, used as visible scene surfaces, or included in repository assets.
The luminance measurements help detect flash and fade timing errors; equal
brightness does not imply equal geometry, texture or composition.

## Changes driven by the audit

The largest timing discrepancy was the second flash: it belonged at 121.20
seconds, approximately 300 ms earlier than the preceding reconstruction.
The title now crosses the camera during that burst, followed by the receding
letters and optical afterglow. The first cut is at 120.30 seconds. The ending
uses measured AgX display-response curves so the letters and background fade
together instead of leaving isolated white text.

The eye's red boundary was measured as approximately **276 × 246 pixels** at
121.00 seconds. The earlier reconstruction was approximately **251 × 249**.
The revised opening is horizontally oval, with a thinner olive retaining seat.
The solid clamps now have wide planar lands, three layered straps, rounded
captive pins and independently moving telescoping rails. A vertical machinery
pocket replaces the invented round bore. Lower diagonal braces lose the extra
inset trim; the left cooling assembly uses broader bent ribs.

The silver Q, U, K, E and 4 have wider metal faces, including substantial lower
bowls and stems. Their chamfers are actual bounded mesh surfaces. The large
iron insignia retains its closed silhouette and clamped upper tips; its grain
and localized green irradiation are separate from the floating technical lines.
The paint has stronger fine wear, scuffing and clustered coating loss, and the
background and clamp lighting are less uniform.

The wider K required a second approach-distance correction: at 121.20 seconds,
the reference's bright stem spans approximately x994–1374 at image row 120.
The first revised render spanned x924 through the right image boundary. The
approach distance now accounts for the thicker stem. Only K crosses at this
checkpoint; the remaining letters enter during the retreat, removing the
incorrect giant A at the left edge. A brief cyan scattering grade preserves
the white crossing while keeping the surrounding flash blue. The captive-pivot cutters
also share their jaw parents, so the slots are actually cut when the geometry
is rebuilt at the held frame; an unparented cutter had missed the moving head.

The two outer reticle contours have a small opening beside the diagonal leads.
Their visibility curve replaces the earlier curve completely, removing a stale
key that caused an unintended brightness rise just after 122 seconds. The held
silver emission and frontal reflection are reduced to retain more bevel contrast.

## Checkpoint observations

These rows identify what was scrutinized at every requested time. The current
render remains a reconstruction; the remaining differences below are not
silently treated as passed matches.

| Original | Blender | Comparison focus and result |
|---|---:|---|
| 2:00.00 | 1 | Preceding gameplay remains in the original; this title-only scene is dark. |
| 2:00.20 | 7 | Same boundary limitation; the eye no longer appears prematurely. |
| 2:00.40 | 13 | Opening burst, visible cyan pupil, radial diffraction and horizontal flare; exact source scattering remains approximate. |
| 2:00.60 | 19 | Burst contraction and iris visibility; eye/faceplate scale and mechanical reveal inspected. |
| 2:00.80 | 25 | Elliptical seat, dark clamp mass and diminishing flare; source blur is stronger. |
| 2:01.00 | 31 | Unobstructed geometry check: eye aspect, three straps, broad fins, pivot and localized paint scar. |
| 2:01.20 | 37 | Corrected second flash and bright near-camera letter crossing. |
| 2:01.40 | 43 | Receding U/A/K/E scale, blue optical afterglow and transient blur. Source retains different ghost trails. |
| 2:01.60 | 49 | Full wordmark entry, iron reveal and fading flare; source temporal trails remain stronger. |
| 2:01.80 | 55 | Overlay emergence and red-to-amber eye transition. |
| 2:02.00 | 61 | Wordmark settling; wider silver strokes and lower bowls compared. |
| 2:02.20 | 67 | Amber center, overlay contrast and opening of the clamps. |
| 2:02.40 | 73 | Lower diagonal braces and unequal cooling/channel detail. |
| 2:02.60 | 79 | Rough iron face and reduced broad glow. |
| 2:02.80 | 85 | Silver reflections, stroke weight and continued camera recession. |
| 2:03.00 | 91 | Vertical left equipment pocket and descending reticle. |
| 2:03.20 | 97 | Right glyph placement, soft technical lines and outer enclosure. |
| 2:03.40 | 103 | Crown seams, recesses and lower background mass. |
| 2:03.60 | 109 | Both curved upper horns; bounded tips remain intact. |
| 2:03.80 | 115 | Lower iron arc, granular surface and edge illumination. |
| 2:04.00 | 121 | Held-frame crops of every letter, eye, left clamp, upper-left housing and lower iron. |
| 2:04.20 | 127 | Moving overlays and faint peripheral arcs through the pullback. |
| 2:04.40 | 133 | Silver highlight width, bevel response and background detail. |
| 2:04.60 | 139 | Late held composition and relative brightness of text and machinery. |
| 2:04.80 | 145 | Attenuation onset and last full-brightness balance. |
| 2:05.00 | 151 | First fade checkpoint; white highlights now attenuate with the scene. |
| 2:05.20 | 157 | Mid-fade text/background balance; broad luminance agrees more closely. |
| 2:05.40 | 163 | Dim coherent composition instead of isolated white lettering. |
| 2:05.60 | 169 | Late fade, subdued overlays and remaining silhouette. |
| 2:05.80 | 175 | Near-black endpoint transition; fine source residuals differ. |
| 2:06.00 | 181 | Additional QA frame confirms the dark olive floor after the fade. |

## Remaining fidelity limits

The final 96-sample checkpoints were reviewed on **1 October 2026**. At 121.20
seconds, the bright K stem spans x1006–1365 at row 120 (359 pixels), compared
with x994–1374 in the source (380 pixels). At 121.00 seconds, the fitted red
eye boundary is approximately 275 × 249 pixels, versus 276 × 246 in the source.
At the held 124.00-second frame, mean display luminance is 36.863 versus 37.931;
this supports the exposure comparison only, not a geometric match.

- The first two checkpoints show a separate gameplay shot. That environment,
  character and action are outside this modeled title scene and remain absent.
- The exact first-flash scattering and the source's temporal ghosting are not
  recovered. The scene uses authored optical effects and real motion blur.
- The burst peaks remain dimmer and more regular than the source, and the
  middle of the closing fade is slightly darker. These differences are visible
  in both the paired frames and the recorded luminance measurements.
- Fine casting transitions, background recess proportions and individual
  surface wear patterns remain approximations. Some machinery is still more
  regular than in the reference.
- The compressed trailer cannot identify every hidden surface or resolve the
  original shader and lighting setup. The scene preserves editable depth and
  geometry rather than embedding source-video pixels.

These are explicit open differences. This revision is not certified as a
pixel-identical or fully recovered original production scene.
