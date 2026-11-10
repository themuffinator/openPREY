#!/usr/bin/env python3
"""Pin the r_resolutionScaleMode upscale of the game's below-native scene.

Single-player renders its scene into game-owned targets at the latched scene
extent and used to present them with a full-screen material, which can only
stretch bilinearly, so modes 2 (sharpened) and 3 (nearest-neighbour) changed
nothing in the campaign. The game now hands the final upscale to the renderer
through idRenderSystem::PresentScaledScene, which queues RC_PRESENT_SCALED_SCENE
for the OpenGL and Vulkan back ends.

The front end, the OpenGL presenter and the game's request helpers are
extracted from the real sources and compiled against counted doubles: no GPU,
window or game runs, so this proves routing, refusals, state restoration and
command contents, not pixels. Source mutations that must fail prove the checks
bite. The remaining call sites are pinned as source tokens.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8").replace("\r\n", "\n")


def require(text: str, token: str, context: str) -> None:
    if token not in text:
        raise AssertionError(f"{context}: missing {token!r}")


def function_body(source: str, signature: str) -> str:
    """The first definition starting with signature (declarations are skipped)."""
    position = 0
    while True:
        position = source.find(signature, position)
        if position < 0:
            raise AssertionError(f"Missing definition of {signature!r}")
        brace = source.index("{", position)
        if source.find(";", position, brace) < 0:
            break
        position += len(signature)
    depth = 0
    for index in range(brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[position:index + 1] + "\n"
    raise AssertionError(f"Unterminated definition of {signature!r}")


def struct_block(source: str, name: str) -> str:
    end = source.index(f"}} {name};") + len(f"}} {name};")
    start = source.rindex("typedef struct {", 0, end)
    return source[start:end] + "\n"


def replace_once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise AssertionError(f"mutation anchor not unique ({source.count(before)}): {before!r}")
    return source.replace(before, after, 1)


COMMON = r'''
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#define CHECK(x) do{++checks;if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";std::exit(1);}}while(false)
static int checks=0;
static std::vector<std::string> calls;
struct idMath {
 static int ClampInt(int lo,int hi,int v){return std::clamp(v,lo,hi);}
 static float ClampFloat(float lo,float hi,float v){return std::clamp(v,lo,hi);}
};
struct Cvar {double value=0;int GetInteger()const{return int(value);}float GetFloat()const{return float(value);}};
'''

FRONT_SUPPORT = r'''
static Cvar r_resolutionScaleMode{2},r_resolutionScaleSharpness{.4};
enum { RENDERER_CONTEXT_PROFILE_COMPATIBILITY, RENDERER_CONTEXT_PROFILE_CORE, RENDERER_CONTEXT_PROFILE_ES };
static struct {bool isInitialized=true;int vidWidth=1280,vidHeight=720;struct {int profile=RENDERER_CONTEXT_PROFILE_COMPATIBILITY;} backendCaps;} glConfig;
struct renderPresentationState_t {
 int frameNumber=7,outputWidth=1280,outputHeight=720,sceneWidth=640,sceneHeight=360,effectiveScalePercent=50;
};
struct idImage {struct Opts {int numMSAASamples=0;} opts;const Opts& GetOpts()const{return opts;}};
struct idRenderTexture {
 idImage* color=nullptr;int width=640,height=360;
 int GetNumColorImages()const{return color?1:0;}idImage* GetColorImage(int)const{return color;}
 int GetWidth()const{return width;}int GetHeight()const{return height;}
};
struct GuiModel {void EmitFullScreen(){calls.push_back("emit");}void Clear(){calls.push_back("clear");}};
enum renderCommand_t { RC_NOP, RC_PRESENT_SCALED_SCENE };
'''

FRONT_TAIL = r'''
alignas(16) static unsigned char commandStorage[512];
static void* R_GetCommandBuffer(int bytes){calls.push_back("command");std::memset(commandStorage,0xcd,sizeof(commandStorage));CHECK(bytes<=(int)sizeof(commandStorage));return commandStorage;}
static bool R_ScenePackets_FrontEndCaptureRequired(){return false;}
static void R_ScenePackets_AddRenderTargetOp(){}
static GuiModel guiModelObject;
struct idRenderSystemLocal {
 int tiledViewport[2]{};int frameCount=7;GuiModel* guiModel=&guiModelObject;renderPresentationState_t state;
 void GetPresentationState(renderPresentationState_t& out)const{out=state;}
 bool PresentScaledScene(idRenderTexture* sceneColorTarget);
};
static idRenderSystemLocal tr;
'''

FRONT_MAIN = r'''
static idImage image;
static idRenderTexture target;
static void Reset(){
 calls.clear();image={};target={};target.color=&image;tr.tiledViewport[0]=tr.tiledViewport[1]=0;tr.frameCount=7;tr.state={};
 glConfig={};r_resolutionScaleMode.value=2;r_resolutionScaleSharpness.value=.4;
}
static const presentScaledSceneCommand_t& Command(){return *reinterpret_cast<const presentScaledSceneCommand_t*>(commandStorage);}
static void Refused(const char* why){(void)why;CHECK(!tr.PresentScaledScene(&target));CHECK(calls.empty());}
int main(){
 for(int mode:{2,3}){
  Reset();r_resolutionScaleMode.value=mode;
  CHECK(tr.PresentScaledScene(&target));
  // the batched full-screen submissions are sealed before the command
  CHECK((calls==std::vector<std::string>{"emit","clear","command"}));
  CHECK(Command().commandId==RC_PRESENT_SCALED_SCENE);CHECK(Command().sceneColorTarget==&target);
  CHECK(Command().sceneWidth==640&&Command().sceneHeight==360);CHECK(Command().outputWidth==1280&&Command().outputHeight==720);
  CHECK(Command().mode==mode);CHECK(Command().sharpness>.39f&&Command().sharpness<.41f);
 }
 Reset();r_resolutionScaleMode.value=7;CHECK(tr.PresentScaledScene(&target));CHECK(Command().mode==3);
 Reset();r_resolutionScaleSharpness.value=4;CHECK(tr.PresentScaledScene(&target));CHECK(Command().sharpness==1.5f);
 Reset();r_resolutionScaleSharpness.value=-1;CHECK(tr.PresentScaledScene(&target));CHECK(Command().sharpness==0.f);
 // a dynamic-resolution or odd extent is fine while it stays below native
 Reset();tr.state.sceneWidth=1280;tr.state.sceneHeight=700;target.width=1280;target.height=700;CHECK(tr.PresentScaledScene(&target));
 for(int mode:{0,1,-4}){Reset();r_resolutionScaleMode.value=mode;Refused("bilinear modes keep the game's material");}
 Reset();CHECK(!tr.PresentScaledScene(nullptr));CHECK(calls.empty());
 Reset();glConfig.isInitialized=false;Refused("no device");
 Reset();glConfig.backendCaps.profile=RENDERER_CONTEXT_PROFILE_ES;Refused("ES crops inside the scene target");
 Reset();tr.tiledViewport[0]=2560;tr.tiledViewport[1]=1440;Refused("tiled capture");
 Reset();tr.frameCount=8;Refused("state latched for another frame");
 Reset();glConfig.vidWidth=1920;Refused("output is not the window");
 Reset();tr.state.sceneWidth=1280;tr.state.sceneHeight=720;target.width=1280;target.height=720;Refused("native scene");
 Reset();tr.state.sceneWidth=2560;tr.state.sceneHeight=1440;target.width=2560;target.height=1440;Refused("supersampled scene");
 Reset();tr.state.sceneWidth=1280;tr.state.sceneHeight=1440;target.width=1280;target.height=1440;Refused("taller than native");
 Reset();target.width=639;Refused("target is not the scene extent");
 Reset();target.height=361;Refused("target is not the scene extent");
 Reset();image.opts.numMSAASamples=4;Refused("multisampled target");
 Reset();target.color=nullptr;Refused("no colour image");
 std::cout<<"PASS front end "<<checks<<" checks\n";
}
'''

GL_SUPPORT = r'''
using GLint=int;using GLfloat=float;using GLhandleARB=unsigned;
constexpr int GL_TEXTURE_2D=1,GL_TEXTURE_MIN_FILTER=2,GL_TEXTURE_MAG_FILTER=3,GL_NEAREST=4,GL_LINEAR=5,GL_LINEAR_MIPMAP_LINEAR=6,GL_MODULATE=7;
static constexpr int RB_RESOLUTION_SCALE_MODE_SHARPEN=2,RB_RESOLUTION_SCALE_MODE_NEAREST=3;
enum {RB_RES_SCALE_UNIFORM_INV_TEX_SIZE,RB_RES_SCALE_UNIFORM_INV_LOW_RES_SIZE,RB_RES_SCALE_UNIFORM_SHARPEN_AMOUNT};
static int texMin=GL_LINEAR,texMag=GL_LINEAR,boundProgram=0,quads=0,quadMin=0,quadMag=0,quadProgram=-1;
static int viewport[4]{},quadExtent[4]{};
static float invLowRes[2]{},invTex[2]{},sharpen=-1;
static bool validShader=true;
static void glTexParameteri(int,int pname,int value){if(pname==GL_TEXTURE_MIN_FILTER)texMin=value;if(pname==GL_TEXTURE_MAG_FILTER)texMag=value;}
static void glGetTexParameteriv(int,int pname,GLint* value){*value=pname==GL_TEXTURE_MIN_FILTER?texMin:texMag;}
static void glUseProgramObjectARB(unsigned program){boundProgram=int(program);}
static void glUniform1iARB(int,int){}
static void glUniform2fvARB(int location,int,const GLfloat* v){if(location==0){invTex[0]=v[0];invTex[1]=v[1];}if(location==1){invLowRes[0]=v[0];invLowRes[1]=v[1];}}
static void glUniform1fARB(int location,GLfloat v){if(location==2)sharpen=v;}
static void glViewport(int x,int y,int w,int h){viewport[0]=x;viewport[1]=y;viewport[2]=w;viewport[3]=h;}
static void glScissor(int,int,int,int){}
static struct Shader {unsigned glslProgramObject=9;int shaderTextureLocations[1]{3};int shaderParmLocations[3]{0,1,2};} rbResolutionScaleStage;
static void RB_InitResolutionScaleStage(){}
static bool R_ValidateGLSLProgram(const Shader*){return validShader;}
static struct {bool GLSLProgramAvailable=true;} glConfig;
struct idScreenRect {int x1=0,y1=0,x2=0,y2=0;};
struct idImage {
 struct Opts {int width=640,height=360,numMSAASamples=0;} opts;
 const Opts& GetOpts()const{return opts;} void Bind(){calls.push_back("bind-scene");}
};
struct idRenderTexture {
 idImage* color=nullptr;bool current=true;
 int GetNumColorImages()const{return color?1:0;}idImage* GetColorImage(int)const{return color;}
 bool MakeCurrent(){return current;}
 static void BindNull(){calls.push_back("bind-default");}
};
static struct {idRenderTexture* renderTexture=nullptr;idRenderTexture* feedbackRenderTexture=nullptr;idScreenRect currentScissor;bool currentRenderCopied=true;} backEnd;
static void R_SetDefaultDrawAndReadBuffers(){}
static void RB_BeginFullscreenPostProcessPass(int,int,int,int){calls.push_back("begin-pass");}
static void RB_EndFullscreenPostProcessPass(){calls.push_back("end-pass");}
static void GL_SelectTexture(int){} static void GL_TexEnv(int){}
static void RB_SetFramebufferSRGBEnabled(bool){}
static void RB_DrawFullscreenPostProcessQuad(int w,int h,int tw,int th){
 ++quads;quadExtent[0]=w;quadExtent[1]=h;quadExtent[2]=tw;quadExtent[3]=th;quadMin=texMin;quadMag=texMag;quadProgram=boundProgram;calls.push_back("quad");}
static struct Images {void BindNull(){calls.push_back("unbind");}} imagesObject,*globalImages=&imagesObject;
static int printed=0;
static struct Common {template<class... T>void Printf(const char*,T...){++printed;}} commonObject,*common=&commonObject;
enum renderCommand_t { RC_NOP, RC_PRESENT_SCALED_SCENE };
'''

GL_MAIN = r'''
static idImage image;
static idRenderTexture target;
static presentScaledSceneCommand_t command;
static void Reset(int mode){
 calls.clear();image={};target={};target.color=&image;texMin=texMag=GL_LINEAR;boundProgram=0;quads=0;quadMin=quadMag=0;quadProgram=-1;
 sharpen=-1;validShader=true;glConfig.GLSLProgramAvailable=true;backEnd.renderTexture=&target;backEnd.currentRenderCopied=true;
 std::memset(&command,0,sizeof(command));command.commandId=RC_PRESENT_SCALED_SCENE;command.sceneColorTarget=&target;
 command.sceneWidth=640;command.sceneHeight=360;command.outputWidth=1280;command.outputHeight=720;command.mode=mode;command.sharpness=.7f;
}
int main(){
 // mode 2: the sharpen program with the command's snapshot, over the native output
 Reset(2);CHECK(RB_PresentScaledScene(command));CHECK(quads==1);CHECK(quadProgram==9);CHECK(boundProgram==0);
 CHECK(sharpen>.69f&&sharpen<.71f);CHECK(invLowRes[0]==1.f/640&&invLowRes[1]==1.f/360);CHECK(invTex[0]==1.f/640);
 CHECK(quadMin==GL_LINEAR&&quadMag==GL_LINEAR);CHECK(texMin==GL_LINEAR&&texMag==GL_LINEAR);
 CHECK(viewport[2]==1280&&viewport[3]==720);CHECK(quadExtent[0]==640&&quadExtent[1]==360&&quadExtent[2]==640&&quadExtent[3]==360);
 CHECK(backEnd.renderTexture==nullptr);CHECK(!backEnd.currentRenderCopied);
 CHECK((calls==std::vector<std::string>{"bind-default","begin-pass","bind-scene","quad","unbind","end-pass"}));
 // mode 2 without its program still fills the output, bilinear
 Reset(2);validShader=false;CHECK(RB_PresentScaledScene(command));CHECK(quads==1);CHECK(quadProgram==0);
 Reset(2);glConfig.GLSLProgramAvailable=false;CHECK(RB_PresentScaledScene(command));CHECK(quads==1);CHECK(quadProgram==0);
 // mode 3: nearest for the draw only; whatever filters the texture had come back
 for(int previous:{GL_LINEAR,GL_LINEAR_MIPMAP_LINEAR}){
  Reset(3);texMin=previous;texMag=GL_LINEAR;CHECK(RB_PresentScaledScene(command));
  CHECK(quadMin==GL_NEAREST&&quadMag==GL_NEAREST);CHECK(quadProgram==0);CHECK(texMin==previous&&texMag==GL_LINEAR);
 }
 // a texture larger than the scene is sampled over the scene's share only
 Reset(3);image.opts.width=1280;image.opts.height=720;CHECK(RB_PresentScaledScene(command));
 CHECK(quadExtent[0]==640&&quadExtent[1]==360&&quadExtent[2]==1280&&quadExtent[3]==720);
 // unusable targets draw nothing
 Reset(3);command.sceneColorTarget=nullptr;CHECK(!RB_PresentScaledScene(command));CHECK(quads==0);
 Reset(3);target.color=nullptr;CHECK(!RB_PresentScaledScene(command));CHECK(quads==0);
 Reset(3);image.opts.numMSAASamples=4;CHECK(!RB_PresentScaledScene(command));CHECK(quads==0);
 Reset(3);image.opts.width=320;CHECK(!RB_PresentScaledScene(command));CHECK(quads==0);
 Reset(2);command.sceneWidth=0;CHECK(!RB_PresentScaledScene(command));CHECK(quads==0);
 CHECK(texMin==GL_LINEAR&&texMag==GL_LINEAR);
 std::cout<<"PASS OpenGL presenter "<<checks<<" checks\n";
}
'''

GAME_SUPPORT = r'''
struct renderPresentationState_t {int outputWidth=1280,outputHeight=720,sceneWidth=640,sceneHeight=360;};
struct idRenderTexture {};
static int modeCvar=2,presentCalls=0;static bool rendererAccepts=true;
static struct {int GetCVarInteger(const char* name){CHECK(std::string(name)=="r_resolutionScaleMode");return modeCvar;}} cvarObject,*cvarSystem=&cvarObject;
static struct {bool PresentScaledScene(idRenderTexture*){++presentCalls;return rendererAccepts;}} renderObject,*renderSystem=&renderObject;
'''

GAME_MAIN = r'''
int main(){
 idRenderTexture target;renderPresentationState_t below;
 for(int mode:{2,3,9}){modeCvar=mode;presentCalls=0;rendererAccepts=true;
  CHECK(openQ4_ScaledScenePresentationRequested(below));CHECK(openQ4_PresentScaledScene(below,&target));CHECK(presentCalls==1);}
 modeCvar=3;presentCalls=0;rendererAccepts=false;CHECK(!openQ4_PresentScaledScene(below,&target));CHECK(presentCalls==1);
 rendererAccepts=true;
 for(int mode:{0,1,-1}){modeCvar=mode;presentCalls=0;
  CHECK(!openQ4_ScaledScenePresentationRequested(below));CHECK(!openQ4_PresentScaledScene(below,&target));CHECK(presentCalls==0);}
 modeCvar=2;presentCalls=0;
 renderPresentationState_t native;native.sceneWidth=1280;native.sceneHeight=720;
 CHECK(!openQ4_PresentScaledScene(native,&target));
 renderPresentationState_t super;super.sceneWidth=2560;super.sceneHeight=1440;
 CHECK(!openQ4_PresentScaledScene(super,&target));
 CHECK(!openQ4_PresentScaledScene(below,nullptr));CHECK(presentCalls==0);
 renderPresentationState_t narrow;narrow.sceneWidth=1280;narrow.sceneHeight=700;
 CHECK(openQ4_PresentScaledScene(narrow,&target));CHECK(presentCalls==1);
 std::cout<<"PASS game "<<checks<<" checks\n";
}
'''


def assemble_front(render_system: str, tr_local: str) -> str:
    return (COMMON + FRONT_SUPPORT + struct_block(tr_local, "presentScaledSceneCommand_t") + FRONT_TAIL
            + function_body(render_system, "bool idRenderSystemLocal::PresentScaledScene( idRenderTexture *sceneColorTarget )")
            + FRONT_MAIN)


def assemble_gl(draw: str, tr_local: str) -> str:
    signatures = (
        "static void RB_BeginNearestUpscale( GLint restoreFilters[2] )",
        "static void RB_EndNearestUpscale( const GLint restoreFilters[2] )",
        "static bool RB_BindResolutionScaleProgram( int sourceWidth, int sourceHeight,",
        "static idImage *RB_TemporalColorImage( const idRenderTexture *target )",
        "static bool RB_BindTemporalDestination( idRenderTexture *target, int width, int height )",
        "bool RB_PresentScaledScene( const presentScaledSceneCommand_t &command )",
    )
    return (COMMON + GL_SUPPORT + struct_block(tr_local, "presentScaledSceneCommand_t")
            + "".join(function_body(draw, s) for s in signatures) + GL_MAIN)


def assemble_game(game: str) -> str:
    signatures = (
        "static bool openQ4_ScaledScenePresentationRequested( const renderPresentationState_t &presentation )",
        "static bool openQ4_PresentScaledScene( const renderPresentationState_t &presentation,",
    )
    return COMMON + GAME_SUPPORT + "".join(function_body(game, s) for s in signatures) + GAME_MAIN


def check_sources(game: str, render_h: str, render_system: str, tr_backend: str, gles: str,
                  vk_backend: str, vk_exec: str, draw: str) -> None:
    scene = function_body(game, "void idGameLocal::RenderScene(const renderView_t *view, idRenderWorld *renderWorld,")
    fast = scene[scene.index("if ( canUseFastNoPost ) {"):scene.index("// Render the scene to the forward render pass rendertexture.")]
    require(fast, "if ( !openQ4_PresentScaledScene( presentation, gameRender.forwardRenderPassResolvedRT ) ) {\n"
            "\t\t\topenQ4_DrawFullScreenMaterial( gameRender.resolvePostProcessMaterial );", "fast no-post presentation")
    final = scene[scene.rindex("idRenderTexture *scaledSceneSource"):]
    require(final, "finalMaterial == gameRender.noPostProcessMaterial\n\t\t? gameRender.postProcessRT[0] : gameRender.postProcessRT[1];",
            "the no-post copy presents _postProcessAlbedo0 directly")
    require(final, "renderSystem->BindRenderTexture( scaledSceneSource, NULL );", "blur and CAS run at the scene extent first")
    if not (final.index("openQ4_ScaledScenePresentationRequested( presentation )")
            < final.index("renderSystem->ClearRenderTarget( false, true, 1.0f, 0.0f, 0.0f, 0.0f );")
            < final.index("if ( !openQ4_PresentScaledScene( presentation, scaledSceneSource ) ) {\n\t\topenQ4_DrawFullScreenMaterial( finalMaterial );")):
        raise AssertionError("final presentation: scene-extent pass, back-buffer depth clear, then the scaled present or the material")
    tail = render_h[render_h.index("virtual void\t\t\tGetVRFrameResult("):render_h.index("extern idRenderSystem *")]
    require(tail, "virtual bool\t\t\tPresentScaledScene( idRenderTexture *sceneColorTarget ) = 0;",
            "PresentScaledScene keeps its existing idRenderSystem slot")
    slots = re.findall(r"\bvirtual\b[^(]*?\b(\w+)\s*\(", tail)
    if slots[:3] != ["GetVRFrameResult", "PresentScaledScene", "BeginGuiRoot"]:
        raise AssertionError(f"renderer extensions must follow the existing scaled-presentation slot: {slots}")
    front = function_body(render_system, "bool idRenderSystemLocal::PresentScaledScene( idRenderTexture *sceneColorTarget )")
    if "#if" in front or "OPENQ4_RENDERER_VK_MODULE" in front:
        raise AssertionError("the front end must not decline a backend at compile time")
    require(tr_backend, "case RC_PRESENT_SCALED_SCENE:", "OpenGL dispatch")
    require(tr_backend, "RB_PresentScaledScene( *reinterpret_cast<const presentScaledSceneCommand_t *>( cmds ) );", "OpenGL dispatch")
    stub = function_body(gles, "bool RB_PresentScaledScene( const presentScaledSceneCommand_t &command )")
    require(stub, "return false;", "the ES module links a presenter the front end never feeds")
    require(vk_backend, "case RC_PRESENT_SCALED_SCENE:", "Vulkan dispatch")
    require(vk_backend, "VK_GuiExecutor_PresentScaledScene(\n\t\t\t\t\t*reinterpret_cast<const presentScaledSceneCommand_t *>( cmds ) );", "Vulkan dispatch")
    vk = function_body(vk_exec, "bool VK_GuiExecutor_PresentScaledScene( const presentScaledSceneCommand_t &command )")
    require(vk, "VK_TemporalPresentation_PresentScaledImage( sceneImage, sceneEntry,\n\t\t\t\tcommand.mode, command.sharpness )",
            "Vulkan presents with the queued mode and sharpness")
    require(vk, "sceneEntry->width == command.sceneWidth", "Vulkan only scales the latched scene extent")
    require(vk, "return VK_TemporalPresentation_DrawResolve( NULL, sceneImage, sceneEntry,", "Vulkan falls back to the bilinear present")
    owned = function_body(vk_exec, "static bool VK_TemporalPresentation_DrawScaledScene( const viewDef_t *viewDef,")
    require(owned, "mode, r_resolutionScaleSharpness.GetFloat() );", "the renderer-owned Vulkan scene keeps the live sharpness")
    present = function_body(draw, "static void RB_PresentSceneRenderTargetToBackBuffer( const rbSceneScaleState_t &scaleState )")
    require(present, "== RB_RESOLUTION_SCALE_MODE_NEAREST;", "the renderer-owned OpenGL scene takes mode 3 too")


def compile_and_run(compiler: str, output: Path, name: str, source: str, env: dict) -> subprocess.CompletedProcess:
    cpp, exe = output / f"{name}.cpp", output / f"{name}.exe"
    cpp.write_text(source, encoding="utf-8")
    build = subprocess.run([compiler, "-std=c++17", str(cpp), "-o", str(exe)], env=env, capture_output=True, text=True)
    (output / f"{name}-compile.log").write_text(build.stdout + build.stderr, encoding="utf-8")
    if build.returncode:
        raise AssertionError(f"{name} failed to compile; see {output}")
    return subprocess.run([str(exe)], env=env, capture_output=True, text=True)


def main() -> None:
    game = read("src/game/Game_render.cpp")
    render_h = read("src/renderer/RenderSystem.h")
    render_system = read("src/renderer/RenderSystem.cpp")
    tr_local = read("src/renderer/tr_local.h")
    tr_backend = read("src/renderer/tr_backend.cpp")
    gles = read("src/renderer/GLES/gles_Backend.cpp")
    vk_backend = read("src/renderer/Vulkan/vk_Backend.cpp")
    vk_exec = read("src/renderer/Vulkan/vk_GuiExecutor.cpp")
    draw = read("src/renderer/draw_common.cpp")
    check_sources(game, render_h, render_system, tr_backend, gles, vk_backend, vk_exec, draw)

    front = assemble_front(render_system, tr_local)
    gl = assemble_gl(draw, tr_local)
    game_code = assemble_game(game)
    variants = {
        "front-production": front,
        "front-mutant-bilinear-modes": replace_once(front, "|| ( mode != 2 && mode != 3 )", "|| false"),
        "front-mutant-es": replace_once(front, "|| glConfig.backendCaps.profile == RENDERER_CONTEXT_PROFILE_ES", "|| false"),
        "front-mutant-native": replace_once(front, "|| ( presentation.sceneWidth == presentation.outputWidth\n\t\t\t\t&& presentation.sceneHeight == presentation.outputHeight )", "|| false"),
        "front-mutant-msaa": replace_once(front, "|| sceneColor == NULL || sceneColor->GetOpts().numMSAASamples > 1", "|| sceneColor == NULL"),
        "front-mutant-unsealed": replace_once(front, "\t\tguiModel->EmitFullScreen();\n", ""),
        "gl-production": gl,
        "gl-mutant-keep-nearest": replace_once(gl, "\tif ( nearest ) {\n\t\tRB_EndNearestUpscale( nearestRestore );\n\t}\n", ""),
        "gl-mutant-live-sharpness": replace_once(gl, "textureWidth, textureHeight, command.sharpness );", "textureWidth, textureHeight, 0.4f );"),
        "gl-mutant-msaa": replace_once(gl, "|| sceneImage->GetOpts().numMSAASamples > 1\n", "\n"),
        "game-production": game_code,
        "game-mutant-any-mode": replace_once(game_code, "return mode == 2 || mode == 3;", "return true;"),
    }
    if len(set(variants.values())) != len(variants):
        raise AssertionError("ineffective production mutation")
    compiler = next((found for name in ("clang++", "g++", "c++") if (found := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError("C++ compiler required")
    (ROOT / ".tmp").mkdir(exist_ok=True)
    output = Path(tempfile.mkdtemp(prefix="scaled-scene-presentation-", dir=ROOT / ".tmp"))
    env = dict(os.environ, TEMP=str(output), TMP=str(output), TMPDIR=str(output))
    passed = []
    for name, source in variants.items():
        run = compile_and_run(compiler, output, name, source, env)
        (output / f"{name}-run.log").write_text(run.stdout + run.stderr, encoding="utf-8")
        production = name.endswith("production")
        if (run.returncode == 0) != production:
            raise AssertionError(f"{name} returned {run.returncode}; see {output}")
        if production:
            passed.append(run.stdout.strip())
    shutil.rmtree(output, ignore_errors=True)
    for line in passed:
        print(line)
    print(f"renderer_scaled_scene_presentation: ok ({len(variants) - len(passed)} source mutations rejected)")


if __name__ == "__main__":
    main()
