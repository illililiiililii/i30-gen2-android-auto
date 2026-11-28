"""Virtual USB/TLS contract tests for the opt-in UYVY DirectDraw backend.

These run the ARM USB client against CE6 API/COM doubles. They verify guest
call counts, same-frame BGRA/GDI fallback and session cleanup, not real
DDRAW.dll capabilities, LCD output, camera priority or physical USB timing.
"""

import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / 'build/gd13my-ce-usb-ddraw/i30usb.dll'
FLIP_ARTIFACT = ROOT / 'build/gd13my-ce-usb-ddraw-flip/i30usb.dll'
OPENSSL = Path(os.environ.get('ProgramFiles', '')) / 'Git/usr/bin/openssl.exe'


def sample_frame():
    import av

    codec = av.CodecContext.create('libx264', 'w')
    codec.width, codec.height, codec.pix_fmt = 800, 480, 'yuv420p'
    codec.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline'}
    frame = av.VideoFrame(800, 480, 'yuv420p')
    for plane, value in zip(frame.planes, (81, 90, 240)):
        plane.update(bytes([value]) * plane.buffer_size)
    return b''.join(bytes(packet) for packet in (*codec.encode(frame), *codec.encode(None)))


class VirtualUyvyDdrawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not ARTIFACT.is_file() or not OPENSSL.is_file():
            return
        sys_path = ROOT / 'src'
        if str(sys_path) not in __import__('sys').path:
            __import__('sys').path.insert(0, str(sys_path))
        from i30_receiver.mock import test_identity
        from tools.emulate_ce_usb import NativeUsbStress, TlsUsbClient

        cls.TlsUsbClient = TlsUsbClient
        cls.NativeUsbStress = NativeUsbStress
        cls.context = test_identity(str(OPENSSL))
        cls.cert, cls.key, cls.peer = cls.context.__enter__()
        cls.files = {'i30-ca.pem': cls.cert.read_bytes(), 'i30-peer.txt': b'i30-mock.local',
                     'i30-client.pem': cls.cert.read_bytes(), 'i30-client-key.pem': cls.key.read_bytes()}
        cls.stream = sample_frame()

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, 'context', None):
            cls.context.__exit__(None, None, None)

    def assert_clean(self, guest):
        self.assertFalse(guest.allocations)
        self.assertTrue(all(count == 0 for count in guest.ddraw['refs'].values()), guest.ddraw['refs'])
        self.assertEqual(guest.ddraw['frees'], 1)
        self.assertEqual(guest.ddraw['loads'], ['DDRAW.dll'])

    @unittest.skipUnless(ARTIFACT.is_file() and OPENSSL.is_file(),
                         'build the ddraw USB ARM artifact and install local OpenSSL first')
    def test_success_presents_through_overlay_without_gdi(self):
        guest = self.TlsUsbClient(ARTIFACT, self.files, self.peer, video=self.stream)
        result = guest.attach()
        self.assertEqual(guest.video_format, 'ddraw')
        self.assertEqual(guest.painted_frames(), 1)
        self.assertEqual(guest.ddraw['shows'], 1)
        self.assertEqual((guest.ddraw['locks'], guest.ddraw['unlocks']), (1, 1))
        self.assertEqual(guest.blit_times, [])
        self.assertIn('i30 CE UYVY DirectDraw backend initialized; hardware output UNVERIFIED.', result['debug'])
        self.assertIn('i30 CE UYVY DirectDraw session closed.', result['debug'])
        self.assert_clean(guest)

    @unittest.skipUnless(ARTIFACT.is_file() and OPENSSL.is_file(),
                         'build the ddraw USB ARM artifact and install local OpenSSL first')
    def test_rejected_frames_reuse_same_frame_for_bgra_gdi(self):
        for mode in ('bad-pitch', 'lock', 'overlay', 'unlock'):
            with self.subTest(mode=mode):
                guest = self.TlsUsbClient(ARTIFACT, self.files, self.peer, video=self.stream, ddraw_mode=mode)
                result = guest.attach()
                self.assertEqual(guest.painted_frames(), 1)
                self.assertEqual(len(guest.blit_times), 1)
                self.assertEqual(guest.ddraw['shows'], int(mode == 'overlay'))
                self.assertIn('i30 CE projection frame presented.', result['debug'])
                self.assert_clean(guest)

    @unittest.skipUnless(ARTIFACT.is_file() and OPENSSL.is_file(),
                         'build the ddraw USB ARM artifact and install local OpenSSL first')
    def test_reverse_camera_hides_overlay(self):
        guest = self.NativeUsbStress(ARTIFACT, self.files, self.peer, [self.stream], failure='reverse')
        result = guest.attach()
        self.assertTrue(guest.camera_active)
        self.assertEqual(guest.painted_frames(), 1)
        self.assertGreaterEqual(guest.ddraw['shows'], 1)
        self.assertGreater(guest.ddraw['hides'], guest.ddraw['shows'])
        self.assertFalse(any('GDI' in line for line in result['debug']))
        self.assert_clean(guest)

    @unittest.skipUnless(ARTIFACT.is_file() and OPENSSL.is_file(),
                         'build the ddraw USB ARM artifact and install local OpenSSL first')
    def test_replug_releases_references_each_session(self):
        guest = self.NativeUsbStress(ARTIFACT, self.files, self.peer, [self.stream])
        for session in (1, 2):
            if session > 1:
                guest.reconnect(self.peer)
            result = guest.attach()
            self.assertEqual(guest.ddraw['shows'], 1, (session, result['debug']))
            self.assertEqual(guest.painted_frames(), 1)
            self.assert_clean(guest)

    @unittest.skipUnless(FLIP_ARTIFACT.is_file() and OPENSSL.is_file(),
                         'build the flip-enabled ddraw USB ARM artifact first')
    def test_flip_variant_presents_and_releases(self):
        guest = self.TlsUsbClient(FLIP_ARTIFACT, self.files, self.peer, video=self.stream)
        result = guest.attach()
        self.assertEqual(guest.painted_frames(), 1)
        self.assertEqual(guest.ddraw['flips'], 1)
        self.assertEqual(guest.ddraw['flip_status'], 1)
        self.assertEqual(guest.blit_times, [])
        self.assertIn('i30 CE UYVY DirectDraw session closed.', result['debug'])
        self.assert_clean(guest)

    @unittest.skipUnless(FLIP_ARTIFACT.is_file() and OPENSSL.is_file(),
                         'build the flip-enabled ddraw USB ARM artifact first')
    def test_flip_failures_reuse_same_frame_for_bgra_gdi(self):
        for mode in ('flip', 'flip-timeout'):
            with self.subTest(mode=mode):
                guest = self.TlsUsbClient(FLIP_ARTIFACT, self.files, self.peer,
                                          video=self.stream, ddraw_mode=mode)
                result = guest.attach()
                self.assertEqual(guest.painted_frames(), 1)
                self.assertEqual(len(guest.blit_times), 1)
                self.assertEqual(guest.ddraw['flips'], 1)
                self.assertEqual(guest.ddraw['flip_status'], int(mode == 'flip-timeout'))
                self.assertGreater(guest.ddraw['hides'], guest.ddraw['shows'])
                self.assertIn('i30 CE projection frame presented.', result['debug'])
                self.assert_clean(guest)


if __name__ == '__main__':
    unittest.main()
