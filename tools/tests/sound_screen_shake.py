#!/usr/bin/env python3
"""Run the production camera-shake queries against authored sound envelopes.

Compiles the actual emitter/world queries, playback clock and distance falloff
with small sound/container doubles. No audio device or proprietary assets are
required. Retail 1.4.2's camera scale and map-unit falloff are the oracle, not
the unrelated light-flicker amplitude or OpenAL gain.
"""
from pathlib import Path
import argparse
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 0
    for end in range(brace, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[start:end + 1]
    raise ValueError(signature)


SUPPORT = r'''
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
using int64 = int64_t;
#define ID_INLINE inline
#define FLOAT_IS_NAN(v) (!std::isfinite(v))
#define DEG2RAD(v) ((v) * 3.14159265358979323846f / 180.0f)
template<class T> T Max(T a, T b) { return std::max(a, b); }
struct idMath {
    static float ClampFloat(float a, float b, float v) { return std::clamp(v, a, b); }
    static int FtoiFast(float v) { return int(v); }
    static float ATan(float y, float x) { return std::atan2(y, x); }
};
struct idStr { static int Length(const char* s) { return int(std::strlen(s)); } };
struct idVec3 {
    float x=0, y=0, z=0;
    idVec3 operator-(const idVec3& v) const { return {x-v.x, y-v.y, z-v.z}; }
    float Length() const { return std::sqrt(x*x+y*y+z*z); }
};
template<class T> struct List : std::vector<T> {
    using std::vector<T>::vector;
    int Num() const { return int(this->size()); }
};
struct idCVar {
    float value;
    float GetFloat() const { return value; }
    bool GetBool() const { return value != 0; }
};
idCVar s_frequencyShift{1}, com_timescale{1}, s_quadraticFalloff{0}, s_constantAmplitude{-1};
enum { SSF_GLOBAL=8, SSF_LOOPING=32, SSF_NO_FLICKER=256 };
struct soundShaderParms_t {
    float volume=0.63095734448f, shakes=1, minDistance=500, maxDistance=5000, frequencyShift=1;
    int soundShaderFlags=0;
};
struct idSoundSample {
    int duration=5000;
    int LengthInMsec() const { return duration; }
    float GetAmplitude(int) const { return 0.75f; }
};
struct idSoundShader {
    const char* data[2]={"za", "az"};
    const char* GetShakeData(int choice) const { return data[choice]; }
};
struct idSoundChannel;
struct idSoundWorld { virtual ~idSoundWorld() = default; };
struct idSoundWorldLocal : idSoundWorld {
    List<struct idSoundEmitterLocal*> emitters;
    struct { idVec3 pos; } listener;
    int now=100;
    float slowmoSpeed=1;
    int GetSoundTime() const { return now; }
    float CurrentShakeAmplitude();
    float ShakeAmplitudeForPosition(const idVec3&);
};
struct idSoundEmitterLocal {
    List<idSoundChannel*> channels;
    idVec3 origin;
    idSoundWorldLocal* soundWorld=nullptr;
    float CurrentAmplitude();
    float ShakeAmplitudeForPosition(int, const idVec3&);
};
struct idSoundChannel {
    soundShaderParms_t parms;
    idSoundShader* soundShader=nullptr;
    idSoundSample* leadinSample=nullptr;
    idSoundSample* loopingSample=nullptr;
    idSoundEmitterLocal* emitter=nullptr;
    int startTime=100, endTime=5200, choice=0, lastFrequencyShiftTime=0;
    float elapsedFrequencyShiftTime=0, lastFrequencyShift=1;
    bool IsLooping() const { return (parms.soundShaderFlags & SSF_LOOPING) != 0; }
};
struct idSoundSystemLocal {
    idSoundWorldLocal* world=nullptr;
    idSoundWorld* GetSoundWorldFromId(int id) { return id == 1 ? world : nullptr; }
    float CurrentShakeAmplitudeForPosition(int, int, const idVec3&);
};
static bool SoundUsesMusicVolume(const soundShaderParms_t&) { return false; }
static void near(float got, float expected, const char* name) {
    if (!std::isfinite(got) || std::fabs(got-expected) > 0.00001f) {
        std::fprintf(stderr, "%s: got %.8f expected %.8f\n", name, got, expected);
        std::exit(1);
    }
}
'''

CASES = r'''
int main() {
    idSoundSample sample;
    idSoundShader shader;
    idSoundWorldLocal world;
    idSoundEmitterLocal emitter;
    emitter.soundWorld=&world;
    idSoundChannel channel;
    channel.soundShader=&shader; channel.leadinSample=&sample; channel.emitter=&emitter;
    emitter.channels={&channel}; world.emitters={&emitter, nullptr};
    idSoundSystemLocal system; system.world=&world;
    auto query=[&](float distance) { return system.CurrentShakeAmplitudeForPosition(1, 999999, {distance,0,0}); };
    // z, -4 dB and shakes 1: the stock cannon's peak, with an original test envelope.
    near(query(0), 0.35801635f, "cannon peak uses camera scale");
    near(query(500), 0.35801635f, "full shake inside minimum range");
    near(query(2750), 0.18261746f, "halfway falloff in map units, before atan");
    near(query(5000), 0, "maximum range");
    near(query(10000), 0, "distant cannon cannot shake the camera");
    world.listener.pos={5000,0,0};
    near(world.CurrentShakeAmplitude(), 0, "listener query uses current position");
    near(query(0), 0.35801635f, "explicit position is not cached listener mix");
    near(system.CurrentShakeAmplitudeForPosition(99, 100, {}), 0, "unknown world");
    s_quadraticFalloff.value=1;
    near(query(2750), 0.09178074f, "optional quadratic falloff");
    s_quadraticFalloff.value=0;
    channel.parms.shakes=10;
    near(query(0), 1.57563106f, "large authored shakes saturate inside atan");
    channel.parms.shakes=1;
    idSoundChannel other=channel;
    emitter.channels.push_back(&other);
    near(query(0), 0.35801635f, "same emitter takes strongest, does not stack");
    other.parms.shakes=.5f;
    near(query(0), 0.35801635f, "weaker channel cannot replace stronger");
    emitter.channels={&channel};
    idSoundEmitterLocal second=emitter;
    world.emitters.push_back(&second);
    near(query(0), 0.71603270f, "independent emitters add");
    world.emitters.pop_back();
    near(emitter.CurrentAmplitude(), 1.44255633f, "light flicker keeps its original scale");
    channel.parms.soundShaderFlags=SSF_NO_FLICKER;
    world.now=134;
    near(query(0), 0, "no_flicker cannot shake a silent envelope tail");
    world.now=167;
    near(query(0), 0, "finished envelope cannot replay during sample tail");
    channel.parms.soundShaderFlags=SSF_LOOPING;
    near(query(0), 0.35801635f, "loop wraps authored envelope");
    channel.choice=1;
    near(query(0), 0, "variant uses its own authored envelope");
    channel.choice=0; channel.parms.soundShaderFlags=SSF_GLOBAL;
    world.now=100;
    near(query(10000), 0.35801635f, "global shake bypasses distance");
    channel.parms.soundShaderFlags=0;
    shader.data[0]="";
    near(query(0), 0, "no invented PCM camera shake");
    shader.data[0]="za";
    world.now=99;
    near(query(0), 0, "future channel");
    world.now=5300;
    near(query(0), 0, "completed channel");
    world.now=100; channel.endTime=1;
    near(query(0), 0, "stopped channel");
    channel.endTime=5200; channel.parms.shakes=0;
    near(query(0), 0, "no_shakes");
    channel.parms.shakes=1;
    s_constantAmplitude.value=1;
    near(query(0), 0, "constant light diagnostic cannot force camera shake");
    s_constantAmplitude.value=-1;
    // The real playback clock must preserve pitch and slow motion, not game time.
    channel.parms.frequencyShift=.5f;
    world.now=150;
    near(query(0), 0.35801635f, "pitch-adjusted envelope stays on first sample");
    world.now=168;
    near(query(0), 0, "pitch-adjusted envelope advances to silence");
    channel.parms.frequencyShift=1;
    channel.lastFrequencyShiftTime=0; channel.elapsedFrequencyShiftTime=0;
    world.slowmoSpeed=.5f; world.now=101;
    near(query(0), 0.35801635f, "first channel update starts slow-motion clock");
    world.now=150;
    near(query(0), 0.35801635f, "slow-motion envelope stays on first sample");
    world.now=168;
    near(query(0), 0, "slow-motion envelope advances to silence");
    std::puts("PASS: camera strength, range, aggregation, envelopes, playback clock and light isolation");
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.tmp/screen-shake/contract')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    emitter = (ROOT / 'src/sound/snd_emitter.cpp').read_text(encoding='utf-8')
    world = (ROOT / 'src/sound/snd_world.cpp').read_text(encoding='utf-8')
    constants = '\n'.join(re.findall(r'^static const (?:int|float) SOUND_(?:SHADER_\w+|FREQUENCY_SHIFT_\w+|CHANNEL_COMPLETION_GRACE_MSEC) = [^;]+;', emitter, re.M))
    bodies = [function(emitter, signature) for signature in (
        'static ID_INLINE float SoundSanitizePositiveValue(',
        'static ID_INLINE float SoundChannelFrequencyShift(',
        'static float SoundChannelPlaybackRate(',
        'static float SoundChannelPlaybackTimeMsec(',
        'static bool SoundChannelHasCompleted(',
        'static void SoundWorldApplyDistanceFalloff(',
        'float idSoundEmitterLocal::CurrentAmplitude(',
        'float idSoundEmitterLocal::ShakeAmplitudeForPosition(',
    )]
    bodies += [function(world, signature) for signature in (
        'float idSoundWorldLocal::CurrentShakeAmplitude(',
        'float idSoundWorldLocal::ShakeAmplitudeForPosition(',
        'float idSoundSystemLocal::CurrentShakeAmplitudeForPosition(',
    )]
    source = output / 'screen-shake.cpp'
    source.write_text(SUPPORT + constants + '\n' + '\n'.join(bodies) + CASES, encoding='utf-8')
    compiler = shutil.which('clang++') or shutil.which('g++')
    if not compiler:
        raise RuntimeError('clang++ or g++ is required')
    executable = output / ('screen-shake.exe' if os.name == 'nt' else 'screen-shake')
    env = dict(os.environ, TEMP=str(output), TMP=str(output), TMPDIR=str(output))
    for name, command in (
        ('compile', [compiler, '-std=c++17', '-O0', str(source), '-o', str(executable)]),
        ('run', [str(executable)]),
    ):
        result = subprocess.run(command, cwd=output, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / f'{name}.log').write_text(result.stdout, encoding='utf-8')
        print(result.stdout, end='')
        if result.returncode:
            raise RuntimeError(f'{name} failed: {output}')


if __name__ == '__main__':
    main()
