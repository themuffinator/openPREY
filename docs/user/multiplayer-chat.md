# Multiplayer chat

> [!NOTE]
> Inherited from openQ4 and not yet checked against PREY. This page describes what the engine code does; PREY behavior stays validation-pending until the [rebase status ledger](../dev/prey-rebase/status-ledger.md) records evidence for it.

## Voice chat

Voice chat is off in openPREY. The engine still carries openQ4's microphone
capture and playback (`s_voiceChatCapture`, `s_voiceChatTest` and
`listVoiceChat` exist), but PREY's v7 game API has no voice recipients, so the
client and server drop voice packets instead of passing them to the game
module. The gate is marked `OPENPREY-GATED(D9)` in `src/framework/async/`.
Voice menus from openQ4's interfaces have nothing to send through.

PREY's own canned voice commands (`clientVoiceChat`, which plays a `snd_voc_*`
sound from the multiplayer player definition) are part of the PREY game module
and are separate from microphone voice chat.

## Text chat

Use PREY's chat binds, or type `say <message>` or `sayTeam <message>` at the
console. `clientMessageMode` opens the chat entry; `clientMessageMode 1` opens
it on the team channel.

Bots added with `addbot` chat through the same path as players; `bot_chat 0`
keeps them quiet. See [Multiplayer bots](../dev/mp-bots.md#chat) for their
chat events and replies.

openPREY's engine replaces the chat history and the entry field of PREY's stock
multiplayer GUIs (`guis/mphud.gui` and `guis/mpmsgmode.gui`) with its own chat
panel. Chat keeps the latest 64 received messages and wraps long lines.

| While typing | Action |
| --- | --- |
| Enter | Send to the displayed channel and close |
| Escape | Cancel and close |
| Tab | Switch All/Team in a team game; each channel keeps its own draft |
| Page Up / Page Down | Scroll received history by a page |
| Mouse wheel | Scroll received history by a line |
| Ctrl+Home / Ctrl+End | Oldest / newest received lines |
| Up / Down | Recall sent messages in the current channel; Down past the newest restores your draft |
| Home / End, Ctrl+Left / Ctrl+Right | Move within the input line |

The key used to open chat chooses the channel every time. In a game without
teams, chat opens on All. Changing channels does not send anything. Team
messages keep the game's server-controlled team and spectator restrictions.

When you scroll upward, incoming messages leave your reading position alone.
The same message stays at the top when the panel width or font size changes.
Ctrl+End resumes following new messages. Closing chat returns the passive
display to the newest messages. Received history and the last 32 distinct
consecutive submissions per channel are held in memory and cleared when a new
map initializes or the UI shuts down; they are not written to disk.

These settings shape the chat panel; they apply immediately and are saved
automatically:

| Console setting | Default | Range / meaning |
| --- | --- | --- |
| `ui_chatScale` | `1` | `0.75`–`2`; font and spacing multiplier |
| `ui_chatWidth` | `320` | `200`–`600` in the shared 640×480 GUI canvas |
| `ui_chatLines` | `6` | `2`–`16` visible history lines, limited by available screen space |
| `ui_chatAlpha` | `0.5` | `0`–`1`; background opacity |
| `ui_chatTime` | `3` | `0`–`60` seconds before fading; `0` hides passive chat while retaining history |
| `ui_chatOffsetX` | `0` | Horizontal offset in GUI units; positive moves right |
| `ui_chatOffsetY` | `0` | Vertical offset in GUI units; positive moves down |

Both the passive panel and the input line sit against the left edge of the
whole display, not the left edge of the centred 4:3 HUD canvas, so on a wide
monitor they stay in the corner instead of floating inward. Offsets are
measured from that edge and clamped to keep the panel on screen, so the full
width of the display is reachable. Custom offsets can move the panel over other
HUD elements. The input limit is 128 bytes.

For console binds, `chatHistory up`, `down`, `top` and `bottom` browse an open
panel. `chatHistory status` reports counts and position without printing messages.

## Quick chat

openQ4's quick-chat wheel (`_quickChat`) belongs to its retained interface.
Its HUD document, `guis/hud/quick_chat.rui`, isn't part of openPREY's `basepr`
content, so the wheel doesn't appear in openPREY.
