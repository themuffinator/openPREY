#!/usr/bin/env python3
"""Exercise production splash/fatal-window ownership against SDL's one-window rule.

This uses an in-memory window API, never desktop capture or device input. Both
Android and desktop branches run; an actual Android APK still needs device tests.
"""
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
struct Window {};
struct Renderer {};
static Window storage;
static Renderer renderer;
static Window* live=nullptr;
static Window* s_sdlWindow=nullptr;
static int creates=0, destroyed=0, hidden=0, retired=0, stoppedText=0, unbound=0, restoredMode=0;
static constexpr int SDL_WINDOW_HIDDEN=1, SDL_WINDOW_BORDERLESS=2, SDL_INIT_VIDEO=4;
static constexpr int SDL_WINDOWPOS_CENTERED=0;
static constexpr int POSIX_SPLASH_WIDTH=640, POSIX_SPLASH_HEIGHT=480;
static const char* GAME_NAME="openQ4";
struct Splash {
    Window* window=nullptr;
    Renderer* renderer=nullptr;
    bool createFailed=false, videoInitializedBySplash=false;
    unsigned windowID=0;
} s_splashWindow;
static void require(bool value,const char* message) { if(!value)throw std::runtime_error(message); }
static Window* SDL_CreateWindow(const char*,int,int,int) {
    if(live)return nullptr;
    ++creates; return live=&storage;
}
static void SDL_DestroyWindow(Window* window) {
    require(window && window==live,"destroyed an unowned window");
    ++destroyed;live=nullptr;
}
static void SDL_HideWindow(Window* window) { require(window==live,"hid an unowned window");++hidden; }
static bool SDL_StopTextInput(Window* window) { require(window==live,"stopped input on dead window");++stoppedText;return true; }
static bool SDL_GL_MakeCurrent(Window* window,void*) { require(window==live,"unbound dead window");++unbound;return true; }
static void SDL3_RetireNativeWindowPublication() { require(s_sdlWindow==live && live,"retired after destruction");++retired; }
static bool SDL3_LeaveFullscreenAndRestoreDesktopMode() { ++restoredMode;return true; }
static unsigned SDL_GetWindowID(Window*) { return 1; }
static const char* SDL_GetError() { return "one window only"; }
static void SDL_QuitSubSystem(int) {}
static void SDL_ShowWindow(Window*) {}
static void SDL_RaiseWindow(Window*) {}
static void SDL_SetWindowPosition(Window*,int,int) {}
static void SDL_PumpEvents() {}
static void Sys_Printf(const char*,...) {}
static bool Posix_SplashEnsureVideo() { return true; }
static Renderer* Posix_CreateSupportRenderer(Window*,const char*) { return &renderer; }
static bool Posix_SplashLoadTexture() { return true; }
static void Posix_SplashRender() {}
static void Posix_SplashDestroy() {
    if(s_splashWindow.window)SDL_DestroyWindow(s_splashWindow.window);
    s_splashWindow=Splash{};
}
#define USE_SDL3 1
PLATFORM
'''
MAIN = r'''
int main() {
    try {
        Sys_ShowSplash();
#ifdef __ANDROID__
        // The host Activity provides the launch screen. The engine must leave
        // SDL's only window slot available for the game context.
        require(live==nullptr && creates==0,"startup splash consumed Android's game window");
#else
        require(live && creates==1,"desktop splash no longer opens");
        Posix_SplashDestroy();
#endif
        s_sdlWindow=SDL_CreateWindow("game",1280,720,0);
        require(s_sdlWindow!=nullptr,"game window could not open");
        Sys_SDL_EmergencyReleaseGameWindow();
#ifdef __ANDROID__
        require(!live && !s_sdlWindow,"fatal console cannot acquire Android's single window");
        require(stoppedText==1 && unbound==1 && retired==1 && restoredMode==0 && hidden==0,"wrong Android retirement sequence");
        Sys_SDL_EmergencyReleaseGameWindow();
        require(destroyed==1,"repeated release destroyed a window twice");
        Window* fatal=SDL_CreateWindow("fatal",640,480,0);
        require(fatal!=nullptr,"fatal window could not open");
        SDL_DestroyWindow(fatal);
#else
        require(live && s_sdlWindow==live && hidden==1 && restoredMode==1,"desktop emergency hide changed");
        require(!stoppedText && !unbound && !retired,"Android-only release reached desktop");
        SDL_DestroyWindow(s_sdlWindow);s_sdlWindow=nullptr;
#endif
        std::puts("splash/game/fatal window ownership passed");return 0;
    } catch(const std::exception& error) { std::fprintf(stderr,"%s\n",error.what());return 1; }
}
'''


def source(mode):
    console = (ROOT/'src/sys/posix/posix_syscon.cpp').read_text()
    backend = (ROOT/'src/sys/sdl3/sdl3_backend.cpp').read_text()
    return (SUPPORT.replace('PLATFORM', '#define __ANDROID__ 1' if mode == 'android' else '')
            + function_body(console, 'void Sys_ShowSplash(')+'\n'
            + function_body(backend, 'void Sys_SDL_EmergencyReleaseGameWindow(')+'\n'+MAIN)


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--generate-native':
        Path(sys.argv[3]).write_text(source(sys.argv[2]), encoding='utf-8')
        return 0
    compiler = next((p for name in ('clang++', 'g++', 'c++') if (p := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError('C++17 compiler required')
    failures = 0
    with tempfile.TemporaryDirectory(prefix='android-windows-', dir=ROOT/'.tmp') as directory:
        for mode in ('android', 'desktop'):
            cpp=Path(directory)/(mode+'.cpp'); exe=cpp.with_suffix('.exe')
            cpp.write_text(source(mode), encoding='utf-8')
            subprocess.run([compiler,'-std=c++17',str(cpp),'-o',str(exe)],check=True)
            print(mode,flush=True)
            failures += subprocess.run([str(exe)]).returncode != 0
    return int(failures != 0)


if __name__ == '__main__':
    raise SystemExit(main())
