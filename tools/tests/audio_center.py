#!/usr/bin/env python3
"""Measure production centre routing with OpenAL surround, quad, stereo and HRTF PCM."""
from pathlib import Path
import argparse
import ctypes as C
import hashlib
import json
import math
import os
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, default=ROOT / '.install/OpenAL32.dll')
    parser.add_argument('--output', type=Path, default=ROOT / '.tmp/audio/center')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cpp = output / 'route.cpp'
    cpp.write_text('''#include "src/sound/SoundSurround.h"
#if defined(_WIN32)
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
extern "C" EXPORT bool eligible(bool surround, bool mono, bool explicitCenter, float fraction, float positionSquared) {
    return SoundUseCenterChannel(surround, mono, explicitCenter, fraction, positionSquared);
}
extern "C" EXPORT void route(const short* input, int frames, float fraction, short* output) {
    SoundRouteMonoToCenter(input, frames, fraction, output);
}
''')
    helper_path = output / ('route.dll' if os.name == 'nt' else 'route.so')
    subprocess.run([os.environ.get('CXX', 'clang++'), '-std=c++17', '-shared', '-O2',
                    *([] if os.name == 'nt' else ['-fPIC']), '-I', str(ROOT), str(cpp), '-o', str(helper_path)], cwd=output, check=True)
    helper = C.CDLL(str(helper_path))
    helper.eligible.argtypes = [C.c_bool, C.c_bool, C.c_bool, C.c_float, C.c_float]
    helper.eligible.restype = C.c_bool
    helper.route.argtypes = [C.POINTER(C.c_short), C.c_int, C.c_float, C.POINTER(C.c_short)]
    helper.route.restype = None
    checks = {
        'explicit_center': helper.eligible(True, True, True, 1, 10000),
        'global_vo': helper.eligible(True, True, False, .75, 0),
        'positional_vo_preserved': not helper.eligible(True, True, False, .75, 10000),
        'authored_stereo_preserved': not helper.eligible(True, False, True, 1, 0),
        'stereo_fallback': not helper.eligible(False, True, True, 1, 0),
        'nonfinite_rejected': not helper.eligible(True, True, True, math.nan, 0),
    }
    # Full int16 domain: no clipping, no LFE dialogue, conserved channel power
    # to within integer rounding, and equal non-centre speaker amplitudes.
    domain = (C.c_short * 65536)(*range(-32768, 32768))
    routed = (C.c_short * (65536 * 6))()
    for fraction in [0, .25, .75, 1]:
        helper.route(domain, len(domain), fraction, routed)
        valid = True
        for i, sample in enumerate(domain):
            values = routed[i * 6:i * 6 + 6]
            valid &= values[3] == 0 and values[0] == values[1] == values[4] == values[5]
            valid &= abs(sum(value * value for value in values) - sample * sample) <= 6 * abs(sample) + 6
        checks[f'pcm_power_{fraction}'] = bool(valid)

    library = args.library.resolve(strict=True)
    dll_directory = os.add_dll_directory(str(library.parent)) if os.name == 'nt' else None
    al = C.CDLL(str(library))
    ptr, integer, uint, floating = C.c_void_p, C.c_int, C.c_uint, C.c_float
    def fn(name, result, *params):
        call = getattr(al, name)
        call.restype, call.argtypes = result, params
        return call
    proc = fn('alcGetProcAddress', ptr, ptr, C.c_char_p)
    open_ = C.CFUNCTYPE(ptr, C.c_char_p)(proc(None, b'alcLoopbackOpenDeviceSOFT'))
    render = C.CFUNCTYPE(None, ptr, ptr, integer)(proc(None, b'alcRenderSamplesSOFT'))
    create = fn('alcCreateContext', ptr, ptr, C.POINTER(integer))
    current = fn('alcMakeContextCurrent', C.c_char, ptr)
    destroy = fn('alcDestroyContext', None, ptr)
    close = fn('alcCloseDevice', C.c_char, ptr)
    query = fn('alcGetIntegerv', None, ptr, integer, integer, C.POINTER(integer))
    error = fn('alGetError', integer)
    extension = fn('alIsExtensionPresent', C.c_char, C.c_char_p)
    alc_extension = fn('alcIsExtensionPresent', C.c_char, ptr, C.c_char_p)
    genb = fn('alGenBuffers', None, integer, C.POINTER(uint))
    gens = fn('alGenSources', None, integer, C.POINTER(uint))
    upload = fn('alBufferData', None, uint, integer, ptr, integer, integer)
    play = fn('alSourcePlay', None, uint)
    source_i = fn('alSourcei', None, uint, integer, integer)
    source_f = fn('alSourcef', None, uint, integer, floating)
    pcm = (C.c_short * 24000)(*(round(4096 * math.sin(i * 2 * math.pi * 440 / 48000)) for i in range(24000)))

    def measure(channels, fraction, hrtf=False):
        device = open_(None)
        layout = {2: 0x1501, 4: 0x1503, 6: 0x1504, 7: 0x1505, 8: 0x1506}[channels]
        attributes = (integer * 9)(0x1990, layout,
                                  0x1991, 0x1406, 0x1007, 48000, 0x1992, int(hrtf), 0)
        context = create(device, attributes)
        if not context:
            close(device)
            raise RuntimeError('Requested loopback context unavailable')
        current(context)
        try:
            mode, status = integer(), integer()
            query(device, 0x19AC, 1, C.byref(mode))
            query(device, 0x1993, 1, C.byref(status))
            direct = extension(b'AL_SOFT_direct_channels') == b'\x01'
            multichannel = extension(b'AL_EXT_MCFORMATS') == b'\x01'
            output_mode = alc_extension(device, b'ALC_SOFT_output_mode') == b'\x01'
            use_center = helper.eligible(direct and multichannel and output_mode and
                                         mode.value in (0x1504, 0x1505, 0x1506), True, fraction == 1, fraction, 0)
            direct_mode = 2 if extension(b'AL_SOFT_direct_channels_remix') == b'\x01' else 1
            b, s = uint(), uint()
            genb(1, C.byref(b)); gens(1, C.byref(s))
            source_i(s, 0x1007, 1)  # looping
            source_i(s, 0x202, 1)  # listener relative
            source_f(s, 0x1021, 0)  # engine owns dry attenuation
            source_f(s, 0x1031, 1)  # unchanged listener/global radius
            data = pcm
            if use_center:
                data = (C.c_short * (len(pcm) * 6))()
                helper.route(pcm, len(pcm), fraction, data)
                source_i(s, 0x1033, direct_mode)  # same unmatched-channel remix policy as the engine
            upload(b, 0x120B if use_center else 0x1101, data, C.sizeof(data), 48000)
            source_i(s, 0x1009, b.value)
            if error():
                raise RuntimeError('OpenAL rejected centre fixture')
            play(s)
            mix = (floating * (48000 * channels))()
            render(device, mix, 48000)
            if error():
                raise RuntimeError('OpenAL render failed')
            rms = [math.sqrt(sum(mix[i * channels + c] ** 2 for i in range(12000, 48000)) / 36000) for c in range(channels)]
            return {'rms': rms, 'center_routed': bool(use_center), 'mode': mode.value, 'hrtf_status': status.value,
                    'direct_mode': direct_mode if use_center else 0,
                    'pcm_sha256': hashlib.sha256(bytes(mix)).hexdigest()}
        finally:
            current(None); destroy(context); close(device)

    values = {name: measure(*params) for name, params in {
        'old_global_51': (6, 0), 'center_51': (6, 1), 'vo_51': (6, .75),
        'center_61': (7, 1), 'vo_61': (7, .75), 'center_71': (8, 1), 'vo_71': (8, .75),
        'quad_baseline': (4, 0), 'quad_center_request': (4, 1),
        'stereo_baseline': (2, 0), 'stereo_center_request': (2, 1),
        'hrtf_baseline': (2, 0, True), 'hrtf_center_request': (2, 1, True),
    }.items()}
    center = values['center_51']['rms']
    vo = values['vo_51']['rms']
    checks.update(
        exclusive_physical_center=center[2] > .08 and max(center[:2] + center[3:]) < 1e-8,
        vo_center_fraction=abs(vo[2] / center[2] - .75) < .001,
        vo_center_dominates=vo[2] > max(vo[:2] + vo[3:]),
        vo_unit_power=abs(sum(v * v for v in vo) / sum(v * v for v in center) - 1) < .001,
        stereo_pcm_unchanged=values['stereo_baseline']['pcm_sha256'] == values['stereo_center_request']['pcm_sha256'],
        hrtf_active=values['hrtf_baseline']['hrtf_status'] == 1,
        hrtf_pcm_unchanged=values['hrtf_baseline']['pcm_sha256'] == values['hrtf_center_request']['pcm_sha256'],
        quad_pcm_unchanged=values['quad_baseline']['pcm_sha256'] == values['quad_center_request']['pcm_sha256'],
    )
    for layout in ['61', '71']:
        exclusive, partial = values[f'center_{layout}']['rms'], values[f'vo_{layout}']['rms']
        checks[f'exclusive_center_{layout}'] = exclusive[2] > .08 and max(exclusive[:2] + exclusive[3:]) < 1e-8
        checks[f'vo_fraction_{layout}'] = abs(partial[2] / exclusive[2] - .75) < .001
        checks[f'vo_no_lfe_{layout}'] = partial[3] == 0
        checks[f'vo_unit_power_{layout}'] = abs(sum(v * v for v in partial) / sum(v * v for v in exclusive) - 1) < .001
    report = {'checks': checks, 'values': values, 'passed': all(checks.values()),
              'physical_device': False, 'provider_sha256': hashlib.sha256(library.read_bytes()).hexdigest(),
              'routing_sha256': hashlib.sha256((ROOT / 'src/sound/SoundSurround.h').read_bytes()).hexdigest()}
    report['harness_sha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
