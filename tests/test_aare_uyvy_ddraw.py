"""Host contract tests for the opt-in UYVY DirectDraw backend.

The harness supplies CE-style COM vtables and loader imports to the real
backend source. It proves the CE6 call sequence, descriptor offsets, failure
handling and reference cleanup in a mock. It does not prove real DDRAW.dll
behaviour, hardware overlay output, or camera ownership.
"""

import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZIG = Path(os.environ.get('LOCALAPPDATA', '')) / 'i30-phase5-tools/zig/zig-x86_64-windows-0.15.2/zig.exe'

# Scenario numbers are shared with the C harness below.
SUCCESS = 0
LOAD_FAIL = 1
NO_PROC = 2
DD_CREATE_FAIL = 3
COOP_FAIL = 4
CAPS_FAIL = 5
NO_OVERLAY_CAPS = 6
NO_FOURCC = 7
PRIMARY_FAIL = 8
OVERLAY_FAIL = 9
NO_BACK = 10
BAD_PITCH = 11
BAD_XPITCH = 12
ZERO_FIELDS = 13
LOCK_FAIL = 14
LOST_LOCK = 15
RESTORE_FAIL = 16
OVERLAY_FAIL_FRAME = 17
OVERLAY_LOST = 18
FLIP_FAIL = 19
FLIP_TIMEOUT = 20
UNLOCK_FAIL = 21
NULL_PRESENT = 22
FALLBACK_PATH = 23
CAPS_RETRY = 24

HARNESS = r'''
#include "ce_aa_uyvy_ddraw.h"
#include <stdlib.h>
#include <string.h>

#define UYVY_FCC 0x59565955U
#define DDERR_SURFACELOST_VALUE ((int32_t)0x887601c2U)
#define OV_SUPPORT 0x80000000U
#define OV_FOURCC 0x4U
#define OV_FLIP 0x1U
#define DDSCAPS_BACKBUFFER 0x2U
#define DDSCAPS_OVERLAY 0x10U
#define DDSCAPS_FLIP 0x4U
#define DDSCAPS_PRIMARYSURFACE 0x40U
#define SURFACE_PITCH (I30_VIDEO_WIDTH * 2 + 32)
#define SURFACE_BYTES (SURFACE_PITCH * I30_VIDEO_HEIGHT)

enum {
    S_SUCCESS = 0, S_LOAD_FAIL, S_NO_PROC, S_DD_CREATE_FAIL, S_COOP_FAIL,
    S_CAPS_FAIL, S_NO_OVERLAY_CAPS, S_NO_FOURCC, S_PRIMARY_FAIL, S_OVERLAY_FAIL,
    S_NO_BACK, S_BAD_PITCH, S_BAD_XPITCH, S_ZERO_FIELDS, S_LOCK_FAIL,
    S_LOST_LOCK, S_RESTORE_FAIL, S_OVERLAY_FAIL_FRAME, S_OVERLAY_LOST,
    S_FLIP_FAIL, S_FLIP_TIMEOUT, S_UNLOCK_FAIL, S_NULL_PRESENT, S_FALLBACK_PATH,
    S_CAPS_RETRY
};

typedef struct DdrawResult {
    int opened;
    int present[4];
    uint32_t failures, disabled, presented, flips, restored, backend_restored;
    uint32_t loads, frees, procs, creates, refs_live;
    uint32_t locks, unlocks, restores, is_lost_calls, enum_calls;
    uint32_t shows, hides, overlay_flags, fx_size;
    uint32_t flips_mock, flip_status_calls;
    uint32_t coop_flags, coop_window;
    uint32_t caps_sizes[2], overlay_caps;
    uint32_t create_flags[3], create_caps[3];
    uint32_t create_w, create_h, pixel_size, pixel_flags, fourcc;
    uint32_t lock_flags, lock_pitch, lock_xpitch, lock_size;
    int32_t src_right, src_bottom;
    uint32_t pack_ok, padding_ok, debug_count;
    uint16_t debug_last[64];
} DdrawResult;

typedef struct FakeObject {
    void **vt;
    uint32_t refs;
    uint32_t kind;
} FakeObject;

static int32_t mock_direct_draw_create(void *guid, void **out, void *outer);

static unsigned scenario;
static FakeObject dd_object, primary_object, overlay_object, back_object;
static void *dd_vt[32], *surface_vt[32];
static uint8_t surface[SURFACE_BYTES];
static uint8_t i420[8 * 4 + 8 * 2 + 8 * 2];
static uint32_t overlay_caps_value;
static uint32_t loads, frees, procs, creates, coop_flags, coop_window;
static uint32_t caps_sizes[2], overlay_caps_seen, create_flags[3], create_caps[3];
static uint32_t create_w, create_h, pixel_size, pixel_flags, fourcc_seen;
static uint32_t cap_calls;
static uint32_t locks, unlocks, restores, is_lost_calls, enum_calls;
static uint32_t shows, hides, overlay_flags_seen, fx_size_seen;
static uint32_t flips_mock, flip_status_calls;
static uint32_t lock_flags, lock_pitch, lock_xpitch, lock_size;
static int32_t src_right, src_bottom;
static uint32_t overlay_recovered;
static uint32_t debug_count;
static uint16_t debug_last[64];

static uint32_t get32(const uint8_t *p, unsigned offset)
{
    return (uint32_t)p[offset] | ((uint32_t)p[offset + 1] << 8) |
           ((uint32_t)p[offset + 2] << 16) | ((uint32_t)p[offset + 3] << 24);
}

static void put32(uint8_t *p, unsigned offset, uint32_t value)
{
    p[offset] = (uint8_t)value;
    p[offset + 1] = (uint8_t)(value >> 8);
    p[offset + 2] = (uint8_t)(value >> 16);
    p[offset + 3] = (uint8_t)(value >> 24);
}

static void set_slot(void **vt, unsigned byte_offset, void *fn)
{
    vt[byte_offset / 4] = fn;
}

void OutputDebugStringW(const CE_WCHAR *text)
{
    unsigned i;
    ++debug_count;
    for (i = 0; i < 63 && text[i]; ++i)
        debug_last[i] = text[i];
    debug_last[i] = 0;
}

CE_HANDLE GetProcessHeap(void) { return (CE_HANDLE)1; }
void *HeapAlloc(CE_HANDLE heap, uint32_t flags, uint32_t size)
{
    (void)heap; (void)flags;
    return calloc(1, size);
}
int HeapFree(CE_HANDLE heap, uint32_t flags, void *memory)
{
    (void)heap; (void)flags;
    free(memory);
    return 1;
}

CE_HANDLE LoadLibraryW(const CE_WCHAR *name)
{
    ++loads;
    if (scenario == S_LOAD_FAIL)
        return 0;
    if (scenario == S_FALLBACK_PATH && name[0] != '\\')
        return 0;
    return (CE_HANDLE)&dd_object;
}

void *GetProcAddressA(CE_HANDLE module, const char *name)
{
    (void)module;
    ++procs;
    return (scenario == S_NO_PROC || strcmp(name, "DirectDrawCreate")) ? 0 : (void *)mock_direct_draw_create;
}

int FreeLibrary(CE_HANDLE module)
{
    (void)module;
    ++frees;
    return 1;
}

static int32_t mock_direct_draw_create(void *guid, void **out, void *outer)
{
    (void)guid; (void)outer;
    if (scenario == S_DD_CREATE_FAIL)
        return -1;
    *out = &dd_object;
    dd_object.refs = 1;
    return 0;
}

static uint32_t mock_dd_release(void *object)
{
    FakeObject *fake = object;
    if (fake->refs)
        --fake->refs;
    return fake->refs;
}

static uint32_t mock_surface_add_ref(void *object)
{
    FakeObject *fake = object;
    return ++fake->refs;
}

static int32_t mock_cooperative(void *object, CE_HANDLE window, uint32_t flags)
{
    (void)object;
    coop_flags = flags;
    coop_window = (uint32_t)(uintptr_t)window;
    return scenario == S_COOP_FAIL ? -1 : 0;
}

static int32_t mock_get_caps(void *object, void *driver, void *emulation)
{
    uint8_t *bytes = driver;
    (void)object; (void)emulation;
    ++cap_calls;
    if (cap_calls <= 2)
        caps_sizes[cap_calls - 1] = get32(bytes, 0);
    if (scenario == S_CAPS_FAIL || (scenario == S_CAPS_RETRY && cap_calls == 1))
        return -1;
    overlay_caps_seen = scenario == S_NO_OVERLAY_CAPS ? OV_FOURCC : overlay_caps_value;
    put32(bytes, 0x48, overlay_caps_seen);
    return 0;
}

static int32_t mock_get_fourcc(void *object, uint32_t *count, uint32_t *codes)
{
    static const uint32_t supported[4] = {0, UYVY_FCC, 0x56555949U, 0};
    (void)object;
    if (!codes) {
        *count = scenario == S_NO_FOURCC ? 3U : 4U;
        return 0;
    }
    if (*count < 4)
        return -1;
    memcpy(codes, supported, sizeof(supported));
    return 0;
}

static int32_t mock_create_surface(void *object, void *desc, void **out, void *outer)
{
    uint8_t *bytes = desc;
    unsigned index = creates++;
    (void)object; (void)outer;
    if (index < 3) {
        create_flags[index] = get32(bytes, 4);
        create_caps[index] = get32(bytes, 100);
    }
    if (!index) {
        if (scenario == S_PRIMARY_FAIL)
            return -1;
        *out = &primary_object;
        primary_object.refs = 1;
        return 0;
    }
    if (index > 1) {
        create_w = get32(bytes, 12);
        create_h = get32(bytes, 8);
    } else {
        create_w = get32(bytes, 12);
        create_h = get32(bytes, 8);
        pixel_size = get32(bytes, 68);
        pixel_flags = get32(bytes, 72);
        fourcc_seen = get32(bytes, 76);
    }
    if (scenario == S_OVERLAY_FAIL)
        return -1;
    *out = &overlay_object;
    overlay_object.refs = 1;
    return 0;
}

static int32_t mock_enum_attached(void *object, void *caps, void (*callback)(void *, void *, void *), void *context)
{
    uint8_t *bytes = caps;
    (void)object;
    ++enum_calls;
    if (get32(bytes, 0) == DDSCAPS_BACKBUFFER && scenario != S_NO_BACK)
        callback(&back_object, caps, context);
    return 1;
}

static int32_t mock_lock(void *object, void *rect, void *desc, uint32_t flags, void *event)
{
    uint8_t *bytes = desc;
    int32_t pitch = (int32_t)SURFACE_PITCH;
    int32_t x_pitch = 2;
    uint32_t size = SURFACE_BYTES;
    (void)object; (void)rect; (void)event;
    ++locks;
    lock_flags = flags;
    if (scenario == S_BAD_PITCH)
        pitch = I30_VIDEO_WIDTH;
    if (scenario == S_BAD_XPITCH)
        x_pitch = -2;
    if (scenario == S_ZERO_FIELDS) {
        x_pitch = 0;
        size = 0;
    }
    put32(bytes, 0, 108);
    put32(bytes, 8, I30_VIDEO_HEIGHT);
    put32(bytes, 12, I30_VIDEO_WIDTH);
    put32(bytes, 16, (uint32_t)pitch);
    put32(bytes, 20, (uint32_t)x_pitch);
    *(uint8_t **)(bytes + 32) = surface;
    put32(bytes, 104, size);
    lock_pitch = (uint32_t)pitch;
    lock_xpitch = (uint32_t)x_pitch;
    lock_size = size;
    if (scenario == S_LOCK_FAIL)
        return -1;
    if (scenario == S_LOST_LOCK && locks == 1)
        return DDERR_SURFACELOST_VALUE;
    return 0;
}

static int32_t mock_unlock(void *object, void *rect)
{
    (void)object; (void)rect;
    ++unlocks;
    return scenario == S_UNLOCK_FAIL ? -1 : 0;
}

static int32_t mock_restore(void *object)
{
    (void)object;
    ++restores;
    return scenario == S_RESTORE_FAIL ? -1 : 0;
}

static int32_t mock_is_lost(void *object)
{
    (void)object;
    ++is_lost_calls;
    if (scenario == S_RESTORE_FAIL)
        return DDERR_SURFACELOST_VALUE;
    return (scenario == S_LOST_LOCK && is_lost_calls == 1) ? DDERR_SURFACELOST_VALUE : 0;
}

static int32_t mock_update_overlay(void *object, void *src, void *dest, void *dst_rect,
                                   uint32_t flags, void *fx)
{
    int32_t *rect = src;
    (void)object; (void)dest; (void)dst_rect;
    fx_size_seen = get32(fx, 0);
    if (flags & 0x400U) {
        overlay_flags_seen = flags;
        ++shows;
        if (rect) {
            src_right = rect[2];
            src_bottom = rect[3];
        }
    } else {
        ++hides;
    }
    if (scenario == S_OVERLAY_FAIL_FRAME && (flags & 0x400U))
        return -1;
    if (scenario == S_OVERLAY_LOST && !overlay_recovered) {
        overlay_recovered = 1;
        return DDERR_SURFACELOST_VALUE;
    }
    return 0;
}

static int32_t mock_flip(void *object, void *target, uint32_t flags)
{
    (void)object; (void)target; (void)flags;
    ++flips_mock;
    return scenario == S_FLIP_FAIL ? -1 : 0;
}

static int32_t mock_flip_status(void *object, uint32_t flags)
{
    (void)object; (void)flags;
    ++flip_status_calls;
    return scenario == S_FLIP_TIMEOUT ? -1 : 0;
}

static void install_vtables(void)
{
    memset(dd_vt, 0, sizeof(dd_vt));
    memset(surface_vt, 0, sizeof(surface_vt));
    memset(&dd_object, 0, sizeof(dd_object));
    memset(&primary_object, 0, sizeof(primary_object));
    memset(&overlay_object, 0, sizeof(overlay_object));
    memset(&back_object, 0, sizeof(back_object));
    dd_object.vt = dd_vt;
    primary_object.vt = surface_vt;
    overlay_object.vt = surface_vt;
    back_object.vt = surface_vt;
    set_slot(dd_vt, 0x08, (void *)mock_dd_release);
    set_slot(dd_vt, 0x14, (void *)mock_create_surface);
    set_slot(dd_vt, 0x24, (void *)mock_get_caps);
    set_slot(dd_vt, 0x2c, (void *)mock_get_fourcc);
    set_slot(dd_vt, 0x44, (void *)mock_cooperative);
    set_slot(surface_vt, 0x04, (void *)mock_surface_add_ref);
    set_slot(surface_vt, 0x08, (void *)mock_dd_release);
    set_slot(surface_vt, 0x14, (void *)mock_enum_attached);
    set_slot(surface_vt, 0x1c, (void *)mock_flip);
    set_slot(surface_vt, 0x34, (void *)mock_flip_status);
    set_slot(surface_vt, 0x48, (void *)mock_is_lost);
    set_slot(surface_vt, 0x4c, (void *)mock_lock);
    set_slot(surface_vt, 0x54, (void *)mock_restore);
    set_slot(surface_vt, 0x68, (void *)mock_unlock);
    set_slot(surface_vt, 0x6c, (void *)mock_update_overlay);
}

static void configure(unsigned value)
{
    unsigned i;
    scenario = value;
    loads = frees = procs = creates = coop_flags = coop_window = 0;
    caps_sizes[0] = caps_sizes[1] = overlay_caps_seen = 0;
    create_flags[0] = create_flags[1] = create_flags[2] = 0;
    create_caps[0] = create_caps[1] = create_caps[2] = 0;
    create_w = create_h = pixel_size = pixel_flags = fourcc_seen = 0;
    cap_calls = 0;
    locks = unlocks = restores = is_lost_calls = enum_calls = 0;
    shows = hides = overlay_flags_seen = fx_size_seen = 0;
    flips_mock = flip_status_calls = lock_flags = lock_pitch = lock_xpitch = lock_size = 0;
    src_right = src_bottom = 0;
    overlay_recovered = debug_count = 0;
    memset(debug_last, 0, sizeof(debug_last));
    memset(surface, 0xa5, sizeof(surface));
    for (i = 0; i < 16; ++i)
        i420[i] = (uint8_t)(16 + i);
    for (i = 0; i < 8; ++i) {
        i420[32 + i] = (uint8_t)(90 + i);
        i420[40 + i] = (uint8_t)(240 + i);
    }
    overlay_caps_value = OV_SUPPORT | OV_FOURCC;
    if (value == S_NO_BACK || value == S_FLIP_FAIL || value == S_FLIP_TIMEOUT)
        overlay_caps_value |= OV_FLIP;
    install_vtables();
}

__declspec(dllexport) int test_case(unsigned value, DdrawResult *out)
{
    static const uint8_t expected[8] = {91, 18, 241, 19, 92, 20, 242, 21};
    I30Ddraw backend;
    I30VideoGeometry geometry = {8, 4, 2, 0, 4, 2};
    unsigned i;
    int opened;

    configure(value);
    memset(out, 0, sizeof(*out));
    opened = i30_ddraw_open((CE_HANDLE)0x1234U, &backend);
    out->opened = opened;
    for (i = 0; i < 4; ++i)
        out->present[i] = i30_ddraw_present(value == S_NULL_PRESENT ? 0 : &backend, &geometry, i420);
    out->failures = backend.failures;
    out->disabled = backend.disabled;
    out->presented = backend.presented;
    out->flips = backend.flips;
    out->backend_restored = backend.restored;
    i30_ddraw_hide(&backend);
    i30_ddraw_close(&backend);

    out->loads = loads;
    out->frees = frees;
    out->procs = procs;
    out->creates = creates;
    out->refs_live = dd_object.refs + primary_object.refs + overlay_object.refs + back_object.refs;
    out->locks = locks;
    out->unlocks = unlocks;
    out->restores = restores;
    out->is_lost_calls = is_lost_calls;
    out->enum_calls = enum_calls;
    out->shows = shows;
    out->hides = hides;
    out->overlay_flags = overlay_flags_seen;
    out->fx_size = fx_size_seen;
    out->flips_mock = flips_mock;
    out->flip_status_calls = flip_status_calls;
    out->coop_flags = coop_flags;
    out->coop_window = coop_window;
    out->caps_sizes[0] = caps_sizes[0];
    out->caps_sizes[1] = caps_sizes[1];
    out->overlay_caps = overlay_caps_seen;
    out->create_flags[0] = create_flags[0];
    out->create_flags[1] = create_flags[1];
    out->create_flags[2] = create_flags[2];
    out->create_caps[0] = create_caps[0];
    out->create_caps[1] = create_caps[1];
    out->create_caps[2] = create_caps[2];
    out->create_w = create_w;
    out->create_h = create_h;
    out->pixel_size = pixel_size;
    out->pixel_flags = pixel_flags;
    out->fourcc = fourcc_seen;
    out->lock_flags = lock_flags;
    out->lock_pitch = lock_pitch;
    out->lock_xpitch = lock_xpitch;
    out->lock_size = lock_size;
    out->src_right = src_right;
    out->src_bottom = src_bottom;
    out->pack_ok = memcmp(surface, expected, sizeof(expected)) == 0;
    out->padding_ok = surface[8] == 0xa5 && surface[2 * SURFACE_PITCH + 8] == 0xa5;
    out->debug_count = debug_count;
    memcpy(out->debug_last, debug_last, sizeof(debug_last));
    return opened;
}
'''


class DdrawResult(ctypes.Structure):
    _fields_ = [
        ('opened', ctypes.c_int),
        ('present', ctypes.c_int * 4),
        ('failures', ctypes.c_uint32),
        ('disabled', ctypes.c_uint32),
        ('presented', ctypes.c_uint32),
        ('flips', ctypes.c_uint32),
        ('restored', ctypes.c_uint32),
        ('backend_restored', ctypes.c_uint32),
        ('loads', ctypes.c_uint32),
        ('frees', ctypes.c_uint32),
        ('procs', ctypes.c_uint32),
        ('creates', ctypes.c_uint32),
        ('refs_live', ctypes.c_uint32),
        ('locks', ctypes.c_uint32),
        ('unlocks', ctypes.c_uint32),
        ('restores', ctypes.c_uint32),
        ('is_lost_calls', ctypes.c_uint32),
        ('enum_calls', ctypes.c_uint32),
        ('shows', ctypes.c_uint32),
        ('hides', ctypes.c_uint32),
        ('overlay_flags', ctypes.c_uint32),
        ('fx_size', ctypes.c_uint32),
        ('flips_mock', ctypes.c_uint32),
        ('flip_status_calls', ctypes.c_uint32),
        ('coop_flags', ctypes.c_uint32),
        ('coop_window', ctypes.c_uint32),
        ('caps_sizes', ctypes.c_uint32 * 2),
        ('overlay_caps', ctypes.c_uint32),
        ('create_flags', ctypes.c_uint32 * 3),
        ('create_caps', ctypes.c_uint32 * 3),
        ('create_w', ctypes.c_uint32),
        ('create_h', ctypes.c_uint32),
        ('pixel_size', ctypes.c_uint32),
        ('pixel_flags', ctypes.c_uint32),
        ('fourcc', ctypes.c_uint32),
        ('lock_flags', ctypes.c_uint32),
        ('lock_pitch', ctypes.c_uint32),
        ('lock_xpitch', ctypes.c_uint32),
        ('lock_size', ctypes.c_uint32),
        ('src_right', ctypes.c_int32),
        ('src_bottom', ctypes.c_int32),
        ('pack_ok', ctypes.c_uint32),
        ('padding_ok', ctypes.c_uint32),
        ('debug_count', ctypes.c_uint32),
        ('debug_last', ctypes.c_uint16 * 64),
    ]


class I30UyvyDdrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ZIG.is_file():
            return
        cls.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        directory = Path(cls.temporary.name)
        harness = directory / 'ddraw_harness.c'
        library = directory / 'ddraw_harness.dll'
        harness.write_text(HARNESS, encoding='ascii')
        subprocess.run([
            str(ZIG), 'cc', '-target', 'x86_64-windows-gnu', '-fshort-wchar', '-O2',
            '-DI30_VIDEO_UYVY_DIRECTDRAW', '-DI30_DDRAW_FLIP', '-DI30_DDRAW_HOST_HARNESS',
            '-I' + str(ROOT / 'src/ce'), '-shared', str(harness),
            str(ROOT / 'src/ce/ce_aa_uyvy_ddraw.c'), '-o', str(library),
        ], check=True)
        dll = ctypes.CDLL(str(library))
        cls.case = dll.test_case
        cls.case.argtypes = [ctypes.c_uint, ctypes.POINTER(DdrawResult)]
        cls.case.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'temporary', None):
            cls.temporary.cleanup()

    def run_case(self, scenario):
        result = DdrawResult()
        self.assertEqual(self.case(scenario, ctypes.byref(result)), result.opened)
        return result

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_success_uses_ce6_abi_and_preserves_pitch_padding(self):
        result = self.run_case(SUCCESS)
        self.assertEqual(result.opened, 1)
        self.assertEqual(list(result.present), [1, 1, 1, 1])
        self.assertEqual(result.coop_flags, 0)  # DDSCL_NORMAL, not fullscreen.
        self.assertEqual(result.coop_window, 0x1234)
        self.assertEqual(list(result.caps_sizes), [112, 0])  # Natural CE6 size succeeds first.
        self.assertEqual(result.overlay_caps, 0x80000004)
        self.assertEqual(result.create_flags[0], 0x1)  # Primary: DDSD_CAPS.
        self.assertEqual(result.create_caps[0], 0x40)  # DDSCAPS_PRIMARYSURFACE.
        self.assertEqual(result.create_flags[1] & 0x1026, 0x1006)  # Caps/width/height/pixelformat; no flip caps.
        self.assertEqual(result.create_caps[1] & 0x18, 0x10)  # Overlay, no flip.
        self.assertEqual((result.create_w, result.create_h), (800, 480))
        self.assertEqual((result.pixel_size, result.pixel_flags, result.fourcc), (32, 4, 0x59565955))
        self.assertEqual(result.lock_flags, 0xa)  # WRITEONLY | WAITNOTBUSY.
        self.assertEqual((result.lock_pitch, result.lock_xpitch, result.lock_size), (1632, 2, 1632 * 480))
        self.assertEqual((result.src_right, result.src_bottom), (4, 2))
        self.assertEqual(result.fx_size, 28)
        self.assertEqual((result.overlay_flags & 0x400, result.overlay_flags & 0x4000), (0x400, 0x4000))
        self.assertEqual(result.pack_ok, 1)
        self.assertEqual(result.padding_ok, 1)
        self.assertEqual(result.refs_live, 0)
        self.assertEqual(result.loads, result.frees)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_caps_natural_size_failure_retries_stock_buffer_size(self):
        result = self.run_case(CAPS_RETRY)
        self.assertEqual(result.opened, 1)
        self.assertEqual(list(result.present), [1, 1, 1, 1])
        self.assertEqual(list(result.caps_sizes), [112, 128])
        self.assertEqual(result.refs_live, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_loader_and_capability_failures_fall_back_without_leaks(self):
        for scenario in (LOAD_FAIL, NO_PROC, DD_CREATE_FAIL, COOP_FAIL, CAPS_FAIL,
                         NO_OVERLAY_CAPS, NO_FOURCC, PRIMARY_FAIL, OVERLAY_FAIL):
            with self.subTest(scenario=scenario):
                result = self.run_case(scenario)
                self.assertEqual(result.opened, 0)
                self.assertEqual(list(result.present), [0, 0, 0, 0])
                self.assertEqual(result.refs_live, 0)
                if scenario == LOAD_FAIL:
                    self.assertEqual((result.loads, result.frees), (2, 0))
                else:
                    self.assertEqual(result.loads, result.frees)
                self.assertGreater(result.debug_count, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_missing_back_buffer_degrades_to_nonflip_overlay(self):
        result = self.run_case(NO_BACK)
        self.assertEqual(result.opened, 1)
        self.assertEqual(list(result.present), [1, 1, 1, 1])
        self.assertEqual(result.enum_calls, 1)
        self.assertEqual(result.creates, 3)  # Primary, failed flip overlay, nonflip overlay.
        self.assertEqual(result.create_caps[2] & 0x18, 0x10)
        self.assertEqual(result.flips_mock, 0)
        self.assertEqual(result.refs_live, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_bad_pitch_and_x_pitch_reject_frame_then_disable_after_three(self):
        for scenario in (BAD_PITCH, BAD_XPITCH):
            with self.subTest(scenario=scenario):
                result = self.run_case(scenario)
                self.assertEqual(result.opened, 1)
                self.assertEqual(list(result.present), [0, 0, 0, 0])
                self.assertEqual(result.disabled, 1)
                self.assertEqual(result.unlocks, 3)
                self.assertEqual(result.shows, 0)
                self.assertEqual(result.refs_live, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_zero_x_pitch_and_surface_size_are_accepted_as_unspecified(self):
        result = self.run_case(ZERO_FIELDS)
        self.assertEqual(result.opened, 1)
        self.assertEqual(list(result.present), [1, 1, 1, 1])
        self.assertEqual(result.pack_ok, 1)
        self.assertEqual(result.refs_live, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_lock_loss_restores_and_retries_same_call(self):
        result = self.run_case(LOST_LOCK)
        self.assertEqual(result.opened, 1)
        self.assertEqual(result.present[0], 1)
        self.assertEqual(result.locks, 5)  # IsLost/Lock each restore once, then retry Lock.
        self.assertEqual(result.restores, 2)
        self.assertEqual(result.backend_restored, 2)
        self.assertEqual(result.disabled, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_persistent_lock_overlay_unlock_and_restore_failures_disable_session(self):
        for scenario in (LOCK_FAIL, OVERLAY_FAIL_FRAME, UNLOCK_FAIL, RESTORE_FAIL):
            with self.subTest(scenario=scenario):
                result = self.run_case(scenario)
                self.assertEqual(result.opened, 1)
                self.assertEqual(list(result.present[:3]), [0, 0, 0])
                self.assertEqual(result.disabled, 1)
                self.assertEqual(result.refs_live, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_overlay_lost_restores_and_shows(self):
        result = self.run_case(OVERLAY_LOST)
        self.assertEqual(result.opened, 1)
        self.assertEqual(result.present[0], 1)
        self.assertEqual(result.restores, 1)
        self.assertEqual(result.shows, 5)  # First frame retries show; later frames show once.
        self.assertEqual(result.refs_live, 0)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_flip_failure_and_timeout_reuse_same_frame_then_disable(self):
        for scenario in (FLIP_FAIL, FLIP_TIMEOUT):
            with self.subTest(scenario=scenario):
                result = self.run_case(scenario)
                self.assertEqual(result.opened, 1)
                self.assertEqual(list(result.present[:3]), [0, 0, 0])
                self.assertEqual(result.disabled, 1)
                self.assertEqual(result.flips_mock, 1)
                self.assertEqual(result.flip_status_calls, 1 if scenario == FLIP_TIMEOUT else 0)
                self.assertEqual(result.refs_live, 0)
        timeout = self.run_case(FLIP_TIMEOUT)
        self.assertEqual(timeout.enum_calls, 1)
        self.assertEqual(timeout.create_flags[1] & 0x20, 0x20)  # Backbuffer requested.

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_null_context_and_windows_path_fallback_are_safe(self):
        result = self.run_case(NULL_PRESENT)
        self.assertEqual(result.opened, 1)
        self.assertEqual(list(result.present), [0, 0, 0, 0])
        self.assertEqual(result.refs_live, 0)
        fallback = self.run_case(FALLBACK_PATH)
        self.assertEqual(fallback.opened, 1)
        self.assertEqual(fallback.loads, 2)
        self.assertEqual(fallback.frees, 1)

    def test_production_build_has_no_host_test_seam(self):
        source = (ROOT / 'src/ce/ce_aa_uyvy_ddraw.c').read_text(encoding='utf-8')
        self.assertIn('I30_DDRAW_HOST_HARNESS', source)
        self.assertNotIn('-DI30_DDRAW_HOST_HARNESS', (ROOT / 'tools/build_ce_usb.py').read_text(encoding='utf-8'))
        self.assertNotIn('-DI30_DDRAW_HOST_HARNESS', (ROOT / 'tools/build_ce_minimal.py').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
