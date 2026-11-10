// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
#pragma once

#include <bit>
#include <charconv>
#include <cstdint>
#include <system_error>

namespace openq4::ui {
// Binary64 <-> decimal text with the exact results of std::to_chars and
// std::from_chars for the fixed, scientific and general formats. libc++ gained
// floating from_chars only in LLVM 20, and Apple's libc++ gates floating
// to_chars behind macOS 13.3, above openQ4's macOS 11 floor. Integer-only
// arithmetic keeps every result independent of the process locale, the
// rounding mode and FTZ/DAZ. chars_format::hex fails with invalid_argument.
// As the standard specifies, from_chars leaves value untouched on any error.
// MSVC's integer-based formatter supplies the same output contract without the
// portable codec's big-integer work on every animated CSS value. Other standard
// libraries retain the portable path, including the macOS 11 deployment floor.
inline std::to_chars_result FloatToChars(char* first, char* last, double value) noexcept;
inline std::to_chars_result FloatToChars(char* first, char* last, double value, std::chars_format format) noexcept;
inline std::to_chars_result FloatToChars(char* first, char* last, double value, std::chars_format format, int precision) noexcept;
inline std::from_chars_result FloatFromChars(const char* first, const char* last, double& value,
	std::chars_format format = std::chars_format::general) noexcept;

namespace float_chars_detail {
// Little-endian base 2^32. The largest intermediates stay below 2^2720: up to
// 800 parsed digits against 5^1123 shifted by a 54-bit quotient, or 2^55 *
// 5^1076 when a rounding bound is expanded. overflow is defensive only.
struct Big {
	static constexpr int Capacity = 96;
	std::uint32_t limb[Capacity] = {};
	int size = 0;
	bool overflow = false;
};
inline void Trim(Big& a) noexcept { while (a.size && !a.limb[a.size-1]) --a.size; }
inline void Assign(Big& a, std::uint64_t value) noexcept {
	a.size = 0;
	for (; value; value >>= 32) a.limb[a.size++] = static_cast<std::uint32_t>(value);
}
inline void MultiplyAdd(Big& a, std::uint32_t factor, std::uint32_t addend = 0) noexcept {
	std::uint64_t carry = addend;
	for (int i = 0; i < a.size; ++i) {
		const std::uint64_t product = std::uint64_t(a.limb[i])*factor+carry;
		a.limb[i] = static_cast<std::uint32_t>(product); carry = product >> 32;
	}
	if (!carry) return;
	if (a.size == Big::Capacity) { a.overflow = true; return; }
	a.limb[a.size++] = static_cast<std::uint32_t>(carry);
}
inline void MultiplyPow5(Big& a, int exponent) noexcept {
	static constexpr std::uint32_t powers[14] = {1,5,25,125,625,3125,15625,78125,390625,1953125,
		9765625,48828125,244140625,1220703125};
	for (; exponent >= 13; exponent -= 13) MultiplyAdd(a,powers[13]);
	if (exponent > 0) MultiplyAdd(a,powers[exponent]);
}
inline void ShiftLeft(Big& a, int bits) noexcept {
	if (!a.size || bits <= 0) return;
	const int words = bits/32, shift = bits%32;
	if (a.size+words+1 > Big::Capacity) { a.overflow = true; return; }
	for (int i = a.size; i >= 0; --i) {
		const std::uint32_t high = i < a.size ? a.limb[i] : 0, low = i ? a.limb[i-1] : 0;
		a.limb[i+words] = shift ? (high << shift) | (low >> (32-shift)) : high;
	}
	for (int i = 0; i < words; ++i) a.limb[i] = 0;
	a.size += words+1; Trim(a);
}
inline void ShiftRightOne(Big& a) noexcept {
	for (int i = 0; i < a.size; ++i) a.limb[i] = (a.limb[i] >> 1) | (i+1 < a.size ? a.limb[i+1] << 31 : 0);
	Trim(a);
}
inline int Compare(const Big& a, const Big& b) noexcept {
	if (a.size != b.size) return a.size < b.size ? -1 : 1;
	for (int i = a.size; i-- > 0;) if (a.limb[i] != b.limb[i]) return a.limb[i] < b.limb[i] ? -1 : 1;
	return 0;
}
// Requires a >= b.
inline void Subtract(Big& a, const Big& b) noexcept {
	std::uint64_t borrow = 0;
	for (int i = 0; i < a.size; ++i) {
		const std::uint64_t subtrahend = (i < b.size ? b.limb[i] : 0)+borrow;
		borrow = a.limb[i] < subtrahend;
		a.limb[i] = static_cast<std::uint32_t>(a.limb[i]-subtrahend);
	}
	Trim(a);
}
inline int BitLength(const Big& a) noexcept {
	return a.size ? 32*(a.size-1)+static_cast<int>(std::bit_width(a.limb[a.size-1])) : 0;
}
inline std::uint32_t DivideSmall(Big& a, std::uint32_t divisor) noexcept {
	std::uint64_t remainder = 0;
	for (int i = a.size; i-- > 0;) {
		const std::uint64_t current = remainder << 32 | a.limb[i];
		a.limb[i] = static_cast<std::uint32_t>(current/divisor); remainder = current%divisor;
	}
	Trim(a); return static_cast<std::uint32_t>(remainder);
}
// floor(numerator/denominator) for a quotient below 2^54; numerator keeps the remainder.
inline std::uint64_t Divide(Big& numerator, const Big& denominator) noexcept {
	Big shifted = denominator; ShiftLeft(shifted,53);
	numerator.overflow = numerator.overflow || shifted.overflow;
	std::uint64_t quotient = 0;
	for (int bit = 53; bit >= 0; --bit, ShiftRightOne(shifted)) {
		if (Compare(numerator,shifted) < 0) continue;
		Subtract(numerator,shifted); quotient |= std::uint64_t(1) << bit;
	}
	return quotient;
}

// value = 0.digit[0]digit[1]... * 10^point, with digit[0] != 0 and no trailing
// zero digits. count == 0 is zero. A binary64 expansion needs at most 769 digits.
struct Decimal {
	static constexpr int Capacity = 800;
	char digit[Capacity] = {};
	int count = 0, point = 0;
};
// Exact decimal expansion of mantissa * 2^exponent for mantissa < 2^55.
inline bool Expand(std::uint64_t mantissa, int exponent, Decimal& out) noexcept {
	out.count = out.point = 0;
	if (!mantissa) return true;
	Big n; Assign(n,mantissa);
	if (exponent >= 0) ShiftLeft(n,exponent); else MultiplyPow5(n,-exponent);
	if (n.overflow) return false;
	std::uint32_t chunk[Big::Capacity*32/29+1]; int chunks = 0;
	while (n.size) chunk[chunks++] = DivideSmall(n,1000000000u);
	if (chunks*9 > Decimal::Capacity) return false;
	char top[10]; int length = 0;
	for (std::uint32_t value = chunk[chunks-1]; value; value /= 10) top[length++] = static_cast<char>(value%10);
	while (length) out.digit[out.count++] = top[--length];
	for (int i = chunks-1; i-- > 0;) {
		std::uint32_t value = chunk[i];
		for (int k = 8; k >= 0; --k, value /= 10) out.digit[out.count+k] = static_cast<char>(value%10);
		out.count += 9;
	}
	out.point = out.count+(exponent < 0 ? exponent : 0);
	while (!out.digit[out.count-1]) --out.count;
	return true;
}
inline int Compare(const Decimal& a, const Decimal& b) noexcept {
	if (!a.count || !b.count) return (a.count != 0)-(b.count != 0);
	if (a.point != b.point) return a.point < b.point ? -1 : 1;
	for (int i = 0; i < a.count && i < b.count; ++i)
		if (a.digit[i] != b.digit[i]) return a.digit[i] < b.digit[i] ? -1 : 1;
	return (a.count > b.count)-(a.count < b.count);
}
// in rounded toward zero to keep >= 1 significant digits.
inline void Truncate(const Decimal& in, int keep, Decimal& out) noexcept {
	out.point = in.point; out.count = keep < in.count ? keep : in.count;
	for (int i = 0; i < out.count; ++i) out.digit[i] = in.digit[i];
	while (out.count && !out.digit[out.count-1]) --out.count;
}
// in truncated to keep >= 1 significant digits, plus one unit in the last of them.
inline void Increment(const Decimal& in, int keep, Decimal& out) noexcept {
	out.point = in.point;
	for (int i = 0; i < keep; ++i) out.digit[i] = i < in.count ? in.digit[i] : char(0);
	int at = keep-1;
	for (; at >= 0 && out.digit[at] == 9; --at) out.digit[at] = 0;
	if (at < 0) { out.digit[0] = 1; out.count = 1; ++out.point; return; }
	++out.digit[at]; out.count = at+1;
}
// Round-half-even to keep significant digits; keep <= 0 rounds at or above the leading digit.
inline void Round(const Decimal& in, long long keep, Decimal& out) noexcept {
	if (keep >= in.count) { out = in; return; }
	out.count = out.point = 0;
	if (keep < 0) return;
	const int at = static_cast<int>(keep), next = in.digit[at];
	const bool up = next > 5 || (next == 5 && (at+1 < in.count || (at && (in.digit[at-1] & 1))));
	if (!at) { if (up) { out.digit[0] = 1; out.count = 1; out.point = in.point+1; } return; }
	if (up) Increment(in,at,out); else Truncate(in,at,out);
}

struct Writer {
	char* next;
	char* last;
	bool full = false;
	void Put(char c) noexcept { if (next == last) full = true; else *next++ = c; }
	void Fill(char c, long long count) noexcept {
		if (count <= 0) return;
		if (count > last-next) { full = true; next = last; return; }
		for (; count; --count) *next++ = c;
	}
	std::to_chars_result Result() const noexcept {
		return full ? std::to_chars_result{last,std::errc::value_too_large} : std::to_chars_result{next,std::errc{}};
	}
};
// Digits at [from, from+count), with zeros outside the stored digits.
inline void PutDigits(Writer& w, const Decimal& d, long long from, long long count) noexcept {
	for (; count > 0 && !w.full; ++from, --count) {
		if (from >= d.count) { w.Fill('0',count); return; }
		w.Put(from < 0 ? '0' : static_cast<char>('0'+d.digit[from]));
	}
}
inline void PutFixed(Writer& w, const Decimal& d, long long fraction) noexcept {
	if (d.point <= 0) w.Put('0'); else PutDigits(w,d,0,d.point);
	if (fraction <= 0) return;
	w.Put('.'); PutDigits(w,d,d.point,fraction);
}
inline void PutScientific(Writer& w, const Decimal& d, long long fraction) noexcept {
	w.Put(static_cast<char>('0'+(d.count ? d.digit[0] : 0)));
	if (fraction > 0) { w.Put('.'); PutDigits(w,d,1,fraction); }
	const int exponent = d.count ? d.point-1 : 0, magnitude = exponent < 0 ? -exponent : exponent;
	w.Put('e'); w.Put(exponent < 0 ? '-' : '+');
	if (magnitude >= 100) w.Put(static_cast<char>('0'+magnitude/100));
	w.Put(static_cast<char>('0'+magnitude/10%10)); w.Put(static_cast<char>('0'+magnitude%10));
}

struct Binary {
	bool negative = false, finite = true, nan = false;
	std::uint64_t mantissa = 0;
	int exponent = 0;
	bool narrowBelow = false;	// the next smaller double is half an ulp away
};
inline Binary Split(double value) noexcept {
	const std::uint64_t bits = std::bit_cast<std::uint64_t>(value), fraction = bits & 0xfffffffffffffULL;
	const int biased = static_cast<int>(bits >> 52 & 0x7ff);
	Binary b;
	b.negative = (bits >> 63) != 0;
	if (biased == 0x7ff) { b.finite = false; b.nan = fraction != 0; return b; }
	b.mantissa = biased ? fraction | std::uint64_t(1) << 52 : fraction;
	b.exponent = (biased ? biased : 1)-1075;
	b.narrowBelow = !fraction && biased > 1;
	return b;
}
// Sign and the non-finite spellings shared by every format; true when complete.
inline bool PutPrefix(Writer& w, const Binary& b) noexcept {
	if (b.negative) w.Put('-');
	if (b.finite) return false;
	for (const char* text = b.nan ? "nan" : "inf"; *text; ++text) w.Put(*text);
	return true;
}
enum class Style { Plain, Fixed, Scientific, General };
inline bool ValidFormat(std::chars_format format) noexcept {
	return format == std::chars_format::fixed || format == std::chars_format::scientific || format == std::chars_format::general;
}
inline Style FormatStyle(std::chars_format format) noexcept {
	return format == std::chars_format::fixed ? Style::Fixed : format == std::chars_format::scientific ? Style::Scientific : Style::General;
}

// The fewest significant digits that read back as value; among equally short
// candidates the nearest, ties to even. Notation choices follow the standard
// library: plain picks the shorter of fixed and scientific (ties to fixed),
// general uses %g's P=6 rule, and fixed prints an integral value exactly.
inline std::to_chars_result Shortest(char* first, char* last, double value, Style style) noexcept {
	Writer w{first,last};
	const Binary b = Split(value);
	if (PutPrefix(w,b)) return w.Result();
	if (!b.mantissa) {
		w.Put('0');
		if (style == Style::Scientific) { w.Put('e'); w.Put('+'); w.Put('0'); w.Put('0'); }
		return w.Result();
	}
	// Midpoints to the neighbouring doubles read back as value only when its
	// mantissa is even (round-half-even).
	Decimal exact, low, high;
	if (!Expand(b.mantissa,b.exponent,exact) || !Expand(2*b.mantissa+1,b.exponent-1,high) ||
		!(b.narrowBelow ? Expand(4*b.mantissa-1,b.exponent-2,low) : Expand(2*b.mantissa-1,b.exponent-1,low)))
		return {last,std::errc::value_too_large};
	const bool inclusive = (b.mantissa & 1) == 0;
	const auto inside = [&](const Decimal& d) noexcept {
		const int fromLow = Compare(d,low), fromHigh = Compare(d,high);
		return (fromLow > 0 || (fromLow == 0 && inclusive)) && (fromHigh < 0 || (fromHigh == 0 && inclusive));
	};
	Decimal shortest, below, above;
	Round(exact,17,shortest);
	for (int keep = 1; keep <= 17 && keep < exact.count; ++keep) {
		Truncate(exact,keep,below); Increment(exact,keep,above);
		const int next = exact.digit[keep];
		const bool up = next > 5 || (next == 5 && (keep+1 < exact.count || (exact.digit[keep-1] & 1)));
		if (inside(up ? above : below)) { shortest = up ? above : below; break; }
		if (inside(up ? below : above)) { shortest = up ? below : above; break; }
	}
	const int digits = shortest.count, scale = shortest.point-digits, exponent = shortest.point-1;
	bool fixed = style == Style::Fixed;
	if (style == Style::Plain) fixed = digits == 1 ? scale >= -3 && scale <= 4 : scale >= -(digits+3) && scale <= 5;
	else if (style == Style::General) fixed = exponent >= -4 && exponent < 6;
	if (!fixed) PutScientific(w,shortest,digits-1);
	else if (scale > 0) PutDigits(w,exact,0,exact.point);
	else PutFixed(w,shortest,-scale);
	return w.Result();
}
// printf's %.*f, %.*e and %.*g in the C locale.
inline std::to_chars_result Precise(char* first, char* last, double value, Style style, int precision) noexcept {
	Writer w{first,last};
	const Binary b = Split(value);
	if (PutPrefix(w,b)) return w.Result();
	if (precision < 0) precision = 6;
	Decimal exact, rounded;
	if (!Expand(b.mantissa,b.exponent,exact)) return {last,std::errc::value_too_large};
	if (style == Style::Fixed) {
		Round(exact,static_cast<long long>(exact.point)+precision,rounded); PutFixed(w,rounded,precision);
	} else if (style == Style::Scientific) {
		Round(exact,1LL+precision,rounded); PutScientific(w,rounded,precision);
	} else {
		// %g keeps precision significant digits, then drops trailing zeros.
		const int significant = precision ? precision : 1;
		Round(exact,significant,rounded);
		const int exponent = rounded.count ? rounded.point-1 : 0;
		const long long stored = rounded.count-rounded.point;
		if (exponent < significant && exponent >= -4) {
			const long long fraction = significant-1LL-exponent;
			PutFixed(w,rounded,fraction < stored ? fraction : stored);
		} else {
			const long long fraction = rounded.count ? rounded.count-1LL : 0;
			PutScientific(w,rounded,fraction < significant-1LL ? fraction : significant-1LL);
		}
	}
	return w.Result();
}

// Correctly rounded magnitude bits for the integer digits[0..count) *
// 10^exponent (digits[0] != 0), nudged upward by sticky; false when that
// overflows or underflows to zero. 800 digits decide every halfway case.
inline bool Assemble(const char* digits, int count, bool sticky, long long exponent, std::uint64_t& bits) noexcept {
	const long long scientific = count-1+exponent;
	if (scientific > 308 || scientific < -324) return false;
	const int decimal = static_cast<int>(exponent);
	Big numerator, denominator;
	for (int i = 0; i < count; i += 9) {
		std::uint32_t chunk = 0, scale = 1;
		for (int k = i; k < count && k < i+9; ++k) { chunk = chunk*10+static_cast<std::uint32_t>(digits[k]); scale *= 10; }
		MultiplyAdd(numerator,scale,chunk);
	}
	// value = numerator/denominator * 2^decimal
	Assign(denominator,1);
	if (decimal >= 0) MultiplyPow5(numerator,decimal); else MultiplyPow5(denominator,-decimal);
	int magnitude = BitLength(numerator)-BitLength(denominator);
	{
		Big a = numerator, c = denominator;
		if (magnitude >= 0) ShiftLeft(c,magnitude); else ShiftLeft(a,-magnitude);
		if (Compare(a,c) < 0) --magnitude;
		if (a.overflow || c.overflow) return false;
	}
	// 2^binary <= value < 2^(binary+1); quantize to the binary64 grid at lsb.
	const int binary = magnitude+decimal;
	if (binary > 1023) return false;
	const int lsb = binary-52 < -1074 ? -1074 : binary-52, shift = decimal-lsb;
	if (shift >= 0) ShiftLeft(numerator,shift); else ShiftLeft(denominator,-shift);
	std::uint64_t quotient = Divide(numerator,denominator);
	ShiftLeft(numerator,1);
	const int half = Compare(numerator,denominator);
	if (numerator.overflow || denominator.overflow) return false;
	if (half > 0 || (half == 0 && (sticky || (quotient & 1)))) ++quotient;
	int biased = lsb+1075;
	if (quotient >> 53) { quotient >>= 1; ++biased; }
	if (!(quotient >> 52)) biased = 0;
	if (biased > 2046) return false;
	bits = std::uint64_t(biased) << 52 | (quotient & 0xfffffffffffffULL);
	return bits != 0;
}
inline bool Word(const char* p, const char* last, const char* word) noexcept {
	for (; *word; ++p, ++word) if (p == last || (*p | 0x20) != *word) return false;
	return true;
}
inline bool Digit(const char* p, const char* last) noexcept { return p != last && *p >= '0' && *p <= '9'; }
// std::from_chars grammar: optional '-', inf/infinity, nan/nan(chars), or
// digits with an optional point and (unless fixed) an optional exponent.
inline std::from_chars_result Parse(const char* first, const char* last, double& value, std::chars_format format) noexcept {
	if (!ValidFormat(format)) return {first,std::errc::invalid_argument};
	const char* p = first;
	const bool negative = p != last && *p == '-';
	if (negative) ++p;
	const std::uint64_t sign = negative ? std::uint64_t(1) << 63 : 0;
	if (Word(p,last,"inf")) {
		value = std::bit_cast<double>(sign | 0x7ff0000000000000ULL);
		return {p+(Word(p+3,last,"inity") ? 8 : 3),std::errc{}};
	}
	if (Word(p,last,"nan")) {
		p += 3;
		if (p != last && *p == '(') {
			const char* close = p+1;
			while (close != last && (Digit(close,last) || ((*close | 0x20) >= 'a' && (*close | 0x20) <= 'z') || *close == '_')) ++close;
			if (close != last && *close == ')') p = close+1;
		}
		value = std::bit_cast<double>(sign | 0x7ff8000000000000ULL);
		return {p,std::errc{}};
	}
	// value = digits * 10^exponent. Leading zeros are skipped; digits past the
	// capacity only move the exponent or mark the value as above a halfway case.
	char digits[Decimal::Capacity] = {};
	int count = 0;
	long long exponent = 0;
	bool any = false, sticky = false;
	const auto accept = [&](char c, bool fraction) noexcept {
		any = true;
		if (!count && c == '0') { exponent -= fraction ? 1 : 0; return; }
		if (count < Decimal::Capacity) { digits[count++] = static_cast<char>(c-'0'); exponent -= fraction ? 1 : 0; }
		else { sticky = sticky || c != '0'; exponent += fraction ? 0 : 1; }
	};
	for (; Digit(p,last); ++p) accept(*p,false);
	if (p != last && *p == '.') for (++p; Digit(p,last); ++p) accept(*p,true);
	if (!any) return {first,std::errc::invalid_argument};
	bool scientific = false;
	if (format != std::chars_format::fixed && p != last && (*p == 'e' || *p == 'E')) {
		const char* q = p+1;
		const bool below = q != last && *q == '-';
		if (q != last && (*q == '+' || *q == '-')) ++q;
		if (Digit(q,last)) {
			long long written = 0;
			for (; Digit(q,last); ++q) if (written < 100000000) written = written*10+(*q-'0');
			exponent += below ? -written : written;
			p = q; scientific = true;
		}
	}
	if (format == std::chars_format::scientific && !scientific) return {first,std::errc::invalid_argument};
	while (count && !digits[count-1]) { --count; ++exponent; }
	std::uint64_t bits = 0;
	if (count && !Assemble(digits,count,sticky,exponent,bits)) return {p,std::errc::result_out_of_range};
	value = std::bit_cast<double>(sign | bits);
	return {p,std::errc{}};
}
} // namespace float_chars_detail

inline std::to_chars_result FloatToChars(char* first, char* last, double value) noexcept {
#if defined(_MSC_VER)
	return std::to_chars(first,last,value);
#else
	return float_chars_detail::Shortest(first,last,value,float_chars_detail::Style::Plain);
#endif
}
inline std::to_chars_result FloatToChars(char* first, char* last, double value, std::chars_format format) noexcept {
	if (!float_chars_detail::ValidFormat(format)) return {first,std::errc::invalid_argument};
#if defined(_MSC_VER)
	return std::to_chars(first,last,value,format);
#else
	return float_chars_detail::Shortest(first,last,value,float_chars_detail::FormatStyle(format));
#endif
}
inline std::to_chars_result FloatToChars(char* first, char* last, double value, std::chars_format format, int precision) noexcept {
	if (!float_chars_detail::ValidFormat(format)) return {first,std::errc::invalid_argument};
#if defined(_MSC_VER)
	return std::to_chars(first,last,value,format,precision);
#else
	return float_chars_detail::Precise(first,last,value,float_chars_detail::FormatStyle(format),precision);
#endif
}
inline std::from_chars_result FloatFromChars(const char* first, const char* last, double& value, std::chars_format format) noexcept {
	return float_chars_detail::Parse(first,last,value,format);
}
} // namespace openq4::ui
