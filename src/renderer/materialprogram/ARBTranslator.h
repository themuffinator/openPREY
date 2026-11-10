// Copyright (C) 2026 DarkMatter Productions
#ifndef OPENQ4_MATERIALPROGRAM_ARBTRANSLATOR_H
#define OPENQ4_MATERIALPROGRAM_ARBTRANSLATOR_H

#include "GLSLCompiler.h"

#include <string>
#include <vector>

namespace oq4material {

// Where a translated program parameter takes its per-draw value from. ARB
// vertex and fragment programs have separate local and environment spaces.
enum class ARBParameterSpace { VertexLocal, VertexEnv, FragmentLocal, FragmentEnv };

struct ARBParameter {
    std::string name;   // generated uniform; bound to the slot at its index
    ARBParameterSpace space = ARBParameterSpace::VertexLocal;
    int index = 0;
};

struct ARBTranslateRequest {
    // Diagnostic names, normally the glprogs paths.
    std::string vertexName;
    std::string fragmentName;
    // Complete file contents. The section is selected the way the OpenGL
    // loader does it: the first !!ARBvp/!!ARBfp header up to the first END.
    // An empty source selects the fixed-function stage it replaces.
    std::string vertexSource;
    std::string fragmentSource;
};

struct ARBTranslation {
    // A compatibility GLSL pair with its bindings, ready for CompileGLSL.
    CompileRequest request;
    // parameters[i] is bound to uniform slot i.
    std::vector<ARBParameter> parameters;
    // Bit n is set when the fragment program samples texture[n].
    unsigned textureMask = 0;
    unsigned cubeTextureMask = 0;
    bool positionInvariant = false;
    std::string diagnostic;
};

// Translates ARB_vertex_program 1.0 and ARB_fragment_program 1.0 material
// programs into compatibility GLSL. Only the state a material stage actually
// has is accepted: matrix state, the engine's program environment, material
// parameters, 2D/cube textures and the attributes the engine supplies.
// Fixed-function lighting, fog, secondary color and other legacy state are
// rejected with a diagnostic instead of being replaced with dummy values.
bool TranslateARB(const ARBTranslateRequest &request, ARBTranslation &result);

// The OpenGL program environment that material stages see. Indices outside
// these sets have no defined value for a material stage.
bool ARBVertexEnvironmentDefined(int index);
bool ARBFragmentEnvironmentDefined(int index);

} // namespace oq4material
#endif
