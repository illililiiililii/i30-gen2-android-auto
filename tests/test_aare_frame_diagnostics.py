"""Checks for the standalone AARE frame crop/shift comparator."""

import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

try:
    import av  # noqa: F401
except ImportError:
    av = None

from compare_aare_frame import analyze, load_rgb  # noqa: E402
from gd13my_display import png  # noqa: E402


def rgb_pattern(width, height):
    return bytes(((x * 17 + y * 31) & 255 for y in range(height) for x in range(width) for _ in range(3)))


def write_png(path, width, height, pixels):
    path.write_bytes(png(width, height,
                         b''.join(b'\0' + pixels[row * width * 3:(row + 1) * width * 3]
                                  for row in range(height))))


def png_size(path):
    return struct.unpack('>II', path.read_bytes()[16:24])


@unittest.skipUnless(av is not None, 'PyAV is not installed')
class AareFrameDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.directory = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_identical_frames_have_zero_error_and_write_diff_images(self):
        source = self.directory / 'source.png'
        display = self.directory / 'display.png'
        pixels = rgb_pattern(16, 8)
        write_png(source, 16, 8, pixels)
        write_png(display, 16, 8, pixels)
        output = self.directory / 'diff'
        report = analyze(source, display, output=output)
        self.assertEqual(report['mae'], 0)
        self.assertEqual(report['rmse'], 0)
        self.assertEqual(report['max_absolute_error'], 0)
        self.assertEqual(report['differing_pixels'], 0)
        self.assertEqual(png_size(Path(report['diff_png'])), (16, 8))
        self.assertEqual(png_size(Path(report['source_aligned_png'])), (16, 8))
        self.assertTrue((output / 'frame-diff.png').is_file())
        json.dumps(report)

    def test_shift_is_applied_to_the_display_coordinates(self):
        source = self.directory / 'source.png'
        display = self.directory / 'display.png'
        source_pixels = rgb_pattern(16, 8)
        write_png(source, 16, 8, source_pixels)
        width, height = 20, 10
        canvas = bytearray(width * height * 3)
        for row in range(8):
            start = ((row + 1) * width + 2) * 3
            canvas[start:start + 16 * 3] = source_pixels[row * 16 * 3:(row + 1) * 16 * 3]
        write_png(display, width, height, bytes(canvas))
        correct = analyze(source, display, shift=(2, 1))
        wrong = analyze(source, display, shift=(1, 1))
        self.assertEqual(correct['mae'], 0)
        self.assertEqual(correct['display_rect'], [2, 1, 16, 8])
        self.assertGreater(wrong['mae'], 0)
        self.assertGreater(wrong['rmse'], 0)

    def test_explicit_crop_and_display_crop_align(self):
        source = self.directory / 'source.png'
        display = self.directory / 'display.png'
        source_pixels = rgb_pattern(16, 8)
        write_png(source, 16, 8, source_pixels)
        crop = (4, 2, 8, 4)
        region = bytearray(8 * 4 * 3)
        for row in range(4):
            start = ((row + crop[1]) * 16 + crop[0]) * 3
            region[row * 24:(row + 1) * 24] = source_pixels[start:start + 24]
        write_png(display, 8, 4, bytes(region))
        report = analyze(source, display, crop=crop, display_crop=(0, 0, 8, 4))
        self.assertEqual(report['mae'], 0)
        self.assertEqual(report['source_rect'], list(crop))

    def test_raw_i420_is_decoded_and_size_is_validated(self):
        raw = self.directory / 'frame.i420'
        raw.write_bytes(bytes([81]) * (16 * 8 * 3 // 2))
        width, height, pixels = load_rgb(raw, (16, 8), 'i420')
        self.assertEqual((width, height, len(pixels)), (16, 8, 16 * 8 * 3))
        reference = self.directory / 'reference.png'
        write_png(reference, 16, 8, pixels)
        report = analyze(raw, reference, source_format='i420', source_size=(16, 8))
        self.assertEqual(report['mae'], 0)
        raw.write_bytes(b'short')
        with self.assertRaises(ValueError):
            load_rgb(raw, (16, 8), 'i420')


if __name__ == '__main__':
    unittest.main()
