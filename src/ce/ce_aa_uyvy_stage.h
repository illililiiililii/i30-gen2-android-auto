#ifndef I30_CE_AA_UYVY_STAGE_H
#define I30_CE_AA_UYVY_STAGE_H

#include "ce_aa_video.h"

#ifdef I30_VIDEO_UYVY_STAGING

#include "ce_aa_uyvy.h"

/* Padded top-down buffer used by the diagnostics-only receiver path. This is
 * not a DirectDraw surface and does not replace the GDI presentation path. */
enum {
    I30_UYVY_STAGE_PITCH = I30_VIDEO_WIDTH * 2U + 32U,
    I30_UYVY_STAGE_BYTES = I30_UYVY_STAGE_PITCH * I30_VIDEO_HEIGHT
};

typedef struct I30UyvyStage {
    uint8_t *surface;
    unsigned frames;
} I30UyvyStage;

/* Return 0 unconditionally so ce_aa_video.c keeps its existing BGRA/GDI
 * fallback. A successful pack is recorded in stage->frames for diagnostics. */
int i30_uyvy_stage(void *context, const I30VideoGeometry *geometry, const uint8_t *i420);

#endif

#endif
