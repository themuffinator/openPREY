#!/usr/bin/env python3
"""Pin openQ4's port of retail Quake 4's per-area EAX reverb (docs/dev/retail-audio-reverb.md).

The numeric behaviour is exercised by tools/tests/native/SoundReverbCoreTest.cpp; this check keeps
the retail constants, file names, messages, cvars and the engine wiring from drifting.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8", errors="replace")


def require(condition: bool, message: str, failures: list) -> None:
    if not condition:
        failures.append(message)


def body(text: str, signature: str) -> str:
    at = text.index(signature)
    start = text.index("{", at)
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[at:index + 1]
    raise ValueError(signature)


def main() -> int:
    failures: list = []
    core = read("src/sound/SoundReverbCore.h")
    reverb = read("src/sound/snd_system.cpp")
    emitter = read("src/sound/snd_emitter.cpp")
    world = read("src/sound/snd_world.cpp")
    shader = read("src/sound/snd_shader.cpp")
    system = read("src/sound/snd_system.cpp")
    local = read("src/sound/snd_local.h")
    public = read("src/sound/sound.h")
    hardware = read("src/sound/OpenAL/AL_SoundHardware.cpp")
    voice = read("src/sound/OpenAL/AL_SoundVoice.cpp")
    settings = read("src/sound/SoundSettings.cpp")
    session = read("src/framework/Session.cpp")
    meson = read("meson.build")
    doc = read("docs/dev/retail-audio-reverb.md")

    # Quake4.exe 1.4.2 source and slot constants
    for token in (
        "SOUND_REVERB_SLOTS = 4",
        "SOUND_REVERB_ROOM_RADIO_MB = -10000",
        "SOUND_REVERB_ROOM_VOICEOVER_MB = -500",
        "SOUND_REVERB_OCCLUSION_PER_PORTAL_MB = -1500",
        "SOUND_REVERB_OCCLUSION_LF_RATIO = 0.0f",
        "SOUND_REVERB_OCCLUSION_ROOM_RATIO = 1.5f",
        "SOUND_REVERB_OCCLUSION_DIRECT_RATIO = 1.0f",
        "SOUND_REVERB_MUTED_ROOM_MB = -10000",
        "SOUND_REVERB_FLAG_DECAY_HF_LIMIT = 0x20",
        "spread * 0.3185f - 0.637f",
        "spread * 0.181f + 0.637f",
        "( size * size * size ) / 16.0f",
        "pan[0] = -scale * listenerDirection[1];",
        "pan[1] = scale * listenerDirection[2];",
        "pan[2] = scale * listenerDirection[0];",
    ):
        require(token in core, f"SoundReverbCore.h lost retail token: {token}", failures)
    plan = body(core, "inline void SoundReverb_PlanSlots(")
    require("distanceSquared > 0.0f && distanceSquared < farthestDistance" in plan,
            "slot gathering must keep retail's nonzero, nearer-than-farthest portal test", failures)
    keep = plan[plan.index("keep slots that already hold"):plan.index("give the remaining areas")]
    require("break" not in keep, "1.4.2 keeps scanning after a pinned-slot match; no break", failures)

    # loaders: file names, lexer flags and retail messages
    for token in (
        '"efxs/default.efx"',
        '"efxs/"',
        '".efx"',
        '".reverb"',
        '"Version"',
        "SOUND_REVERB_EFX_VERSION = 1",
        "LEXFL_NOSTRINGCONCAT | LEXFL_NOFATALERRORS",
        '"sound: found %s\\n"',
        '"sound: missing %s and %s\\n"',
        "\"Loaded reverb file '%s'\\n\"",
        "\"Malformed reverb file header in '%s'\"",
        "\"Malformed reverb file '%s' line %d\"",
        "\"Invalid reverb area number %d [0,%d] in '%s'\"",
        "\"Unknown reverb type '%s' in '%s'\"",
        '"idEFXFile::ReadEffect: Unknown effect definition"',
        '"idEFXFile::ReadEffect: Invalid parameter in reverb definition"',
        '"idEFXFile::ReadEffect: EOF without closing brace"',
        '"idEFXFile::LoadFile: Unknown file version"',
        'FindEffect( "default" )',
    ):
        require(token in reverb, f"snd_system.cpp lost retail reverb token: {token}", failures)
    load = body(reverb, "bool idSoundReverb::LoadEffectFile(")
    require("if( ReadEffect( src, effect ) )" in load and load.count("effects.Clear();") == 1,
            "1.4.2 skips an effect that fails to parse and keeps the rest of the file", failures)
    for name in ("environment size", "environment diffusion", "room hf", "room lf", "decay time",
                 "decay hf ratio", "decay lf ratio", "reflections delay", "reflections pan",
                 "reverb delay", "reverb pan", "echo time", "echo depth", "modulation time",
                 "modulation depth", "air absorption hf", "hf reference", "lf reference",
                 "room rolloff factor", "flags"):
        require(f'token == "{name}"' in reverb, f"EFX property not parsed: {name}", failures)

    # retail cvars with retail flags
    require('idCVar s_useEAXReverb( "s_useEAXReverb", "1", CVAR_SOUND | CVAR_ARCHIVE | CVAR_BOOL,' in reverb,
            "s_useEAXReverb must keep retail's archived default 1", failures)
    require('idCVar s_useEAXOcclusion( "s_useEAXOcclusion", "1", CVAR_SOUND | CVAR_BOOL | CVAR_ARCHIVE,' in reverb,
            "s_useEAXOcclusion must keep retail's archived default 1", failures)
    require('idCVar s_muteEAXReverb( "s_muteEAXReverb", "0", CVAR_SOUND | CVAR_BOOL,' in reverb,
            "s_muteEAXReverb must keep retail's default 0", failures)
    require('"listReverbs"' in system, "listReverbs command missing", failures)

    # wiring: level load, per-frame slots before voices, per-voice routing
    require("soundSystem->EndLevelLoad( fullMapName.c_str() );" in session,
            "the session must pass its maps/<name> path to EndLevelLoad, as retail does", failures)
    require("virtual\tvoid\t\t\tEndLevelLoad( const char* mapName ) = 0;" in public,
            "idSoundSystem::EndLevelLoad must take the map name", failures)
    for method in ("GetReverbName( int reverb ) = 0", "GetNumAreas() = 0", "GetReverb( int area ) = 0",
                   "SetReverb( int area, const char* reverbName, const char* fileName ) = 0"):
        require(method in public, f"retail reverb editor interface missing: {method}", failures)
    require("reverb.LoadLevel( mapName" in system, "EndLevelLoad must load the reverb tables", failures)
    require("world != session->sw" in body(system, "void idSoundReverb::Update("),
            "only the game sound world may move the slots; the menu world shares its render world", failures)
    update = body(world, "void idSoundWorldLocal::Update()")
    require(update.index("soundSystemLocal.reverb.Update( this );") < update.index("chan->UpdateHardware( 0.0f, currentTime );"),
            "reverb slots must be placed before any channel takes its sends", failures)
    hw = body(emitter, "void idSoundChannel::UpdateHardware(")
    require("SetReverbSource( soundSystemLocal.reverb.SlotForArea( emitter->lastValidPortalArea )" in hw,
            "voices must route to their own area's slot", failures)
    require("leadinSample->NumChannels() == 1" in hw, "only mono voices reach the reverb", failures)
    require("IsRadioChatterChannel( this )" in hw and "SSF_IS_VO" in hw, "radio and voice-over room levels", failures)
    require("soundSystemLocal.hardware.HasEFX() && s_useEAXOcclusion.GetBool() && s_useOcclusion.GetBool()" in hw,
            "EAX occlusion exists only with EAX reverb, as in retail", failures)
    spatialize = body(emitter, "void idSoundEmitterLocal::Update(")
    require(spatialize.index("lastValidPortalArea = soundInArea;") < spatialize.index("if( ( useOcclusion || globalOcclusion ) && s_useOcclusion.GetBool() )"),
            "every emitter in range tracks its area, independent of occlusion", failures)
    require("parms.wetLevel = 1.0f;" in body(shader, "bool idSoundShader::ParseShader("),
            "sound shaders must default to the full retail reverb send", failures)
    require("channel->soundShader->GetParms()->wetLevel > 0.0f" in world,
            "old saves and demos must get their shader's wet level back", failures)

    # hardware and settings integration
    for token in ("int idSoundHardware_OpenAL::SyncReverbSlots()", "void idSoundHardware_OpenAL::ReleaseAreaReverbSlots()",
                  "voices[i].DetachReverbSends();", "AL_EAXREVERB_REFLECTIONS_PAN", "AL_EAXREVERB_LATE_REVERB_PAN",
                  "AL_REVERB_DENSITY", "ALC_MAX_AUXILIARY_SENDS"):
        require(token in hardware, f"AL_SoundHardware.cpp lost: {token}", failures)
    route = body(voice, "void idSoundVoice_OpenAL::ApplyWetDryRouting()")
    require("primarySlot, 0, openalAuxFilter" in route and "areaSlot, 1, openalAreaAuxFilter" in route,
            "send 0 feeds the primary slot and send 1 the source's area slot", failures)
    require("if (!enabled && !Native([&] {h.ReleaseAreaReverbSlots();return true;})) return false;" in settings,
            "turning EFX off must release the area slots first", failures)
    require("h.GetPrimaryAuxEffectSlot()" in settings, "checked routing must feed the primary slot", failures)
    require("h.HasAreaReverbResources()" in settings and "openalAreaAuxFilter" in settings,
            "portable recovery must inventory the area reverb resources", failures)
    require("SoundReverbCore.h" in local, "snd_local.h must include the shared core", failures)

    # tests and documentation
    require("tools/tests/native/SoundReverbCoreTest.cpp" in meson and "'openq4-sound-reverb-core'" in meson,
            "the native core test must stay registered", failures)
    for token in ("0x101742d0", "0x10173780", "0x1016e6a9", "efx-presets.h", "s_useEAXOcclusion", "s_muteEAXReverb"):
        require(token in doc, f"docs/dev/retail-audio-reverb.md lost: {token}", failures)

    if failures:
        for failure in failures:
            print("FAIL:", failure)
        return 1
    print("sound retail reverb contract: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
