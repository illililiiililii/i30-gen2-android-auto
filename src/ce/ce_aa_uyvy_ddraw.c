#include "ce_aa_uyvy_ddraw.h"
#include "ce_aa_uyvy.h"

#include <stddef.h>

#ifdef I30_VIDEO_UYVY_DIRECTDRAW

CE_HANDLE LoadLibraryW(const CE_WCHAR *name);
void *GetProcAddressA(CE_HANDLE module, const char *name);
int FreeLibrary(CE_HANDLE module);

/* CE6 application ABI. These byte offsets are taken from the CE6 interface
 * declarations and confirmed against the stock .061 LibVideo.dll ARM call
 * sites. Do not replace them with desktop DirectDraw 2/4/7 slot numbers. */
enum {
    DD_DD_CREATE_SURFACE = 0x14, DD_DD_GET_CAPS = 0x24, DD_DD_GET_FOURCC = 0x2c,
    DD_DD_SET_COOPERATIVE = 0x44, DD_DD_RELEASE = 0x08
};
enum {
    DD_S_ENUM_ATTACHED = 0x14, DD_S_FLIP = 0x1c, DD_S_GET_FLIP_STATUS = 0x34,
    DD_S_IS_LOST = 0x48, DD_S_LOCK = 0x4c, DD_S_RESTORE = 0x54,
    DD_S_UNLOCK = 0x68, DD_S_UPDATE_OVERLAY = 0x6c, DD_S_ADD_REF = 0x04,
    DD_S_RELEASE = 0x08
};

enum { DD_SURFACE_DESC_SIZE = 108, DD_PIXEL_FORMAT_SIZE = 32, DD_CAPS_SIZE = 112,
       DD_CAPS_BUFFER_SIZE = 128, DD_OVERLAY_FX_SIZE = 28 };
enum {
    DDSD_CAPS = 0x1, DDSD_HEIGHT = 0x2, DDSD_WIDTH = 0x4, DDSD_BACKBUFFERCOUNT = 0x20,
    DDSD_PIXELFORMAT = 0x1000,
    DDPF_FOURCC = 0x4,
    DDSCAPS_BACKBUFFER = 0x2, DDSCAPS_FLIP = 0x4, DDSCAPS_OVERLAY = 0x10,
    DDSCAPS_PRIMARYSURFACE = 0x40,
    DDOVERLAYCAPS_FLIP = 0x1, DDOVERLAYCAPS_FOURCC = 0x4,
    DDOVERLAYCAPS_OVERLAYSUPPORT = 0x80000000U,
    /* CE6-era headers use NORMAL=0/FULLSCREEN=1. The CE6 tutorial sample uses
     * FULLSCREEN, but that can take display ownership from the stock map, so
     * this opt-in backend deliberately asks for NORMAL. */
    DDSCL_NORMAL = 0,
    DDLOCK_WRITEONLY = 0x2, DDLOCK_WAITNOTBUSY = 0x8,
    DDOVER_HIDE = 0x20, DDOVER_SHOW = 0x400, DDOVER_WAITNOTBUSY = 0x4000,
    DDFLIP_WAITNOTBUSY = 0x8, DDGFS_ISFLIPDONE = 0x2,
    DDERR_SURFACELOST = (int32_t)0x887601c2U
};
enum { I30_UYVY_FOURCC = 0x59565955U, I30_MAX_FOURCC_CODES = 64, I30_MAX_FAILURES = 3 };

typedef int32_t (*I30DirectDrawCreate)(void *, void **, void *);
typedef int32_t (*I30DdHResult0)(void *);
typedef uint32_t (*I30DdRef)(void *);
typedef int32_t (*I30DdSetCooperative)(void *, CE_HANDLE, uint32_t);
typedef int32_t (*I30DdGetCaps)(void *, void *, void *);
typedef int32_t (*I30DdGetFourCC)(void *, uint32_t *, uint32_t *);
typedef int32_t (*I30DdCreateSurface)(void *, void *, void **, void *);
typedef int32_t (*I30DdLock)(void *, void *, void *, uint32_t, void *);
typedef int32_t (*I30DdUnlock)(void *, void *);
typedef int32_t (*I30DdUpdateOverlay)(void *, void *, void *, void *, uint32_t, void *);
#ifdef I30_DDRAW_FLIP
typedef int32_t (*I30DdFlip)(void *, void *, uint32_t);
typedef int32_t (*I30DdFlipStatus)(void *, uint32_t);
typedef int32_t (*I30DdEnumAttached)(void *, void *, void *, void *);
#endif

typedef struct I30DdrawRect { int32_t left, top, right, bottom; } I30DdrawRect;

typedef struct I30LockedSurface {
    uint8_t *pixels;
    uint32_t size;
    int32_t pitch, x_pitch, width, height;
} I30LockedSurface;

static void **dd_vtable(void *object)
{
    return object ? *(void ***)object : 0;
}

/* CE6 vtable offsets are byte offsets into a 4-byte-slot table. Dividing by 4
 * is exact on ARM; a host harness can use native-width table entries with the
 * same slot indices without changing the ARM ABI. */
static void *dd_vtable_slot(void **vtable, unsigned offset)
{
    return vtable ? vtable[offset / 4] : 0;
}

static void zero_bytes(void *memory, unsigned size)
{
    uint8_t *bytes = memory;
    for (unsigned i = 0; i < size; ++i)
        bytes[i] = 0;
}

static uint32_t get_u32(const uint8_t *bytes, unsigned offset)
{
    return (uint32_t)bytes[offset] | ((uint32_t)bytes[offset + 1] << 8) |
           ((uint32_t)bytes[offset + 2] << 16) | ((uint32_t)bytes[offset + 3] << 24);
}

static int32_t get_i32(const uint8_t *bytes, unsigned offset)
{
    return (int32_t)get_u32(bytes, offset);
}

static void put_u32(uint8_t *bytes, unsigned offset, uint32_t value)
{
    bytes[offset] = (uint8_t)value;
    bytes[offset + 1] = (uint8_t)(value >> 8);
    bytes[offset + 2] = (uint8_t)(value >> 16);
    bytes[offset + 3] = (uint8_t)(value >> 24);
}

static int32_t dd_release(void *object)
{
    void **vtable = dd_vtable(object);
    if (!vtable)
        return 0;
    I30DdRef release = (void *)dd_vtable_slot(vtable,DD_DD_RELEASE);
    return (int32_t)release(object);
}

#ifdef I30_DDRAW_FLIP
static uint32_t surface_add_ref(void *surface)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return 0;
    I30DdRef add_ref = (void *)dd_vtable_slot(vtable,DD_S_ADD_REF);
    return add_ref(surface);
}
#endif

static int32_t dd_set_cooperative(void *dd, CE_HANDLE window)
{
    void **vtable = dd_vtable(dd);
    if (!vtable)
        return -1;
    I30DdSetCooperative call = (void *)dd_vtable_slot(vtable,DD_DD_SET_COOPERATIVE);
    return call(dd, window, DDSCL_NORMAL);
}

static int32_t dd_get_caps(void *dd, void *caps, uint32_t size)
{
    void **vtable = dd_vtable(dd);
    if (!vtable)
        return -1;
    uint8_t *bytes = caps;
    zero_bytes(bytes, DD_CAPS_BUFFER_SIZE);
    put_u32(bytes, 0, size);
    I30DdGetCaps call = (void *)dd_vtable_slot(vtable,DD_DD_GET_CAPS);
    return call(dd, caps, 0);
}

static int32_t dd_get_fourcc(void *dd, uint32_t *count, uint32_t *codes)
{
    void **vtable = dd_vtable(dd);
    if (!vtable)
        return -1;
    I30DdGetFourCC call = (void *)dd_vtable_slot(vtable,DD_DD_GET_FOURCC);
    return call(dd, count, codes);
}

static int32_t dd_create_surface(void *dd, const uint8_t *desc, void **surface)
{
    void **vtable = dd_vtable(dd);
    if (!vtable)
        return -1;
    I30DdCreateSurface call = (void *)dd_vtable_slot(vtable,DD_DD_CREATE_SURFACE);
    return call(dd, (void *)desc, surface, 0);
}

static int32_t surface_lock(void *surface, I30LockedSurface *locked)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return -1;
    uint8_t desc[DD_SURFACE_DESC_SIZE];
    zero_bytes(desc, sizeof(desc));
    put_u32(desc, 0, sizeof(desc));
    I30DdLock call = (void *)dd_vtable_slot(vtable,DD_S_LOCK);
    int32_t result = call(surface, 0, desc, DDLOCK_WRITEONLY | DDLOCK_WAITNOTBUSY, 0);
    if (result)
        return result;
    /* CE6 DDSURFACEDESC stores dwHeight at +0x08 and dwWidth at +0x0c. */
    locked->height = (int32_t)get_u32(desc, 8);
    locked->width = (int32_t)get_u32(desc, 12);
    locked->pitch = get_i32(desc, 16);
    locked->x_pitch = get_i32(desc, 20);
#ifdef I30_DDRAW_HOST_HARNESS
    /* Test-only seam: a 64-bit host harness cannot round-trip a CE6 32-bit
     * LPVOID. Production ARM builds read the CE6 DWORD below. */
    locked->pixels = *(uint8_t **)(desc + 32);
#else
    locked->pixels = (uint8_t *)(uintptr_t)get_u32(desc, 32);
#endif
    locked->size = get_u32(desc, 104);
    return 0;
}

static int32_t surface_unlock(void *surface)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return -1;
    I30DdUnlock call = (void *)dd_vtable_slot(vtable,DD_S_UNLOCK);
    return call(surface, 0);
}

static int32_t surface_restore(void *surface)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return -1;
    I30DdHResult0 call = (void *)dd_vtable_slot(vtable,DD_S_RESTORE);
    return call(surface);
}

static int32_t surface_is_lost(void *surface)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return -1;
    I30DdHResult0 call = (void *)dd_vtable_slot(vtable,DD_S_IS_LOST);
    return call(surface);
}

static int32_t surface_update_overlay(void *surface, const I30DdrawRect *src,
                                      void *primary, uint32_t flags, void *fx)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return -1;
    I30DdUpdateOverlay call = (void *)dd_vtable_slot(vtable,DD_S_UPDATE_OVERLAY);
    return call(surface, (void *)src, primary, 0, flags, fx);
}

#ifdef I30_DDRAW_FLIP
static int32_t surface_flip(void *surface, uint32_t flags)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return -1;
    I30DdFlip call = (void *)dd_vtable_slot(vtable,DD_S_FLIP);
    return call(surface, 0, flags);
}

static int32_t surface_flip_status(void *surface, uint32_t flags)
{
    void **vtable = dd_vtable(surface);
    if (!vtable)
        return -1;
    I30DdFlipStatus call = (void *)dd_vtable_slot(vtable,DD_S_GET_FLIP_STATUS);
    return call(surface, flags);
}

static int32_t enum_back_buffer(void *surface, void *desc, void *context)
{
    void **found = context;
    (void)desc;
    if (!surface || *found)
        return 1;
    if (!surface_add_ref(surface))
        return 1;
    *found = surface;
    return 1;
}

static void *back_buffer(void *overlay)
{
    void **vtable = dd_vtable(overlay);
    uint8_t caps[4];
    void *found = 0;
    if (!vtable)
        return 0;
    put_u32(caps, 0, DDSCAPS_BACKBUFFER);
    I30DdEnumAttached call = (void *)dd_vtable_slot(vtable,DD_S_ENUM_ATTACHED);
    call(overlay, caps, enum_back_buffer, &found);
    return found;
}
#endif

static int caps_support_uyvy(void *dd, uint32_t *overlay_caps)
{
    uint8_t caps[DD_CAPS_BUFFER_SIZE];

    /* Natural CE6 DDCAPS is 112 bytes; the stock image passes 128. Try both
     * sizes without treating either as a verified GD13MY contract. */
    for (unsigned attempt = 0; attempt < 2; ++attempt) {
        const uint32_t size = attempt ? DD_CAPS_BUFFER_SIZE : DD_CAPS_SIZE;
        if (dd_get_caps(dd, caps, size))
            continue;
        *overlay_caps = get_u32(caps, 0x48);
        if ((*overlay_caps & (DDOVERLAYCAPS_OVERLAYSUPPORT | DDOVERLAYCAPS_FOURCC)) ==
            (DDOVERLAYCAPS_OVERLAYSUPPORT | DDOVERLAYCAPS_FOURCC))
            return 1;
        /* A driver that silently ignores the natural CE6 size can leave the
         * capability word zero; retry with the stock image's buffer size. */
    }
    OutputDebugStringW(L"i30 CE UYVY DirectDraw GetCaps failed or overlay caps absent.\r\n");
    return 0;
}

static int uyvy_fourcc_supported(void *dd)
{
    uint32_t count = 0, *codes;
    int found = 0;

    if (dd_get_fourcc(dd, &count, 0) || !count || count > I30_MAX_FOURCC_CODES)
        return 0;
    codes = HeapAlloc(GetProcessHeap(), 0, count * sizeof(*codes));
    if (!codes)
        return 0;
    if (!dd_get_fourcc(dd, &count, codes) && count && count <= I30_MAX_FOURCC_CODES) {
        for (uint32_t i = 0; i < count; ++i) {
            if (codes[i] == I30_UYVY_FOURCC) {
                found = 1;
                break;
            }
        }
    }
    HeapFree(GetProcessHeap(), 0, codes);
    if (!found)
        OutputDebugStringW(L"i30 CE UYVY DirectDraw UYVY FourCC absent.\r\n");
    return found;
}

static void *create_primary(void *dd)
{
    uint8_t desc[DD_SURFACE_DESC_SIZE];
    void *surface = 0;

    zero_bytes(desc, sizeof(desc));
    put_u32(desc, 0, sizeof(desc));
    put_u32(desc, 4, DDSD_CAPS);
    put_u32(desc, 100, DDSCAPS_PRIMARYSURFACE);
    return dd_create_surface(dd, desc, &surface) == 0 ? surface : 0;
}

static void *create_overlay(void *dd, int flip)
{
    uint8_t desc[DD_SURFACE_DESC_SIZE];
    uint32_t flags = DDSD_CAPS | DDSD_WIDTH | DDSD_HEIGHT | DDSD_PIXELFORMAT;
    uint32_t caps = DDSCAPS_OVERLAY;
    void *surface = 0;

    zero_bytes(desc, sizeof(desc));
    put_u32(desc, 0, sizeof(desc));
    put_u32(desc, 4, flags);
    put_u32(desc, 8, I30_VIDEO_HEIGHT);
    put_u32(desc, 12, I30_VIDEO_WIDTH);
    if (flip) {
        put_u32(desc, 4, flags | DDSD_BACKBUFFERCOUNT);
        put_u32(desc, 24, 1);
        caps |= DDSCAPS_FLIP;
    }
    put_u32(desc, 68, DD_PIXEL_FORMAT_SIZE);
    put_u32(desc, 72, DDPF_FOURCC);
    put_u32(desc, 76, I30_UYVY_FOURCC);
    put_u32(desc, 100, caps);
    return dd_create_surface(dd, desc, &surface) == 0 ? surface : 0;
}

static void prepare_fx(void *fx)
{
    zero_bytes(fx, DD_OVERLAY_FX_SIZE);
    put_u32(fx, 0, DD_OVERLAY_FX_SIZE);
}

static int show_overlay(I30Ddraw *ddraw, const I30DdrawRect *src)
{
    uint8_t fx[DD_OVERLAY_FX_SIZE];
    void *surface = ddraw->front ? ddraw->front : ddraw->overlay;
    int32_t result;

    prepare_fx(fx);
    result = surface_update_overlay(surface, src, ddraw->primary,
                                    DDOVER_SHOW | DDOVER_WAITNOTBUSY, fx);
    if (result == DDERR_SURFACELOST && surface_restore(surface) == 0) {
        ++ddraw->restored;
        result = surface_update_overlay(surface, src, ddraw->primary,
                                        DDOVER_SHOW | DDOVER_WAITNOTBUSY, fx);
    }
    if (result)
        return 0;
    ddraw->shown = 1;
    return 1;
}

static void hide_overlay(I30Ddraw *ddraw, int force)
{
    uint8_t fx[DD_OVERLAY_FX_SIZE];
    void *surface = ddraw->front ? ddraw->front : ddraw->overlay;
    int32_t result;

    if (!surface || (!force && !ddraw->shown))
        return;
    prepare_fx(fx);
    result = surface_update_overlay(surface, 0, ddraw->primary, DDOVER_HIDE, fx);
    if (result == DDERR_SURFACELOST && surface_restore(surface) == 0) {
        ++ddraw->restored;
        result = surface_update_overlay(surface, 0, ddraw->primary, DDOVER_HIDE, fx);
    }
    if (!result)
        ddraw->shown = 0;
}

static void ddraw_fail(I30Ddraw *ddraw, const CE_WCHAR *message)
{
    if (!ddraw || ddraw->disabled)
        return;
    OutputDebugStringW(message);
    /* One failed frame is retried on the next frame; three disable the session
     * so a broken driver cannot stall the USB thread indefinitely. */
    if (++ddraw->failures < I30_MAX_FAILURES)
        return;
    ddraw->disabled = 1;
    OutputDebugStringW(L"i30 CE UYVY DirectDraw disabled after repeated failures; GDI fallback retained.\r\n");
}

/* Every rejected frame must remove a possibly stale overlay before the caller
 * paints the same decoded frame through BGRA + GDI. */
static int reject_frame(I30Ddraw *ddraw, const CE_WCHAR *message)
{
    if (ddraw)
        hide_overlay(ddraw, 1);
    ddraw_fail(ddraw, message);
    return 0;
}

#ifdef I30_DDRAW_FLIP
/* A flip changes which chain surface is visible. Once it fails or times out
 * the surface order is no longer trustworthy, so the whole backend is retired
 * for this session and every later frame uses BGRA + GDI. */
static int reject_flip(I30Ddraw *ddraw, const CE_WCHAR *message)
{
    int rejected = reject_frame(ddraw, message);

    if (ddraw) {
        ddraw->flip = 0;
        ddraw->flip_pending = 0;
        ddraw->disabled = 1;
        OutputDebugStringW(L"i30 CE UYVY DirectDraw disabled after flip failure; GDI fallback retained.\r\n");
    }
    return rejected;
}
#endif

int i30_ddraw_open(CE_HANDLE window, I30Ddraw *ddraw)
{
    static const CE_WCHAR ddraw_name[] = L"DDRAW.dll";
    static const CE_WCHAR ddraw_path[] = L"\\Windows\\DDRAW.dll";
    uint32_t overlay_caps = 0;
    void *module, *dd = 0, *primary = 0, *overlay = 0;
    I30DirectDrawCreate create;
#ifdef I30_DDRAW_FLIP
    int flip = 0;
#endif

    if (!window || !ddraw)
        return 0;
    zero_bytes(ddraw, sizeof(*ddraw));
    module = LoadLibraryW(ddraw_name);
    if (!module)
        module = LoadLibraryW(ddraw_path);
    if (!module) {
        OutputDebugStringW(L"i30 CE UYVY DirectDraw DDRAW.dll unavailable; GDI fallback retained.\r\n");
        return 0;
    }
    create = (void *)GetProcAddressA(module, "DirectDrawCreate");
    if (!create || create(0, &dd, 0) || !dd)
        goto failed;
    if (dd_set_cooperative(dd, window))
        goto failed;
    if (!caps_support_uyvy(dd, &overlay_caps) || !uyvy_fourcc_supported(dd))
        goto failed;
    primary = create_primary(dd);
    if (!primary)
        goto failed;
#ifdef I30_DDRAW_FLIP
    if ((overlay_caps & DDOVERLAYCAPS_FLIP) &&
        (overlay = create_overlay(dd, 1)) != 0) {
        ddraw->back = back_buffer(overlay);
        if (ddraw->back) {
            flip = 1;
        } else {
            dd_release(overlay);
            overlay = 0;
        }
    }
#endif
    if (!overlay)
        overlay = create_overlay(dd, 0);
    if (!overlay)
        goto failed;

    ddraw->module = module;
    ddraw->dd = dd;
    ddraw->primary = primary;
    ddraw->overlay = overlay;
    ddraw->front = overlay;
    ddraw->write = ddraw->back ? ddraw->back : overlay;
#ifdef I30_DDRAW_FLIP
    ddraw->flip = flip;
#endif
    OutputDebugStringW(L"i30 CE UYVY DirectDraw backend initialized; hardware output UNVERIFIED.\r\n");
    return 1;

failed:
    if (overlay)
        dd_release(overlay);
    if (ddraw->back) {
        dd_release(ddraw->back);
        ddraw->back = 0;
    }
    if (primary)
        dd_release(primary);
    if (dd)
        dd_release(dd);
    FreeLibrary(module);
    return 0;
}

int i30_ddraw_ready(const I30Ddraw *ddraw)
{
    return ddraw && ddraw->module && ddraw->dd && ddraw->primary && ddraw->overlay &&
           ddraw->front && ddraw->write && !ddraw->disabled;
}

void i30_ddraw_hide(I30Ddraw *ddraw)
{
    if (ddraw)
        hide_overlay(ddraw, 1);
}

#ifdef I30_DDRAW_FLIP
/* A flip is only committed after the driver reports completion. Until then
 * front/write stay unchanged so a rejected frame can hide the surface it
 * actually showed and let the caller repaint the same decoded frame. */
static int finish_flip(I30Ddraw *ddraw)
{
    void *old_front;
    int32_t result;

    if (!ddraw->flip_pending)
        return 1;
    result = surface_flip_status(ddraw->write, DDGFS_ISFLIPDONE);
    if (!result) {
        ddraw->flip_pending = 0;
        old_front = ddraw->front;
        ddraw->front = ddraw->write;
        ddraw->write = old_front;
        return 1;
    }
    return reject_flip(ddraw, L"i30 CE UYVY DirectDraw flip completion timed out; GDI fallback retained.\r\n");
}
#endif

int i30_ddraw_present(void *context, const I30VideoGeometry *geometry, const uint8_t *i420)
{
    I30Ddraw *ddraw = context;
    I30LockedSurface locked;
    I30DdrawRect src;
    void *surface;
    uint64_t total;
    int32_t result;
    int packed;

    if (!i30_ddraw_ready(ddraw) || !geometry || !i420)
        return reject_frame(ddraw, L"i30 CE UYVY DirectDraw rejected a frame.\r\n");
#ifdef I30_DDRAW_FLIP
    if (!finish_flip(ddraw))
        return 0;
#endif

    surface = ddraw->write;
    if (ddraw->needs_restore) {
        if (surface_restore(surface))
            return reject_frame(ddraw, L"i30 CE UYVY DirectDraw restore failed; GDI fallback retained.\r\n");
        ++ddraw->restored;
        ddraw->needs_restore = 0;
    }
    if (surface_is_lost(surface) == DDERR_SURFACELOST) {
        if (surface_restore(surface)) {
            ddraw->needs_restore = 1;
            return reject_frame(ddraw, L"i30 CE UYVY DirectDraw restore failed; GDI fallback retained.\r\n");
        }
        ++ddraw->restored;
    }
    result = surface_lock(surface, &locked);
    if (result == DDERR_SURFACELOST && surface_restore(surface) == 0) {
        ++ddraw->restored;
        result = surface_lock(surface, &locked);
    }
    if (result)
        return reject_frame(ddraw, L"i30 CE UYVY DirectDraw Lock failed; GDI fallback retained.\r\n");

    total = (uint64_t)(uint32_t)locked.pitch * (uint64_t)I30_VIDEO_HEIGHT;
    /* Some drivers leave lXPitch/dwSurfaceSize at zero in Lock. Accept zero as
     * unspecified; a reported size smaller than pitch*height is not safe. */
    if (locked.pitch <= 0 || locked.pitch < (int32_t)I30_VIDEO_WIDTH * 2 ||
        total > 0xffffffffU || (locked.x_pitch && locked.x_pitch != 2) || !locked.pixels ||
        (locked.width && locked.width != I30_VIDEO_WIDTH) ||
        (locked.height && locked.height != I30_VIDEO_HEIGHT) ||
        (locked.size && locked.size < (uint32_t)total)) {
        surface_unlock(surface);
        return reject_frame(ddraw, L"i30 CE UYVY DirectDraw rejected Lock pitch or size.\r\n");
    }
    packed = i30_pack_uyvy(geometry, i420, locked.pixels, (size_t)total, (size_t)locked.pitch);
    result = surface_unlock(surface);
    if (result) {
        ddraw->needs_restore = 1;
        return reject_frame(ddraw, L"i30 CE UYVY DirectDraw Unlock failed; GDI fallback retained.\r\n");
    }
    if (!packed)
        return reject_frame(ddraw, L"i30 CE UYVY DirectDraw packer rejected the frame; GDI fallback retained.\r\n");

    src.left = src.top = 0;
    src.right = (int32_t)geometry->width;
    src.bottom = (int32_t)geometry->height;
    if (!show_overlay(ddraw, &src))
        return reject_frame(ddraw, L"i30 CE UYVY DirectDraw overlay show failed; GDI fallback retained.\r\n");

#ifdef I30_DDRAW_FLIP
    if (ddraw->flip && ddraw->back) {
        result = surface_flip(ddraw->front, DDFLIP_WAITNOTBUSY);
        if (result)
            return reject_flip(ddraw, L"i30 CE UYVY DirectDraw Flip failed; GDI fallback retained.\r\n");
        ddraw->flip_pending = 1;
        ++ddraw->flips;
        if (!finish_flip(ddraw))
            return 0;
    }
#endif
    ddraw->failures = 0;
    ++ddraw->presented;
    return 1;
}

void i30_ddraw_close(I30Ddraw *ddraw)
{
    if (!ddraw)
        return;
    if (ddraw->presented)
        OutputDebugStringW(L"i30 CE UYVY DirectDraw session closed.\r\n");
    hide_overlay(ddraw, 1);
    if (ddraw->back)
        dd_release(ddraw->back);
    if (ddraw->overlay)
        dd_release(ddraw->overlay);
    if (ddraw->primary)
        dd_release(ddraw->primary);
    if (ddraw->dd)
        dd_release(ddraw->dd);
    if (ddraw->module)
        FreeLibrary(ddraw->module);
    zero_bytes(ddraw, sizeof(*ddraw));
}

#endif
