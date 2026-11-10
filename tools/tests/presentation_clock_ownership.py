#!/usr/bin/env python3
"""Execute production scheduler methods and SP/MP/network timestamp boundaries."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def definition(text, name):
    match = re.search(r'\b(?:int|float)\s+' + re.escape(name) + r'\([^;{}]*\)\s*const\s*\{', text)
    if not match:
        raise RuntimeError('Missing production clock definition: ' + name)
    start = text.index('{', match.start())
    depth = 1
    end = start + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end]


def main():
    compiler = next((shutil.which(c) for c in ('clang++', 'g++', 'c++') if shutil.which(c)), None)
    if not compiler:
        raise RuntimeError('Executable clock coverage requires a C++ compiler')
    header = (ROOT / 'src/framework/Common.h').read_text(encoding='utf-8')
    common = (ROOT / 'src/framework/Common.cpp').read_text(encoding='utf-8')
    usercmd = (ROOT / 'src/framework/UsercmdGen.h').read_text(encoding='utf-8')
    constants = '\n'.join(re.findall(r'const int USERCMD_(?:HZ|MSEC)\s*=.*?;', usercmd))
    assert len(constants.splitlines()) == 2
    methods = '\n'.join(definition(header, name) for name in (
        'GetUserCmdTime', 'GetUserCmdDeltaMsec', 'GetUserCmdMsecNumerator', 'GetUserCmdMsecDenominator'))
    methods += '\n' + '\n'.join(definition(common, 'idCommonLocal::' + name).replace('idCommonLocal::', '')
                                 for name in ('GetUserCmdHz', 'GetUserCmdMSec'))
    sp = (ROOT / 'src/game/Game_local.cpp').read_text(encoding='utf-8')
    mp = (ROOT / 'src/mpgame/Game_local.cpp').read_text(encoding='utf-8')
    server = (ROOT / 'src/framework/async/AsyncServer.cpp').read_text(encoding='utf-8')
    sp_step = re.search(r'const int frameMsec = GetMSec\(\);\s*time \+= frameMsec;', sp).group()
    mp_step = re.search(r'time \+= GetMSec\(\);', mp).group()
    network_step = re.search(r'gameTime = gameFrame \* common->GetUserCmdMSec\(\);', server).group()
    source = r'''
#include <cstdio>
#include <cstdlib>
CHECK_CONSTANTS
struct Common { CHECK_METHODS };
struct Game { int time=0, step=16; int GetMSec() const { return step; }
  void SP() { SP_STEP } void MP() { MP_STEP } };
#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "line %d: %s\n", __LINE__, #x); std::exit(1); } } while(0)
int main() {
  Common owner; Common *common=&owner; Game sp,mp;
  CHECK(owner.GetUserCmdTime(-1)==0 && owner.GetUserCmdTime(0)==0);
  CHECK(owner.GetUserCmdMSec()==16 && owner.GetUserCmdHz()==60);
  for(int gameFrame=1;gameFrame<=1000000;++gameFrame) {
    sp.SP(); mp.MP(); int gameTime; NETWORK_STEP
    CHECK(gameTime==sp.time && gameTime==mp.time && gameTime==gameFrame*16);
    CHECK(owner.GetUserCmdTime(gameFrame)==static_cast<long long>(gameFrame)*1000/60);
    const int delta=owner.GetUserCmdDeltaMsec(gameFrame); CHECK(delta==16 || delta==17);
  }
  sp.step=8; const int before=sp.time; sp.SP(); CHECK(sp.time==before+8);
  std::puts("production scheduler/SP/MP/network clocks: one million ticks agree");
}
'''
    for marker, value in [('CHECK_CONSTANTS', constants), ('CHECK_METHODS', methods),
                          ('SP_STEP', sp_step), ('MP_STEP', mp_step), ('NETWORK_STEP', network_step)]:
        source = source.replace(marker, value)
    temporary = ROOT / '.tmp/clock-ownership'
    temporary.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temporary) as directory:
        path = Path(directory)
        (path / 'clock.cpp').write_text(source, encoding='utf-8')
        executable = path / 'clock.exe'
        subprocess.run([compiler, '-std=c++17', '-O2', str(path / 'clock.cpp'), '-o', str(executable)],
                       cwd=ROOT, check=True)
        subprocess.run([str(executable)], cwd=ROOT, check=True)


if __name__ == '__main__':
    main()
