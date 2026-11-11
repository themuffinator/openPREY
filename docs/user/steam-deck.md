# Steam Deck

> [!NOTE]
> Inherited from openQ4 and not yet checked against PREY. This page describes what the engine code does; PREY behavior stays validation-pending until the [rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence for it.

Linux builds of openPREY stage an `openPREY-steamdeck` launcher beside the client in `.install/`, with a matching `share/applications/openprey-steamdeck.desktop` entry. PREY (2006) isn't sold on Steam, so you add openPREY to Steam yourself as a non-Steam game and point it at your own copy of PREY.

## Launching

- Use `openPREY-steamdeck` instead of `openPREY-client_x64`.
- The launcher exports `OPENPREY_STEAMDECK=1`, starts the client with `+set com_platformProfile steamdeck +set r_fullscreen 0`, and passes on any extra command-line arguments.
- SDL3 picks native Wayland or X11 (XWayland) itself. Launch with `OPENPREY_FORCE_X11=1` to force XWayland; the launcher and direct client launches both honor it.
- If native Wayland hits a libdecor startup or window-decoration problem on a specific compositor, launch with `OPENPREY_WAYLAND_DISABLE_LIBDECOR=1`.
- If you launch `openPREY-client_x64` directly on a Steam Deck or SteamOS host, openPREY selects the `steamdeck` profile while `com_platformProfile` is still `default`. Set `OPENPREY_NO_STEAMDECK_AUTODETECT=1` or `OPENPREY_DISABLE_STEAMDECK_AUTODETECT=1` to turn that off.

## What the Profile Sets

The `steamdeck` profile runs `openprey_profile_steamdeck.cfg` from openPREY's `pak0` on top of the normal defaults. It sets:

- `in_joystick 1`, so the Deck's controls work as an SDL gamepad;
- `in_gyro 1` with `in_gyroSensitivity 0.20` and `in_gyroDeadZone 0.015`, for gyro aiming;
- `in_touchpadMode 1`, so the trackpads move the menu and console cursor, and `in_touchscreen 1`;
- `com_steamDeckAutoFrameCap 1` and `com_steamDeckFrameCap 0` (see [Performance](#performance));
- `in_joystickLowBatteryRumbleThreshold 20` and `in_joystickLowBatteryRumbleScale 0.75`, which cap rumble while the controller battery is at or below 20 percent without changing your rumble strength.

Auto-Detect also places the Steam Deck profile on the Performance preset; see [Display Settings](display-settings.md#auto-detect).

## Controls

The profile doesn't bind any buttons, and PREY's own `default.cfg` predates controller support, so bind the Deck's buttons in **Options -> Controls** or from the console. [Input Settings](input-settings.md#controller-buttons) lists the `JOY` name of every button, including the rear paddles (`JOY19` to `JOY22`).

In gameplay, Start (`JOY7`) or View (`JOY8`) opens the menu.

Tuning and haptics:

- Rumble follows the game's sound-driven shake data. Use `in_joystickRumble 0` to turn the motors off, or tune strength with `in_joystickRumbleScale`.
- Raise or lower `in_gyroSensitivity` if gyro aim feels slow or fast.
- `in_touchpadMode 2` uses the trackpads for mouse-look, `0` disables trackpad motion, and `3` keeps motion off while keeping trackpad button binds.
- `in_touchscreen 1` routes touchscreen taps and drags to menus, the console and loading-continue input when SDL delivers native touch events.
- For every controller cvar, see the [Input Settings guide](input-settings.md#controller-settings).

## Steam Input and Diagnostics

Use a Steam Input layout that presents the Deck as a gamepad with its gyro and trackpads available to SDL. Steam-level gyro-to-mouse or trackpad-to-mouse mappings work, but they hide those inputs from openPREY's own `in_gyro` and `in_touchpadMode` handling.

Run `listControllers` from the console when diagnosing Deck input. It prints the active SDL gamepad/joystick, GUID, type, path, power state, touchpad count, sensor capability, gyro/touchpad cvars, touchscreen routing and low-battery rumble state. Save the log output with bug reports.

## Performance

- While the Steam Deck profile is active, `com_steamDeckAutoFrameCap 1` applies a Deck-friendly `com_maxfps` only if `com_maxfps` is still the global default of `240`.
- The automatic cap uses SDL's current display refresh, clamped to `40..90`. LCD Deck sessions normally land on `60`; higher-refresh sessions can land higher.
- Set `com_maxfps` yourself to keep a specific cap. Set `com_steamDeckAutoFrameCap 0` to disable the automatic default, or set `com_steamDeckFrameCap` to a nonzero value to choose the Deck cap explicitly.

### Shadow Maps on Deck

openQ4 recommended these settings for shadow maps on Deck-class hardware. They haven't been measured with PREY:

```cfg
seta r_shadows 1
seta r_useShadowMap 1
seta r_shadowMapSize 1024
seta r_shadowMapPointSize 512
seta r_shadowMapCSM 1
seta r_shadowMapCascadeCount 3
seta r_shadowMapMaxUpdatesPerView 2
vid_restart
```

With an update budget set, the renderer spends each frame's shadow renders on the most important stale lights and serves the rest from its cache, so shadow cost stays bounded in dense scenes. See the [Shadow Mapping guide](shadow-mapping.md) for the full reference.

## Finding Your PREY Files

Copy your PREY (2006) installation onto the Deck, then tell openPREY where it is:

- Set `OPENPREY_PREY_PATH` (or `OPENPREY_PREY_ROOT`) to the PREY folder that contains `base`, or
- launch with `+set fs_basepath "/path/to/Prey"`, pointing at the folder that contains `base`, not at `base` itself.

On Linux, multiple paths in these variables can be separated with `:` or `;`. openPREY also keeps openQ4's scan of Steam library folders for a `steamapps/common/Prey` folder, which only helps if you placed your copy there yourself. See [Getting Started](getting-started.md#if-auto-detection-fails) for more.

## Notes

- Suspend/resume and foreground/background SDL events release captured input, stop rumble, write the current config, and reacquire controllers when the app returns.
- The developer Deck QA checklist is in [steam-deck-qa.md](../dev/steam-deck-qa.md).
