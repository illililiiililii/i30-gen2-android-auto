"""Host checks for the diagnostics-only UYVY receiver stage.

The stage packs into memory but returns 0 so ce_aa_video.c keeps BGRA + GDI as
the visible output. These tests prove only the in-memory contract, not a
DirectDraw surface or real hardware acceleration.
"""

import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZIG = Path(os.environ.get('LOCALAPPDATA', '')) / 'i30-phase5-tools/zig/zig-x86_64-windows-0.15.2/zig.exe'

HARNESS = r'''
#include "ce_aa_uyvy_stage.h"

__declspec(dllexport) unsigned test_stage_bytes(void)
{
    return I30_UYVY_STAGE_BYTES;
}

__declspec(dllexport) int test_stage(uint8_t *surface, unsigned coded_w, unsigned coded_h,
                                     unsigned left, unsigned top, unsigned width, unsigned height,
                                     const uint8_t *i420, unsigned *frames)
{
    I30UyvyStage stage = {surface, 0};
    I30VideoGeometry geometry = {coded_w, coded_h, left, top, width, height};
    int result = i30_uyvy_stage(&stage, &geometry, i420);
    *frames = stage.frames;
    return result;
}
'''


class I30UyvyStageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ZIG.is_file():
            return
        cls.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        directory = Path(cls.temporary.name)
        harness = directory / 'uyvy_stage_harness.c'
        library = directory / 'uyvy_stage.dll'
        harness.write_text(HARNESS, encoding='ascii')
        subprocess.run([str(ZIG), 'cc', '-target', 'x86_64-windows-gnu', '-O2',
                        '-DI30_VIDEO_UYVY_STAGING', '-I' + str(ROOT / 'src/ce'), '-shared', str(harness),
                        str(ROOT / 'src/ce/ce_aa_uyvy_stage.c'), '-o', str(library)], check=True)
        dll = ctypes.CDLL(str(library))
        cls.bytes = dll.test_stage_bytes
        cls.bytes.restype = ctypes.c_uint
        cls.stage = dll.test_stage
        cls.stage.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                              ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint)]
        cls.stage.restype = ctypes.c_int

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'temporary', None):
            cls.temporary.cleanup()

    def surface(self):
        data = (ctypes.c_ubyte * self.bytes())()
        ctypes.memset(data, 0xa5, self.bytes())
        return data

    def i420(self):
        luma = bytes(range(16, 48))
        cb = bytes(range(90, 98))
        cr = bytes(range(240, 248))
        return (ctypes.c_ubyte * len(luma + cb + cr)).from_buffer_copy(luma + cb + cr)

    def call_stage(self, surface, width=4, frames=None):
        counter = ctypes.c_uint()
        result = self.stage(surface, 8, 4, 2, 0, width, 2, self.i420(), ctypes.byref(counter))
        return result, counter.value, surface

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_packs_cropped_uyvy_and_preserves_row_padding(self):
        frames = ctypes.c_uint()
        surface = self.surface()
        result = self.stage(surface, 8, 4, 2, 0, 4, 2, self.i420(), ctypes.byref(frames))
        self.assertEqual(result, 0)  # BGRA/GDI remains the visible path.
        self.assertEqual(frames.value, 1)
        expected = bytes((91, 18, 241, 19, 92, 20, 242, 21))
        self.assertEqual(bytes(surface[:8]), expected)
        self.assertEqual(bytes(surface[1632:1640]), bytes((91, 26, 241, 27, 92, 28, 242, 29)))
        pitch = 800 * 2 + 32
        self.assertEqual(bytes(surface[8:8 + 32]), bytes([0xa5]) * 32)
        self.assertEqual(bytes(surface[2 * pitch + 8:2 * pitch + 40]), bytes([0xa5]) * 32)

    @unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
    def test_failure_paths_never_claim_a_packed_frame(self):
        frames = ctypes.c_uint()
        self.assertEqual(self.stage(None, 8, 4, 2, 0, 4, 2, self.i420(), ctypes.byref(frames)), 0)
        self.assertEqual(frames.value, 0)
        odd_width = self.stage(self.surface(), 8, 4, 2, 0, 3, 2, self.i420(), ctypes.byref(frames))
        self.assertEqual(odd_width, 0)
        self.assertEqual(frames.value, 0)

    def test_stage_is_not_a_directdraw_backend(self):
        source = (ROOT / 'src/ce/ce_aa_uyvy_stage.c').read_text(encoding='utf-8')
        self.assertNotIn('DDRAW', source)
        self.assertIn('return 0;', source)


if __name__ == '__main__':
    unittest.main()
