// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once
#include <charconv>
#include <cmath>
#include <cstring>

namespace openq4::ui {
inline const char* GuiStateInteger(int value, char (&text)[64]) {
	const auto result=std::to_chars(text,text+sizeof(text)-1,value);
	*result.ptr='\0';
	return text;
}
// GUI dictionaries retain printf's six-decimal representation. Most published
// layout dimensions are integral, so format those without the floating-point
// conversion/locale machinery. Null asks the caller to keep its printf path
// for fractional, large and exceptional values.
// Like the rest of the GUI number protocol, this uses the engine's C locale.
inline const char* GuiStateIntegralFloat(float value, char (&text)[64]) {
	if (value>=-2147483648.f && value<2147483648.f) {
		const int integer=static_cast<int>(value);
		if (value==static_cast<float>(integer)) {
			char* begin=text;
			if (integer==0 && std::signbit(value)) *begin++='-';
			const auto result=std::to_chars(begin,text+sizeof(text)-8,integer);
			std::memcpy(result.ptr,".000000",8);
			return text;
		}
	}
	return nullptr;
}
}
