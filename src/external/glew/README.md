# Vendored GLEW

- Source: GLEW 2.3.1 (`glew-2.3.1.tgz`, nigels-com/glew), the newest upstream
  release.
- License: Modified BSD / MIT (see header banners).
- Contents: the generated `glew.h`, `wglew.h` and `glew.c`; `glxew.h` is only
  needed by the subproject copy's include tree.
- `src/renderer/qgl.h` includes `glew.h` from here, so this tree is the header
  source of truth for the engine and both renderer modules.
- Local deltas against the upstream release:
  - `glew.h` adds `#define GLEW_STATIC` (openQ4 links GLEW statically).
  - `glew.c` includes `"glew.h"` / `"wglew.h"` instead of `<GL/...>`, and adds
    the `OPENQ4_GLEW_SDL3_LOADER` path that routes proc-address lookup through
    `OpenQ4_GlewGetProcAddress` and compiles out the WGL and GLX loaders.
- The copy that actually compiles is `subprojects/glew/src/glew.c`; keep the two
  byte-identical. `tools/tests/linux_sdl3_glew_loader.py` pins the SDL3-loader
  markers in both files.
- Upstream's generated `glew.h` defines `GLEW_VERSION_MICRO 4` in the 2.3.1
  release even though the release is 2.3.1. That mismatch is upstream's, not a
  local edit — do not "correct" it.
