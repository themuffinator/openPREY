#!/usr/bin/env python3
"""Run actual UI initialization/ownership methods on a different engine thread.

Android loads the library on the Java thread, then starts the engine on SDLThread.
The fixture uses no window, device input or graphics API. Command registration,
the Runtime constructor and unrelated engine services are counted stand-ins.
"""
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

from filesystem_case_segments import function_body

ROOT = Path(__file__).resolve().parents[2]
SUPPORT = r'''
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <future>
#include <memory>
#include <thread>
#include <vector>
struct idCmdArgs { int Argc() const { return 0; } const char* Argv(int) const { return ""; } };
struct idStr { static int Cmp(const char* a,const char* b) { return std::strcmp(a,b); } };
static constexpr int CMD_FL_SYSTEM=1,CMD_FL_CHEAT=2;
struct Commands { unsigned count=0;template<class... T>void AddCommand(T...){++count;} } commands,*cmdSystem=&commands;
struct Common { void Printf(const char*,...){} void Warning(const char*,...){} } commonObject,*common=&commonObject;
struct Host { void DumpGeometry(){} void SetGeneratedImageProbe(bool){} } host;
namespace openq4::ui { struct Runtime { explicit Runtime(Host&){} }; }
struct retainedUIEditControl { std::uint64_t lifetime=0; };
using retainedUIViewCallback_t=void(*)(void*,int);
struct retainedUIView_t {
    std::shared_ptr<retainedUIEditControl> edit;
    std::unique_ptr<openq4::ui::Runtime> runtime;
    retainedUIViewCallback_t callback=nullptr;void* owner=nullptr;
};
std::vector<retainedUIView_t*> views;
unsigned editWorkDepth=0;bool editDraining=false,resourcesRefreshing=false;
bool BusyEditCanvas(){return false;} void DrainEditViews(){}
std::uint64_t NextEditLifetime(){static std::uint64_t n=0;return ++n;}
struct Allocation { std::uint64_t allocationId=7;bool nativeInputClosing=false,nativeInputChanging=false; } allocation;
struct Allocations {
    int Num() const {return 1;}
    Allocation* operator[](int) const {return &allocation;}
};
struct idRectangle {idRectangle(){} idRectangle(int,int,int,int){}};
struct DeviceContext {void Init(){}};
struct idChatWindow { static void History_f(const idCmdArgs&){} static void Input_f(const idCmdArgs&){} };
void UI_ObserveLegacy(const idCmdArgs&){}
class idUserInterfaceManagerLocal {
public:
    PRESENCE_THREAD
    bool nativeBoundaryActive=false,textBoundaryActive=false,clipboardBoundaryActive=false;
    int applicationPumpDepth=0;
    Allocations allocations;
    idRectangle screenRect;DeviceContext dc;
    void Init();void HudTest(const idCmdArgs&){}
    bool QueryNativeInputAllocation(std::uintptr_t,std::uint64_t&) const noexcept;
} uiManagerLocal;
'''
MAIN = r'''
static bool CheckOwner(bool expected) {
    auto* view=RetainedUI_CreateView(nullptr,nullptr);
    const bool created=view!=nullptr;
    if(view){views.clear();delete view;}
    std::uint64_t identity=99;
    const bool queried=uiManagerLocal.QueryNativeInputAllocation(reinterpret_cast<std::uintptr_t>(&allocation),identity);
    const bool valid=created==expected && queried==expected && identity==(expected?7u:99u);
    if(!valid)std::fprintf(stderr,"UI engine ownership: expected=%d view=%d allocation=%d identity=%llu\n",
        expected,created,queried,static_cast<unsigned long long>(identity));
    return valid;
}
int main() {
    // All namespace and manager constructors have already run on this thread.
    // Match SDLActivity: initialize and operate the engine on another thread.
    std::promise<bool> ready;std::promise<void> release;
    auto released=release.get_future();
    std::thread engine([&]{
        uiManagerLocal.Init();
        ready.set_value(CheckOwner(true));
        released.wait();
    });
    bool valid=ready.get_future().get();
    valid=CheckOwner(false) && valid; // loader thread must no longer own the UI
    release.set_value();engine.join();
    // A fresh initialization with no surviving views binds the current engine
    // thread, including ordinary desktop startup and serial engine restarts.
    uiManagerLocal.Init();
    valid=CheckOwner(true) && valid;
    bool workerRejected=false;std::thread worker([&]{workerRejected=CheckOwner(false);});worker.join();
    valid=valid && workerRejected && commands.count>0;
    if(valid)std::puts("UI initialization binds view and allocation ownership to the engine thread; foreign calls rejected");
    return valid?0:1;
}
'''


def source():
    retained = (ROOT / 'src/ui/RetainedUI.cpp').read_text()
    manager = (ROOT / 'src/ui/UserInterface.cpp').read_text()
    header = (ROOT / 'src/ui/UserInterfaceLocal.h').read_text()
    owner = re.search(r'(?:const )?std::thread::id editThread\s*=[^;]+;', retained).group(0)
    presence = re.search(r'(?:const )?std::thread::id nativePresenceThread\s*=[^;]+;', header).group(0)
    init = function_body(retained, 'void RetainedUI_Init()')
    callbacks = re.findall(r'AddCommand\("[^"]+",\s*(\w+)', init)
    stubs = '\n'.join('void ' + name + '(const idCmdArgs&){}' for name in callbacks)
    return (SUPPORT.replace('PRESENCE_THREAD', presence) + '\n' + owner + '\n' + stubs + '\n'
            + init + '\n' + function_body(manager, 'void idUserInterfaceManagerLocal::Init()')
            + '\n' + function_body(retained, 'retainedUIView_t* RetainedUI_CreateView(')
            + '\n' + function_body(manager, 'bool idUserInterfaceManagerLocal::QueryNativeInputAllocation(') + MAIN)


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--generate-native':
        Path(sys.argv[2]).write_text(source(), encoding='utf-8')
        return 0
    compiler = next((p for name in ('clang++', 'g++', 'c++') if (p := shutil.which(name))), None)
    if not compiler:
        raise RuntimeError('C++17 compiler required')
    with tempfile.TemporaryDirectory(prefix='ui-engine-thread-', dir=ROOT / '.tmp') as directory:
        cpp = Path(directory) / 'ownership.cpp'
        exe = cpp.with_suffix('.exe')
        cpp.write_text(source(), encoding='utf-8')
        subprocess.run([compiler, '-std=c++17', '-pthread', str(cpp), '-o', str(exe)], check=True)
        return subprocess.run([str(exe)]).returncode


if __name__ == '__main__':
    raise SystemExit(main())
