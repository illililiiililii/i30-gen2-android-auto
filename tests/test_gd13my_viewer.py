from pathlib import Path
from queue import SimpleQueue
import struct
import sys
from tempfile import TemporaryDirectory
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from gd13my_disk_state import persistent_diska
from gd13my_guest_clock import UTC_PLACEHOLDER
from gd13my_mmio import MicomCdp, OmapUart, ReadOnlyHsMmc
from view_gd13my import AppPartitionOverlay, NAVIGATION_MENU_ACK, USB_TEST_READY, USB_TEST_SUCCESS, KernelRun, WindowedRun


class Gd13myWindowInputTests(unittest.TestCase):
    def setUp(self):
        self.run = WindowedRun.__new__(WindowedRun)
        self.run.menu_button = Event()
        self.run.menu_button.set()
        self.run.menu_sent = None
        self.run.menu_slow = False
        self.run.navigation_ready = False
        self.run.messages = SimpleQueue()
        self.run.micom = MicomCdp(OmapUart())
        self.run.uart = SimpleNamespace(output=bytearray(NAVIGATION_MENU_ACK))

    def test_early_menu_request_waits_for_navigation_and_a_fresh_ack(self):
        self.run.service_menu_button(1)
        self.assertTrue(self.run.menu_button.is_set())
        self.assertFalse(self.run.micom.uart.input)
        self.run.navigation_ready = True
        self.run.service_menu_button(2)
        self.assertFalse(self.run.menu_button.is_set())
        self.assertEqual(bytes(self.run.micom.uart.input), bytes.fromhex('16 00 60 02 1e 01 7d'))
        self.run.service_menu_button(3)
        self.assertIsNotNone(self.run.menu_sent)
        self.run.service_menu_button(33)
        self.assertTrue(self.run.menu_slow)
        self.run.uart.output.extend(NAVIGATION_MENU_ACK)
        self.run.service_menu_button(34)
        self.assertIsNone(self.run.menu_sent)
        self.assertEqual(self.run.messages.get()[1], 'F2 전송 완료 · 순정 내비 응답 확인 중')
        self.assertEqual(self.run.messages.get()[1], 'F2 전송 완료 · 순정 내비 응답이 늦음')
        self.assertEqual(self.run.messages.get()[1], '순정 내비가 F2 입력을 처리함')

    def test_pending_touch_does_not_block_menu_delivery(self):
        self.run.navigation_ready = True
        self.run.clock_units = self.run.next_poll_units = self.run.next_touch_tick = 0
        self.run.closing = Event()
        self.run.touch = SimpleNamespace(pending=1)
        self.run.phone_port = None
        self.run.controls = None
        self.run.display = SimpleNamespace(active=None)
        self.run.next_serial_time = float('inf')
        with patch.object(KernelRun, 'advance_clock'):
            self.run.advance_clock(None, 0, 4, None)
        self.assertTrue(self.run.micom.uart.input)
        self.assertEqual(self.run.touch.pending, 1)

    def test_usb_driver_registration_reenumerates_once_even_across_serial_chunks(self):
        self.run.phone_port = Mock()
        self.run.usb_test_offset = 0
        self.run.uart.output.extend(USB_TEST_READY[:10])
        self.run.service_usb_test()
        self.run.phone_port.reconnect.assert_not_called()
        self.run.uart.output.extend(USB_TEST_READY[10:])
        self.run.service_usb_test()
        self.run.service_usb_test()
        self.run.phone_port.reconnect.assert_called_once_with()

    def test_lowering_usb_clock_preserves_ticks_and_reschedules_both_polls(self):
        self.run.clock_units = 640_000_000
        self.run.irq_poll_at = self.run.next_poll_units = self.run.clock_units + 1024
        self.run.usb_clock_units = 12_000_000
        with patch('view_gd13my.emulate_gd13my.VIRTUAL_CPU_UNITS_PER_SECOND', 64_000_000):
            prior_ticks = self.run.clock_ticks()
            self.run.use_usb_clock()
            self.assertEqual(self.run.clock_ticks(), prior_ticks)
        self.assertEqual(self.run.clock_units, 120_000_000)
        self.assertEqual(self.run.next_poll_units, self.run.clock_units)
        self.assertEqual(self.run.irq_poll_at, self.run.clock_units)

    def test_projection_claims_once_after_complete_ce_usb_success(self):
        self.run.phone_port = Mock()
        self.run.usb_test_offset = 0
        self.run.projection = Mock(running=False)
        self.run.uart.output.extend(USB_TEST_READY + USB_TEST_SUCCESS[:-1])
        self.run.service_usb_test()
        self.run.phone_port.reconnect.assert_called_once_with()
        self.run.phone_port.take_projection_link.assert_not_called()
        self.run.uart.output.extend(USB_TEST_SUCCESS[-1:])
        self.run.service_usb_test()
        self.run.projection.start.assert_called_once_with(self.run.phone_port.take_projection_link.return_value)
        self.run.projection.running = True
        self.run.uart.output.extend(USB_TEST_READY)
        self.run.service_usb_test()
        self.run.phone_port.reconnect.assert_called_once_with()
        self.run.phone_port.take_projection_link.assert_called_once_with()


class Gd13myDiskStateTests(unittest.TestCase):
    def test_host_utc_refreshes_without_changing_persistent_image_identity(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            media, app, state = (root / name for name in ('media.img', 'app.img', 'state.sqlite3'))
            contents = bytearray(4 * 512)
            contents[450] = 0x0c
            struct.pack_into('<II', contents, 454, 1, 2)
            contents[510:512] = b'\x55\xaa'
            contents[1024:1024 + len(UTC_PLACEHOLDER)] = UTC_PLACEHOLDER
            media.write_bytes(contents)
            app.write_bytes(contents[:1536])
            for boot in (1, 2):
                utc = b'I30UTC01' + bytes([boot]) * 16
                with media.open('rb') as original, app.open('rb') as compact:
                    backing = AppPartitionOverlay(original, compact)
                    card = ReadOnlyHsMmc(backing, first_lba=100)
                    with persistent_diska(state, card) as restored, patch('view_gd13my.utc_mailbox', return_value=utc):
                        self.assertEqual(restored, boot - 1)
                        backing.enable_host_utc(1024)
                        backing.seek(1020)
                        self.assertEqual(backing.read(40), bytes(4) + utc + bytes(12))
                        card.overlay[101] = b'x' * 512
            self.assertEqual(app.read_bytes(), contents[:1536])

    def test_disk_state_restores_only_diska_and_reserves_one_writer(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / 'bench.img'
            state = root / 'bench.sqlite3'
            media = bytearray(5 * 512)
            media[450] = 0x0c
            struct.pack_into('<II', media, 454, 1, 2)
            media[510:512] = b'\x55\xaa'
            image.write_bytes(media)
            with image.open('rb') as backing:
                card = ReadOnlyHsMmc(backing, first_lba=100)
                with persistent_diska(state, card) as restored:
                    self.assertEqual(restored, 0)
                    card.overlay.update({100: b'm' * 512, 101: b'a' * 512, 103: b'b' * 512})
                    with self.assertRaisesRegex(ValueError, 'Could not open or save DiskA state'):
                        with persistent_diska(state, ReadOnlyHsMmc(backing, first_lba=100)):
                            self.fail('Opened a second writer')
                next_boot = ReadOnlyHsMmc(backing, first_lba=100)
                with self.assertRaisesRegex(RuntimeError, 'interrupted'):
                    with persistent_diska(state, next_boot) as restored:
                        self.assertEqual(restored, 1)
                        self.assertEqual(next_boot.overlay, {101: b'a' * 512})
                        next_boot.overlay[101] = b'x' * 512
                        raise RuntimeError('interrupted')
                final_boot = ReadOnlyHsMmc(backing, first_lba=100)
                with persistent_diska(state, final_boot):
                    self.assertEqual(final_boot.overlay, {101: b'a' * 512})
            self.assertEqual(image.read_bytes(), media)
            media[512] = 1
            image.write_bytes(media)
            with image.open('rb') as backing:
                with self.assertRaisesRegex(ValueError, 'different image'):
                    with persistent_diska(state, ReadOnlyHsMmc(backing, first_lba=100)):
                        self.fail('Applied saved sectors to a different base')
