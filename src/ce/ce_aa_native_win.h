#ifndef I30_CE_AA_NATIVE_WIN_H
#define I30_CE_AA_NATIVE_WIN_H

#include "ce_aa_native_display.h"

typedef struct CePoint { int32_t x, y; } CePoint;
typedef struct CeRect { int32_t left, top, right, bottom; } CeRect;

enum {
    CE_GW_NEXT = 2, CE_GW_PREV = 3, CE_GW_OWNER = 4,
    CE_GWL_STYLE = -16, CE_GWL_EXSTYLE = -20, CE_GWL_USERDATA = -21,
    CE_WS_TOPMOST = 8, CE_WAIT_OBJECT_0 = 0, CE_ERROR_ALREADY_EXISTS = 183
};

#ifdef __cplusplus
extern "C" {
#endif

CE_HANDLE CreateEventW(void *, int, int, const CE_WCHAR *);
uint32_t GetLastError(void);
CE_HANDLE FindWindowW(const CE_WCHAR *, const CE_WCHAR *);
CE_HANDLE GetWindow(CE_HANDLE, unsigned);
CE_HANDLE GetParent(CE_HANDLE);
int IsWindow(CE_HANDLE);
int IsWindowVisible(CE_HANDLE);
int32_t GetWindowLongW(CE_HANDLE, int);
int32_t SetWindowLongW(CE_HANDLE, int, int32_t);
uint32_t GetWindowThreadProcessId(CE_HANDLE, uint32_t *);
int GetClientRect(CE_HANDLE, CeRect *);
int ClientToScreen(CE_HANDLE, CePoint *);
int SetWindowPos(CE_HANDLE, CE_HANDLE, int, int, int, int, uint32_t);

#ifdef __cplusplus
}
#endif

static inline int i30_stock_display_safe(void)
{
    /* This CE image opens named events with CreateEventW. A newly created
     * event is reset and can't grant permission. */
    CE_HANDLE event = CreateEventW(0, 1, 0, I30_STOCK_DISPLAY_SAFE);
    if (!event)
        return 0;
    int allowed = GetLastError() == CE_ERROR_ALREADY_EXISTS &&
                  WaitForSingleObject(event, 0) == CE_WAIT_OBJECT_0;
    CloseHandle(event);
    if (!allowed)
        return 0;
    event = CreateEventW(0, 1, 0, I30_STOCK_CAMERA_ACTIVE);
    if (!event)
        return 0;
    uint32_t camera = WaitForSingleObject(event, 0);
    CloseHandle(event);
    return camera == 258U; /* WAIT_TIMEOUT: the stock rear-view latch is clear. */
}

static inline int i30_projection_above_map(CE_HANDLE window, CE_HANDLE map)
{
    return window && map && IsWindowVisible(map) &&
           GetWindow(window, CE_GW_OWNER) == map &&
           !(GetWindowLongW(window, CE_GWL_EXSTYLE) & CE_WS_TOPMOST) &&
           !(GetWindowLongW(map, CE_GWL_EXSTYLE) & CE_WS_TOPMOST) &&
           GetWindow(window, CE_GW_NEXT) == map;
}

#endif
