# Input Settings and Controls Guide

> [!NOTE]
> Inherited from openQ4 and not yet checked against PREY. This page describes what the engine code does; PREY behavior stays validation-pending until the [rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence for it.

This guide covers keyboard, mouse and controller input in openPREY: the stock PREY menus, console commands, config files and common troubleshooting.

## Quick Start

- To rebind actions, open **Options -> Controls** in the stock PREY menu.
- To tune the mouse, open **Options -> Game Options**. Controller settings are console cvars (see [Controller Settings](#controller-settings)).
- Press `` ` `` or `~` to open the console (`con_allowConsole 1`, the default).
- Run `listBinds` to see your current bindings.
- Run `listControllers` to print SDL gamepad, joystick, gyro, touchpad, battery and Steam Deck routing diagnostics.
- Run `writeConfig my-input-backup.cfg` to save a manual backup before large binding changes.

## Where Things Are

The stock **Options -> Controls** menu has these tabs:

| Tab | Actions |
|---|---|
| Movement | Forward, back, move left/right, jump, crouch, strafe. |
| Combat | Attack, alternate attack, previous/next weapon, lighter, spirit walk, throw grenade. |
| Weapons | Direct weapon slots 1 to 7. |
| Look | Turn left/right, look up/down, mouse look, centre view, zoom. |
| Other | Quick save, quick load, screenshot, help. |
| Multiplayer | Chat, team chat, toggle team, spectate, ready, vote yes/no, scoreboard. |
| Profiles | Saved control profiles. |

To rebind an action, select its row and press the key, mouse button or controller button you want. Analog sticks are configured through the controller cvars instead of being rebound as buttons.

The retained interface (`ui_retained 1`) has openQ4's own Settings pages, including controller tuning, prompt styles and menu-navigation options. It's inherited and hasn't been checked with PREY.

## Where openPREY Stores Input Settings

At startup, openPREY loads config in this order:

1. `default.cfg` from your PREY installation's `base` folder
2. `openprey_defaults.cfg` (if present; openPREY doesn't ship one yet)
3. `openprey_profile_<profile>.cfg` when a platform profile is active; openPREY ships `openprey_profile_steamdeck.cfg`
4. `openPREYConfig.cfg`
5. `autoexec.cfg` (if present)

What this means in practice:

- Default binds come from PREY's own `default.cfg`.
- openPREY-specific overrides can be layered on top through `openprey_defaults.cfg`.
- Platform-specific overrides are applied through `com_platformProfile`.
- Your saved personal changes live in `openPREYConfig.cfg`, written under the writable save/config area (`fs_savepath`, which defaults to `fs_homepath`).
- You can place your own final overrides in `autoexec.cfg`.

## Mouse Settings

The stock **Options -> Game Options** menu sets free look, toggle zoom, inverted mouse (`m_pitch`), mouse smoothing and sensitivity. The rest are console cvars.

| Setting | Backing cvar | Default | What it changes |
|---|---|---:|---|
| Free Look | `in_freeLook` | `1` | Lets the mouse control view direction. |
| Toggle Zoom | `in_toggleZoom` | `0` | Makes zoom a toggle instead of hold-to-zoom. |
| Invert Mouse | `m_pitch` | `0.022` | A negative value flips vertical mouse look. |
| Mouse Smooth | `m_smooth` | `1` | Higher values (up to `8`) smooth motion but feel less direct. |
| Mouse Sensitivity | `sensitivity` | `5` | Main mouse look speed. With `m_cpi` set, this is degrees per centimetre. |
| Mouse CPI | `m_cpi` | `0` | Set this to your mouse CPI/DPI for physical sensitivity. `0` keeps classic raw-count behavior. |
| View Filter | `m_filter` | `0` | Optional Quake Live-style view-angle history filtering. Leave it off for the most direct input. |
| Mouse Accel | `cl_mouseAccel` | `0` | Quake Live-style acceleration. Positive values add sensitivity as movement rate rises; negative values subtract it. |
| Accel Offset | `cl_mouseAccelOffset` | `0` | Movement-rate threshold before acceleration starts. |
| Accel Curve | `cl_mouseAccelPower` | `2` | Acceleration curve shape. `2` matches Quake Live's default power. |
| Sensitivity Cap | `cl_mouseSensCap` | `0` | Caps accelerated sensitivity when set above `0`. |
| Console Access | `con_allowConsole` | `1` | `1` lets tilde open the console; `0` requires Ctrl+Alt+Tilde. |

`m_maxMouseDelta 0` (the default) keeps the high-DPI path unclamped. Set a positive value only if a faulty mouse or driver creates large camera jumps. `cl_mouseAccelDebug 1` writes acceleration samples to `logs/mouse.log` under the active save path.

For CPI-normalized tuning, set `m_cpi` to the mouse hardware value and use `360 / sensitivity` as an approximate centimetres-per-360 target.

SDL3 builds use relative mouse capture during gameplay on Windows and Linux. On Linux, openPREY requests unscaled relative deltas from SDL where the desktop stack supports them and preserves fractional movement before it reaches the engine's event queue. `Mouse1` through `Mouse8` are bindable by name on SDL3 and the native X11 fallback, and the wheel is `MWHEELUP` and `MWHEELDOWN`.

## Controller Settings

Controller input works in SDL3 builds on Windows and Linux. The native Linux and legacy Win32 input fallbacks are keyboard and mouse only. The stock PREY menu has no controller page, so set these from the console or a config file.

| Cvar | Default | What it changes |
|---|---:|---|
| `in_joystick` | `1` | Enables SDL3 gamepad/joystick input and hotplug support. |
| `in_joystickSouthpaw` | `0` | `1` swaps the movement and look sticks. |
| `in_joystickDeadZone` | `0.18` | The centre area ignored by analog sticks. |
| `in_joystickLookSensitivity` | `0.75` | Scales controller turn speed after stick deflection is normalized. |
| `in_joystickLookCurve` | `1.35` | Higher values damp small aim movements; full-stick turn speed is set by look sensitivity. |
| `in_joystickMoveCurve` | `1.0` | `1.0` is linear movement. Higher values make walking easier near the centre but need more stick travel for full speed. |
| `in_joystickInvertLook` | `0` | Flips vertical controller look. |
| `in_joystickTriggerThreshold` | `0.35` | How far LT/RT must be pressed before they count as buttons. |
| `in_joystickRumble` | `1` | Enables rumble when the device supports it. |
| `in_joystickRumbleScale` | `1.0` | Scales rumble intensity from `0.0` to `2.0`. |
| `in_joystickLowBatteryRumbleThreshold` | `0` (`20` in the Steam Deck profile) | Caps rumble when SDL reports a controller battery at or below this percentage; `0` disables the cap. |
| `in_joystickLowBatteryRumbleScale` | `0.75` | Maximum rumble scale below the low-battery threshold. This doesn't rewrite `in_joystickRumbleScale`. |

Suggested adjustments:

- If the view or movement drifts, raise `in_joystickDeadZone` a little.
- If aiming feels sluggish, raise `in_joystickLookSensitivity`.
- If small aim corrections are too twitchy, raise `in_joystickLookCurve` or `in_joystickDeadZone`.
- If you can't reach full turn speed comfortably, lower `in_joystickLookCurve` toward `1.0`.
- If triggers fire too easily, raise `in_joystickTriggerThreshold`; if they feel unresponsive, lower it.

SDL gamepads use SDL's standard controller database, so Xbox, PlayStation, Steam Input and similar pads shouldn't need axis remapping. Linux SDL3 builds opt into SDL's HIDAPI controller backends by default, so PlayStation, Switch, Steam, Steam Deck and Xbox-class controllers can expose their buttons, sticks, triggers, rumble, battery, gyro and touchpad. Run `listControllers` to see which SDL driver, hint state and capabilities are active for a connected device.

### Generic joysticks

Generic SDL joysticks use raw axes. These cvars default to `-1` (automatic), which picks the axes shown:

| Cvar | Automatic choice | What it changes |
|---|---:|---|
| `in_joystickUseDedicatedLookAxes` | `-1` | `-1` uses look axes only when a paired look stick is available, `0` keeps classic single-stick behavior, and `1` forces dedicated look axes when any mapped look axis exists. |
| `in_joystickMoveAxisX` / `in_joystickMoveAxisY` | `0` / `1` | Raw joystick axes used for movement or classic stick look. |
| `in_joystickLookAxisX` / `in_joystickLookAxisY` | `2` / `3` | Raw joystick axes used for dedicated look on four-axis devices. |
| `in_joystickUpAxis` / `in_joystickUpAxisNegative` | `4` / `5` | Optional vertical/throttle axes; when both exist, openPREY uses positive minus negative. |

Set an axis cvar to `-1` for automatic, or to a raw SDL axis number from `0` to `31`. These only affect generic SDL joysticks; SDL gamepads keep the fixed `JOY` button layout below.

### Gyro, touchpad and touchscreen

| Cvar | Default | What it changes |
|---|---:|---|
| `in_gyro` | `0` (`1` in the Steam Deck profile) | Uses an SDL gamepad gyro as mouse-look input during gameplay when the device has one. |
| `in_gyroSensitivity` | `1.0` (`0.20` in the Steam Deck profile) | Scales gyro mouse-look motion. It still flows through normal mouse sensitivity. |
| `in_gyroDeadZone` | `0.015` | Ignores tiny gyro rates, in radians per second. |
| `in_gyroYawAxis` / `in_gyroPitchAxis` | `2` / `0` | Which SDL gyro data indices drive yaw and pitch. |
| `in_gyroInvertYaw` / `in_gyroInvertPitch` | `0` / `0` | Flips gyro yaw or pitch if the device orientation feels backwards. |
| `in_touchpadMode` | `0` (`1` in the Steam Deck profile) | `0` disables motion, `1` moves the menu/console cursor, `2` sends mouse-look deltas during gameplay, and `3` keeps touchpad motion off while preserving touchpad button binds. |
| `in_touchpadSensitivity` | `1.0` | Scales gamepad touchpad motion. |
| `in_touchscreen` | `1` | Routes SDL touchscreen taps and drags to menu, console and loading-continue input. |

## Controller Buttons

SDL gamepads use fixed `JOY` button names, so binds work across Xbox, PlayStation and Steam Input layouts. PREY's `default.cfg` predates controller support, and openPREY doesn't add controller binds yet, so bind the buttons you want from **Options -> Controls** or the console.

| Button | Name |
|---|---|
| LB / L1 | `JOY1` |
| RB / R1 | `JOY2` |
| A / Cross (bottom) | `JOY3` |
| B / Circle (right) | `JOY4` |
| Y / Triangle (top) | `JOY5` |
| X / Square (left) | `JOY6` |
| Start / Options / Menu | `JOY7` |
| Back / Select / View | `JOY8` |
| D-pad up / down / right / left | `JOY9` / `JOY10` / `JOY11` / `JOY12` |
| Left / right stick click | `JOY13` / `JOY14` |
| RT / R2 | `JOY15` |
| LT / L2 | `JOY16` |
| Guide, when the OS delivers it | `JOY17` |
| Touchpad button | `JOY18` |
| Right paddle 1 / left paddle 1 | `JOY19` / `JOY20` |
| Right paddle 2 / left paddle 2 | `JOY21` / `JOY22` |
| Extra buttons | `JOY23` to `JOY28` |

`JOY29` to `JOY32` and generic `AUX1` to `AUX16` are bindable for other device buttons. [VR](vr.md) motion controllers press these same `JOY` buttons.

## Useful Console Commands

| Command | What it does |
|---|---|
| `bind <key> "<command>"` | Assigns a command to a key or button. |
| `unbind <key>` | Removes a bind from one key or button. |
| `unbindall` | Clears all binds. Use with care. |
| `listBinds` | Prints the current binds. |
| `listControllers` | Prints SDL controller diagnostics: the active gamepad/joystick, touchpad and gyro capability, touchscreen routing and low-battery rumble state. |
| `writeConfig <filename>` | Writes a config snapshot to a `.cfg` file. |

Examples:

```cfg
bind JOY15 "_attack"
bind JOY3 "_moveUp"
bind JOY4 "_moveDown"
bind mouse2 "_zoom"
listBinds
writeConfig my-input-backup.cfg
```

Most input cvars are archived, so changes made through the menu or with `seta` persist after exit.

## Using the Console

The console takes the keyboard and the mouse while it's open.

| Key | What it does |
|---|---|
| `` ` `` or `~` | Opens and closes the console. Hold `Shift` to open it at a reduced height. |
| `Esc` | Closes the completion list if one is showing, otherwise the console. |
| `Enter` | Runs the line. If the highlighted completion would change the line, takes it first. |
| `Tab`, `Shift+Tab` | Completes the word at the caret and steps through the matches. |
| `Up`, `Down` | Steps through the commands you ran before; `Down` returns to the line you were typing. While the completion list shows, they move through the list. |
| `Page Up`, `Page Down`, mouse wheel | Scrolls the log by `con_scrollLines` lines. While the completion list shows, the page keys move through it a page at a time. |
| `Ctrl+Home`, `Ctrl+End` | Jumps to the oldest and the newest line of the log. |
| `Home`, `End`, `Left`, `Right` | Moves the caret; with `Ctrl`, `Left` and `Right` move a word. Add `Shift` to select. |
| `Ctrl+A`, `Ctrl+C`, `Ctrl+X`, `Ctrl+V` | Select all, copy, cut and paste. `Shift+Insert` also pastes; `Insert` switches between inserting and overwriting. |
| `Ctrl+L` | Clears the log. |

With the mouse you can click in the edit line to place the caret and drag to select, drag across the log to select and copy text with `Ctrl+C` (`Shift`+click extends the selection), drag the scrollbar, and click a completion to take it. A click below the console closes it.

| Setting | What it does |
|---|---|
| `con_height` | How far down the screen the console opens, `0.1` to `1` (default `0.5`). |
| `con_scrollLines` | Lines scrolled per wheel notch or page key (default `6`). |
| `con_scrollSmooth` | `1` animates scrolling, `0` jumps. |
| `con_completionPopup` | `1` shows the completion list while you type, `0` leaves completion to `Tab`. |

## Example Tweaks

### CPI-Normalized Mouse With Acceleration Disabled

```cfg
seta sensitivity 3.5
seta m_smooth 1
seta m_cpi 0
seta m_filter 0
seta cl_mouseAccel 0
seta cl_mouseAccelOffset 0
seta cl_mouseAccelPower 2
seta cl_mouseSensCap 0
```

### Invert Mouse

```cfg
seta m_pitch -0.022
```

### Toggle Crouch and Toggle Zoom

```cfg
seta in_toggleCrouch 1
seta in_toggleZoom 1
```

### Controller Tuning With a Larger Dead Zone and Weaker Rumble

```cfg
seta in_joystick 1
seta in_joystickDeadZone 0.24
seta in_joystickLookSensitivity 0.75
seta in_joystickLookCurve 1.35
seta in_joystickTriggerThreshold 0.40
seta in_joystickRumbleScale 0.50
```

### Steam Deck Profile Selection

```cfg
seta com_platformProfile steamdeck
```

On a Steam Deck or SteamOS, direct `openPREY-client_x64` launches auto-select this profile while `com_platformProfile` is still `default`. Set `OPENPREY_NO_STEAMDECK_AUTODETECT=1` to keep direct launches on the default profile.

## Troubleshooting

| Problem | Try this |
|---|---|
| Console doesn't open | Check `con_allowConsole 1`, or open it with Ctrl+Alt+Tilde. |
| Controller isn't detected | Make sure `in_joystick` is `1`, reconnect the device, run `listControllers`, and check whether Steam Input is remapping it. |
| Controller buttons do nothing | Controller buttons have no default binds; bind them in **Options -> Controls** or with `bind`. |
| Movement or aim drifts | Raise `in_joystickDeadZone` until the drift stops. |
| Aim feels too fast | Lower `in_joystickLookSensitivity`; if tiny stick movements are the problem, raise `in_joystickLookCurve`. |
| Triggers activate by accident | Raise `in_joystickTriggerThreshold`. |
| Rumble doesn't work | Set `in_joystickRumble 1` and `in_joystickRumbleScale` above `0`, confirm the device supports haptics, and reset `s_controllerRumble` to `1` if it was changed. |
| Rumble gets weaker at low battery | Raise `in_joystickLowBatteryRumbleScale`, lower `in_joystickLowBatteryRumbleThreshold`, or set the threshold to `0`. |
| Steam Deck gyro doesn't work | Confirm `in_gyro 1`, run `listControllers`, and make sure Steam Input isn't hiding the gyro from the game. |
| Steam Deck touchpad moves aim instead of menus | Set `in_touchpadMode 1`; use `2` only when you want touchpad mouse-look during gameplay. |
| Mouse look is backwards vertically | Flip the sign of `m_pitch`, or set `in_joystickInvertLook` for a controller. |
| A binding change didn't stick | Quit normally so `openPREYConfig.cfg` is rewritten, or put the `bind` in `autoexec.cfg`. |

For Steam Deck launcher details, see the [Steam Deck guide](steam-deck.md).
