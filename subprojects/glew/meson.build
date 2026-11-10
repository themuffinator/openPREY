project(
  'glew',
  'c',
  default_options: ['default_library=static'],
)

glew_inc = include_directories('include')

glew_c_args = ['-DGLEW_NO_GLU']
if get_option('openq4_sdl3_loader')
  glew_c_args += ['-DOPENQ4_GLEW_SDL3_LOADER']
endif

glew_lib = static_library(
  'glew',
  files('src/glew.c'),
  include_directories: glew_inc,
  c_args: glew_c_args,
)

glew_dep = declare_dependency(
  include_directories: glew_inc,
  link_with: glew_lib,
)

glew_dedicated_dep = disabler()
if host_machine.system() == 'linux' or host_machine.system() == 'windows' or host_machine.system() == 'darwin'
  # Dedicated targets link no GL. Provide a small static GLEW variant that
  # resolves through openQ4's target-owned hook; the per-platform dedicated
  # GL stubs implement that hook without loading graphics code. The
  # SDL3-loader define also compiles out both wglew halves on Windows, and on
  # macOS it takes precedence over the NSGL branch so the Vulkan renderer
  # module never reaches for OpenGL.framework.
  glew_dedicated_lib = static_library(
    'glew_dedicated',
    files('src/glew.c'),
    include_directories: glew_inc,
    # GLAPI=extern: GL-free dedicated targets satisfy GL 1.1 references from
    # plain stub definitions, so the dllimport decoration must go
    c_args: ['-DGLEW_NO_GLU', '-DOPENQ4_GLEW_SDL3_LOADER', '-DGLAPI=extern'],
  )

  glew_dedicated_dep = declare_dependency(
    include_directories: glew_inc,
    link_with: glew_dedicated_lib,
  )
endif
