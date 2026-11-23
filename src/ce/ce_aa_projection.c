#include "ce_aa_projection.h"
#include "ce_aa_video.h"
#include "ce_aa_native_win.h"

CE_HANDLE GetForegroundWindow(void);
CE_HANDLE GetDC(CE_HANDLE);
CE_HANDLE GetDCEx(CE_HANDLE, CE_HANDLE, uint32_t);
int GetClipBox(CE_HANDLE, CeRect *);
int ReleaseDC(CE_HANDLE, CE_HANDLE);
void *LocalAlloc(uint32_t, uint32_t);
void *LocalFree(void *);

enum { VIDEO_CHANNEL = I30_PROJECTION_VIDEO_CHANNEL, CONTROL = 4, H264_BASELINE = 3 };
enum { OPEN = 7, CLOSE = 9, PING = 11, GOODBYE = 15, AUDIO_FOCUS_REQUEST = 18 };
enum { DATA = 0, CODEC = 1, SETUP = 0x8000, START = 0x8001, STOP = 0x8002, FOCUS = 0x8007 };
enum { PROJECTED = 1, NATIVE = 2, PROJECTED_NO_INPUT = 4 };
enum VideoState { ADVERTISED, OPENED, CONFIGURED, STREAMING };

typedef struct Projection {
    CE_HANDLE window;
    I30Video *decoder;
    enum VideoState state;
    uint32_t session;
    unsigned requested_focus, granted_focus;
    int rendered;
} Projection;

CE_HANDLE i30_projection_surface(void)
{
#ifdef I30_VIRTUAL_LCD_BENCH
    /* The isolated virtual-phone image owns the LCD for this test. */
    return (CE_HANDLE)1;
#else
    CE_HANDLE window = FindWindowW(I30_NAVIGATION_PROJECTION_CLASS, 0);
    if (window) {
        CeRect rect;
        return IsWindowVisible(window) && i30_stock_display_safe() &&
               i30_projection_above_map(window, GetWindow(window, CE_GW_OWNER)) &&
               GetClientRect(window, &rect) && rect.right - rect.left == I30_VIDEO_WIDTH &&
               rect.bottom - rect.top == I30_VIDEO_HEIGHT ? window : 0;
    }
    window = FindWindowW(L"I30.GD13MY.VideoSurface.1", 0);
    if (!window)
        window = FindWindowW(0, I30_PROJECTION_WINDOW_TITLE);
    return window && window == GetForegroundWindow() ? window : 0;
#endif
}

CE_HANDLE i30_projection_target(void)
{
#ifndef I30_VIRTUAL_LCD_BENCH
    CE_HANDLE window = FindWindowW(I30_NAVIGATION_PROJECTION_CLASS, 0);
    if (window)
        return GetWindow(window, CE_GW_OWNER) ? window : 0;
#endif
    return i30_projection_surface();
}

static int take_varint(const uint8_t **bytes, unsigned *size, uint32_t *value)
{
    *value = 0;
    for (unsigned shift = 0; shift < 32U && *size; shift += 7) {
        uint32_t byte = **bytes;
        ++*bytes;
        --*size;
        if (shift == 28U && byte > 15U)
            return 0;
        *value |= (byte & 127U) << shift;
        if (!(byte & 128U))
            return 1;
    }
    return 0;
}

static int fields(const uint8_t *bytes, unsigned size, uint32_t *field1, uint32_t *field2)
{
    unsigned seen = 0;
    while (size) {
        uint32_t tag, value;
        if (!take_varint(&bytes, &size, &tag) || tag < 8U)
            return -1;
        switch (tag & 7U) {
        case 0:
            if (!take_varint(&bytes, &size, &value))
                return -1;
            if (tag == 8U) {
                *field1 = value;
                seen |= 1U;
            } else if (tag == 16U) {
                *field2 = value;
                seen |= 2U;
            }
            break;
        case 1:
            if (size < 8)
                return -1;
            size -= 8;
            bytes += 8;
            break;
        case 2:
            if (!take_varint(&bytes, &size, &value) || value > size)
                return -1;
            size -= value;
            bytes += value;
            break;
        case 5:
            if (size < 4)
                return -1;
            size -= 4;
            bytes += 4;
            break;
        default:
            return -1;
        }
    }
    return (int)seen;
}

static void reset_video(Projection *video)
{
    i30_video_close(video->decoder);
    video->decoder = 0;
    video->requested_focus = 0;
    video->granted_focus = NATIVE;
}

static CE_HANDLE begin_paint(void *window)
{
#ifdef I30_VIRTUAL_LCD_BENCH
    (void)window;
    return GetDC(0);
#else
    if (i30_projection_surface() != window)
        return 0;
    if (window != FindWindowW(I30_NAVIGATION_PROJECTION_CLASS, 0))
        return GetDC(window);
    enum { DCX_CACHE = 2, DCX_CLIPSIBLINGS = 0x10, NULLREGION = 1 };
    CE_HANDLE dc = GetDCEx(window, 0, DCX_CACHE | DCX_CLIPSIBLINGS);
    CeRect visible;
    if (dc && (GetClipBox(dc, &visible) <= NULLREGION || !i30_stock_display_safe())) {
        ReleaseDC(window, dc);
        return 0;
    }
    return dc;
#endif
}

static void end_paint(void *window, CE_HANDLE dc)
{
#ifdef I30_VIRTUAL_LCD_BENCH
    (void)window;
    ReleaseDC(0, dc);
#else
    ReleaseDC(window, dc);
#endif
}

static int update_focus(const I30SecureChannel *wire, Projection *video, unsigned unsolicited)
{
    if (!video->requested_focus)
        return 1;
    unsigned focus = i30_projection_surface() == video->window ? video->requested_focus : NATIVE;
    if (unsolicited && focus == video->granted_focus)
        return 1;
    const uint8_t reply[] = {0x80, 8, 8, (uint8_t)focus, 16, (uint8_t)unsolicited};
    if (!wire->send(wire->context, VIDEO_CHANNEL, 0, reply, sizeof(reply)))
        return 0;
    if (unsolicited) {
        OutputDebugStringW(focus == NATIVE ? L"i30 CE projection yielded to the stock display.\r\n" :
                                             L"i30 CE projection resumed on its authorized surface.\r\n");
    }
    video->granted_focus = focus;
    return 1;
}

static int control(const I30SecureChannel *wire, Projection *video, unsigned code,
                   uint8_t *message, unsigned length)
{
    const uint8_t accepted[] = {0, 8, 8, 0};
    uint32_t priority = 0, service = 0;
    if (code == CLOSE) {
        reset_video(video);
        video->state = ADVERTISED;
        return 1;
    }
    if (code != OPEN || fields(message + 2, length - 2, &priority, &service) != 3 ||
        service != VIDEO_CHANNEL || video->state != ADVERTISED)
        return 0;
    video->state = OPENED;
    return wire->send(wire->context, VIDEO_CHANNEL, CONTROL, accepted, sizeof(accepted));
}

static int paint_packet(const I30SecureChannel *wire, Projection *video, unsigned code,
                        uint8_t *message, unsigned length)
{
    const unsigned prefix = code == DATA ? 10U : 2U;
    uint8_t ack[10] = {0x80, 4, 8};
    unsigned end = 3;
    uint32_t session = video->session;
    if (video->state != STREAMING || length <= prefix)
        return 0;
    const I30VideoTarget target = {video->window, begin_paint, end_paint};
    int can_paint = video->granted_focus != NATIVE && i30_projection_surface() == video->window;
    int rendered = i30_video_push(video->decoder, can_paint ? &target : 0, message + prefix, length - prefix);
    if (rendered < 0)
        return 0;
    if (rendered && !video->rendered) {
        video->rendered = 1;
        OutputDebugStringW(L"i30 CE projection frame presented.\r\n");
    }
    while (session >= 128U) {
        ack[end++] = (uint8_t)(session | 128U);
        session >>= 7;
    }
    ack[end++] = (uint8_t)session;
    ack[end++] = 16;
    ack[end++] = 1;
    return wire->send(wire->context, VIDEO_CHANNEL, 0, ack, end);
}

static int media(const I30SecureChannel *wire, Projection *video, unsigned code,
                 uint8_t *message, unsigned length)
{
    uint32_t one = 0, two = 0;
    if (code == DATA || code == CODEC)
        return paint_packet(wire, video, code, message, length);
    int present = fields(message + 2, length - 2, &one, &two);
    if (present < 0 || video->state == ADVERTISED)
        return 0;
    switch (code) {
    case SETUP: {
        const uint8_t config[] = {0x80, 3, 8, 2, 16, 1, 26, 1, 0};
        if (!(present & 1) || one != H264_BASELINE ||
            (video->state != OPENED && video->state != CONFIGURED))
            return 0;
        video->state = CONFIGURED;
        return wire->send(wire->context, VIDEO_CHANNEL, 0, config, sizeof(config));
    }
    case START:
        if (present != 3 || (one & 0x80000000U) || two || video->state != CONFIGURED)
            return 0;
        video->decoder = i30_video_open();
        video->session = one;
        video->state = STREAMING;
        return video->decoder != 0;
    case STOP:
        reset_video(video);
        video->state = OPENED;
        return 1;
    case FOCUS: {
        if (!(present & 2))
            return 0;
        video->requested_focus = (two == PROJECTED || two == PROJECTED_NO_INPUT) ? two : NATIVE;
        return update_focus(wire, video, 0);
    }
    default:
        return 0;
    }
}

int i30_projection_video(const I30SecureChannel *wire, CE_HANDLE window)
{
    const unsigned capacity = I30_VIDEO_INPUT_LIMIT + 10U;
    uint8_t *video_buffer = LocalAlloc(0, capacity);
    Projection video = { .window = window, .state = ADVERTISED, .granted_focus = NATIVE };
    int graceful = 0;
    if (!video_buffer)
        return 0;
    while (update_focus(wire, &video, 1)) {
        unsigned channel, flags, code;
        uint8_t *message;
        int size = wire->receive(wire->context, &channel, &flags, video_buffer, capacity, &message);
        if (size < 2)
            break;
        code = ((unsigned)message[0] << 8) | message[1];
        if (channel == 0 && !flags) {
            if (code == GOODBYE) {
                const uint8_t reply[] = {0, 16};
                graceful = wire->send(wire->context, 0, 0, reply, sizeof(reply));
                break;
            }
            if (code == PING) {
                message[1] = 12;
                if (!wire->send(wire->context, 0, 0, message, (unsigned)size))
                    break;
            } else if (code == AUDIO_FOCUS_REQUEST) {
                /* This service advertises only video. Leave the stock audio source in control. */
                const uint8_t reply[] = {0, 19, 8, 3, 16, 0};
                if (!wire->send(wire->context, 0, 0, reply, sizeof(reply)))
                    break;
            }
            continue;
        }
        if (channel != VIDEO_CHANNEL ||
            !(flags == CONTROL ? control(wire, &video, code, message, (unsigned)size) :
              !flags && media(wire, &video, code, message, (unsigned)size)))
            break;
    }
    reset_video(&video);
    LocalFree(video_buffer);
    return graceful;
}
