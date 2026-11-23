#include "ce_aa_video.h"

#include "h264bsd_decoder.h"

#include <stddef.h>
#include <stdlib.h>

typedef struct BitmapHeader {
    uint32_t size;
    int32_t width, height;
    uint16_t planes, bits;
    uint32_t format, image_size;
    int32_t x_density, y_density;
    uint32_t colors_used, colors_important;
} BitmapHeader;

_Static_assert(sizeof(BitmapHeader) == 40, "WinCE BITMAPINFOHEADER");

int StretchDIBits(CE_HANDLE, int, int, int, int, int, int, int, int,
                  const void *, const BitmapHeader *, unsigned, uint32_t);

struct I30Video {
    storage_t decoder;
    unsigned picture;
};

/* Decoder allocations are process-local and bounded for the selected 800x480 profile. */
void *malloc(size_t size)
{
    if (!size || size > 4U * 1024U * 1024U)
        return 0;
    return HeapAlloc(GetProcessHeap(), 0, (uint32_t)size);
}

void free(void *memory)
{
    if (memory)
        HeapFree(GetProcessHeap(), 0, memory);
}

I30Video *i30_video_open(void)
{
    I30Video *video = malloc(sizeof(*video));
    if (!video)
        return 0;
    video->picture = 0;
    if (h264bsdInit(&video->decoder, 1) != H264BSD_RDY) {
        free(video);
        return 0;
    }
    return video;
}

void i30_video_close(I30Video *video)
{
    if (video) {
        h264bsdShutdown(&video->decoder);
        free(video);
    }
}

static int paint(I30Video *video, const I30VideoTarget *target)
{
    storage_t *decoder = &video->decoder;
    const unsigned coded_w = h264bsdPicWidth(decoder) * 16U;
    const unsigned coded_h = h264bsdPicHeight(decoder) * 16U;
    unsigned cropped, left, width, top, height, id, keyframe, errors;
    if (!coded_w || !coded_h || coded_w > I30_VIDEO_WIDTH || coded_h > I30_VIDEO_HEIGHT)
        return -1;
    h264bsdCroppingParams(decoder, &cropped, &left, &width, &top, &height);
    if (!cropped) {
        left = top = 0;
        width = coded_w;
        height = coded_h;
    }
    if (!width || !height || left >= coded_w || width > coded_w - left ||
        top >= coded_h || height > coded_h - top)
        return -1;
    if (!target) {
        h264bsdNextOutputPicture(decoder, &id, &keyframe, &errors);
        return 0;
    }
    const u32 *pixels = h264bsdNextOutputPictureBGRA(decoder, &id, &keyframe, &errors);
    if (!pixels)
        return 0;
    const BitmapHeader info = {sizeof(info), (int32_t)coded_w, -(int32_t)coded_h, 1, 32, 0,
        coded_w * coded_h * 4U, 0, 0, 0, 0};
    CE_HANDLE dc = target->begin(target->context);
    if (!dc)
        return 0;
    int painted = StretchDIBits(dc, 0, 0, I30_VIDEO_WIDTH, I30_VIDEO_HEIGHT,
                                (int)left, (int)top, (int)width, (int)height,
                                pixels, &info, 0, 0x00cc0020U);
    target->end(target->context, dc);
    return painted > 0 ? 1 : -1;
}

int i30_video_push(I30Video *video, const I30VideoTarget *target, uint8_t *bytes, unsigned size)
{
    int pictures = 0;
    unsigned stalled = 0;
    if (!video || !bytes || !size || size > I30_VIDEO_INPUT_LIMIT)
        return -1;
    while (size) {
        u32 used = 0;
        u32 result = h264bsdDecode(&video->decoder, bytes, size, video->picture, &used);
        if (result > H264BSD_HDRS_RDY || used > size || (!used && ++stalled > 2U))
            return -1;
        if (result == H264BSD_HDRS_RDY &&
            (h264bsdProfile(&video->decoder) != 66 ||
             h264bsdPicWidth(&video->decoder) > I30_VIDEO_WIDTH / 16U ||
             h264bsdPicHeight(&video->decoder) > I30_VIDEO_HEIGHT / 16U))
            return -1;
        if (result == H264BSD_PIC_RDY) {
            int frame = paint(video, target);
            if (frame < 0)
                return -1;
            pictures += frame;
            ++video->picture;
        }
        if (used) {
            stalled = 0;
            bytes += used;
            size -= used;
        }
    }
    return pictures;
}
