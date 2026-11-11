# Virtual reality (OpenXR)

> [!NOTE]
> Inherited from openQ4 and not yet checked against PREY. This page describes what the engine code does; PREY behavior stays validation-pending until the [rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence for it.

openPREY's engine carries openQ4's OpenXR support for PC VR headsets. It draws
the game in stereo at your headset's resolution, tracks your head, turns a
motion controller's aim into player input, and shows the HUD, menus, loading
screens and video cinematics on floating screens in front of you.

VR mode is **experimental** and **untested with PREY**. Nobody has yet played
PREY's wall-walking, gravity changes, portals or spirit walk in a headset.

OpenXR is built into the SDL3 client on Windows and Linux (Meson option
`openxr`, on by default when it can be built). Dedicated servers never include
it.

## What PREY's game module doesn't do

openQ4 built part of its VR support into its Quake 4 game code. PREY's game
module, built from the PREY SDK, has no VR-specific code, so these parts are
missing in openPREY:

- the gun drawn in your hand and shots leaving it (the `vr_weaponOffset*` and
  `vr_weaponPitch` settings have nothing to move);
- physical crouching: the engine flags a crouched head, but PREY's game
  doesn't read the flag, so use your crouch button;
- vibration on shots and hits, and room-scale collision feedback;
- the comfort changes openQ4 made to view bob, weapon kick and screen shake.

The engine-side parts described below still apply.

## What you need

- A PC VR headset and an **OpenXR runtime that supports OpenGL or Vulkan**,
  set as the system's active OpenXR runtime:
  - **SteamVR** (Valve Index, HTC Vive, Pimax, Bigscreen and many others);
  - the **Meta Quest Link** PC app for Quest headsets over Link or Air Link;
  - **Monado** on Linux.

  Windows Mixed Reality's own runtime does not support OpenGL. On a WMR
  headset, run the game through SteamVR instead.
- Either renderer: **OpenGL** (the default) or **Vulkan** (`r_renderApi
  vulkan`). On Vulkan the runtime picks the GPU your headset is attached to,
  so turning VR on for the first time restarts the renderer once.
- On Linux, either renderer works on an X11 desktop. On a Wayland desktop,
  use Vulkan, or OpenGL with a runtime that can bind it there (Monado can;
  SteamVR cannot, so with SteamVR start openPREY with the environment variable
  `OPENPREY_FORCE_X11=1` to run it through XWayland).

## Turning VR on

1. Start your headset and its OpenXR runtime (for example SteamVR).
2. Enter `vr_enable 1` at the console. VR starts at once. The setting is
   saved, so the next launch starts in VR on its own. You can also launch with
   `+set vr_enable 1`.

PREY's stock menus have no VR settings. openQ4's **Virtual Reality** settings
tab is part of the retained interface (`ui_retained 1`), which hasn't been
checked with PREY; the console settings below cover everything it sets.

When VR is on, the desktop window shows what your left eye sees. To turn VR
off again, enter `vr_enable 0`.

If the headset isn't connected yet, openPREY waits for it and starts VR as soon
as it appears.

In single player, taking the headset off or opening your runtime's own menu
(the SteamVR dashboard, the Meta menu) pauses the game on the pause menu.
Resume from the menu when you're back. Set `vr_pauseOnFocusLoss 0` to keep
the game running instead. Multiplayer can't pause, so there the game carries
on.

If you quit SteamVR, or the runtime closes VR some other way, the game carries
on in its desktop window (paused on the menu in single player). Enter
`vr_restart` to go back into VR; it looks for the runtime and the headset at
once. `vr_enable` stays on, so the next launch starts in VR as usual.

If an XR frame or session fails, the engine clears held VR controls and
returns to desktop rendering. Session failures retry after three seconds; a
stopped or lost runtime waits for `vr_restart`. openQ4 checked this recovery
with a simulated OpenXR runtime; real-headset qualification remains open.

The ordinary `screenshot` command captures a desktop view during VR gameplay.
On OpenGL, for a developer capture of the last rendered eye, use
`screenshot image _vrEyeColor0 "screenshots/vr-left.tga"` or `_vrEyeColor1` for the
right eye. These are engine render-target captures.
Use `screenshot image _vrScreenColor "screenshots/vr-hud.tga"` to capture the
separate HUD surface. The Vulkan renderer keeps its eye targets to itself, so
those image names exist only on OpenGL.

If the desktop window is minimized or hidden behind the headset's own
display, the headset keeps rendering; only the desktop mirror waits for the
window to come back.

## Controls

Controllers act like a gamepad, so your gamepad bindings apply and you can
rebind them like any gamepad button. The weapon hand is the right hand; set
`vr_leftHanded 1` to swap the triggers, grips and sticks.

Menus open on a floating screen in front of you. Point your weapon-hand
controller at the screen: a dot shows where it points, and the trigger clicks
there like a mouse. The sticks also work in menus.

By default you aim with the controller in your weapon hand: its direction
becomes your view angles, the way a mouse's would. Set `vr_aimMode 0` to aim
with your head instead. With `vr_twoHanded 1`, holding your off hand in front
of your weapon hand and squeezing its grip aims from your rear hand through
your front hand.

| Setting | Default | What it does |
| --- | --- | --- |
| `vr_aimMode` | 1 | 1 aim with the weapon-hand controller, 0 aim with your head |
| `vr_aimLaser` | 1 | 0 no marker, 1 laser dot, 2 laser dot and a beam |
| `vr_twoHanded` | 1 | 1 the off-hand grip held in front aims with both hands |
| `vr_leftHanded` | 0 | 1 puts the weapon hand on the left |
| `vr_hapticStrength` | 1 | vibration strength from 0 (off) to 1; PREY's game module sends no vibration |

## Comfort

- Turning is done in steps (snap turn) by default.
- While the stick moves you or turns you smoothly, the edges of your view
  darken around a clear centre (the comfort vignette); walking about your
  room never triggers it.
- Menus, loading screens and video cinematics appear on the floating screen
  instead of moving your view. Nobody has tried PREY's in-game cutscenes in VR.

With `vr_roomScale 1`, the steps you take in your room reach the game as
ordinary movement input, and leaning moves only your head, up to
`vr_headOffsetLimit` from your character.

| Setting | Default | What it does |
| --- | --- | --- |
| `vr_turnMode` | 0 | 0 snap turn, 1 smooth turn |
| `vr_snapTurnAngle` | 45 | degrees per snap turn |
| `vr_smoothTurnSpeed` | 120 | smooth turn speed, degrees per second |
| `vr_moveDirection` | 0 | 0 walk where you look, 1 walk where the off-hand controller points |
| `vr_stickDeadzone` | 0.2 | thumbstick deadzone |
| `vr_comfortVignette` | 0.5 | how strongly the comfort vignette narrows your view, from 0 (off) to 1 (a black edge around a 60 degree clear centre) |
| `vr_roomScale` | 1 | 1 your steps about the room move your character, 0 it stays put |
| `vr_headOffsetLimit` | 16 | how far you can lean from your character before the view stops (game units) |

Use `vr_recenter` to make your current position and direction the front. It
helps to bind it to a key, for example `bind F12 vr_recenter`. Your
headset's own recenter (for example holding the Oculus button) does the same,
at the moment the headset applies it, so the view doesn't jump.

### Seated or standing

`vr_playSpace` decides where your height is measured from:

- **Standing** (`2`) measures your height from the floor your headset knows.
  Recentering while you crouch, sit or lean only turns and moves the front: it
  never moves the floor. The engine learns your standing eye height the first
  time it recenters; to measure it again, stand up straight and enter
  `vr_calibrateHeight`, or set it in metres with `vr_standingHeight`.
- **Seated** (`1`) measures your height from where you recentered: wherever
  your head is then becomes standing height, which suits playing in a chair.
- **Automatic** (`0`), the default, stands when your headset knows where the
  floor is and sits when it doesn't.

If you choose Standing and your runtime knows no floor, the engine says so and
plays seated. `vr_status` shows the play space in use, your standing eye
height and the size of your play area.

| Setting | Default | What it does |
| --- | --- | --- |
| `vr_playSpace` | 0 | 0 automatic, 1 seated, 2 standing |
| `vr_standingHeight` | 0 | standing play: your eye height above the floor in metres; 0 learns it at the next recenter |

## Display

| Setting | Default | What it does |
| --- | --- | --- |
| `vr_renderScale` | 1.0 | multiplies the headset's recommended resolution (0.5-2.0; apply with `vr_restart`) |
| `vr_worldScale` | 39.37 | game units per metre; lower makes the world feel bigger |
| `vr_hudDistance` | 1.4 | HUD distance in metres |
| `vr_hudWidth` | 1.2 | HUD width in metres |
| `vr_hudHeightOffset` | -0.1 | HUD height relative to your eyes, in metres, when you aim with the controller (head aiming centres the HUD so its crosshair lines up) |
| `vr_screenDistance` | 2.5 | menu and cinematic screen distance in metres |
| `vr_screenWidth` | 3.0 | menu and cinematic screen width in metres |
| `vr_mirror` | 1 | desktop window: 0 black, 1 left eye, 2 the floating screen |

The floating screen and the HUD take the shape of the game window, so menus
look the same as on your monitor.

Mirrors and other reflective surfaces show each eye its own reflection.
Screens in the world are drawn once per frame for both eyes, which saves CPU
time without changing what you see; `r_vrStereoGuiShare 0` draws them for
each eye separately.

Temporal anti-aliasing works in VR when you ask for it with `r_temporalAA 1`:
each eye keeps its own history, and a fast head turn starts the history again
instead of smearing. The automatic setting (`r_temporalAA 2`) leaves it off in
VR, because the headset already renders at its own resolution. Dynamic
resolution stays off in VR. MSAA (`r_multiSamples`) and SMAA work as well. See
[Temporal AA and dynamic resolution](temporal-presentation.md).

## Multiplayer

Your aim reaches the server the same way a mouse's does, so a VR player can
join an openPREY server without anything extra on the server. Shots leave from
your view, as they do on the desktop.

## Troubleshooting

Enter `vr_status` in the console to see the runtime, headset, session state,
resolution and refresh rate the engine is using. `vr_debug 1` logs session
events.

- **"no runtime is available"**: no OpenXR runtime is installed or active.
  Set one as active in its own settings, for example in SteamVR under
  Settings > OpenXR.
- **"supports neither OpenGL nor Vulkan"**: the active runtime can't render
  either. Switch to SteamVR or Meta Quest Link.
- **"does not support Vulkan"** or **"does not support OpenGL"**: switch
  `r_renderApi` to the other renderer and restart.
- **"cannot bind it ... native Wayland"**: your runtime can't use OpenGL on a
  Wayland desktop. Use `r_renderApi vulkan`, or start openPREY with
  `OPENPREY_FORCE_X11=1`.
- **"the runtime did not create the Vulkan renderer's device"**: the runtime
  refused to make the Vulkan device for your headset, so VR stays off;
  `vr_restart` tries again.
- **The image looks washed out**: the runtime didn't offer an sRGB image
  format. Report your headset and runtime.
