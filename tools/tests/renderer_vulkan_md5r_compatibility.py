#!/usr/bin/env python3
"""Regression contract for Vulkan-compatible MD5R runtime surfaces."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEST_PATH = "tools/tests/renderer_vulkan_md5r_compatibility.py"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def require(haystack: str, needle: str, context: str) -> None:
    if needle not in haystack:
        raise AssertionError(f"Missing {needle!r} in {context}")


def require_order(haystack: str, needles: tuple[str, ...], context: str) -> None:
    previous = -1
    for needle in needles:
        position = haystack.find(needle, previous + 1)
        if position == -1:
            raise AssertionError(f"Missing {needle!r} in {context}")
        if position <= previous:
            raise AssertionError(f"Expected ordered snippets in {context}: {needles!r}")
        previous = position


def braced_body(source: str, marker: str, context: str) -> str:
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"Missing {marker!r} in {context}")

    opening_brace = source.find("{", start + len(marker))
    if opening_brace == -1:
        raise AssertionError(f"Missing opening brace after {marker!r} in {context}")

    depth = 0
    for index in range(opening_brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"Could not find closing brace for {marker!r} in {context}")


def parenthesized_body(source: str, marker: str, context: str) -> str:
    start = source.find(marker)
    if start == -1:
        raise AssertionError(f"Missing {marker!r} in {context}")

    opening_parenthesis = source.find("(", start + len(marker))
    if opening_parenthesis == -1:
        raise AssertionError(f"Missing opening parenthesis after {marker!r} in {context}")

    depth = 0
    for index in range(opening_parenthesis, len(source)):
        char = source[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]

    raise AssertionError(f"Could not find closing parenthesis for {marker!r} in {context}")


def validate_vulkan_module_build_contract() -> None:
    meson = read("meson.build")
    require(
        meson,
        "renderer_gl_module_args = engine_cpp_args + [",
        "OpenGL renderer module build",
    )
    gl_target = parenthesized_body(
        meson,
        "renderer_gl_module_target = shared_module",
        "OpenGL renderer module target",
    )
    require(gl_target, "cpp_args: renderer_gl_module_args", "OpenGL renderer module target")
    require_order(
        meson,
        (
            "renderer_vk_module_args = engine_cpp_args + [",
            "'-DOPENQ4_RENDERER_VK_MODULE'",
            "renderer_vk_module_target = shared_module(",
        ),
        "Vulkan renderer module build",
    )
    if meson.count("'-DOPENQ4_RENDERER_VK_MODULE'") != 1:
        raise AssertionError("OPENQ4_RENDERER_VK_MODULE should be defined only for the Vulkan renderer module")

    target = parenthesized_body(
        meson,
        "renderer_vk_module_target = shared_module",
        "Vulkan renderer module target",
    )
    require(
        target,
        "cpp_args: renderer_vk_module_args",
        "Vulkan renderer module target",
    )
    if "cpp_args: engine_cpp_args" in target:
        raise AssertionError("renderer-vk must consume renderer_vk_module_args, not the shared engine argument list")

    for emitter in ("renderer_gl", "renderer_vk"):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "build" / "meson_sources.py"), "--emit", emitter],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"{emitter} source discovery failed:\n"
                f"{result.stdout}{result.stderr}"
            )

        sources = result.stdout.splitlines()
        if sources.count("src/renderer/Model_md5r.cpp") != 1:
            raise AssertionError(f"{emitter} must compile exactly one src/renderer/Model_md5r.cpp")


def validate_runtime_gate_helpers() -> None:
    source = read("src/renderer/Model_md5r.cpp")

    packed_gate = braced_body(
        source,
        "static ID_INLINE bool R_MD5R_UsePackedRuntimeSurfaces()",
        "MD5R packed-runtime helper",
    )
    require_order(
        packed_gate,
        (
            "#if defined( OPENQ4_RENDERER_VK_MODULE )",
            "return false;",
            "#else",
            "return true;",
            "#endif",
        ),
        "MD5R packed-runtime helper",
    )

    # A PBR-authored mesh keeps classic geometry on OpenGL too: the native
    # PBR owner lights idDrawVert streams, not md5r-program packed batches.
    mesh_gate = braced_body(
        source,
        "static ID_INLINE bool R_MD5R_MeshUsesPackedRuntimeSurface( const rvMD5RMesh &mesh )",
        "MD5R per-mesh packed-runtime helper",
    )
    require_order(
        mesh_gate,
        (
            "return R_MD5R_UsePackedRuntimeSurfaces()",
            "&& ( mesh.material == NULL || !mesh.material->HasPBR() );",
        ),
        "MD5R per-mesh packed-runtime helper",
    )

    tangent_gate = braced_body(
        source,
        "static ID_INLINE bool R_MD5R_DeferDynamicTangents()",
        "MD5R dynamic-tangent helper",
    )
    require_order(
        tangent_gate,
        (
            "#if defined( OPENQ4_RENDERER_VK_MODULE )",
            "return false;",
            "#else",
            "return r_useDeferredTangents.GetBool();",
            "#endif",
        ),
        "MD5R dynamic-tangent helper",
    )


def validate_static_surface_gate() -> None:
    source = read("src/renderer/Model_md5r.cpp")
    function = braced_body(
        source,
        "bool rvRenderModelMD5R::GenerateStaticSurfaces()",
        "MD5R static-surface generation",
    )
    gate = braced_body(
        function,
        "if ( R_MD5R_UsePackedRuntimeSurfaces() )",
        "MD5R static packed-surface gate",
    )

    require_order(
        function,
        (
            "FinishSurfaces( false );",
            "if ( R_MD5R_UsePackedRuntimeSurfaces() )",
            "tri->primBatchMesh =",
        ),
        "MD5R static-surface generation",
    )

    assignment_count = function.count("tri->primBatchMesh =")
    if assignment_count != 2:
        raise AssertionError(
            "GenerateStaticSurfaces should retain the two typed primBatchMesh assignment variants"
        )
    if gate.count("tri->primBatchMesh =") != assignment_count:
        raise AssertionError("Every static primBatchMesh attachment must remain inside the Vulkan compatibility gate")
    require(gate, "|| !R_MD5R_MeshUsesPackedRuntimeSurface( mesh ) ) {",
            "MD5R static packing skips PBR-authored meshes")


def validate_dynamic_surface_gate() -> None:
    source = read("src/renderer/Model_md5r.cpp")
    tri_surf_source = read("src/rendergeo/RenderGeometryTriSurf.cpp")
    update = braced_body(
        source,
        "bool rvRenderModelMD5R::UpdateDynamicSurface(",
        "MD5R dynamic-surface update",
    )

    require(
        update,
        "if ( skinScale == 0.0f\n"
        "\t\t&& R_MD5R_MeshUsesPackedRuntimeSurface( mesh )\n"
        "\t\t&& R_MD5R_UpdatePackedDynamicSurface(",
        "MD5R packed dynamic updater gate",
    )

    cleanup = braced_body(
        update,
        "if ( tri->primBatchMesh != NULL )",
        "MD5R partial packed-surface cleanup",
    )
    require_order(
        cleanup,
        (
            "R_FreeStaticTriSurf( tri );",
            "surface.geometry = NULL;",
            "tri = NULL;",
        ),
        "MD5R partial packed-surface cleanup",
    )
    require_order(
        update,
        (
            "R_MD5R_UpdatePackedDynamicSurface(",
            "if ( tri->primBatchMesh != NULL )",
            "if ( calculateTangents && !R_MD5R_DeferDynamicTangents() )",
            "R_DeriveTangents( tri );",
        ),
        "MD5R classic dynamic fallback",
    )

    generate = braced_body(
        source,
        "bool rvRenderModelMD5R::GenerateDynamicSurface(",
        "MD5R dynamic-surface generation",
    )
    require(
        generate,
        "bool canUsePackedDynamicSurface = skinScale == 0.0f\n"
        "\t\t&& R_MD5R_MeshUsesPackedRuntimeSurface( mesh )\n"
        "\t\t&& R_MD5R_CanUsePackedDynamicSurface(",
        "MD5R packed dynamic admission gate",
    )
    require_order(
        generate,
        (
            "const float skinScale = ent.shaderParms[ SHADERPARM_MD5_SKINSCALE ];",
            "bool canUsePackedDynamicSurface = skinScale == 0.0f",
            "if ( !canUsePackedDynamicSurface )",
            "if ( !BuildDynamicMeshTemplate( mesh ) )",
            "if ( !UpdateDynamicSurface(",
        ),
        "MD5R dynamic classicization path",
    )

    tri_surf_free = braced_body(
        tri_surf_source,
        "void R_ReallyFreeStaticTriSurf(",
        "triangle-surface ownership cleanup",
    )
    require_order(
        tri_surf_free,
        (
            "tri->deformedSurface && tri->primBatchMesh != NULL",
            "tri->numAllocedIndices > 0",
            "tri->ambientSurface == NULL || tri->indexes != tri->ambientSurface->indexes",
            "triIndexAllocator.Free( tri->indexes );",
            "tri->indexes = NULL;",
            "tri->numAllocedIndices = 0;",
            "if ( !tri->deformedSurface )",
        ),
        "packed dynamic MD5R index ownership cleanup",
    )
    require(
        tri_surf_source,
        "#if defined( _MD5R_SUPPORT ) || defined( Q4SDK_MD5R )\n"
        "\t// Dynamic packed MD5R surfaces own their materialized draw-index buffer,",
        "packed dynamic MD5R cleanup feature guard",
    )


def validate_skinning_fidelity() -> None:
    source = read("src/renderer/Model_md5r.cpp")

    blend_weights = braced_body(
        source,
        "static void R_MD5R_SetBlendWeights(",
        "MD5R packed blend-weight decoder",
    )
    require(
        blend_weights,
        "value[ dimension ] = 1.0f - explicitWeightSum;",
        "MD5R synthesized fourth blend weight",
    )
    if "ClampFloat" in blend_weights:
        raise AssertionError("Packed MD5R fourth-weight reconstruction must preserve the signed retail remainder")

    implicit_weight = braced_body(
        source,
        "static int R_MD5R_GetImplicitBlendWeightIndex(",
        "MD5R implicit blend-weight classification",
    )
    require_order(
        implicit_weight,
        (
            "vertexBuffer.hasLoadVertexFormat",
            "vertexBuffer.loadVertexFormat",
            "vertexBuffer.vertexFormat",
            "format.blendWeightDim >= 4",
            "format.blendWeightTransformCount != format.blendWeightDim + 1",
            "return format.blendWeightDim;",
        ),
        "MD5R implicit blend-weight classification",
    )

    skin_weight = braced_body(
        source,
        "static ID_INLINE float R_MD5R_GetSkinningBlendWeight(",
        "MD5R signed implicit blend weight",
    )
    require(
        skin_weight,
        "return influenceIndex == implicitWeightIndex\n"
        "\t\t? blendWeights[ influenceIndex ]\n"
        "\t\t: idMath::Fabs( blendWeights[ influenceIndex ] );",
        "MD5R signed implicit blend weight",
    )
    if skin_weight.count("idMath::Fabs( blendWeights[ influenceIndex ] )") != 1:
        raise AssertionError("Only authored MD5R blend weights may use magnitude normalization")

    skin_vertex = braced_body(
        source,
        "static bool R_MD5R_SkinVertexPosition(",
        "MD5R CPU skinning",
    )
    require_order(
        skin_vertex,
        (
            "const int implicitWeightIndex = R_MD5R_GetImplicitBlendWeightIndex( vertexBuffer );",
            "R_MD5R_GetSkinningBlendWeight( blendWeights, influenceIndex, implicitWeightIndex );",
            "skinnedPosition += weight * ( entJoints[ jointIndex ] * sourcePosition );",
            "totalWeight += idMath::Fabs( weight );",
            "skinnedPosition = entJoints[ jointIndex ] * sourcePosition;",
            "if ( skinScale != 0.0f )",
            "skinnedPosition *= skinScale;",
        ),
        "MD5R legacy skin-scale handling",
    )

    packed_skin_vertex = braced_body(
        source,
        "static bool R_MD5R_SkinVertexPositionFromPackedTransforms(",
        "MD5R packed-transform skinning",
    )
    require_order(
        packed_skin_vertex,
        (
            "const int implicitWeightIndex = R_MD5R_GetImplicitBlendWeightIndex( vertexBuffer );",
            "R_MD5R_GetSkinningBlendWeight( blendWeights, influenceIndex, implicitWeightIndex );",
            "skinnedPosition += weight * R_MD5R_TransformPackedPosition(",
            "totalWeight += idMath::Fabs( weight );",
        ),
        "MD5R packed-transform signed remainder handling",
    )


def validate_runtime_diagnostics() -> None:
    source = read("src/renderer/Model_md5r.cpp")
    print_function = braced_body(
        source,
        "void rvRenderModelMD5R::Print() const",
        "MD5R model diagnostics",
    )
    require(print_function, '"runtime surfaces: %s.\\n"', "MD5R model diagnostics")
    require(
        print_function,
        'R_MD5R_UsePackedRuntimeSurfaces() ? "packed primitive batches" : "classic Vulkan-compatible geometry"',
        "MD5R model diagnostics",
    )


def validate_native_file_loading() -> None:
    source = read("src/renderer/Model_md5r.cpp")
    model_manager = read("src/renderer/ModelManager.cpp")
    model_local = read("src/renderer/Model_local.h")
    lexer = read("src/idlib/Lexer.cpp")
    lexer_header = read("src/idlib/Lexer.h")
    render_world = read("src/renderer/RenderWorld_load.cpp")

    prebuilt_probe = braced_body(
        model_manager,
        "static bool R_ModelManager_FindLoadablePrebuiltMD5R(",
        "prebuilt MD5R probe",
    )
    require_order(
        prebuilt_probe,
        (
            'if ( cvarSystem->GetCVarBool( "com_binaryRead" ) )',
            "fileSystem->OpenFileRead( compiledName )",
            "fileSystem->OpenFileRead( md5rName )",
        ),
        "prebuilt MD5R probe",
    )

    load_model = braced_body(
        source,
        "void rvRenderModelMD5R::LoadModel()",
        "native MD5R loader",
    )
    require(load_model, "!parser->IsLoaded()", "native MD5R loader")
    if "parser->LoadFile(" in load_model:
        raise AssertionError("The filename lexer must not load the native MD5R source twice")

    parse_vertex_format = braced_body(
        source,
        "void rvRenderModelMD5R::ParseVertexFormat(",
        "MD5R vertex-format parser",
    )
    require(
        parse_vertex_format,
        "MD5R_VERTEX_DATA_UBYTEN, vertexFormat.blendIndexTokenType",
        "MD5R blend-index default",
    )
    if parse_vertex_format.count("MD5R_VERTEX_DATA_COLOR") != 2:
        raise AssertionError("Diffuse and specular colors must both default to the native Color datatype")

    parse_vertex_buffer = braced_body(
        source,
        "void rvRenderModelMD5R::ParseVertexBuffer(",
        "MD5R vertex-buffer parser",
    )
    require_order(
        parse_vertex_buffer,
        (
            'if ( parser.PeekTokenString( "}" ) )',
            "vertexBuffer.rebuildOnLoad = true;",
            "return;",
        ),
        "compressed MD5R rebuild marker",
    )
    require(model_local, "bool\t\t\t\t\t\trebuildOnLoad;", "MD5R vertex-buffer descriptor")

    decoder = braced_body(
        source,
        "static void R_MD5R_DecodePackedFloatComponents(",
        "native MD5R packed decoder",
    )
    require_order(
        decoder,
        (
            "case MD5R_VERTEX_DATA_UBYTEN:",
            "laneShifts[ 1 ] = 8;",
            "laneShifts[ 2 ] = 16;",
            "laneShifts[ 3 ] = 24;",
            "case MD5R_VERTEX_DATA_DEC_10_10_10N:",
            "laneShifts[ 0 ] = 20;",
            "laneShifts[ 1 ] = 10;",
            "1.0f / 511.0f",
        ),
        "native MD5R packed lane decoding",
    )

    writer = braced_body(
        source,
        "void rvRenderModelMD5R::WriteVertexFormat(",
        "MD5R vertex-format writer",
    )
    require(writer, '"%sSpecularColor Int\\n"', "MD5R vertex-format writer")
    require(writer, '"%sPointSize Float\\n"', "MD5R vertex-format writer")

    vertex_buffer_writer = braced_body(
        source,
        "void rvRenderModelMD5R::WriteVertexBuffer(",
        "MD5R vertex-buffer writer",
    )
    require_order(
        vertex_buffer_writer,
        (
            "vertexBuffer.rebuildOnLoad && !R_MD5R_HasResolvedVertexPayload(",
            "if ( writeEmptyRebuildPayload )",
            "return;",
            "for ( int vertexIndex = 0;",
        ),
        "unresolved compressed MD5R payload preservation",
    )

    binary_writer = braced_body(
        lexer,
        "void idLexer::WriteBinaryFile(",
        "binary-token companion writer",
    )
    if re.search(
        r'GetCVarBool\s*\(\s*"com_binaryread"\s*\)',
        binary_writer,
        flags=re.IGNORECASE,
    ):
        raise AssertionError("Requested binary companion writes must not depend on binary-read policy")
    require_order(
        binary_writer,
        (
            "idLexer src(filename, LEXFL_WRITEBINARY | swap, OSPath);",
            "while(src.ReadToken(&token))",
        ),
        "binary-token companion writer",
    )
    require(
        lexer_header,
        "WriteBinaryFile(char const * const filename, bool OSPath = false);",
        "binary-token companion writer declaration",
    )

    model_file_writer = braced_body(
        source,
        "bool rvRenderModelMD5R::WriteFile(",
        "MD5R file writer",
    )
    require_order(
        model_file_writer,
        (
            'idFile *outFile = fileSystem->OpenFileWrite( fileName, "fs_savepath" );',
            "if ( outFile == NULL )",
            "WriteModel( *outFile );",
            "fileSystem->CloseFile( outFile );",
            "if ( compressed )",
        ),
        "MD5R engine-owned file lifetime",
    )
    if "idAutoPtr<idFile>" in model_file_writer:
        raise AssertionError("Renderer modules must close engine-owned files through idFileSystem")
    if "outFile.reset" in model_file_writer or "delete outFile" in model_file_writer:
        raise AssertionError("Renderer modules must not destroy engine-owned files directly")
    if model_file_writer.count("fileSystem->CloseFile( outFile );") != 1:
        raise AssertionError("MD5R export must close its engine-owned file exactly once")
    model_compressed = braced_body(
        model_file_writer,
        "if ( compressed )",
        "compressed MD5R model export branch",
    )
    model_compressed_end = model_file_writer.find(model_compressed) + len(model_compressed)
    model_uncompressed = braced_body(
        model_file_writer[model_compressed_end:],
        "else",
        "uncompressed MD5R model export branch",
    )
    require_order(
        model_compressed,
        (
            'fileSystem->RelativePathToOSPath( fileName, "fs_savepath" )',
            "idLexer::WriteBinaryFile( savePathFileName.c_str(), true );",
        ),
        "compressed MD5R model export branch",
    )
    if "RemoveFile(" in model_compressed or "RemoveExplicitFile(" in model_compressed:
        raise AssertionError("Compressed MD5R model export must retain its newly written companion")
    require_order(
        model_uncompressed,
        (
            "idStr compiledFileName = fileName;",
            "compiledFileName += Lexer::sCompiledFileSuffix;",
            'fileSystem->RelativePathToOSPath( compiledFileName.c_str(), "fs_savepath" )',
            "fileSystem->RemoveExplicitFile( compiledSavePath.c_str() );",
        ),
        "uncompressed MD5R model export branch",
    )
    if "fileSystem->RemoveFile(" in model_uncompressed:
        raise AssertionError("Uncompressed MD5R model export must not remove a higher-priority cdpath companion")
    if "WriteBinaryFile(" in model_uncompressed:
        raise AssertionError("Uncompressed MD5R model export must not emit a compiled companion")

    world_file_writer = braced_body(
        render_world,
        "bool idRenderWorldLocal::WriteMD5R(",
        "MD5RProc file writer",
    )
    world_compressed = braced_body(
        world_file_writer,
        "if ( compressed )",
        "compressed MD5RProc export branch",
    )
    world_compressed_end = world_file_writer.find(world_compressed) + len(world_compressed)
    world_uncompressed = braced_body(
        world_file_writer[world_compressed_end:],
        "else",
        "uncompressed MD5RProc export branch",
    )
    require_order(
        world_compressed,
        (
            'fileSystem->RelativePathToOSPath( exportFilename.c_str(), "fs_savepath" )',
            "idLexer::WriteBinaryFile( savePathExportFilename.c_str(), true );",
        ),
        "compressed MD5RProc export branch",
    )
    if "RemoveFile(" in world_compressed or "RemoveExplicitFile(" in world_compressed:
        raise AssertionError("Compressed MD5RProc export must retain its newly written companion")
    require_order(
        world_uncompressed,
        (
            "idStr compiledExportFilename = exportFilename;",
            "compiledExportFilename += Lexer::sCompiledFileSuffix;",
            'fileSystem->RelativePathToOSPath( compiledExportFilename.c_str(), "fs_savepath" )',
            "fileSystem->RemoveExplicitFile( compiledSavePath.c_str() );",
        ),
        "uncompressed MD5RProc export branch",
    )
    if "fileSystem->RemoveFile(" in world_uncompressed:
        raise AssertionError("Uncompressed MD5RProc export must not remove a higher-priority cdpath companion")
    if "WriteBinaryFile(" in world_uncompressed:
        raise AssertionError("Uncompressed MD5RProc export must not emit a compiled companion")


def validate_ci_registration() -> None:
    validator = read("tools/validation/openq4_validate.py")
    commit = read(".github/workflows/commit-validation.yml")
    push = read(".github/workflows/push-verification.yml")

    if validator.count("renderer_vulkan_md5r_compatibility.py") != 1:
        raise AssertionError("Local validation runner must register the Vulkan MD5R compatibility test exactly once")

    for workflow, context in (
        (commit, "commit validation workflow"),
        (push, "push verification workflow"),
    ):
        if workflow.count(TEST_PATH) != 2:
            raise AssertionError(f"{context} must compile and directly run {TEST_PATH}")
        require(workflow, f"python {TEST_PATH}", context)


def main() -> None:
    validate_vulkan_module_build_contract()
    validate_runtime_gate_helpers()
    validate_static_surface_gate()
    validate_dynamic_surface_gate()
    validate_skinning_fidelity()
    validate_runtime_diagnostics()
    validate_native_file_loading()
    validate_ci_registration()
    print("renderer_vulkan_md5r_compatibility: ok")


if __name__ == "__main__":
    main()
