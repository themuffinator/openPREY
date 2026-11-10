#import "../posix/posix_public.h"

#import <Foundation/NSGeometry.h>
@class NSEvent;

#import <ApplicationServices/ApplicationServices.h>

// Native GL context state for the legacy native backend lives in
// macos_native_gl.h so the SDL3 release path never sees those tokens
// (docs/dev/macos-native-backend-containment-policy.md).

// sys

const char *macosx_scanForLibraryDirectory(void);

// In macosx_input.m
void Sys_InitInput(void);
void Sys_ShutdownInput(void);
CGDirectDisplayID Sys_DisplayToUse(void);
//extern void osxQuit();
void SetProgramPath(char *path);
void Sys_SetMouseInputRect(CGRect newRect);

void Sys_AnnoyingBanner();

// In macosx_glimp.m
bool Sys_Hide();
bool Sys_Unhide();

void Sys_PauseGL();
void Sys_ResumeGL();
