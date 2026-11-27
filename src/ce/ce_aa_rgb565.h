#ifndef I30_CE_AA_RGB565_H
#define I30_CE_AA_RGB565_H

#include <stddef.h>
#include <stdint.h>

/* WinCE 16-bit BI_BITFIELDS masks: little-endian RGB565 (BGR byte order in memory). */
enum {
    I30_RGB565_RED_MASK = 0xf800U,
    I30_RGB565_GREEN_MASK = 0x07e0U,
    I30_RGB565_BLUE_MASK = 0x001fU
};

/* Same integer coefficients and rounding as h264bsdConvertToBGRA, followed by
 * the standard 5/6/5 truncation. Kept in a host-compilable header so the pixel
 * layout can be unit tested without a Windows CE runtime. */
static inline uint16_t i30_yuv_pixel_rgb565(int c, int d, int e)
{
    int r = (298 * c + 409 * e + 128) >> 8;
    int g = (298 * c - 100 * d - 208 * e + 128) >> 8;
    int b = (298 * c + 516 * d + 128) >> 8;
    r = r < 0 ? 0 : (r > 255 ? 255 : r);
    g = g < 0 ? 0 : (g > 255 ? 255 : g);
    b = b < 0 ? 0 : (b > 255 ? 255 : b);
    return (uint16_t)(((unsigned)r >> 3) << 11 | ((unsigned)g >> 2) << 5 | ((unsigned)b >> 3));
}

/* Tight planar YUV420 (h264bsd DPB layout), tightly packed top-down RGB565.
 * Both chroma planes are sampled at col/2, row/2. Width and height are even. */
static inline void i30_yuv420_to_rgb565_impl(unsigned width, unsigned height,
                                             const uint8_t *luma, const uint8_t *cb,
                                             const uint8_t *cr, uint16_t *out)
{
    const unsigned chroma_width = width / 2U;
    for (unsigned row = 0; row < height; ++row) {
        const uint8_t *y = luma + (size_t)row * width;
        const uint8_t *u = cb + (size_t)(row / 2U) * chroma_width;
        const uint8_t *v = cr + (size_t)(row / 2U) * chroma_width;
        uint16_t *pixel = out + (size_t)row * width;
        for (unsigned col = 0; col < width; ++col) {
            const unsigned chroma_col = col / 2U;
            pixel[col] = i30_yuv_pixel_rgb565((int)y[col] - 16, (int)u[chroma_col] - 128,
                                               (int)v[chroma_col] - 128);
        }
    }
}

#endif
