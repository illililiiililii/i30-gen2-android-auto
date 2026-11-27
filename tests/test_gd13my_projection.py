from pathlib import Path
from queue import SimpleQueue
import sys
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from gd13my_projection import Projection, ProjectionSurface
from gd13my_musb import UsbTransferError, UsbTransferPending
from gd13my_usb_pc import PhonePort, VERSION_REQUEST
from view_gd13my import WindowedRun
from i30_receiver.audio import AudioMixer, Microphone
from i30_receiver.cli import openssl_path
from i30_receiver.mock import (ACCESSORY, MockCapture, MockPlayback, MockUsb, PORT, VirtualClock,
                               mock_client, synthetic_h264, test_identity)
from i30_receiver.platform import Platform
from i30_receiver.session import SessionManager
from i30_receiver.transport import AoaTransport, Device, InterfaceNotReady, Timeout

try:
    import av
except ImportError:
    av = None

VERSION_RESPONSE = bytes.fromhex('000300080002000100070000')


class Gd13myProjectionTests(unittest.TestCase):
    def test_guest_usb_waits_until_accessory_interface_can_be_claimed(self):
        class Configuration(list):
            bConfigurationValue = 1

        phone = PhonePort.__new__(PhonePort)
        phone.requested_port = phone.port = '1-2'
        phone.next_poll = 0
        phone.device = phone.raw = phone.link = None
        phone.controller, phone.backend, phone.notify = Mock(), Mock(), Mock()
        accessory = Device(phone.port, 0x18d1, 0x2d01, 6)
        raw = Mock(speed=3, bMaxPacketSize0=64)
        link = object()
        phone.backend.devices.return_value = [accessory]
        phone.backend.get_device.return_value = raw
        phone.backend.active_configuration.return_value = Configuration()
        phone.backend.open_accessory.side_effect = [InterfaceNotReady('WinUSB is starting'), link]

        self.assertFalse(phone.poll())
        self.assertIsNone(phone.device)
        phone.controller.set_cable.assert_not_called()

        phone.next_poll = 0
        self.assertTrue(phone.poll())
        self.assertIs(phone.link, link)
        phone.controller.set_cable.assert_called_once_with(True, True)

    def test_phone_port_transfers_a_single_handle_after_complete_version(self):
        port = PhonePort.__new__(PhonePort)
        port.link, port.controller, port.notify, port.trace = Mock(), Mock(), Mock(), Mock()
        port.device, port.raw, port.config = Mock(), port.link.device, 1
        port.link.input_endpoint, port.link.output_endpoint = 0x81, 0x01
        port.bulk_reader = port.bulk_input = None
        port.backend = Mock()
        port.backend.invoke.return_value = len(VERSION_REQUEST)
        port.read_bulk_packet = Mock(side_effect=(VERSION_RESPONSE[:7], VERSION_RESPONSE[7:]))
        port.write(0x01, VERSION_REQUEST)
        self.assertIsNone(port.take_projection_link())
        port.read(0x81, 512)
        self.assertIsNone(port.take_projection_link())
        port.read(0x81, 512)
        link = port.link
        self.assertEqual(port.take_projection_link(), (link, VERSION_RESPONSE))
        self.assertIsNone(port.take_projection_link())
        port.controller.set_cable.assert_called_once_with(False)
        self.assertEqual(port.next_poll, float('inf'))
        link.close.assert_not_called()

    def test_version_write_timeout_reports_physical_replug_and_discards_old_response(self):
        port = PhonePort.__new__(PhonePort)
        port.link, port.backend, port.notify = Mock(), Mock(), Mock()
        port.device, port.config = Mock(), 1
        port.link.output_endpoint = 0x01
        port.version_input, port.version_packet = bytearray(), VERSION_RESPONSE
        port.backend.invoke.side_effect = Timeout('USB I/O timed out')

        with self.assertRaisesRegex(UsbTransferError, 'USB I/O timed out'):
            port.write(0x01, VERSION_REQUEST)

        message, = port.notify.call_args.args
        self.assertIn('WinCE Android Auto 버전 요청', message)
        self.assertIn('휴대폰 USB 케이블을 뺐다가 다시 연결하세요', message)
        self.assertIsNone(port.version_input)
        self.assertIsNone(port.take_projection_link())
        port.link.close.assert_not_called()

    def test_pending_physical_read_does_not_wait_on_the_guest_thread(self):
        ready = Event()
        port = PhonePort.__new__(PhonePort)
        port.bulk_reader = port.bulk_input = None
        port.backend, link = Mock(), Mock()

        def physical_read(*_args, **_kwargs):
            self.assertTrue(ready.wait(timeout=2))
            return b'usb'

        port.backend.invoke.side_effect = physical_read
        try:
            with self.assertRaises(UsbTransferPending):
                port.read_bulk_packet(link, 0x81, 512)
            ready.set()
            self.assertEqual(port.bulk_input.result(timeout=2), b'usb')
            self.assertEqual(port.read_bulk_packet(link, 0x81, 512), b'usb')
            port.backend.invoke.assert_called_once_with(link.device.read, 0x81, 512, timeout=15)
        finally:
            ready.set()
            port.bulk_reader.shutdown()

    def test_five_ignition_shutdowns_release_the_interface_before_reopen(self):
        from concurrent.futures import ThreadPoolExecutor

        physical = Mock()
        for _ in range(5):
            port = PhonePort.__new__(PhonePort)
            port.device, port.raw, port.link = Mock(), physical, Mock(device=physical)
            port.controller, port.backend, port.trace = Mock(), Mock(inventory={1: physical}), Mock()
            port.bulk_reader = ThreadPoolExecutor(max_workers=1)
            pending = port.bulk_reader.submit(lambda: b'')
            port.bulk_input = pending
            port.link.close.side_effect = lambda: self.assertTrue(pending.done())
            link = port.link
            port.shutdown()
            self.assertIsNone(port.bulk_reader)
            self.assertIsNone(port.raw)
            self.assertIsNone(port.link)
            self.assertIsNone(port.bulk_input)
            self.assertFalse(port.backend.inventory)
            self.assertEqual(port.next_poll, float('inf'))
            link.close.assert_called_once()
            port.backend.dispose.assert_not_called()
            port.controller.set_cable.assert_called_once_with(False)

    def test_lcd_capture_waits_for_the_complete_guest_blit(self):
        run = WindowedRun.__new__(WindowedRun)
        run.uart = Mock(output=bytearray(b'i30 LCD blit begin\r\n'), trace_limit=1024)
        run.lcd_blit_offset = 0
        run.lcd_blit_serial_length = 0
        run.lcd_blit_active = False
        run.lcd_blit_started = None
        run.boot_started = 0
        run.lcd_blits = {'completed': 0, 'deferred_polls': 0, 'sampled_wall_seconds': 0.0}
        run.cpu, run.display = Mock(), Mock()
        run.display.capture_rgb.return_value = ({}, None)
        run.navigation_ready = True
        run.lcd_stats = {'ready': {'polls': 0, 'capture_seconds': 0.0}}
        run.publish_frame()
        run.uart.output.extend(b'i30 LCD blit en')
        run.publish_frame()
        run.display.capture_rgb.assert_not_called()
        run.uart.output.extend(b'd\r\n')
        run.publish_frame()
        run.display.capture_rgb.assert_called_once()
        self.assertEqual(run.lcd_blits['deferred_polls'], 2)
        self.assertEqual(run.lcd_blits['completed'], 1)

    @unittest.skipUnless(av and openssl_path(), 'Requires local PyAV and OpenSSL')
    def test_usb_handoff_completes_tls_video_input_audio_and_stock_priority(self):
        clock = VirtualClock()
        platform = Platform(clock=clock.now, pause=clock.pause)
        with TemporaryDirectory() as directory, test_identity(openssl_path()) as (cert, key, server):
            backend = MockUsb(server, platform, phase3=True, interactive=True, video_packets=synthetic_h264(av))
            link = backend.open_accessory(ACCESSORY)
            link.write(VERSION_REQUEST, 100)
            reported_version = b''.join(link.read(100) for _ in range(3))
            self.assertEqual(reported_version, VERSION_RESPONSE)
            projection = Projection(av, SimpleQueue(), Path(directory) / 'bench')
            projection.ready.set()
            projection.worker = Mock()
            playback, capture = MockPlayback(), MockCapture(platform.clock)
            surface = ProjectionSurface(av, platform.log, projection.publish)
            phase = 0

            def poll():
                nonlocal phase
                if phase == 0 and projection.frame() is not None and surface.host.session.touch_ready:
                    self.assertTrue(projection.frame().startswith(b'P6\n800 480\n255\n'))
                    projection.queue('pointer', 'ACTION_DOWN', 210, 140)
                    projection.queue('key', 'VOICE', True)
                    projection.queue('key', 'VOICE', False)
                    phase = 1
                elif phase == 1 and backend.mic_closed:
                    projection.stock_priority.set()
                    self.assertIsNone(projection.frame())
                    phase = 2
                elif phase == 2:
                    self.assertFalse(surface.host.visible)
                    self.assertTrue(playback.closed)
                    projection.stock_priority.clear()
                    phase = 3
                elif phase == 3 and projection.frame() is not None:
                    phase = 4
                projection.poll_input(surface.host)

            manager = SessionManager(None, mock_client(cert, key), platform, surface, host=surface.host,
                                     audio=AudioMixer(playback), microphone=Microphone(capture),
                                     poll_ui=poll, touch_input=True)
            result = manager.run_connected(link, reported_version, seconds=1)
            self.assertFalse(result.errors)
            self.assertTrue(result.graceful_shutdown)
            self.assertEqual(result.active_sessions, 1)
            self.assertEqual(phase, 4)
            self.assertGreaterEqual(surface.frame_count, 2)
            self.assertEqual(len(backend.touch_reports), 2)
            self.assertEqual(backend.mic_blocks, 3)
            self.assertTrue(playback.closed and capture.closed)
            self.assertIsNone(projection.frame())
            self.assertEqual(backend.closed, 1)

    def test_stopped_receiver_disposes_preopened_link(self):
        link = Mock()
        manager = SessionManager(None, None, Platform(stop_requested=lambda: True), None)
        manager.run_connected(link, VERSION_RESPONSE)
        link.close.assert_called_once_with()
        link.write.assert_not_called()

    def test_invalid_guest_version_does_not_start_tls(self):
        link, tls = Mock(), Mock()
        manager = SessionManager(None, tls, Platform(), None)
        denied_version = VERSION_RESPONSE[:-1] + b'\x01'
        result = manager.run_connected(link, denied_version)
        self.assertEqual(result.active_sessions, 0)
        self.assertTrue(result.errors)
        tls.assert_not_called()
        link.write.assert_not_called()
        link.close.assert_called_once_with()

    @unittest.skipUnless(av and openssl_path(), 'Requires local PyAV and OpenSSL')
    def test_usb_disconnect_restores_the_last_stock_surface(self):
        clock = VirtualClock()
        platform = Platform(clock=clock.now, pause=clock.pause)
        with test_identity(openssl_path()) as (cert, key, server):
            backend = MockUsb(server, platform, ('unplug',), phase3=True, interactive=True,
                              video_packets=synthetic_h264(av))
            playback = MockPlayback()
            frames = []
            surface = ProjectionSurface(av, platform.log, frames.append)
            manager = SessionManager(AoaTransport(backend, PORT, platform), mock_client(cert, key), platform,
                                     surface, host=surface.host, audio=AudioMixer(playback),
                                     microphone=Microphone(MockCapture(platform.clock)), touch_input=True)
            result = manager.run()
            self.assertIn('Mock phone cable unplugged', result.errors)
            self.assertTrue(any(frame is not None for frame in frames))
            self.assertIsNone(frames[-1])
            self.assertFalse(surface.host.visible)
            self.assertEqual(backend.closed, 1)
