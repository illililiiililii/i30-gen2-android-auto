#ifndef I30_CE_AA_VIDEO_H
#define I30_CE_AA_VIDEO_H

#include "ce_minimal.h"

enum { I30_VIDEO_WIDTH = 800, I30_VIDEO_HEIGHT = 480, I30_VIDEO_INPUT_LIMIT = 2 * 1024 * 1024 };

typedef struct I30Video I30Video;

typedef struct I30VideoTarget {
    void *context;
    CE_HANDLE (*begin)(void *context);
    void (*end)(void *context, CE_HANDLE dc);
} I30VideoTarget;

I30Video *i30_video_open(void);
void i30_video_close(I30Video *video);

/* Decode mutable Annex B data. A null context updates the decoder without drawing.
 * Return the number of pictures painted, or -1 for a rejected stream or GDI error. */
int i30_video_push(I30Video *video, const I30VideoTarget *target, uint8_t *bytes, unsigned size);

#endif
