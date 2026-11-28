#include "ce_aa_video.h"
#include "ce_aa_rgb565.h"

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

typedef struct Rgb565BitmapHeader {
    BitmapHeader info;
    uint32_t red, green, blue;
} Rgb565BitmapHeader;

_Static_assert(sizeof(BitmapHeader) == 40, "WinCE BITMAPINFOHEADER");
_Static_assert(sizeof(Rgb565BitmapHeader) == 52, "WinCE 16-bit BI_BITFIELDS header");

enum { I30_BI_BITFIELDS = 3U, I30_SRCCOPY = 0x00cc0020U };

int StretchDIBits(CE_HANDLE, int, int, int, int, int, int, int, int,
                  const void *, const BitmapHeader *, unsigned, uint32_t);

struct I30Video {
    storage_t decoder;
    unsigned picture;
    uint16_t *frame565;       /* Reused direct-conversion frame; never written during a blit. */
    uint32_t *bgra_fallback;  /* Allocated only when GDI rejects the 16-bit DIB. */
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
    video->frame565 = 0;
    video->bgra_fallback = 0;
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
        free(video->frame565);
        free(video->bgra_fallback);
        free(video);
    }
}

#ifdef I30_VIDEO_RGB565
/* Allocate the bounded 800x480 frame once per stream, never per frame. The
 * decoder is already restricted to this coded size by i30_video_push(). */
static uint16_t *frame565_buffer(I30Video *video)
{
    if (!video->frame565)
        video->frame565 = malloc(sizeof(uint16_t) * I30_VIDEO_WIDTH * I30_VIDEO_HEIGHT);
    return video->frame565;
}
#endif

#if defined(I30_VIDEO_RGB565) || defined(I30_VIDEO_UYVY_STAGING) || defined(I30_VIDEO_UYVY_DIRECTDRAW)
static uint32_t *bgra_fallback_buffer(I30Video *video)
{
    if (!video->bgra_fallback)
        video->bgra_fallback = malloc(sizeof(uint32_t) * I30_VIDEO_WIDTH * I30_VIDEO_HEIGHT);
    return video->bgra_fallback;
}
#endif

/* External symbol so ARM fixtures can time the direct color conversion. */
__attribute__((noinline)) void i30_yuv420_to_rgb565(unsigned width, unsigned height, const uint8_t *luma,
                          const uint8_t *cb, const uint8_t *cr, uint16_t *out)
{
    i30_yuv420_to_rgb565_impl(width, height, luma, cb, cr, out);
}

static int blit_bgra(const I30VideoTarget *target, const I30VideoGeometry *geometry, const void *pixels)
{
    const BitmapHeader info = {sizeof(info), (int32_t)geometry->coded_w, -(int32_t)geometry->coded_h,
                               1, 32, 0, geometry->coded_w * geometry->coded_h * 4U, 0, 0, 0, 0};
    CE_HANDLE dc = target->begin(target->context);
    if (!dc)
        return 0;
    OutputDebugStringW(L"i30 LCD blit begin\r\n");
    int painted = StretchDIBits(dc, 0, 0, I30_VIDEO_WIDTH, I30_VIDEO_HEIGHT,
                                (int)geometry->left, (int)geometry->top,
                                (int)geometry->width, (int)geometry->height,
                                pixels, &info, 0, I30_SRCCOPY);
    target->end(target->context, dc);
    OutputDebugStringW(L"i30 LCD blit end\r\n");
    return painted > 0 ? 1 : -1;
}

#ifdef I30_VIDEO_RGB565
static int paint_from_yuv565(I30Video *video, const I30VideoTarget *target,
                            const I30VideoGeometry *geometry, const uint8_t *data)
{
    uint16_t *pixels = frame565_buffer(video);
    const unsigned pixels_count = geometry->coded_w * geometry->coded_h;
    if (!pixels)
        return -1;
    const size_t chroma = (size_t)pixels_count / 4U;
    i30_yuv420_to_rgb565(geometry->coded_w, geometry->coded_h, data, data + pixels_count,
                         data + pixels_count + chroma, pixels);
    const Rgb565BitmapHeader info = {
        {sizeof(info.info), (int32_t)geometry->coded_w, -(int32_t)geometry->coded_h,
         1, 16, I30_BI_BITFIELDS, (uint32_t)pixels_count * 2U, 0, 0, 0, 0},
        I30_RGB565_RED_MASK, I30_RGB565_GREEN_MASK, I30_RGB565_BLUE_MASK};
    CE_HANDLE dc = target->begin(target->context);
    if (!dc)
        return 0;
    OutputDebugStringW(L"i30 LCD blit begin\r\n");
    int painted = StretchDIBits(dc, 0, 0, I30_VIDEO_WIDTH, I30_VIDEO_HEIGHT,
                                (int)geometry->left, (int)geometry->top,
                                (int)geometry->width, (int)geometry->height,
                                pixels, &info.info, 0, I30_SRCCOPY);
    target->end(target->context, dc);
    OutputDebugStringW(L"i30 LCD blit end\r\n");
    return painted > 0 ? 1 : -1;
}
#endif

#if defined(I30_VIDEO_RGB565) || defined(I30_VIDEO_UYVY_STAGING) || defined(I30_VIDEO_UYVY_DIRECTDRAW)
static int paint_from_yuv_bgra(I30Video *video, const I30VideoTarget *target,
                              const I30VideoGeometry *geometry, const uint8_t *data)
{
    uint32_t *pixels = bgra_fallback_buffer(video);
    if (!pixels)
        return -1;
    h264bsdConvertToBGRA(geometry->coded_w, geometry->coded_h, (u8 *)data, (u32 *)pixels);
    return blit_bgra(target, geometry, pixels);
}
#endif

#if !defined(I30_VIDEO_RGB565) && !defined(I30_VIDEO_UYVY_STAGING) && !defined(I30_VIDEO_UYVY_DIRECTDRAW)
static int paint_bgra(storage_t *decoder, const I30VideoTarget *target, const I30VideoGeometry *geometry)
{
    unsigned id, keyframe, errors;
    const u32 *pixels = h264bsdNextOutputPictureBGRA(decoder, &id, &keyframe, &errors);
    if (!pixels)
        return 0;
    return blit_bgra(target, geometry, pixels);
}
#endif

static int paint(I30Video *video, const I30VideoTarget *target)
{
    storage_t *decoder = &video->decoder;
    I30VideoGeometry geometry = {h264bsdPicWidth(decoder) * 16U, h264bsdPicHeight(decoder) * 16U, 0, 0, 0, 0};
    unsigned cropped, id, keyframe, errors;
    if (!geometry.coded_w || !geometry.coded_h ||
        geometry.coded_w > I30_VIDEO_WIDTH || geometry.coded_h > I30_VIDEO_HEIGHT)
        return -1;
    h264bsdCroppingParams(decoder, &cropped, &geometry.left, &geometry.width,
                          &geometry.top, &geometry.height);
    if (!cropped) {
        geometry.left = geometry.top = 0;
        geometry.width = geometry.coded_w;
        geometry.height = geometry.coded_h;
    }
    if (!geometry.width || !geometry.height || geometry.left >= geometry.coded_w ||
        geometry.width > geometry.coded_w - geometry.left || geometry.top >= geometry.coded_h ||
        geometry.height > geometry.coded_h - geometry.top)
        return -1;
    if (!target) {
        h264bsdNextOutputPicture(decoder, &id, &keyframe, &errors);
        return 0;
    }
#if defined(I30_VIDEO_RGB565) || defined(I30_VIDEO_UYVY_STAGING) || defined(I30_VIDEO_UYVY_DIRECTDRAW)
    const uint8_t *data = h264bsdNextOutputPicture(decoder, &id, &keyframe, &errors);
    if (!data)
        return 0;
#if defined(I30_VIDEO_UYVY_STAGING) || defined(I30_VIDEO_UYVY_DIRECTDRAW)
    if (target->present_yuv && target->present_yuv(target->context, &geometry, data))
        return 1;
#endif
#ifdef I30_VIDEO_RGB565
    int painted = paint_from_yuv565(video, target, &geometry, data);
    if (painted >= 0)
        return painted;
    OutputDebugStringW(L"i30 CE GDI rejected 16-bit DIB; using BGRA fallback.\r\n");
#endif
    return paint_from_yuv_bgra(video, target, &geometry, data);
#else
    return paint_bgra(decoder, target, &geometry);
#endif
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
