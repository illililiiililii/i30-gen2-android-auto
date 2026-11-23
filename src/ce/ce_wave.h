#ifndef I30_CE_WAVE_H
#define I30_CE_WAVE_H

#include <windows.h>
#include <mmsystem.h>

#define I30_WAVE_SLOTS 3
#define I30_PLAYBACK_BYTES 3840 /* 48 kHz stereo, 20 ms */
#define I30_CAPTURE_BYTES 640   /* 16 kHz mono, 20 ms */

/* Zero-initialize and retain storage until close succeeds. Call on one thread. */
typedef struct I30Playback {
    HWAVEOUT handle;
    UINT cursor;
    WAVEHDR slots[I30_WAVE_SLOTS];
    BYTE data[I30_WAVE_SLOTS][I30_PLAYBACK_BYTES];
} I30Playback;

typedef struct I30Capture {
    HWAVEIN handle;
    UINT cursor;
    WAVEHDR slots[I30_WAVE_SLOTS];
    BYTE data[I30_WAVE_SLOTS][I30_CAPTURE_BYTES];
} I30Capture;

MMRESULT i30_playback_query(UINT device);
MMRESULT i30_capture_query(UINT device);
MMRESULT i30_playback_open(I30Playback *out, UINT device, BOOL stock_granted);
MMRESULT i30_capture_open(I30Capture *in, UINT device, BOOL stock_granted);
MMRESULT i30_playback_write(I30Playback *out, const BYTE *pcm, DWORD size);
MMRESULT i30_capture_read(I30Capture *in, BYTE *pcm, DWORD capacity, DWORD *size);
MMRESULT i30_playback_close(I30Playback *out);
MMRESULT i30_capture_close(I30Capture *in);

#endif
