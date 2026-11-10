#!/usr/bin/env python3
"""Pin the MD5 to MD5R conversion that r_convertMD5toMD5R relies on.

Converted characters drew as black blobs on OpenGL and cast no shadow volumes.
The md5r vertex programs posed the bind-pose draw stream correctly, but
CopyPrimBatchTriangles copied the sil-trace buffer's bind-pose positions over
the skinned sil-trace verts, so every CPU consumer (bounds, culling, light
tris, shadow volumes, the classic draw paths) stayed on the bind pose. The old
converter also emitted a single prim batch of up to 256 joints with no basis,
colour or shadow stream, so the packed interaction and shadow draws could not
run, and the packed shadow draw bound the unskinned md5rshadow.vp for every
vertex format.

The converter now packs MD5 meshes the way retail does: prim batches of at most
25 joints (the env[0..74] palette), the bind-pose basis and colour on the draw
stream, the sil-trace view sharing it, a turbo shadow stream of two vertices
per sil-trace vertex, and silhouette edges renumbered per batch with cross-batch
edges left dangling on both sides.

r_convertStaticToMD5R crashed the OpenGL driver on the first frame. A packed
stage left buffer 0 bound, so the next stage's classic colour array took its
ambient-cache offset as a CPU address, and the packed stage draw never fed
md5rstdtex.vp the colours it reads. Converted static models also drew their
two-sided lit surfaces twice: the converter packs the back-side copies the
source's FinishSurfaces made, and GenerateStaticSurfaces then made more.
Retail keeps static surfaces 1:1 with the packed meshes.
"""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="latin-1")


def function_body(text: str, head: str) -> str:
    """Return the definition whose signature starts with head, skipping declarations."""
    match = re.search(re.escape(head) + r"[^;{}]*\{", text)
    if match is None:
        raise AssertionError(f"Missing definition of {head!r}")
    depth = 0
    for index in range(match.end() - 1, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[match.start() : index + 1]
    raise AssertionError(f"Unbalanced body for {head!r}")


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def require(text: str, needle: str, context: str) -> None:
    if needle not in text:
        raise AssertionError(f"{context}: missing {needle!r}")


def forbid(text: str, needle: str, context: str) -> None:
    if needle in text:
        raise AssertionError(f"{context}: still contains {needle!r}")


def require_ordered(text: str, needles: tuple[str, ...], context: str) -> None:
    position = 0
    for needle in needles:
        found = text.find(needle, position)
        if found < 0:
            raise AssertionError(f"{context}: missing {needle!r} after offset {position}")
        position = found + len(needle)


def validate_skinned_positions(source: str) -> None:
    copy = function_body(source, "bool rvRenderModelMD5R::CopyPrimBatchTriangles(")
    require_ordered(
        copy,
        (
            "const bool useSkinnedSilTraceVerts = ( silTraceVerts != NULL && joints.Num() > 0 );",
            "if ( useSkinnedSilTraceVerts ) {",
            "silTraceVertexBuffer = NULL;",
            "for ( int primBatchIndex = 0; primBatchIndex < mesh.primBatches.Num(); ++primBatchIndex ) {",
            "destVert.xyz = currentSilTraceVerts[ silTraceVertexIndex ].xyzw.ToVec3();",
        ),
        "CopyPrimBatchTriangles keeps a jointed model's skinned sil-trace positions",
    )

    packed = function_body(source, "static bool R_MD5R_UpdatePackedDynamicSurface(")
    require(
        compact(packed),
        "tri->tangentsCalculated = hasNormals && hasTangents && hasBinormals && ( !skinnedDrawStream || skinBasis );",
        "a skinned packed surface only claims a basis it skinned this frame",
    )
    require_ordered(
        packed,
        (
            "if ( skinBasis ) {",
            "R_MD5R_SkinVertexBasis( silTraceVertexBuffer, sourceVertexIndex, primBatch, entJoints, numJoints, posed )",
            "rawSilTraceVerts[ destVertexIndex ].xyzw.Set( posed.xyz.x, posed.xyz.y, posed.xyz.z, 1.0f );",
            "R_MD5R_CopyPrimBatchTriangles(",
            "tri->verts[ vertIndex ].normal = skinnedBasisVerts[ vertIndex ].normal;",
        ),
        "the packed update skins the converted basis with the sil-trace positions",
    )

    classic = function_body(source, "bool rvRenderModelMD5R::UpdateDynamicSurface(")
    require(
        compact(classic),
        "const bool skinBasis = skinScale == 0.0f && tri->numMirroredVerts == 0 "
        "&& R_MD5R_HasSkinnableBasis( drawVertexBuffer );",
        "the classic MD5R update skins the authored basis like idMD5Mesh",
    )
    require(classic, "if ( !gpuContractAttached && !skinBasis ) {", "classic update skips re-deriving a skinned basis")

    blend = function_body(source, "static bool R_MD5R_SkinVertexBasis(")
    require_ordered(
        blend,
        (
            "R_MD5R_GetSkinningBlendWeight( blendWeights, influenceIndex, implicitWeightIndex )",
            "idJointMat::Mad( blended, entJoints[ jointIndex ], weight );",
            "idJointMat::Mul( blended, entJoints[ jointIndex ], weight );",
            "vert.normal = blended * vertexBuffer.normals[ sourceVertexIndex ];",
            "vert.tangents[ 1 ] = blended * vertexBuffer.binormals[ sourceVertexIndex ];",
        ),
        "R_MD5R_SkinVertexBasis applies one blended joint matrix to position and basis",
    )


def validate_converter(source: str, local: str) -> None:
    require(
        local,
        "const int MD5R_MAX_PRIM_BATCH_TRANSFORMS = 25;",
        "Model_local.h prim-batch palette size",
    )
    require(
        local,
        "bool\t\t\t\t\t\tAppendConvertedMD5Mesh( const idMD5Mesh &sourceMesh, int meshIdentifier );",
        "Model_local.h converter member",
    )

    init = function_body(source, "bool rvRenderModelMD5R::InitFromMD5Model(")
    require(init, "AppendConvertedMD5Mesh( sourceModel.meshes[ meshIndex ], meshIndex )", "InitFromMD5Model")
    forbid(init, "bindPoseJoints", "InitFromMD5Model no longer re-skins the source to the bind pose")
    forbid(source, "R_MD5R_InitSkinnedVertexFormat", "Model_md5r.cpp drops the old basis-less format")

    draw_format = function_body(source, "static void R_MD5R_InitConvertedDrawVertexFormat(")
    for needle in (
        "vertexFormat.blendWeightDim = 3;",
        "vertexFormat.blendWeightTransformCount = 4;",
        "vertexFormat.hasNormal = true;",
        "vertexFormat.hasTangent = true;",
        "vertexFormat.hasBinormal = true;",
        "vertexFormat.hasDiffuseColor = true;",
        "vertexFormat.hasTexCoord[ 0 ] = true;",
    ):
        require(draw_format, needle, "converted draw stream format")
    shadow_format = function_body(source, "static void R_MD5R_InitConvertedShadowVertexFormat(")
    require(shadow_format, "vertexFormat.positionDim = blended ? 4 : 3;", "converted shadow stream format")

    append = function_body(source, "bool rvRenderModelMD5R::AppendConvertedMD5Mesh(")
    require_ordered(
        append,
        (
            "if ( batchTransformCount + numTriangleJoints <= MD5R_MAX_PRIM_BATCH_TRANSFORMS ) {",
            "batchFirstTri.Append( triIndex );",
        ),
        "the converter splits prim batches at the palette size",
    )
    for needle, context in (
        ("drawBuffer.normals[ drawIndex ] = normal;", "draw stream carries the bind-pose normal"),
        ("drawBuffer.binormals[ drawIndex ] = binormal;", "draw stream carries the bind-pose binormal"),
        ("drawBuffer.diffuseColors[ drawIndex ] = 0;", "draw stream carries the MD5 surface colour"),
        ("const float polarity = binormal * tangent.Cross( normal );", "four-bone face polarity"),
        ("( polarity < 0.0f ) ? -weights[ 0 ] : weights[ 0 ]", "polarity rides on the dominant draw weight"),
        ("const float implicitWeight = 1.0f - ( weights[ 0 ] + weights[ 1 ] + weights[ 2 ] );", "implicit fourth weight"),
        ("shadowBuffer.blendWeights[ shadowIndex ].Set( weights[ 0 ], weights[ 1 ], weights[ 2 ], implicitWeight );",
         "shadow weights stay unsigned for md5rshadow4.vp"),
        ("( ( pair == 0 ) ? 0xFF000000u : 0u )", "md5rshadow1.vp extrusion selector byte"),
        ("mesh.shadowVolVertexBuffer = shadowVertexBufferIndex;", "mesh names its shadow stream"),
        ("mesh.shadowVolIndexBuffer = -1;", "turbo shadow indices are built per light"),
        ("primBatch.silTraceGeoSpec = primBatch.drawGeoSpec;", "sil-trace view shares the draw stream"),
        ("primBatch.shadowVolGeoSpec.vertexStart = vertexStart * 2;", "turbo shadow pairs"),
        ("primBatch.shadowVolGeoSpec.vertexCount = vertexCount * 2;", "turbo shadow pairs"),
        ("silTraceIndexBuffer.indices[ index ] = cornerLocal[ index ];", "sil-trace indices are batch-local"),
        ("drawIndexBuffer.indices[ index ] = vertexStart + cornerLocal[ index ];", "draw indices are absolute"),
    ):
        require(append, needle, context)
    require_ordered(
        append,
        (
            "edge.p2 = secondFaceInBatch ? sourceEdge.p2 - firstTri : batchTriangles;",
            "edge.p1 = sourceEdge.p2 - firstTri;",
            "edge.p2 = batchTriangles;",
            "edge.v1 = sourceEdge.v2;",
            "edge.v2 = sourceEdge.v1;",
        ),
        "cross-batch silhouette edges dangle on both sides with each face's winding",
    )


def validate_cache(source: str) -> None:
    require(
        source,
        "static const unsigned int MD5R_MODEL_GENERATED_CACHE_PARSER_VERSION = 0x00030003U;",
        "converted payloads from the old layout are discarded",
    )
    validate = function_body(source, "static bool R_MD5RCacheValidateMesh(")
    require(validate, "R_MD5RCacheValidShadowBufferPair( mesh, vertexBuffers.Num(), indexBuffers.Num() )",
            "the cache accepts a turbo shadow stream without an index buffer")
    pair = function_body(source, "static bool R_MD5RCacheValidShadowBufferPair(")
    require(pair, "mesh.primBatches[batchIndex].shadowVolGeoSpec.primitiveCount != 0", "turbo shadow streams claim no primitives")
    parse = function_body(source, "void rvRenderModelMD5R::ParseMesh(")
    require(parse, "mesh.shadowVolIndexBuffer < -1", "the text loader reads a turbo shadow stream back")


def validate_backend() -> None:
    arb2 = read("src/renderer/draw_arb2.cpp")
    require(
        compact(arb2),
        "static_assert( ARB2_MD5R_MAX_PALETTE_TRANSFORMS == MD5R_MAX_PRIM_BATCH_TRANSFORMS,",
        "draw_arb2.cpp palette size matches the converter",
    )
    shadow = function_body(arb2, "static bool RB_ARB2_DrawPackedMD5RShadowBatches(")
    require_ordered(
        shadow,
        (
            "const program_t shadowProgram = RB_ARB2_GetMD5RVertexProgram( ARB2_MD5R_SHADOW_VOLUME_VPROG_BASE, vertexFormatIndex );",
            "R_BindARBProgram( GL_VERTEX_PROGRAM_ARB, shadowProgram, \"packed shadow vertex program\", false )",
            "RB_ARB2_LoadMD5RPaletteTransformRows(",
        ),
        "packed shadow batches pick md5rshadow1/4.vp by vertex format",
    )
    forbid(
        shadow,
        "R_BindARBProgram( GL_VERTEX_PROGRAM_ARB, ARB2_MD5R_SHADOW_VOLUME_VPROG_BASE,",
        "packed shadow batches never extrude a skinned stream with md5rshadow.vp",
    )

    turbo = read("src/renderer/tr_turboshadow.cpp")
    walls = function_body(turbo, "static int R_CreatePackedTurboShadowSideWalls(")
    require(walls, "|| sil.p2 > batchTriangleCount", "packed side walls accept the dangling sentinel")
    require(
        walls,
        "const int f2 = ( sil.p2 == batchTriangleCount ) ? 1 : batchFacing[ sil.p2 ];",
        "a dangling edge's missing face counts as lit",
    )


def validate_static_conversion(source: str, local: str) -> None:
    model = read("src/renderer/Model.cpp")
    require(
        compact(function_body(model, "void idRenderModelStatic::FinishSurfaces()")),
        "void idRenderModelStatic::FinishSurfaces() { FinishSurfaces( true ); }",
        "the virtual FinishSurfaces still makes back sides for every other model",
    )
    finish = function_body(model, "void idRenderModelStatic::FinishSurfaces( bool createBackSides )")
    require_ordered(
        finish,
        (
            "for ( i = 0 ; i < numOriginalSurfaces && createBackSides ; i++ ) {",
            "if ( surf->shader->ShouldCreateBackSides() ) {",
            "R_ReverseTriangles( newTri );",
            "R_CleanupTriangles(",
        ),
        "FinishSurfaces( false ) skips only the back-side copies",
    )
    require(local, "void\t\t\t\t\t\tFinishSurfaces( bool createBackSides );", "Model_local.h FinishSurfaces overload")

    generate = function_body(source, "bool rvRenderModelMD5R::GenerateStaticSurfaces()")
    require(generate, "FinishSurfaces( false );", "static MD5R surfaces stay 1:1 with the packed meshes")
    forbid(generate, "FinishSurfaces();", "GenerateStaticSurfaces never recreates back sides")

    arb2 = read("src/renderer/draw_arb2.cpp")
    bind = function_body(arb2, "static bool RB_ARB2_BindPackedMD5RStageVertexData(")
    require(compact(bind), "bool needsTangents, bool needsVertexColor ) {", "the packed stage bind owns the colour array")
    require_ordered(
        bind,
        (
            "idVertexCache::BindArrayBuffer( 0 );",
            "if ( needsVertexColor && hasVertexColors ) {",
            "glColorPointer( 4, GL_UNSIGNED_BYTE, sizeof( dword ), reinterpret_cast<const void *>( vertexBuffer.diffuseColors.Ptr() ) );",
            "glEnableClientState( GL_COLOR_ARRAY );",
            "} else {",
            "glDisableClientState( GL_COLOR_ARRAY );",
        ),
        "packed stages read the packed colours, never the caller's classic colour array",
    )
    prepare = function_body(arb2, "void RB_ARB2_PrepareStageTexturing(")
    require_ordered(
        prepare,
        (
            "const bool needsVertexColor = !fillingDepth && pStage->vertexColor != SVC_IGNORE;",
            "RB_ARB2_BindPackedMD5RStageVertexData( *drawVertexBuffer, vertexFormatIndex, "
            "needsTexCoord0, needsNormals, needsTangents, needsVertexColor )",
        ),
        "the stage's vertex-colour mode decides the packed colour source",
    )

    common = read("src/renderer/draw_common.cpp")
    passes = function_body(common, "void RB_STD_T_RenderShaderPasses(")
    require_ordered(
        passes,
        (
            "for ( stage = 0; stage < stageCount ; stage++ ) {",
            "if ( R_TriHasPrimBatchMesh( tri ) ) {",
            "ac = (idDrawVert *)vertexCache.Position( tri->ambientCache );",
            "glVertexPointer( 3, GL_FLOAT, sizeof( idDrawVert ), RB_DrawVertAttributePointer( ac, offsetof( idDrawVert, xyz ) ) );",
            "resetTexCoords = true;",
            "if ( resetTexCoords ) {",
            "RB_SetStageVertexColorPointer( surf, stage, ac );",
        ),
        "each stage rebinds the ambient cache before deriving classic pointers from ac",
    )


def validate_registration() -> None:
    validator = read("tools/validation/openq4_validate.py")
    require(validator, '"renderer_md5r_conversion_contract.py"', "openq4_validate.py")
    for workflow in (".github/workflows/commit-validation.yml", ".github/workflows/push-verification.yml"):
        text = read(workflow)
        require(text, "tools/tests/renderer_md5r_conversion_contract.py \\", workflow)
        require(text, "python tools/tests/renderer_md5r_conversion_contract.py", workflow)


def main() -> None:
    source = read("src/renderer/Model_md5r.cpp")
    local = read("src/renderer/Model_local.h")
    validate_skinned_positions(source)
    validate_converter(source, local)
    validate_cache(source)
    validate_backend()
    validate_static_conversion(source, local)
    validate_registration()
    print("renderer_md5r_conversion_contract: ok")


if __name__ == "__main__":
    main()
