# openPREY UI Visual Design

Specification version 1.22, 21 November 2026.

Status: reference survey and design contract. openPREY renders the stock Prey
GUIs by default. A first vector replacement, the home screen's navigation, its
small frames, the Load Game, Save Game and Credits pages, the death screen,
Options with all four tabs, the system check and the level loading screen, is built for the
retained interface and presents while `ui_retained` is 1 (section 12.5). Sections 1 to 11 record what makes the Prey
interface look and behave like Prey, so that fixes, widescreen work, new
settings pages and every further replacement stay inside that identity.
Section 12 covers openPREY's own additions.

| Part | State |
| --- | --- |
| Stock survey (sections 1 to 11, Appendices A and B) | Measured from the retail archives, the art and engine captures |
| Aspect expansion, loading screens and Video pages (section 12.1) | Built |
| Initializing screen (section 12.6) | Built behind `ui_retained`: the energy ball, beam, flare and wordmark over a drifting nebula |
| Rifle scope at any aspect (section 10.8) | Built in the legacy GUI with the stock art |
| Alien-script translation (section 11.4) | Built |
| 3D main-menu backdrop and entrance (section 12.2) | Specified, not built. The menu draws the stock layers |
| Vector or retained-UI replacement (sections 12.3 and 12.5) | Home navigation, bottom bar, New Game, Mods, Exit, Quit Game, Load Game, Save Game, Credits, the death screen, Options (every tab and the Reset Defaults dialog), the system check and the level loading screen built behind `ui_retained`; MultiPrey and the message boxes are still the stock ones |

The companion [Interface Atlas](prey-ui/atlas/prey-interface-atlas.html) draws
the measured components, screens and motion as editable vector
reconstructions. Open it in a browser next to this document.

`docs/dev/ui-visual-design.md` is the upstream openQ4 specification for Quake 4.
It arrives with every merge from `openq4-upstream/main` and describes a
different game. Its Marine olive palette, orange interaction colour, upper-case
labels and stepped framing bands do not apply to Prey. Where the two documents
disagree about a Prey screen, this one governs.

## Contents

1. [Purpose, authority and reference](#1-purpose-authority-and-reference)
2. [Brand and visual identity](#2-brand-and-visual-identity)
3. [Coordinates, density and aspect expansion](#3-coordinates-density-and-aspect-expansion)
4. [Colour, alpha and light](#4-colour-alpha-and-light)
5. [Typography and language](#5-typography-and-language)
6. [Framing and geometry](#6-framing-and-geometry)
7. [Components and interaction states](#7-components-and-interaction-states)
8. [Motion and sound](#8-motion-and-sound)
9. [Screen composition](#9-screen-composition)
10. [HUD and in-game overlays](#10-hud-and-in-game-overlays)
    - [10.8 The rifle scope](#108-the-rifle-scope)
11. [In-world device GUIs](#11-in-world-device-guis)
    - [11.4 Type and the translation mechanic](#114-type-and-the-translation-mechanic)
12. [openPREY additions and modern direction](#12-openprey-additions-and-modern-direction)
    - [12.2 The 3D backdrop and entrance](#122-the-3d-backdrop-and-entrance)
    - [12.5 The retained navigation](#125-the-retained-navigation)
    - [12.6 The initializing screen](#126-the-initializing-screen)
13. [Project branding](#13-project-branding)
14. [The Interface Atlas](#14-the-interface-atlas)
- [Appendix A. Survey method](#appendix-a-survey-method)
- [Appendix B. Measured furniture](#appendix-b-measured-furniture)
- [Appendix C. Observations recorded during the survey](#appendix-c-observations-recorded-during-the-survey)
- [Appendix D. Change record](#appendix-d-change-record)

## 1. Purpose, authority and reference

Prey's interface is part of its fiction. The front end opens a portal onto the
Sphere hanging over Earth; the HUD reads as Tommy's own perception; alien
consoles speak a script he cannot read until the game translates it. Keep that
relationship between interface and world when changing any GUI. A screen that
works but drops the portal, the steel-glass furniture or the alien script no
longer looks like Prey.

Read this specification before you change a stock GUI, add a settings page,
draw an icon or compose a replacement screen. Keep the measurements in source
units and convert them last.

### Source hierarchy

1. The installed Prey archives establish stock visuals, animation, behaviour,
   fonts and sounds. Both known retail layouts apply (`pak000.pk4` to
   `pak004.pk4`, or `pak_data.pk4`, `pak_sound.pk4` and the `pak_en_*`
   language packs; see [official-pk4-checksums.md](official-pk4-checksums.md)).
2. Repository `content/basepr/` overrides establish openPREY's current
   behaviour: aspect expansion, the extra video pages and the loading level
   name (section 12).
3. This specification records geometry, colour, type, motion and state, and
   says which of them a change must keep.
4. Engine captures provide comparison views. Record the map or GUI, state,
   renderer, resolution and the command used (Appendix A).

The effective copy of a stock file is the one the virtual filesystem resolves
last. openPREY's `pak0.pk4` and `pak1.pk4` in `basepr/` override thirteen
retail scripts (section 12.1 names them); measure those from
`content/basepr/pak0/`, everything else from the retail archives.

### Measuring stock sources

Stock GUIs author every rectangle on a 640x480 virtual canvas. This document
records those measurements in source units (`u`). At the 1280x720 dp reference
of the upstream retained-UI system, `1 u = 1.5 dp` on both axes; the 4:3
canvas maps to the central 960x720 dp and aspect expansion supplies the rest.

- Interface bitmaps stretch into window rectangles. Record proportions in the
  texture (visible bounds, rail thickness, fade span) and scale them by the
  drawn rectangle. Appendix B gives texel measurements.
- A `textscale` of `s` draws an em of `48 s` u: the engine scales each atlas
  by 48 over its point size, so the 48-point atlas draws at 1.0 and the
  24-point atlas at 2.0. Take cap and x-heights from glyph ink, not from `.dat`
  rectangles.
- Record colours with their material blend. The same art looks different under
  `blend add`, `blend blend` or a masked stage.
- Convert stock float colours with `floor(255 x + 0.5)`, so 0.7 is `B3` and
  0.3 is `4D`.
- Record motion from `transition` durations. The two optional arguments after
  the duration are the fractions of it spent accelerating and decelerating;
  when they sum to more than 1 the interpolator scales them in proportion to
  fill the duration. The stock `"500" "500" "500"` is therefore 250 ms
  accelerating and 250 ms decelerating, an even ease-in-out.
- Cite the effective file. Line references in this document are to the files
  under `content/basepr/pak0/guis/` where openPREY overrides a script, and to
  the retail archives otherwise.
- Record numbers and descriptions only. Extracted art, fonts and captures stay
  outside tracked source.

## 2. Brand and visual identity

Prey (Human Head Studios, 2006) is the story of Domasi "Tommy" Tawodi, a
Cherokee garage mechanic abducted with his girlfriend Jen and his grandfather
Enisi by the Sphere, a living alien ship that harvests Earth. Its world has
four registers, and the interface uses all of them:

| Register | What it is | Where the UI shows it |
| --- | --- | --- |
| Space and the Sphere | Black space, the Sphere's slate shell with glowing blue plates and green bioluminescent patches, Earth's limb below | The front-end backdrop, loading art, the menu sun |
| Portals | Blue energy rings that cut holes in space | The front-end opening and frame, the in-world portal controls |
| The alien ship | Biomechanical consoles in amber, bronze and rust; the Hider script | Device GUIs, keypads, scanners (section 11) |
| Tommy's heritage | The spirit walk, the hawk Talon, Enisi's guidance | The hawk emblem, the spirit HUD, loading art |

The front end and every out-of-world screen speak one visual language: **steel
glass in a portal**. Translucent slate-blue furniture with pale steel rails,
cool text that brightens toward white, claw-shaped frame corners, and behind it
all a portal opening onto the Sphere.

### Recognition traits

These traits make an interface read as Prey. A reconstruction of a stock screen
that drops one of them is not visually complete.

1. **A portal onto space.** The front end is a view through an open portal:
   a blue energy rim (body `#2F64DC`, core `#A4F9FE`) bounds the leading edge,
   and through it a star field, the Sphere lit by a small sun, and Earth's limb
   across the foot. Menus never sit on a flat colour.
2. **The wordmark.** `PREY` in very wide extended capitals: dark fill, a thin
   cyan-white edge (`#AFFCFF`), and a horizontal blue lens streak (`#3380B1`)
   through the letters' middle. It sits centred above the Sphere at
   100,55 u, 476x37 u.
3. **The arc of hooks.** Navigation hangs from a silver-blue arc with rivets
   (`#859BAF` to `#9DB8D0`). Each entry is a thin bar that begins in a hook at
   the arc and ends in a small ring; the entries step outward along the curve.
4. **Steel glass.** Frames and controls are translucent slate-blue
   (`#6F86A1`, `#546579`, `#5C6C81`) bounded by pale steel rails (`#B3C6E2`).
   Fills fade from the leading edge (0.77) to almost nothing (0.06) at the
   trailing edge.
5. **Claw corners.** Every frame ends in four mirrored claw brackets,
   38x32 u: a pale-railed hook around a dark oval socket. Between them a 4 u
   strip carries a 1.5 u rail along the top and bottom. There are no side
   rails: the black body stops 25 u inside each end, so the claws stand clear
   of it.
6. **Asymmetric ends.** Bars, buttons and rows begin with a slanted or curved
   cut and end with a different one. Nothing is a plain rectangle and nothing
   is a pill.
7. **Two cool faces.** An extended display face with small-capital lower case
   carries navigation, titles and bottom-bar actions; a condensed face with a
   very tall x-height carries rows, values, lists and buttons. Text is steel
   blue (`#B3CCE6` at 0.9), brightens toward white on hover, and usually casts
   the engine drop shadow (section 5).
8. **Centred, Title Case labels.** Controls centre their labels (nine in ten
   windows that set an alignment use `textalign 1`); the main navigation leads
   from its hook. Strings are Title Case: New Game, MultiPrey, Return to Main
   Menu.
9. **Panels grow out of the bar.** Sub-menus grow from the bottom bar with an
   even ease-in-out over 500 ms; full-screen pages widen first (200 ms) and then
   rise (500 ms). The navigation hides while any page is open; the wordmark
   hides under a full-screen page.
10. **Warmth belongs to the world.** The front end is almost entirely cool. Its
    only warm accents are the gold of a hovered server-list heading
    (`#E6CC73`) and one yellow bonus line in the credits. Amber, bronze, rust
    and red belong to the alien ship, the hawk emblem and the help pages.

### Divergences to avoid

- Quake 4's olive plates, orange focus and upper-case labels.
- Orange or warm interaction states in the front end. Prey interaction
  brightens toward white and slides; it never changes hue.
- Cyan used as a general accent. Portal cyan belongs to the portal, the
  wordmark and spirit effects; controls stay steel.
- Opaque flat cards, square-cornered plates, symmetric pill buttons and
  rounded rectangles with identical corners.
- All-capital strings for navigation or buttons. The display face supplies
  its own small capitals.
- Body text in the display face. It is too wide for sentences.
- Controls laid directly over the Sphere without a frame's black body.
- A large page heading. The page title sits in the frame's title bar.

### Families

| Family | Identity | Required fidelity |
| --- | --- | --- |
| Front end (`mainmenu`, `restart`, `netmenu`, `msg`) | Steel glass in a portal over space | Portal opening and rim, Sphere backdrop, arc of hooks, claw frames, growth from the bar |
| In-game multiplayer menu (`mpmain`) | The front-end vocabulary without the portal | Tabs, 3-slice buttons, chat and status rows |
| Loading (`map/loading`) | Full-bleed level art, name band, bar progress | Top name band, claw-ended progress bar, level art per map |
| Help and key reference (`help`) | Six tabs, each tinting its page its own colour | Keyboard map, binding rows, tab colours |
| Credits (`mainmenu_credit*`, `credits`) | Wordmark, sheared fly-in lines | Shear and slide choreography, heading/title/name colours |
| Single-player HUD (`hud`) | Section 10 | Section 10 |
| Multiplayer HUD and scoreboard (`mphud`, `scoreboard`) | Section 10 | Section 10 |
| In-world devices (`guis/roadhouse`, `biolabs`, `generic_*`, ...) | Section 11 | Section 11 |

## 3. Coordinates, density and aspect expansion

The stock grid is the 640x480 canvas. openPREY expands it to the screen's
aspect and gives GUI scripts these values and keys (section 12.1 says where
each is used):

| Name | Kind | Meaning |
| --- | --- | --- |
| `gui::virtual_screen_x_expand`, `gui::virtual_screen_y_expand` | GUI variable | The extra canvas on each side, in canvas units |
| `gui::virtual_screen_diagonal` | GUI variable | The diagonal of the whole screen in canvas units: the side of a square that covers the screen at any turn. GUI expressions have no square root to work it out |
| `screenalignx`, `screenaligny` | Window key | Pin a window to a screen edge |
| `backgroundLeft`, `backgroundRight`, `backgroundTop`, `backgroundBottom` | Window key | Edge slices that continue a full-screen background beyond the canvas |
| `naturalmatscale` | Window key | Holds a tiled material's density as its window widens |
| `canvasfill` | `renderDef` key | Draws the model view across the whole expanded canvas, keeping the projection its rect defines |
| `matcanvasfill` | Window key | Draws one picture across the whole screen |

Loading screens use the openQ4 method: the session composes the art and its
`_left`, `_right`, `_top` and `_bottom` tiles in memory into one picture of
the window's shape, and the GUI draws it with `matcanvasfill` when
`gui::loading_bkgnd_canvasfill` is 1.

| Stock element | Source (u) | Reference (dp) |
| --- | --- | --- |
| Canvas | 640x480 | Central 960x720 |
| Wordmark | 476x37 at 100,55 | 714x55.5 |
| Navigation arc | 150x362 at 50,102 | 225x543 |
| Navigation pitch / bar height | 27 / 19.5 | 40.5 / 29.25 |
| Navigation label box / hit strip | 300x25 / 200–220x20 | 450x37.5 / 300–330x30 |
| Bottom bar | 450x32 at 180,438 | 675x48 |
| Small sub-menu frame | 376x270 at 180,200 | 564x405 |
| Full-screen page frame | 620x460 at 10,10 | 930x690 |
| Frame corner / edge strip | 38x32 / 4 | 57x48 / 6 |
| Title bar: small frame / full page | 312x24 / 556x24, both at 32,8 | 468x36 / 834x36 |
| Bottom title bar: small frame / full page | 312x19 at 32,243 / 556x19 at 32,432 | 468x28.5 / 834x28.5 |
| Settings row: pitch / plate | 30 / 25 | 45 / 37.5 |
| Button (3-slice) | 80–170 x 22–30; most are 100–125 x 25–30 | 120–255 x 33–45 |
| Side-tab column / page (Options) | 100 / 470x370 | 150 / 705x555 |
| Dialog frame: Reset Defaults / confirmations | 360x250 at 142,100 / 360x140 at 142,132 | 540x375 / 540x210 |
| Loading name band / progress outline | 640x35 at 0,10 / 304x30 at 168,443 | 960x52.5 / 456x45 |

Stock hit strips do not fill their pitch: the navigation strips are 20 u high
on a 27 u pitch. A replacement makes the whole pitch the target, with the 30 u
(45 dp) settings row as the minimum on desktop and 48 dp for touch.

Keep the following anchors under aspect expansion:

- The portal rim stays on the leading screen edge. The wordmark, Sphere and
  sub-menu frames stay on the central 4:3 axis. The portal's view is the 4:3
  view scaled up to the screen's width about the canvas centre (its rect is
  `-x, -0.75x, 640 + 2x, 480 + 1.5x` for an expansion of `x` a side), so the
  rim keeps its stock place against the leading edge and the far side of the
  ring, just past the 4:3 canvas, stays off screen. The rim is therefore
  larger on wider screens. On a screen taller than 4:3 the view keeps its
  scale and shows more of the ring above and below.
- The navigation arc stays in the leading half of the 4:3 canvas; it does not
  slide to the screen edge.
- The star field, Earth's limb and loading art fill the full screen width.
  The painted layers do so with edge slices (section 12.1); the 3D backdrop
  of section 12.2 does so by holding its vertical field of view, so a wider
  screen sees more to each side.
- The bottom bar and full-screen page frames stay inside the 4:3 canvas.
  Widening them is an optional modern layout (section 12), not a stock
  behaviour.
- The 4:3 canvas is centred on both axes. On a screen taller than 4:3 the
  stock backdrop expands above and below the canvas, so a retained document
  centres its 4:3 stage vertically too (`STAGE` in
  `tools/ui/build_retained_screens.py`); a stage pinned to the top would part
  the navigation and frames from the wordmark and the Sphere.

## 4. Colour, alpha and light

All colours below are sRGB; alpha is separate. Values come from
`guis/mainmenu/menucolors.guifragment`, which defines the front end's palette in
one place, and from sampled interface art (Appendix B).

### Text

| Token | sRGB / stock value | Use |
| --- | --- | --- |
| `prey.text.nav` | `#B3CCE6` at 0.90 (0.7, 0.8, 0.9) | Main navigation, frame titles |
| `prey.text.navHover` | `#CCE6FF` at 1.00 (0.8, 0.9, 1) | Hovered navigation, bottom-bar hover |
| `prey.text.bottom` | `#B3CCE6` at 1.00 | Bottom-bar and bottom-title actions |
| `prey.text.label` | `#FFFFFF` at 0.90 | Setting labels, dialog body (`STATIC_FORECOLOR`) |
| `prey.text.value` | `#B8C9E6` at 0.90 (0.72, 0.79, 0.9) | Editable values, bindings (`EDITABLE_FORECOLOR`) |
| `prey.text.valueOff` | `#B8C9E6` at 0.40 | Unavailable values |
| `prey.text.button` | `#CCDEFA` at 1.00 (0.8, 0.87, 0.98) | Button labels, radio labels, skill heading |
| `prey.text.buttonOff` | `#B5C9E3` at 0.30 (0.71, 0.79, 0.89) | Unavailable buttons |
| `prey.text.tab` | `#B5C9E3` at 0.70 | Inactive tab labels |
| `prey.text.tabHover` | `#CCDEFA` at 1.00 | Hovered tab labels |
| `prey.text.hover` | `#FFFFFF` at 1.00 | Hovered values, buttons, active tabs, list headings |
| `prey.text.list` | `#A6BAD4` at 1.00 (0.65, 0.73, 0.83) | List rows |
| `prey.text.headingHover` | `#E6CC73` at 1.00 (0.9, 0.8, 0.45) | Hovered list column heading; the front end's only warm colour |
| `prey.text.headingInk` | `#262930` (0.15, 0.16, 0.19) | Text on a filled heading band; defined in `menucolors.guifragment` but used by no stock screen |

### Furniture

| Token | sRGB / alpha | Use |
| --- | --- | --- |
| `prey.rail` | `#B3C6E2` | Frame rails, claw rims, active top-tab rim |
| `prey.claw.body` | `#3B4351` to `#576272` | Claw corner body |
| `prey.claw.socket` | `#171B20` | Claw corner socket |
| `prey.frame.body` | `#000000` at 0.70 (0.50 for the home bottom bar and the Options page) | Frame body (`background "_black"` under `matcolor`) |
| `prey.plate.button` | `#6F86A1`; fill 0.77 → 0.06 leading to trailing, rims 1.0 | 3-slice buttons |
| `prey.plate.buttonHover` | `#6F86A1`; even fill 0.30, rims 1.0 | Hovered 3-slice buttons |
| `prey.plate.row` | `#546579`; fill 0.77 → 0.06, rims 1.0 | Setting rows, group boxes |
| `prey.plate.title` | `#5C6C81` at 0.69 (slanted ends 0.60) | Frame title bars |
| `prey.plate.header` | `#111A25` at 0.60, `#6D7F95` rims | Section and column header bars |
| `prey.tab.top` | idle `#252831`, opaque; active `#7F95AA` → `#222A31` top to foot under a `#B3C6E2` rim | Top tabs (`tabedge`, `tabstrip` and their `active` forms) |
| `prey.tab.side` | idle `#3E4C61` at 0.45; active `#5A6E80` → `#222A31` leading to trailing, `#A7BFD7` rim top and foot | Side tabs (`tabtop`, `tabhstrip`, `tabbottom` and their `active` forms) |
| `prey.page.wash` | `#4A5263` at 0.10 under `#222A31` shading that starts at 0.93 on the page's top and leading edges | Tab page body |
| `prey.separator` | `#BDCFE0` (0.74, 0.81, 0.88) | Tab container outlines |
| `prey.heading.band` | `#61758C` with a 1 u `#B5C9E3` border | Filled heading bands; defined but used by no stock screen |
| `prey.list.wash` | `#A6C4E6` at 0.15 | List and edit field backing |
| `prey.list.selection` | `#A6BAD4` at 0.30, outline `#B5C9E3` at 0.70 | Selected list row |
| `prey.radio.active` | `#99ABC7` at 0.70 | Selected radio segment |
| `prey.frame.picture` | `#A7C4E8` | Portrait and level-shot frames |
| `prey.scroll` | `#ADC5E3`, thumb `#BDD3F0` | Scroll bars |
| `prey.slider` | rail `#323C45` with `#94B2CC` ticks, knob `#BBCDDE` | Sliders |
| `prey.arc` | `#859BAF` to `#9DB8D0`; bars `#9AB1CA` | Navigation arc and bars |
| `prey.scrim` | `#000000` at 0.80 (Reset Defaults); 0.40–0.50 (confirmations); 0.60 (`msg`) | Dialog overlay |
| `prey.softfocus` | A 5 u (7.5 dp) Gaussian blur at 0.80 saturation of the screen beneath, under any scrim | Retained pop-ups (openPREY; section 12.5); in no stock screen |

### World and brand

| Token | sRGB | Source |
| --- | --- | --- |
| `prey.space` | `#000000`; stars to `#161616` | `preymenu/background1.tga`, added |
| `prey.portal.core` | `#A4F9FE` (peak `#DDFFFF`) | Portal rim, sampled |
| `prey.portal.body` | `#2F64DC` | Portal rim, sampled |
| `prey.wordmark.edge` | `#AFFCFF` | `menu/prey.tga` brightest |
| `prey.wordmark.streak` | `#3380B1` | Wordmark glow, sampled |
| `prey.sphere.shell` | `#0F171B` on average; `#2A3D48` along the lit lower rim, `#4A6F84` at its brightest | `background3.tga`, sampled |
| `prey.sphere.plate` | `#2D4569` on average; `#223B60` to highlights near `#AFC5E3` | `background4.tga`, sampled; the plates cover about a fifth of the disc |
| `prey.sphere.bio` | `#1F6043` | Sphere's green patches, sampled |
| `prey.earth` | `#A7B5CF` (to `#E8EAF0`) | `background2.tga` |
| `prey.load.name` | `#A6BFFF` at 0.80 (0.65, 0.75, 1) | Loading level name |
| `prey.load.fill` | `#5959FF` at 0.65 (0.35, 0.35, 1) | Loading progress |
| `prey.hawk.edge` / `prey.hawk.body` | `#1BDDEF` / `#5D0900` to orange | `menu/icons/prey.tga`; the project icon |

### Opacity

| Layer | Rest | Interaction |
| --- | --- | --- |
| Navigation bar | 0.60 (authored 0.70; reset to 0.60 whenever the menu opens) | 1.00 while hovered |
| Navigation label | 0.90 | 1.00, `#CCE6FF` |
| Frame body | 0.70 (home bottom bar and Options page 0.50) | Stable |
| Button plate | Leading fill 0.77 → trailing 0.06 | Even 0.30 fill; label to white |
| Setting row plate | Leading fill 0.77 → trailing 0.06 | Stable; the value text turns white |
| Inactive / active tab | Side 0.45 / 1.00; top 1.00 / 1.00 | Hover tints the plate with `hoverMatColor` 0.7 grey and the label to `#CCDEFA` |
| Dialog scrim | Black over the whole canvas: 0.80 (Reset Defaults), 0.40–0.50 (confirmations) | Appears and disappears at once |
| Loading name band | 0.55 black | Stable |

### Light and composition modes

The backdrop is lit, not painted. Its materials in `materials/guiresources.mtr`
use:

- **Additive** (`blend add`): the star field (two layers of `background1`, one
  rotating at `time*0.0005` and scrolling, surged by the `powersurge` table),
  two layers of `background5` slowly rotating and breathing in scale, and the
  sun (`sol`), which rotates and pulses with the `solsurge` table and feeds the
  glow stage.
- **Alpha blend** (`blend blend`): the Sphere's back and front layers and
  Earth.
- **Masked additive**: the Sphere's inner clouds and Earth's clouds are added
  only inside a mask written by `maskcolor`/`maskalpha`
  (`blend gl_dst_alpha, gl_one`), at 0.1 and 0.2 strength, rotating
  (`time*0.01`) or scrolling. Clouds therefore move inside the planet and the
  Sphere without ever leaving their silhouettes.
- **Screen capture**: `guis/assets/menu/menuscreenshot` maps `_menushot`, the
  frame captured when the menu opens in game, flipped vertically.
- **Models**: the portal is two unlit `renderDef` models.
  `models/sfx/menu/portal.lwo` draws only during the first 500 ms of the
  opening; `portal2.lwo` then replaces it, over the backdrop and under the
  wordmark and navigation.

A replacement keeps the additive and masked layers as light: an additive star
or sun layer must brighten what is beneath it, and clouds must stay inside
their planet's silhouette. Section 12.2 replaces the painted Sphere and Earth
layers with lit 3D bodies and keeps the star, sun and portal layers.

### Contrast

Measure composited contrast over the brightest part of the backdrop that a
control can cover. The likeliest failures are frame titles (`#B3CCE6` at 0.9 on
`#5C6C81` at 0.69 over Earth), unavailable buttons (0.30) and list rows over
the Sphere's lit plates. Target 4.5:1 for essential text and 3:1 for large text
and control boundaries. Where stock opacity fails, strengthen the local frame
body behind the text rather than recolouring the text.

## 5. Typography and language

Prey ships three faces in `fonts/english/` (each in 12, 24 and 48-point
atlases). openPREY ships scalable TrueType tracings of them in
`content/basepr/pak0/fonts/` (`menu.ttf`, `english.ttf`, `alien.ttf`; see
[ttf-font-system.md](ttf-font-system.md)); the retail atlases themselves stay
out of Git. Use the tracings for any replacement or reference drawing; their
advances match the retail records exactly.

### Faces

| Face (path) | Character | Stock use |
| --- | --- | --- |
| Display (`fonts/menu`) | Very wide extended geometric face; lower case renders as small capitals | Main navigation, frame titles, bottom bars, loading level name |
| Body (`fonts/english`, internal name `prey`) | Condensed, heavy, squared curves, very tall x-height | Setting rows, values, buttons, lists, dialogs, help, HUD text |
| Alien (`fonts/alien`) | The Hider script: one stem per glyph built from dots, bars, hooks and rings, every glyph at full cell height | Untranslated device GUIs (section 11) |

Measured from glyph ink in the 48-point atlases:

| Face | Cap height / em | x-height / cap | Cap advance / cap height | Notes |
| --- | --- | --- | --- | --- |
| Display | 0.375 | 0.72 | 2.0 (H), 2.6 (M) | Baseline sits 6 texels above the cell foot |
| Body | 0.69 | 0.82 | 0.58 | Space 0.30 of cap height |
| Alien | 0.71 (full cell) | 1.0 | 0.55 | No distinct lower case |

Compare faces by cap height: at the same `textscale` the body face's capitals
are 1.8 times taller than the display face's.

### Type ramp

| Role | Face | Stock `textscale` | Cap height (u / dp) | Colour |
| --- | --- | --- | --- | --- |
| Loading level name | Display | 0.60 | 10.8 / 16.2 | `prey.load.name` |
| Full-page title | Display | 0.55 | 9.9 / 14.9 | `prey.text.nav` |
| New Game title, skill heading, section headers on header bars | Display | 0.45 | 8.1 / 12.2 | `prey.text.nav`; the skill heading `prey.text.button` |
| Small-frame title (Exit, Quit Game, Mods, Connecting) | Display | 0.40 | 7.2 / 10.8 | `prey.text.nav` |
| Main navigation | Display | 0.39 (Exit 0.40) | 7.0 / 10.5 | `prey.text.nav` |
| Bottom-title action | Display | 0.40 (Options 0.36) | 7.2 / 10.8 | `prey.text.bottom` |
| Home bottom bar | Display | 0.35 | 6.3 / 9.5 | `prey.text.bottom` |
| Button label | Body | 0.33 (0.35 on New Game, Exit and Quit Game; 0.40 on the death screen) | 10.9 / 16.4 | `prey.text.button` |
| Setting label and value | Body | 0.33 | 10.9 / 16.4 | `prey.text.label`, `prey.text.value` |
| List row | Body | 0.25–0.34 (server browser and Mods 0.25, Load 0.31, Save 0.32) | 8.3–11.3 / 12.4–16.9 | `prey.text.list` |
| Dialog title | Body | 0.33 | 10.9 / 16.4 | `prey.text.label` |
| Dialog body, check labels | Body | 0.25 | 8.3 / 12.4 | `prey.text.label` |

`textscale 0.33` is the commonest size by far: 227 of the 390 text windows
(58%) in the retail `mainmenu.gui` and its fragments. Use it as the default
body size. 0.25 is the floor for essential text in the main menu; only the key
legends of `help` and `mpmain` go smaller (0.15–0.20).

### Case, alignment and shadow

- Strings are Title Case in the language tables (`#str_20553` "New Game",
  `#str_20135` "MultiPrey", `#str_20018` "Return to Main Menu"). Keep that case
  in new strings; the display face turns lower case into small capitals itself.
- Centre labels in their box. `textalign 1` is set by 349 of the 388 retail
  windows (90%) that set an alignment across the seven front-end scripts
  (`mainmenu` with its fragments, `mpmain`, `restart`, `netmenu`, `msg`,
  `help` and `map/loading`). Labels sit in the leading half of a setting row
  and values in the trailing half, each centred in its half. Main navigation
  labels set no alignment and lead from just past their bar's hook. Leading
  alignment otherwise appears in the Reset Defaults check labels and two list
  captions; trailing alignment in the Create Server value fields and the Find
  Servers filter labels.
- Most strings set `shadow 1`: about five in six text windows outside the
  credits. The main navigation labels, the confirmation dialogs and list rows
  do not. Keep the drop shadow on text over imagery.
- Use `textaligny` to seat text on furniture rather than moving rectangles:
  titles use -8 (full page), -5 (New Game) or -3 (small frames), bottom titles
  -6, rows -2 to -6.
- Use each face's own spacing. The stock never tracks text.

All display strings use the language system. Preserve `#str_*` keys and format
arguments. New openPREY GUI strings use the `#str_122xxx` range
(`strings/english_openprey.lang`).

## 6. Framing and geometry

Every element below can be rebuilt as vector geometry from the measured
construction. Appendix B holds the texel measurements.

### The arc of hooks

- The arc (`curve_ig.tga`, 256x514 texels, drawn 150x362 u at 50,102) is a thin
  silver-blue curve with rivets along its inner edge. It bows toward the
  leading edge and reaches the foot of the screen near the bottom bar.
- Six bars hang from it (`bar.tga`, `bar2.tga`, `bar3.tga`, `bar4.tga`; 19.5 u
  tall). Each is a hairline with a hook where it meets the arc and a small ring
  at its trailing end. Their leading edges step outward with the curve:
  x = 62, 65, 70, 78, 89, 105 u at y = 208, 235, 262, 289, 316, 343 u.
- Bar length follows the label: 178, 140, 146, 146, 115 and 80 u.
- Labels sit 8 u above their bar (label box y = bar y − 8) and 14–18 u in from
  the bar's leading edge.

### The claw-cornered frame

The frame (`superWindowDef`) draws:

1. A black body at the frame's `matcolor` alpha, inset from the frame
   rectangle by its `margins` (left, right, top, bottom: 25, 25, 1 or 7, 0).
   The body therefore stops 25 u inside each end and the claws stand clear of
   it.
2. Four copies of `window_cornerUL`, 38x32 u, mirrored into each corner. Each
   is a hook-shaped bracket: a pale rim about 2 u wide around a slate body,
   with a dark oval socket (34x44 texels of the 128x128 art, so about
   10x11 u) in its lower half. Its beak runs along the outer edge and joins
   the edge rail; its foot curls toward the inside.
3. Top and bottom edges of `window_top` stretched between the corners, 4 u
   tall, of which the top 1.5 u is opaque `prey.rail`.
4. No side edges.

When a frame is no taller than its corner height, only the lower pair of
corners and the bottom edge draw. The home bottom bar is such a frame, 32 u
tall. `margins` moves only the body; children use the frame's own coordinates.

### Title bars

- Top title bar: 24 u tall at 32,8 inside the frame and 64 u narrower than
  it (312 u in the small frame, 556 u on a full page); a 3-slice of
  `titlebar_corner`, `titlebarstrip` and the mirrored corner, `edgeWidth 12`.
  Its ends slant inward toward the bottom, so the bar is wider at the top.
- Bottom title bar: 19 u tall and the same width, 8–9 u above the frame's
  foot; `titlebar_corner_inv`, `edgeWidth 8`. Its ends slant the other way, so
  the pair frames the panel like a lens.
- Fill `prey.plate.title` (`#5C6C81` at 0.69, 0.60 on the slanted ends) with
  no rim.

### Plates

| Plate | Art | Leading end | Trailing end | Fill |
| --- | --- | --- | --- | --- |
| Button | `button/corner`, `strip`, `invcorner`; `edgeWidth 12` (8 to 16 on a few) | Curved slope, wider at the foot | Slanted chamfer | `#6F86A1`, 0.77 → 0.06 with full rims |
| Hovered button | `button/rollover_*` | Same | Same | Even 0.30 fill; rims unchanged |
| Setting row | `textbar_corner`, `textbarstrip`, `textbar_invcorner` | Slanted cut, wider at the top | Curved bracket | `#546579`, 0.77 → 0.06, 1-texel rims |
| Header bar | `text_titlebar_corner`, `text_titlebarstrip` | Rounded with slant | Mirrored | `#111A25` at 0.60, `#6D7F95` rims |
| Group box | `text_titlebox_left`, `text_titlebox`, `text_titlebox_right` | Rounded | Rounded | `#546579`, horizontal fade, 2-texel rim |
| Picture frame | `pictureframe_corner`, `_left`, `_strip` | Rounded 4-texel stroke | Same | Outline only, `#A7C4E8` |

Buttons, setting rows and group boxes fade from leading to trailing; only
their rims run the full length. Title bars and header bars are the flat
exceptions.

### Tabs

- Top tabs sit above the page in a `tabContainerDef` (`tabMargins 100, 0`).
  The scripts name no art for them, so the engine draws its defaults,
  `tabedge` and `tabstrip`. Inactive tabs are opaque `#252831` with a rounded
  rise on their leading edge. The active tab grades from `#7F95AA` at the top
  to `#222A31` at the foot under a `#B3C6E2` rim, and joins the page.
- Side tabs are a vertical column (`horizontal 1`, `tabMargins 40, 0`): 100 u
  wide beside a 470x370 u page in Options, 80 u in Create Server and 103 u in
  the server-details panel. They name their own art (`tabtop`, `tabhstrip`,
  `tabbottom`). Inactive side tabs are low plates in `#3E4C61` at 0.45. The
  active one is a chamfered plate graded from `#5A6E80` on its leading edge to
  the page's `#222A31` ground, with a `#A7BFD7` rim along its top and foot.
- The container outlines the page in `prey.separator` (`seperatorLines 1, 1,
  1, 1`). The page itself is a `#4A5263` wash at 0.10 under `fadebg` shading
  in `#222A31`: 0.90 to 0.97 at the page's top and leading edges, 0.64 a
  sixteenth of the way in, 0.28 at an eighth and gone by a quarter.
  `fadebg_top` and `fadebg_side` carry one edge each.
- **An active tab and its page are one surface, with no visible seam between
  them.** The art is made for it: the active tab ends in opaque `#222A31`
  exactly where it meets the page (the foot of a top tab, the trailing edge
  of a side tab), and the page's shading begins there in the same colour at
  0.93. Three rules keep the join clean:
  1. The page's outline breaks across the active tab. The separator is not
     drawn along the active tab's span on the edge that faces the tabs; it
     resumes at the tab's two ends, where the tab's own rim meets it.
  2. The active tab's rim covers only its free edges: the top and both ends
     of a top tab; the top, leading edge and foot of a side tab. No rim, line
     or shadow runs along the edge that touches the page.
  3. The active tab and the page meet without a gap or an overlap that shows:
     the active tab's plate runs to the page's edge at every scale, and
     nothing is drawn between them.
- **Only the active tab is joined. Every inactive tab keeps its seam.** The
  page's outline runs whole and at full strength along each inactive tab,
  top tabs and side tabs alike, and parts it from the page. An inactive
  tab's plate stops at the outline and never covers, dims or interrupts it,
  under hover and focus as well as at rest. When the selection moves, the
  line returns under the tab that was left in the same frame as it opens
  under the tab that was chosen.

  Both rules hold in every state: at rest, under hover and focus, while a
  page grows, and at every aspect and resolution.

### Controls

- **Check box**: 32x32-texel art drawn at 12x12 u; a dark `#39424A` square
  with a pale `#ABC5DD` cross when set (`matcolor` 1) and nothing when clear
  (`matcolor` 0). A 1 u border takes `prey.text.value` and turns white on
  hover. Its label starts 8 u after the box.
- **Radio segments**: adjoining rectangles with a 1 u `#CCDEFA` border; the
  selected segment fills with `prey.radio.active`.
- **Slider**: 100x16 u; a dark rail with pale tick dots and a ring knob
  (`sliderbackground.tga`, `sliderbutton.tga`).
- **Scroll bar**: a pale `#ADC5E3` rail with rounded caps and a `#BDD3F0`
  thumb.
- **Edit field**: a `prey.list.wash` rectangle with `prey.text.value` text at
  0.33 that turns white on hover; the save-name field is white throughout.
- **List**: column headings in white on `prey.list.wash` cells with a 1 u
  black border; rows in `prey.text.list` at 0.25–0.34; the selected row gets
  `prey.list.selection` and its outline.

### Progress bar

`bottombar.tga` (512x32 texels) is a claw-ended capsule: a socket ring at each
end and a slim rail with small rivet groups between them. Only the loading
screen uses it, as the progress outline (304x30 u) around a 256x12 u fill.
Despite its name it is not the home bottom bar, which is a claw frame.

## 7. Components and interaction states

| Component | Rest | Hover or focus | Press | Unavailable |
| --- | --- | --- | --- | --- |
| Main navigation | Label `prey.text.nav`; bar 0.60 | Label `#CCE6FF`; bar to 1.0 and 5 u toward the arc (6 u on the fourth entry); label 6–9 u toward the arc; 150 ms | `guisounds_menu_clickin` on press; action on press (Resume on release) | Hidden (Resume Game without a recent save) |
| Bottom-bar action | `prey.text.bottom` | `#CCE6FF` | Click sound | Hidden in game |
| Button | Label `#CCDEFA`; graded plate | Label white; `rollover_*` plate | Click sound | Label 0.30; `noevents 1`; still drawn |
| Setting row | Label white 0.9, value `#B8C9E6` 0.9 | Value white; plate unchanged | Choice advances; no script sound | Value at 0.40 |
| Check box | Border `#B8C9E6` 0.9 | Border white | Toggles the cross | Hidden or 0.40 |
| Radio segment | Border `#CCDEFA`; clear fill | Label white | Fills `#99ABC7` 0.7; `guisounds_menu_tick` | — |
| Tab | Label `#B5C9E3` 0.7 | Label `#CCDEFA`; plate tinted | `guisounds_menu_tabflip`; becomes active (label white) | — |
| List heading | White | Gold `#E6CC73` (server browser only) | Sorts (server browser only) | — |
| List row | `#A6BAD4` | — | Selected: 0.30 wash and outline | — |

Interaction never changes hue in the front end: everything brightens toward
white. The navigation's slide toward the arc is the only positional hover
response; other controls respond with colour and plate art only.

An active tab and its page are one surface (section 6): no line, gap or
change of colour parts them in any state.

Keyboard and controller focus must look the same as hover. The stock has no
separate focus state; a replacement uses the hover treatment plus a rim at full
`prey.rail` so focus stays visible when the pointer rests elsewhere.

## 8. Motion and sound

### The stock opening

`AnimPortalIn` (`guis/mainmenu.gui:126`) plays whenever the menu opens, out
of game and in game, in the stock and in openPREY today. Section 12.2 keeps
it for the menu opened in game and replaces it out of game with the entrance,
once that is built.

| Time | Event |
| --- | --- |
| 0 ms | Everything hidden except the back portal model, a point at the centre (320,240 u) |
| 100 ms | The portal grows to fill the canvas over 200 ms |
| 300 ms | The portal model's view offset moves from −120, 0 to −43, 7 over 200 ms, swinging its rim to the leading edge |
| 500 ms | The front portal model replaces the back one; the wordmark and navigation appear at once; the backdrop fades in from black over 100 ms; menu music starts |

The music loop is restarted every 320 s for a 318 s track. When the menu opens
in game (`noIntro`), the frozen game frame (`_menushot`) stays visible around
the opening portal until 500 ms, so the portal appears to tear open the game
itself; from then on the in-game menu shows the same space backdrop.

### Navigation hover

Hover runs 150 ms (bar slide, bar alpha, label slide); leaving runs 200 ms.
The label's colour changes at once. Both use linear interpolation.

### Sub-menus

| Page | Growth | Duration |
| --- | --- | --- |
| New Game, Exit, Quit Game, Mods | From the bottom bar (180,438,450,32) to the small frame (180,200,376,270) | 500 ms ease-in-out |
| Options, Load Game, Save Game, MultiPrey, Credits | Bottom bar → full-width bar (10,438,620,32) in 200 ms, then → full page (10,10,620,460) | 200 ms linear + 500 ms ease-in-out |

- Opening a full-screen page hides the wordmark and swings the front portal
  model's view offset from −43 to −15 over 400 ms; closing reverses it, starting
  300 ms in.
- The title bar of a full-screen page appears when the vertical growth starts.
- Closing reverses the growth; the navigation reappears when the frame is back
  in the bar (500 ms or 700 ms).
- The navigation hides the moment a page starts to grow, so it takes no
  input. `desktop::inSubmenu` is set only when the growth ends; until then
  Escape still closes the whole menu. A full-screen page also disables its
  navigation entry for the 800 ms after it closes.

### Credits

The credits page scrolls 5300 u over 130 s. Each of its 50 title lines flies
in from x = 1000 u to x = 150 u over 500 ms (even ease-in-out) sheared to one
side, swings to the opposite shear between 400 and 500 ms and straightens by
600 ms; the shear peaks at 0.6. Names and headings appear in place. Headings
are `#CCDEFA`, titles `#D1E3FC` and names `#99ADC7` at 0.88. Lines fade 18 s
after they appear, over 900 ms, to 0 or to white 0.7.

### Ambient

- Stars: one additive layer static, one rotating very slowly and scrolling;
  both surged by `powersurge`.
- Sun: rotates at `time*0.01` and pulses with `solsurge` at 0.17 Hz.
- Sphere and Earth clouds: rotate or scroll inside their masks.
- Portal: the model's own animated materials.

### Sounds

| Sound | Use |
| --- | --- |
| `guisounds_menu_clickin` | Any press (125 uses) |
| `guisounds_menu_tabflip` | Tab change (43) |
| `guisounds_menu_tick` | List selection, server-heading sort, radio segment (21) |
| `guisounds_menu_cancel` | Cancel (8) |
| `guisounds_menu_slidein` / `slideout` | Full-screen page grows / shrinks |
| `guisounds_menu_slideinsmall` / `slideoutsmall` | Small page grows / shrinks |
| `guisounds_menu_connect` | Refreshing or filtering the server list |
| `guisounds_menu_volumetick` | Volume slider |

Use counts are for the retail main menu and `mpmain`. In openPREY's copies
the three added Video pages bring `clickin` to 128 and `tabflip` to 46, and
`tick` falls to 18 with the three Texture Quality segments (section 12.1).

### Reduced motion

A reduced-motion setting keeps the order of events and drops their travel: the
portal appears at full size, the 3D backdrop appears at rest without its
entrance, pages fade in place over 120 ms instead of growing, the navigation
brightens without sliding, and ambient rotation stops.

## 9. Screen composition

| Screen | Composition |
| --- | --- |
| Home, out of game | Portal rim at the leading edge; stars, Sphere and sun, Earth's limb (painted layers today, the 3D bodies of section 12.2 once built); wordmark; arc with New Game, Load Game, MultiPrey, Options, Exit (and Resume Game when a recent save exists); bottom bar with Updates, Credits, Mods |
| Home, in game | Same backdrop; Resume Game, Quit Game, Save Game, Load Game, Options, Exit; bottom bar with Credits only |
| New Game | Small frame: title bar "Start a New Game", heading "Choose Skill", Tommy's portrait (110x110 u), Normal and Cherokee buttons (Cherokee is the harder "wicked" mode, drawn at 0.30 and inert until unlocked; Casino appears after the Roadhouse), a description on hover, bottom title "Return to Main Menu" |
| Load Game | Full page: a three-column list (Name, Date, Time) in a framed table beside a level-shot frame, Time Played, Load and Delete buttons |
| Save Game | Full page: the same list, a captioned name field and one 145x25 u Save button |
| MultiPrey | Full page with top tabs Player Settings, Create Server and Find Servers; Player Settings has Player Name, Data Rate and Auto Weapon Switch rows over the player-model picker (openPREY hides the stock Game Key Status row); Find Servers holds a server table (status icons, Server, Players, Ping, Type, Map), Quick Refresh, Refresh All, Internet/LAN segments, a details panel with side tabs, PunkBuster state, Join Game |
| Options | Full page with four top tabs (Controls, Game Options, Video, Audio). All but Audio have side tabs (Controls: Movement, Combat, Weapons, Look, System, MultiPrey, Profiles; Video: the stock Video, Advanced 1 and Advanced 2 pages plus openPREY's Display, Post FX and Advanced FX). Each page is a header bar, then setting rows on a 30 u pitch. Bottom title: Return to Main Menu, Reset to defaults. Apply Changes is a button on the Video page |
| Exit / Quit Game | Small frame: "Are you sure?", Yes and No; Exit adds "Exit to Operating System" above the prompt |
| Dialog: Reset Defaults | 0.80 black scrim; a 360x250 u claw frame with a centred title, explanation, five check boxes and two buttons |
| Dialog: confirmations | Load, delete, overwrite, restart-required and PunkBuster notices: 0.40–0.50 black scrim; a 360x140 u claw frame at 142,132 with a message and buttons |
| Credits | Full page: the wordmark, then sheared fly-in credit lines |
| Mods | Small frame: a list and Load MOD |
| Loading | Level art across the screen, a 0.55 black name band at the top with the level name in the display face, an objectives panel (430x74 u at 20,348, black 0.45, text 0.28), a status line (0.40) and a claw-ended progress bar at the foot |
| Death (`restart`) | The star field alone, fading in from black over 1 s: no Sphere, Earth or portal. The wordmark at 60,80 (510x35 u) and a 280x220 u frame at 172,184 with Load, Restart and Main Menu buttons (150x30 u, 0.40) |
| Connecting (`netmenu`) | A small frame titled "Connecting to Server" with Cancel |
| In-game multiplayer (`mpmain`) | Status row, top tabs, a chat panel with Say Global, Go to Main Menu and Disconnect buttons; no portal |
| Help (`help`) | A keyboard map in a frame; six tabs, each tinting its page of binding rows its own colour (red, blue, green, yellow, aqua, orange) |

The front end is composed around the Sphere: the navigation lives on the
leading side, pages appear on the central axis, and nothing covers the
wordmark except a full-screen page.

## 10. HUD and in-game overlays

Prey's HUD shows state through Tommy's body, not through numbers. There are no
numerals for health or ammo: his silhouette fills with blood and spirit, ammo
is a pair of slim meters, and the weapon bar appears only while switching.
Tommy's equipment is drawn as steel-blue line art on dark translucent fills;
red appears only for danger. The HUD GUIs are `guis/hud.gui` and its fragments
in `guis/hud/`, `guis/mphud.gui`, `guis/scoreboard.gui` and `guis/cursor.gui`
(`def/player.def:195-196`).

### 10.1 Single-player composition

| Element | Rect (u) | Construction | Source |
| --- | --- | --- | --- |
| Health figure | 35x90 at 30,373 | Tommy's standing silhouette (`hud/tommy.tga`, visible about 26x82 u) with an outline; fills bottom-up | `hud/hud_healthbars.guifragment:11-15` |
| Spirit figure | 35x90 at 23,369 | The same silhouette 7 u left and 4 u up, behind the health figure | `:5-9` |
| Lighter | 14x60 at 74,402; Zippo 30x30 at 85,432 | A small mirrored meter with a red-to-yellow heat fill and a flame glow | `hud/hud_lighter.guifragment:5-43` |
| Ammo meters | 21x100 at 610,368 (592 when an alternate bar shows) | A tall capsule with a chamfered top and a hooked ring foot; an 8x66 u fill rises from the foot | `hud/hud_ammobars.guifragment:12-100` |
| Weapon bar | 490x60 at 75,5 | Seven 70x60 tiles, wrench to rocket launcher, sheared `0, -0.22` (about 12° forward); the end tiles are capped | `hud/hud_weaponswitchicons.guifragment:14-333` |
| Pickups | column 32x320 at 600,36 | Up to ten 32x32 icons, newest on top; wide icons grow leftward to 64 u and stand upright | `hud/hud_itempickups.guifragment:41-111` |
| Crosshair | 32x32 at 304,224 | Eight styles; red `#FF3C00` locked variant over damageable targets | `cursor.gui:7-104` |
| Damage arcs | three 128x64 arcs on 480x480 rotators centred on the screen | Thin red crescents about 92 u wide at radius 134–150 u, turned toward the attacker | `hud/hud_damageindictor.guifragment:7-53` |
| Boss and progress bar | 230x36 capsule at 210,70 when shown | Mirrored halves of `bossbarbg` around a 210x20 blood-red fill; caption in the alien face | `hud/hud_progressbar.guifragment:46-79` |
| Tips | 420x164 window from 220,200 | A keycap image (96x48) with its key label, the tip text starting at the screen centre | `hud/hud_tips.guifragment:51-97` |
| Subtitles | 640x50 line at y 400, centred | Body face 0.5, white with shadow | `hud/hud_subtitles.guifragment:5-36` |
| Letterbox | 50 u black bars | Hides everything except tips and subtitles during scripted scenes | `hud.gui:36-52`; `src/Prey/game_playerview.cpp:7-8` |

The groups are edge clusters: health and lighter at the bottom left, ammo at
the bottom right, pickups down the right edge, weapons and the boss bar at the
top centre. Under aspect expansion openPREY pins the health figures and the
lighter to the bottom-left corner, the ammo meters and the pickup column to the bottom-right
and subtitles to the bottom edge (`screenalignx`, `screenaligny`). Keep every
cluster on its edge or corner and the crosshair, damage arcs and tips on the
true centre.

### 10.2 Palette

| Token | sRGB / alpha | Use |
| --- | --- | --- |
| `hud.ink` | `#A0B2CA`, highlights to `#B0D0F8` and `#CAE1FF` | Meter and tile outlines, icon line art |
| `hud.well` | `#1C242D` at 0.50 (tiles), black at 0.36 (meters) | Dark translucent fills |
| `hud.health` | `#990000`; empty figure `#4D0000`; pulse `#FF0000` | Health figure |
| `hud.health.over` | `#BFD9FF`; pulse white | Health figure above 100 maximum health |
| `hud.spirit` | `#4D66B3`; empty figure `#001A4D`; pulse `#8099FF` | Spirit figure |
| `hud.ammo` | `#8CA6CC` at 0.73 (alternate `#5973BF` at 0.75) | Ammo fills |
| `hud.ammo.line` | `#8CA1E6`; alternate `#596BFF` at 0.8; low `#731A1A` | Weapon tile ammo lines |
| `hud.selector` | `#748DA8` rim at 0.75, `#4C5BD3` fill at 0.15 | Selected weapon tile |
| `hud.icon.idle` / `hud.icon.empty` | `#BFBFBF` / `#BF0D0D` (selected `#FF4D4D`) | Weapon icons |
| `hud.danger` | `#FF0000`; low-ammo flicker `#FF1A00`; damage arcs `#DA0000` | Low and empty states |
| `hud.boss` | `#A01800` fill in a `#85A6C9` / `#323E4B` capsule | Boss and progress bar |
| `hud.crosshair` | `#A5B7D9` to `#D1D8E5`; locked `#FF3C00` | Crosshairs, drawn with an inverting blend at 0.35 |
| `hud.text` | White; shadowed on tips and subtitles, plain on the autosave line | Tips, subtitles, autosave |

Crosshairs use `blend gl_one_minus_dst_color, gl_one_minus_src_alpha` at 0.35,
so they invert whatever is behind them and stay visible on any surface. Keep
that behaviour in any replacement reticle.

### 10.3 Shape and type

- **Tommy's kit**: steel-blue line art, chamfered corners (the weapon tile's
  top trailing corner, the item icon frame's bottom trailing corner, the ammo
  bar's bottom trailing corner), hooked meter feet, and a forward shear on the
  weapon bar and pickups (`shear 0, -0.22`). Key labels shear the other way
  (`shear 0, 0.22`).
- **The body face** carries all HUD text, from 0.25 (multiplayer names,
  chat, scoreboard rows) through 0.3–0.4 (key labels, tips, scores) to 0.5
  (subtitles). The display face does not appear in the HUD.
- **The alien face** writes the boss and progress caption and the shuttle's
  status text, apart from its low-health and low-power warnings, which use the
  body face. It is Hider script the player is not meant to read.
- **Comic-book icons**: the frag skull, timer stopwatch and Zippo have heavy
  pale outlines with a black outer stroke.
- HUD strings are Title Case ("Frags", "Team Red"); world-console titles are
  all capitals ("WALLWALK ACTIVE").

### 10.4 Motion and feedback

| Behaviour | Timing | Source |
| --- | --- | --- |
| Weapon bar | Visible 2000 ms after a change, fades over the next 1000 ms; the selected icon swaps at once from 50x28 to 60x35 u | `hud_weaponswitchicons:9-51` |
| Health or spirit pickup | Outline and fill pulse to the pulse colour and back, 300 + 300 ms | `hud_healthbars:88-138` |
| Maximum-health pickup | A pale 2x ghost of the figure grows in 500 ms, holds to 2500 ms, shrinks in 300 ms | `:245-260` |
| Low health | At 25 or less the health fill blinks on a 667 ms triangle. Below 25, outside spirit walk and death walk, a full-screen hurt overlay and a heartbeat loop join it | `:148`; `src/Prey/game_playerview.cpp:577-584`; `src/Prey/game_player.cpp:766-777` |
| Low ammo | The meter's foot dot pulses on a 333 ms triangle; the frame flickers on a random 1667 ms table | `hud_ammobars:22-39` |
| Out of ammo | Meter frame and well turn red at once | `:28-34` |
| Damage | Each arc fades from 1 to 0 over 1000 ms | `hud_damageindictor:17-19` |
| Pickups | Fade in over 500 ms, out from 1750 to 2000 ms, faster when queued; the column slides down | `src/Prey/game_player.cpp:677-727` |
| Tips | Fade in and out over 300 ms | `hud_tips:14-48` |
| Subtitles | Fade in and out over 1000 ms | `hud_subtitles:13-24` |
| Boss bar | Slides 75 u down over 800 ms while its frame fades in over 2000 ms | `hud_progressbar:5-18` |

The HUD plays no sound for weapon switches or pickups; the player entity plays
`player_healthpulse`, `player_spiritpulse` and the low-health heartbeat.

### 10.5 Spirit walk and death walk

- Spirit walk swaps the two figures over 700 ms: the blue spirit figure moves
  in front of the red health figure.
- The world takes the spirit grade: tint `#80CCFF` (0.5, 0.8, 1.3), 25%
  desaturation, contrast 1.9, a slight blur and four additive swirls
  (`materials/decals.mtr:366-434`).
- Death walk desaturates fully and adds a radial blur
  (`materials/decals.mtr:437-471`); damage arcs hide.
- Spirit blue (`#4D66B3`, `#8099FF`, `#80CCFF`) is reserved for the spirit:
  do not use it for other HUD states.

### 10.6 Multiplayer HUD and scoreboard

- The multiplayer HUD keeps the health, spirit, ammo and pickup groups and
  adds a top-right standings box (110x64 u in deathmatch, 110x31 u in team
  games; black 0.5 with a `#66738C` rim),
  frag and timer icons with `#B3CCE6` counts, a vote line, a game-state line,
  the player's name under the figure and the aimed player's name above the
  crosshair. Its weapon bar uses 60x50 u tiles without enlargement.
- Team colours: red `#FF0000`, blue `#3380CC`, deathmatch yellow `#FFCC1A`
  for names; `#CC3333` and `#3333CC` in the standings.
- The scoreboard is a 477x355 u slate panel (`#334D66` at 0.6, 1 u `#B3CCE6`
  border) at 75,90: Name (186 u), Frags, Wins and Ping (91 u each) over
  black 0.35 column wells. Deathmatch lists 8 rows on a 30 u pitch with
  18 u portraits; team games list two blocks of 8 rows on a 15 u pitch under
  solid red `#BF0000` and blue `#0000A6` heading strips carrying each team's
  score. The local player's row takes a `#B3CCE6` 0.2 bar. Rows use the body
  face at 0.25, headings 0.3.
- Chat shows ten lines (600x15 u from 0,220) at 0.25 with shadow; the message
  field is a tabbed panel (Global, Team) in `#4A5263` with a `#B3CCE6`
  bordered field.

### 10.7 Vehicles and weapon displays

- **Shuttle HUD** (`guis/vehicles/shuttlehud.gui`): four groups fly in over
  1000 ms from the screen edges. Hider tech, not Tommy's: ivory bone brackets
  and ribbed fins (`#F8F0C8`), a rotating compass dial, curved rung gauges for
  health (red to `#FFCC4D`), power (white to `#0099FF`) and velocity (green to
  red), red-orange claw crosshairs (`#FF2F00`) and alien-script status text in
  `#FFFFF2`; the two low warnings are in the body face, `#FF3B1A`. The bone
  art shimmers on a 1000 ms `powersurge2` cycle.
- **Weapon-mounted GUIs** are drawn on the view models: the auto cannon's
  curved heat gauge, the Hider weapon's olive panel, the Soul Stripper's three
  canisters (plasma red-yellow, rail blue-white, sunbeam orange-cream, freeze
  aqua). The rifle's scope is a full-screen overlay: section 10.8.

### 10.8 The rifle scope

Two weapons zoom. The Hunter rifle's alternate mode raises a scope with a
full-screen overlay, `guis/weapons/sniperoverlay.gui` (named by
`gui_zoomOverlay` in `def/weapon_rifle.def`). The spirit bow narrows the view
to 75° over 1500 ms and has no overlay.

The scope is a living eye, Hunter technology like the hand lock of section 11.
The view is seen through a veined lens whose red tint runs in bands, and a
ring of instruments in reds and oranges grows out of its centre. It carries no
steel blue, and no text in the body face except the key tips.

The measurements below come from the stock art and from captures of the stock
overlay as openPREY draws it, over black and over mid-grey (Appendix A).

#### Parts

The parts share one centre. The script offsets several rectangles to cancel a
constant scroll in their materials; in the captures they centre on 317,237,
3 u from the screen centre. Radii are from that centre, at rest. Angles run
clockwise from the top. Except for the lens and the reticle, every part is
added to the view, so its colour is given as it appears over black.

| Part (material) | Geometry (u) | Colour | Life |
| --- | --- | --- | --- |
| Lens tint (first stage of `models/weapons/rifle/scopeview`) | The whole canvas, in horizontal bands 15 u to a cycle | `#622222`, from 0.05 to 0.26 opaque across each band, the same at every zoom | Scrolls one canvas height a second |
| Lens veins (its three other stages) | The whole canvas: a fine vein network, clear at the centre and darker outward. At full strength it takes 0.07 of the view's brightness at 195 u, 0.34 at 260 u and 0.6 beyond 340 u | Veins `#301313` to `#4A2D2D`; strength is the zoom value | Three copies turn at 0.015, −0.015 and −0.01 turns a second |
| Iris tint (`scopeviewbars`) | A disc out to 227 u, clear inside 36 u, strongest near the rings | `#6E0000` at 0.3: about `#250404` at 100 u | Flashes with the heartbeat. Snaps to a third of its size for about 50 ms twice in every 5 s, 0.57 s apart |
| Hatching (`rifle_barrel1`) | Fine radial lines from about 120 u out to a rim line at 165 u | Crimson lines; rim `#77211B` | Brightness swings between half and full every 667 ms |
| Outer ring (`rifle_barrel2`) | A line at 175 u | `#7C2015` | With the hatching |
| Compass (`rifle_letters`) | About sixty groups of alien letters round a circle from 155 to 169 u, tops outward | `#812E1E` at rest | Turns against the clock as the weapon's yaw grows, degree for degree. Flashes on a 1.11 s heartbeat: 0.6 at rest, full for one eighteenth of each beat |
| Clamps (`rifle_barrel_clamps`) | Three, at 0°, 120° and 240°. Each is a 17° sector between two bright edges, fading in from about 112 u, under a cap 55 u wide at 180 to 190 u, just outside the outer ring | The art's grey under a tint of 0.7, 0.3, 0 that cools to 0.6, 0.1, 0: `#743200` to `#631100` at its brightest | Steady |
| Reticle (`rifle_barrel3`) | A ring 17.5 u in radius and three wedges at 0°, 120° and 240° that cross it: 9 u wide at 26 u, tapering to 3 u at 10 u | It multiplies the view: dark brown over a light scene, unseen over a dark one | Flickers 5% in size |
| Glow (`rifle_barrel`) | About 10 u in radius at the centre | `#E80000` | Random flicker; its size breathes by a sixth |
| Zoom scale (`rifle_number2`) | An outlined crescent on the leading side. Its outer edge is 238 u from the centre, from 44° below level to 44° above; it is 2 u thick at its top and 14 u at its foot, with a hooked tip at each end. Sixteen rows of alien numerals stand outside it in a column, x 60 to 100, y 47 to 425 | `#6F271D`; the numerals dimmer | Steady |
| Zoom pointer (`rifle_number3`) | A wedge 17x7 u that rides the crescent at 231 u, brightest at its outer end | `#FF3410`, fading inward | Angle above level: 126° × (zoom value − 0.3) − 43° |
| Text block (`rifle_number1`) | Four centred lines of alien text within x 552 to 608, y 128 to 220 | `#501F19` | Steady |
| Key tips | Two rows at 400,30: a keycap 96x48 u with its key in the body face 0.3, sheared 0.22, and the tip in the body face 0.4, `#A0B2CA` with shadow | — | Each time the scope is raised in single-player with tips on; fade in over 300 ms |

The clamp art's alpha channel holds a second drawing, a clawed head with an
oval socket. The material's blend ignores alpha, so the game never shows it:
the clamps are the wedges.

#### Zoom

- The field of view runs from 5° to 40° in 5° steps and starts at 20°; the
  last value is remembered. Each step retargets the view over 75 ms and plays
  `weapon_rifle_scope_click`.
- The zoom value is `1 − 0.7 × (fov − 5) / 35`: 0.3 at 40° and 1.0 at 5°. It
  sets the strength of the lens's veins, so the eye closes in as the view
  narrows, and the pointer's angle.
- Zooming in raises the pointer: it stands 43° below level at 40°, 7° above
  at 20° and 45° above at 5°, an 88° sweep that matches the crescent.

#### Raising and lowering

| Time | Event |
| --- | --- |
| 0 ms | The lens is there at once. The clamps grow from a point at the centre to full size in 300 ms and cool over 1000 ms. The iris tint fades in over 400 ms, the zoom scale and pointer over 1000 ms, the text block over 2000 ms. The view narrows over 75 ms. `weapon_rifle_raisescope` plays and `weapon_rifle_scopeloop` starts |
| 300 ms | The compass grows from the centre in 300 ms; the hatching, outer ring and reticle in 200 ms; the glow fades in over 500 ms |
| 2000 ms | Complete |

Captures at about 150 and 450 ms show the sequence in that order. Lowering
removes the overlay at once and plays `weapon_rifle_lowerscope`; the view
widens over 75 ms.

While the scope is up the rifle's own crosshair is off (`crosshair 0`), its
laser sight is drawn for other players and hidden from the scoped view, the
renderer's scope-view flag is set (`renderSystem->SetScopeView`) so that
materials can show a scope-only stage, and turning slows with the field of
view (`src/Prey/prey_weaponrifle.cpp:255-372`).

#### Design for openPREY

1. Keep every part, colour, blend and timing above. The scope is Hunter
   technology: no steel blue, no numerals or labels in the body face, and no
   added readouts such as range or ammunition.
2. Centre the instrument on the true screen centre and never stretch it. It
   is laid out on a 480 u square that scales with the screen's height, so it
   is a circle at every aspect. The stock sits 3 u up and toward the leading
   edge; that offset is a side effect of its materials, not a design.
3. Cover the whole screen with the lens. Run the tint's bands across the full
   width, and draw the three turning vein layers on a square as wide as the
   screen's diagonal, so that no turn bares a corner. The stock draws the
   lens on the 4:3 canvas only.
4. Keep the zoom scale, its numerals, the pointer and the text block with the
   instrument, at their canvas positions. They do not move to the screen's
   edges. The key tips stay at 400,30 on the canvas.
5. Rebuild the parts as vector or high-resolution art from these
   measurements. The stock textures are 64 to 512 texels across and soften on
   a modern display. Draw the clamps as the wedges the game shows, not the
   unused drawing in their alpha.
6. Keep the reticle as a multiply over the view, with the glow at its centre.
   It is the scope's character that the sight darkens the target, and the
   glow marks the centre when the scene is dark. The dim parts (`#501F19`,
   the numerals) are texture, not information.
7. With reduced motion the instrument appears whole in a 120 ms fade, the
   veins stop turning, the bands stand still and the flashes hold at rest.
   The compass and the pointer still move: they are readings.
8. The spirit bow keeps no overlay. The spirit realm has no instruments.

#### Aspect expansion as built

openPREY's `guis/weapons/sniperoverlay.gui` builds rules 2 to 4 with the stock
art, in the legacy GUI. The instrument, the zoom scale and pointer, the text
block and the key tips keep their canvas rectangles; the canvas scales
uniformly, so the instrument is a circle on the screen's centre at every
aspect, filling the height of a wide screen and the width of a tall one. The
lens is drawn in two parts whose stages are the stock `scopeview` stages
unchanged, split into `models/weapons/rifle/scopeview_lens_tint` and
`models/weapons/rifle/scopeview_lens_veins` (`materials/rifle_scope_aspect.mtr`):

- The tint is laid in whole 640x480 tiles: the canvas, one tile on each side
  for a wide screen and up to two above and below for a tall one, so the
  bands keep their 15 u pitch and their speed. Its texture wraps vertically,
  so the bands run on across tiles without a seam; it does not wrap
  horizontally, so the side tiles are mirrored (`matscalex -1`) to meet the
  canvas edge without one. The tiles cover aspects from 4:1 to 1:3.75.
- The veins lie on a square `gui::virtual_screen_diagonal` wide on the
  screen's centre, with their strength still the zoom value.

Laying the veins on that square moves their dark rim to the screen's corners.
The stock stretched them over the 640x480 canvas, so every point of the
canvas edge sat on the texture's rim, about 0.76 of the view covered at full
strength through the three layers. On the square only the corners do: at
full strength the middle of the top edge is about 0.24 covered and of the
side edge 0.56 at 4:3, 0.09 and 0.65 at 16:9. That is the cost of rules 2
and 3 together: a round field dark at the middle of a long edge is as dark at
that radius everywhere, over the instrument too, and a field small enough for
that leaves the corners bare when it turns.

### 10.9 Rules for HUD changes

- Do not add numeric health or ammo readouts to the stock HUD. An optional
  numeric mode belongs to a separate, clearly optional HUD preset.
- Keep the silhouette gauges and their red/blue roles, the steel-blue ink, the
  forward shear and the transient weapon bar.
- Keep danger red and spirit blue for their states; do not introduce warm
  accents for neutral information.
- Keep the alien face where the stock uses it; translating shuttle status
  text would change the game.

## 11. In-world device GUIs

Prey's world screens are the opposite of its front end: saturated, unstable
and mostly unreadable. Every device GUI authors a 640x480 desktop, but each
family has its own palette, shape language and motion. Never dress a device in
the front end's steel glass.

### 11.1 Families

| Family | Members | Identity |
| --- | --- | --- |
| A. Roadhouse (Earth, 2006) | `guis/roadhouse/*`: blackjack, poker, slots, "Rune Man", marquees, jukebox, TV, clock | Bar-room consumer electronics: rounded CRT bezels, green felt, chrome reels, a blue jukebox dome; saturated primaries; the body face only; never translated |
| B. Sphere machines | `generic_1`, `generic_2`, `generic_unlock_1`, `forcefield*`, `alarm`, `eyestalk`, `wallwalk`, `gravity`, `elevator*`, `keyenter`, `keycode`, `itemcabinet`, `generictranslatable`, `off1`, `bsod`, `static*` | A black field framed by mirrored chamfered brackets, one large state icon (broken ring, iris, clamp, cellular field, triskelion, keypad), alien-script status words, and the shared overlay stack |
| B2. Bronze bone iris | `generic_3`, `portal_control` (projection eye, skinwrap, superportal, Keeper consoles) | No text: two mirrored bronze bracket panels around a four-frame bone-and-knuckle iris, sliding claw locks and blinking blue-violet lights |
| C. Information and propaganda | `noninteract_*`, `nia_trans_d` | Non-interactive wall screens: Mother slogans in two centred alien lines on a tinted copper frame; Earth and specimen scans in rust and cyan with target rings, oscilloscopes and digit rain |
| D. Biolab readouts | `guis/biolabs/*` | One hue per screen: cobalt and cyan (drone recharge), lime wireframe (Hider weapon), blood orange (mutate), hospital blue with a heartbeat (Jen) |
| E. Keeper fortress | `guis/keeperfortress/*` | A rust-brown riveted frame around grey pictograms; text and frames drawn with additive hologram materials |
| F. Hunter-hand lock | `hunterhand.gui` | A black tapered trapezoid in orange `#CF7D1C`; a handprint scan becomes a row of alien DNA letters |
| G. Hider briefing | `dialog_elhuit.gui` | Image only: a navy frame around an orange Sphere, Keepers, the superportal and Earth, with amber targeting rings |

No device GUI belongs to the spirit realm: `hunterhand.gui` refuses its scan
while the player is spirit-walking.

### 11.2 The Sphere overlay stack

The full stack, back to front, as `guis/forcefield.gui` builds it (`:37-110`
and `:206-219`; materials in `materials/guiresources.mtr:837-899`):

| Layer | Treatment |
| --- | --- |
| Half frames | One white line-art half panel drawn at 10,10,310,460 and again mirrored at 320,10,−310,460, tinted per device |
| Scanlines | A soft band tiled every 128 px, grey 0.7 at 0.5, scrolling up at 0.5 per second, window alpha 0.05 |
| Roll bar | One dark band about 120 u tall, tinted `#B3804D`, rolling every 5 s |
| Flicker | Black at `powersurge2[time*0.002]`: 0.05–0.25, a 500 ms jitter |
| Static | `static001` at 0.02, scrolling and rotating |
| Used | Black 0.8 dimmer once a one-shot console has been used |
| Status text and the hit window | Drawn over everything above |
| Damage | Static at 0.2 and a rolling V-hold bar at 0.4 while `gui::damaged`, over the text |

The stack makes Sphere screens look like unstable bio-electronics. The full
set appears on `forcefield*`, `gravity`, `wallwalk`, `keyenter` and
`generic_1`, which draws one whole frame instead of mirrored halves. Other
screens carry subsets: families D and E have only the scanlines, the roll bar
and the damage pair; `alarm`, `eyestalk`, `elevator*` and `keycode` have no
scanline, roll, flicker or static layer. A replacement keeps each screen's own
subset, including the damage pair where the stock has it.

### 11.3 Palettes

| Family | Measured colours |
| --- | --- |
| A | Labels white 0.8 with shadow; numbers teal `#1AFFE6`; button plates cyan `#00FFFF`, hover yellow `#FFFF00`; red suits `#FF0000`; clock `#B30000`; jukebox VU red to yellow |
| B ice | Frames `#80CCFF` at 0.7 (forcefield, eyestalk), `#66CCFF` at 0.7 (unlock), `#73A6FF` at 0.9 (wallwalk); text white 0.85 or `#BFD9FF` |
| B amber | `generic_1`: outer broken ring `#FF4000`, inner ring `#FFF299`, alien text `#FFE680`; organic frame art amber-brown (`#563702` to `#C17A05`); item cabinet `#FF9F0A` |
| B state | Go `#00FF00` / `#00CC00`, stop `#FF0000` / `#CC0000`; keypad hover `#A6FF33`, accept `#66E6FF`, invalid `#FF1A00`; elevator hover `#FF3300`, lamp `#FF4D00` |
| B2 | Frames `#FFD980` at 0.9 over bronze art (`#A48C5E`, peak `#FDE797`); lights `#687DDE` |
| C | Slogan text `#FFCC99` at 0.6; frame tints `#8099FF`, `#66CCFF`, `#CCFF80`, `#B34D66`, `#B3FF4D`, `#00B3FF` over copper (`#612B19`); scan bars `#CC4D1A`, `#CC8000`; readouts `#FFE680`, `#1AFFFF`; target rings `#FF4D1A` |
| D | Drone `#0B1A40` / `#1D77B4` with amber `#FFE680` text; Hider analysis `#E6FFCC` on lime `#708645`; mutate `#A72F0F` with `#33CCFF` DNA; Jen `#4D99FF` ↔ `#80CCFF` |
| E | Frame `#391C0C`; glyph flicker `#FF4D1A` and `#FFCC66` on a 20 ms `jitter1` cycle; alert `#FF1A1A` ↔ `#FFCC80` |
| F | `#CF7D1C`, `#40260A`, `#423D24`, `#575233` |
| G | Frame `#223B4D`; Sphere `#BF581B` (peak `#F9C968`); rings `#FFB366` at 0.2–0.3; Keeper outlines `#80CCFF` |

Across the ship, cold ice blue means machinery and warm amber, bronze and
rust mean organic structure. Green and red keep their go and stop meanings.

### 11.4 Type and the translation mechanic

- Sphere devices write in the alien face; the Roadhouse writes in the body
  face. Status words run from 0.5 to 0.9, slogans from 1.0 to 2.0, keypad
  keys at 1.4, keypad readouts at 1.8 and the code display at 3.8. Status
  words are mostly all capitals ("FORCEFIELD ACTIVE"); case only shows after
  translation.
- The alien face is case-insensitive, and its letter widths track the body
  face, so an alien string is 7–10% narrower than the same English string.
  Its digits are dotted round forms, unlike its letters.
- The Hiders count in octal: the keypad has keys 0–7, countdowns print in base
  8 and the Hider-analysis and drone digit columns contain only 0–7
  (`guis/keyenter.gui:203-444`, `src/Prey/game_console.cpp:542-547`). The
  rule is not universal: `biolabs/mutate1.gui` and the Earth-scan readouts
  show 8 and 9.
- **Translation.** Device text is an ordinary English string drawn in the
  alien face. When Talon lands on a console's perch, the game ramps the GUI
  float `translationAlpha` from its current value to 1 over 1000 ms, linearly,
  and plays `console_generic_translation`; when Talon leaves, it ramps back
  to 0 silently (`src/Prey/game_console.cpp:12,330-386`,
  `src/Prey/game_talon.cpp:1679-1713`). A vehicle HUD starts translating
  1000 ms after its local pilot enters and ramps over a further 1000 ms
  (`src/Prey/game_vehicle.cpp:567-608`). No stock GUI reads
  `translationAlpha`; the engine draws the reveal.
- **The reveal.** openPREY draws it as the 2007 engine does (`PREY.exe`
  `idWindow::DrawText` and the window's `DrawTranslation`, read from the
  binary; `src/ui/Window.cpp` `idWindow::Draw`). Each redraw the GUI reads
  `translationAlpha`, clamped to 0–1. Every window in the alien face then
  draws its text, shadow included, at its own alpha times
  1 − `translationAlpha`. Each of those windows not marked `notranslation 1`
  also draws the same string in the default face (`fonts`, the body face),
  6 u higher, in its text colour at alpha `translationAlpha` itself, with no
  shadow. The English is not multiplied by the window's alpha, so a
  half-alpha digit readout translates at full strength and the shuttle's
  blinking crash warning holds steady once translated. At 0 nothing changes;
  between, the two faces cross-fade; at 1 only English remains.
- `notranslation 1` only withholds the English: the alien text still fades,
  so biolab digit columns are gone at 1 and return as the console
  untranslates. `notranslation 0` (`guis/biolabs/jennyscan1.gui:180`) is the
  default. Retail parses the key into a window flag; openPREY keeps it as the
  window variable earlier builds made, so saved games keep their layout, and
  reads it once the window is parsed. Windows in any other face never change.
- Two retail paths stay unimplemented because nothing shipped uses them. The
  state bool `translationProject` selects a projected variant (alien text
  holds 20%, the English drifts with time by the `gui_translationOffset_x`,
  `_y`, `_z` and `_vertical` cvars); game code only sets it false
  (`src/Prey/game_vehicle.cpp:600`). `idUserInterface::Translate(fontname)`,
  reached by the GUI command `setfont` (`src/Prey/game_console.cpp:257-266`),
  re-fonts every window in retail; no stock GUI sends `setfont`, and
  openPREY's slot of that name looks up language strings.

### 11.5 Interaction and motion

| Pattern | Timing | Example |
| --- | --- | --- |
| Whole-face button | — (most Sphere devices are one invisible hit window, 30,30,580,420, over decorative art) | `guis/forcefield.gui:168-172` |
| Ring snap | Rings rotate home in 500 ms; ticks flash 200/400 ms; a ping ring grows and fades over 1000 ms | `generic_1.gui:97-177, 220-221` |
| Clip-wipe text | A text window's width grows from 1 u over 1500–2000 ms, revealing left to right | `generic_1.gui:274-296` |
| Iris step | Four frames cross-fade 200 ms each; locks slide 55 u (right) and 59 u (left) in 300 ms | `generic_3.gui:64-150` |
| Status pulse | Alpha 1 → 0.2 in 200 ms, back in 150 ms, loop 700 ms | `alarm.gui:112-127` |
| Gravity flip | The slider rotates 180° over 1800 ms | `gravity.gui:250-302` |
| Keypad | Key hover in 70 ms; accept line fades in over 500 ms; verdicts in the alien face | `keyenter.gui:14-232` |
| Stutter-on | 50 ms alpha steps (0.5, 1, 0.4, 1) before a fade | `dialog_elhuit.gui:72-104` |
| Data rain | Four digit strings take turns, 50 ms each, on a 200 ms loop | `biolabs/hideranalyze.gui:306-386` |
| CRT power (Roadhouse) | The screen collapses to a point at 320,240 in 300 ms | `roadhouse/blackjack.gui:49-71` |
| GAME OVER (Roadhouse) | Grows from 0.2 to 3.2 over 4000 ms while cycling six hues | `blackjack.gui:954-988` |

Idle and translation sounds come from the entity definitions
(`console_generic_idle`, `console_generic_translation`; `def/consoles.def`).
Activation, deactivation and keypad sounds are `play` commands in the GUI
scripts: `console_generic_activate` and `_deactivate`, the keypad's
`guisounds_menu_keyclick`, `console_keypad_victory` and `_failure`. The
Roadhouse uses `console_cards_*`, `console_slots_*`, `console_arcade_*`,
`console_jukebox_music*` and `console_tv_*`.

### 11.6 Cursor and hand

Focusing an interactive world GUI lowers the weapon and raises Tommy's hand,
which plays a press animation on each click; the Hunter hand item swaps in an
alien hand (`def/player.def:490`, `def/items.def:90`). The 2D cursors are a
faceted silver-blue arrow, a white pointing hand and the organic chrome menu
cursor (`guis/assets/guicursor_*.tga`). Roadhouse cabinets ask for the
"Earth" cursor (`cursor 2`). The retail mapping of cursor numbers to images is
not in the data; retail `PREY.exe` 1.4 loads them as arrow 0, hand 1 and menu
2, as Doom 3 does.

All three are 32-texel art. Retail draws the pointer's box at 16 units of the
640x480 canvas on a menu GUI (`menugui 1`) and at 32 on a world GUI, half
Doom 3's 32 and 64 (`idUserInterfaceLocal::DrawCursor` in `PREY.exe` 1.4). The
hotspot is the box's top-left corner. With aspect correction the box stays
square and scales with the canvas height, as the menu does.

### 11.7 Rules for device changes

- Keep each family's palette and shape language; never mix families on one
  screen.
- Keep the overlay stack and its timings on Sphere screens.
- Keep alien text alien until translated, octal numerals octal, and
  `notranslation` windows untranslated.
- Retail authoring slips (`"1 1sd 0 1"` in `blackjack.gui:289`, a blue
  channel of 2 in `droid_recharge.gui:448`, a no-op hover in `generic_1`)
  are recorded in Appendix C; fix them only on purpose and say so.

## 12. openPREY additions and modern direction

### 12.1 Current additions

openPREY's overrides in `content/basepr/pak0/` change thirteen stock scripts:
`mainmenu.gui` and its Options, MultiPrey and Mods fragments, `restart.gui`,
`map/loading.gui`, `hud.gui` and its health, ammo, pickup and subtitle
fragments, `subtitles.gui` and `weapons/sniperoverlay.gui`. `pak1` adds
sixteen images, fifteen of them edge tiles. The overrides extend the stock
vocabulary rather than replace it:

- **Aspect expansion.** Wide and tall screens show more space rather than
  black bars.
  - *Main menu.* The stock layers draw over black, as in the stock. The star
    layers widen with the screen (`naturalmatscale` holds their density).
    Earth continues through its window's edge slices (`preymenu/earth_left`,
    `_right`, `_bottom`); their materials repeat the stock Earth stages, so
    the drifting clouds run on across the join. The portal's view spans the
    screen (section 3; `canvasfill`, section 12.2).
  - *Death screen.* `restart.gui` keeps the flat painting with its own edge
    slices (`background_left`, `_right`, `_top`, `_bottom`).
  - *Edge tiles.* Every tile is generated from the retail art by
    `tools/assets/generate_menu_backdrop_tiles.py`, which continues each
    painting's Earth in polar strips about its disc, so the limb, glow and
    foreshortening carry on as painted. The side tiles are the faithful
    ones; the bottom tiles, seen only on screens taller than 4:3, are
    plainer.
  - *Colour fills.* A colour fill over exactly the 4:3 canvas (a dialog's
    scrim, a fade, `msg.gui`'s dimmed desktop) covers the expanded canvas,
    so dialogs dim the whole screen.
  - *Loading screens.* `guis/map/loading.gui` and the session's fallback
    screen compose the levelshot, or `guis/assets/loading/loading`, with its
    `_left`, `_right`, `_top` and `_bottom` tiles into one picture that fills
    the canvas, as openQ4 does. A picture without both of the tiles its
    window needs is drawn at 4:3 instead; stretching its edge columns
    smeared it. The composite is cached per source and window size. The
    session finds the picture as retail does (`levelshot-capture.md`): a
    save's own screenshot when a save is loading, else the map's loading art
    `guis/assets/loading/<map>`, else that art from an addon pak, else the
    generic picture. `pak2` carries recaptures of 32 of them with their
    tiles, taken at the retail cameras.
  - *HUD and scope.* HUD groups and subtitles pin to screen edges with
    `screenalignx` and `screenaligny` (section 10.1). The rifle scope's lens
    covers the whole screen (section 10.8).
- **Loading.** The level name comes from `gui::loading_levelname`, an optional
  author line sits under it (display face 0.3, `#D9D9FF` at 0.75), and
  per-map backgrounds can fill the canvas (`matcanvasfill`).
- **Video settings.** Six side tabs, built from stock setting rows, choices,
  sliders and edit fields:
  - *Video* keeps the stock Detect plate and replaces the three Texture
    Quality radio segments with a Quality Preset row over the engine's nine
    presets (Minimum to Maximum), which three segments cannot hold. Video
    Resolution lists what the selected display reports (Desktop Native, its
    modes, Custom) instead of the stock fixed list. Render Scale and Vertical
    Sync join Full Screen, Brightness and Gamma.
  - *Display* is new: Rendering API, Monitor, Fullscreen Mode, Borderless
    Window, Refresh Rate, Frame Rate Limit, Span All Monitors, and Window
    Size and Custom Resolution as two numeric edit fields each (44x19 u,
    `prey.list.wash`, either side of an "x") centred in the value column.
  - *Advanced 1* gains Shadow Maps; Vertical Sync moved to Video and
    Antialiasing to Post FX. Shader Detail is drawn at 0.40 while shader
    programs are off or the Vulkan backend is active, where it has no effect.
  - *Advanced 2* drops High Particle Detail until the engine reads
    `r_lowParticleDetail`.
  - *Post FX* and *Advanced FX* add multisampling (to 16x), post-process
    anti-aliasing, SSAO, bloom, HDR tone mapping, CRT, motion blur, colour
    saturation and contrast.

  A side-tab column shares its height, less the 40 u margin, among its tabs:
  the six Video tabs are 55 u tall (`textaligny 21`), where the stock three
  were 110 u (`textaligny 30`). A change that needs a video restart lights
  Apply Changes on every page, as in the stock.

New pages and settings follow that precedent: build them from the stock plates,
rows, tabs and faces, at stock sizes and colours, inside the claw frame.

### 12.2 The 3D backdrop and entrance

**Status: specified, not built.** Until it is built the main menu draws the
stock painted layers with the stock opening, as section 12.1 describes. This
subsection is the design contract for the work and is written in the present
tense, as the finished menu behaves. The Interface Atlas draws it to these
numbers.

openPREY's main menu draws the Sphere and Earth as lit 3D bodies under one
camera, in place of the stock's painted layers. Out of game it opens close on
the Sphere's shell, a little off-centre, then swings round the Sphere on a
curve as it pulls away, quickly and smoothly, until the frame lays over the
stock painting: the Sphere and Earth come to rest exactly where the 2D layers
draw them, with Earth in front.

The portal rim and its models, the wordmark, the arc, the bottom bar, every
page and all of sections 4 to 7 stay stock. The star field stays the stock
layers at rest and turns with the camera during the entrance.

#### Rest composition

The rest frame is an accurate recreation of the stock frame. These targets are
measured from the stock art in its stock rectangles, on the 4:3 canvas.

| Element | Target | Source and tolerance |
| --- | --- | --- |
| Sphere | Radius 186, centred at 357,222 | The painted disc of `background3.tga` in its rectangle at 165,30 (384x388 u). Outline within 2 u |
| Sun flare | Radius 32 at 357,224 | The stock `sol` window, 64x64 u at 325,192: 0.17 of the Sphere's radius. Additive, over the shell and under the plates |
| Earth's limb | A circle of radius 1695 about 689,2069: through 99,480, 350,408 and 639,374 | The solid edge of `background2.tga` in its rectangle at 0,330 (640x150 u). Within 3 u |
| Earth's glow | Fades out 45 u above the limb: 0.60 at 3 u, 0.35 at 10 u, 0.19 at 17 u, 0.09 at 28 u | The painting's halo |
| Sorting | Earth in front of the Sphere | The stock draws stars, Sphere back, sun, Sphere front, then Earth (`guis/mainmenu.gui:307-334`), so Earth's limb and glow lie over the Sphere's foot: the Sphere's disc reaches y 408 where the limb beneath it stands at y 407 |
| Plates | 133, covering 17% of the disc | `background4.tga`. Each plate within 3 u of its painted place |
| Green patches | Six, in three groups about 262,271, 455,303 and 426,352 | The shell layer |
| Portal rim | Unchanged: glow edge on a circle of radius 368 about 404,192 | Appendix B |

Laid over a capture of the stock menu at the same aspect, the rest frame shows
no doubled edge: the Sphere's outline, Earth's limb and the plates coincide
with the painting. The arc, the navigation and the wordmark therefore sit over
the Sphere exactly as they do in the stock menu.

The 3D bodies then do what the painting cannot. From the rest frame the Sphere
turns slowly and Earth's clouds drift, so the frame matches the painting at
the moment the entrance ends and departs from it gradually.

#### Scene

One unit is the Sphere's radius R. The axes are the rest camera's: the Sphere
sits at the origin; x runs toward the trailing edge, y up and z into the
screen.

| Item | Value |
| --- | --- |
| Camera | Vertical field of view 30° at every aspect (a focal length of 895.7 u on the 480 u canvas) |
| Camera at rest | At −0.195, −0.095, −4.921, 4.93 R from the Sphere's centre, looking along +z with y up |
| Camera at the start | At −0.903, −0.123, −1.077: 1.41 R from the centre and 0.41 R above the shell, 40° round the Sphere toward the leading side and 5° below its equator. It looks across the shell, turned 35° toward the trailing side and 9° upward from its rest heading |
| Earth | Radius 4.41 R, centred at 0.755, −4.776, −3.442: 5 R from the rest camera, which rides 0.59 R above its surface |
| Depth | Earth's limb is 2.35 R from the rest camera and the Sphere's near face 3.93 R, so Earth stands in front. The two surfaces are 0.52 R apart and never touch |
| Key light | Arrives from 0.09, −0.85, −0.52: from below, the side on which Earth lies, as the painting is lit |
| Sphere's turn | Holds the painted face until the camera rests, then once in 240 s about an axis tilted 20° toward the trailing edge |
| Earth's clouds | Drift 1.5 u a second along the limb |
| Stars | At infinity: they do not shift with the camera's travel and they turn with its heading |

The rest composition is the contract. The scene values are one solution that
meets it; another field of view, scale or start point is acceptable when the
rest frame, the sorting, the start framing and the checkpoints below still
hold. At rest the camera does not move: no drift, sway or shake.

#### Appearance

Build both bodies to reproduce the painting from the rest camera.

- **The Sphere's shell.** Near black over most of its face (`#0B1013` to
  `#0F171B`), brightening to `#2A3D48` in a rim along the lower limb, with a
  black crown: the light comes from below. Shallow craters; no specular
  highlight.
- **The plates.** Angular shards of blue ice, typically 16x6 u at rest and up
  to 33x16 u, in loose clusters. They are self-lit: the painting shows them
  equally bright (`prey.sphere.plate`, about `#2C4366`, with highlights toward
  `#AFC5E3`) on the lit and the dark side. Each sits where it is painted. The
  green patches (`#145D3C` to `#20724F`) do too.
- **The far side.** The painting shows one face, and the entrance looks at
  the Sphere from 38° round it. Author the rest of the Sphere in the same
  manner, at the same density, so neither the entrance nor the turn reveals a
  bare or different surface.
- **Earth.** A white band about 25 u deep along the limb (`#DBE0ED` to
  `#D0D4E4`), blue-grey beneath it (`#94A2C8` to `#78889B`) under cloud, and
  the glow above the limb, which lies over the Sphere's foot.
- **The stock light layers stay.** Stars remain additive; the sun flare
  brightens the shell beneath it.

#### The entrance

The entrance plays when the menu opens out of game (the `playIntro` event) and
lasts 1200 ms.

| Time | Event |
| --- | --- |
| 0 ms | Black. The camera is at its start: the shell fills the screen, the Sphere's centre is drawn at 400,300 (80 u toward the trailing edge of the canvas centre and 60 u below it) and its apparent radius is 900 u. Earth is out of sight below. Menu music starts |
| 0–150 ms | The backdrop fades up from black, linear |
| 0–1200 ms | The camera's curve: it swings 38° round the Sphere toward its rest direction while it pulls back from 1.41 R to 4.93 R, turning to hold its aim |
| 425 ms | The camera crosses to Earth's side of the two bodies. From here Earth is the nearer body |
| 700–1100 ms | The portal rim swings in from beyond the leading edge, linear. This is the swing that closes a full-screen page: the front portal model's view offset runs from −15 to −43 |
| 780–1200 ms | Earth's limb enters at the trailing foot of the screen and rises into its place, in front of the Sphere |
| 1000–1200 ms | The wordmark, arc and bottom bar fade in together, linear, and take input from 1000 ms |
| 1200 ms | Rest: the stock composition |

**The curve.** One eased progress `e` drives everything.

- The camera's direction from the Sphere's centre swings along a great arc
  from the start direction to the rest direction: 38° in all, in proportion
  to `e`.
- Its distance grows so that the Sphere's apparent radius falls
  geometrically: `r = 900 × (186 / 900)^e`.
- It looks at a point that moves in a straight line, in proportion to `e`,
  from −0.102, 0.094, 0.075 (just off the Sphere's centre, which puts the
  Sphere off-centre in the opening frame) to the point straight ahead of the
  rest camera. The world's y stays up, so the camera never rolls.

**Easing.** `e` follows the stock interpolator with 15% acceleration and 85%
deceleration (`"1200" "0.15" "0.85"`), so speed peaks at 180 ms and falls away
for the rest of the move. Because the Sphere's apparent radius follows `e`,
not the camera's distance, equal steps of `e` shrink the Sphere by equal
ratios, which is what makes the move read as quick at first and smooth to the
end. Easing the distance instead spends nearly all of the visible change in
the first frames.

| Time | `e` | Sphere radius (u) | Sphere centre (u) | Camera distance (R) | Heading from rest | Earth |
| --- | --- | --- | --- | --- | --- | --- |
| 0 ms | 0 | 900 | 400,300 | 1.41 | 35° trailing, 9° up | Out of frame, behind the Sphere |
| 180 ms | 0.150 | 710 | 394,277 | 1.61 | 30°, 7° | Out of frame |
| 400 ms | 0.477 | 424 | 378,242 | 2.34 | 18°, 3° | Out of frame; passes in front at 425 ms |
| 700 ms | 0.796 | 256 | 364,226 | 3.63 | 7°, 1° | In front, still below the frame |
| 950 ms | 0.949 | 201 | 357,223 | 4.56 | 2°, 0° | Limb at y 403 on the trailing edge |
| 1200 ms | 1 | 186 | 357,222 | 4.93 | 0°, 0° | Limb at y 374 on the trailing edge: rest |

- **Sorting.** The two bodies never overlap on screen while the camera
  crosses between them, so the change at 425 ms is not seen: Earth simply
  arrives in front. Sort the bodies by depth in one scene; do not composite
  them as fixed layers.
- **Earth.** Its limb rises 106 u at the trailing edge between 780 ms and
  rest, slowing as it arrives. The camera passes no closer than 0.44 R to
  Earth's surface.
- **Stars.** They turn with the camera, 35° across the screen over the move,
  fastest at the start, and stand still at rest.
- **First frame.** The camera opens over the plates of the Sphere's leading
  side with the sun flare in view, so the first frame shows ice and veins
  rather than bare shell. It covers the whole screen up to 21:9.
- **Input.** Any key, button or click during the entrance skips to rest at
  once. The entrance never holds input for more than 1000 ms.
- **Sound.** The music carries the move; there is no effect.

#### Variants

| Case | Behaviour |
| --- | --- |
| Menu opened in game (`noIntro`) | The stock `AnimPortalIn` over the frozen frame (section 8). At 500 ms the 3D backdrop, already at rest, fades in over 100 ms. No camera move |
| Returning from a page | No entrance. Full-screen pages still swing the portal out and back |
| Reduced motion | The backdrop appears at rest, Earth in front: no entrance, turn or cloud drift |
| Scene unavailable | If the models do not load or a renderer cannot draw the scene, the stock painted layers draw at their stock rectangles with the stock opening. The menu never shows a bare star field |
| Death screen (`restart`) | Unchanged: stars only |

#### Aspect

The camera holds its vertical field of view, so the 4:3 region of any screen
shows exactly the rest composition and a wider screen adds star field and
limb at each side. The Sphere stays at 357,222 in canvas units. Earth's limb
continues along the same curve and leaves the trailing edge near y 373 on
16:9 and y 378 on 21:9.

#### Engine notes

`renderDef` (`src/ui/RenderWindow.cpp`) already gives a GUI a private render
world with up to three models and five lights, and its `viewOffset`,
`modelOrigin` and `modelRotate` accept `transition`. The stock menu uses it
for the portal. The scene needs four things it lacks:

1. **Field of view.** A `renderDef` draws with a fixed 90° horizontal field
   of view; the scene needs 30° vertical. The retained-UI entry
   `DrawModelScene` already takes one. `canvasfill 1` already draws a
   `renderDef` across the whole expanded canvas through an off-axis frustum
   that keeps the projection its rect defines; the portal uses it.
2. **A camera that turns.** A `renderDef` moves its camera with `viewOffset`
   and always looks along one axis. The curve needs a view axis as well.
3. **Independent bodies.** Models after the first share the first model's
   origin and rotation. The Sphere turns while Earth holds, so either each
   model takes its own origin and rotation, or Earth's offset is built into
   its mesh and the Sphere's turn is animated in its material.
4. **The curve.** A `transition` eases one value in a straight line. The
   camera's arc, its geometric pull-back and its aim need driving per frame
   from code, or a new interpolation mode.

Draw both bodies in one scene with depth testing, so that Earth hides the
Sphere's foot at rest and the order is right throughout the move. The star
layers are 2D windows today: either draw the stars in the scene as a sky, or
slide the stock layers by the camera's heading, so that they turn with the
camera and come to rest unmoved.

The stock script records two more constraints (`guis/mainmenu.gui:17-20`).
Keep the scene in one `renderDef`: several share their lights and wash each
other out. Use static meshes: animated ones are clipped early by the near
plane. At the start the shell passes 0.41 R from the camera, so scale the
scene until that distance clears the near clip plane.

The models and materials are new openPREY work under `content/basepr/pak0/`,
placed as `docs/dev/source-layout.md` directs. Build the Sphere's front face
from the stock painting as seen from the rest camera, so that every plate
lands where it is painted, and author the far side to match. Whether its
textures are projected from the installed art or redrawn is a licensing
decision for `LICENSING.md`, not for this document; the Interface Atlas uses
measurements only. Author the Sphere's colour map for the opening frame:
2048x1024 with a tiling detail layer.

#### Acceptance

A build meets this subsection when:

1. At rest on a 4:3 canvas the Sphere's outline is within 2 u of radius 186
   about 357,222, Earth's limb within 3 u of the stock circle, and each plate
   within 3 u of its painted place. Laid over a capture of the stock menu,
   the rest frame shows no doubled edge.
2. At rest Earth is in front of the Sphere: its limb and glow cover the
   Sphere's foot as in the stock menu, and no frame of the entrance shows the
   farther body over the nearer one.
3. The entrance lasts 1200 ms to within one frame. At 180, 400 and 700 ms the
   Sphere's radius is within 5% of the table and the camera's heading within
   2°.
4. The first visible frame shows plates and covers the screen at 4:3, 16:9
   and 21:9.
5. Input skips the entrance, and the menu takes input by 1000 ms.
6. The menu opened in game plays the stock opening with no camera move.
7. Reduced motion and the unavailable-scene fallback behave as in the table.
8. Text over the backdrop still meets the contrast targets of section 4.

### 12.3 Principles for a replacement

Any future vector or retained-UI replacement of the Prey front end must:

1. Keep the portal: the rim on the leading edge, the tear through the frozen
   frame when the menu opens in game, and the view of the Sphere over Earth.
2. Keep steel glass: translucent graded plates, pale rails, cool text, claw
   corners. Reconstruct the furniture as vectors from Appendix B; do not put a
   low-resolution bitmap in a vector box.
3. Keep the growth from the bar and the hiding of the wordmark under full
   pages.
4. Keep the two faces in their roles, Title Case and centred labels.
5. Add what the stock lacks without changing its look: a visible focus state,
   controller prompts in the bottom title bar, scalable text, and opaque
   frame bodies where contrast fails.
6. Widen pages only within a comfortable reading width (about 960 u on
   21:9 and wider); the backdrop always reaches the edges.

### 12.4 Patterns to avoid

- Upstream openQ4 Marine components, framing bands or palette in Prey screens.
- New accent hues in the front end, including Quake 4 orange or a second blue.
- Replacing the backdrop with a static picture or a blurred gameplay frame.
- Animated chrome beyond the stock's: no pulsing rails, sweeping highlights or
  particle effects on controls.
- Camera drift, shake, lens flares or depth of field in the menu backdrop.
  The only camera move is the entrance.
- An entrance that plays every time the menu regains focus, or that cannot be
  skipped.

### 12.5 The retained navigation

**Status: built, off by default.** `ui_retained 1` selects it; `ui_retained 0`
(the default) presents the stock menu unchanged. It is the first replacement
made to section 12.3, in the manner of openQ4's retained menus: documents for
the retained interface ([document format](ui/document-format.md)), generated
by a script from this specification and committed.

| Document | Presents | Holds |
| --- | --- | --- |
| `guis/menu/title.rui` | Home, out of game | The arc of hooks with Resume Game (while a save exists), New Game, Load Game, MultiPrey, Options and Exit; the bottom bar with Updates, Credits and Mods; the New Game, Mods and Exit frames |
| `guis/menu/pause.rui` | Home, in a single-player game | Resume Game, Quit Game, Save Game, Load Game, Options and Exit; the bottom bar with Credits; the Quit Game and Exit frames |
| `guis/menu/loadgame.rui` | Load Game, from either home | The saves table (Name, Date, Time), the selected save's picture, date, time and Time Played, Load and Delete, and their confirmations |
| `guis/menu/savegame.rui` | Save Game, from the pause | The saves table, the name field, Save, the overwrite confirmation and the refusal notice |
| `guis/menu/restartmenu.rui` | The death screen | The frame with Load, Restart and Main Menu and the line under each that says what it does |
| `guis/menu/credits.rui` | Credits, from either home | The stock credits sheet rising through the page |
| `guis/menu/settings.rui` | Options, from either home | The four top tabs, Controls' seven pages, Game Options' two, Video's six and the Audio page, and the Reset Defaults dialog |
| `guis/menu/presetcheck.rui` | The system check, before the main menu | The claw frame with the detected hardware, the nine presets as a ladder (recommended lit, current outlined), the recommendation's scale and frame cap, Apply Recommended (Continue when nothing would change), Keep Current and Ask Me Next Time |
| `guis/loading/loading.rui` | Every level load, in place of `guis/map/loading.gui` | The level's art across the screen, the name band with the level's name and author line, the objectives panel, the progress bar in its claw-ended outline and the loader's phase |

`tools/ui/build_retained_screens.py` writes them from the measurements of
sections 3 to 8 and the Interface Atlas's constructions; `--check` reports a
stale document, and the Meson test `openprey-retained-screens` runs it. Edit
the generator, never the documents.

#### What is replaced and what is kept

The home documents draw only the navigation. The stock menu keeps drawing
beneath them, so the portal and its opening, the star field, the Sphere,
Earth, the wordmark, the music and, in a game, the frozen frame the portal
tears open are the stock menu's own (section 12.3, rule 1; section 12.4
forbids replacing the backdrop with a picture). Section 12.2's 3D backdrop,
when it is built in `guis/mainmenu.gui`, appears under the retained navigation
without a change here.

- `guis/mainmenu.gui` leaves its navigation and bottom bar undrawn while
  `gui::retainedHome` is 1. The session sets it whenever a home document can
  present, through the stock pages too, so the stock and retained navigation
  never show together.
- The session covers the stock menu with the home document exactly while the
  stock navigation would show (`Main_Menu::visible`): from the end of the
  portal opening at 500 ms, and whenever no stock page is up. The home fades
  in over 100 ms with the backdrop.
- New Game, Mods, Exit and Quit Game are frames of the home documents. They
  grow from the bottom bar as section 8 records, and the navigation and
  bottom bar hide while one is open.
- Load Game, Save Game and Credits are documents of their own (below).
- Options is a document of its own (below).
- MultiPrey and the update check are still the stock menu's. The home asks
  the session for one, the session sends `guis/mainmenu.gui` a
  `retainedPage_*` named event, and the stock page grows from the same
  bottom-bar rectangle; the home stops covering the menu until the page is
  back in the bar. A retained document for MultiPrey takes the request
  instead once it exists at the path the session already looks for
  (`guis/menu/multiplayer.rui`); that session route is inherited from openQ4
  and has not been run with a Prey document.
- The death screen is a document of its own (below).
- The system check (`docs/dev/ui/performance-presets.md`, "System check") is
  a document of its own. It is drawn over the stock check's backdrop and
  wordmark, which the session keeps drawing beneath it, as under the death
  screen; the stock `guis/presetcheck.gui` leaves its own dialog undrawn
  while `gui::retainedHome` is set. Both are described under the system
  check below.
- The loading screen is a document of its own (below). A map's own
  `guis/map/<map>.gui`, and a mod's own copy of the stock screen, still
  present instead.
- The message boxes, the in-game multiplayer menu and a multiplayer game's
  Escape menu are the stock GUIs.

#### Construction

Everything is vector geometry in the tokens of section 4; the only bitmaps are
Tommy's three New Game portraits, which are pictures, not furniture.

- **Canvas.** 720 dp spans the view's height; the stock 4:3 canvas is the
  central 960 dp (1 u = 1.5 dp), so the navigation stays in the leading half
  of the 4:3 canvas and the frames on the central axis at every aspect
  (section 3). Checked at 4:3, 16:9 and 21:9.
- **Arc and bars.** The Atlas's arc path, with its shaded edge, highlight and
  25 rivets, and six hook bars at the stock steps (section 6). An entry's
  target is its whole 27 u pitch (section 3).
- **Frames.** The claw corner is the Atlas's silhouette with its socket and a
  rim cut to the body by a mask; a frame is four mirrored corners, the 1.5 u
  rails between them and a black body inset 25 u at each end. The home bottom
  bar draws the lower pair only.
- **Buttons.** The 3-slice outline with the graded plate at rest and the even
  rollover plate when lit.
- **Type.** The display face for navigation, titles and bottom bars, the body
  face for buttons and prompts, at the stock `textscale` values. The retained
  interface draws the traced faces 6% smaller than the stock atlases at the
  same em, so the generator raises sizes by that much (`FONT_FIT`). It places
  each label so that its capitals land where the stock window draws them: in
  a stock window the centre of the capitals lies 0.84 em (display) or 0.76 em
  (body) below the window's top plus `textaligny`; in a retained line it lies
  0.21 em (display) or 0.05 em (body) below the line's centre. These figures
  were measured from stock and retained captures at 1280x720.

#### Interaction, motion and sound

- Hover and focus follow section 7. Focus is the hover treatment plus the
  rim at full `prey.rail`: the hook bar redrawn in it for a navigation entry,
  the outline for a button, a hairline under a bottom-bar action. While the
  pointer leads, only the entry under it is lit.
- The arrow keys and a controller step down the arc and wrap through the
  bottom bar; in a frame they step between its buttons and its bottom action.
  Back closes a frame, resumes the game from the pause and opens Exit from
  the title.
- A navigation entry slides toward the arc over 150 ms and returns over
  200 ms; buttons and bottom-bar actions change at once. A frame grows from
  the bottom bar (180,438,450,32) to 180,200,376,270 over 500 ms with the even
  ease-in-out and shrinks the same way; its upper claws and top rail arrive in
  the first 60 ms, since a frame no taller than its corners has none. Its
  contents keep their places and are uncovered as it grows.
- Pop-ups soften the screen behind them in `prey.softfocus`: the backdrop,
  or the paused game, behind a frame, and the page behind a dialog. A frame's
  soft focus comes in as it grows and goes as it shrinks, on the same 500 ms
  ease. A dialog's arrives and leaves with it at once, beneath its stock
  scrim, which still darkens the screen as the stock dialog does. Where the
  renderer cannot blur the screen (`ui_retainedSoftFocus` is 0, as on GLES
  or with the opaque-backing option) a pop-up has only what the stock one
  had. The stock screens soften nothing; this is the retained interface's
  addition.
- A New Game skill shows its portrait and description while it is lit, as the
  stock rollovers do. Cherokee is drawn unavailable until `g_nightmare` is
  set; Casino appears once `g_roadhouseCompleted` is.
- Sounds are the stock ones, named by the documents' events: `clickin` on a
  press, `cancel` on No, `slideinsmall` and `slideoutsmall` as a frame grows
  and shrinks.
- With reduced motion (`ui_retainedReducedMotion`) the retained interface
  applies the end of each move at once.

#### Load Game and Save Game

Each is the stock page rebuilt at the stock rectangles (section 9): the
620x460 u claw frame with its title bars, the Name, Date and Time headings in
white on `prey.list.wash` cells, the column boxes, the two picture frames
round the headings and the list, the scroll bar, and 3-slice buttons. Load
Game sits on the `prey.page.wash` page with the level-shot frame, the save's
date and time, Time Played (shown when the save records it) and Load and
Delete; Save Game has the name field on `prey.list.wash`, its caption and
Save.

- **Presenting.** The home asks the session for the page
  (`idSessionLocal::BeginRetainedPage`), which fills it with the saves and
  presents it at once over the stock menu's backdrop. The stock menu dresses
  that backdrop as it does for its own full pages on `retainedCover_page`: the
  wordmark hides and the portal's view swings in over 400 ms. While the home
  rests (500 ms with the focus unchanged) the pages it leads to are prepared
  out of sight, so the first open does not compile their artwork: the title
  prepares Load Game, Options and Credits, the pause Options, Save Game,
  Load Game and Credits (`idSessionLocal::WarmRetainedPages`).
- **Growth.** The page widens from the bottom bar to the full-width bar in
  200 ms and rises to 10,10,620,460 in 500 ms (section 8); the title bar and
  the upper claws appear as the rise starts. Back shrinks it the same way,
  the wordmark and portal come back on the stock timing
  (`retainedCover_home`), and the home takes the screen when the page is in
  the bar, 700 ms later (`idSessionLocal::LeaveRetainedPage`). With reduced
  motion the home returns at once.
- **The list.** Rows are 20 u high in `prey.text.list`; the session fills 64
  at a time, newest first, with each save's name, date and time
  (`PublishRetainedLoadRows`), and Previous Saves and Next Saves rows turn the
  list when there are more. A press selects a row (`guisounds_menu_tick`):
  the selected row carries `prey.list.selection` and its outline, the pointer
  turns a row's text white, and focus adds an outline at full `prey.rail`.
  Accept on the selected row loads it on Load Game and moves to the name
  field on Save Game.
- **Asking first.** Delete always asks, and Load asks in a game, with the
  stock confirmations: a 0.40 black scrim over the whole screen and a
  360x140 u claw frame at 142,132 that appears and disappears at once.
  Cancel holds the focus. Saving over an existing save asks the same way and
  names the save; a save the session refuses, or a save that cannot be
  loaded or deleted, says why.
- **After saving** the menu closes and the game resumes, as the stock page
  does.

Differences from the stock pages: the stock list's double-click to load is
Accept on the selected row; the confirmations for Load and Delete do not name
the save; and Load Game does not repeat the save's description beside its
picture.

#### Mods

A small frame of the title, grown from the bottom bar like New Game: the list
of installed mods on a white 0.10 ground (270x130 u at 51,59, rows 16 u high
at 0.25 with the name and version in the stock columns), its scroll bar, and
Load MOD (100x25 u at 221,200). The session fills the list and opens the
frame on the title's Mods request, with the running mod selected
(`idSessionLocal::PublishRetainedMods`). A press selects a mod; Accept on the
selected mod, or Load MOD, restarts the engine into it as the stock button
does. The list holds 32 mods.

#### Credits

A full page like Load Game, reached from either home. Its window (620x400 u
at 0,31 in the frame) shows the stock credits sheet, 5300 u tall, rising at
the stock rate. The generator reads the 169 credits, two banners and three
pictures from the stock script openPREY carries
(`guis/mainmenu/mainmenu_creditcontent.guifragment`): each one's rectangle,
`textscale` and string key. The document holds those numbers and keys only.

- **The head.** The wordmark fades in from 700 ms to 0.90 over 1 s, the first
  banner from 1700 ms, the studio mark from 3500 ms, and the second banner
  and its mark from 28 s and 29 s, as `Credits_AnimIn` times them.
- **The roll.** The sheet starts to rise at 2700 ms and takes 130 s; then the
  whole sequence starts again. It keeps this timing under reduced motion,
  because the roll is the page's content.
- **Credits.** Each appears when it has risen to canvas y 350, as the stock
  `creditDef` does. Headings (`#CCDEFA`) and names (`#99ADC7` at 0.88) appear
  in place; each of the 50 titles (`#D1E3FC`) flies in from x 1000 u to its
  place over 500 ms with the even ease-in-out.

Differences from the stock page: the retained interface has no shear, so a
title flies in upright; the stock fade 18 s after a credit appears is left
out, since a credit has left the window by then; and the hidden buttons and
their bonus panel are not carried over.

#### Options

A full page on the Options page's 0.50 body, with the stock tab furniture
(section 6) as vectors: four top tabs at 125,35 (117.5x20 u each), the
570x370 u tab page at 25,55 with its wash, its shading from the top and from
the leading edge of the inner page, and its `prey.separator` outline, and a
100 u column of side tabs that share the height below a 40 u margin. The
active tab and its page are one surface: the outline is drawn in runs, and
the run beside or under a tab shows only while that tab is inactive.

**Every tab is rebuilt**, and so is the Reset Defaults dialog. The page opens
on Controls, as the stock page does.

- **Controls.** The stock page's seven side tabs (Movement, Combat, Weapons,
  Look, System, MultiPrey and Profiles), 47 u tall each. A binding page's
  header bar with its two headings (Action, Key Assignment), its rows and the
  line at its foot are read from the stock script. A row is the setting
  row's plate with the action in the leading half and its keys in the
  trailing half in `prey.text.value`: named as the language names them,
  joined with a middle dot, or `<empty>`.
  - *Binding.* Accept or a click waits for a key, and the keys read "Press
    any key...". The next key pressed joins the action's keys, two of each
    device family, as the stock field binds them, and plays
    `guisounds_menu_tick`. Escape, Start or Back cancel; Backspace or Delete
    clear the row. Out of a wait, Delete, Backspace or the west face button
    clears the focused row. The session takes the key
    (`idSessionLocal::RetainedControlsKey`) and knows each row by its place in
    `PREY_CONTROLS_BINDINGS`. The generator refuses to write the page while
    that list differs from the stock script's rows.
  - *Profiles.* At the stock places: what profiles are for, the saved
    profiles in a list on a black 0.50 ground in a picture frame with its
    scroll bar (32 at most), the name field, and Delete, Load and Save As. A
    press selects a profile and puts its name in the field; Accept on the
    selected one loads it. Delete and Load are lit while a profile is
    selected, Save As while there is a name. They act as the stock buttons do
    (Appendix C.2). The list is read again when the tab is chosen and when
    the page opens.

- **Rows from the stock script.** The generator reads Game Options' side
  tabs, headings and rows from `guis/mainmenu/mainmenu_options.guifragment`:
  each row's rectangle, label, setting, choices and slider range. A row is
  the graded `prey.plate.row` plate with its label centred in the leading
  half and its value in the trailing half.
- **Choices.** The value shows the current option, named from the stock
  choice string. Left and Right cycle it, as a click cycles the stock
  control; Accept or a click unfolds a list across the row, black with the
  `prey.separator` outline, 18 u a row, with each option under the value. The
  list is the retained control's addition.
- **Sliders.** The stock 100x16 u rail with its tick dots and ring knob
  (`prey.slider`), and the number after it, which the stock does not show.
- **Settings change at once**, as the stock controls' do, through the
  engine's list of settings a page may change (`FindPlayerSetting`), which
  bounds each one to the values its stock control offers.
- **Video.** The six side tabs of section 12.1 (Video, Display, Advanced 1,
  Advanced 2, Post FX, Advanced FX), each 55 u tall, with their rows read
  from the stock script like the others:
  - *Plain settings* (most choices and every slider) change at once.
  - *Lists the session builds.* Video Resolution, Monitor, Refresh Rate and
    Frame Rate Limit show what the selected display reports, as the stock
    rows do; the row sends the entry's index and the session applies it with
    the stock menu command. A list shows eight entries and scrolls the rest.
  - *Quality Preset* applies the preset through the stock command; *Detect*
    loads the recommended one. The Detect plate is the group box: rounded, a
    horizontal `prey.plate.row` fade with its rim.
  - *Window Size and Custom Resolution* are two number fields either side of
    an "x", on `prey.list.wash`, taking 320 to 16384 across and 240 to 16384
    down.
  - *Full Screen* is held on the page until Apply Changes, as the stock row
    is; every other row writes its setting when it changes.
  - *Apply Changes* sits on every page and is lit while a setting that takes
    a video restart differs from what is in effect: the resolution, the
    monitor, Fullscreen Mode, Borderless Window, Refresh Rate, Span All
    Monitors, either size, MSAA Samples, the preset or Full Screen. Changing
    one back puts it out again, where the stock button stays lit once
    anything has touched it. It restarts the video system; the page comes
    back with the focus on the side tab it shows.
  - *Rendering API* takes the game restarted: while the choice differs from
    the API the process started with, the stock dialog's line shows at the
    foot of the Display page.
  - *Shader Detail* is drawn at 0.40 and takes no input while shader programs
    are off or the Vulkan backend is active (section 12.1).
- **Audio.** One page with no side tabs, as in the stock. Its rows are read
  from the stock script like the others, with these differences in how they
  act:
  - *Volume.* Effect Volume and Music Volume run 0 to 100 in steps of 5 over
    the stock sliders' 0 to 1, and the session maps them onto decibels as the
    stock `volumeslider` does (`6 log2 v`, silence at 0). The effect slider
    plays `guisounds_menu_volumetick`.
  - *Rows the sound system acts on.* Sound System, Speaker Setup, Sound Device
    and EAX send the session a verb with their value; it sets what the stock
    control sets and runs the stock control's own `sound` command, which
    restarts the sound system where the stock page does and may answer with
    the stock message box.
  - *Sound Device.* The list is the session's, as the stock page's is: up to
    16 devices with the one in use chosen. A name too long for the value
    column ends in an ellipsis, and the list gives names the row's width.
  - *What shows and what dims.* The software-mixing rows (Speaker Setup,
    Reverse Channels) show while OpenAL is off and the OpenAL rows (Sound
    Device, EAX) while it is on, each under its own heading. Sound System is
    drawn at 0.40 and takes no input unless a mixer choice is offered, and
    EAX likewise unless the device supports it, as the stock page dims them.
    The EAX mark shows while EAX is in use.
- **Reset Defaults.** Reset to defaults on the bottom bar opens the stock
  dialog, rebuilt from the stock overlay (`Overlay_ResetDefaults`): a 0.80
  black scrim, the 360x250 u claw frame at 142,100, its title and line, five
  check boxes (Controls, Game Options, Video Settings, Audio Settings, Reset
  all settings), and Reset and Cancel. It appears and disappears at once,
  with every box clear and the focus on Cancel. A check box is the 12 u
  ground with its border and the cross while it is ticked; the pointer
  whitens the border and focus adds an outline in `prey.rail`. Reset is lit
  while a box is ticked and resets what is ticked as the stock button does;
  Reset all settings resets every part and every setting (`cvar_restart`).
  The page shows the result at once, and a video setting that takes a
  restart lights Apply Changes.
- **Feedback.** The plate is unchanged; the value turns white under the
  pointer or focus, and focus adds the plate's outline at full `prey.rail`.
  A tab's label turns `prey.text.tabHover`; a tab change plays
  `guisounds_menu_tabflip`.
- **Keys.** The arrow keys and a controller step to the nearest control that
  way, except where the page names the step: Up from a page's first control
  reaches its own top tab (the nearest was often a neighbour, Video from
  Audio's first row), and Return to Main Menu and Reset to defaults step to
  each other and stop at the bottom bar's ends.

#### The death screen

The 280x220 u claw frame at 172,184 with its two empty title bars and the
Load, Restart and Main Menu buttons (150x30 u, 0.40), over the stock screen's
backdrop. As with the home, `guis/restart.gui` keeps drawing beneath the
document: its painting with the edge slices, the wordmark and its fade from
black are the stock screen's own, and it leaves its frame and buttons undrawn
while `gui::retainedHome` is 1 (`idSessionLocal::OpenRestartMenu`).

- The frame's body stops 20 u inside each end here, not 25 (`margins 20, 20,
  7, 0`).
- The document arrives with the stock fade: nothing for 100 ms, then to full
  over 1000 ms.
- Each button has a line under it that says what it does (0.28, white 0.70),
  which fades in over 400 ms while the button is lit and out again, as the
  stock rollover does. The focus opens on Load, so its line shows on arrival.
- Load loads the newest save and Restart the level's restart slot, as the
  stock buttons do; either restarts the level when there is nothing to load.
  Main Menu opens the menu.
- The stock buttons' labels dim to white 0.50 once the pointer has left
  them; the retained ones return to `prey.text.button`.

#### The loading screen

Retail Prey loads every level under one screen, `guis/map/loading.gui`
(`idSessionLocal::LoadLoadingGui` in `PREY.exe` 1.4); the session presents
`guis/loading/loading.rui` in its place. The document draws what openPREY's
override of that screen draws (section 12.1), at its measurements, and
nothing of the stock screen draws beneath it.

- **Art.** The session sets the picture (`loading_levelshot`) as section
  12.1 finds it. With both tiles the window needs it is the composed
  picture, drawn across the whole screen; otherwise the 4:3 picture is drawn
  on the centred 4:3 canvas over black (`loading_bkgnd_canvasfill`).
- **Name band.** Black 0.55, 35 u high at 10 u from the screen's top and
  across its whole width; the level's name centred on it in the display face
  at 0.6, `prey.load.name`, with the engine shadow. The author line (display
  0.3, `#D9D9FF` at 0.75) shows only for a map that has one.
- **Objectives.** The panel (430x74 u at 20,348, black 0.45) with the
  objectives in the display face at 0.28, shown only for a map that has
  them.
- **Progress.** The fill (256x12 u at 192,455, `prey.load.fill`) grows with
  the load under the outline, whose wash darkens it as the stock windows
  stack. The outline is `bottombar.tga` traced as vectors at 304x30 u: a
  black 0.40 wash between two claw ends, each a steel hook
  (`#617186` at 0.91 with a `#97B2D7` rim) on a black 0.72 outline, pierced
  by an oval; along the foot a rail of four bands (black 0.78, `#AECCF4`
  0.82, `#5D6D82` 0.81, black 0.65); on it five groups of three rivets,
  47.5 u apart.
- **Phase.** Where the stock screen kept its status line, commented out,
  beside the bar at 474,445: the loader's phase (Map, World, Assets,
  Finishing, then Load Time) in the body face at 0.28 and, under it, its
  count (assets loaded of the total, then the load time) at 0.25, both
  right-aligned, `#BFD1FF` at 0.72 and 0.50.
- **Placement.** The name band and author line keep to the screen's top and
  the objectives, bar and phase to its foot on a screen taller than 4:3, as
  the stock windows do with `screenaligny`; the objectives, bar and phase
  stay on the 4:3 canvas's columns.
- **Motion.** None but the fill, as in the stock. A multiplayer join that
  holds the screen over the match fades it out over 250 ms.

#### The system check

Shown before the main menu when the performance presets have changed since
the configuration last checked them (`docs/dev/ui/performance-presets.md`,
"System check"). It is one dialog in both interfaces, at the same stock
coordinates, so the retained document is the stock screen redrawn.

- **Backdrop.** The death screen's: the static menu backdrop
  (`guis/assets/menu/background_*`) and the wordmark, here at 190,14,260,18
  above the frame. The stock screen draws it; the retained document draws
  over it, with `prey.softfocus` and a 0.50 scrim beneath its frame.
- **Frame.** The claw frame at 100,50,440,392 with a 0.70 body. Its title is
  centred at the frame's top; the question under it, in the body face at
  0.25, takes up to three lines.
- **Readout.** Two section header bars (Detected Hardware, Performance
  Preset) with their names in the display face at 0.33. Under the first,
  five rows: the name in `prey.text.label`, the value from x 150 in
  `prey.text.value`. Under the second, the nine presets as a ladder of
  12 u cells, Minimum leading, each `prey.list.wash` a little stronger than
  the last; the recommended cell is filled in `prey.text.button` and the
  current one outlined in white with a marker under it, with the two end
  names under the ends. Then Recommended (in `prey.text.button` at 0.30)
  with its render scale and frame cap, Current, and a line naming
  Options > Video as the place to change it later.
- **Actions.** Apply Recommended (Continue when nothing would change) and
  Keep Current as 170x25 u 3-slice buttons, and Ask Me Next Time under them
  as a bottom bar's action in the display face. Focus opens on the first;
  Left and Right step between the buttons and Down reaches the action.
  Escape or Back is Ask Me Next Time. While the recommendation applies, the
  three give way to "Applying settings..." until the renderer and sound have
  restarted.
- **Sounds.** `clickin` on Apply and Keep, `cancel` on Ask Me Next Time.

#### Not yet built

- Controller prompts in the bottom title bar, and text that scales with the
  interface's text size without leaving its plates (section 12.3, rule 5).
- The stock Audio page's sound-driver notice (the engine never raises it),
  the Advanced 2 page's driver box, whose button opens a web page, and the
  crosshair's picture beside its name.
- MultiPrey and the message boxes. Each is a document for the generator
  and, where the session has no route for it, a session verb.
- The hook bars and the arc are the Atlas's reconstructions and are lighter
  than the stock art: the stock hook is about 15 u wide where the vector one
  is 11 u, and the stock arc carries a socket where each bar joins it.

### 12.6 The initializing screen

**Status: built, off by default.** While the engine starts it repaints one
screen between its startup steps (`RetainedUI_DrawInitialization` in
`src/ui/RetainedUI.cpp`). With `ui_retained 1` that screen is the retained
document `guis/loading/initialization.rui`; with `ui_retained 0` the engine
keeps its fallback, the stock loading painting with its characters and a line
of console text. The retained screen does not use the painting or any other
retail picture, and draws no characters: it is portal light in space, the
cool register of section 2 alone.

`tools/ui/build_retained_initialization.py` writes the document, and
`tools/ui/initialization_textures.py` paints its nine textures into
`content/basepr/pak1/guis/assets/initialization/` from fixed seeds. `--check`
reports either as stale (the Meson test `openprey-retained-initialization`);
edit the generators, never their output.

#### Composition

Lengths are dp on the retained 720 dp canvas, from the screen's centre, y
down. Everything sits on the vertical axis through the centre, so every
aspect keeps it; the scene is drawn on a 3200x1800 dp stage, so it runs
full-bleed from 4:3 to 32:9.

| Layer | Place | Construction |
| --- | --- | --- |
| Space | Full bleed | A near-black field, `#010207` to `#040915` downward |
| Nebula | 2000x1000 dp about the centre | Two added textures. The far one is rolling gas: violet (`#5B2EA6` to `#7A2FA8`) to the upper left, teal (`#1497B8` to `#1FB9A6`) to the right, blue between and in a bridge over the wordmark, cut by dark dust lanes, lit pale where it is densest and scattering a soft glow; it carries a faint dust of unresolved stars. The near one is finer bright wisps. The middle of the lower half stays dark for the energy and the status line, and both fade to nothing before their edge |
| Stars | The stage | 300 sharp diamonds, 0.55 to 1.9 dp, white to pale blue, which hold still, and eleven bright stars with a halo and a cross of lens spikes |
| Energy ball | 0, 128 | An orb 56 dp in radius: an inside of plasma filaments wrapped on a sphere, hot at its heart, under a bright limb with a short corona. Spiralling plasma in two layers at its heart, four loops of plasma on tilted orbits (radius 68 to 102 dp), two ray bursts, a pale core, and a `prey.portal.body` halo (720 dp) that lights the space about it |
| Beam | From the ball up off the screen | Three vertical bands, glow (180 dp), body (40 dp) and core (9 dp), each a horizontal gradient to `prey.portal.core` and white, added. A mask keeps it full to the flare and fades it out above |
| Flare | 0, -148 | A bloom, a faint lens ring (radius 182 dp), seven rays, a fine burst, a hot centre, and three horizontal streaks: wide (2600x90 dp, `prey.wordmark.streak`), core (1900x16 dp, `#CFF6FF`) and hot (860x6 dp, white) |
| Wordmark | On the flare, 700 dp wide, capitals 54 dp | `PREY` traced from the menu face and widened 1.6 times, as the Interface Atlas draws it: a dark fill (`#16304C` through `#010204` to `#10243A`, top to foot), a 1.5 dp `prey.wordmark.edge` outline and a soft cyan glow |
| Status line | Centred on 262 | The startup step in the body face, 20 dp, `prey.text.nav` at 0.9, 1.5 dp tracking |
| Progress rule | Top at 292 | Seven 34x2 dp segments on a 40 dp pitch, `prey.text.nav` at 0.16, lit to 0.85 as steps complete, and a spark of portal light on the current one |

The step comes from the message: `#str_04343` (Loading) is step 0 and Prey's
six startup steps, `#str_04346` (sound) to `#str_04351` (menus), are 1 to 6.

#### Motion

- **At rest.** Space drifts: the far nebula turns 1.2 degrees and swells 4%
  over 96 s, the near wisps the other way over 70 s, so the layers part
  against each other. The bright stars twinkle on periods of 2.9 to 5.2 s.
  The ball breathes and flickers (0.94 to 4.2 s cycles); its inside turns
  once in 14 s, its heart's plasma in 9 and 6.5 s and its rays in 26 and
  41 s, in opposite senses, and each plasma loop runs round its orbit in
  2.7 to 5.6 s. Pulses of energy climb the beam on
  five unequal cycles (2.3 to 5.3 s) and the beam's bands shimmer. The
  flare's streaks breathe and its rays sway. A glint crosses the lettering
  every 9 s.
- **Steps.** A new step's line fades and rises 7 dp into place over 320 ms;
  the marker glides to its segment over 440 ms and the segments it passes
  fill in turn, 70 ms apart.
- **Entrance (1.4 s).** The first frame is black and pays for the
  document's creation; the entrance then plays from the start. The black
  lifts over 220 ms while space eases back from 110%. The ball ignites from
  a point, overshoots to 116% at 300 ms and settles by 620 ms. From 220 ms
  the beam shoots up out of it behind a bright front, which strikes the
  flare at about 420 ms: the flare flashes and stretches out to either side
  (118% at about 720 ms, at rest by 960 ms), the wordmark appears in 120 ms
  under the flash's peak, the status line and rule rise into place by about
  1 s, and the first glint crosses the lettering from 1.15 s.
- **Reduced motion** (`ui_retainedReducedMotion`) shows the rest pose at
  once: no entrance, loops, pulses, marker or glint.

#### Cost

The screen repaints while the engine loads, so it must be cheap to build.
Soft light is drawn as textured quads (four vertices each) that scale and
turn without being compiled again; a vector gradient that soft subdivides
into thousands of triangles. Only edges that must stay sharp are vectors,
and they hold still or move in ways that keep their compilation: the beam's
bands are plain triangles, the sharp stars stay out of the entrance's zoom,
and the wordmark rests at an opacity of 0.002 rather than 0 before it
appears, so that it compiles in the veiled first frame, and then appears in
120 ms rather than fading, since every frame of a fade compiles its glow
again. No light passes through a zero scale (a light at rest between
appearances is held at 0.001): a degenerate transform sent an earlier
draft's gradient subdivision into a loop.

The engine repaints the screen on a pace of its own (60 Hz on a smoothed
frame cost, within half the time during the entrance and a fifth after it).
Measured on 20 November 2026 (windowed OpenGL at 1280x720, on a machine
shared with other runs): about 110 repaints in a start of 4.5 to 6 s, 0.7
to 1.3 s of it repainting; frames at rest build in 3 to 7 ms and entrance
frames in up to 20 ms, about 60,000 vertices at rest, most of them the
wordmark's antialiased letters and glow. The stock fallback repaints three
times. The first three startup steps (sound, network, renderer) run before
the screen can draw, so the rule moves from step 0 straight to step 4.

## 13. Project branding

openPREY's own marks live in `assets/`:

| Asset | Path | Use |
| --- | --- | --- |
| Application icon | `assets/icons/prey.*` | The hawk Talon in red and orange flame with a cyan electric edge; executables, desktop entries, installers |
| Splash | `assets/splash/prey_rt_bitmap_4001.bmp` | Windows startup splash: the stone hawk with the dark extended wordmark |
| README banner | `assets/docs/img/banner.png` | "open" in a white geometric sans beside "PREY" in dark navy extended capitals, over the Sphere and the glowing spirit hawk |
| Release package home | `assets/release/README.html` | The `README.html` at the root of every package: the portal rim, Sphere and Earth's limb behind the hawk and wordmark, the arc of hooks as its section menu, the home bottom bar for its documentation links, and claw-cornered frames with setting-row plates and 3-slice buttons for its content |
| Project overview and documentation portal | `assets/docs/README.html`; `SITE_CSS` in `tools/build/generate_release_docs.py` | The same vocabulary for the repository overview page and every packaged documentation page; side columns are tab containers whose links are side tabs |
| Web faces | `assets/docs/fonts/openprey-{menu,default}.woff` | The display and body tracings, subset for the pages above by `tools/assets/fonts/embed_atlas_fonts.py`; the release home embeds them so it works offline from an unpacked archive |
| Consoles | `kConsole*Color` in `src/framework/Console.cpp`, `S_COLOR_CONSOLE` in `src/idlib/Str.cpp`, `src/sys/sys_console_theme.h` | In-game console: black field (`prey.space`), text, edge and accents in `prey.portal.core` `#A4F9FE`, selection `prey.portal.body` `#2F64DC`, version `#6D7F95`. System console (Win32 and SDL): dark slate from `prey.sphere.shell`, never black: window `#0F171B`, log `#172229`, input `#121B21`, buttons `#1F2D36`/`#2A3D48`, borders `#2A3D48`/`#4A6F84`, text `#A4F9FE`, secondary text `#7F95AA`; the fatal-error strip keeps its red-orange |

Rules for project material:

- Write the project name `openPREY`: lower-case "open", upper-case "PREY".
  The game is "Prey" in running text and `PREY` only in the wordmark.
- Set "PREY" in a wide extended face with generous tracking, never condensed.
  Pair it with a plain geometric sans for "open" and for taglines.
- Use the hawk as the project emblem. Draw it in cyan light (`#1BDDEF` to
  `#AFFCFF`) on dark grounds or in the icon's flame colours; do not recolour it
  steel or olive.
- Ground project material in space black with portal blue light
  (`prey.portal.body`, `prey.portal.core`); keep the warm hawk as the single
  warm element.
- The retail wordmark and box art belong to their owners. Project material
  reconstructs the style; it does not reuse the retail bitmaps.
- `assets/` holds only openPREY's own marks. The upstream Quake 4 icons,
  splash and trailer logo were removed in `d39359088`; if a merge from
  `openq4-upstream/main` brings them back, leave them out of `assets/` and
  out of every package.

## 14. The Interface Atlas

[`prey-ui/atlas/prey-interface-atlas.html`](prey-ui/atlas/prey-interface-atlas.html)
is a single self-contained page of vector reconstructions, drawn to this
document's measurements. Its twelve sheets are numbered, and each names the
sections it draws:

| Sheet | Draws | Sections |
| --- | --- | --- |
| 01 Home screen | The home screen at 4:3, 16:9 and 21:9, out of game and in game, with both backdrops (the 3D scene of section 12.2 and the stock painting, drawn from one measured plate table so that they coincide at rest); the portal rim scaled to the screen's width; navigation hover; every page's growth from the bottom bar; the entrance on a timeline, in six frames and in plan and side elevation; the stock opening | 2, 3, 6, 8, 9, 12.2 |
| 02 Brand | The wordmark's construction, the hawk in its spirit and flame treatments, the project name | 2, 13 |
| 03 Tokens | Every colour token: text, furniture, world and brand, HUD | 4, 10.2 |
| 04 Type | The three faces with their metrics, the alien script, the type ramp at 1 u to a pixel | 5 |
| 05 Claw frame | The claw corner's construction and an assembled frame with its title bars | 6, Appendix B |
| 06 Plates | Buttons at rest, hovered and unavailable; header bar, setting rows, group box, radio segments, title bars, picture frame | 6, 7 |
| 07 Controls | The Options page at its stock size: top and side tabs joined to their page, openPREY's Video page row for row, stock binding rows, an example page of list, radio segments and check boxes, an edit field and the Reset Defaults dialog | 6, 7, 9, 12.1 |
| 08 HUD | The single-player HUD with live gauges, weapon bar, pickups, damage arcs, tips, the eight crosshairs and the spirit walk | 10.1 to 10.5 |
| 09 Rifle scope | The scope overlay: raising, zoom, heading and aspect | 10.8 |
| 10 Scoreboard | Deathmatch and team layouts | 10.6 |
| 11 Devices | A force-field console with its overlay stack and the translation reveal; one tile for each device family | 11 |
| 12 Loading and credits | The loading screen and the credits' fly-in | 8, 9, 12.1 |

Example rows, names and scene dressing are placeholders and are labelled as
such. The home sheet labels the 3D backdrop as specified, not built.

- It contains no retail art or captures. It draws in Prey's own three faces,
  as the TrueType tracings openPREY ships in `content/basepr/pak0/fonts`
  ([ttf-font-system.md](ttf-font-system.md)), subset to Latin and embedded as
  WOFF by `tools/assets/fonts/embed_atlas_fonts.py`; run that tool after any
  font rebuild. The same run refreshes the release package home and the web
  faces under `assets/docs/fonts/` (section 13). Sizes follow the engine (a
  `textscale` of s is a 48 s u em), and display text is lowered by the menu
  face's 6/48 em baseline lift. Only page prose (Saira Condensed) and
  captions (IBM Plex Mono) load from Google Fonts.
- Update it in the same change as this document whenever a measurement,
  token or behaviour changes, and bump the version in both. The page's
  header carries the version.
- Keep the page's own text legible: the document's 4.5:1 contrast target
  (section 4) applies to its captions and labels too.
- The file is a complete standards-mode HTML document (doctype, `<head>` with
  charset and viewport, `<body>`), so opened from disk it renders exactly as
  the published copy does. Keep every `<style>` block in the head.
- A published copy for sharing is kept as the "openPREY Interface Atlas"
  artifact; the tracked file is the source of truth.

## Appendix A. Survey method

The 1.0 survey read the retail `pak_data.pk4` and `pak_en_t.pk4` of a CD-era
install: 106 `.gui` and 30 `.guifragment` scripts, 519 interface images, the
three faces' `.dat` metrics and atlases, `materials/guiresources.mtr`,
`interface.mtr`, `weaponguis.mtr` and the English language table. Scripts were
aggregated for colours, faces, `textscale`, materials, transitions and sounds;
interface art was sampled for colour, alpha profile and visible bounds.

Captures came from openPREY itself, in a hidden window at 1280x960 so the 4:3
canvas maps to 2 pixels per unit, with the stock GUIs loaded through `testGUI`:

```text
openPREY-client_x64.exe +set fs_basepath <Prey install> +set fs_savepath <private dir>
  +set r_fullscreen 0 +set r_hiddenWindow 1 +set r_mode -1
  +set r_windowWidth 1280 +set r_windowHeight 960
  +set r_customWidth 1280 +set r_customHeight 960
  +set win_allowMultipleInstances 1 +set s_noSound 1
  +exec uisurvey.cfg
```

`r_windowWidth` and `r_windowHeight` set the hidden window's size; the
`r_custom*` pair alone can yield 1280x720 frames. `win_allowMultipleInstances`
keeps the launch from exiting when another openPREY client is already running.

The configuration runs `testGUI <file>`, `waitMsec`, `GuiEvent` and
`screenshot`. To open sub-menus without host input, the survey used a private
copy of `mainmenu.gui` in the private save path with test-only named events
that call the stock `*_AnimIn` and `*_AnimOut` timelines. Captures and copies
stay outside the repository.

The rifle scope (section 10.8) was captured the same way for version 1.8.
`testGUI` opens a GUI with no game state behind it, so the survey used private
copies of `guis/weapons/sniperoverlay.gui` in which `gui::fov` and `gui::yaw`
are replaced by fixed values: zoom values 0.3, 0.7 and 1.0, yaw 0 and 40. One
copy adds a mid-grey ground beneath the overlay, so that the lens and the
multiplied reticle show. Each was started with `GuiEvent zoomIn` and captured
at rest after 3.2 s; one more run was captured at about 150 and 450 ms.

### Later captures

Since 11 November 2026 a configuration file can drive the stock menu, so a
capture no longer needs a private copy of `mainmenu.gui`:

- `openq4_guiAction <window>` runs a window's `onAction`; with `release` it
  runs `onActionRelease`, for the buttons that act on release (Resume Game,
  the Profiles buttons, message-box buttons). Every ancestor of the window
  must be visible, so switch to its tab first.
- `openq4_guiSet <window>::<variable> <value>` sets a window variable:
  `openq4_guiSet Options_TabContainer::activetab 2` shows the Video tab.
  `openq4_guiSet gui::<key> <value>` sets a GUI state value, and
  `openq4_guiGet` reads a window variable.
- `openq4_guiCursor <x> <y>` places the pointer, which otherwise follows the
  system mouse and is missing from an unattended capture.
- `openq4_browser report`, `select` and `hover` read and drive the server
  browser.

Launch `.install/openPREY-client_x64.exe` in a window (`+set r_fullscreen 0`)
with a private `fs_savepath` under `.tmp/<task>/` and `+set logFile 2` for a
log. `wait` counts frames, and the menu draws several hundred a second: wait
about 1500 before the first action and 3000 to outlast a two-second timeout.
A fresh save path counts as a first launch, which detects a preset and
overwrites renderer cvars given on the command line, so set those from the
configuration file. A run that loads a map is muted with `s_volume 0`, not
`s_noSound 1`, which several map scripts cannot survive
([prey-subviews.md](prey-subviews.md)).

## Appendix B. Measured furniture

Texel measurements of the stock art in `guis/assets/menu/`. Proportions apply
at the drawn size.

| Art (texels) | Drawn (u) | Measurement |
| --- | --- | --- |
| `prey.tga` 512x64 | 476x37 | Letters fill the middle 60% of the height; edge `#AFFCFF`; streak to the full width at 0.24–0.71 alpha |
| `curve_ig.tga` 256x514 | 150x362 | Visible arc 3% coverage at 0.70; rail `#859BAF` to `#9DB8D0`, shaded edge and rivets down to `#586774` |
| `bar.tga` 256x32 | up to 178x19.5 | Hook in the leading 12%, ring in the trailing 4%, hairline between |
| `window_cornerul.tga` 128x128 | 38x32 | Rim 7 texels (`#B3C6E2`); body `#3B4351`; socket x 27–60, y 45–88 (34x44 texels, `#171B20`); silhouette x 2–127, y 0–114; beak along y 0–17 for x > 90 |
| `window_top.tga` 128x128 | edge 4 u | Opaque `#B3C6E2` for the top 49 texels (1.5 u), clear below |
| `titlebar_corner.tga` 16x32 | 12 wide | Slant from x 1 at the top to x 10 at the foot; `#5C6C81` at 0.60 (the strip between is 0.69) |
| `titlebar_corner_inv.tga` 16x32 | 8 wide | Slant from x 10 at the top to x 1 at the foot |
| `button/strip.tga` 256x64 | button body | Rims at y 4–6 and 58–60 opaque; fill 0.77 → 0.06 across the width |
| `button/rollover_strip.tga` 256x64 | button body | Same rims at 1.0; even fill 0.30 |
| `button/corner.tga` 32x128 | 12 wide | Stroke from x 24–30 at y 16 to x 3–10 at y 111: the end leans outward toward the foot |
| `button/invcorner.tga` 32x128 | 12 wide | Stroke from x 1–6 at y 16 to x 22–27 at y 111 |
| `textbarstrip.tga` 256x32 | row body | 1-texel rims at 1.0; fill 0.77 → 0.06 across the width, 0.4 at mid-height |
| `textbar_corner.tga` 16x32 | row start | Slant from x 1 at y 4 to x 10 at y 27 |
| `textbar_invcorner.tga` 64x128 | row end | Curve from x 13 at y 16 to x 48 at y 111 |
| `text_titlebarstrip.tga` 256x32 | header body | Rims `#6D7F95` at y 0 and 31; inner `#3C4A5A` 0.8; body `#111A25` 0.6 |
| `tabstrip.tga` 16x32 | idle top tab | Opaque `#252831` |
| `tabstripactive.tga` 16x32 | active top tab | `#7F95AA` at the top through `#3E4C5A` to `#222A31` at the foot |
| `tabedgeactive.tga` 64x128 | active top tab end | Rim `#B3C6E2` along the top and leading edge |
| `tabhstrip.tga` 64x16 | idle side tab | `#3E4C61` at 0.40–0.46 |
| `tabhstripactive.tga` 128x16 | active side tab | `#5A6E80` on the leading edge to `#222A31` toward the page |
| `tabtopactive.tga` 128x16 | active side tab start | Rim `#A7BFD7` 2 texels along the top |
| `pictureframe_corner.tga` 16x16 | frame corner | Rounded stroke 4–5 texels, `#A7C4E8` |
| `fadebg.tga` 256x256 | tab page | `#222A31` from its top and leading edges: 0.90–0.97 at the edge, 0.81 at 8 texels, 0.64 at 16, 0.28 at 32, 0.06 at 48, 0 by 64. `fadebg_top` and `fadebg_side` carry one edge each |
| `checkbox.tga` 32x32 | about 12x12 | Ground `#39424A`; cross `#ABC5DD`, strokes 7 texels |
| `bottombar.tga` 512x32 | 304x30 | Socket ring at each end; rim `#B0CEF7` |

### Backdrop composition

Fitted to the home screen captured at 1280x960 (Appendix A). Least-squares
circle fits; the residual is the largest distance of a sampled edge point from
the fitted circle.

| Feature | Geometry (u) | Residual | Notes |
| --- | --- | --- | --- |
| Portal glow edge | Circle centred at 404,192, radius 368 | 1.4 u | Space lies inside; the glow fades to black at this edge |
| Portal core | About 20–30 u outside the glow edge | — | Peak `#DDFFFF`; along y 240 u: `#59A2FF` at the screen edge, `#D0FFFF`–`#DDFFFF` at 12–21 u, `#40C6FD` at 27 u, `#063C8D` at 39 u, black by 50 u |
| Sphere | Circle centred at 357,222, radius 186 | 3 u | Fitted to the painted disc of `background3.tga`; both stock layers span 165,30,384,388 and the sun sits at 357,224 between them |
| Earth's limb | Circle centred at 689,2069, radius 1695 | 2 u | The solid edge of `background2.tga` in its 0,330,640,150 rectangle: through 99,480, 350,408 and 639,374. A glow fades out 45 u above it; a fit to the glow's visible edge in a capture gives 683,2151, radius 1780. Earth draws after both Sphere layers, so it lies in front of the Sphere's foot |
| Plates | 133 plates over 17% of the disc; semi-axes 8 and 3 u at the median, up to 16.5 and 8 u | — | `background4.tga`, each connected plate fitted as an ellipse. Mean colour `#2C4366`, the same on the lit and the dark side. The Interface Atlas source holds the table |
| Navigation arc | From about 61,104 to 192,461 | — | `curve_ig` alpha begins near the top of its 150x362 rectangle |

Section 12.2 takes the Sphere, Earth and plate rows as the 3D backdrop's rest
composition.

## Appendix C. Observations recorded during the survey

These were seen while capturing and are recorded for follow-up. C.1 lists
what is still open, C.2 what openPREY has since fixed and how each fix was
checked, and C.3 slips in the retail data, which stay as shipped unless a
change says otherwise (section 11.7). None of them changes a measurement in
the sections above.

### C.1 Open

- Front-end survey, 11 November 2026: a long sound device name still runs past
  the stock value column. The Mods list shows the version from the build's
  base version, taken from upstream openQ4 tags (0.13.2), and lists `basepr`
  itself.
- The Reset Defaults dialog's 0.80 scrim did not visibly darken the Options
  page beneath it in the capture. The scrim is a GUI fill drawn under image
  plates, so this is likely the same draw-order cause; it has not been
  rechecked since `70b9d052a`.
- openPREY's Post FX and Advanced FX pages sit on a 28 u row pitch with labels
  at 0,0,200,25 and `textaligny 0`; stock pages use 30 u, 5,5,190,20 and −6.
  Bring them to the stock pitch when they are next edited.
- `hud/hud_lighter.guifragment` carries no `screenalign` keys, although the
  health figures beside it are pinned to the bottom-left corner. On a wide
  screen the lighter meter should therefore stay on the 4:3 canvas while the
  figures move out; not yet checked in a capture.
- The server browser's game-type tables are Quake 4's. Its game types,
  `l_gameTypes` and `ServerBrowserGameType` in
  `src/framework/async/ServerScan.cpp`, have no `deathmatch`. So a Prey
  deathmatch server's type shows as the raw token "deathmatch", both in its
  row and in `server_gameType` (seen in the server-details check of C.2). The
  stock page's game-type filter (`MFS_FilterGametype`, `#str_20194`
  "Any;Deathmatch;Team DM") sets `gui_filter_gameType` to 1 or 2, which
  `IsFiltered` reads as `l_gameTypes`' "DM" and "Tourney". Neither matches
  what a Prey server reports, so either choice hides every server. This is
  read from the code and was not run. `RETAINED_CREATE_GAMETYPES`
  (`src/framework/Session_menu.cpp`) offers the same twelve types.
  `Session_GetLongMPGameTypeName` (`src/framework/Session.cpp`) still names
  Quake 4's modes by `#str_41300` to `#str_41307`, which are Tommy's lines
  too. They are unreachable for the same reason, and the first four can reuse
  `#str_122046` to `#str_122049`.
- The stock Find Servers page's players filter (`MFS_FilterPlayers`,
  `#str_20197` "Show all;Hide full;Hide both") keeps Doom 3's values, where 2
  hides full and empty servers. The engine reads `gui_filter_players` as Quake
  4's two bits (`#str_200306`'s four choices), so "Hide both" hides only empty
  servers.
- A LAN scan lists a server once for each address that answers it. In the
  server-details check of C.2, one dedicated server bound to `127.0.0.1:28004`
  and `[::]:28004` came back six times: once on loopback and once per IPv6
  link-local interface (`GetLANServers`' multicast sweep).
- Startup logs warn about upstream Quake 4 front-end files
  (`guis/arena_menu.gui`, `arena/openq4_campaign.cfg`,
  `gfx/guis/mainmenu/level_edge_fade`) that do not exist in Prey.
- `content/basepr/pak0` and `pak1` carry 640 GUI scripts and interface images
  (123 scripts, 517 images) that are byte-identical to the retail files,
  besides the 13 modified scripts and 16 new images, 15 of them edge tiles.

### C.2 Fixed in openPREY

Each entry names its commit, or is marked uncommitted where the fix was still
in the working tree when version 1.14 was written. The engine entries are
kept because the survey found them and the stock screens of sections 7 to 11
depend on the behaviour they restore; `docs/dev/releases/unreleased.md`
carries their summaries.

- **The backdrop after a live preset change** (rechecked 21 November 2026,
  `6624aa1fc` and later): applying a different performance preset while the
  menu was up (`applyPerformancePreset balanced` from Enhanced, the command
  the Quality Preset row runs) turned the main menu's backdrop white outside
  the 4:3 panel and grey behind it until the next `vid_restart`. Balanced,
  Minimum, Ultra and Enhanced applied in turn over the stock menu, and steps
  of the retained Quality Preset row and Detect, now leave it as it was. The
  commit that fixed it was not identified; the renderer-reload fixes merged
  from openQ4 (`966d8ae6f`) are the likeliest.

- **Tab labels under OpenGL** (`70b9d052a`): in openPREY's Options and
  MultiPrey pages, the four top tab labels and the active side tab's label did
  not draw under OpenGL. They were drawn, then covered by their own tab
  plates: `RB_STD_DrawView` split 2D GUI views by material sort around the fog
  pass, so all `SS_GUI` text and fills drew before any `SS_MEDIUM` image, and
  Prey's implicit `.tga` tab plates are `SS_MEDIUM`. 2D views now draw in
  submission order, matching retail and the Vulkan path. This also restores
  the tab labels in `mpmain.gui` and `help.gui`, and text that sat under
  translucent plates (setting labels, the bottom-bar "Return to Main Menu",
  the Action and Key Assignment headings) now draws at full strength. The
  measurements in this document come from retail scripts and art, not from
  those dimmed captures.
- **The page outline under an active tab** (`2a032db7f`, `src/ui/Window.cpp`):
  tab pages drew their `#BDCFE0` separator along all four edges
  (`idWindow::DrawBorderAndCaption`), the edge under the active tab included,
  which put a one-unit line between an active tab and its page, against the
  rule of section 6. The separator now stops at the active tab's two ends.
- **Repeated window names** (`src/ui/Window.cpp`): `map game/feedingtowerb`
  stopped on the map-start autosave with `idWindow::WriteToSaveGame: child
  'elevatortext' … 'guis/elevatorcall.gui' has an inconsistent parent`. The
  script defines two text windows named `elevatortext`. Retail kept both,
  because a plain leaf window became an `idSimpleWindow` that a later
  definition of the same name could not replace; openPREY keeps every window
  as a full `idWindow`, so the second definition was parsed into the first,
  which dropped the first text line and cleared the window's parent pointer. A
  repeated name now makes a second window where retail did, and a window that
  is redefined in place keeps its parent and child id. The same rule applies
  to the first `LoadListCap_Top` in the Load Game list and the first
  `bg_keeper2` in `dialog_elhuit.gui`, which were being replaced the same way;
  those two have not been checked in a capture.
- **The autosave's payload version** (`9ef7412e2`;
  `src/game/gamesys/SaveGame.h`, `SaveGame.cpp` and
  `src/framework/SaveGameReleases.h`): the same autosave did not reach disk.
  The staged file was rejected with `has invalid payload footer marker`, and a
  manual `savegame` failed the same way. The Prey game library stamped its
  payload as compatibility version 2, while the engine appends the integrity
  trailer that it only expects on version 3 and later payloads, so it looked
  for the footer 16 bytes late. The library now stamps version 5, the version
  the session writes, with the build's own wire-ABI stamp, and reads the
  trailer after its footer. `feedingtowerb`, `roadhouse` and `salvage` each
  write their map-start autosave and a manual save, and `loadgame` restores
  them without save or GUI stream errors. See
  `docs/dev/savegame-reliability.md`.
- **Repeated names in the credits** (`2a032db7f`, `src/ui/Window.cpp`):
  `creditDef` lines in `mainmenu_creditcontent.guifragment` reuse names too
  (`CreditWriting3` twelve times over). They carry scripts, so each repeat was
  still parsed into the earlier window, and only the last line of the Writing
  section drew. Every repeated definition now makes its own window, as in
  Prey's Doom 3 engine; a lookup by name finds the first. The full credits
  have not been compared line by line with retail.
- **Menu commands the engine ignored** (uncommitted,
  `src/framework/Session_menu.cpp`; front-end survey, 11 November 2026): the
  front-end commands that Prey's stock pages send and the engine ignored.
  Retail `PREY.exe` 1.4 was read for each.
  - Reset Defaults: `resetgame`, `resetvideo` and `resetaudio` now each
    reset the cvars that their Options page shows, as listed in
    `Session_ResetMainMenuCVars`. Retail reset every cvar flagged
    `CVAR_GAME`, `CVAR_RENDERER` or `CVAR_SOUND`. In openPREY those flags also
    cover the player name, server settings and developer cvars, so the reset
    leaves those alone. After the Video reset the engine detects a preset, as
    a first launch does (retail ran `setMachineSpec`). If a reset changes a
    setting that needs a restart, Apply Changes lights. If it changes the
    audio device, speakers, OpenAL or EAX, the sound system restarts.
  - Controls > Profiles works as retail's did. Save As writes the bindings to
    `<name>.binds` in the save path's game directory (`unbindall`, then
    `bind` lines). Load runs only that file's binding commands, and Delete
    removes the file. Path, wildcard, quote and command characters are dropped
    from a profile name.
  - MultiPrey > Player Settings no longer shows Game Key Status. openPREY has
    no key check (its key state is always N/A) and no key prompt, so the row
    is hidden. Auto Weapon Switch and the player-model block move up 30 u
    (`mainmenu_multiplayer.guifragment`).
  - Resume Game shows on the out-of-game menu while a loadable save exists,
    and loads the newest save. Deleting the last save hides it again.
  - Updates shows a waiting box ("Checking for updates...", with Cancel) until
    a reply comes or two seconds pass. With no reply it now says that the
    update server did not reply; it no longer says "Prey is up to date". The
    version-reply prompt's missing `#str_104330` is now defined
    (`src/framework/async/AsyncClient.cpp`, `strings/*_openprey.lang`).

  Captures used `openq4_guiAction <window> release`, which runs a window's
  `onActionRelease`. Resume Game, the Profiles buttons and the message box
  buttons act on release.
- **`onTabActivate` commands** (uncommitted, `src/ui/Window.cpp`): a tab's
  `onTabActivate` command was never dispatched.
  `idWindow::UpdateTabContainerState` ran the script, but the command stayed
  on the tab window, and the tab's next `idWindow::Time` cleared it before it
  could reach the GUI's pending commands. A click lost it the same way,
  because the tab container returned an empty command once the tab changed.
  The tab-flip sound, Player Settings' `modelscan`, Create Server's
  `CheckUpdate ; MAPScan`, Find Servers' `UpdateServers ; CheckUpdate` and the
  Profiles page's `scanforprofiles` were all lost. Now a tab switch moves the
  commands that `onTabActivate` raises on the tab into the GUI's pending
  commands, as timeline events' are, while the GUI is active. That includes a
  named event that the tab answers itself, as Find Servers does. A click
  returns them at once. The first tab state, set when the GUI initialises, is
  not a switch: its script still runs, but its commands are dropped, so
  opening a menu plays no tab-flip sound and starts no scan. `gui_debugScript
  3` logs each queued command (`GUI: onTabActivate window=... queues "..."`).
  Checked in the windowed client from `.install/` by switching tabs with
  `openq4_guiSet <container>::activetab N`: the Options tabs, Controls >
  Profiles, and MultiPrey's Player Settings and Create Server each played the
  tab-flip sound (`s_showStartSound 1`), and Create Server sent its version
  check. The click path was checked only by reading the code. The session
  still lists profiles whenever the menu opens, because a menu reopened on the
  Profiles tab does not switch to it.
- **Commands raised through a script's `namedEvent`** (uncommitted,
  `src/ui/GuiScript.cpp`): a command raised on another window through a
  script's `namedEvent` was lost. A named event runs the script of each window
  that answers it, and a `set "cmd"` there raises the command on the answering
  window, whose next `idWindow::Time` cleared it. Opening MultiPrey runs
  `namedEvent "Multiplayer_FindServers::ScanForServers"` from
  `Multiplayer_AnimIn`, which raised `UpdateServers ; CheckUpdate` on
  `Multiplayer_FindServers`. The unqualified form lost commands the same way:
  Apply Changes on Options > Video runs `namedEvent "VidRestart"`, and
  `Options_Video` raised `video restart`, so neither Apply Changes nor leaving
  Options restarted the video mode. Now `Script_NamedEvent` queues the
  commands that the event raises on the windows it reaches, as timeline
  events' are, while the GUI is active. That covers the named window and its
  children, or the whole GUI for the unqualified form. The sending window
  keeps its own commands, which its script's caller returns. A window that
  answers its own event, as Find Servers' `onTabActivate` does, therefore
  sends them once. Commands already on a window before the event stay where
  they were. `gui_debugScript 3` logs each queued command (`GUI: namedEvent
  '...' window=... queues "..."`). Checked in the windowed client from
  `.install/`. Opening MultiPrey (`openq4_guiAction MainOG_Title4`) queued
  `UpdateServers ; CheckUpdate` from `Multiplayer_AnimIn`. Those ran before
  its own `modelscan`, and the client sent its version check (`developer 1`).
  Apply Changes (`openq4_guiAction OVN_ApplyChanges`) ran one `vid_restart`.
  Switching back to the Find Servers tab queued its commands once, through
  `onTabActivate` alone. The queueing now lives in
  `idUserInterfaceLocal::RunNamedEvent`, which the next entry shares.
- **World-GUI commands for events the game sends** (uncommitted,
  `src/ui/UserInterface.cpp`): the commands that a world GUI raised for a
  named event sent by the game were lost. `idEntity::CallNamedEvent`
  (`src/game/EntityAdditions.cpp`) sends the event through
  `idUserInterface::HandleNamedEvent`, then calls `HandleEvent( SE_NONE )` to
  collect the commands, as Human Head's comment there expects. The commands
  landed on the answering window, usually the Desktop, and the desktop's
  `HandleEvent` clears its own `cmd` first, so the call returned nothing. Lost
  were an AI-used console's `AIUse` (`activate ; play
  console_generic_activate` on the alarm, forcefield, wallwalk, portal and
  generic consoles, `spin` on the slots), `ScriptUse`
  (`generic_unlock_1.gui`), `Death` (`noninteract_d.gui`), the roadhouse
  games' `TurnOn` and `Update` (`reset`, `play console_game_gameover`), the
  arcade game's `TurnOff` (`reset`) and the jukebox's `TurnOn`,
  `TurnOnRoadhouse` and `TurnOff` (`turnon`, `turnoff`). In retail `PREY.exe`
  1.4, `idUserInterfaceLocal::HandleNamedEvent` only runs the desktop's
  `idWindow::RunNamedEvent`. That function clears the window's `cmd`, runs the
  event on the window and its children, then appends what the window raised to
  the GUI's pending commands, with no check that the GUI is active. Now
  `HandleNamedEvent` queues the commands that the event raises on any window,
  whether or not the GUI is active, as retail did. An entity GUI is active
  only while the player points at it (`idPlayer::UpdateFocus`), and an AI uses
  a console the player need not be looking at. Commands already on a window
  before the event stay where they were; retail cleared them. The script
  `namedEvent` (previous entry) goes through the same function, keeping its
  sender exception and its active-GUI condition, so nothing is queued twice.
  Of the shipped GUIs, only world GUIs answer a game-sent named event with a
  command. No HUD fragment does, so nothing piles up on the HUD, whose
  commands nothing reads, and the session's events to the menus raise none.
  Checked in the windowed client from `.install/` with `gui_debugScript 3` and
  `s_showStartSound 1`. On `game/harvesterb`, `script
  "map_harvesterb::OutdoorBridgeCycle();"` sent `ScriptUse` to
  `hrvBBridgeConsole`: `play console_generic_deactivate` was queued once and
  the sound played once. On `game/roadhouse`, `ArcadeGamesTurnOff()` queued
  the arcade game's `reset`, `JukeBoxPlayAbduction()` queued `turnon`, and
  `UFOFlyBy1()` queued `turnoff` on both jukebox GUIs, after which the jukebox
  stopped its track. No command was logged as not handled. Opening MultiPrey
  and Apply Changes were checked again: one version check and one
  `vid_restart`, and the menus queued nothing that the session sent.
- **Server browser status strings** (uncommitted,
  `content/basepr/pak0/strings/*_openprey.lang`): the server browser's status
  line and progress notice (`idServerScan::UpdateBrowserStatus` and
  `UpdateLoadProgress`) used Quake 4 string IDs that Prey's language files
  lack. Retail Prey has no strings for them, because its browser showed no
  scan status. During a scan the lookup warned "Unknown string id" every frame
  for `#str_107298` and `#str_107736`, about 1,500 times in the first second
  after MultiPrey opened. `#str_42861` (the idle count) and `#str_41502` (the
  mod filter's "All") are five-digit IDs, which the lookup does not warn
  about, so they showed as the bare ID. The English, French, Italian and
  Spanish `*_openprey.lang` files now supply them under Quake 4's IDs:
  `#str_107293`, `#str_107294` ("Scanned %d Prey servers"), `#str_107297`,
  `#str_107298`, `#str_107736`, `#str_42861` and `#str_41502`. They also
  supply the favorite labels `#str_200292` and `#str_200293`, which warned
  when the scan published the selection. Checked in the windowed client from
  `.install/`. Opening MultiPrey (`openq4_guiAction MainOG_Title4`) logged no
  Unknown string id warnings, and `openq4_browser report` showed "Getting list
  of servers...", "Scanning - Found: 0" and the filter "All". A LAN scan
  (`openq4_guiSet gui::lanSet 1` before opening) showed "Scanning for LAN
  servers...", then "Scanned 0 Prey servers" and "Showing 0 out of 0 servers".
  No server answered, so "Scanning %d/%d: %s" and the LAN's "Scanning - Found:
  %s" with a server name were not shown.
- **Server detail strings** (uncommitted,
  `src/framework/async/ServerScan.cpp`,
  `content/basepr/pak0/strings/*_openprey.lang`): a listed or selected
  server's details looked up Quake 4 string IDs that Prey's files lack, or
  that mean something else in them. The tooltip's settings labels
  (`idServerScan::GetServerDetails`) warned "Unknown string id": Map, Yes and
  No (`#str_107702` to `#str_107704`), Time Limit (`#str_107659`), Pure
  (`#str_107662`), Team Damage (`#str_107664`), Auto Balance Teams
  (`#str_107666`) and Allow Spectators (`#str_104254`). The English, French,
  Italian and Spanish `*_openprey.lang` files now supply them under those IDs,
  in Prey's mixed case: retail Prey writes the same terms "Yes", "Time Limit",
  "Team Damage" and "Allow Spectators" (`#str_20125`, `#str_20154`,
  `#str_20151`, `#str_04254`). The selected server's `server_passworded` used
  Quake 4's "PASSWORD ENABLED" (`#str_200933`); it now uses retail's own
  `#str_41114`, "PASSWORD REQUIRED", which retail `PREY.exe` 1.4 sets for the
  stock page's "Passworded:" row. Quake 4's players-filter choices
  (`#str_200306`) are named only in a comment, so no lookup ever asked for
  them. Several game-type and limit labels collided with Prey's own IDs. Duel,
  Clan Arena, Freeze Tag and Red Rover (`#str_41300` to `#str_41303`) and
  Round Limit (`#str_41404`) are Tommy's subtitle lines in retail's
  `strings/english001.lang`. DeadZone's Control Time (`#str_122008`) is
  openPREY's own "Post Anti-Aliasing". The DeadZone type (`#str_42860`) is a
  five-digit ID that Prey lacks, so it showed bare. The code now names them by
  openPREY IDs: `#str_122046` to `#str_122049` for the four types,
  `#str_122050` Round Limit, `#str_122051` Control Time, and the existing
  `#str_122001` for DeadZone. None of these types can come from a Prey server.
  Prey's game library offers only `singleplayer`, `deathmatch` and `Team DM`
  (`si_gameTypeArgs`), and the cvar's value list turns any other value into
  `singleplayer`. Retail's filter likewise offers only "Any;Deathmatch;Team
  DM" (`#str_20194`). The Quake 4 rows stay, as upstream has them, but they
  can still show as the retained Join page's game-type filter names
  (`idServerScan::GameTypeFilterName`). Checked in the windowed client from
  `.install/` against `.install/openPREY-ded_x64.exe` on `game/dmshuttle1`
  (`net_ip 127.0.0.1`, `si_usePass 1`). After `openq4_guiSet gui::lanSet 1`,
  `openq4_guiAction MainOG_Title4`, `openq4_browser select 0`, `openq4_browser
  hover 0` and `openq4_browser report`, the client's `qconsole.log` held no
  Unknown string id lines. The selection read "PASSWORD REQUIRED". The tooltip
  read "Map: Shuttle 1", "Time Limit: 10", "Frag Limit: 10", "Team Damage:
  No", "Auto Balance Teams: No", "Pure: Yes" and "Allow Spectators: Yes".

### C.3 Retail data

- The Earth layer's last texel column (`preymenu/background2.tga`) is brighter
  than its neighbours. The stock hides it on the screen edge; under aspect
  expansion the main menu's Earth window stops 1.5 texels short of it
  (`matscalex 0.9985`) so it does not draw a line at the right slice's join.
- Retail authoring slips: `matcolor "1 1sd 0 1"` on the blackjack Stay hover
  (`guis/roadhouse/blackjack.gui:289`); `COLOR_BRIGHTORANGE_INVIS` defined
  with alpha 1.00 (`guis/hunterhand.gui:19`); bet-arrow hover tints a window
  with no art; `generic_1`'s hover is a no-op; a blue channel of 2 in
  `guis/biolabs/droid_recharge.gui:448`; the multiplayer weapon bar sits about
  39 u left of centre; the red team heading is 14 u tall and the blue 15 u;
  the out-of-game Load Game entry sets its own `forecolor` on hover, so its
  label never brightens (`guis/mainmenu.gui:531`); Save Game re-enables its
  navigation entry with `noEvents "0"` where the other pages set `"1"`
  (`guis/mainmenu/mainmenu_savegame.guifragment:36`).
- Retail references `guis/countdown.gui` and `guis/crane.gui`
  (`def/consoles.def:497,534`), which are not in the archives.

## Appendix D. Change record

### Version 1.22, 21 November 2026

- Section 12.5 adds the system check (`guis/menu/presetcheck.rui`) and its
  stock counterpart `guis/presetcheck.gui`, both new: a subsection describes
  them, and the document table and status table at the head list the
  retained one.
- Appendix C: the white backdrop after a live preset change no longer
  reproduces and moves from C.1 to C.2.

### Version 1.21, 20 November 2026

- Section 12.5 adds the retained level loading screen
  (`guis/loading/loading.rui`), with the progress outline traced from
  `bottombar.tga`; the status table at the head and the list of what is not
  yet built follow.
- Section 12.1: the loading picture is found as retail finds it, a save's
  screenshot first, and a picture without the tiles its window needs is
  drawn at 4:3.
- The Interface Atlas takes the version and draws the progress outline as
  traced.

### Version 1.20, 20 November 2026

- Section 12.6 is new: the retained initializing screen, with its
  composition, motion, entrance and cost. The status table at the head
  lists it.
- The Interface Atlas takes the version; no drawing changed.

### Version 1.19, 20 November 2026

- Section 12.5, Options: Up from a page's first control reaches its own top
  tab, and the bottom bar's two actions stop at its ends.
- Section 12.5, Load Game and Save Game: which pages the title and the pause
  prepare while they rest; Save Game and Credits joined.
- Section 12.5, "Not yet built": the pause names Prey's difficulties (Normal,
  Cherokee) instead of Quake 4's ranks, so it no longer logs an unknown
  string id.
- The Interface Atlas takes the version; no drawing changed.

### Version 1.18, 20 November 2026

- Section 3: the 4:3 canvas is centred on both axes, so on a screen taller
  than 4:3 a retained document's stage stays with the stock backdrop's
  wordmark and Sphere instead of the top edge.
- Section 10.1: the lighter is pinned to the bottom-left corner with the
  health figures.
- The Interface Atlas takes the version; no drawing changed.

### Version 1.17, 20 November 2026

- Section 4 adds `prey.softfocus`, and section 12.5 has the retained
  pop-ups soften the screen behind them: the home's frames as they grow,
  and every dialog beneath its stock scrim.
- Section 12.5: Options' Controls tab and the Reset Defaults dialog are
  rebuilt, so every tab of Options is the retained page's. It records the
  binding rows and how a key is taken, the Profiles page, and the dialog
  with its check boxes. The page now opens on Controls, as the stock page
  does. The status paragraph, the table at the head and "Not yet built"
  follow.
- The Interface Atlas takes the version; no drawing changed.

### Version 1.16, 14 November 2026

- Section 12.5 is new: the retained navigation, the first replacement built
  to section 12.3. It records what the home documents replace and what the
  stock menu keeps drawing, how the two hand over, the construction, and the
  measured relation between stock and retained text (size and the place of
  the capitals). It also records the retained Load Game and Save Game pages:
  how they present over the stock backdrop, grow and leave, how the list
  behaves and where they differ from the stock pages, and the retained death
  screen over the stock one's backdrop and fade, the Mods frame, and the
  retained Credits page laid out from the stock credits script, and the
  Options page with its tab furniture and the rows of its Game Options,
  Video and Audio tabs read from the stock script. The status paragraph and
  table at the head say what is built.
- The Interface Atlas takes the version; no drawing changed.

### Version 1.15, 13 November 2026

A second pass, which checks every path and line citation in the document
against the repository and the retail archives, and the atlas against the
pages it draws.

- Section 13 no longer forbids shipping Quake 4 icons, a splash and a
  trailer logo that left `assets/` in `d39359088`; the rule now covers a
  merge that brings them back. Every other repository path the document
  names exists, and every line citation falls inside its file.
- Appendix A records how captures are driven since 11 November: the
  `openq4_gui*` and `openq4_browser` commands, the frame-counting `wait`,
  the first-launch preset and the `s_noSound` trap.
- The contents list sections 10.8 and 11.4, which other documents cite.

The Interface Atlas corrects three drawings that had drifted from this
document:

- Its stock backdrop was an approximation with random plates, a Sphere
  184 u in radius about 357,224.5 and Earth's limb on the glow's circle.
  It is now drawn from the measured plate table through the rest camera,
  as the 3D rest frame is, so switching backdrops moves nothing (section
  12.2, rest composition).
- Its portal rim kept its 4:3 size on wide screens. It now grows with the
  screen's width about the canvas centre, as section 3 describes the
  build.
- Its Controls sheet showed a shortened Options page whose Video tab mixed
  openPREY's six side tabs with the stock Texture Quality segments. It is
  now the page at its stock size, with a 0.50 body, the six tabs 55 u
  tall and openPREY's Video page row for row (section 12.1); the radio
  segments and check boxes move to an example page.

Its faint captions inside drawings take the 4.5:1 colour, and its brand
rules follow section 13.

### Version 1.14, 13 November 2026

An editorial pass that checks the document against the repository and the
retail archives; no measurement of the stock interface changes.

- State: the header gains a table of what is built and what is only
  specified. Sections 3, 8, 9 and 12.2 no longer describe the 3D backdrop and
  its entrance as if they were in the build; section 12.2 opens with its
  status.
- Counts, recounted against the retail archives: openPREY overrides thirteen
  stock scripts, not eleven, and adds sixteen images (sections 1 and 12.1,
  Appendix C); `clickin` is used 128 times and `tabflip` 46 in openPREY's
  copies, and `tick` 18 (section 8).
- Side tabs: the stock Video page had three side tabs 110 u tall, not five
  at 66 u (section 12.1). The engine shares a column's height, less its
  margin, among its tabs.
- Section 3 lists the aspect-expansion values and keys in a table, with
  `naturalmatscale`, `canvasfill` and `matcanvasfill`. Section 12.1's
  aspect-expansion entry is split by screen.
- Line references into openPREY's `guis/mainmenu.gui` follow the rebuilt
  backdrop (sections 8 and 12.2, Appendix C).
- Section 14 lists the atlas's twelve sheets with the sections each draws,
  the Scoreboard sheet among them, and corrects the entrance to six frames.
- Appendix C is sorted into open observations, fixes and retail slips. Two
  entries that version 1.13 had already fixed are marked so (the tab page's
  outline under the active tab, and the credits' repeated window names), and
  the two fixes committed in `9ef7412e2` and `2a032db7f` no longer read as
  uncommitted.

The Interface Atlas numbers its sheets, keeps its sheet list in view while
scrolling and marks the sheet being read, enlarges its headings, raises its
faintest text to the 4.5:1 target, separates the token groups, adds the three
tokens its sheet had left out (`prey.text.headingInk`, `prey.heading.band`
and `hud.text`), and labels the 3D backdrop and entrance as specified, not
built.

### Version 1.13, 11 November 2026

Sections 3 and 12.1 describe the main menu's aspect expansion as rebuilt.
The stale flat painting under the stock layers is gone (it showed through
the additive stars and put a second Earth limb beside the layered one); the
star layers widen with the screen; Earth continues through new edge slices;
the portal's view scales to the screen's width, so the rim keeps its place
and no longer ends in a hard edge at the canvas, and its shimmer covers the
whole screen. Every edge tile, the flat painting's included, is regenerated
from the retail art by `tools/assets/generate_menu_backdrop_tiles.py`; the
previous ones continued only the flat painting and the bottom one was a
photograph of a desert Earth. Full-canvas colour fills now cover the
expanded canvas, so dialog scrims and fades dim the whole screen. Section
12.2 notes the `renderDef` `canvasfill` key.

Engine fixes that bring stock screens back to the stock: a repeated window
name makes a second window again, as in Prey's Doom 3 engine (the credits'
Writing section had collapsed to its last line); an active tab's page
outline now breaks across the tab (section 6, rule 1). Apply Changes sits at
the same height on all six Video pages, the Mods list puts each version in
its own column, the Sound Device choice stores the device name rather than
its label (and drops OpenAL Soft's "OpenAL Soft on" prefix from labels), the
Create Server page shows Prey's map pictures, and the Reset Defaults
dialog's Controls box restores Prey's key layout.

### Version 1.12, 11 November 2026

Section 10.8 records the rifle scope's aspect expansion as built in the
legacy GUI: the instrument stays on the canvas, the lens tint is tiled over
the whole screen at its stock pitch, and the veins turn on a square as wide
as the screen's diagonal. It measures what that square costs: the veins'
dark rim moves from the canvas edge to the screen's corners, so the middles
of the long edges are lighter than in the stock. Section 3 adds
`gui::virtual_screen_diagonal`, which the legacy GUI now publishes beside the
expansion values.

### Version 1.11, 11 November 2026

Section 13 records the console palette. Both consoles leave the Quake 4
amber and olive: the in-game console keeps its black field with portal-rim
cyan text and edge, and the system console moves to the Sphere shell's dark
slate, which is deliberately not black.

### Version 1.10, 11 November 2026

Sections 9 and 12.1 describe the reworked Video pages: a sixth side tab,
Display; the Quality Preset row that replaces the Texture Quality radio
segments; the display-reported resolution list; Render Scale, Frame Rate
Limit, Shadow Maps and Motion Blur rows; and numeric edit fields for window
and custom sizes. The Interface Atlas lists the six side tabs.

### Version 1.9, 11 November 2026

Section 6 states the other half of the tab rule in its own right: only the
active tab is joined to its page, and every inactive tab keeps the page's
outline beneath it, whole and at full strength. Version 1.7 said so in one
sentence, and the Interface Atlas broke it: its tab plates all ran 0.6 u
into the page, so the opaque inactive top tabs covered the outline and the
translucent inactive side tabs dimmed it. The atlas now ends an inactive
plate at the outline and runs only the active plate into the page.

### Version 1.8, 11 November 2026

Section 10.8 is re-measured from captures of the stock scope overlay drawn by
openPREY (Appendix A), which correct version 1.7 in several places. The
clamps are translucent 17° wedges under a cap, not the clawed heads held in
their art's unused alpha channel. The reticle is a ring 17.5 u in radius, not
22 u, and its wedges cross it. The rings stand at 165 and 175 u. The lens is
two things: a banded red tint that is constant, and veins whose strength
follows the zoom. The zoom scale is an outlined crescent with hooked ends and
a column of numerals. Zooming in raises the pointer, the opposite of what 1.7
assumed, and the compass turns against the clock as the yaw grows. The iris
blinks twice in every 5 s. The design rules now say to keep the reticle's
multiply, to draw the clamps as the game shows them, and to centre the
instrument, which the stock leaves 3 u off. The Interface Atlas's scope sheet
is redrawn to these captures.

### Version 1.7, 11 November 2026

Active tabs and their pages are one surface (sections 6 and 7): the page's
outline breaks across the active tab, the tab's rim leaves the joining edge
bare, and nothing is drawn between them. The page shading is remeasured: it
starts at 0.90 to 0.97 on the page's top and leading edges, not 0.66, in the
same `#222A31` the active tab ends in. Appendix C records that the engine
still draws the separator under the active tab.

Section 10.8 specifies the rifle scope: its twelve parts measured from the
stock overlay and art, the zoom range and the value that drives the lens and
the pointer, the raising sequence, and eight rules for openPREY, among them a
circular instrument on the true centre and a lens that covers the whole
screen at any aspect. The rules for HUD changes move to 10.9.

The Interface Atlas draws seamless tabs on every tabbed page and gains a
rifle scope sheet with zoom, heading and aspect controls.

### Version 1.6, 10 November 2026

Earth now stands in front of the Sphere, as the stock layers sort them, and
the entrance is a curved camera move (section 12.2). Version 1.5 kept Earth
far behind the Sphere and pulled the camera straight back without turning.
Earth is now the nearer body: radius 4.41 R, 5 R from the rest camera, its
limb 2.35 R away against 3.93 R for the Sphere's near face, so its limb and
glow cover the Sphere's foot at rest. The camera starts 0.41 R above the
Sphere's leading side, swings 38° round it while it pulls back to 4.93 R and
turns 35° to hold its aim; Earth passes in front at 425 ms and its limb
rises into the stock frame from 780 ms. The rest composition, the 1200 ms
duration and the easing are unchanged. The stars turn with the camera, the
Sphere holds its painted face until rest, and the engine notes and
acceptance checks gain the turning camera and the depth sorting. The
Interface Atlas draws the curve, sorts the two bodies by depth, shows the
entrance in six frames and maps the scene from above and from the side.

### Version 1.5, 10 November 2026

The 3D backdrop now rests on the stock composition (section 12.2). Version
1.4 placed a smaller Sphere on the wordmark's axis above a more curved Earth;
the rest frame is now an accurate recreation of the stock painting, measured
from the art: the Sphere 186 u in radius about 357,222, Earth's solid limb on
a circle of radius 1695 u about 689,2069 under its 45 u glow, and 133
self-lit plates in their painted places. The scene, the lighting, the
entrance's start framing and checkpoints, the aspect figures and the first
acceptance check are re-solved to it. The entrance keeps its 1200 ms and its
easing. Appendix B's backdrop rows are refitted to the art and gain the plate
layout, and `prey.sphere.shell` is resampled. The Interface Atlas draws the
new rest frame from the measured plate table.

### Version 1.4, 10 November 2026

Adds the 3D main-menu backdrop and entrance (section 12.2): the Sphere and
Earth as lit bodies under one camera, the rest composition, the 1200 ms
pull-back from the Sphere's shell, its variants, the engine work it needs and
its acceptance checks. Section 12 gains numbered subsections.

Corrects the survey against the scripts, the art and the engine:

- Tabs: top tabs draw the engine's default `tabedge` and `tabstrip` art; the
  values 1.3 gave for them belong to the side tabs. `prey.tab.idle` and
  `prey.tab.active` become `prey.tab.top` and `prey.tab.side`.
- Frames: `margins` insets the black body, not the children, so the claws
  stand clear of it. The home bottom bar is a claw frame, not `bottombar.tga`.
- Type: full-page titles are 0.55, small-frame titles 0.40, most buttons 0.33
  and list rows 0.25–0.34; the size and alignment statistics now name their
  file sets; the shadow rule lists its exceptions.
- Dialogs: only Reset Defaults uses the 0.80 scrim and the 360x250 frame.
- Motion and sound: `transition` acceleration is a fraction of the duration;
  the opening swaps the back portal model for the front one at 500 ms; credit
  titles alone fly in; `guisounds_menu_connect` marks a server refresh and
  `guisounds_menu_tick` a list, sort or radio change.
- Screens: Save Game, Death, Help, Options and the confirmation dialogs are
  described as scripted.
- HUD: line references follow the effective files; the low-health thresholds,
  selected-icon size, standings box, pinned groups and four art-sampled
  colours are corrected.
- Devices: the overlay stack is cited from `forcefield.gui`, in drawing
  order, with the screens that carry only part of it; ice-frame colours, the
  Keeper flicker, the octal rule's exceptions, the data rain and the sound
  sources are corrected.
- Colour: floats convert with `floor(255 x + 0.5)` throughout, which moves
  section 10's `4C` and `B2` components to `4D` and `B3`.

The Interface Atlas follows: its home sheet draws the 3D backdrop with true
perspective, plays the entrance on a multi-track timeline, shows it in five
frames and in side elevation, and keeps the stock backdrop and opening for
reference. Its frames, tabs, tokens and HUD values match this version.

### Version 1.3, 10 November 2026

Section 11.4 now describes the translation reveal as implemented in
`5d8f5b924`, read from the retail engine: alien text fades by
1 − `translationAlpha`, the English appears 6 u higher at `translationAlpha`
without a shadow, and `notranslation 1` only withholds the English. The
Interface Atlas's console demo follows it. Appendix C records the tab-label
fix (`70b9d052a`) and a new autosave crash, and Appendix A's capture command
gains `r_windowWidth`, `r_windowHeight` and `win_allowMultipleInstances`.

### Version 1.2, 10 November 2026

The Interface Atlas now draws in Prey's own faces: openPREY's TrueType
tracings, rebuilt with a smoother 48-point trace (build 1.100, see
[ttf-font-system.md](ttf-font-system.md)) and embedded as subset WOFF. Its
sizes follow the engine's 48 s u em, display text carries the menu face's
6/48 em baseline lift, and the alien script is the real alien face rather
than drawn glyphs. Section 5 now points at the shipped tracings.

### Version 1.1, 10 November 2026

Adds the backdrop composition measured from a fresh capture (Appendix B): the
portal's glow edge and core, the Sphere, Earth's limb and the navigation arc.
The Interface Atlas is redrawn to it, rests on its finished states instead of
playing the opening on load, keeps its timeline running in hidden pages,
gives its SVG controls a visible keyboard focus ring, starts side tabs 40 u
below the page (`tabMargins 40, 0`) and redraws the Load Game list from the
capture.

### Version 1.0, 10 November 2026

First specification of the Prey interface for openPREY: brand registers and
recognition traits; the front-end palette from `menucolors.guifragment` and
sampled art; the three faces' measured metrics and ramp; the arc of hooks, the
claw-cornered frame, title bars, plates, tabs and controls; the opening, hover,
growth and credits motion; the sound map; screen compositions; the HUD's
silhouette gauges, palette, shear and feedback; the multiplayer HUD and
scoreboard; vehicle and weapon displays; the eight device families, the Sphere
overlay stack and the translation mechanic; openPREY's current additions;
project branding rules; and the Interface Atlas.
