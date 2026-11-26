#ifndef I30_CE_AA_NATIVE_DISPLAY_H
#define I30_CE_AA_NATIVE_DISPLAY_H

#include "ce_minimal.h"
#include "ce_aa_display_events.h"

#define I30_NAVIGATION_PROJECTION_CLASS L"I30.GD13MY.NavigationProjection.1"

enum { I30_TOUCH_MESSAGE = 0x8002, I30_TOUCH_READ = 0, I30_TOUCH_ENABLE = 1, I30_TOUCH_DISABLE = 2 };
enum { I30_TOUCH_EMPTY = 0, I30_TOUCH_RESET = 1, I30_TOUCH_DOWN = 2, I30_TOUCH_UP = 3, I30_TOUCH_MOVE = 4 };
/* The private window message transfers a scalar. No pointers cross processes. */
#define I30_TOUCH_ACTION(sample) ((sample) >> 19)
#define I30_TOUCH_X(sample) ((sample) & 1023U)
#define I30_TOUCH_Y(sample) (((sample) >> 10) & 511U)

#ifdef __cplusplus
extern "C" {
#endif

/* The navigation UI thread calls this from the stock menu touch handler. */
int I30ToggleProjection(CE_HANDLE menu);
int I30AutoStartProjection(CE_HANDLE menu);
/* The stock .061 pre-dispatch path calls this before its own touch handler. */
int I30RouteProjectionTouch(CE_HANDLE source, uint32_t message, int32_t point);

/* An in-process OEM display handler can request a synchronous refresh after
 * updating the permission event. The display owner maintains the event. */
void I30StockDisplayChanged(void);

#ifdef __cplusplus
}
#endif
#endif
