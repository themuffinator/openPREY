// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include <cstdio>
#include <map>
#include <stdexcept>
#include <string>
using byte=unsigned char;
using idStr=std::string;
static int checks=0;
static void check(bool ok,const char* why) {++checks;if(!ok)throw std::runtime_error(why);}
namespace Engine {
static std::map<byte*,int> owned;
static int bytes=0,allocations=0,releases=0;
static byte* MT_GetMaterialTypeArray(idStr name,int& width,int& height) {
    width=height=0;
    if(name=="missing") return nullptr;
    width=name=="first"?64:128;height=32;
    int size=width*height;
    auto* result=new byte[size];owned[result]=size;bytes+=size;++allocations;
    for(int i=0;i<size;++i)result[i]=static_cast<byte>(i%251);
    return result;
}
void Mem_Free(byte* ptr) {
    if(!ptr)return;
    auto found=owned.find(ptr);
    check(found!=owned.end(),"engine received an unknown or already freed map");
    bytes-=found->second;owned.erase(found);delete[] ptr;++releases;
}
struct idDeclManagerLocal {
    byte* GetMaterialTypeArray(const char*,int&,int&);
    void FreeMaterialTypeArray(byte*);
};
// @GET@
// @FREE@
}
static Engine::idDeclManagerLocal manager;
static auto* declManager=&manager;
[[maybe_unused]] static void Mem_Free(byte*) {throw std::runtime_error("renderer freed an engine-owned hit map");}
struct Lexer {idStr next;void ReadTokenOnLine(idStr* out){*out=next;}};
struct Material {
    byte* materialTypeArray=nullptr;
    idStr materialTypeArrayName;
    int MTAWidth=0,MTAHeight=0;
    void ParseImage(const char* path) {
        Lexer src{path};idStr token;
        for(int once=0;once<1;++once)
        // @REPLACE@
    }
    void FreeData() {
        // @RELEASE@
    }
};
int main() {try {
    for(int cycle=0;cycle<64;++cycle) {
        Material m;
        m.FreeData();check(Engine::bytes==0,"empty purge changed accounting");
        m.ParseImage("first");
        check(Engine::bytes==2048 && m.MTAWidth==64 && m.MTAHeight==32,"first allocation mismatch");
        check(m.materialTypeArray[1000]==1000%251,"hit-map bytes changed across boundary");
        m.ParseImage("second");
        check(Engine::bytes==4096 && Engine::owned.size()==1,"replacement leaked the previous hit map");
        m.ParseImage("missing");
        check(!m.materialTypeArray && !Engine::bytes && m.MTAWidth==0 && m.MTAHeight==0,"failed replacement retained a map");
        m.ParseImage("first");m.FreeData();m.FreeData();
        check(!m.materialTypeArray && !Engine::bytes && Engine::owned.empty(),"purge did not release through its owner");
    }
    check(Engine::allocations==Engine::releases,"module allocation/free counts drifted");
    std::printf("PASS %d hit-map ownership checks\n",checks);return 0;
}catch(const std::exception& e){std::fprintf(stderr,"FAIL %s\n",e.what());return 1;}}
