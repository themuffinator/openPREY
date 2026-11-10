// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "src/ui/retained/Runtime.h"
#include "src/ui/retained/GeneratedImagePool.h"
#include <RmlUi/Core.h>
#include <RmlUi/Core/RenderManager.h>
#include <RmlUi/Core/Geometry.h>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <map>

using namespace openq4::ui;
static void Check(bool condition, const char* message) {
    if (!condition) { std::fprintf(stderr,"FAIL: %s\n",message); std::exit(1); }
}

static void PoolLimits() {
    GeneratedImagePool pool;
    for (auto size : {std::size_t(0),std::size_t(15),std::size_t(17),std::numeric_limits<std::size_t>::max()})
        Check(!pool.Reserve(2,2,size),"byte count must exactly describe bounded RGBA8 pixels");
    for (int edge : {-1,0,4097,std::numeric_limits<int>::max()})
        Check(!pool.Reserve(edge,2,16) && !pool.Reserve(2,edge,16),"reject invalid dimensions before multiplication");
    auto slot=pool.Reserve(4096,4096,GeneratedImagePool::ByteBudget);
    Check(slot && pool.Publish(slot),"largest image fits the aggregate budget exactly");
    Check(!pool.Reserve(1,1,4),"live bytes bound allocations independently of slot count");
    Check(pool.Retire(slot,7) && !pool.Retire(slot,7),"retirement occurs once");
    pool.Collect(7,[](unsigned){ Check(false,"same-frame queued draws cannot lose their image"); return true; });
    Check(!pool.Reserve(1,1,4),"retired bytes remain charged until collection");
    pool.Collect(8,[](unsigned){ return false; });
    Check(pool.ResidentBytes()==GeneratedImagePool::ByteBudget,"failed shrink preserves accounting");
    pool.Collect(8,[](unsigned){ return true; });
    Check(!pool.ResidentBytes(),"safe collection frees the budget");
    for (unsigned i=1;i<=GeneratedImagePool::Capacity;++i)
        Check(pool.Reserve(1,1,4)==i,"registry names are bounded and reused in order");
    Check(!pool.Reserve(1,1,4),"small images cannot exceed the registry bound");
    pool.Reset([](unsigned){ return false; });
    Check(pool.ResidentBytes()==GeneratedImagePool::Capacity*4,"failed reset cannot erase resident costs");
    pool.Reset([](unsigned){ return true; });
    Check(!pool.ResidentBytes(),"generation teardown releases reserved and retired storage");
    Check(!pool.Publish(0) && !pool.Publish(65) && !pool.Retire(0,0),"invalid leases are harmless");
}

struct TestHost final : Host {
    GeneratedImagePool pool;
    std::map<unsigned,std::vector<std::uint8_t>> images;
    std::uint64_t frame=1;
    unsigned uploads=0,releases=0,errors=0,draws=0;
    std::uintptr_t lastDraw=0;
    bool failUpload=false;
    bool ReadFile(const std::string&,std::string&) override { return false; }
    bool ReadCVar(const std::string&,size_t,StateValue&) override { return false; }
    std::string Translate(const std::string& text) override { return text; }
    void Log(bool error,const std::string&) override { if(error) ++errors; }
    std::uintptr_t LoadMaterial(const std::string&,int& w,int& h) override { w=h=1; return 1000; }
    void Collect() { pool.Collect(frame,[this](unsigned id){ images.erase(id); return true; }); }
    std::uintptr_t GenerateTexture(std::span<const std::uint8_t> pixels,int width,int height) override {
        ++uploads; Collect();
        auto id=pool.Reserve(width,height,pixels.size());
        if(!id) return 0;
        if(failUpload) { pool.Retire(id,frame); return 0; }
        images[id]={pixels.begin(),pixels.end()}; Check(pool.Publish(id),"publish reserved image"); return id;
    }
    void ReleaseGeneratedTexture(std::uintptr_t texture) override {
        Check(pool.Retire(static_cast<unsigned>(texture),frame),"release only this host's live generated lease"); ++releases;
    }
    void Draw(const std::vector<Vertex>& v,const std::vector<int>& indices,std::uintptr_t texture) override {
        if(texture && texture!=1000) {
            Check(images.contains(static_cast<unsigned>(texture)),"submitted texture storage is alive");
            Check(v.size()==4 && indices.size()==6,"generated quad reaches ordinary geometry submission");
            Check(v[0].a>.49f && v[0].a<.51f && v[0].r==v[0].a,"premultiplied tint preserved");
            lastDraw=texture; ++draws;
        }
    }
    std::uint64_t RenderFrame() const override { return frame; }
    bool BeginLayer(std::uint32_t,int,int) override { return true; }
    void CompositeLayer(std::uint32_t,std::uint32_t,float,const Bounds&) override {}
    void MaskLayer(std::uint32_t,std::uint32_t,const Bounds&) override {}
    void EndLayer(std::uint32_t) override {}
    FontMetrics GetFontMetrics(const std::string&,int) override { return {}; }
    Glyph GetGlyph(const std::string&,int,std::uint32_t) override { return {}; }
};

static Rml::Geometry Quad(Rml::RenderManager& manager) {
    Rml::Mesh mesh;
    for(const auto p: {Rml::Vector2f(0,0),Rml::Vector2f(32,0),Rml::Vector2f(32,32),Rml::Vector2f(0,32)})
        mesh.vertices.push_back({p,{128,0,0,128},p/32.f});
    mesh.indices={0,1,2,0,2,3}; return manager.MakeGeometry(std::move(mesh));
}
static Rml::CallbackTexture Texture(Rml::RenderManager& manager,std::vector<Rml::byte> pixels={128,0,0,128},Rml::Vector2i size={1,1}) {
    return manager.MakeCallbackTexture([pixels=std::move(pixels),size](const Rml::CallbackTextureInterface& target){
        return target.GenerateTexture({pixels.data(),pixels.size()},size);
    });
}
static void Load(Runtime& runtime,double now) {
    Check(runtime.LoadMarkup("<rml><head><style>body{margin:0;width:64px;height:64px;}</style></head><body/></rml>","generated.rml"),"load actual retained context");
    runtime.Frame({64,64},now);
}

static void RuntimeOwnership() {
    TestHost host;
    Runtime first(host),second(host); Load(first,1);
    auto& a=Rml::GetContext(0)->GetRenderManager();
    auto stock=a.LoadTexture("ordinary-image");
    Check(stock.GetDimensions()==Rml::Vector2i(1,1),"ordinary image uses its existing material path");
    auto image=Texture(a);
    Check(Rml::Texture(image).GetDimensions()==Rml::Vector2i(1,1) && host.uploads==1,"Rml callback uploads once");
    Check(host.images.begin()->second==std::vector<std::uint8_t>({128,0,0,128}),"host receives exact premultiplied pixels");
    auto geometry=Quad(a); geometry.Render({},image); const auto old=host.lastDraw;
    Load(second,1);
    // RmlUi keeps contexts in an unordered map, so an index does not name the
    // second view on every standard library; select the other render manager.
    Rml::RenderManager* other_manager=nullptr;
    for(int i=0;i<Rml::GetNumContexts();++i)
        if(auto* candidate=&Rml::GetContext(i)->GetRenderManager(); candidate!=&a) other_manager=candidate;
    Check(Rml::GetNumContexts()==2 && other_manager,"second context has its own render manager");
    auto& b=*other_manager;
    auto peer=Texture(b); auto other=Quad(b); other.Render({},peer);
    Check(host.lastDraw!=old && host.pool.ResidentBytes()==8,"independent contexts own distinct generated images");
    auto replacement=Texture(a,{0,128,0,128}); geometry.Render({},replacement);
    Check(host.lastDraw!=old && host.pool.ResidentBytes()==12,"replacement remains separate from queued old draws");
    image.Release(); image.Release();
    Check(host.releases==1 && host.images.contains(static_cast<unsigned>(old)),"release once while preserving queued storage");
    host.Collect(); Check(host.images.size()==3,"same-frame collection preserves queued draws");
    ++host.frame; host.Collect(); Check(host.images.size()==2,"later frame collects only the retired image");
    geometry.Release();
    first.Shutdown();
    Check(host.releases==2 && host.pool.IsLive(static_cast<unsigned>(host.lastDraw))==false,"closing a context releases its generated images");
    replacement.Release();
    other.Render({},peer); Check(host.draws==4,"peer view survives another context closing");
    other.Release(); peer.Release(); second.Shutdown();
    ++host.frame; host.Collect();
    Check(host.releases==3 && host.images.empty() && !host.pool.ResidentBytes(),"all generated images released after final view");
    Check(!host.errors,"successful lifetime has no diagnostics");
}

static void RuntimeFailuresAndReuse() {
    TestHost host;
    for(int cycle=0;cycle<1000;++cycle) {
        Runtime runtime(host); Load(runtime,cycle+1);
        auto& manager=Rml::GetContext(0)->GetRenderManager();
        {
            auto image=Texture(manager);
            Check(Rml::Texture(image).GetDimensions()==Rml::Vector2i(1,1),"reopened view generates texture");
            Check(host.images.size()==1 && host.images.begin()->first==1,"1000-cycle image and registry residency stay bounded");
        }
        runtime.Shutdown(); ++host.frame; host.Collect();
        Check(!host.pool.ResidentBytes(),"1000-cycle close retires all image bytes");
    }
    Runtime runtime(host); Load(runtime,1001);
    auto& manager=Rml::GetContext(0)->GetRenderManager();
    const auto before=host.uploads;
    for(auto dimensions : {Rml::Vector2i(0,1),Rml::Vector2i(-1,1),Rml::Vector2i(4097,1),Rml::Vector2i(2,2)}) {
        auto bad=Texture(manager,{1,2,3,4},dimensions);
        Check(Rml::Texture(bad).GetDimensions()==Rml::Vector2i(0,0),"invalid generated input has no texture");
    }
    Check(host.uploads==before && host.errors>=4,"invalid dimensions and byte counts never reach the host");
    host.failUpload=true;
    { auto bad=Texture(manager); Check(Rml::Texture(bad).GetDimensions()==Rml::Vector2i(0,0),"failed upload returns no texture"); }
    host.failUpload=false; ++host.frame; host.Collect();
    { auto good=Texture(manager); Check(Rml::Texture(good).GetDimensions()==Rml::Vector2i(1,1),"upload recovers on fresh texture"); }
    runtime.Shutdown(); ++host.frame; host.Collect(); Check(!host.pool.ResidentBytes(),"failure and recovery leak no budget");
}

int main() {
    PoolLimits(); RuntimeOwnership(); RuntimeFailuresAndReuse();
    std::puts("Generated images: actual Rml callback, premultiplied data, bounds, failures, independent views, replacement, retirement and 1000 reopen cycles passed");
}
