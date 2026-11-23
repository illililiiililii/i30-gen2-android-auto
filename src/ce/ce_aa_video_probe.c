#include "ce_aa_video.h"

CE_HANDLE GetDC(CE_HANDLE window);
int ReleaseDC(CE_HANDLE window, CE_HANDLE dc);

static CE_HANDLE begin_paint(void *window)
{
    return GetDC(window);
}

static void end_paint(void *window, CE_HANDLE dc)
{
    ReleaseDC(window, dc);
}

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
            const I30VideoTarget target = {0, begin_paint, end_paint};
            if (video)
                painted = i30_video_push(video, &target, bytes, length) > 0;
            i30_video_close(video);
        }
        if (bytes)
            HeapFree(heap, 0, bytes);
        CloseHandle(file);
    }
    OutputDebugStringW(painted ? L"i30 CE H.264 picture painted.\r\n" : L"i30 CE H.264 video probe failed.\r\n");
    ExitThread(painted ? 0U : 1U);
}
