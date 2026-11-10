// Copyright (C) 2026 DarkMatter Productions. GPL-3.0-or-later.
// FloatToChars/FloatFromChars against the standard library where it has the
// floating overloads (MSVC STL, libstdc++), against printf/strtod elsewhere
// (libc++), and against fixed expectations everywhere. Midpoints between
// neighbouring doubles are built with exact decimal arithmetic.
#include "src/ui/retained/FloatChars.h"
#include <bit>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <limits>
#include <string>
#include <vector>
#if defined(__SSE__) || defined(_M_X64)
#include <xmmintrin.h>
#define TEST_SSE 1
#elif defined(__aarch64__) && (defined(__GNUC__) || defined(__clang__))
#define TEST_FPCR 1
#endif
// UI_FLOAT_CHARS_LIBC_ORACLE exercises the libc++ path on any C library.
#if defined(__cpp_lib_to_chars) && __cpp_lib_to_chars >= 201611L && !defined(UI_FLOAT_CHARS_LIBC_ORACLE)
#define TEST_STD_ORACLE 1
#endif
using namespace openq4::ui;
static unsigned checks;
#define CHECK(x) do{++checks;if(!(x)){std::fprintf(stderr,"FAIL %d: %s\n",__LINE__,#x);std::exit(1);}}while(false)
#define CHECK_TEXT(x,got,want) do{++checks;if(!(x)){std::fprintf(stderr,"FAIL %d: %s\n  got  %s\n  want %s\n",__LINE__,#x,std::string(got).c_str(),std::string(want).c_str());std::exit(1);}}while(false)

// Flush-to-zero and denormals-are-zero, where the target exposes them.
struct Flush {
#if TEST_SSE
	unsigned old=_mm_getcsr();Flush(){_mm_setcsr(old|0x8040u);}~Flush(){_mm_setcsr(old);}
#elif TEST_FPCR
	std::uint64_t old;Flush(){__asm__ volatile("mrs %0, fpcr":"=r"(old));const std::uint64_t set=old|(std::uint64_t(1)<<24);__asm__ volatile("msr fpcr, %0"::"r"(set));}
	~Flush(){__asm__ volatile("msr fpcr, %0"::"r"(old));}
#else
	Flush(){}
#endif
};

enum Mode { Plain, Fixed, Scientific, General, FixedP, ScientificP, GeneralP };
static const std::chars_format formats[] = {std::chars_format::general,std::chars_format::fixed,std::chars_format::scientific,
	std::chars_format::general,std::chars_format::fixed,std::chars_format::scientific,std::chars_format::general};
static std::string Ours(double value, Mode mode, int precision = 0, std::errc* error = nullptr) {
	char text[1200];
	const auto r = mode == Plain ? FloatToChars(text,text+sizeof(text),value) : mode < FixedP ?
		FloatToChars(text,text+sizeof(text),value,formats[mode]) : FloatToChars(text,text+sizeof(text),value,formats[mode],precision);
	if (error) *error = r.ec;
	CHECK(r.ec == std::errc{});
	return {text,r.ptr};
}
#if TEST_STD_ORACLE
static std::string Theirs(double value, Mode mode, int precision = 0) {
	char text[1200];
	const auto r = mode == Plain ? std::to_chars(text,text+sizeof(text),value) : mode < FixedP ?
		std::to_chars(text,text+sizeof(text),value,formats[mode]) : std::to_chars(text,text+sizeof(text),value,formats[mode],precision);
	CHECK(r.ec == std::errc{});
	return {text,r.ptr};
}
#else
static std::string Printf(double value, Mode mode, int precision) {
	char text[1200];
	const char* pattern = mode == FixedP ? "%.*f" : mode == ScientificP ? "%.*e" : "%.*g";
	const int length = std::snprintf(text,sizeof(text),pattern,precision,value);
	CHECK(length > 0 && length < int(sizeof(text)));
	return {text,std::size_t(length)};
}
#endif
static bool Same(double a, double b) { return std::bit_cast<std::uint64_t>(a) == std::bit_cast<std::uint64_t>(b); }
static double ParseOurs(const std::string& text) {
	double value = 0;
	const auto r = FloatFromChars(text.data(),text.data()+text.size(),value);
	CHECK_TEXT(r.ec == std::errc{} && r.ptr == text.data()+text.size(),text,"a complete parse");
	return value;
}

static const int precisions[] = {0,1,2,3,6,9,10,16,17,25,60};
static void CompareValue(double value) {
	for (Mode mode : {Plain,Fixed,Scientific,General}) {
		const std::string ours = Ours(value,mode);
		// Every shortest form reads back exactly.
		CHECK_TEXT(Same(ParseOurs(ours),value),ours,"round trip");
#if TEST_STD_ORACLE
		const std::string theirs = Theirs(value,mode);
		CHECK_TEXT(ours == theirs,ours,theirs);
		double parsed = 0;
		const auto r = std::from_chars(ours.data(),ours.data()+ours.size(),parsed);
		CHECK(r.ec == std::errc{} && r.ptr == ours.data()+ours.size() && Same(parsed,value));
#else
		CHECK_TEXT(Same(std::strtod(ours.c_str(),nullptr),value),ours,"strtod round trip");
#endif
		// A buffer one byte short fails as value_too_large at last.
		char small[1200];
		const auto shortResult = mode == Plain ? FloatToChars(small,small+ours.size()-1,value) :
			FloatToChars(small,small+ours.size()-1,value,formats[mode]);
		CHECK(shortResult.ec == std::errc::value_too_large && shortResult.ptr == small+ours.size()-1);
	}
	for (Mode mode : {FixedP,ScientificP,GeneralP}) {
		for (int precision : precisions) {
			const std::string ours = Ours(value,mode,precision);
#if TEST_STD_ORACLE
			const std::string theirs = Theirs(value,mode,precision);
#else
			const std::string theirs = Printf(value,mode,precision);
#endif
			CHECK_TEXT(ours == theirs,ours,theirs);
		}
	}
}

// Expected spellings shared by MSVC STL and libstdc++.
static void Golden() {
	struct Row { double value; const char *plain, *fixed, *scientific, *general; };
	const Row rows[] = {
		{100.0,"100","100","1e+02","100"},
		{123456.0,"123456","123456","1.23456e+05","123456"},
		{1234567.0,"1234567","1234567","1.234567e+06","1.234567e+06"},
		{1e-5,"1e-05","0.00001","1e-05","1e-05"},
		{0.0001,"1e-04","0.0001","1e-04","0.0001"},
		{1e4,"10000","10000","1e+04","10000"},
		{1e5,"1e+05","100000","1e+05","100000"},
		{1e23,"1e+23","99999999999999991611392","1e+23","1e+23"},
		{1e22,"1e+22","10000000000000000000000","1e+22","1e+22"},
		{0.1,"0.1","0.1","1e-01","0.1"},
		{-0.0,"-0","-0","-0e+00","-0"},
		{0.0,"0","0","0e+00","0"},
		{9007199254740992.0,"9007199254740992","9007199254740992","9.007199254740992e+15","9.007199254740992e+15"},
		{123456789012345680.0,"123456789012345680","123456789012345680","1.2345678901234568e+17","1.2345678901234568e+17"},
		{.07500000000000001,"0.07500000000000001","0.07500000000000001","7.500000000000001e-02","0.07500000000000001"},
		{std::numeric_limits<double>::max(),"1.7976931348623157e+308",nullptr,"1.7976931348623157e+308","1.7976931348623157e+308"},
		{std::numeric_limits<double>::denorm_min(),"5e-324",nullptr,"5e-324","5e-324"}};
	for (const Row& row : rows) {
		CHECK_TEXT(Ours(row.value,Plain) == row.plain,Ours(row.value,Plain),row.plain);
		if (row.fixed) CHECK_TEXT(Ours(row.value,Fixed) == row.fixed,Ours(row.value,Fixed),row.fixed);
		CHECK_TEXT(Ours(row.value,Scientific) == row.scientific,Ours(row.value,Scientific),row.scientific);
		CHECK_TEXT(Ours(row.value,General) == row.general,Ours(row.value,General),row.general);
	}
	CHECK(Ours(std::numeric_limits<double>::denorm_min(),Fixed) == "0."+std::string(323,'0')+"5");
	CHECK(Ours(1.5e300,Fixed).rfind("150000000000000007875714038280663037305670287166223873237378",0) == 0 && Ours(1.5e300,Fixed).size() == 301);
	CHECK(Ours(0.125,FixedP,2) == "0.12" && Ours(0.375,FixedP,2) == "0.38" && Ours(-0.001,FixedP,2) == "-0.00");
	CHECK(Ours(0.5,FixedP,0) == "0" && Ours(1.5,FixedP,0) == "2" && Ours(2.5,FixedP,0) == "2" && Ours(0.006,FixedP,2) == "0.01");
	CHECK(Ours(1.0,GeneralP,-3) == "1" && Ours(0.0,ScientificP,3) == "0.000e+00" && Ours(0.0,GeneralP,3) == "0" && Ours(0.0,FixedP,3) == "0.000");
	CHECK(Ours(0.1,GeneralP,17) == "0.10000000000000001" && Ours(1e23,GeneralP,17) == "9.9999999999999992e+22");
	CHECK(Ours(100000.0,GeneralP,6) == "100000" && Ours(1e6,GeneralP,6) == "1e+06" && Ours(9.9999,GeneralP,2) == "10");
	CHECK(Ours(1e-5,GeneralP,3) == "1e-05" && Ours(1.25e-4,GeneralP,3) == "0.000125" && Ours(1e100,ScientificP,2) == "1.00e+100");
	CHECK(Ours(std::numeric_limits<double>::infinity(),Plain) == "inf" && Ours(-std::numeric_limits<double>::infinity(),FixedP,3) == "-inf");
	CHECK(Ours(std::numeric_limits<double>::quiet_NaN(),General) == "nan");
	char text[8];
	CHECK(FloatToChars(text,text+sizeof(text),1.0,std::chars_format::hex).ec == std::errc::invalid_argument);
	CHECK(FloatToChars(text,text+sizeof(text),1.0,std::chars_format::hex,3).ec == std::errc::invalid_argument);
	CHECK(FloatToChars(text,text+sizeof(text),1.0,std::chars_format::fixed,1000000000).ec == std::errc::value_too_large);
}

// Grammar, consumed length, range errors and an untouched value on failure.
static void Grammar() {
	struct Row { const char* text; std::chars_format format; std::errc ec; int consumed; double value; };
	const double inf = std::numeric_limits<double>::infinity(), keep = 12345.0;
	const auto general = std::chars_format::general, fixed = std::chars_format::fixed, scientific = std::chars_format::scientific;
	const Row rows[] = {
		{"1e-400",general,std::errc::result_out_of_range,6,keep}, {"1e400",general,std::errc::result_out_of_range,5,keep},
		{"-1e400",general,std::errc::result_out_of_range,6,keep},
		{"2.4703282292062327e-324",general,std::errc::result_out_of_range,23,keep},
		{"2.4703282292062328e-324",general,std::errc{},23,std::numeric_limits<double>::denorm_min()},
		{"1.7976931348623158e308",general,std::errc{},22,std::numeric_limits<double>::max()},
		{"1.7976931348623159e308",general,std::errc::result_out_of_range,22,keep},
		{"1e-320",general,std::errc{},6,1e-320}, {"1e5",fixed,std::errc{},1,1.0}, {"1e",general,std::errc{},1,1.0},
		{"1e+",general,std::errc{},1,1.0}, {"1e-x",general,std::errc{},1,1.0}, {".5",general,std::errc{},2,0.5},
		{"5.",general,std::errc{},2,5.0}, {"-.5e1",general,std::errc{},5,-5.0}, {"1.e3",general,std::errc{},4,1000.0},
		{".",general,std::errc::invalid_argument,0,keep}, {"-",general,std::errc::invalid_argument,0,keep},
		{"",general,std::errc::invalid_argument,0,keep}, {".e3",general,std::errc::invalid_argument,0,keep},
		{"+1",general,std::errc::invalid_argument,0,keep}, {" 1",general,std::errc::invalid_argument,0,keep},
		{"e5",general,std::errc::invalid_argument,0,keep}, {"1.5",scientific,std::errc::invalid_argument,0,keep},
		{"1.5e3",scientific,std::errc{},5,1500.0}, {"1.5E+3",general,std::errc{},6,1500.0},
		{"infinity",general,std::errc{},8,inf}, {"-INFinit",general,std::errc{},4,-inf}, {"inf",fixed,std::errc{},3,inf},
		{"+inf",general,std::errc::invalid_argument,0,keep}, {"in",general,std::errc::invalid_argument,0,keep},
		{"0x1p3",general,std::errc{},1,0.0}, {"0e99999999999999999999",general,std::errc{},22,0.0},
		{"-0.000",general,std::errc{},6,-0.0}, {"1e-99999999999999999999",general,std::errc::result_out_of_range,23,keep},
		{"00012.5000e-0003",general,std::errc{},16,0.0125}, {"123abc",general,std::errc{},3,123.0}};
	for (const Row& row : rows) {
		const std::size_t length = std::strlen(row.text);
		double value = keep;
		const auto r = FloatFromChars(row.text,row.text+length,value,row.format);
		CHECK_TEXT(r.ec == row.ec && r.ptr == row.text+row.consumed && Same(value,row.value),row.text,"grammar row");
#if TEST_STD_ORACLE
		double theirs = keep;
		const auto s = std::from_chars(row.text,row.text+length,theirs,row.format);
		CHECK_TEXT(s.ec == r.ec && s.ptr == r.ptr && (s.ec != std::errc{} || Same(theirs,value)),row.text,"std grammar row");
#endif
	}
	for (const char* text : {"nan","-nan","NaN(abc_1)","nan(abc","nan()","nan(-)"}) {
		double value = 0; const std::size_t length = std::strlen(text);
		const auto r = FloatFromChars(text,text+length,value);
		CHECK(r.ec == std::errc{} && std::isnan(value) && std::signbit(value) == (text[0] == '-'));
		const std::size_t consumed = std::strcmp(text,"NaN(abc_1)") == 0 || std::strcmp(text,"nan()") == 0 ? length : text[0] == '-' ? 4 : 3;
		CHECK_TEXT(r.ptr == text+consumed,text,"nan consumption");
	}
	double value = keep;
	const char one[] = "1";
	CHECK(FloatFromChars(one,one+1,value,std::chars_format::hex).ec == std::errc::invalid_argument && value == keep);
}

// Exact decimal arithmetic on digit strings for halfway cases.
static std::string Digits(double value) {
	// %.800e prints every digit of a binary64 value; drop the point and exponent.
	char text[1000];
#if TEST_STD_ORACLE
	const auto r = std::to_chars(text,text+sizeof(text),value,std::chars_format::scientific,800);
	CHECK(r.ec == std::errc{}); *r.ptr = 0;
#else
	std::snprintf(text,sizeof(text),"%.800e",value);
#endif
	std::string digits; digits += text[0]; digits.append(text+2,800);
	return digits + "e" + std::string(std::strchr(text,'e')+1);
}
static void HalfwayCases(double value) {
	const double next = std::nextafter(value,std::numeric_limits<double>::infinity());
	if (!std::isfinite(next)) return;
	// Both operands share value's decimal exponent unless next crosses a power
	// of ten; align next to value's exponent by prefixing zeros if needed.
	const std::string a = Digits(value), b = Digits(next);
	const int ea = std::atoi(a.c_str()+a.find('e')+1), eb = std::atoi(b.c_str()+b.find('e')+1);
	std::string da = a.substr(0,a.find('e')), db = b.substr(0,b.find('e'));
	if (eb > ea) { da.insert(da.begin(),char('0')); da.pop_back(); }
	const int exponent = eb > ea ? eb : ea;
	// (da + db) / 2 with one extra digit; the digits are exact for both inputs.
	std::string sum(da.size()+1,'0'); int carry = 0;
	for (std::size_t i = da.size(); i-- > 0;) { const int d = (da[i]-'0')+(db[i]-'0')+carry; sum[i+1] = char('0'+d%10); carry = d/10; }
	sum[0] = char('0'+carry);
	std::string half(sum.size()+1,'0'); int remainder = 0;
	for (std::size_t i = 0; i < sum.size(); ++i) { const int d = remainder*10+(sum[i]-'0'); half[i] = char('0'+d/2); remainder = d%2; }
	half[sum.size()] = char('0'+remainder*5);
	// half holds the midpoint's digits with the decimal point after half[1].
	const auto text = [&](const std::string& digits) { return digits.substr(0,2)+"."+digits.substr(2)+"e"+std::to_string(exponent); };
	const bool evenLow = (std::bit_cast<std::uint64_t>(value) & 1) == 0;
	const std::string tie = text(half);
	CHECK_TEXT(Same(ParseOurs(tie),evenLow ? value : next),tie,"tie to even");
	CHECK_TEXT(Same(ParseOurs(text(half+"0000000001")),next),tie,"just above halfway");
	// Just below: subtract one unit at a far digit (the midpoint ends in 5).
	std::string below = half+"0000000000"; std::size_t i = below.size();
	while (i-- > 0 && below[i] == '0') below[i] = '9';
	--below[i];
	CHECK_TEXT(Same(ParseOurs(text(below)),value),text(below),"just below halfway");
	// Past the 800-digit capacity only a sticky nonzero digit decides the tie.
	const std::string far = half+std::string(1200,'0')+"1";
	CHECK_TEXT(Same(ParseOurs(text(far)),next),text(far).substr(0,40),"sticky above halfway");
	CHECK_TEXT(Same(ParseOurs(text(half+std::string(1200,'0'))),evenLow ? value : next),tie,"long tie");
#if TEST_STD_ORACLE
	for (const std::string& t : {tie,text(below),text(far)}) {
		double theirs = 0; const auto r = std::from_chars(t.data(),t.data()+t.size(),theirs);
		CHECK_TEXT(r.ec == std::errc{} && Same(theirs,ParseOurs(t)),t.substr(0,60),"std halfway parse");
	}
#elif !defined(_WIN32)
	// UCRT's strtod rounds exact ties upward; Apple libc, glibc and bionic do not.
	for (const std::string& t : {tie,text(below),text(far)})
		CHECK_TEXT(Same(std::strtod(t.c_str(),nullptr),ParseOurs(t)),t.substr(0,60),"strtod halfway parse");
#endif
}

static std::uint64_t state = 0x9e3779b97f4a7c15ULL;
static std::uint64_t Random() { state ^= state << 13; state ^= state >> 7; state ^= state << 17; return state; }

int main(int argc, char** argv) {
	const unsigned count = argc > 1 ? unsigned(std::strtoul(argv[1],nullptr,10)) : 1500;
	Golden();
	Grammar();
	std::vector<double> values = {0.0,-0.0,1.0,-1.0,0.1,0.2,0.3,1.0/3,2.0/3,1e23,1e22,9007199254740993.0,9007199254740994.0,
		123456789012345680.0,1e-310,1e308,0.5,0.25,0.125,2.5,1.5,.1375,1.375,.025,.07500000000000001,1e12,-1e12,1e-7,1e-100,
		std::numeric_limits<double>::min(),std::nextafter(std::numeric_limits<double>::min(),1.0),
		std::nextafter(std::numeric_limits<double>::min(),0.0),std::numeric_limits<double>::denorm_min(),
		2*std::numeric_limits<double>::denorm_min(),std::numeric_limits<double>::max(),
		std::nextafter(std::numeric_limits<double>::max(),0.0),std::bit_cast<double>(std::uint64_t(0x10000000000001ULL))};
	for (int e = -1074; e <= 1023; e += 7) values.push_back(std::ldexp(1.0,e));
	for (int e = -323; e <= 308; e += 3) { const std::string t = "1e"+std::to_string(e); values.push_back(ParseOurs(t)); }
	for (unsigned i = 0; i < count; ++i) {
		std::uint64_t bits = Random();
		if ((bits & 0x7ff0000000000000ULL) == 0x7ff0000000000000ULL) continue;
		values.push_back(std::bit_cast<double>(bits));
		// Short authored decimals such as settings and slider steps.
		const std::string authored = std::to_string(Random()%2000000)+"e"+std::to_string(int(Random()%16)-12);
		values.push_back(ParseOurs(authored));
	}
	for (double value : values) CompareValue(value);
	for (double value : values) if (value > 0) HalfwayCases(value);
	// Integer-only conversion ignores FTZ/DAZ: subnormals survive both ways.
	{
		std::vector<std::string> gradual;
		for (double value : values) gradual.push_back(Ours(value,GeneralP,17)+" "+Ours(value,Plain)+" "+Ours(value,Fixed));
		Flush flush;
		for (std::size_t i = 0; i < values.size(); ++i) {
			const std::string text = Ours(values[i],GeneralP,17)+" "+Ours(values[i],Plain)+" "+Ours(values[i],Fixed);
			CHECK_TEXT(text == gradual[i],text.substr(0,60),gradual[i].substr(0,60));
			CHECK(Same(ParseOurs(Ours(values[i],Plain)),values[i]));
		}
	}
#if TEST_STD_ORACLE
	// LegacyGuiImport prints floats through the double overload: printf
	// promotes float to double, so %.9g is the same text either way.
	for (unsigned i = 0; i < count; ++i) {
		const float value = std::bit_cast<float>(static_cast<std::uint32_t>(Random()));
		if (!std::isfinite(value)) continue;
		char a[64], b[64];
		const auto x = std::to_chars(a,a+sizeof(a),value,std::chars_format::general,std::numeric_limits<float>::max_digits10);
		const auto y = FloatToChars(b,b+sizeof(b),double(value),std::chars_format::general,std::numeric_limits<float>::max_digits10);
		CHECK_TEXT(x.ec == y.ec && std::string(a,x.ptr) == std::string(b,y.ptr),std::string(b,y.ptr),std::string(a,x.ptr));
	}
	std::printf("UiFloatCharsTest: %u checks passed against the standard library\n",checks);
#else
	std::printf("UiFloatCharsTest: %u checks passed against printf/strtod\n",checks);
#endif
}
