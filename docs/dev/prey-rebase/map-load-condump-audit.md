# Prey map load conDump audit

- Generated: 2026-11-21T17:57:05+00:00
- Started: 2026-11-21T17:42:38+00:00
- Map manifest: `.vscode/prey-maps.json`
- Renderer API: `gl`
- Retail asset root: `C:\Program Files (x86)\R.G. Mechanics\Prey`
- openPREY install root: `.install`
- Raw audit output: `.tmp/audit-gl`
- Per-map timeout: 120s
- Post-load settle time before conDump: 2500ms

## Summary

- Maps attempted: 37
- Maps with conDumps: 37
- Map-command loads that completed: 37
- Positive target-map completion markers: 37
- Process exits with conDumps and verified map loads: 37
- Detected map-load failures: 0
- Missing positive target-map completion markers: 0
- Timeouts: 0
- Non-zero process exits: 0
- Unknown process exit statuses: 0
- Unique issue signatures: 27
- Actionable issue signatures: 10
- Known notice signatures: 17

## Issue families

| Family | Severity | Unique issues | Maps | Occurrences | Examples |
| --- | --- | ---: | --- | ---: | --- |
| Image/material dependency load warning | warning | 4 | all 37 maps | 185 | `WARNING: Couldn't load image: gfx/guis/mainmenu/level_edge_fade : gfx/guis/mainmenu/level_edge_fade#__0200`; `WARNING: Couldn't load image: gfx/guis/mainmenu/screen : gfx/guis/mainmenu/screen#__0200`; `WARNING: Couldn't load image: gfx/guis/mainmenu/tooltip_edge : gfx/guis/mainmenu/tooltip_edge#__0200` |
| Other issue-like console line | warning | 3 | all 37 maps | 112 | `WARNING: Couldn't load gui: 'guis/arena_menu.gui'`; `WARNING: arena campaign: could not load 'arena/openq4_campaign.cfg'`; `WARNING: Entity 'func_skybox_portal_36' has bad portal source (-192 -96 192)` |
| Sound asset/decode warning | warning | 1 | all 37 maps | 37 | `WARNING: Couldn't load sound 'main_menu_gameplay' using default (probed: main_menu_gameplay)` |
| Non-precached decl load | warning | 2 | game/dmescher, game/dmescher2, game/dmgravitylab_6, game/dmplanes_4, game/dmroadhouse, game/dmsalvagewalk, game/dmshuttle1, game/dmshuttle2, … (+3) | 22 | `WARNING: Loading non pre-cached fx decl fx/portal_closed_idle`; `WARNING: Loading non pre-cached particle decl portal_closed_idle` |
| Performance preset report | notice | 1 | all 37 maps | 37 | `First-launch performance preset 'enhanced': dedicated GPU capacity; not a measured frame rate; GPU=discrete, RAM=40658 MiB, dedicated VRAM=8188 MiB (0=unknown/shared), drawable=2560x1440, CPUs=20, scene scale=100%, post AA=2, display=240 Hz (0=unknown), frame cap=240; preserving configured overrides.` |
| Unavailable OpenGL extension probe | notice | 1 | all 37 maps | 74 | `X..GL_ANGLE_texture_compression_dxt5 not found` |
| Map without a retail reverb file | notice | 15 | game/deathwalk1, game/deathwalk2, game/deathwalk3, game/dmescher, game/dmescher2, game/dmgravitylab_6, game/dmplanes_4, game/dmroadhouse, … (+7) | 15 | `sound: missing efxs/deathwalk1.efx and efxs/default.efx`; `sound: missing efxs/deathwalk2.efx and efxs/default.efx`; `sound: missing efxs/deathwalk3.efx and efxs/default.efx` |

## Unique issues

| ID | Severity | Maps | Occurrences | Representative issue |
| --- | --- | --- | ---: | --- |
| U001 | warning | all 37 maps | 37 | `WARNING: arena campaign: could not load 'arena/openq4_campaign.cfg'` |
| U002 | warning | all 37 maps | 74 | `WARNING: Couldn't load gui: 'guis/arena_menu.gui'` |
| U003 | warning | all 37 maps | 74 | `WARNING: Couldn't load image: gfx/guis/mainmenu/level_edge_fade : gfx/guis/mainmenu/level_edge_fade#__0200` |
| U004 | warning | all 37 maps | 37 | `WARNING: Couldn't load image: gfx/guis/mainmenu/screen : gfx/guis/mainmenu/screen#__0200` |
| U005 | warning | all 37 maps | 37 | `WARNING: Couldn't load image: gfx/guis/mainmenu/tooltip_edge : gfx/guis/mainmenu/tooltip_edge#__0200` |
| U006 | warning | all 37 maps | 37 | `WARNING: Couldn't load image: gfx/guis/mainmenu/tooltip_mid : gfx/guis/mainmenu/tooltip_mid#__0200` |
| U007 | warning | all 37 maps | 37 | `WARNING: Couldn't load sound 'main_menu_gameplay' using default (probed: main_menu_gameplay)` |
| U008 | warning | game/dmescher, game/dmescher2, game/dmgravitylab_6, game/dmplanes_4, game/dmroadhouse, game/dmsalvagewalk, game/dmshuttle1, game/dmshuttle2, … (+3) | 11 | `WARNING: Loading non pre-cached fx decl fx/portal_closed_idle` |
| U009 | warning | game/dmescher, game/dmescher2, game/dmgravitylab_6, game/dmplanes_4, game/dmroadhouse, game/dmsalvagewalk, game/dmshuttle1, game/dmshuttle2, … (+3) | 11 | `WARNING: Loading non pre-cached particle decl portal_closed_idle` |
| U010 | warning | game/lotaa | 1 | `WARNING: Entity 'func_skybox_portal_36' has bad portal source (-192 -96 192)` |
| U011 | notice | all 37 maps | 37 | `First-launch performance preset 'enhanced': dedicated GPU capacity; not a measured frame rate; GPU=discrete, RAM=40658 MiB, dedicated VRAM=8188 MiB (0=unknown/shared), drawable=2560x1440, CPUs=20, scene scale=100%, post AA=2, display=240 Hz (0=unknown), frame cap=240; preserving configured overrides.` |
| U012 | notice | all 37 maps | 74 | `X..GL_ANGLE_texture_compression_dxt5 not found` |
| U013 | notice | game/deathwalk1 | 1 | `sound: missing efxs/deathwalk1.efx and efxs/default.efx` |
| U014 | notice | game/deathwalk2 | 1 | `sound: missing efxs/deathwalk2.efx and efxs/default.efx` |
| U015 | notice | game/deathwalk3 | 1 | `sound: missing efxs/deathwalk3.efx and efxs/default.efx` |
| U016 | notice | game/dmescher | 1 | `sound: missing efxs/dmescher.efx and efxs/default.efx` |
| U017 | notice | game/dmescher2 | 1 | `sound: missing efxs/dmescher2.efx and efxs/default.efx` |
| U018 | notice | game/dmgravitylab_6 | 1 | `sound: missing efxs/dmgravitylab_6.efx and efxs/default.efx` |
| U019 | notice | game/dmplanes_4 | 1 | `sound: missing efxs/dmplanes_4.efx and efxs/default.efx` |
| U020 | notice | game/dmroadhouse | 1 | `sound: missing efxs/dmroadhouse.efx and efxs/default.efx` |
| U021 | notice | game/dmsalvagewalk | 1 | `sound: missing efxs/dmsalvagewalk.efx and efxs/default.efx` |
| U022 | notice | game/dmshuttle1 | 1 | `sound: missing efxs/dmshuttle1.efx and efxs/default.efx` |
| U023 | notice | game/dmshuttle2 | 1 | `sound: missing efxs/dmshuttle2.efx and efxs/default.efx` |
| U024 | notice | game/dmsphere | 1 | `sound: missing efxs/dmsphere.efx and efxs/default.efx` |
| U025 | notice | game/dmtopillogical_4 | 1 | `sound: missing efxs/dmtopillogical_4.efx and efxs/default.efx` |
| U026 | notice | game/dmtunnelrat_8 | 1 | `sound: missing efxs/dmtunnelrat_8.efx and efxs/default.efx` |
| U027 | notice | game/dmwallwalk2 | 1 | `sound: missing efxs/dmwallwalk2.efx and efxs/default.efx` |

## Per-map results

| Map | Kind | Status | Time | Issues | conDump | Log |
| --- | --- | --- | ---: | --- | --- | --- |
| game/roadhouse | sp | ok | 23.4s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/01_game_roadhouse/basepr/logs/condumps/01_game_roadhouse.txt` | `.tmp/audit-gl/savepaths/01_game_roadhouse/basepr/logs/01_game_roadhouse.log` |
| game/feedingtowera | sp | ok | 29.6s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/02_game_feedingtowera/basepr/logs/condumps/02_game_feedingtowera.txt` | `.tmp/audit-gl/savepaths/02_game_feedingtowera/basepr/logs/02_game_feedingtowera.log` |
| game/feedingtowerb | sp | ok | 30.4s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/03_game_feedingtowerb/basepr/logs/condumps/03_game_feedingtowerb.txt` | `.tmp/audit-gl/savepaths/03_game_feedingtowerb/basepr/logs/03_game_feedingtowerb.log` |
| game/lotaa | sp | ok | 20.6s | U011, U002, U003, U004, U005, U006, U007, U010, U001, U012 | `.tmp/audit-gl/savepaths/04_game_lotaa/basepr/logs/condumps/04_game_lotaa.txt` | `.tmp/audit-gl/savepaths/04_game_lotaa/basepr/logs/04_game_lotaa.log` |
| game/feedingtowerc | sp | ok | 21.6s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/05_game_feedingtowerc/basepr/logs/condumps/05_game_feedingtowerc.txt` | `.tmp/audit-gl/savepaths/05_game_feedingtowerc/basepr/logs/05_game_feedingtowerc.log` |
| game/feedingtowerd | sp | ok | 23.1s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/06_game_feedingtowerd/basepr/logs/condumps/06_game_feedingtowerd.txt` | `.tmp/audit-gl/savepaths/06_game_feedingtowerd/basepr/logs/06_game_feedingtowerd.log` |
| game/salvage | sp | ok | 19.7s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/07_game_salvage/basepr/logs/condumps/07_game_salvage.txt` | `.tmp/audit-gl/savepaths/07_game_salvage/basepr/logs/07_game_salvage.log` |
| game/salvageboss | sp | ok | 20.7s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/08_game_salvageboss/basepr/logs/condumps/08_game_salvageboss.txt` | `.tmp/audit-gl/savepaths/08_game_salvageboss/basepr/logs/08_game_salvageboss.log` |
| game/lotab | sp | ok | 16.5s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/09_game_lotab/basepr/logs/condumps/09_game_lotab.txt` | `.tmp/audit-gl/savepaths/09_game_lotab/basepr/logs/09_game_lotab.log` |
| game/shuttlea | sp | ok | 21.3s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/10_game_shuttlea/basepr/logs/condumps/10_game_shuttlea.txt` | `.tmp/audit-gl/savepaths/10_game_shuttlea/basepr/logs/10_game_shuttlea.log` |
| game/shuttleb | sp | ok | 24.0s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/11_game_shuttleb/basepr/logs/condumps/11_game_shuttleb.txt` | `.tmp/audit-gl/savepaths/11_game_shuttleb/basepr/logs/11_game_shuttleb.log` |
| game/biolabsa | sp | ok | 24.6s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/12_game_biolabsa/basepr/logs/condumps/12_game_biolabsa.txt` | `.tmp/audit-gl/savepaths/12_game_biolabsa/basepr/logs/12_game_biolabsa.log` |
| game/biolabsb | sp | ok | 20.8s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/13_game_biolabsb/basepr/logs/condumps/13_game_biolabsb.txt` | `.tmp/audit-gl/savepaths/13_game_biolabsb/basepr/logs/13_game_biolabsb.log` |
| game/superportal | sp | ok | 20.5s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/14_game_superportal/basepr/logs/condumps/14_game_superportal.txt` | `.tmp/audit-gl/savepaths/14_game_superportal/basepr/logs/14_game_superportal.log` |
| game/harvestera | sp | ok | 19.9s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/15_game_harvestera/basepr/logs/condumps/15_game_harvestera.txt` | `.tmp/audit-gl/savepaths/15_game_harvestera/basepr/logs/15_game_harvestera.log` |
| game/harvesterb | sp | ok | 20.9s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/16_game_harvesterb/basepr/logs/condumps/16_game_harvesterb.txt` | `.tmp/audit-gl/savepaths/16_game_harvesterb/basepr/logs/16_game_harvesterb.log` |
| game/spindlea | sp | ok | 20.0s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/17_game_spindlea/basepr/logs/condumps/17_game_spindlea.txt` | `.tmp/audit-gl/savepaths/17_game_spindlea/basepr/logs/17_game_spindlea.log` |
| game/spindleb | sp | ok | 24.7s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/18_game_spindleb/basepr/logs/condumps/18_game_spindleb.txt` | `.tmp/audit-gl/savepaths/18_game_spindleb/basepr/logs/18_game_spindleb.log` |
| game/girlfriendx | sp | ok | 23.4s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/19_game_girlfriendx/basepr/logs/condumps/19_game_girlfriendx.txt` | `.tmp/audit-gl/savepaths/19_game_girlfriendx/basepr/logs/19_game_girlfriendx.log` |
| game/lotad | sp | ok | 31.6s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/20_game_lotad/basepr/logs/condumps/20_game_lotad.txt` | `.tmp/audit-gl/savepaths/20_game_lotad/basepr/logs/20_game_lotad.log` |
| game/keeperfortress | sp | ok | 66.4s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/21_game_keeperfortress/basepr/logs/condumps/21_game_keeperfortress.txt` | `.tmp/audit-gl/savepaths/21_game_keeperfortress/basepr/logs/21_game_keeperfortress.log` |
| game/spherebrain | sp | ok | 30.8s | U011, U002, U003, U004, U005, U006, U007, U001, U012 | `.tmp/audit-gl/savepaths/22_game_spherebrain/basepr/logs/condumps/22_game_spherebrain.txt` | `.tmp/audit-gl/savepaths/22_game_spherebrain/basepr/logs/22_game_spherebrain.log` |
| game/deathwalk1 | sp | ok | 16.2s | U011, U002, U003, U004, U005, U006, U007, U001, U012, U013 | `.tmp/audit-gl/savepaths/23_game_deathwalk1/basepr/logs/condumps/23_game_deathwalk1.txt` | `.tmp/audit-gl/savepaths/23_game_deathwalk1/basepr/logs/23_game_deathwalk1.log` |
| game/deathwalk2 | sp | ok | 17.5s | U011, U002, U003, U004, U005, U006, U007, U001, U012, U014 | `.tmp/audit-gl/savepaths/24_game_deathwalk2/basepr/logs/condumps/24_game_deathwalk2.txt` | `.tmp/audit-gl/savepaths/24_game_deathwalk2/basepr/logs/24_game_deathwalk2.log` |
| game/deathwalk3 | sp | ok | 15.1s | U011, U002, U003, U004, U005, U006, U007, U001, U012, U015 | `.tmp/audit-gl/savepaths/25_game_deathwalk3/basepr/logs/condumps/25_game_deathwalk3.txt` | `.tmp/audit-gl/savepaths/25_game_deathwalk3/basepr/logs/25_game_deathwalk3.log` |
| game/dmescher | mp | ok | 21.4s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U016 | `.tmp/audit-gl/savepaths/26_game_dmescher/basepr/logs/condumps/26_game_dmescher.txt` | `.tmp/audit-gl/savepaths/26_game_dmescher/basepr/logs/26_game_dmescher.log` |
| game/dmescher2 | mp | ok | 17.3s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U017 | `.tmp/audit-gl/savepaths/27_game_dmescher2/basepr/logs/condumps/27_game_dmescher2.txt` | `.tmp/audit-gl/savepaths/27_game_dmescher2/basepr/logs/27_game_dmescher2.log` |
| game/dmgravitylab_6 | mp | ok | 21.2s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U018 | `.tmp/audit-gl/savepaths/28_game_dmgravitylab_6/basepr/logs/condumps/28_game_dmgravitylab_6.txt` | `.tmp/audit-gl/savepaths/28_game_dmgravitylab_6/basepr/logs/28_game_dmgravitylab_6.log` |
| game/dmplanes_4 | mp | ok | 16.8s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U019 | `.tmp/audit-gl/savepaths/29_game_dmplanes_4/basepr/logs/condumps/29_game_dmplanes_4.txt` | `.tmp/audit-gl/savepaths/29_game_dmplanes_4/basepr/logs/29_game_dmplanes_4.log` |
| game/dmroadhouse | mp | ok | 17.8s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U020 | `.tmp/audit-gl/savepaths/30_game_dmroadhouse/basepr/logs/condumps/30_game_dmroadhouse.txt` | `.tmp/audit-gl/savepaths/30_game_dmroadhouse/basepr/logs/30_game_dmroadhouse.log` |
| game/dmsalvagewalk | mp | ok | 15.6s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U021 | `.tmp/audit-gl/savepaths/31_game_dmsalvagewalk/basepr/logs/condumps/31_game_dmsalvagewalk.txt` | `.tmp/audit-gl/savepaths/31_game_dmsalvagewalk/basepr/logs/31_game_dmsalvagewalk.log` |
| game/dmshuttle1 | mp | ok | 17.2s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U022 | `.tmp/audit-gl/savepaths/32_game_dmshuttle1/basepr/logs/condumps/32_game_dmshuttle1.txt` | `.tmp/audit-gl/savepaths/32_game_dmshuttle1/basepr/logs/32_game_dmshuttle1.log` |
| game/dmshuttle2 | mp | ok | 33.5s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U023 | `.tmp/audit-gl/savepaths/33_game_dmshuttle2/basepr/logs/condumps/33_game_dmshuttle2.txt` | `.tmp/audit-gl/savepaths/33_game_dmshuttle2/basepr/logs/33_game_dmshuttle2.log` |
| game/dmsphere | mp | ok | 15.7s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U024 | `.tmp/audit-gl/savepaths/34_game_dmsphere/basepr/logs/condumps/34_game_dmsphere.txt` | `.tmp/audit-gl/savepaths/34_game_dmsphere/basepr/logs/34_game_dmsphere.log` |
| game/dmtopillogical_4 | mp | ok | 21.2s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U025 | `.tmp/audit-gl/savepaths/35_game_dmtopillogical_4/basepr/logs/condumps/35_game_dmtopillogical_4.txt` | `.tmp/audit-gl/savepaths/35_game_dmtopillogical_4/basepr/logs/35_game_dmtopillogical_4.log` |
| game/dmtunnelrat_8 | mp | ok | 29.7s | U011, U002, U003, U004, U005, U006, U007, U001, U012, U026 | `.tmp/audit-gl/savepaths/36_game_dmtunnelrat_8/basepr/logs/condumps/36_game_dmtunnelrat_8.txt` | `.tmp/audit-gl/savepaths/36_game_dmtunnelrat_8/basepr/logs/36_game_dmtunnelrat_8.log` |
| game/dmwallwalk2 | mp | ok | 28.4s | U011, U002, U003, U004, U005, U006, U007, U008, U009, U001, U012, U027 | `.tmp/audit-gl/savepaths/37_game_dmwallwalk2/basepr/logs/condumps/37_game_dmwallwalk2.txt` | `.tmp/audit-gl/savepaths/37_game_dmwallwalk2/basepr/logs/37_game_dmwallwalk2.log` |

## Reproduction

From the repository root:

```powershell
py -3 tools\validation\prey_map_load_condump_audit.py --renderer-api gl --basepath "C:\Program Files (x86)\R.G. Mechanics\Prey"
```

Every launch is forced windowed with `+set r_fullscreen 0` and uses the engine `conDump` command.
