# Presentation clock ownership

Stage-one contract, 18 October 2026. Owners: HF-01/HF-02 in the
[roadmap](roadmap.md). This contract does not promote a refresh rate or change
authoritative simulation, save formats, network timestamps or demo timing.

| Clock | Production owner and units | Boundary |
| --- | --- | --- |
| Host elapsed time | `idSys::GetClockTicks` / `ClockTicksPerSecond`; monotonic fractional milliseconds | QPC on Windows and the platform monotonic implementation elsewhere. Calendar time is not an input. Integer `Sys_Milliseconds` remains the established event/scheduler boundary. |
| Scheduler/usercmd | `idCommon::GetUserCmdTime`: floor(tick * 1000 / Hz), widened multiplication; `Common::Async` | At 60 Hz deadlines alternate 16 and 17 ms. Rendering may run between ticks. This ladder is not game time. |
| Authoritative game | SP/MP `idGameLocal::RunFrame`, `GetMSec()` | Ordinary 60 Hz game steps remain 16 ms. Physics, scripts, event dispatch, RNG, traces and damage keep this clock. |
| Network | `idAsyncServer::RunFrame`, game frame * integer game step | Snapshot labels and duplicated usercmd labels agree with the game. Changing them to the scheduler ladder accumulates 40 ms of disagreement per real second. |
| Prediction | MP prediction/game frames and acknowledged snapshot state | Draw samples cannot submit commands, replay prediction or commit a pose. A remote player's displayed pose age is the client's lead less the replay tics it re-simulates that remote for; the client advertises that budget (`net_mpRemoteExtrapolation`) and lag compensation rewinds by the age, never by a draw-time sample (MP-07). Remote bodies stay outside presentation interpolation while the local client plays, so the rewind owes them no extra presentation delay; a spectator, which fires nothing, draws them on its camera's clock. |
| Camera, eligible roots and view weapon | SP/MP `PreparePlayerSceneForRender` | One frozen high-resolution phase over previous/current authoritative poses. The intentional delay is at most one tick; no collision extrapolation. Opt-in late look turns only the drawn first-person eye and what it holds toward unapplied input, frozen once per draw ([presentation owners](presentation-owners.md)). Alternate views, client debris and active AF poses share the same phase. |
| Skeletons | `presentationAnimationTime` | Previous time plus the rounded phase-scaled interval, clamped to the two snapshots. Integer animator API is retained. Altered tic rates/discontinuous intervals remain authoritative. |
| Materials and effects | `GetPresentationTimeMsec` | Current time plus the bounded phase-scaled game step, monotonic within an epoch. It consumes the same frozen phase as camera/root sampling. Integer renderer/effect APIs stay integer. |
| Root UI | `common->GetPresentationTime`, retained UI frame/timer ownership | Host presentation time continues through an SP menu pause; it does not advance game scripts. World-GUI semantics remain UI-09/HF-06 work. |
| Audio | Sound-world time, pause and sound-system sample clock | Sound is not advanced by presentation sampling. Cinematic skip explicitly carries sound time forward. AUD-02 owns audible lifecycle qualification, including Arena's known pause gap. |
| Capture/demo | Session render-demo, game/network-demo and AVI clocks | Game demo/timedemo presentation bypasses remain. Capture uses engine render targets, not wall-clock screenshots; deterministic demo semantics are unchanged. |
| XR pose/display | OpenXR `predictedDisplayTime` | Runtime-domain time for `xrLocate*` and frame submission only. It is not numerically compared with QPC/host ticks. |
| XR smooth turn | `PresentationFrameDelta` sampled after successful wait/begin | Host elapsed seconds, clamped to 0..0.1; first frame/restart/frequency changes seed zero. No millisecond truncation; no assumed XrTime conversion. |

## Pause, time scale and discontinuities

Ordinary SP menu pause and `g_stopTime` hold the authoritative scene: phase 1,
material time equal to game time. Resume reanchors the transient phase. SP slow
motion retains the normal usercmd cadence while using a smaller integer game
step. Its altered animation cadence still selects the authoritative skeletal
fallback. Accelerated time and other altered scheduler rates retain their
existing behavior; this change does not claim smooth animation at arbitrary
tic rates.

Competitive pause and the Arena tableau/menu freeze use the existing MP
`ThinkMatchPaused`/deadline rebasing path while network/game labels advance.
They are not an SP stop-time switch. The existing draw admission and effect
owners remain authoritative; audio pause parity belongs to AUD-02/MP-04.

The shared `PresentationClock` predicts a real tick boundary from each game
delta rather than reanchoring to every late draw. Early observations correct
immediately; late correction remains capped at 1 ms per tick. Long stalls with
an unchanged game sample saturate at phase 1 instead of periodically cycling
back to phase 0. More than four catch-up ticks, map/restore time reversal,
backwards host time or a changed rate/step reset the transient epoch. All game
delta arithmetic is widened before subtraction, so signed clock wrap does not
overflow this policy. Material output saturates at the integer boundary until
the next epoch rather than overflowing it. This is not a global repair of the
engine's other 32-bit timestamp users.

`PreparePlayerSceneForRender` freezes `presentationClockSample` before camera,
entity, weapon and material consumers run. `EndPresentationSceneForRender`
releases it, including multiplayer early exits. No clock policy state is saved
or transmitted. HF-03 through HF-05 added draw-only owners for late look,
alternate views, client debris and AF poses on this clock; their contract,
remaining exclusions (remote actors, angular joint modifiers, fractures) and
evidence are in [presentation owners](presentation-owners.md).

## Regression evidence

`openq4-presentation-clock` compiles the production policy and exercises
submillisecond samples, exact 16/17 ms deadlines, one million ticks, 30/60/120/
144/165/240/360/997 Hz sampling, jitter, catch-up, missed ticks, game/host wrap,
pause/resume, slow steps, resets and XR deltas. A synthetic authoritative event
ledger is identical across presentation caps; it is a policy test, not a claim
to replay the entire game.

`ui_retained_pause.py` compiles the actual SP clock methods against a deterministic
clock and renderer recorder, including repeated reads of a frozen scene.
The recovered `presentation_interpolation_contract.py` protects both in-tree
games' presentation-only ownership, restoration and admission paths. Its old
Python copies of clock algorithms were removed in favor of the native policy
test. Runtime results and exact workload identities are recorded in the
[baseline evidence](baseline-evidence.md); physical motion/latency and real XR
comfort remain separate qualification gates.

`presentation_clock_ownership.py` additionally compiles the actual `idCommon`
scheduler methods and the current SP/MP/server timestamp update expressions.
One million ticks keep SP, MP and snapshot labels identical at 16 ms while
the scheduler follows its exact 16/17 ms ladder. This tests those production
boundaries, with the rest of the game intentionally outside the fixture.

The final live Air Defense 1 SP and Q4DM1 MP controls record 256 buffered samples
each, including the exact frozen fractional host sample, game step, scheduler
rate and phase. Both retain monotonic host samples, bounded phase and 16 ms game
labels at 60 Hz. Diagnostics preserve their original `rt/t/f` prefix and add
`hrt/step/hz/phase`; the first observation is not a serialized clock anchor for
complete offline replay. Logs and hashes are in the baseline evidence index.
