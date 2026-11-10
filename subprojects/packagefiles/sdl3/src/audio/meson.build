if host_machine.system() == 'windows'
  cdata.set('SDL_AUDIO_DRIVER_DSOUND', 1)
  #  cdata.set('SDL_AUDIO_DRIVER_WASAPI', 1)
  subdir('directsound')
  #  subdir('wasapi')
elif host_machine.system() == 'darwin'
  cdata.set('SDL_AUDIO_DRIVER_COREAUDIO', 1)
  subdir('coreaudio')
else
  cdata.set('SDL_AUDIO_DRIVER_PIPEWIRE', 1)
  subdir('pipewire')
endif

# SDL's opt-in dummy driver supplies silence for automated capture lifecycle
# tests. It is never selected as a fallback for a physical microphone.
cdata.set('SDL_AUDIO_DRIVER_DUMMY', 1)
sources += files('dummy/SDL_dummyaudio.c')

sources += files(
  'SDL_audio.c',
  'SDL_audiocvt.c',
  'SDL_audiodev.c',
  'SDL_audioqueue.c',
  'SDL_audioresample.c',
  'SDL_audiotypecvt.c',
  'SDL_mixer.c',
  'SDL_wave.c',
)
