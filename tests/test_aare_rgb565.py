"""Host-side checks for the CE direct YUV420 -> RGB565 converter."""

import ctypes
import os
from pathlib import Path
import random
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ZIG = Path(os.environ.get('LOCALAPPDATA', '')) / 'i30-phase5-tools/zig/zig-x86_64-windows-0.15.2/zig.exe'

HARNESS = r'''
#include "ce_aa_rgb565.h"

__declspec(dllexport) void i30_test_convert(unsigned width, unsigned height,
                                            const uint8_t *y, const uint8_t *cb,
                                            const uint8_t *cr, uint16_t *out)
{
    i30_yuv420_to_rgb565_impl(width, height, y, cb, cr, out);
}
'''


def reference_pixel(y, cb, cr):
    """Integer path used by h264bsdConvertToBGRA, reduced to RGB565."""
    c, d, e = y - 16, cb - 128, cr - 128
    channels = ((298 * c + 409 * e + 128) >> 8,
                (298 * c - 100 * d - 208 * e + 128) >> 8,
                (298 * c + 516 * d + 128) >> 8)
    r, g, b = (max(0, min(255, value)) for value in channels)
    return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)


@unittest.skipUnless(ZIG.is_file(), 'local Zig host C compiler is absent')
class AareRgb565Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        directory = Path(cls.temporary.name)
        source = directory / 'harness.c'
        source.write_text(HARNESS, encoding='ascii')
        library = directory / 'rgb565.dll'
        subprocess.run([str(ZIG), 'cc', '-target', 'x86_64-windows-gnu', '-O2',
                        '-I' + str(ROOT / 'src/ce'), '-shared', str(source),
                        '-o', str(library)], check=True)
        cls.convert = ctypes.CDLL(str(library)).i30_test_convert
        cls.convert.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_void_p,
                                ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def convert_frame(self, width, height, luma, cb=None, cr=None):
        luma = bytes(luma)
        cb = bytes(cb if cb is not None else [128] * (width // 2 * height // 2))
        cr = bytes(cr if cr is not None else [128] * (width // 2 * height // 2))
        out = (ctypes.c_uint16 * (width * height))()
        self.convert(width, height, luma, cb, cr, out)
        return out

    def test_masks_match_little_endian_rgb565(self):
        self.assertEqual((0xf800, 0x07e0, 0x001f),
                         (31 << 11, 63 << 5, 31))

    def test_primaries_are_not_swapped(self):
        samples = {
            'red': (81, 90, 240),
            'green': (145, 54, 34),
            'blue': (41, 240, 110),
            'white': (235, 128, 128),
            'black': (16, 128, 128),
        }
        values = {}
        for name, pixel in samples.items():
            result = self.convert_frame(2, 2, [pixel[0]] * 4, [pixel[1]], [pixel[2]])[0]
            values[name] = ((result >> 11) & 31, (result >> 5) & 63, result & 31)
        self.assertEqual(values['black'], (0, 0, 0))
        self.assertEqual(values['white'], (31, 63, 31))
        self.assertGreater(values['red'][0], 24)
        self.assertGreater(values['green'][1], 24)
        self.assertGreater(values['blue'][2], 24)
        self.assertLess(values['red'][2], 8)
        self.assertLess(values['green'][0], 8)
        self.assertLess(values['blue'][0], 8)

    def test_matches_bgra_rounding_for_sampled_yuv(self):
        rng = random.Random(0x565)
        luma = [rng.randrange(0, 256) for _ in range(256)]
        cb = [rng.randrange(0, 256) for _ in range(64)]
        cr = [rng.randrange(0, 256) for _ in range(64)]
        result = self.convert_frame(16, 16, luma, cb, cr)
        for row in range(16):
            for col in range(16):
                expected = reference_pixel(luma[row * 16 + col],
                                           cb[(row // 2) * 8 + col // 2],
                                           cr[(row // 2) * 8 + col // 2])
                self.assertEqual(result[row * 16 + col], expected, (row, col))

    def test_rows_are_top_down_and_tightly_packed(self):
        width, height = 8, 6
        luma = [16 + 8 * row for row in range(height) for _ in range(width)]
        cb = [90 + row for row in range(height // 2) for _ in range(width // 2)]
        cr = [180 - row for row in range(height // 2) for _ in range(width // 2)]
        result = self.convert_frame(width, height, luma, cb, cr)
        self.assertEqual(len(result), width * height)
        for row in range(height):
            for col in range(width):
                expected = reference_pixel(luma[row * width + col],
                                           cb[(row // 2) * (width // 2) + col // 2],
                                           cr[(row // 2) * (width // 2) + col // 2])
                self.assertEqual(result[row * width + col], expected, (row, col))
        self.assertNotEqual(result[0], result[(height - 1) * width])


if __name__ == '__main__':
    unittest.main()
