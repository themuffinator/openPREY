// Backend-owned readback of one ordinary presented frame. All calls run on the
// render thread. Poll never waits; the mapped bytes live until Release.
#ifndef OPENQ4_SAVE_PREVIEW_CAPTURE_H
#define OPENQ4_SAVE_PREVIEW_CAPTURE_H
bool RB_RequestSavePreview();
void RB_QueueSavePreview();
int RB_PollSavePreview( const byte *&pixels, int &width, int &height, bool &topDown, bool &bgra );
void RB_ReleaseSavePreview();
#endif
