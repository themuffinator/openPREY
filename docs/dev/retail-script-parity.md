# Retail map-script parity

Audit of 10 November 2026. It covers whether retail Prey (2006) scripts run in
openPREY as they do in the retail 32-bit `gamex86.dll`. That means the 60 files
under `script/` in `pak_data.pk4`, compiled as one program through
`script/prey_main.script`, plus the `call`/`callRef` keys in map entities.

## What was verified

| Layer | Method | Result |
| --- | --- | --- |
| Compile | The compiler rejects unknown events and signature mismatches (`idCompiler::ParseEventDef`) | All 786 `scriptEvent` declarations and every retail script compile |
| Event surface | `listEventCallbacks` output compared with the event definitions and class event tables extracted from retail `gamex86.dll` | All 1,028 retail events match by name, argument format and return type. All 259 retail per-class event tables match entry for entry |
| Callback ABI | `EVENT()` records each C++ callback's parameter register classes, and `idClass::Init` warns on any disagreement with the event's format | 0 mismatches after the fixes below |
| VM semantics | `tools/tests/script_vm_conformance.py` (65 checks) | All pass on Win64 |
| Runtime | `prey_map_load_condump_audit.py --settle-ms 25000` over all 37 maps | No script compile/runtime errors, unsupported-event warnings or stack overflows |

The only event-surface differences are openPREY additions that scripts cannot
call: `<openprey_script_silence_done>` on `idEntity`, the `<eventDispatchSmoke>`
test class, and `'d'` return types on the internal `<script_setcallback>` and
`<script_setsilencecallback>` events.

### Why the callback check exists

Event callbacks are stored type-erased and invoked through the generated
`src/game/gamesys/Callbacks.cpp` table, which chooses the call signature from
the event's format string. On 32-bit x86 every argument went on the stack, so a
callback whose C++ parameters disagreed with the format still received the right
bits. Win64 passes floats in XMM registers and everything else in integer
registers, so the same mismatch reads an unrelated register. A callback may
ignore trailing arguments; that is safe on both ABIs.

### Stack size

`LOCALSTACK_SIZE` is 12,288 bytes, twice retail's 6,144. Every 64-bit script slot
is at most twice its 32-bit size (float, boolean and entity grow from 4 to 8
bytes; vector from 12 to 16; string stays 128), so any call chain that fit
retail's stack fits this one. `MAX_STACK_DEPTH` (64 calls) is unchanged.

## Fixed in this audit

- **Callback signature mismatches** (none is called by a retail script):
  - `hhWeapon::Event_AddToAltClip` took `int` for an `'f'` event.
  - `idAnimated::Event_LaunchMissiles` took `int framedelay` for an `'f'` argument.
  - `attackMissile` (`'s'`) was bound directly to the three-parameter virtual
    `idAI::Event_AttackMissile`, so `projDef` and `boneDir` came from stale
    registers. It now goes through `idAI::Event_ScriptAttackMissile`, which
    passes `NULL, 0` and keeps virtual dispatch to the `hhMonsterAI` and
    `hhCreatureX` overrides.
- **`old_bind`**: retail never reads this key; the string appears nowhere in
  retail `gamex86.dll` or either executable. In `feedingtowera` the designers
  renamed `bind` to `old_bind` on 61 entities (34 lights, 26 `func_static`s and
  a speaker, all bound to `ftaDropShip1`) to keep them unbound. Honouring the key
  made them leave with the ship in `DropShip1Takeoff()` and disappear with it in
  `DropShipsRemove()`. `idEntity::Spawn`/`Event_SpawnBind` read only `bind` again.
- **`waitForSilence`**: retail waits only on entities that respond to
  `<script_setsilencecallback>`, which is `hhAnimatedEntity` and its subclasses.
  That includes the player, every actor (`idAFEntity_Base` derives from
  `hhAnimatedEntity`) and AF attachments such as heads. Any other entity returns
  immediately. Voice tracking stays on `idEntity`, and `Event_WaitForSilence`
  restores the retail `RespondsTo` gate. Every retail call targets an animated
  entity, so retail content behaves the same. Without the gate, a wait on an
  entity that can never speak never returns.

## Retail quirks kept deliberately

These come from the SDK compiler and VM and behave identically on 32-bit
retail. Changing them would change what retail scripts observe.

- A `boolean` function returning a float expression (`return a > 1;`) yields
  1316880384 instead of 1. `ParseReturnStatement` searches the `=` opcode table
  with source and destination swapped and emits `STORE_BOOLTOF`. Truthiness is
  preserved for every non-zero float, and retail scripts only test such results
  for truth. The conformance test pins the retail value.
- `idCompiler::CheckToken` compares token text without checking the token type,
  so the string literal `"thread"` is parsed as the `thread` keyword.
- Non-integral floats concatenated to strings use `%f` (`"x" + 1.5` gives
  `x1.500000`). Vectors drop trailing zeros (`1 2 3`).
- Call-by-string float arguments (`idTypeDefFloat::PushOntoStack`) use the
  invalid `sscanf` format `%.2f` and always push 0. No retail map passes
  arguments in `call` keys; all 537 call keys name zero-argument functions, and
  `callRef` passes only an entity name.

## Known openPREY divergences outside the script VM

The behavior-change audit since the SDK import (`git diff 2a8b64822`) found
earlier openPREY fixes that change what retail scripts observe. They are
recorded here, not reverted, because each was made on purpose:

| Area | Change | Retail scripts affected |
| --- | --- | --- |
| `idEntity::Event_PlayerCanSee` (`EntityAdditions.cpp`) | Also accepts hits on the AF body or bind master, actor eye and bounds-centre tests, and an AF attachment's owner | Conversation and boss gates in roadhouse, biolabs, feedingtowerb, girlfriendx, epilogue, lota, deathwalk, salvageboss, feedingtowera |
| Player trigger touches (`idEntity::TouchTriggers`, `hhTrigger`) | Touches are swept from the previous origin; swept touches skip the `IsEncroaching` cancel | Any player-touched trigger crossed within one frame |
| `idPhysics_RigidBody` | Bound rigid bodies push when their master is non-solid or small | Moveables bound to non-solid movers |
| `idEntity::UpdatePVSAreas` | Bounds over 10,000 units use a ±256 box at the origin | `playerCanSee`, `waitPVS` and dormancy for huge models |
| `hhPlayer::Weapon_Combat` | Fire within 80 units clicks GUIs and talks to `talks 1` AI | GUIs 70–80 units away |
| Joint binds, `ConvertLocalToWorldTransform` | Use the current physics transform instead of last-presented or `UpdateModelTransform` side effects | Joint-bound entities, healer droid and tracking projectile spin |
| `hhRenderEntity` combat models | Relinked every present; not reloaded on `Event_ModelDefHandleIsValid` | `useCombatModel` entities bound to movers or given a new model by script |
| `idEntity::StartSound` | Plays a sound shader name when the `snd_` key is missing | Only entities missing the key |
| Cinematic skip | Continues through `hhPlayer::InCinematic()` sections | Skipping roadhouse and feedingtowera cinematics |
| `idActor` SP player model | Walk animations stand in for missing `run_*` | `ai_player.script` run cycles |

## Running the checks

```bash
python tools/tests/script_vm_conformance.py
```

The runner stages `content/basepr/dev/script/openprey_vm_conformance.script` as
the loose `maps/game/roadhouse.script` inside an isolated `fs_savepath` under
`.tmp/script-vm-conformance/`. `WorldSpawn` compiles that fixture on top of the
full retail program. The engine runs windowed. `--fs-game` selects a mod
directory next to the executable when `.install/basepr` is in use. The fixture
is development-only, and the packaging guards keep it out of PK4s.

For the event surface, run `listEventCallbacks` in the console. It prints one
tab-separated `eventDef` line per event and one `eventCallback` line per class
binding (with the callback's parameter classes). Diff that output against the
same data extracted from a retail binary. Signature warnings appear in the log
at game start, after `Initializing class hierarchy`.
