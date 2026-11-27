#ifndef I30_CE_AA_UYVY_H
#define I30_CE_AA_UYVY_H

#include "ce_aa_video.h"

#include <stddef.h>

/* h264bsd produces tightly packed Y, Cb, Cr planes. Pack U Y0 V Y1 directly
 * into an already locked, top-down surface. Source and destination must not
 * overlap. Pitch and size are in bytes. Leave row padding untouched. */
static inline int i30_pack_uyvy(const I30VideoGeometry *frame, const uint8_t *i420,
                               uint8_t *surface, size_t size, size_t pitch)
{
    const size_t width = frame->width, height = frame->height;
    const size_t coded_w = frame->coded_w, coded_h = frame->coded_h;
    if (!i420 || !surface || !width || !height || !coded_w || !coded_h ||
        ((coded_w | coded_h | frame->left | width) & 1U) ||
        frame->left >= coded_w || width > coded_w - frame->left ||
        frame->top >= coded_h || height > coded_h - frame->top ||
        coded_h > SIZE_MAX / coded_w || width > SIZE_MAX / 2U)
        return 0;
    const size_t luma_size = coded_w * coded_h;
    const size_t row_size = width * 2U;
    if (luma_size > SIZE_MAX - luma_size / 2U || pitch < row_size ||
        size < row_size || height - 1U > (size - row_size) / pitch)
        return 0;

    for (size_t row = 0; row < height; ++row) {
        const size_t source_row = frame->top + row;
        const uint8_t *y = i420 + source_row * coded_w + frame->left;
        const uint8_t *u = i420 + luma_size + (source_row / 2U) * (coded_w / 2U) + frame->left / 2U;
        const uint8_t *v = u + luma_size / 4U;
        uint8_t *pixel = surface + row * pitch;
        for (size_t pair = 0; pair < width / 2U; ++pair) {
            pixel[0] = *u++;
            pixel[1] = *y++;
            pixel[2] = *v++;
            pixel[3] = *y++;
            pixel += 4;
        }
    }
    return 1;
}

#endif
