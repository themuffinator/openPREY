#!/usr/bin/env python3
import json
from pathlib import Path
import re


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def read_repo_file(relative_path):
    return (Path(__file__).resolve().parents[2] / relative_path).read_text(encoding="utf-8")


def cxx_braced_block(source, start):
    """The source from start through the brace closing the first block opened after it."""
    assert_true(start >= 0, "the block's opening line should exist")
    open_brace = source.find("{", start)
    assert_true(open_brace >= 0, "the block should open a brace")
    depth = 0
    for index in range(open_brace, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise AssertionError("the block should close its brace")


def cxx_code(text):
    """C++ without comments or layout, to compare two copies of the same code."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    text = re.sub(r"//[^\n]*", " ", text)
    return " ".join(text.split())


def test_msaa_cvar_exposes_guarded_steps():
    init_cpp = read_repo_file(Path("src") / "renderer" / "RenderSystem_init.cpp")

    assert_true(
        'const char *r_multiSamplesArgs[] = { "0", "2", "4", "8", "16", NULL };' in init_cpp,
        "r_multiSamples completion should expose only supported MSAA steps",
    )
    assert_true(
        '"MSAA sample count: 0 = off, 2/4/8/16 = supported quality steps", 0, 16, idCmdSystem::ArgCompletion_String<r_multiSamplesArgs>' in init_cpp,
        "r_multiSamples should have an explicit 0..16 range and discrete completion",
    )


def test_msaa_cvar_normalizes_unsupported_values_before_gl_init():
    init_cpp = read_repo_file(Path("src") / "renderer" / "RenderSystem_init.cpp")

    assert_true("static int R_NormalizeMultiSamplesValue" in init_cpp, "renderer should normalize unsupported MSAA cvar values")
    for snippet in (
        "if ( samples <= 1 )",
        "return 0;",
        "if ( samples <= 2 )",
        "return 2;",
        "if ( samples <= 4 )",
        "return 4;",
        "if ( samples <= 8 )",
        "return 8;",
        "return 16;",
    ):
        assert_true(snippet in init_cpp, f"missing MSAA normalization branch {snippet!r}")
    assert_true(
        "const int normalizedMultiSamples = R_NormalizeMultiSamplesValue( originalMultiSamples );" in init_cpp,
        "display cvar normalization should apply the MSAA ladder",
    )
    assert_true(
        "r_multiSamples.SetInteger( normalizedMultiSamples );" in init_cpp,
        "unsupported r_multiSamples values should be rewritten before GL setup",
    )


def test_gfxinfo_reports_effective_aa_state():
    init_cpp = read_repo_file(Path("src") / "renderer" / "RenderSystem_init.cpp")

    assert_true("static void R_GfxInfoPrintAAState( void )" in init_cpp, "gfxInfo should have a dedicated AA state reporter")
    assert_true("R_GfxInfoGLMaxSamples" in init_cpp and "GL_MAX_SAMPLES" in init_cpp, "gfxInfo should report GL max MSAA samples")
    assert_true("R_GfxInfoPostAAName" in init_cpp, "gfxInfo should name post-AA modes")
    assert_true("SMAA1xMedium" in init_cpp and "SMAA1xUltra" in init_cpp and "SMAA1xColorPrototype" in init_cpp, "gfxInfo should use user-facing post-AA mode names")
    assert_true("modern-forward-resolve" in init_cpp and "modern-scene-single-sample" in init_cpp,
                "gfxInfo should distinguish an actual modern MSAA resolve from a single-sample frame")
    assert_true("&& R_ModernGLExecutor_Stats().modernVisibleExecuted" in init_cpp,
                "a rejected modern transaction must not suppress native AA reporting")
    assert_true("texture-msaa-unavailable" in init_cpp, "gfxInfo should explain unavailable texture MSAA")
    assert_true("gl-max-clamp" in init_cpp, "gfxInfo should report GL max sample clamping")
    # Once a main scene has drawn, gfxInfo reports the samples of the target it
    # drew into rather than r_multiSamples clamped to GL_MAX_SAMPLES: Xvfb's
    # sample-less window, a changed r_multiSamples awaiting vid_restart and the
    # game's forward target under supersampling all made that prediction wrong.
    observed_start = init_cpp.find("static bool R_GfxInfoObservedMSAA(")
    observed = init_cpp[observed_start:init_cpp.find("static void R_GfxInfoPrintAAState( void ) {")]
    assert_true(observed_start >= 0, "gfxInfo should report the main scene's observed MSAA")
    assert_true("if ( backEnd.mainSceneTargetContext != tr.glContextGeneration ) {\n\t\treturn false;" in observed,
                "only a main scene drawn in the current context should be observed")
    assert_true("const int targetSamples = backEnd.mainSceneTargetSamples;" in observed,
                "gfxInfo should report the recorded render texture samples")
    # Without multisample textures (Apple's GL 2.1 context) every render texture
    # is single-sample, so the scene is multisampled only when its view drew
    # straight into the window; report that instead of the requested count.
    assert_true('"default-framebuffer"' in observed and '"default-framebuffer-single-sample"' in observed,
                "gfxInfo should report window MSAA when the scene drew into the default framebuffer")
    window_branch = observed.find("if ( backEnd.mainSceneTargetIsWindow ) {")
    assert_true(0 <= window_branch < observed.find("R_DefaultFramebufferSamples()"),
                "gfxInfo should read the window's samples only for a scene that drew there")
    assert_true('"scene-target"' in observed and '"scene-target-single-sample"' in observed,
                "gfxInfo should explain a scene target whose samples differ from the request")
    # The modern executor reports its own resolve, and before any main scene has
    # drawn (startup self-tests) the count is still predicted.
    assert_true("mainSceneObserved = !modernVisiblePost && R_GfxInfoObservedMSAA(" in init_cpp,
                "the modern executor's resolve report should take precedence over the observed target")
    assert_true("if ( !mainSceneObserved && requestedMSAA > 1 ) {" in init_cpp,
                "gfxInfo should keep predicting MSAA until a main scene has drawn")
    draw_common = read_repo_file(Path("src") / "renderer" / "draw_common.cpp")
    draw_view = draw_common[draw_common.find("void\tRB_STD_DrawView( void ) {"):]
    target_chosen = draw_view.find("backEnd.renderTexture = rbSceneRenderTexture;")
    target_recorded = draw_view.find("backEnd.mainSceneTargetIsWindow = ( sceneTarget == NULL );")
    assert_true(0 <= target_chosen < target_recorded,
                "the main view should record its target after the renderer picks its own scene target")
    assert_true("? backEnd.renderTexture : R_GetDefaultRenderTarget();" in draw_view,
                "a VR frame's eye texture stands in for the window as the scene target")
    # A levelshot, envshot or light-grid capture renders its own view outside the
    # game's forward target; it must not replace the gameplay frame's record.
    assert_true("&& !tr.takingScreenshot && tr.tiledViewport[0] == 0 ) {" in draw_view,
                "screenshot and capture views should keep the gameplay frame's record")
    assert_true("backEnd.mainSceneTargetSamples = sceneColor != NULL ? Max( 0, sceneColor->GetOpts().numMSAASamples ) : 0;" in draw_view,
                "the main view should record its target's color samples")
    assert_true(
        "Renderer AA: MSAA requested=%d effective=%d reason=%s GL_MAX_SAMPLES=%s alphaToCoverage=%d PostAA=%d(%s) postAAEffective=%d postAAReason=%s screenFraction=%d%% supersampling=%s resolutionScaleMode=%d" in init_cpp,
        "gfxInfo should print the AA summary fields",
    )
    assert_true("R_GfxInfoPrintAAState();" in init_cpp, "gfxInfo should call the AA state reporter")


def test_gles_view_path_records_main_scene_target():
    # renderer-gles compiles RenderSystem_init.cpp but not draw_common.cpp, and
    # draws views through its own RB_DrawView. Without a copy of RB_STD_DrawView's
    # record, gfxInfo on an ES context only ever predicted the MSAA.
    draw_common = read_repo_file(Path("src") / "renderer" / "draw_common.cpp")
    gles_backend = read_repo_file(Path("src") / "renderer" / "GLES" / "gles_Backend.cpp")

    desktop_test = cxx_braced_block(
        draw_common, draw_common.find("static bool RB_IsMainScenePostProcessView( const viewDef_t *viewDef ) {"))
    gles_test = cxx_braced_block(
        gles_backend, gles_backend.find("static bool RB_GLES_IsMainScenePostProcessView( const viewDef_t *viewDef ) {"))
    assert_true(
        cxx_code(gles_test).replace("RB_GLES_IsMainScenePostProcessView", "RB_IsMainScenePostProcessView")
        == cxx_code(desktop_test),
        "the GLES main-view test should stay a copy of RB_IsMainScenePostProcessView")

    draw_view = draw_common[draw_common.find("void\tRB_STD_DrawView( void ) {"):]
    desktop_record = cxx_braced_block(draw_view, draw_view.find("if ( RB_IsMainScenePostProcessView( backEnd.viewDef )"))
    gles_view = cxx_braced_block(gles_backend, gles_backend.find("void RB_DrawView( const void *data ) {"))
    record_start = gles_view.find("if ( RB_GLES_IsMainScenePostProcessView( backEnd.viewDef )")
    gles_record = cxx_braced_block(gles_view, record_start)
    assert_true(
        cxx_code(gles_record).replace("RB_GLES_IsMainScenePostProcessView", "RB_IsMainScenePostProcessView")
        == cxx_code(desktop_record),
        "the GLES view path should record the main scene target exactly as RB_STD_DrawView does")
    for snippet, purpose in (
        ("&& !tr.takingScreenshot && tr.tiledViewport[0] == 0 ) {", "screenshots and captures keep the gameplay frame's record"),
        ("? backEnd.renderTexture : R_GetDefaultRenderTarget();", "the target choice stays RB_STD_DrawView's, VR stand-in included"),
        ("backEnd.mainSceneTargetContext = tr.glContextGeneration;", "the record belongs to the current context"),
        ("backEnd.mainSceneTargetIsWindow = ( sceneTarget == NULL );", "a scene drawn into the window reports the window's samples"),
        ("backEnd.mainSceneTargetSamples = sceneColor != NULL ? Max( 0, sceneColor->GetOpts().numMSAASamples ) : 0;",
         "the record keeps the target's color samples"),
    ):
        assert_true(snippet in gles_record, f"GLES record: {purpose}")

    # Recorded where RB_STD_DrawView would run, after the empty-view and
    # r_skipRender returns, and ahead of both ES paths: gles_d3 draws the view
    # itself and the modern executor's path falls through.
    skip_render = gles_view.find("if ( r_skipRender.GetBool() && backEnd.viewDef->viewEntitys ) {")
    gles_d3_draw = gles_view.find("RB_GLESD3_DrawView();")
    modern_path = gles_view.find("RB_GLES_ResolveSceneResolutionScale();")
    assert_true(0 <= skip_render < record_start < gles_d3_draw < modern_path,
                "the GLES view path should record each drawn main view before either backend draws it")
    # RB_DrawView must stay gles_d3's only entry, or a view could skip the record.
    renderer_root = Path(__file__).resolve().parents[2] / "src" / "renderer"
    callers = {
        path.relative_to(renderer_root).as_posix(): calls
        for path in renderer_root.rglob("*.cpp")
        if (calls := path.read_text(encoding="utf-8", errors="replace").count("RB_GLESD3_DrawView();"))
    }
    assert_true(callers == {"GLES/gles_Backend.cpp": 1},
                f"RB_GLESD3_DrawView should be called only from the GLES RB_DrawView, found {callers}")


def test_postaa_settings_surface_exposes_all_modes():
    repo_root = Path(__file__).resolve().parents[2]
    init_cpp = read_repo_file(Path("src") / "renderer" / "RenderSystem_init.cpp")
    system_gui = read_repo_file(Path("content") / "basepr" / "pak0" / "guis" / "mainmenu" / "mainmenu_options.guifragment")
    structure_md = read_repo_file(Path("docs/dev") / "settings-menu-structure.md")
    display_settings_md = read_repo_file(Path("docs/user") / "display-settings.md")
    registry = json.loads((repo_root / "docs/dev" / "settings-menu-registry.json").read_text(encoding="utf-8"))["settings"]

    assert_true(
        '"post AA mode: 0 = off, 1 = SMAA 1x medium, 2 = SMAA 1x high, 3 = SMAA 1x ultra, 4 = SMAA 1x colour-edge prototype", 0, 4' in init_cpp,
        "r_postAA should expose the full 0..4 mode range",
    )
    assert_true('values\t\t"0;1;2;3;4"' in system_gui, "Prey System menu Post AA choice should expose all modes")
    for language in ("english", "french", "italian", "spanish"):
        lang_file = read_repo_file(Path("content") / "basepr" / "pak0" / "strings" / f"{language}_openprey.lang")
        line = next((candidate for candidate in lang_file.splitlines() if '"#str_122024"' in candidate), "")
        assert_true(line.count(";") == 4, f"{language} Post AA choices should list five labels")

    postaa_entry = next((entry for entry in registry if entry.get("id") == "system.post_aa"), None)
    assert_true(postaa_entry is not None, "settings registry should include the Post AA entry")
    assert_true(postaa_entry["values"] == ["0", "1", "2", "3", "4"], "settings registry should list all Post AA values")
    assert_true(postaa_entry["cvar_range"] == {"low": "0", "high": "4"}, "settings registry should track the full r_postAA range")
    assert_true("`4 Color Edge`" in structure_md, "settings menu structure docs should mention the color-edge Post AA mode")
    assert_true("`4`: color-edge prototype" in display_settings_md, "display settings guide should document the color-edge Post AA mode")


def test_postaa_smaa_quality_presets_are_explicit_and_logged():
    edge_shader = read_repo_file(Path("content") / "basepr" / "pak0" / "glprogs" / "smaa_edge.fs")
    weights_shader = read_repo_file(Path("content") / "basepr" / "pak0" / "glprogs" / "smaa_weights.fs")
    render_system = read_repo_file(Path("src") / "renderer" / "RenderSystem.cpp")

    assert_true("postProcessSMAAQuality.Set( 0.0f, 0.10f, 8.0f, 2.0f );" in render_system, "SMAA should retain a safe medium-quality default")
    assert_true("quality.x" in edge_shader and "kEdgeModeColor" in edge_shader, "edge shader should consume the preset edge mode")
    assert_true("quality.y" in edge_shader, "edge shader should consume the preset edge threshold")
    assert_true("quality.w" in edge_shader, "edge shader should consume the preset local contrast scale")
    assert_true("quality.z" in weights_shader and "MaxSearchSteps()" in weights_shader, "weights shader should consume the preset search budget")


def test_sdl3_context_creation_has_msaa_fallback_ladder():
    # The context ladder itself lives in the renderer-gl module; the SDL calls
    # it drives stay in the platform backend behind the window-services seam.
    gl_module = read_repo_file(Path("src") / "renderer" / "OpenGL" / "gl_ContextSDL3.cpp")
    sdl3_backend = read_repo_file(Path("src") / "sys" / "sdl3" / "sdl3_backend.cpp")

    assert_true("static int SDL3_BuildMSAASampleFallbacks" in gl_module, "SDL3 backend should build an MSAA fallback ladder")
    assert_true("static const int sampleSteps[] = {16, 8, 4, 2, 0};" in gl_module, "SDL3 MSAA fallback ladder should descend 16 -> 8 -> 4 -> 2 -> 0")
    assert_true("SDL3_BuildFramebufferDesc(parms, candidate, candidateMultiSamples, framebufferDesc);" in gl_module, "SDL3 context attempts should apply the current MSAA fallback value")
    assert_true("SDL3: trying OpenGL context %s with MSAA samples=%d" in gl_module, "SDL3 should log the context/MSAA attempt")
    assert_true("SDL3: OpenGL context %s with MSAA samples=%d failed" in gl_module, "SDL3 should log failed context/MSAA attempts")
    assert_true("r_multiSamples.SetInteger(selectedMultiSamples);" in gl_module, "SDL3 fallback should update the effective r_multiSamples value")
    # The per-attempt sample count must actually reach SDL, or the ladder would
    # silently retry the same visual until it ran out of candidates.
    assert_true("SDL_GL_SetAttribute(SDL_GL_MULTISAMPLEBUFFERS, 1)" in sdl3_backend, "SDL3 backend should request a multisample buffer for the current ladder step")
    assert_true("SDL_GL_SetAttribute(SDL_GL_MULTISAMPLESAMPLES, desc->multiSamples)" in sdl3_backend, "SDL3 backend should request the current ladder step's sample count")


def test_sdl3_logs_requested_selected_and_actual_msaa_attributes():
    gl_module = read_repo_file(Path("src") / "renderer" / "OpenGL" / "gl_ContextSDL3.cpp")
    sdl3_backend = read_repo_file(Path("src") / "sys" / "sdl3" / "sdl3_backend.cpp")

    assert_true("GetGLAttribute(RENDER_GLATTR_MULTISAMPLE_BUFFERS, &multisampleBuffers)" in gl_module, "SDL3 should query actual multisample buffer count")
    assert_true("GetGLAttribute(RENDER_GLATTR_MULTISAMPLE_SAMPLES, &multisampleSamples)" in gl_module, "SDL3 should query actual multisample sample count")
    assert_true("case RENDER_GLATTR_MULTISAMPLE_BUFFERS:" in sdl3_backend and "SDL_GL_MULTISAMPLEBUFFERS; break;" in sdl3_backend, "SDL3 backend should map the multisample buffer selector onto SDL")
    assert_true("case RENDER_GLATTR_MULTISAMPLE_SAMPLES:" in sdl3_backend and "SDL_GL_MULTISAMPLESAMPLES; break;" in sdl3_backend, "SDL3 backend should map the multisample sample selector onto SDL")
    assert_true("SDL_GL_GetAttribute(sdlAttribute, outValue)" in sdl3_backend, "SDL3 backend should resolve GL attribute queries through SDL")
    assert_true("SDL3: reported OpenGL multisample attributes: requested=%d selected=%d actualBuffers=%s%d actualSamples=%s%d" in gl_module, "SDL3 should report requested, selected, and actual MSAA attributes")
    assert_true("SDL3_LogGLContextAttributes(requestedMultiSamples, selectedMultiSamples);" in gl_module, "SDL3 should pass requested/selected MSAA values into context logging")


def test_render_texture_failures_degrade_and_retry_msaa():
    # Keep the public game-side retry contract aligned with the engine's private
    # FBO lifecycle without exposing idImage implementation details to GameLibs.
    render_texture_h = read_repo_file(Path("src") / "renderer" / "RenderTexture.h")
    render_texture_cpp = read_repo_file(Path("src") / "renderer" / "OpenGL" / "gl_RenderTexture.cpp")
    render_system_cpp = read_repo_file(Path("src") / "renderer" / "RenderSystem.cpp")
    backend_cpp = read_repo_file(Path("src") / "renderer" / "tr_backend.cpp")
    game_render_system = read_repo_file(Path("src") / "renderer" / "RenderSystem.h")

    assert_true("bool\t\t\t\t\tInitRenderTexture(void);" in render_texture_h, "FBO initialization should report success")
    assert_true("R_FramebufferStatusName" in render_texture_cpp, "FBO failures should name the framebuffer status")
    assert_true("GL_FRAMEBUFFER_INCOMPLETE_MULTISAMPLE" in render_texture_cpp, "FBO diagnostics should identify multisample mismatch")
    assert_true("GL context: vendor=" in render_texture_cpp, "FBO diagnostics should include renderer context")
    assert_true("R_ReportFramebufferAttachment" in render_texture_cpp, "FBO diagnostics should describe attachments")
    assert_true("return FailFramebuffer( framebufferStatus" in render_texture_cpp, "incomplete FBOs should take the recoverable failure path")
    assert_true("Failed to create rendertexture" not in render_texture_cpp, "FBO incompleteness must not remain fatal")
    assert_true("if ( !renderTexture->InitRenderTexture() )" in render_system_cpp, "render-system creation should reject incomplete FBOs")
    assert_true("delete renderTexture;" in render_system_cpp and "return NULL;" in render_system_cpp, "failed initial FBOs should be destroyed and returned as NULL")
    assert_true("R_IsRenderTextureFailureLatched" in render_system_cpp, "unchanged rejected attachment sets should not retry every frame")
    assert_true("GetStorageGeneration()" in render_system_cpp and "contextGeneration" in render_system_cpp, "failure latch should retry after storage or context changes")
    assert_true("idRenderTexture*& renderTexture" in render_system_cpp, "resize failure should be able to clear the owner's target pointer")
    assert_true("renderTexture = NULL;" in render_system_cpp and "DestroyRenderTexture( failedRenderTexture );" in render_system_cpp, "failed resized targets should be retired instead of remaining non-null")
    assert_true("cmd->msaaRenderTexture == NULL || cmd->destRenderTexture == NULL" in backend_cpp, "MSAA resolve should guard missing targets")
    assert_true("!cmd->msaaRenderTexture->EnsureDeviceHandle()" in backend_cpp, "MSAA resolve should guard unusable targets")

    assert_true("virtual int\t\t\t\tGetImageMSAASamples" in game_render_system, "renderer API should expose allocated sample count narrowly")


def main():
    test_msaa_cvar_exposes_guarded_steps()
    test_msaa_cvar_normalizes_unsupported_values_before_gl_init()
    test_gfxinfo_reports_effective_aa_state()
    test_gles_view_path_records_main_scene_target()
    test_postaa_settings_surface_exposes_all_modes()
    test_postaa_smaa_quality_presets_are_explicit_and_logged()
    test_sdl3_context_creation_has_msaa_fallback_ladder()
    test_sdl3_logs_requested_selected_and_actual_msaa_attributes()
    test_render_texture_failures_degrade_and_retry_msaa()
    print("renderer_msaa_cvar_safety: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
