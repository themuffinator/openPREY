// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include <cmath>
#include <deque>
#include <cstdio>
#include <limits>
#include <stdexcept>
#include <string>
struct Value {
    float v=0;
    Value& operator=(float f) {v=f;return *this;}
    operator float() const {return v;}
    void Zero() {v=0;}
    void Bind(Value&,int) {}
};
struct idVec4 : Value { idVec4(float,float,float,float) {} };
struct Rect {float x=0,y=0,w=0,h=0;};
static bool OpenQ4_IsFiniteSaveGameRectangle(const Rect& r) {
    return std::isfinite(r.x)&&std::isfinite(r.y)&&std::isfinite(r.w)&&std::isfinite(r.h);
}
static bool OpenQ4_IsFiniteSaveGameVec2(const Value& v) {return std::isfinite(v.v);}
struct Common {[[noreturn]] void Error(const char*,...) {throw std::runtime_error("rejected layout");}} commonObject;
static auto* common=&commonObject;
struct GUI {const char* GetSourceFile() const{return "offscreen-terminal.gui";}} guiObject;
struct idFile {};
struct idWindow {
	std::deque<int> ops;
    // Deterministically model a recycled allocation containing nonfinite bits.
    float actualX=std::numeric_limits<float>::quiet_NaN(),actualY=actualX;
    Rect drawRect,clientRect,textRect;
    int childID,flags,lastTimeRun,fontNum,timeLine,cursor,textAlign,screenAlignX,screenAlignY,textShadow,numOps;
    float xOffset,yOffset,forceAspectWidth,forceAspectHeight,matScalex,matScaley,borderSize,textAlignx,textAligny;
    bool noTime,visible,alwaysThink,noEvents,hover,hideCursor;
    Value origin,rotate,shear,textScale,textspacing,textstyle,backColor,foreColor,hoverColor,matColor,borderColor;
    Value backColor_r,backColor_g,backColor_b,backColor_w,matColor_r,matColor_g,matColor_b,matColor_w;
    Value foreColor_r,foreColor_g,foreColor_b,foreColor_w,hoverColor_r,hoverColor_g,hoverColor_b,hoverColor_w;
    Value borderColor_r,borderColor_g,borderColor_b,borderColor_w;
    void *background,*focusedChild,*captureChild,*overChild,*parent,*saveOps,*saveRegs;
    static constexpr int SCRIPT_COUNT=3,SCREEN_ALIGN_X_MIDDLE=0,SCREEN_ALIGN_Y_MIDDLE=0;
    void* scripts[SCRIPT_COUNT];
    std::string backGroundName,name="Desktop";
    GUI* gui=&guiObject;
    void CommonInit();
    void WriteToSaveGame(idFile*);
};
// @INIT@
// @ADMISSION@
static int checks=0;
static void check(bool ok,const char* why) {++checks;if(!ok)throw std::runtime_error(why);}
static bool accepted(idWindow& window,idFile* file) {
    try {window.WriteToSaveGame(file);return true;}catch(const std::runtime_error&){return false;}
}
int main() {try {
    idFile file;
    for(int i=0;i<32;++i) {
        idWindow w;
        w.CommonInit();
        check(w.actualX==0 && w.actualY==0,"offscreen coordinates were not initialized");
        check(accepted(w,&file),"save before first layout must succeed");
        w.actualX=480;w.actualY=640;
        w.CommonInit();
        check(w.actualX==0 && w.actualY==0 && accepted(w,&file),"reparse retained stale physical coordinates");
    }
    for(float invalid:{std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}) {
        for(int field=0;field<5;++field) {
            idWindow w;w.CommonInit();
            switch(field) {
                case 0:w.actualX=invalid;break;case 1:w.actualY=invalid;break;
                case 2:w.drawRect.x=invalid;break;case 3:w.textstyle=invalid;break;case 4:w.shear=invalid;break;
            }
            check(!accepted(w,&file),"invalid saved layout was silently accepted");
        }
    }
    idWindow w;w.CommonInit();
    w.textstyle=128;check(!accepted(w,&file),"out of range text style accepted");
    w.textstyle=0;check(!accepted(w,nullptr),"missing file accepted");
    w.gui=nullptr;check(!accepted(w,&file),"missing GUI accepted");
    std::printf("PASS %d initial GUI save-state checks\n",checks);
    return 0;
}catch(const std::exception& e){std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}}
