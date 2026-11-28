#ifndef I30_CE_AA_UYVY_DDRAW_H
#define I30_CE_AA_UYVY_DDRAW_H

#include "ce_aa_video.h"

/* Opt-in WinCE 6.0 UYVY DirectDraw output. Nothing in this file is compiled
 * unless I30_VIDEO_UYVY_DIRECTDRAW is selected by the build tool. The backend
 * uses only IDirectDraw / IDirectDrawSurface and the CE6 108-byte
 * DDSURFACEDESC; it deliberately avoids the desktop 2/4/5/7 interfaces. */
typedef struct I30Ddraw {
    void *module;
    void *dd;
    void *primary;
    void *overlay;
    void *back;
    void *front;              /* Surface currently owned by the overlay chain. */
    void *write;              /* Surface unlocked and packed this frame. */
    uint32_t surface_size;
    int32_t pitch;
    int32_t x_pitch;
    unsigned restored;
    unsigned failures;
    unsigned presented;
    unsigned flips;
    unsigned flip_pending;
    int flip;
    int shown;
    int needs_restore;
    int disabled;
} I30Ddraw;

int i30_ddraw_open(CE_HANDLE window, I30Ddraw *ddraw);
int i30_ddraw_ready(const I30Ddraw *ddraw);
int i30_ddraw_present(void *context, const I30VideoGeometry *geometry, const uint8_t *i420);
void i30_ddraw_hide(I30Ddraw *ddraw);
void i30_ddraw_close(I30Ddraw *ddraw);

#endif
