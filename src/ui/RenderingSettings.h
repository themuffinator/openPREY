// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
#include "application/SettingsValue.h"
#include "../renderer/RendererDeviceCatalog.h"

namespace openq4::ui {
// Engine adapter: the service owns one inventory for the lifetime of its view.
// A pick re-enumerates and verifies the displayed catalog before editing a draft.
class RenderingSettings {
public:
	void Reset() { captured=false; }
	void Read(const StateValues& draft, bool clean, StateValues& values);
	bool Select(double index,const std::string& token,StateValues& patch,std::string& error);
	bool Backend(const std::string& api,StateValues& patch,std::string& error);
	static bool Pending(const StateValues& draft);
	static bool Restart(std::string& error);
	static const std::map<std::string,size_t>& Schema();
private:
	void Capture();
	bool captured=false, available=false;
	std::uint64_t token=0;
	renderDeviceCatalog_t catalog{};
};
}
