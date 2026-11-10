# openQ4 Input Key Matrix Audit (2026-04-23)

This checklist audits SDL3 input parity against the legacy Win32 path for:

- console
- GUI edit fields
- chat
- binds
- numpad
- modifiers

For player-facing setup instructions, see [../user/input-settings.md](../user/input-settings.md). This file is a developer audit, not the everyday controls guide.

## Method

- Reviewed shared SDL3 event generation in `src/sys/sdl3/sdl3_backend.cpp`, as reached through the Windows, Linux, and macOS wrapper entries.
- Reviewed native Linux X11 input in `src/sys/linux/input.cpp`.
- Reviewed native macOS Cocoa input in `src/sys/macos/macos_event.mm`.
- Reviewed shared POSIX poll buffering in `src/sys/posix/posix_input.cpp`.
- Compared behavior to legacy `WM_KEY*` + `WM_CHAR`/DirectInput paths in:
  - `src/sys/win32/win_wndproc.cpp`
  - `src/sys/win32/win_input.cpp`
- Reviewed consumer paths:
  - `src/framework/Console.cpp`
  - `src/framework/EditField.cpp`
  - `src/ui/EditWindow.cpp`
  - `src/ui/Window.cpp`
  - `src/framework/Session.cpp`

## Checklist

| Area | Coverage | Result | Notes |
|---|---|---|---|
| Console input | Toggle key, enter/submit, tab-complete, history, paging, backspace, ctrl shortcuts | Pass | `SE_KEY` + `SE_CHAR` paths align for core behavior, and `Sys_GetConsoleKey` now follows the active SDL3 layout for the grave/console scancode. |
| GUI edit fields | Backspace/delete, cursor movement, enter handling, ctrl-h/ctrl-a/ctrl-e style chars | Pass | Backspace regression fixed via control-char synthesis on keydown. |
| Chat input | Text entry/editing in GUI-driven chat fields | Pass (stock single-byte/control) | SDL text input is decoded as complete codepoints before the stock Quake 4 bitmap-font range is enforced; unsupported commits are ignored instead of corruptly narrowed, and control chars remain restored on keydown. |
| Binds | Key-down bind execution in session loop (including function keys and mouse/wheel) | Pass | Printable `SE_KEY` values come from SDL3's current-layout keycode translation for ASCII plus the reserved Latin-1 keynums (`K_TILDE_N`, `K_SUPERSCRIPT_TWO`, ...); all other layout-specific keycodes fall back to physical-scancode (US-position) mapping so they can never collide with the special-key space at 127-253 (previously German `ü` mapped onto `K_PRINT_SCR`). |
| Mouse buttons | `MOUSE1` through `MOUSE8`, wheel up/down, console/menu routing | Pass | SDL3 maps extended buttons 6-8 onto the engine's existing `K_MOUSE6..K_MOUSE8` range, and console routing treats all eight mouse keys as mouse input. |
| Mouse motion | Captured relative motion, menu/console absolute routing, high-DPI/fractional deltas | Pass | SDL3 relative motion is requested unscaled, fractional Linux deltas are accumulated before integer engine events, and menu/console coordinates continue through the existing GUI-space transform. |
| Poll contracts | Queue ranges, failed-return outputs, zero/no-op deltas | Pass | SDL3, POSIX/native fallback, dedicated stubs, and legacy Win32 reject invalid key/mouse actions, skip zero movement/wheel deltas, and zero output parameters when no event is returned. Usercmd generation also ignores impossible key IDs. |
| Controllers | SDL3 gamepads, generic joysticks, triggers, D-pad/hat, hotplug, rumble | Pass (SDL3) | Windows/Linux/macOS SDL3 use the stable `JOY1..JOY32` semantic mapping for gamepads, expose fallback joystick buttons through `AUX` keys, poll shaped axes, add trigger-button hysteresis, and release button/axis state on disconnect. Generic raw joysticks keep sane auto axes (`0/1` move, `2/3` look, `4/5` vertical/throttle) with console cvars for devices whose SDL axis order differs. macOS support is a preview, and controller runtime validation on real hardware remains part of device signoff. |
| Native Linux input | X11 keyboard, text chars, mouse buttons/wheel/motion | Pass (fallback) | Unknown keycodes no longer enter the poll buffer, X11 buttons 8-10 map to `MOUSE6..MOUSE8`, and the POSIX polling layer ignores invalid key `0` defensively. |
| Experimental native macOS input | Cocoa keyboard/text/modifiers, mouse buttons/wheel/motion | Pass (keyboard/mouse) | Unknown virtual keys no longer become literal `?` binds, Return/Tab/Backspace/Ctrl-letter chars are synthesized for edit fields, Command/Caps modifier changes are tracked, mouse buttons reach `MOUSE8`, and fractional scroll wheel deltas accumulate before wheel events. |
| Numpad | KP enter/arrows/home/end/ins/del, KP operators, KP equals | Pass (core) | SDL3 mapping includes KP key families used by id key enums. |
| Modifiers | Ctrl/Shift/Alt/RightAlt behavior | Pass (core) | RightAlt locale behavior now matches legacy intent for english vs selected non-english languages. |

## Remaining Parity Gaps

1. Legacy keynums still cap bindable printable keys to the engine's 8-bit key range.
   - SDL3 layout-aware translation restores the intended non-English bind semantics for printable ASCII and the Latin-1 characters with dedicated keynum slots (`¡ ² ´ º à ç è ì ñ ò ù`), including console-toggle lookup.
   - Other layout-specific keycodes (e.g. German umlauts, non-Latin layouts) bind through their physical US-position scancode fallback; making them bindable by character needs a broader input-system expansion beyond the legacy `< 256` keynum space.
2. macOS SDL3 source selection reaches the shared controller backend and CI covers compile/link/package validation, but real-device runtime validation is still needed for keyboard layouts, trackpads, controllers, and rumble.

## Recommended Next Steps

1. Validate the SDL3 layout-aware path against real AZERTY/QWERTZ/Spanish/Italian keyboards during runtime bring-up and record any layout-specific regressions in this matrix.
2. Validate Linux X11/XWayland/Wayland mouse capture with at least one high-DPI mouse and one device exposing buttons beyond `MOUSE5`.
3. Continue macOS SDL3 keyboard/edit-field, controller hotplug/rumble, multi-button mouse, and trackpad scrolling signoff on hardware; then repeat the native Cocoa fallback keyboard/mouse smoke pass when that comparison path changes.
4. Decide whether future non-Latin-1 keyboard support should extend the legacy keynum/bind system beyond the current 8-bit printable-key range.
