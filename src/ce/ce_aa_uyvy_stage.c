#include "ce_aa_uyvy_stage.h"

#ifdef I30_VIDEO_UYVY_STAGING

int i30_uyvy_stage(void *context, const I30VideoGeometry *geometry, const uint8_t *i420)
{
    I30UyvyStage *stage = context;
    if (!stage || !stage->surface || !geometry ||
        !i30_pack_uyvy(geometry, i420, stage->surface, I30_UYVY_STAGE_BYTES, I30_UYVY_STAGE_PITCH)) {
        OutputDebugStringW(L"i30 CE UYVY diagnostic pack rejected; GDI fallback retained.\r\n");
        return 0;
    }
    ++stage->frames;
    /* Evidence-only: the visible frame still comes from BGRA + StretchDIBits. */
    return 0;
}

#endif
