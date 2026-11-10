subdir('yuv2rgb')

if host_machine.system() == 'windows'
  cdata.set('SDL_VIDEO_DRIVER_WINDOWS', 1)
  subdir('windows')
elif host_machine.system() == 'darwin'
  subdir('cocoa')
else
  cdata.set('SDL_VIDEO_DRIVER_WAYLAND', 1)
  subdir('wayland')
  x11_option = get_option('x11')
  if not x11_option.disabled()
    x11_dep = dependency('x11', required: x11_option)
    xext_dep = dependency('xext', required: x11_option)
    # xproto is required for some XInput2 functions.
    xproto_dep = dependency('xproto', required: x11_option)
    # SDL3 assumes XInput2 is always available when the X11 driver is built.
    xi_dep = dependency('xi', required: x11_option)

    if x11_dep.found() and xext_dep.found() and xproto_dep.found() and xi_dep.found()
      cdata.set('SDL_VIDEO_DRIVER_X11', 1)
      cdata.set('SDL_VIDEO_DRIVER_X11_XINPUT2', 1)
      sdl_deps += x11_dep
      sdl_deps += xext_dep
      sdl_deps += xproto_dep
      sdl_deps += xi_dep
      subdir('x11')
    endif
  endif
endif

sources += files(
  'SDL_RLEaccel.c',
  'SDL_blit.c',
  'SDL_blit_0.c',
  'SDL_blit_1.c',
  'SDL_blit_A.c',
  'SDL_blit_N.c',
  'SDL_blit_auto.c',
  'SDL_blit_copy.c',
  'SDL_blit_slow.c',
  'SDL_bmp.c',
  'SDL_clipboard.c',
  'SDL_egl.c',
  'SDL_fillrect.c',
  'SDL_pixels.c',
  'SDL_rect.c',
  'SDL_rotate.c',
  'SDL_stb.c',
  'SDL_stretch.c',
  'SDL_surface.c',
  'SDL_video.c',
  'SDL_video_unsupported.c',
  'SDL_vulkan_utils.c',
  'SDL_yuv.c',
)
