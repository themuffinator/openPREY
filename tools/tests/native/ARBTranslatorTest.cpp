// Copyright (C) 2026 DarkMatter Productions
// Translates ARB_vertex_program/ARB_fragment_program material programs into
// compatibility GLSL and compiles them to SPIR-V with the in-process compiler.
// The fixtures are original; with --arb-dir the installed game's own glprogs
// are translated too, without copying their text anywhere.
#include "../../../src/renderer/materialprogram/ARBTranslator.h"
#include <cstdio>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>

namespace material = oq4material;
static int passed = 0;
static std::filesystem::path output;

static void Require(bool value, const std::string &description) {
    if (!value) { std::fprintf(stderr, "ARBTranslatorTest: %s\n", description.c_str()); std::exit(1); }
}

static bool Contains(const std::string &text, const std::string &part) { return text.find(part) != std::string::npos; }

static material::ARBTranslation Accept(const char *label, const std::string &vertex, const std::string &fragment) {
    material::ARBTranslateRequest request;
    request.vertexName = std::string("glprogs/") + label + ".vp";
    request.fragmentName = std::string("glprogs/") + label + ".fp";
    request.vertexSource = vertex;
    request.fragmentSource = fragment;
    material::ARBTranslation translation;
    Require(material::TranslateARB(request, translation), std::string(label) + ": translation failed: " + translation.diagnostic);
    material::CompileResult compiled;
    const bool ok = material::CompileGLSL(translation.request, compiled);
    if (!output.empty()) {
        std::ofstream(output / (std::string(label) + ".vert.glsl")) << translation.request.vertexSource;
        std::ofstream(output / (std::string(label) + ".frag.glsl")) << translation.request.fragmentSource;
    }
    Require(ok, std::string(label) + ": generated GLSL did not compile: " + compiled.diagnostic +
        "\n--- vertex ---\n" + translation.request.vertexSource + "\n--- fragment ---\n" + translation.request.fragmentSource);
    Require(compiled.vertex.size() > 5 && compiled.vertex[0] == 0x07230203 && compiled.fragment[0] == 0x07230203,
        std::string(label) + ": missing SPIR-V");
    Require(compiled.textureMask == translation.textureMask && compiled.cubeTextureMask == translation.cubeTextureMask,
        std::string(label) + ": texture reflection disagrees with the translation");
    // Every 2D lookup must honor the per-slot orientation of Vulkan-rendered
    // images; cube lookups never flip.
    const bool samples2D = (translation.textureMask & ~translation.cubeTextureMask) != 0;
    Require(Contains(compiled.fragmentSource, "oq4FlipTexture2D") == samples2D,
        std::string(label) + ": 2D lookups do not route through the orientation helpers");
    ++passed;
    return translation;
}

static void Reject(const char *label, const std::string &vertex, const std::string &fragment, const char *expected) {
    material::ARBTranslateRequest request;
    request.vertexName = "glprogs/reject.vp";
    request.fragmentName = "glprogs/reject.fp";
    request.vertexSource = vertex;
    request.fragmentSource = fragment;
    material::ARBTranslation translation;
    const bool translated = material::TranslateARB(request, translation);
    Require(!translated, std::string(label) + ": invalid program was accepted");
    Require(Contains(translation.diagnostic, expected),
        std::string(label) + ": diagnostic '" + translation.diagnostic + "' lacks '" + expected + "'");
    Require(translation.parameters.empty() && translation.request.vertexSource.empty(),
        std::string(label) + ": a failed translation published partial output");
    ++passed;
}

// A scrolling, distance-scaled refraction in the style of the stock heat
// effects, written for this test.
static const char *ScrollVertex = R"(!!ARBvp1.0
OPTION ARB_position_invariant;
# local[0] scroll, local[1] strength
PARAM unit = { 1, 0, 0, 1 };
TEMP eye, clip, w;
ADD result.texcoord[1], vertex.texcoord[0], program.local[0];
MOV eye, unit;
DP4 eye.z, vertex.position, state.matrix.modelview.row[2];
DP4 clip, eye, state.matrix.projection.row[0];
DP4 w, eye, state.matrix.projection.row[3];
MAX w, w, 1;
RCP w, w.w;
MUL clip, clip, w;
MIN clip, clip, 0.02;
MUL result.texcoord[2], clip, program.local[1];
MOV result.texcoord[0], vertex.texcoord;
END
)";

static const char *ScrollFragment = R"(!!ARBfp1.0
OPTION ARB_precision_hint_fastest;
TEMP normal, screen, mask;
PARAM bias = { -1, -1, -1, -1 };
PARAM two = 2;
TEX mask, fragment.texcoord[0], texture[2], 2D;
SUB mask.xy, mask, 0.01;
KIL mask;
TEX normal, fragment.texcoord[1], texture[1], 2D;
MOV normal.x, normal.a;
MAD normal, normal, two, bias;
MUL screen, fragment.position, program.env[1];
MAD_SAT screen, normal, fragment.texcoord[2], screen;
MUL screen, screen, program.env[0];
TEX result.color.xyz, screen, texture[0], 2D;
END
)";

// Every vertex instruction, relative addressing, matrix modifiers, ALIAS,
// OUTPUT and the engine's tangent attributes.
static const char *EveryVertexInstruction = R"(!!ARBvp1.0
ATTRIB pos = vertex.position;
ATTRIB tangent = vertex.attrib[9];
ATTRIB bitangent = vertex.attrib[10];
PARAM mvp[4] = { state.matrix.mvp };
PARAM rows[] = { program.local[0..3], { 0.5, 0.25 }, 3.0 };
PARAM inv = state.matrix.modelview.inverse.row[1];
PARAM it = state.matrix.modelview.invtrans.row[2];
PARAM tr = state.matrix.texture[0].transpose.row[0];
ADDRESS a0;
TEMP r0, r1, r2;
ALIAS t = r2;
OUTPUT oPos = result.position;
OUTPUT oCol = result.color;
DP4 oPos.x, mvp[0], pos;
DP4 oPos.y, mvp[1], pos;
DP4 oPos.z, mvp[2], pos;
DP4 oPos.w, mvp[3], pos;
ARL a0.x, program.local[4].x;
MOV r0, rows[a0.x + 1];
ADD r1, r0, -rows[a0.x - 1].yzwx;
ABS r1, r1;
DP3 r2.x, tangent, bitangent;
DPH r2.y, pos, inv;
DST r2, r0, r1;
EX2 r2.z, r0.y;
EXP r1, r0.x;
FLR r1, r1;
FRC r1.xy, r1;
LG2 r1.w, r0.z;
LIT r1, r0;
LOG r1, r0.w;
MAD t, r0, r1, it;
MAX t, t, tr;
MIN t, t, { 4, 4, 4, 4 };
MUL r0, r0, vertex.normal;
POW r0.x, r1.x, r2.y;
RCP r0.y, r0.z;
RSQ r0.z, r0.z;
SGE r1, r0, r2;
SLT r2, r0, r1;
SUB r0, r0, r2;
SWZ r1, r0, -x, 0, 1, w;
XPD r2.xyz, r0, r1;
MOV oCol, vertex.color;
MOV result.color.back, vertex.color.primary;
MOV result.texcoord[3], r2;
MOV result.texcoord[4], program.env[5];
MOV result.texcoord[5], program.env[6];
MOV result.fogcoord.x, r0.x;
END
)";

static const char *EveryFragmentInstruction = R"(!!ARBfp1.0
OPTION ARB_precision_hint_nicest;
ATTRIB uv = fragment.texcoord[3];
ATTRIB col = fragment.color.primary;
PARAM k[2] = { program.local[0], { 1, 2, 3 } };
TEMP r0, r1, r2;
OUTPUT out = result.color;
TEX r0, uv, texture[0], 2D;
TXP r1, uv, texture[0], 2D;
TXB r2, uv, texture[1], CUBE;
TXP r2, fragment.texcoord[4], texture[1], CUBE;
CMP r0, -r1, r2, k[1];
COS r1.x, r0.x;
SIN r1.y, r0.y;
SCS r2.xy, r0.z;
LRP r0, r1, r2, col;
POW r1.w, r0.x, r0.y;
RSQ r1.z, r1.w;
LIT r2, r1;
DP4 r2.w, r0, k[0];
XPD r0.xyz, r1, r2;
SWZ r1, r0, 1, -g, b, 0;
MAD_SAT r0, r0.wzyx, r1.x, fragment.texcoord[5];
MOV_SAT r1.rgb, r0;
MUL out, r0, r1;
MOV result.depth.z, fragment.position.z;
END
)";

static const char *FragmentOnly = R"(!!ARBfp1.0
TEMP c;
TEX c, fragment.texcoord[0], texture[3], 2D;
MUL result.color, c, fragment.color;
END
)";

static const char *VertexOnly = R"(!!ARBvp1.0
OPTION ARB_position_invariant;
MOV result.color, vertex.color;
END
)";

static std::string CombinedFile(const char *vertex, const char *fragment) {
    // Material .vfp files carry both programs; each loader picks its own.
    return std::string("# combined program\n") + vertex + "\n#=====\n" + fragment;
}

static std::string ReadFile(const std::filesystem::path &path) {
    std::ifstream file(path, std::ios::binary);
    std::ostringstream text;
    text << file.rdbuf();
    return text.str();
}

int main(int argc, char **argv) {
    std::filesystem::path arbDir;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--output" && i + 1 < argc) { output = argv[++i]; std::filesystem::create_directories(output); }
        else if (arg == "--arb-dir" && i + 1 < argc) { arbDir = argv[++i]; }
    }

    const std::string scroll = CombinedFile(ScrollVertex, ScrollFragment);
    auto haze = Accept("scroll", scroll, scroll);
    Require(haze.positionInvariant, "scroll: ARB_position_invariant was lost");
    Require(haze.textureMask == 0x7 && haze.cubeTextureMask == 0, "scroll: texture units");
    Require(haze.parameters.size() == 4, "scroll: expected four parameters");
    Require(haze.parameters[0].space == material::ARBParameterSpace::VertexLocal && haze.parameters[0].index == 0 &&
        haze.parameters[1].space == material::ARBParameterSpace::VertexLocal && haze.parameters[1].index == 1 &&
        haze.parameters[2].space == material::ARBParameterSpace::FragmentEnv && haze.parameters[2].index == 1 &&
        haze.parameters[3].space == material::ARBParameterSpace::FragmentEnv && haze.parameters[3].index == 0,
        "scroll: parameter spaces and order");
    Require(Contains(haze.request.vertexSource, "ftransform()"), "scroll: invariant position must use ftransform");
    Require(Contains(haze.request.fragmentSource, "discard"), "scroll: KIL must discard");
    Require(Contains(haze.request.fragmentSource, "clamp("), "scroll: _SAT must clamp");

    auto everything = Accept("every_instruction", EveryVertexInstruction, EveryFragmentInstruction);
    Require(!everything.positionInvariant, "every_instruction: explicit position");
    Require(everything.textureMask == 0x3 && everything.cubeTextureMask == 0x2, "every_instruction: 2D and cube units");
    Require(Contains(everything.request.vertexSource, "attribute vec3 attr_Tangent;") &&
        Contains(everything.request.vertexSource, "attribute vec3 attr_Bitangent;"), "every_instruction: tangent attributes");
    Require(Contains(everything.request.vertexSource, "arbInverse("), "every_instruction: inverse matrix helper");
    Require(Contains(everything.request.vertexSource, "gl_BackColor = arbOutBackColor"), "every_instruction: back color");
    Require(Contains(everything.request.fragmentSource, "gl_FragDepth"), "every_instruction: depth result");

    auto fragmentOnly = Accept("fragment_only", "", FragmentOnly);
    Require(fragmentOnly.positionInvariant && fragmentOnly.textureMask == 0x8, "fragment_only: fixed-function vertex stage");
    Require(Contains(fragmentOnly.request.vertexSource, "gl_TexCoord[0] = gl_TextureMatrix[0] * gl_MultiTexCoord0"),
        "fragment_only: fixed-function texture coordinates");
    auto vertexOnly = Accept("vertex_only", VertexOnly, "");
    Require(vertexOnly.textureMask == 0 && Contains(vertexOnly.request.fragmentSource, "gl_FragColor = gl_Color"),
        "vertex_only: fixed-function fragment stage");

    // A comment or identifier containing END truncates the program, as it
    // does in R_LoadARBProgram, so the truncated program must be rejected.
    Reject("end-in-comment", "", "!!ARBfp1.0\n# BLEND the result\nMOV result.color, fragment.color;\nEND\n", "END");
    Reject("missing-header", "", "MOV result.color, fragment.color;\nEND\n", "!!ARBfp");
    Reject("missing-end", "", "!!ARBfp1.0\nMOV result.color, fragment.color;\n", "END terminator");
    Reject("lighting-state", "!!ARBvp1.0\nOPTION ARB_position_invariant;\nMOV result.color, state.light[0].diffuse;\nEND\n", "",
        "fixed-function state");
    Reject("undefined-env", "!!ARBvp1.0\nOPTION ARB_position_invariant;\nMOV result.texcoord[0], program.env[3];\nEND\n", "",
        "program.env[3]");
    Reject("undefined-fragment-env", "", "!!ARBfp1.0\nMOV result.color, program.env[5];\nEND\n", "program.env[5]");
    Reject("rect-target", "", "!!ARBfp1.0\nTEX result.color, fragment.texcoord[0], texture[0], RECT;\nEND\n", "RECT");
    Reject("3d-target", "", "!!ARBfp1.0\nTEX result.color, fragment.texcoord[0], texture[0], 3D;\nEND\n", "3D");
    Reject("mixed-targets", "",
        "!!ARBfp1.0\nTEMP a;\nTEX a, fragment.texcoord[0], texture[1], 2D;\nTEX result.color, a, texture[1], CUBE;\nEND\n",
        "two different targets");
    Reject("fog-option", "", "!!ARBfp1.0\nOPTION ARB_fog_linear;\nMOV result.color, fragment.color;\nEND\n", "ARB_fog_linear");
    Reject("position-invariant-write",
        "!!ARBvp1.0\nOPTION ARB_position_invariant;\nMOV result.position, vertex.position;\nEND\n", "", "ARB_position_invariant");
    Reject("secondary-color", "", "!!ARBfp1.0\nMOV result.color, fragment.color.secondary;\nEND\n", "secondary");
    Reject("fogcoord", "", "!!ARBfp1.0\nMOV result.color, fragment.fogcoord;\nEND\n", "fragment.fogcoord");
    Reject("unsupported-attrib", "!!ARBvp1.0\nOPTION ARB_position_invariant;\nMOV result.texcoord[0], vertex.attrib[6];\nEND\n", "",
        "vertex.attrib[6]");
    Reject("vertex-blend", "!!ARBvp1.0\nOPTION ARB_position_invariant;\nMOV result.texcoord[0], vertex.weight;\nEND\n", "",
        "vertex.weight");
    Reject("undeclared", "", "!!ARBfp1.0\nMOV result.color, r9;\nEND\n", "undeclared");
    Reject("read-result", "", "!!ARBfp1.0\nOUTPUT o = result.color;\nMOV o, fragment.color;\nMOV result.color, o;\nEND\n",
        "cannot be read");
    Reject("vertex-only-opcode", "", "!!ARBfp1.0\nTEMP a;\nEXP a, fragment.color.x;\nMOV result.color, a;\nEND\n",
        "not valid in fragment programs");
    Reject("fragment-only-opcode", "!!ARBvp1.0\nOPTION ARB_position_invariant;\nTEMP a;\nKIL a;\nEND\n", "",
        "not valid in vertex programs");
    Reject("vertex-saturate", "!!ARBvp1.0\nOPTION ARB_position_invariant;\nMOV_SAT result.color, vertex.color;\nEND\n", "",
        "_SAT");
    Reject("unknown-opcode", "", "!!ARBfp1.0\nNRM result.color, fragment.color;\nEND\n", "unknown instruction NRM");
    Reject("array-size", "", "!!ARBfp1.0\nPARAM p[3] = { program.local[0..1] };\nMOV result.color, p[0];\nEND\n",
        "does not match");
    Reject("array-index", "", "!!ARBfp1.0\nPARAM p[2] = { program.local[0..1] };\nMOV result.color, p[2];\nEND\n",
        "out of range");
    Reject("texture-unit", "", "!!ARBfp1.0\nTEX result.color, fragment.texcoord[0], texture[8], 2D;\nEND\n", "texture image unit 8");
    Reject("version", "", "!!ARBfp2.0\nMOV result.color, fragment.color;\nEND\n", "ARBfp1.0");
    Reject("redeclared", "", "!!ARBfp1.0\nTEMP a;\nTEMP a;\nMOV result.color, fragment.color;\nEND\n", "already declared");
    Reject("both-empty", "", "", "no ARB program source");
    {
        // One distinct parameter more than the 32 uniform slots.
        std::string many = "!!ARBfp1.0\nTEMP a;\nMOV a, program.local[0];\n";
        for (int i = 1; i <= 32; ++i) { many += "ADD a, a, program.local[" + std::to_string(i) + "];\n"; }
        many += "MOV result.color, a;\nEND\n";
        Reject("parameter-capacity", "", many, "distinct program parameters");
    }

    int stock = 0;
    if (!arbDir.empty()) {
        // Every program file with both stages is translated and compiled in
        // place; the generated GLSL is written only when --output is given.
        for (const auto &entry : std::filesystem::directory_iterator(arbDir)) {
            const std::filesystem::path path = entry.path();
            const std::string ext = path.extension().string();
            if (ext != ".vfp" && ext != ".VFP") { continue; }
            const std::string text = ReadFile(path);
            if (text.find("!!ARBvp") == std::string::npos || text.find("!!ARBfp") == std::string::npos) { continue; }
            material::ARBTranslateRequest request;
            request.vertexName = request.fragmentName = path.filename().string();
            request.vertexSource = request.fragmentSource = text;
            material::ARBTranslation translation;
            if (!material::TranslateARB(request, translation)) {
                std::printf("ARBTranslatorTest: %s not translated: %s\n", path.filename().string().c_str(), translation.diagnostic.c_str());
                continue;
            }
            material::CompileResult compiled;
            Require(material::CompileGLSL(translation.request, compiled),
                path.filename().string() + ": translated program did not compile: " + compiled.diagnostic);
            if (!output.empty()) {
                std::ofstream(output / (path.stem().string() + ".vert.glsl")) << translation.request.vertexSource;
                std::ofstream(output / (path.stem().string() + ".frag.glsl")) << translation.request.fragmentSource;
            }
            std::printf("ARBTranslatorTest: compiled %s\n", path.filename().string().c_str());
            ++stock;
        }
    }
    std::printf("ARBTranslatorTest: %d cases passed%s\n", passed,
        arbDir.empty() ? "" : (", " + std::to_string(stock) + " installed programs compiled").c_str());
    return 0;
}
