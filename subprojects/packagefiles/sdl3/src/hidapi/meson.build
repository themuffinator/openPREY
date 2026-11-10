if host_machine.system() == 'windows'
  subdir('windows')
elif host_machine.system() == 'darwin'
  #  subdir('mac')
else
  subdir('linux')
endif

sources += files('SDL_hidapi.c')
