from pathlib import Path
import struct
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from gd13my_display import (CONFIG, CONTROL, DISPC, GFX_ATTRIBUTES, GFX_BA0, GFX_DESTINATION_KEY,
                            GFX_PIXEL_INC, GFX_ROW_INC, GFX_SIZE, LcdDisplay, TRANS_COLOR, VID1_REGISTERS)
from gd13my_mmio import (ClockManager, DebugUart, EmptyI2c, GpTimer, MicomCdp, OmapIntc, OmapSdMa, OmapUart,
                         PowerRegisters, ReadOnlyHsMmc, SdMaIrq, SyncTimer, TouchController, boot_devices)
from gd13my_musb import HostMusb, UsbTransferError


class MusbTransport:
    control_packet_size = 64

    def __init__(self):
        self.requests = []
        self.writes = []

    def reset(self):
        self.requests.clear()

    def control(self, setup, payload):
        self.requests.append((setup, payload))
        return bytes(range(setup[4])) if setup[0] & 0x80 else b''

    def write(self, address, data):
        self.writes.append((address, data))

    def read(self, address, size):
        if address != 0x81:
            raise UsbTransferError('Endpoint fault')
        return b'bulk'


class HostMusbTests(unittest.TestCase):
    def setUp(self):
        self.transport = MusbTransport()
        self.musb = HostMusb(self.transport)

    def fifo_write(self, fifo, data):
        for byte in data:
            self.musb.write(fifo, 1, byte)

    def fifo_read(self, fifo, size):
        return bytes(self.musb.read(fifo, 1) for _ in range(size))

    def test_connect_interrupt_and_control_in_packets_reach_the_guest(self):
        musb = self.musb
        devices = boot_devices(DebugUart(), timer_irq=True, musb=musb)
        self.assertIs(devices[0x48200000][1].sources[92], musb)
        musb.write(0x0b, 1, 0x30)
        musb.write(0x06, 2, 1)
        musb.set_cable(True, True)
        self.assertFalse(musb.irq_pending())
        self.assertEqual(musb.read(0x60, 1), 0)
        musb.write(0x60, 1, 1)
        self.assertTrue(musb.irq_pending())
        self.assertEqual(musb.read(0x0a, 1), 0x10)
        self.assertFalse(musb.irq_pending())
        self.assertEqual(musb.read(0x60, 1), 0x1d)
        self.fifo_write(0x20, struct.pack('<BBHHH', 0x80, 6, 0x200, 0, 90))
        musb.write(0x102, 2, 0x0a)
        self.assertEqual(musb.read(2, 2), 1)
        self.assertEqual(self.transport.requests, [((0x80, 6, 0x200, 0, 90), b'')])
        for start, count in ((0, 64), (64, 26)):
            musb.write(0x12, 2, 0x20)
            self.assertEqual(musb.read(0x108, 1), count)
            self.assertEqual(self.fifo_read(0x20, count), bytes(range(start, start + count)))
            musb.write(0x102, 2, 0)
        musb.write(0x102, 2, 0x42)
        self.assertIsNone(musb.setup)
        musb.set_cable(False)
        self.assertEqual(musb.read(0x0a, 1), 0x20)
        self.assertEqual(musb.read(0x60, 1), 0x1d)

    def test_vendor_data_out_and_bulk_use_the_selected_endpoint(self):
        musb = self.musb
        musb.set_cable(True)
        self.fifo_write(0x20, struct.pack('<BBHHH', 0x40, 52, 0, 0, 4))
        musb.write(0x102, 2, 0x0a)
        self.assertFalse(self.transport.requests)
        self.fifo_write(0x20, b'i30\0')
        musb.write(0x102, 2, 2)
        self.assertEqual(self.transport.requests, [((0x40, 52, 0, 0, 4), b'i30\0')])
        musb.write(0x11a, 1, 0x21)
        self.fifo_write(0x24, b'aa')
        musb.write(0x112, 2, 1)
        self.assertEqual(self.transport.writes, [(1, b'aa')])
        musb.write(0x114, 2, 64)
        musb.write(0x11c, 1, 0x21)
        musb.write(0x116, 2, 0x20)
        self.assertEqual(musb.read(0x118, 2), 4)
        self.assertEqual(self.fifo_read(0x24, 4), b'bulk')
        musb.write(0x11c, 1, 0x22)
        musb.write(0x116, 2, 0x20)
        self.assertEqual(musb.read(0x116, 2), 4)

    def test_bulk_mode_zero_dma_feeds_the_fifo_and_latches_a_separate_interrupt(self):
        musb = self.musb
        memory = bytearray(b'abcdefgh........')
        musb.dma_memory = (lambda addr, count: 0 <= addr <= len(memory) - count,
                           lambda addr, count: memory[addr:addr + count],
                           lambda addr, data: memory.__setitem__(slice(addr, addr + len(data)), data))
        devices = boot_devices(DebugUart(), timer_irq=True, musb=musb)
        dma_irq = devices[0x48200000][1].sources[93]
        musb.set_cable(True)
        musb.write(0x110, 2, 64)
        musb.write(0x11a, 1, 0x21)
        musb.write(0x208, 4, 0)
        musb.write(0x20c, 4, 8)
        musb.write(0x204, 4, 0x61b)
        self.assertEqual(musb.read(0x208, 4), 8)
        self.assertEqual(musb.read(0x20c, 4), 0)
        self.assertEqual(musb.read(0x112, 2) & 3, 2)
        self.assertEqual(self.transport.writes, [])
        self.assertTrue(dma_irq.irq_pending())
        self.assertEqual(musb.read(0x200, 4), 1)
        self.assertFalse(dma_irq.irq_pending())
        musb.write(0x112, 2, 1)
        self.assertEqual(self.transport.writes, [(1, b'abcdefgh')])

        musb.write(0x114, 2, 64)
        musb.write(0x11c, 1, 0x21)
        musb.write(0x218, 4, 8)
        musb.write(0x21c, 4, 8)
        musb.write(0x214, 4, 0x619)
        self.assertFalse(dma_irq.irq_pending())
        musb.write(0x116, 2, 0x8020)
        self.assertEqual(memory[8:], b'bulk....')
        self.assertEqual(musb.read(0x218, 4), 12)
        self.assertEqual(musb.read(0x21c, 4), 4)
        self.assertEqual(musb.read(0x116, 2) & 1, 0)
        self.assertEqual(musb.read(0x200, 1), 2)

    def test_zero_length_bulk_receive_completes_dma_without_touching_ram(self):
        musb = self.musb
        self.transport.read = lambda _address, _size: b''
        def unexpected_memory_access(*_):
            self.fail('An empty USB packet must not access DMA memory')
        musb.dma_memory = (unexpected_memory_access,) * 3
        musb.set_cable(True, high_speed=True)
        musb.write(0x114, 2, 512)
        musb.write(0x11c, 1, 0x21)
        musb.write(0x116, 2, 0xc020)
        self.assertEqual(musb.read(0x118, 2), 0)
        self.assertEqual(musb.read(0x116, 2), 0x8001)
        musb.write(0x208, 4, 0x81787000)
        musb.write(0x20c, 4, 0)
        musb.write(0x204, 4, 0x619)
        self.assertEqual(musb.read(0x204, 4), 0x618)
        self.assertEqual(musb.read(0x208, 4), 0x81787000)
        self.assertEqual(musb.read(0x116, 2), 0x8000)
        self.assertEqual(musb.read(0x200, 1), 1)


class Gd13myPeripheralTests(unittest.TestCase):
    def test_micom_delivers_validated_startup_frames_through_uart(self):
        uart = OmapUart()
        micom = MicomCdp(uart)
        uart.peer = micom.receive
        uart.write(4, 1, 3)
        self.assertEqual(uart.read(8, 1), 2)
        self.assertFalse(uart.irq_pending())
        for byte in bytes.fromhex('16 00 e0 01 03 00'):
            uart.write(0, 1, byte)
        self.assertEqual(uart.read(0x14, 1), 0x60)
        for byte in bytes.fromhex('16 00 e0 01 03 e2'):
            uart.write(0, 1, byte)
        self.assertEqual(uart.read(8, 1), 4)
        data = bytearray()
        while uart.read(0x14, 1) & 1:
            data.append(uart.read(0, 1))
        self.assertEqual(data, bytes.fromhex('16 00 06 06 16 00 e0 02 12 00 f0 16 01 e0 01 13 f3'))
        self.assertEqual(list(micom.exchanges), ['e0 01 03'])

    def test_micom_reports_navigation_knob_level_when_the_guest_requests_it(self):
        uart = OmapUart()
        micom = MicomCdp(uart)
        self.assertEqual(micom.set_navigation_volume(19), 18)
        for byte in bytes.fromhex('16 10 d0 01 c2 03'):
            micom.receive(byte)
        self.assertEqual(bytes(uart.input), bytes.fromhex('16 00 d0 02 d1 12 11 16 10 06 16 16 01 d0 02 d2 12 13'))

    def test_idle_wake_reports_retained_power_domains(self):
        power = PowerRegisters()
        power.wake()
        self.assertEqual([power.read(offset, 4) for offset in (0x9e8, 0xae8)], [3, 3])

    def test_sgx530_revision_is_read_only(self):
        _, sgx = boot_devices(DebugUart())[0x50000000]
        sgx.write(0x14, 4, 0)
        self.assertEqual(sgx.read(0x14, 4), 0x00010201)

    def test_mcspi_channels_shift_on_enabled_tx_and_consume_rx_status(self):
        _, spi = boot_devices(DebugUart())[0x48098000]
        spi.write(0x68, 4, 15 << 7)
        spi.write(0x74, 4, 0x1234)
        self.assertEqual(spi.read(0x6c, 4), 0)
        spi.write(0x70, 4, 1)
        self.assertEqual(spi.read(0x6c, 4), 2)
        spi.write(0x74, 4, 0x1234)
        self.assertEqual(spi.read(0x6c, 4), 7)
        self.assertEqual(spi.read(0x78, 4), 0xffff)
        self.assertEqual(spi.read(0x6c, 4), 6)
        spi.write(0x68, 4, (15 << 7) | (2 << 12))
        spi.write(0x74, 4, 0)
        self.assertEqual(spi.read(0x6c, 4), 6)

    def test_touch_routes_gpio_and_spi_interrupts_and_encodes_both_contact_edges(self):
        touch = TouchController()
        devices = boot_devices(DebugUart(), timer_irq=True, touch=touch)
        _, intc = devices[0x48200000]
        _, spi = devices[0x48098000]
        intc.write(0xa8, 4, 1)
        intc.write(0xc8, 4, 2)
        touch.gpio.write(0x64, 4, touch.PIN)
        touch.gpio.write(0x4c, 4, touch.PIN)
        spi.write(0x68, 4, 31 << 7)
        spi.write(0x70, 4, 1)
        spi.write(0x1c, 4, 1 << 14)
        for down, prefix in ((True, 0xc1000000), (False, 0xc0000000)):
            touch.submit(0x345, 0x156, down)
            self.assertEqual(intc.pending(), [32])
            touch.gpio.write(0x18, 4, touch.PIN)
            spi.write(0x74, 4, 0x80000000)
            self.assertEqual(spi.read(0x78, 4), prefix | 0x314556)
            self.assertEqual(intc.pending(), [65])
            spi.write(0x18, 4, 1 << 14)
            self.assertEqual(intc.pending(), [])

    def test_isp1582_reset_uses_spaced_byte_lanes_and_preserves_chip_id(self):
        _, usb = boot_devices(DebugUart())[0x20000000]
        usb.write(0xf0, 1, 0x5a)
        usb.write(0x1a, 1, 0xff)
        self.assertEqual(usb.read(0x1a, 1), 2)
        usb.write(0x18, 1, 0x10)
        self.assertEqual(usb.read(0xf0, 1), 0x5a)
        usb.write(0x18, 1, 0)
        self.assertEqual(usb.read(0xf0, 1), 0)
        self.assertEqual(usb.read(0x1a, 1), 0)
        usb.write(0xe2, 1, 0xff)
        self.assertEqual([usb.read(offset, 1) for offset in (0xe0, 0xe2, 0xe4)], [0x30, 0x82, 0x15])

    def test_disconnected_musb_keeps_cable_status_read_only(self):
        _, musb = boot_devices(DebugUart())[0x480ab000]
        self.assertEqual(musb.read(0x60, 1), 0x80)
        musb.write(0x60, 1, 0xff)
        self.assertEqual(musb.read(0x60, 1), 0x83)
        musb.write(0x404, 4, 2)
        self.assertEqual(musb.read(0x408, 4), 1)
        self.assertEqual(musb.read(0x60, 1), 0x80)

    def test_musb_flushfifo_clears_on_empty_control_endpoint(self):
        _, musb = boot_devices(DebugUart())[0x480ab000]
        musb.write(0x103, 1, 1)
        self.assertEqual(musb.read(0x103, 1), 0)
        musb.write(0x102, 2, 0x100)
        self.assertEqual(musb.read(0x102, 2), 0)

    def test_iva2_dpll_status_tracks_guest_lock_and_bypass_requests(self):
        clock = ClockManager()
        self.assertEqual(clock.read(0x24, 4), 0)
        clock.write(0x04, 4, 0x47)
        self.assertEqual(clock.read(0x24, 4), 1)
        clock.write(0x24, 4, 0)
        self.assertEqual(clock.read(0x24, 4), 1)
        clock.write(0x04, 4, 0x45)
        self.assertEqual(clock.read(0x24, 4), 0)

    def test_core_interconnect_status_reports_running_clocks(self):
        clock = ClockManager()
        clock.write(0xa48, 4, 0xf)
        self.assertEqual(clock.read(0xa48, 4), 0xf)
        clock.write(0xa4c, 4, 0)
        self.assertEqual(clock.read(0xa4c, 4), 3)

    def test_iva2_peripheral_soft_resets_clear_registers_and_report_reset_done(self):
        devices = boot_devices(DebugUart())
        for base, name in ((0x48094000, 'Mailbox'), (0x5d000000, 'IVA2 MMU')):
            with self.subTest(name=name):
                device_name, bank = devices[base]
                self.assertEqual(device_name, name)
                bank.write(0x1c, 4, 1)
                bank.write(0x10, 4, 2)
                self.assertEqual(bank.read(0x10, 4), 0)
                self.assertEqual(bank.read(0x14, 4), 1)
                self.assertEqual(bank.read(0x1c, 4), 0)

    def test_emmc_reads_a_sector_and_refuses_writes(self):
        sector = bytes(range(256)) * 2
        with tempfile.TemporaryFile() as image:
            image.write(bytes(512) + sector)
            image.flush()
            mmc = ReadOnlyHsMmc(image, first_lba=131070)
            mmc.write(0x10c, 4, 1 << 24)
            self.assertEqual(mmc.read(0x110, 4), 0xc0ff8000)
            mmc.write(0x108, 4, 1 << 16)
            mmc.write(0x10c, 4, 3 << 24)
            mmc.write(0x10c, 4, 7 << 24)
            mmc.write(0x130, 4, 0xffffffff)
            mmc.write(0x104, 4, 512)
            mmc.write(0x108, 4, 131071)
            mmc.write(0x10c, 4, (17 << 24) | (1 << 21))
            self.assertTrue(mmc.read(0x130, 4) & mmc.BRR)
            data = b''.join(struct.pack('<I', mmc.read(0x120, 4)) for _ in range(128))
            self.assertEqual(data, sector)
            self.assertEqual(list(mmc.read_requests), [(131071, 1)])
            self.assertTrue(mmc.read(0x130, 4) & mmc.TC)
            mmc.write(0x10c, 4, 24 << 24)
            self.assertTrue(mmc.read(0x110, 4) & (1 << 26))
            image.seek(512)
            self.assertEqual(image.read(), sector)

    def test_emmc_accepts_the_multiblock_read_used_by_nav_map_init(self):
        count = 0x1ff8
        marker = b'last map sector'.ljust(512, b'\0')
        with tempfile.TemporaryFile() as image:
            image.seek((count - 1) * 512)
            image.write(marker)
            image.flush()
            mmc = ReadOnlyHsMmc(image, first_lba=131070)
            mmc.write(0x10c, 4, 1 << 24)
            mmc.write(0x108, 4, 1 << 16)
            mmc.write(0x10c, 4, 3 << 24)
            mmc.write(0x10c, 4, 7 << 24)
            mmc.write(0x130, 4, 0xffffffff)
            mmc.write(0x104, 4, count << 16 | 512)
            mmc.write(0x108, 4, 131070)
            mmc.write(0x10c, 4, 0x12220032)
            self.assertEqual(list(mmc.read_requests), [(131070, count)])
            self.assertFalse(mmc.read(0x130, 4) & (mmc.DTO | mmc.ERRI))
            self.assertEqual(mmc.read_data((count - 1) * 512), bytes((count - 1) * 512))
            self.assertEqual(mmc.read_data(512), marker)
            self.assertTrue(mmc.read(0x130, 4) & mmc.TC)

    def test_dispc_captures_latched_rgb565_pixels_with_row_padding(self):
        display = LcdDisplay()
        base = 0x80001000
        ram = struct.pack('<5H', 0xf800, 0x07e0, 0xabcd, 0x001f, 0xffff)
        for reg, value in ((GFX_BA0, base), (GFX_SIZE, 0x00010001), (GFX_ATTRIBUTES, 0x0d),
                           (GFX_ROW_INC, 3), (GFX_PIXEL_INC, 1), (CONTROL, 0x21)):
            display.write(DISPC + reg, 4, value)
        display.write(DISPC + GFX_BA0, 4, 0x90000000)  # Shadow update, no GO yet.
        report, image = display.capture(lambda _, n: ram[:n], lambda addr, n: addr == base and n == len(ram))
        self.assertEqual((report['width'], report['height'], report['uniform']), (2, 2, False))
        length = struct.unpack_from('>I', image, 33)[0]
        self.assertEqual(image[37:41], b'IDAT')
        self.assertEqual(zlib.decompress(image[41:41 + length]), bytes.fromhex('00 ff0000 00ff00 00 0000ff ffffff'))

    def test_emmc_sd_dma_and_settings_overlay(self):
        data = bytes(range(256)) * 2
        with tempfile.TemporaryFile() as image:
            image.write(data + bytes(512))
            image.flush()
            card = ReadOnlyHsMmc(image, writable_lbas=(1, 2))
            card.write(0x10c, 4, 7 << 24)
            card.write(0x104, 4, 512)
            memory = {}
            port, target = 0x4809c120, 0x83000000
            dma = OmapSdMa(card, port, (lambda a, n: (a, n) == (target, 512), memory.get, memory.__setitem__))
            irq = SdMaIrq(dma, 0)
            for offset, value in ((0x18, 1), (0x88, 1 << 5), (0x90, 2), (0x94, 128), (0x98, 1),
                                  (0x9c, port), (0xa0, target), (0x80, (1 << 14) | (1 << 7))):
                dma.write(offset, 4, value)
            card.write(0x10c, 4, (17 << 24) | (1 << 21) | 1)
            dma.service()
            self.assertEqual(memory[target], data)
            self.assertTrue(irq.irq_pending())
            self.assertTrue(card.read(0x130, 4) & card.TC)
            dma.write(8, 4, 1)
            self.assertFalse(irq.irq_pending())
            card.write(0x108, 4, 1)
            card.write(0x10c, 4, (24 << 24) | (1 << 21))
            for (word,) in struct.iter_unpack('<I', data):
                card.write(0x120, 4, word)
            card.write(0x10c, 4, (17 << 24) | (1 << 21))
            self.assertEqual(card.read_data(512), data)
            image.seek(512)
            self.assertEqual(image.read(), bytes(512))

    def test_dispc_preserves_stock_controls_over_video_at_the_graphics_key(self):
        display = LcdDisplay()
        base = 0x84000000
        key = 0xf818
        memory = bytearray(struct.pack('<HHI', 0xf800, key, 0))
        for register, value in zip(VID1_REGISTERS, (base + 4, 0, 1, 0x0d, 1, 1)):
            display.write(DISPC + register, 4, value)
        for register, value in ((GFX_BA0, base), (GFX_SIZE, 1), (GFX_ATTRIBUTES, 0x0d), (GFX_ROW_INC, 1),
                                (GFX_PIXEL_INC, 1), (CONFIG, GFX_DESTINATION_KEY), (TRANS_COLOR, key), (CONTROL, 0x21)):
            display.write(DISPC + register, 4, value)

        def contains(address, size):
            return base <= address and address + size <= base + len(memory)

        def write(address, data):
            offset = address - base
            memory[offset:offset + len(data)] = data

        def read(address, size):
            offset = address - base
            return memory[offset:offset + size]

        self.assertTrue(display.copy_map_to_video(bytes.fromhex('0000ff 00ff00'), 2, 1, write, contains))
        self.assertEqual(memory[:4], struct.pack('<HH', 0xf800, key))
        _, image = display.capture(read, contains)
        length = struct.unpack_from('>I', image, 33)[0]
        self.assertEqual(zlib.decompress(image[41:41 + length]), bytes.fromhex('00 ff0000 00ff00'))

    def test_stock_calibration_cross_can_be_seen_through_the_graphics_key(self):
        display = LcdDisplay()
        base, width, height, key = 0x84000000, 800, 480, 0xf818
        stride = width * 2
        size = stride * height
        geometry = (height - 1) << 16 | (width - 1)
        graphics = struct.pack('<H', key) * (width * height)
        backdrop = bytearray(b'\xff\xff' * (width * height))
        for x, y in ((388, 240), (412, 240), (400, 228), (400, 252)):
            struct.pack_into('<H', backdrop, y * stride + x * 2, 0)
        for register, value in zip(VID1_REGISTERS, (base + size, 0, geometry, 0x0d, 1, 1)):
            display.write(DISPC + register, 4, value)
        for register, value in ((GFX_BA0, base), (GFX_SIZE, geometry), (GFX_ATTRIBUTES, 0x0d),
                                (GFX_ROW_INC, 1), (GFX_PIXEL_INC, 1), (CONFIG, GFX_DESTINATION_KEY),
                                (TRANS_COLOR, key), (CONTROL, 0x21)):
            display.write(DISPC + register, 4, value)
        planes = {base: graphics, base + size: backdrop}
        display.capture(lambda address, count: planes[address][:count],
                        lambda address, count: address in planes and count == size)
        self.assertEqual(display.calibration_contact(set()), (400, 240))
        self.assertIsNone(display.calibration_contact({(400, 240)}))

    def test_sync_timer_follows_virtual_clock_independently_of_reads(self):
        clock = 32768
        timer = SyncTimer(lambda: clock)
        self.assertEqual(timer.read(0x10, 4), 32768)
        self.assertEqual(timer.read(0x11, 1), 0x80)
        timer.write(0x10, 4, 0)
        self.assertEqual(timer.read(0x10, 4), 32768)
        clock = (1 << 32) + 17
        self.assertEqual(timer.read(0x10, 4), 17)

    def test_timer_match_routes_through_unmasked_irq37(self):
        clock = 0
        timer = GpTimer(lambda: clock)
        intc = OmapIntc({37: timer})
        self.assertIsNone(timer.ticks_to_match())
        timer.write(0x1c, 4, 1)
        timer.write(0x24, 4, 0x41)
        clock = 5
        timer.write(0x38, 4, 8)
        self.assertEqual(timer.counter(), 5)
        self.assertEqual(timer.ticks_to_match(), 3)
        clock = 9
        self.assertFalse(intc.pending())
        intc.write(0xa8, 4, 1 << 5)
        self.assertTrue(intc.pending())
        timer.write(0x18, 4, 1)
        self.assertFalse(intc.pending())

    def test_i2c_nack_routes_to_irq_and_clears_on_acknowledgement(self):
        i2c = EmptyI2c()
        intc = OmapIntc({61: i2c})
        intc.write(0xa8, 4, 1 << 29)
        i2c.write(0x04, 2, 6)
        i2c.write(0x24, 2, 0x8003)
        self.assertEqual(i2c.read(0x08, 2), 6)
        self.assertEqual(intc.pending(), [61])
        i2c.write(0x08, 2, 6)
        self.assertEqual(intc.pending(), [])
