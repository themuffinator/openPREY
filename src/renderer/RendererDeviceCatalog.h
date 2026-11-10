// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

// Plain owned data across the renderer-module boundary. No pointers into an
// unloaded module, physical-device handles, or enumeration indices escape.
static const unsigned RENDER_DEVICE_LIMIT = 32;
struct renderDeviceInfo_t {
	char id[33]; // Vulkan deviceUUID, lowercase hex; empty if identity unavailable.
	char name[256];
	bool usable; // Core renderer requirements; presentation is checked at startup.
	bool preferred;
};
struct renderDeviceCatalog_t {
	unsigned count;
	renderDeviceInfo_t devices[RENDER_DEVICE_LIMIT];
	char activeId[33];
};

inline bool RenderDevicePreferenceValid(const char* value) {
	if (!value) return false;
	if (value[0]=='a' && value[1]=='u' && value[2]=='t' && value[3]=='o' && value[4]=='\0') return true;
	unsigned i=0;
	for (; value[i] && i<32; ++i)
		if (!((value[i]>='0' && value[i]<='9') || (value[i]>='a' && value[i]<='f'))) return false;
	return i==32 && value[i]=='\0';
}
