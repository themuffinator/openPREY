#!/usr/bin/env python3
"""Execute the production voice rate/fragment gate with deterministic channel debt."""
from pathlib import Path
import os
import subprocess
from sound_settings import body

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = (ROOT / 'src/framework/async/MsgChannel.cpp').read_text()
    production = body(source, 'bool idMsgChannel::CanSendUnfragmented(')
    production += body(source, 'bool idMsgChannel::ReadyToSend(')
    harness = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <limits>
using int64=int64_t;
template<class T> T Max(T a,T b){return std::max(a,b);}
struct idMath {static int ClampInt(int a,int b,int c){return std::clamp(c,a,b);}};
int Net_FragmentSize(int){return 1300;}
struct Reliable {int size=0; int GetTotalSize()const{return size;}};
struct idMsgChannel {
    Reliable reliableSend; int remoteAddress=0,maxRate=128000,lastSendTime=1000,lastDataBytes=0;
    bool unsentFragments=false;
    bool ReadyToSend(int) const;
    bool CanSendUnfragmented(int,int,int burstMsec=0) const;
};
@PRODUCTION@
int main(){
    idMsgChannel channel;
    assert(channel.CanSendUnfragmented(1000,200));
    channel.lastDataBytes=800; // this frame's gameplay snapshot was charged first
    assert(!channel.CanSendUnfragmented(1000,200));
    assert(channel.CanSendUnfragmented(1000,200,20));
    channel.maxRate=2000;
    assert(!channel.CanSendUnfragmented(1000,200,20));
    assert(!channel.CanSendUnfragmented(5000,200,20)); // expired debt does not admit a rate burst
    channel.maxRate=50000; channel.lastDataBytes=800;
    assert(!channel.CanSendUnfragmented(1000,200,20));
    assert(channel.CanSendUnfragmented(1001,200,20));
    assert(!channel.CanSendUnfragmented(1000,200,2000)); // caller cannot enlarge the 20 ms burst
    channel.lastDataBytes=0; channel.reliableSend.size=1100;
    assert(!channel.CanSendUnfragmented(2000,200,20)); // never fragments behind reliable backlog
    channel.reliableSend.size=0; channel.unsentFragments=true;
    assert(!channel.CanSendUnfragmented(2000,200,20));
    channel.unsentFragments=false; channel.maxRate=0;
    assert(channel.CanSendUnfragmented(1000,200,20));
    assert(!channel.CanSendUnfragmented(1000,-1,20));
    assert(!channel.CanSendUnfragmented(1000,1292,20));
    assert(channel.CanSendUnfragmented(1000,1291,20));
    assert(!channel.CanSendUnfragmented(1000,std::numeric_limits<int>::max(),20));
    std::puts("PASS: voice debt cap, bounded burst, reliable backlog, fragmentation and malformed size gates");
}
'''.replace('@PRODUCTION@', production)
    scratch = ROOT / '.tmp/audio/voice-transport'
    scratch.mkdir(parents=True, exist_ok=True)
    cpp, exe = scratch / 'test.cpp', scratch / ('test.exe' if os.name == 'nt' else 'test')
    cpp.write_text(harness)
    subprocess.run([os.environ.get('CXX', 'clang++'), '-std=c++20', '-Wall', '-Wextra', '-Werror', str(cpp), '-o', str(exe)], cwd=scratch, check=True)
    subprocess.run([str(exe)], cwd=scratch, check=True)


if __name__ == '__main__':
    main()
