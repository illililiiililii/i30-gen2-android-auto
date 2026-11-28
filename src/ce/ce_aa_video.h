#ifndef I30_CE_AA_VIDEO_H
#define I30_CE_AA_VIDEO_H

#include "ce_minimal.h"

enum { I30_VIDEO_WIDTH = 800, I30_VIDEO_HEIGHT = 480, I30_VIDEO_INPUT_LIMIT = 2 * 1024 * 1024 };

typedef struct I30Video I30Video;

typedef struct I30VideoGeometry {
    unsigned coded_w, coded_h, left, top, width, height;
} I30VideoGeometry;

typedef struct I30VideoTarget {
    void *context;
    CE_HANDLE (*begin)(void *context);
    void (*end)(void *context, CE_HANDLE dc);
#if defined(I30_VIDEO_UYVY_STAGING) || defined(I30_VIDEO_UYVY_DIRECTDRAW)
    /* Optional synchronous I420 consumer. Return 1 only when the caller has
     * visibly consumed the frame; 0 reuses this same decoded frame for GDI.
     * The decoder owns the input and may reuse it after this call. */
    int (*present_yuv)(void *context, const I30VideoGeometry *geometry, const uint8_t *i420);
#endif
} I30VideoTarget;

I30Video *i30_video_open(void);
void i30_video_close(I30Video *video);

/* Decode mutable Annex B data. A null target updates the decoder without presenting.
 * Return the number of pictures consumed by the target, or -1 on error. */
int i30_video_push(I30Video *video, const I30VideoTarget *target, uint8_t *bytes, unsigned size);

#endif
