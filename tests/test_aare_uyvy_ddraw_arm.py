"""ARM Unicorn contract tests for the opt-in UYVY DirectDraw backend.

These tests use the standalone ARM probe built by tools/build_ce_minimal.py and
CE6 API/COM doubles. They verify guest call order, descriptor offsets and
same-frame BGRA/GDI fallback, not real DDRAW.dll behaviour or LCD output.
"""

from pathlib import Path
import unittest

from tools.verify_ce_uyvy_three_path_benchmark import DdrawProbe
from tools.verify_ce_uyvy_staging import sample


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / 'build/gd13my-ce-uyvy-ddraw-noflip/i30video.exe'
FLIP_ARTIFACT = ROOT / 'build/gd13my-ce-uyvy-ddraw/i30video.exe'


class ArmUyvyDdrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ARTIFACT.is_file():
            return
        cls.stream = sample(800, 480)

    def run_probe(self, path, mode=None, flip=False):
        probe = DdrawProbe(path, self.stream, mode=mode, flip=flip)
        probe.run(probe.pe.OPTIONAL_HEADER.AddressOfEntryPoint)
        self.assertEqual(probe.live_bytes, 0)
        self.assertEqual(probe.allocations, {})
        self.assertTrue(all(count == 0 for count in probe.ddraw['refs'].values()), probe.ddraw['refs'])
        return probe

    def run_mode(self, mode):
        return self.run_probe(ARTIFACT, mode=mode)

    @unittest.skipUnless(ARTIFACT.is_file(), 'build the ddraw ARM probe first')
    def test_success_presents_without_gdi_fallback(self):
        probe = self.run_mode(None)
        self.assertEqual(probe.status, 0)
        self.assertEqual(probe.blits, [])
        self.assertEqual((probe.ddraw['shows'], probe.ddraw['locks'], probe.ddraw['unlocks']), (1, 1, 1))
        self.assertEqual(probe.ddraw['show_flags'][0] & 0x400, 0x400)
        self.assertEqual(probe.ddraw['src_rects'], [(0, 0, 800, 480)])
        self.assertEqual(probe.ddraw['loads'], ['DDRAW.dll'])
        self.assertEqual(probe.ddraw['frees'], 1)

    @unittest.skipUnless(ARTIFACT.is_file(), 'build the ddraw ARM probe first')
    def test_initialization_failures_disable_output_without_a_frame(self):
        for mode in ('library', 'proc', 'create', 'cooperative', 'caps', 'fourcc', 'surface'):
            with self.subTest(mode=mode):
                probe = self.run_mode(mode)
                self.assertEqual(probe.status, 1)
                self.assertEqual(probe.blits, [])
                self.assertEqual(probe.ddraw['shows'], 0)

    @unittest.skipUnless(ARTIFACT.is_file(), 'build the ddraw ARM probe first')
    def test_bad_pitch_lock_and_overlay_failures_reuse_same_frame_for_gdi(self):
        for mode in ('bad-pitch', 'bad-xpitch', 'lock', 'overlay', 'restore'):
            with self.subTest(mode=mode):
                probe = self.run_mode(mode)
                self.assertEqual(probe.status, 0)
                self.assertEqual(len(probe.blits), 1)
                self.assertEqual(probe.blits[0][0], (40, 800, -480, 1, 32))
                self.assertEqual(probe.ddraw['shows'], 0 if mode != 'overlay' else 1)

    @unittest.skipUnless(ARTIFACT.is_file(), 'build the ddraw ARM probe first')
    def test_surface_loss_restores_and_retries(self):
        probe = self.run_mode('lost')
        self.assertEqual(probe.status, 0)
        self.assertEqual(probe.blits, [])
        self.assertEqual((probe.ddraw['restores'], probe.ddraw['shows']), (1, 1))
        restored = self.run_mode('overlay-lost')
        self.assertEqual(restored.status, 0)
        self.assertEqual(restored.blits, [])
        self.assertEqual((restored.ddraw['restores'], restored.ddraw['shows']), (1, 2))

    @unittest.skipUnless(ARTIFACT.is_file(), 'build the ddraw ARM probe first')
    def test_unlock_failure_falls_back(self):
        probe = self.run_mode('unlock')
        self.assertEqual(probe.status, 0)
        self.assertEqual(len(probe.blits), 1)
        self.assertEqual(probe.ddraw['unlocks'], 1)

    @unittest.skipUnless(FLIP_ARTIFACT.is_file(), 'build the flip-enabled ddraw ARM probe first')
    def test_flip_chain_presents_without_gdi_fallback(self):
        probe = self.run_probe(FLIP_ARTIFACT, flip=True)
        self.assertEqual(probe.status, 0)
        self.assertEqual(probe.blits, [])
        self.assertEqual((probe.ddraw['shows'], probe.ddraw['flips']), (1, 1))
        self.assertEqual(probe.ddraw['flip_status'], 1)

    @unittest.skipUnless(FLIP_ARTIFACT.is_file(), 'build the flip-enabled ddraw ARM probe first')
    def test_missing_back_buffer_degrades_to_nonflip_overlay(self):
        probe = self.run_probe(FLIP_ARTIFACT, mode='no-back', flip=True)
        self.assertEqual(probe.status, 0)
        self.assertEqual(probe.blits, [])
        self.assertEqual((probe.ddraw['shows'], probe.ddraw['flips']), (1, 0))

    @unittest.skipUnless(FLIP_ARTIFACT.is_file(), 'build the flip-enabled ddraw ARM probe first')
    def test_flip_failure_and_timeout_reuse_same_frame_for_gdi(self):
        for mode in ('flip', 'flip-timeout'):
            with self.subTest(mode=mode):
                probe = self.run_probe(FLIP_ARTIFACT, mode=mode, flip=True)
                self.assertEqual(probe.status, 0)
                self.assertEqual(len(probe.blits), 1)
                self.assertEqual(probe.blits[0][0], (40, 800, -480, 1, 32))
                self.assertEqual(probe.ddraw['flips'], 1)
                self.assertEqual(probe.ddraw['flip_status'], int(mode == 'flip-timeout'))


if __name__ == '__main__':
    unittest.main()
