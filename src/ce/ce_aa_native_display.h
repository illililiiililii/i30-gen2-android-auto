#ifndef I30_CE_AA_NATIVE_DISPLAY_H
#define I30_CE_AA_NATIVE_DISPLAY_H

#include "ce_minimal.h"
#include "ce_aa_display_events.h"

#define I30_NAVIGATION_PROJECTION_CLASS L"I30.GD13MY.NavigationProjection.1"

#ifdef __cplusplus
extern "C" {
#endif

/* The navigation UI thread calls this from the stock menu touch handler. */
int I30ToggleProjection(CE_HANDLE menu);

/* An in-process OEM display handler can request a synchronous refresh after
 * updating the permission event. The display owner maintains the event. */
void I30StockDisplayChanged(void);

#ifdef __cplusplus
}
#endif
#endif
