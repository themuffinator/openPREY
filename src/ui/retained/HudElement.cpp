// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#include "HudElement.h"
#include "Runtime.h"
#include "VectorElement.h"
#include <RmlUi/Core/RenderManager.h>
#include <algorithm>
#include <cmath>

namespace openq4::ui {
namespace {
VectorVertex Mix(const VectorVertex& a, const VectorVertex& b, double t) {
	return {a.x+(b.x-a.x)*t,a.y+(b.y-a.y)*t,a.r+(b.r-a.r)*t,a.g+(b.g-a.g)*t,a.b+(b.b-a.b)*t,a.a+(b.a-a.a)*t};
}
// GUI clipping precedes its affine transform. Clip to that exact transformed
// quad, including mirrors/shears, instead of replacing it with an AABB.
VectorMesh Clip(const VectorMesh& mesh, const std::array<VectorPoint,4>& quad) {
	VectorMesh result;
	const auto cross = [](VectorPoint a,VectorPoint b,VectorPoint p) { return (b.x-a.x)*(p.y-a.y)-(b.y-a.y)*(p.x-a.x); };
	const double sign = cross(quad[0],quad[1],quad[2]) >= 0 ? 1 : -1;
	// The usual crosshair is already inside its window. Preserve its disjoint
	// coverage quads instead of splitting them into duplicated triangle lists;
	// the host can then cache the exact pixel coverage in its atlas.
	if (std::all_of(mesh.vertices.begin(),mesh.vertices.end(),[&](const auto& v) {
		for (int edge=0;edge<4;++edge)
			if (sign*cross(quad[edge],quad[(edge+1)%4],{v.x,v.y})<0) return false;
		return true;
	})) return mesh;
	for (size_t i=0;i+2<mesh.indices.size();i+=3) {
		std::vector<VectorVertex> polygon{mesh.vertices[mesh.indices[i]],mesh.vertices[mesh.indices[i+1]],mesh.vertices[mesh.indices[i+2]]};
		for (int edge=0;edge<4 && !polygon.empty();++edge) {
			std::vector<VectorVertex> clipped;
			auto previous = polygon.back();
			double before = sign*cross(quad[edge],quad[(edge+1)%4],{previous.x,previous.y});
			for (const auto& next : polygon) {
				const double after = sign*cross(quad[edge],quad[(edge+1)%4],{next.x,next.y});
				if ((before >= 0) != (after >= 0)) clipped.push_back(Mix(previous,next,before/(before-after)));
				if (after >= 0) clipped.push_back(next);
				previous=next; before=after;
			}
			polygon=std::move(clipped);
		}
		if (polygon.size()<3) continue;
		const int base=static_cast<int>(result.vertices.size());
		result.vertices.insert(result.vertices.end(),polygon.begin(),polygon.end());
		for (size_t n=1;n+1<polygon.size();++n) result.indices.insert(result.indices.end(),{base,base+static_cast<int>(n),base+static_cast<int>(n+1)});
	}
	return result;
}
bool Finite(const HudPrimitive& item) {
	for (auto v:item.quad) if (!std::isfinite(v) || std::abs(v)>1000000) return false;
	for (auto v:item.uv) if (!std::isfinite(v) || std::abs(v)>10000) return false;
	for (auto v:item.colour) if (!std::isfinite(v)) return false;
	return true;
}
}
bool HudElement::Prepare(const std::vector<HudPrimitive>& items,const Node& root,int width,int height,
	RuntimeStatistics& stats,std::string& error,bool& changed) {
	changed=entries.size()!=items.size();
	ready=false; statistics=&stats;
	if (items.size()>32768 || width<=0 || height<=0) { error="HUD presentation exceeds its limits"; return false; }
	auto* manager=GetRenderManager();
	if (!manager) { error="HUD render manager unavailable"; return false; }
	if (catalog.empty()) {
		std::vector<const Node*> nodes{&root};
		while (!nodes.empty()) {
			const auto* node=nodes.back(); nodes.pop_back(); catalog.emplace(node->id,node);
			for (const auto& child:node->children) nodes.push_back(&child);
		}
	}
	entries.resize(items.size());
	for (size_t index=0;index<items.size();++index) {
		const auto& item=items[index]; auto& entry=entries[index];
		if (!Finite(item)) { error="Non-finite HUD presentation"; return false; }
		const bool sameShape=entry.valid && entry.width==width && entry.height==height &&
			entry.previous.artwork==item.artwork && entry.previous.material==item.material &&
			entry.previous.quad==item.quad && entry.previous.uv==item.uv;
		if (sameShape && entry.previous.colour==item.colour) continue;
		changed=true;
		entry.geometry.clear();
		if (!sameShape) {
			entry.meshes.clear(); entry.blends.clear(); entry.texture={}; entry.valid=false;
			std::array<VectorPoint,4> quad;
			for (int i=0;i<4;++i) quad[i]={item.quad[2*i]*width/640.0,item.quad[2*i+1]*height/480.0};
			if (item.artwork.empty()) {
				if (item.material.empty()) { error="HUD picture has no material"; return false; }
				entry.texture=manager->LoadTexture("material:"+item.material);
				const auto size=entry.texture.GetDimensions();
				if (size.x<=0 || size.y<=0) { error="Missing HUD image: "+item.material; return false; }
				VectorMesh mesh;
				for (const auto& p:quad) mesh.vertices.push_back({p.x,p.y,1,1,1,1});
				mesh.indices={0,1,2,0,2,3}; entry.meshes.push_back(std::move(mesh)); entry.blends.push_back(PathBlend::Normal);
			} else {
				const auto found=catalog.find(item.artwork);
				if (found==catalog.end() || found->second->paths.empty()) { error="Missing HUD artwork: "+item.artwork; return false; }
				const double du=item.uv[2]-item.uv[0],dv=item.uv[3]-item.uv[1];
				// Solid primitives have degenerate UVs; artwork still fills the quad.
				const bool solid=du==0 || dv==0;
				const double u0=solid?0:item.uv[0],v0=solid?0:item.uv[1],u1=solid?1:item.uv[2],v1=solid?1:item.uv[3];
				const int left=static_cast<int>(std::floor(std::min(u0,u1))),right=static_cast<int>(std::ceil(std::max(u0,u1)));
				const int top=static_cast<int>(std::floor(std::min(v0,v1))),bottom=static_cast<int>(std::ceil(std::max(v0,v1)));
				if ((right-left)*(bottom-top)>256) { error="HUD artwork tile limit: "+item.artwork; return false; }
				for (int v=top;v<bottom;++v) for (int u=left;u<right;++u) {
					VectorOptions options; options.widthDp=128; options.heightDp=128;
					options.transform.a=(quad[1].x-quad[0].x)/(u1-u0)/128;
					options.transform.b=(quad[1].y-quad[0].y)/(u1-u0)/128;
					options.transform.c=(quad[3].x-quad[0].x)/(v1-v0)/128;
					options.transform.d=(quad[3].y-quad[0].y)/(v1-v0)/128;
					options.transform.tx=quad[0].x+(u-u0)*128*options.transform.a+(v-v0)*128*options.transform.c;
					options.transform.ty=quad[0].y+(u-u0)*128*options.transform.b+(v-v0)*128*options.transform.d;
					options.pixelBounds=VectorPixelBounds{0,0,width,height};
					for (const auto& path:found->second->paths) {
						VectorMesh mesh;
						if (!TessellatePath(path,options,mesh,error)) return false;
						entry.meshes.push_back(Clip(mesh,quad)); entry.blends.push_back(path.blend);
					}
				}
			}
		}
		entry.previous=item; entry.width=width; entry.height=height; entry.valid=true;
	}
	ready=true; return true;
}
void HudElement::OnRender() {
	if (!ready || !statistics) return;
	auto* manager=GetRenderManager(); if (!manager) return;
	const auto state=manager->GetState(); manager->SetTransform(nullptr);
	auto byte=[](double x) { return static_cast<Rml::byte>(std::lround(std::clamp(x,0.0,1.0)*255)); };
	for (auto& entry:entries) {
		const auto& item=entry.previous;
		if (entry.geometry.empty()) {
			for (size_t i=0;i<entry.meshes.size();++i) {
				const auto& source=entry.meshes[i]; const auto blend=entry.blends[i];
				Rml::Mesh mesh;
				for (size_t n=0;n<source.vertices.size();++n) {
					const auto& p=source.vertices[n]; const double a=std::clamp(static_cast<double>(item.colour[3]),0.0,1.0);
					Rml::ColourbPremultiplied colour(byte(p.r*item.colour[0]*a),byte(p.g*item.colour[1]*a),byte(p.b*item.colour[2]*a),byte(p.a*a));
					if (blend==PathBlend::Additive) colour.alpha=0;
					else if (blend==PathBlend::Multiply) colour={byte(1-p.a*a+p.r*item.colour[0]*a),byte(1-p.a*a+p.g*item.colour[1]*a),byte(1-p.a*a+p.b*item.colour[2]*a),byte(p.a*a)};
					Rml::Vector2f uv{0,0};
					if (item.artwork.empty()) uv={item.uv[(n==1 || n==2)?2:0],item.uv[n>=2?3:1]};
					mesh.vertices.push_back({{static_cast<float>(p.x),static_cast<float>(p.y)},colour,uv});
				}
				mesh.indices.assign(source.indices.begin(),source.indices.end());
				entry.geometry.push_back(manager->MakeGeometry(std::move(mesh))); ++statistics->vectorUploads;
			}
		}
		for (size_t i=0;i<entry.geometry.size();++i) {
			if (entry.blends[i]==PathBlend::Multiply) {
				if (!multiply) multiply=manager->LoadTexture(std::string("material:")+MultiplySource);
				entry.geometry[i].Render({0,0},multiply);
			} else entry.geometry[i].Render({0,0},entry.texture);
		}
		if (!item.artwork.empty()) ++statistics->vectorElements;
	}
	manager->SetState(state);
}
}
