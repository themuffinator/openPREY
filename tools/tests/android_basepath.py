#!/usr/bin/env python3
"""Run the production base-path selection with Android and desktop hosts."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from filesystem_case_segments import function_body

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = r'''
#include <cstdio>
#include <stdexcept>
#include <string>
PLATFORM
static void require(bool value,const char* message) { if(!value)throw std::runtime_error(message); }
struct idStr: std::string { using std::string::operator=; };
struct Cvar {
    std::string value;
    const char* GetString() const { return value.c_str(); }
    void SetString(const char* text) { value=text; }
} fs_basepath;
struct Common { void Warning(const char*,...) {} void Printf(const char*,...) {} } commonStorage;
static Common* common=&commonStorage;
static const char* BASE_GAMEDIR="q4base";
static int discoveryCalls=0;
static bool discover=false;
static bool FS_HasGameFilesAtBasePath(const char* path) { return std::string(path)=="/retail"; }
static bool FS_AutoDiscoverBasePath(idStr& path) { ++discoveryCalls;path="/discovered";return discover; }
static const char* Sys_DefaultBasePath() { return "/"; }
'''
MAIN = r'''
int main() {
    try {
        fs_basepath.SetString("/retail");SelectBasePath();
        require(fs_basepath.value=="/retail" && !discoveryCalls,"valid host path changed");
        for(bool available: {false,true}) {
            discover=available;discoveryCalls=0;
            fs_basepath.SetString("/storage/emulated/0/Android/data/com.darkmatter.openq4/files");
            SelectBasePath();
#ifdef __ANDROID__
            require(fs_basepath.value=="/storage/emulated/0/Android/data/com.darkmatter.openq4/files",
                "missing Android retail media discarded the host's data folder");
            require(!discoveryCalls,"Android host path triggered desktop install discovery");
#else
            require(fs_basepath.value==(available ? "/discovered" : "/") && discoveryCalls==1,
                "desktop invalid-override discovery changed");
#endif
            discoveryCalls=0;fs_basepath.SetString("");SelectBasePath();
            require(fs_basepath.value==(available ? "/discovered" : "/") && discoveryCalls==1,
                "unset-path fallback changed");
        }
        std::puts("base-path selection passed");return 0;
    } catch(const std::exception& error) { std::fprintf(stderr,"%s\n",error.what());return 1; }
}
'''


def source(mode):
    initialization = function_body((ROOT/'src/framework/FileSystem.cpp').read_text(),
                                   'void idFileSystemLocal::Init(')
    # Execute the complete selection block with fake discovery, including the
    # fallback. Required-PK4 validation remains in the subsequent Startup call.
    start = initialization.index('\t// fs_basepath auto-discovery order:')
    end = initialization.index('\t// fs_homepath is the user-writable root;', start)
    return (SUPPORT.replace('PLATFORM', '#define __ANDROID__ 1' if mode == 'android' else '')
            + '\nstatic void SelectBasePath() {\n' + initialization[start:end] + '}\n' + MAIN)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--generate-native':
        Path(sys.argv[3]).write_text(source(sys.argv[2]), encoding='utf-8')
        return 0
    compiler = next((p for name in ('clang++', 'g++', 'c++') if (p := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError('C++17 compiler required')
    failures = 0
    with tempfile.TemporaryDirectory(prefix='android-basepath-', dir=ROOT/'.tmp') as directory:
        for mode in ('android', 'desktop'):
            cpp=Path(directory)/(mode+'.cpp'); exe=cpp.with_suffix('.exe')
            cpp.write_text(source(mode), encoding='utf-8')
            subprocess.run([compiler,'-std=c++17',str(cpp),'-o',str(exe)],check=True)
            print(mode,flush=True)
            failures += subprocess.run([str(exe)]).returncode != 0
    return int(failures != 0)


if __name__ == '__main__':
    raise SystemExit(main())
