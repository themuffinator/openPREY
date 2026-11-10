#!/usr/bin/env python3
"""Exercise production legacy-HUD evaluation reuse with a window recorder."""
from pathlib import Path
import shutil
import subprocess
import tempfile

from filesystem_case_segments import function_body

ROOT = Path(__file__).resolve().parents[2]


def main():
    source = (ROOT / 'src/ui/UserInterface.cpp').read_text(encoding='utf-8')
    bodies = '\n'.join(function_body(source, signature) for signature in (
        'static const char *SetGuiDictionaryValue(',
        'void idUserInterfaceLocal::SetStateString(',
        'void idUserInterfaceLocal::SetStateBool(',
        'void idUserInterfaceLocal::SetStateInt(',
        'void idUserInterfaceLocal::SetStateFloat(',
        'void idUserInterfaceLocal::StateChanged(',
        'void idUserInterfaceLocal::RunTimeEvents(',
        'void idUserInterfaceLocal::Trigger(',
        'void idUserInterfaceLocal::SetInteractive('))
    support = r'''
#include <cassert>
#include <cstdio>
#include <memory>
#include <string>
#include <vector>
#include <map>
#include <cstdarg>
#include <cstdlib>
#include "src/ui/GuiStateNumber.h"
const char* va(const char* format,...){
    static char text[128];va_list args;va_start(args,format);std::vsnprintf(text,sizeof(text),format,args);va_end(args);return text;
}
struct idStr {static int Icmp(const char* a,const char* b){return std::string(a).compare(b);}};
struct Common {int prints=0;void Printf(const char*,...){++prints;}} commonObject;
auto* common=&commonObject;
struct CVar {int value=0;bool GetBool()const{return value!=0;}int GetInteger()const{return value;}};
CVar ui_retainedHudStateCache{1},gui_debugScript;
// Match idDict's pooled immutable strings and refcounted copy semantics.
struct Entry {
    std::shared_ptr<const std::string> key,value;
    const std::string& GetValue()const{return *value;}
    bool operator==(const Entry& other)const{return key==other.key && value==other.value;}
};
std::map<std::string,std::weak_ptr<const std::string>> keys,values;
auto intern(const std::string& value,bool key=false){
    auto& strings=key?keys:values;
    auto result=strings[value].lock();
    if(!result){result=std::make_shared<const std::string>(value);strings[value]=result;}
    return result;
}
struct Dict {
    std::vector<Entry> entries;
    int writes=0;
    mutable int numericReads=0;
    void Set(const std::string& key,const std::string& value){
        ++writes;
        for(auto& entry:entries)if(*entry.key==key){entry.value=intern(value);return;}
        entries.push_back({intern(key,true),intern(value)});
    }
    int GetNumKeyVals()const{return int(entries.size());}
    const Entry* GetKeyVal(int index)const{return &entries[index];}
    const Entry* FindKey(const std::string& key)const{
        for(const auto& entry:entries)if(*entry.key==key)return &entry;
        return nullptr;
    }
    const char* GetString(const char* key,const char* fallback="")const{
        const auto* entry=FindKey(key);return entry?entry->value->c_str():fallback;
    }
    float GetFloat(const char* key,const char* fallback="0")const{++numericReads;return std::strtof(GetString(key,fallback),nullptr);}
    int GetInt(const char* key,const char* fallback="0")const{++numericReads;return std::atoi(GetString(key,fallback));}
    bool GetBool(const std::string& key,const char* fallback="0")const{
        ++numericReads;
        for(const auto& entry:entries)if(*entry.key==key)return *entry.value=="1";
        return *fallback=='1';
    }
};
using idDict=Dict;
using idKeyValue=Entry;
struct idWindow {
    inline static CVar gui_edit;
    int evaluations=0,events=0,triggers=0,lastTime=-1;
    bool interactive=true;
    void StateChanged(bool){++evaluations;}
    bool Interactive()const{return interactive;}
    bool RunTimeEvents(int time){if(time==lastTime)return false;lastTime=time;++events;return true;}
    void Trigger(){++triggers;}
};
struct idRemasteredHud {
    inline static bool enabled=true;
    bool failed=false;
    bool Failed()const{return failed;}
    static bool Enabled(){return enabled;}
    int forwards=0;
    std::map<std::string,std::string> published;
    void ForwardState(const char* name,const char* value){++forwards;published[name]=value;}
};
struct idUserInterfaceLocal {
    int time=0,evaluatedHudTime=0;
    bool loading=false,interactive=false,evaluatedHudValid=false;
    Dict state,evaluatedHudState;
    idWindow* desktop=nullptr;
    idRemasteredHud* remastered=nullptr; idRemasteredHud* essentialHud=nullptr;
    std::string source="guis/hud.gui";
    void SetStateString(const char*,const char*);
    void SetStateBool(const char*,bool);
    void SetStateInt(const char*,int);
    void SetStateFloat(const char*,float);
    void StateChanged(int,bool);
    void RunTimeEvents(int);
    void Trigger(int);
    void SetInteractive(bool);
};
'''
    checks = r'''
int main(){
    idUserInterfaceLocal gui;idWindow window;idRemasteredHud hud;
    gui.desktop=&window;gui.remastered=&hud;gui.state.Set("health","100");
    gui.StateChanged(100,false);assert(window.evaluations==1 && gui.interactive);
    for(int i=0;i<1000;++i){gui.state.Set("health","100");gui.StateChanged(100,false);}
    assert(window.evaluations==1);
    // Dictionary writes made through a raw state pointer are detected too.
    gui.state.Set("health","80");gui.StateChanged(100,false);assert(window.evaluations==2);
    gui.state.Set("new","1");gui.StateChanged(100,false);assert(window.evaluations==3);
    gui.state.entries.erase(gui.state.entries.begin()+1);gui.StateChanged(100,false);assert(window.evaluations==4);
    gui.StateChanged(101,false);assert(window.evaluations==5);
    gui.RunTimeEvents(200);gui.StateChanged(101,false);assert(window.evaluations==6 && window.events==1);
    gui.RunTimeEvents(200);gui.StateChanged(101,false);assert(window.evaluations==6 && window.events==1);
    gui.Trigger(101);gui.StateChanged(101,false);assert(window.evaluations==7 && window.triggers==1);
    gui.SetInteractive(false);gui.StateChanged(101,false);assert(window.evaluations==8 && gui.interactive);
    gui.state.Set("noninteractive","1");gui.StateChanged(101,false);assert(!gui.interactive);
    auto twoWalks=[&](bool redraw=false){int before=window.evaluations;gui.StateChanged(101,redraw);gui.StateChanged(101,redraw);assert(window.evaluations==before+2);};
    twoWalks(true);gui.loading=true;twoWalks();gui.loading=false;
    hud.failed=true;twoWalks();hud.failed=false;
    idRemasteredHud::enabled=false;twoWalks();idRemasteredHud::enabled=true;
    ui_retainedHudStateCache.value=0;twoWalks();ui_retainedHudStateCache.value=1;
    idWindow::gui_edit.value=1;twoWalks();idWindow::gui_edit.value=0;
    gui_debugScript.value=1;twoWalks();gui_debugScript.value=0;
    gui.remastered=nullptr;twoWalks();gui.remastered=&hud;
    gui.StateChanged(101,false);int before=window.evaluations;
    gui.StateChanged(101,false);assert(window.evaluations==before);
    gui.RunTimeEvents(201);gui.StateChanged(101,false);assert(window.evaluations==before+1);
    // Equal writes still republish to a replacement changed by an event. Only
    // the stock dictionary's pooled-string churn and unused debug reads go.
    idUserInterfaceLocal publisher;idRemasteredHud peer;publisher.remastered=&peer;
    for(int i=0;i<1000;++i){
        publisher.SetStateString("text","hello");publisher.SetStateBool("flag",true);
        publisher.SetStateInt("count",42);publisher.SetStateFloat("width",1280);
    }
    assert(publisher.state.writes==4 && publisher.state.numericReads==0 && peer.forwards==4000);
    peer.published["width"]="event value";publisher.SetStateFloat("width",1280);
    assert(peer.published["width"]=="1280.000000" && publisher.state.writes==4);
    idRemasteredHud essential; publisher.essentialHud=&essential;
    publisher.SetStateInt("player_air",56);
    assert(peer.published["player_air"]=="56" && essential.published["player_air"]=="56");
    publisher.essentialHud=nullptr;
    publisher.state.Set("width","640.000000");publisher.SetStateFloat("width",1280);
    assert(std::string(publisher.state.GetString("width"))=="1280.000000" && publisher.state.writes==7);
    publisher.SetStateFloat("width",-0.f);assert(std::string(publisher.state.GetString("width"))=="-0.000000");
    publisher.SetStateFloat("width",.25f);assert(std::string(publisher.state.GetString("width"))=="0.250000");
    publisher.SetStateString("text",publisher.state.GetString("text"));assert(peer.published["text"]=="hello");
    idUserInterfaceLocal alias;
    alias.SetStateString("same","same");
    const auto oldValue=std::weak_ptr<const std::string>(alias.state.FindKey("same")->value);
    alias.SetStateString(alias.state.GetString("same"),"replacement");
    assert(oldValue.expired() && std::string(alias.state.GetString("same"))=="replacement");
    gui_debugScript.value=4;const int oldPrints=commonObject.prints;
    publisher.SetStateBool("flag",false);publisher.SetStateInt("count",43);publisher.SetStateFloat("width",720);
    assert(publisher.state.numericReads==3 && commonObject.prints==oldPrints+3);
    publisher.SetStateBool("flag",false);publisher.SetStateInt("count",43);publisher.SetStateFloat("width",720);
    assert(publisher.state.numericReads==6 && commonObject.prints==oldPrints+3);
    gui_debugScript.value=0;
    std::puts("retained HUD state: identical publications reuse evaluation; mutations, clocks, scripts, fallback and diagnostics remain live");
}
'''
    compiler = next((path for name in ('clang++', 'g++', 'c++') if (path := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError('C++ compiler required')
    (ROOT / '.tmp').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ui-hud-state-', dir=ROOT / '.tmp') as folder:
        cpp, binary = Path(folder) / 'hud.cpp', Path(folder) / 'hud.exe'
        cpp.write_text(support + bodies + checks, encoding='utf-8')
        subprocess.run([compiler, '-std=c++17', '-I', str(ROOT), str(cpp), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
