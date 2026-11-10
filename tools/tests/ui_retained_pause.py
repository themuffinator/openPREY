#!/usr/bin/env python3
"""Compile the production paused-scene path against a renderer recorder."""
from pathlib import Path
import shutil
import subprocess
import tempfile

from filesystem_case_segments import function_body

ROOT = Path(__file__).resolve().parents[2]


def clock_fixture():
    source = (ROOT / 'src/game/Game_local.cpp').read_text(encoding='utf-8')
    constants = '\n'.join(line for line in source.splitlines()
        if line.startswith('static const ') and ('PRESENTATION_CLOCK_MAX_CATCHUP_TICS' in line or 'PRESENTATION_CLOCK_MAX_LATE_CORRECTION_MSEC' in line))
    declarations = r'''
#include <cassert>
#include <cstdio>
#include <cmath>
#include "src/framework/PresentationClock.h"
template<class T>T Min(T a,T b){return a<b?a:b;}
template<class T>T Max(T a,T b){return a>b?a:b;}
struct idMath {
    static int Ftoi(float n){return int(n);}
    static int ClampInt(int lo,int hi,int n){return Max(lo,Min(hi,n));}
    static float ClampFloat(float lo,float hi,float n){return Max(lo,Min(hi,n));}
};
struct {int GetUserCmdHz()const{return 60;}} commonObject;
auto* common=&commonObject;
struct {bool value=false;bool GetBool()const{return value;}} g_stopTime;
double realTime=1000;
struct Clock { double GetClockTicks()const{return realTime;} double ClockTicksPerSecond()const{return 1000;} } clockSource;
struct idLib {static Clock* sys;}; Clock* idLib::sys=&clockSource;
enum {DEMO_PLAYING=1};
struct idGameLocal {
    bool isMultiplayer=false,presentationMenuPaused=false,demo=false,timedemo=false;
    int time=100,presentationAnimationTime=-1;
    float presentationSceneFraction=-1;
    mutable openq4::PresentationClock presentationClock;
    float presentationClockSample=-1;
    int GetMSec()const{return 16;}
    int GetDemoState()const{return demo?DEMO_PLAYING:0;}
    bool IsTimeDemo()const{return timedemo;}
    float GetPresentationTicFraction()const;
    float GetPresentationInterpolationFraction()const;
    int GetPresentationTimeMsec()const;
    void EndPresentationSceneForRender();
};
'''
    bodies = '\n'.join(function_body(source, signature) for signature in (
        'float idGameLocal::GetPresentationTicFraction(', 'float idGameLocal::GetPresentationInterpolationFraction(',
        'int idGameLocal::GetPresentationTimeMsec(', 'void idGameLocal::EndPresentationSceneForRender('))
    return declarations + constants + '\n' + bodies + r'''
int main(){
    idGameLocal game;
    assert(game.GetPresentationTicFraction()==0);
    realTime+=1000.0/120;assert(game.GetPresentationTicFraction()==.5f);
    game.presentationMenuPaused=true;
    // A long ordinary pause must never periodically re-anchor at fraction zero,
    // move the camera backwards or invalidate an otherwise unchanged scene.
    for(int i=0;i<1000;++i){
        realTime+=13;
        assert(game.GetPresentationTicFraction()==1 && game.GetPresentationInterpolationFraction()==1);
        assert(game.GetPresentationTimeMsec()==game.time);
    }
    game.EndPresentationSceneForRender();assert(!game.presentationMenuPaused);
    assert(game.GetPresentationTicFraction()==0);
    realTime+=1000.0/120;assert(game.GetPresentationTicFraction()==.5f && game.GetPresentationTimeMsec()==108);
    game.time+=16;realTime+=1000.0/120;assert(game.GetPresentationTicFraction()==0);
    g_stopTime.value=true;assert(game.GetPresentationTicFraction()==1 && game.GetPresentationTimeMsec()==116);
    // Multiplayer keeps its running simulation/presentation clock even if a
    // caller supplies the pause hint or the single-player diagnostic stop flag.
    game.isMultiplayer=true;game.presentationMenuPaused=true;
    assert(game.GetPresentationTicFraction()==0);realTime+=1000.0/120;assert(game.GetPresentationTicFraction()==.5f);
    game.demo=true;assert(game.GetPresentationTimeMsec()==116 && game.GetPresentationInterpolationFraction()==1);
    game.demo=false;game.presentationMenuPaused=false;
    game.presentationClockSample=game.GetPresentationTicFraction();
    const float frozen=game.presentationClockSample;
    const int materialTime=game.GetPresentationTimeMsec();
    realTime+=2.125;
    assert(game.GetPresentationTicFraction()==frozen && game.GetPresentationTimeMsec()==materialTime);
    game.EndPresentationSceneForRender();assert(game.presentationClockSample<0);
    std::puts("retained pause: long menu pause holds the authoritative scene clock; resume, stop-time, multiplayer and demo contracts passed");
}
'''


def main():
    source = (ROOT / 'src/game/PlayerView.cpp').read_text(encoding='utf-8')
    body = function_body(source, 'bool idPlayerView::CanReusePausedScene(') + '\n' + function_body(source, 'void idPlayerView::DrawPausedScene(')
    support = r'''
#include <cassert>
#include <cstdio>
enum { RF_NO_GUI=1, RF_PRIMARY_VIEW=2, FMT_RGBA8, TF_NEAREST };
struct idUserInterface {};
struct renderView_t { int vieworg=0,viewaxis=0,x=0,y=0,width=640,height=480; float fov_x=90,fov_y=60; };
struct renderPresentationState_t {int frameNumber=0;};
struct idImageOpts {int width=0,height=0,format=0,numLevels=0;bool isPersistant=false;};
struct {int time=100;} gameLocal;
struct {bool enabled=true;bool GetBool()const{return enabled;}} ui_retainedPauseCache;
struct {int FindMaterial(const char*)const{return 1;}} declarations;
auto* declManager=&declarations;
struct Renderer {
    int width=1280,height=720,generation=1,frame=1,captures=0,draws=0;
    bool uiViewport=true,allocation=true;
    int GetScreenWidth()const{return width;} int GetScreenHeight()const{return height;}
    int GetVideoRestartCount()const{return generation;}
    void GetPresentationState(renderPresentationState_t& state)const{state.frameNumber=frame;}
    bool GetUseUIViewportFor2D()const{return uiViewport;}
    void SetUseUIViewportFor2D(bool value){uiViewport=value;}
    void SetColor4(float r,float g,float b,float a){assert(r==1&&g==1&&b==1&&a==1);}
    void DrawStretchPic(float x,float y,float w,float h,float s0,float t0,float s1,float t1,int material){
        assert(!uiViewport && x==0 && y==0 && w==640 && h==480 && s0==0 && t0==1 && s1==1 && t1==0 && material==1);++draws;
    }
    void* CreateImage(const char*,const idImageOpts* options,int filter){
        assert(options->width==width && options->height==height && options->format==FMT_RGBA8 &&
            options->numLevels==1 && options->isPersistant && filter==TF_NEAREST);
        return allocation ? this : nullptr;
    }
    void CaptureRenderToImage(const char*){++captures;}
} renderer;
auto* renderSystem=&renderer;
struct idPlayerView {
    bool pauseSceneValid=false;
    int pauseSceneWidth=0,pauseSceneHeight=0,pauseSceneGeneration=-1,pauseSceneTime=-1,pauseSceneFrame=-1;
    renderView_t pauseSceneView{};
    int scenes=0;
    void SingleView(idUserInterface*,const renderView_t*,int flags){assert(flags==(RF_NO_GUI|RF_PRIMARY_VIEW));++scenes;}
    void DrawPausedScene(idUserInterface*,const renderView_t*,bool);
    bool CanReusePausedScene(const renderView_t*)const;
};
'''
    support += body + r'''
int main(){
    idPlayerView player;renderView_t view;
    auto draw=[&](bool paused=true){++renderer.frame;player.DrawPausedScene(nullptr,&view,paused);assert(renderer.uiViewport);};
    draw();assert(player.scenes==1 && renderer.captures==0 && renderer.draws==0 && !player.CanReusePausedScene(&view));
    player.DrawPausedScene(nullptr,&view,true); // Repeated draw in one frame is not stability.
    assert(player.scenes==2 && renderer.captures==0);
    draw();assert(player.scenes==3 && renderer.captures==1 && renderer.draws==0 && player.CanReusePausedScene(&view));
    assert(!player.CanReusePausedScene(nullptr));
    for(int i=0;i<20;++i)draw();
    assert(player.scenes==3 && renderer.captures==1 && renderer.draws==20);
    draw(false);assert(player.scenes==4 && !player.pauseSceneValid);
    auto invalidates=[&]{assert(!player.CanReusePausedScene(&view));const auto count=renderer.captures;draw();assert(renderer.captures==count);draw();assert(renderer.captures==count+1);draw();assert(renderer.captures==count+1 && player.CanReusePausedScene(&view));};
    invalidates();
    ++renderer.generation;invalidates();
    renderer.width=1920;renderer.height=1080;invalidates();
    ++gameLocal.time;invalidates();
    ++view.vieworg;invalidates();++view.viewaxis;invalidates();++view.fov_x;invalidates();
    ++view.width;invalidates();++view.y;invalidates();
    renderer.frame+=10;invalidates(); // A settings page interrupted this view.
    ui_retainedPauseCache.enabled=false;draw();assert(!player.pauseSceneValid);
    ui_retainedPauseCache.enabled=true;invalidates();
    renderer.allocation=false;++renderer.generation;
    const auto captures=renderer.captures,scenes=player.scenes;
    draw();draw();assert(!player.pauseSceneValid && renderer.captures==captures && player.scenes==scenes+2);
    renderer.allocation=true;invalidates();
    renderer.width=0;draw();assert(!player.pauseSceneValid);
    std::puts("retained pause: scene reuse, resume, video restart, resize, time/view changes, interrupted presentation and allocation fallback passed");
}
'''
    compiler = next((path for name in ('clang++', 'g++', 'c++') if (path := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError('C++ compiler required')
    (ROOT / '.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ui-pause-', dir=ROOT / '.tmp') as folder:
        cpp, binary = Path(folder) / 'pause.cpp', Path(folder) / 'pause.exe'
        cpp.write_text(support, encoding='utf-8')
        subprocess.run([compiler, '-std=c++17', '-I', str(ROOT), str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
        cpp, binary = Path(folder) / 'clock.cpp', Path(folder) / 'clock.exe'
        cpp.write_text(clock_fixture(), encoding='utf-8')
        subprocess.run([compiler, '-std=c++17', '-I', str(ROOT), str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
