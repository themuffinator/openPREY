// Production registry/sealing code with explicit entity, landing and hash
// fixtures. Geometry/trajectory proofs are exercised in the separate fixture.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <vector>
#define CHECK(x) do { if(!(x)) { std::fprintf(stderr,"line %d: %s\n",__LINE__,#x); std::exit(1); } } while(0)
template<class T> T Min(T a,T b) { return std::min(a,b); }
template<class T> struct idList : std::vector<T> {
    int Num() const { return int(this->size()); }
    void Append(const T& value) { this->push_back(value); }
    void SetNum(int n) { this->resize(n); }
};
struct idVec3 {
    float x=0,y=0,z=0;
    idVec3()=default; idVec3(float a,float b,float c):x(a),y(b),z(c) {}
    idVec3 operator+(const idVec3& b) const { return {x+b.x,y+b.y,z+b.z}; }
    idVec3 operator-(const idVec3& b) const { return {x-b.x,y-b.y,z-b.z}; }
    idVec3 operator*(float f) const { return {x*f,y*f,z*f}; }
    float LengthSqr() const { return x*x+y*y+z*z; }
    const char* ToString(int) const { return "fixture"; }
};
struct idBounds {
    idVec3 bounds[2];
    idVec3& operator[](int i) { return bounds[i]; }
    const idVec3& operator[](int i) const { return bounds[i]; }
    idVec3 GetCenter() const { return (bounds[0]+bounds[1])*0.5f; }
    void TranslateSelf(const idVec3& v) { bounds[0]=bounds[0]+v; bounds[1]=bounds[1]+v; }
    bool IntersectsBounds(const idBounds& b) const {
        return bounds[0].x<=b[1].x && bounds[1].x>=b[0].x &&
            bounds[0].y<=b[1].y && bounds[1].y>=b[0].y &&
            bounds[0].z<=b[1].z && bounds[1].z>=b[0].z;
    }
};
enum { NAVTRAVEL_WALK, NAVTRAVEL_DROP, NAVTRAVEL_JUMP, NAVTRAVEL_JUMPPAD, NAVTRAVEL_TELEPORT };
constexpr int NAV_MAX_TRANSPORT_LANDINGS=4,NAVNODE_TRANSPORT=1,TH_THINK=1;
constexpr float NAV_JUMPPAD_COST=100,NAV_TELEPORT_COST=20;
struct idEntity {
    int type=0,entityNumber=0; bool live=true,validBounds=true,natural=true;
    int acceptedLandings=0;
    idBounds bounds{{{-32,-32,-128},{32,32,-116}}};
    struct Physics { idVec3 origin; const idVec3& GetOrigin() const { return origin; } int GetContents() const { return 1; } } physics;
    struct Target { idEntity* entity; idEntity* GetEntity() const { return entity; } };
    idList<Target> targets;
    struct Link { idEntity* next=nullptr; idEntity* Next() const { return next; } } spawnNode;
    bool IsType(int t) const { return type==t; }
    bool IsActive(int) const { return live; }
    const char* GetName() const { return "pad_fixture"; }
    Physics* GetPhysics() { return &physics; }
};
struct rvJumpPad { static int GetClassType() { return 1; } };
struct idTrigger_Multi { static int GetClassType() { return 2; } };
struct idPlayerStart { static int GetClassType() { return 3; } };
struct Game {
    idEntity::Link spawnedEntities;
    idEntity* entities[8]={};
    template<class... T> void Printf(const char*,T...) {}
} gameLocal;
struct Debug { bool GetBool() const { return false; } } bot_debug;
struct idClipModel {
    idBounds bounds{{{-32,-32,-128},{32,32,-116}}};
    const idBounds& GetAbsBounds() const { return bounds; }
    const void* GetCollisionModel() const { return nullptr; }
    idVec3 GetOrigin() const { return {}; }
    int GetAxis() const { return 0; }
};
struct Collision {
    int calls=0; bool hit=true;
    template<class... T> bool Contents(T...) { ++calls; return hit; }
} collision;
Collision* collisionModelManager=&collision;
int navAgentTrace=0,mat3_identity=0;
bool NavTravelVolumeBounds(idEntity* e,idBounds& b) { b=e->bounds; return e->validBounds; }
static const idClipModel* contactVolume=nullptr;
const idClipModel* NavTravelVolumeClip(idEntity*) { return contactVolume; }
class rvNavMesh {
public:
    struct Node { idVec3 origin; int gx=0,gy=0,flags=0,firstLink=0; };
    struct navTransport_t {
        idBounds bounds; int entityNum=0,travelType=0,numDestinations=0;
        int destinations[NAV_MAX_TRANSPORT_LANDINGS]; float costs[NAV_MAX_TRANSPORT_LANDINGS];
        bool naturalFirst=false;
    };
    idList<Node> nodes;
    idList<navTransport_t> transports;
    struct Hash { int GenerateKey(int,int) const { return 0; } int First(int) const { return 0; } int Next(int n) const { return n==0 ? 1 : -1; } } nodeHash;
    int CellKey(int,int) const { return 0; }
    int transportNodes=0,fixtureFrom=0,linksAdded=0,landingQueries=0;
    static const idBounds& GetAgentBounds() { static const idBounds b{{{-16,-16,0},{16,16,72}}}; return b; }
    void CellCoords(const idVec3& v,int& x,int& y) const { x=int(std::floor(v.x/24)); y=int(std::floor(v.y/24)); }
    int NodeForEntityPoint(const idVec3& p) const { return p.z>0 ? 1 : fixtureFrom; }
    bool PadLandings(idEntity* e,int from,const idBounds&,int,idList<int>& landings,idList<float>& costs) {
        CHECK(from>=0); ++landingQueries;
        if(e->acceptedLandings) { landings.Append(1); costs.Append(100); }
        return e->natural;
    }
    void LinkNodes(int from,int,float,int,int) { CHECK(from>=0); nodes[from].firstLink=++linksAdded; }
    void AddOffMeshLinks();
    void SealTransportVolumes();
    int TransportAt(const idBounds&) const;
    bool NaturalPadLanding(int,idVec3&) const;
    bool IsSteeredPadLanding(int,const idVec3&) const;
};
// PRODUCTION_FUNCTIONS
int main() {
    idEntity pad,target; pad.type=rvJumpPad::GetClassType(); pad.entityNumber=2;
    idClipModel volume;
    CHECK(!NavPadVolumeTouches(&pad,{0,0,-128}));
    contactVolume=&volume; collision.hit=false;
    CHECK(!NavPadVolumeTouches(&pad,{0,0,-128}) && collision.calls==1);
    collision.hit=true;
    CHECK(NavPadVolumeTouches(&pad,{0,0,-128}) && collision.calls==2);
    CHECK(!NavPadVolumeTouches(&pad,{200,0,-128}) && collision.calls==2);
    contactVolume=nullptr;
    target.physics.origin={0,0,512}; pad.targets.Append({&target});
    gameLocal.spawnedEntities.next=&pad; gameLocal.entities[2]=&pad;
    auto mesh=[]() { rvNavMesh n; n.nodes.Append({{0,0,-128},0,0,0,7}); n.nodes.Append({{240,0,0},10,0,0,7}); return n; };
    for(int source:{0,-1}) {
        auto nav=mesh(); nav.fixtureFrom=source; nav.AddOffMeshLinks();
        CHECK(nav.transports.Num()==1 && nav.transports[0].numDestinations==0);
        CHECK(!nav.transports[0].naturalFirst && nav.linksAdded==0);
        CHECK(nav.landingQueries==(source==0 ? 1 : 0));
        CHECK(nav.TransportAt(pad.bounds)==pad.entityNumber);
        idVec3 landing; CHECK(!nav.NaturalPadLanding(pad.entityNumber,landing));
        CHECK(!nav.IsSteeredPadLanding(pad.entityNumber,{240,0,0}));
        nav.SealTransportVolumes();
        CHECK(nav.transportNodes==1 && nav.nodes[0].firstLink==-1);
        CHECK(nav.nodes[0].flags & NAVNODE_TRANSPORT);
        CHECK(nav.nodes[1].firstLink==7 && nav.nodes[1].flags==0);
    }
    pad.acceptedLandings=1; auto useful=mesh(); useful.AddOffMeshLinks(); useful.SealTransportVolumes();
    CHECK(useful.transports[0].numDestinations==1 && useful.linksAdded==2);
    idVec3 landing; CHECK(useful.NaturalPadLanding(pad.entityNumber,landing));
    CHECK(landing.x==240 && !useful.IsSteeredPadLanding(pad.entityNumber,landing));
    pad.live=false; auto disabled=mesh(); disabled.AddOffMeshLinks(); disabled.SealTransportVolumes();
    CHECK(disabled.transports.Num()==0 && disabled.transportNodes==0);
    pad.live=true; pad.targets.clear(); auto targetless=mesh(); targetless.AddOffMeshLinks();
    CHECK(targetless.transports.Num()==0);
    std::puts("Active transport registry: missing source/landing pads seal ground without invented routes; useful/disabled pads retained: PASS");
}
