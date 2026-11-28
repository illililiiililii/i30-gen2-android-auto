#include "ce_aa_video.h"

#ifdef I30_VIDEO_UYVY_STAGING
#include "ce_aa_uyvy.h"
#endif
#ifdef I30_VIDEO_UYVY_DIRECTDRAW
#include "ce_aa_uyvy_ddraw.h"
#endif

CE_HANDLE GetDC(CE_HANDLE window);
int ReleaseDC(CE_HANDLE window, CE_HANDLE dc);

static CE_HANDLE begin_paint(void *context)
{
    (void)context;
    return GetDC(0);
}

static void end_paint(void *context, CE_HANDLE dc)
{
    (void)context;
    ReleaseDC(0, dc);
}

#ifdef I30_VIDEO_UYVY_STAGING
enum { UYVY_PITCH = I30_VIDEO_WIDTH * 2 + 32, UYVY_BYTES = UYVY_PITCH * I30_VIDEO_HEIGHT };

typedef struct UyvyStage {
    uint8_t *bytes;
    unsigned frames;
} UyvyStage;

static int stage_uyvy(void *context, const I30VideoGeometry *geometry, const uint8_t *i420)
{
    UyvyStage *stage = context;
    if (!i30_pack_uyvy(geometry, i420, stage->bytes, UYVY_BYTES, UYVY_PITCH))
        return 0;
    ++stage->frames;
    return 1;
}
#endif

/* Bench-only entry. A projection session supplies its display context and USB payload. */
void i30_ce_entry(void)
{
    CE_HANDLE file = CreateFileW(L"\\DiskA\\Application\\NAVI\\i30-video.h264", 0x80000000U, 1, 0, 3, 0x80, 0);
    CE_HANDLE heap = GetProcessHeap();
    int painted = 0;
    if (file != (CE_HANDLE)-1) {
        uint32_t length = 0, surplus = 0;
        uint8_t trailing;
        uint8_t *bytes = HeapAlloc(heap, 0, I30_VIDEO_INPUT_LIMIT);
        if (bytes && ReadFile(file, bytes, I30_VIDEO_INPUT_LIMIT, &length, 0) && length &&
            ReadFile(file, &trailing, 1, &surplus, 0) && !surplus) {
            I30Video *video = i30_video_open();
            if (video) {
#ifdef I30_VIDEO_UYVY_STAGING
                UyvyStage stage = {HeapAlloc(heap, 0, UYVY_BYTES), 0};
                const I30VideoTarget target = {&stage, begin_paint, end_paint, stage_uyvy};
                painted = i30_video_push(video, &target, bytes, length) > 0;
                OutputDebugStringW(stage.frames ?
                    L"i30 CE UYVY staged in memory.\r\n" :
                    L"i30 CE UYVY staging unavailable.\r\n");
                if (stage.bytes)
                    HeapFree(heap, 0, stage.bytes);
#elif defined(I30_VIDEO_UYVY_DIRECTDRAW)
                I30Ddraw ddraw;
                const I30VideoTarget target = {&ddraw, begin_paint, end_paint, i30_ddraw_present};
                if (i30_ddraw_open((CE_HANDLE)1, &ddraw)) {
                    painted = i30_video_push(video, &target, bytes, length) > 0;
                    i30_ddraw_close(&ddraw);
                }
                OutputDebugStringW(painted ?
                    L"i30 CE UYVY DirectDraw presented a frame.\r\n" :
                    L"i30 CE UYVY DirectDraw unavailable; GDI fallback used.\r\n");
#else
                const I30VideoTarget target = {0, begin_paint, end_paint};
                painted = i30_video_push(video, &target, bytes, length) > 0;
#endif
            }
            i30_video_close(video);
        }
        if (bytes)
            HeapFree(heap, 0, bytes);
        CloseHandle(file);
    }
#if defined(I30_VIDEO_UYVY_STAGING) || defined(I30_VIDEO_UYVY_DIRECTDRAW)
    OutputDebugStringW(painted ? L"i30 CE H.264 output consumed.\r\n" : L"i30 CE H.264 video probe failed.\r\n");
#else
    OutputDebugStringW(painted ? L"i30 CE H.264 picture painted.\r\n" : L"i30 CE H.264 video probe failed.\r\n");
#endif
    ExitThread(painted ? 0U : 1U);
}
