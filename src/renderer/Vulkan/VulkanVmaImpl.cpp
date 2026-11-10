// Copyright (C) 2026 DarkMatter Productions
//
// Vulkan Memory Allocator implementation translation unit. Kept separate so
// the library's warnings and template instantiation stay out of module code.

// the engine PCH poisons snprintf/vsnprintf toward idStr and idlib's Math.h
// #undefs INT_MIN/INT_MAX (name-clash prevention); VMA and the std headers it
// drags in (<limits>, <mutex>) need the real CRT declarations back
#undef snprintf
#undef vsnprintf
#include <cstdio>
#ifndef INT_MAX
#define INT_MAX		2147483647
#endif
#ifndef INT_MIN
#define INT_MIN		( -2147483647 - 1 )
#endif
#ifndef UINT_MAX
#define UINT_MAX	0xffffffffu
#endif

#if defined( _MSC_VER )
	#pragma warning( push )
	#pragma warning( disable : 4100 4127 4189 4324 4505 )
#elif defined( __GNUC__ ) || defined( __clang__ )
	#pragma GCC diagnostic push
	#pragma GCC diagnostic ignored "-Wunused-parameter"
	#pragma GCC diagnostic ignored "-Wunused-variable"
	#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
#endif

#include "volk.h"

// VMA_STATIC_VULKAN_FUNCTIONS=0 / VMA_DYNAMIC_VULKAN_FUNCTIONS=1 come from
// the build so every translation unit sees one configuration
#define VMA_IMPLEMENTATION
#include "vk_mem_alloc.h"

#if defined( _MSC_VER )
	#pragma warning( pop )
#elif defined( __GNUC__ ) || defined( __clang__ )
	#pragma GCC diagnostic pop
#endif
