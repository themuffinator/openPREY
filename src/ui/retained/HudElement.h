// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
#include "Hud.h"
#include "Vector.h"
#include <RmlUi/Core/Element.h>
#include <RmlUi/Core/Geometry.h>
#include <RmlUi/Core/Texture.h>
#include <map>

namespace openq4::ui {
struct Node;
struct RuntimeStatistics;
// Presentation-only child of the editable artwork catalog. It owns neither
// scripts nor input. All paths compile before publication, so a failed frame
// can fall back without leaving a partly drawn HUD on screen.
class HudElement final : public Rml::Element {
public:
	explicit HudElement(const Rml::String& tag) : Rml::Element(tag) {}
	bool Prepare(const std::vector<HudPrimitive>&, const Node&, int width, int height,
		RuntimeStatistics&, std::string& error, bool& changed);
protected:
	void OnRender() override;
private:
	struct Entry {
		HudPrimitive previous;
		int width = 0, height = 0;
		std::vector<VectorMesh> meshes;
		std::vector<PathBlend> blends;
		std::vector<Rml::Geometry> geometry;
		Rml::Texture texture;
		bool valid = false;
	};
	std::vector<Entry> entries;
	std::map<std::string,const Node*> catalog;
	RuntimeStatistics* statistics = nullptr;
	Rml::Texture multiply;
	bool ready = false;
};
}
