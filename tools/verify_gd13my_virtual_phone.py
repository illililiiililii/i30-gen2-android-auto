"""Send an Android Auto test frame over the GD13MY guest's virtual USB port."""

import argparse
import json
from pathlib import Path
from queue import SimpleQueue
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic

import av
from pyfatfs.PyFatFS import PyFatFS

import emulate_gd13my as kernel
from build_ce_minimal import import_assembly, native_sections, pe_image
from build_gd13my_diska import PARTITION_OFFSET
from gd13my_display import RGB565
from gd13my_mmio import ReadOnlyHsMmc
from gd13my_musb import HostMusb, UsbTransferError
from gd13my_software_gl import GuestGL
from inspect_ce_pe import rom_exports
from view_gd13my import AppPartitionOverlay, DISK_START_LBA, NAVIGATION_MENU_ACK, WindowedRun

sys.path.insert(0, str(kernel.ROOT / 'src'))
from i30_receiver import schema
from i30_receiver.mock import test_identity
from i30_receiver.tls import TlsRecords
from i30_receiver.wire import CONTROL, ENCRYPTED, FrameReader, Message, ProtocolError, Reassembler, encode

API = ('GetModuleHandleW', 'RegisterClassW', 'CreateWindowExW', 'DefWindowProcW', 'SetForegroundWindow',
       'GetForegroundWindow', 'ShowWindow', 'SetWindowPos', 'GetMessageW', 'DispatchMessageW',
       'CreateProcessW', 'CloseHandle', 'WaitForSingleObject', 'OutputDebugStringW', 'ExitThread', 'Sleep')
FIRST_FRAME = b'i30 CE projection frame presented.'
DISPLAY_RELEASED = b'i30 CE projection released the display.'


def build_probe(compiler, scratch, lcd_bench, owned_window, calibrate):
    source = kernel.ROOT / 'src/ce'
    imports, elf = scratch / 'probe.S', scratch / 'probe.elf'
    imports.write_text(import_assembly(rom_exports(), API), encoding='ascii')
    bench = ['-DI30_VIRTUAL_LCD_BENCH'] if lcd_bench else []
    if owned_window:
        bench.append('-DI30_TEST_OWNED_WINDOW')
    if calibrate:
        bench.append('-DI30_WAIT_FOR_CALIBRATION')
    subprocess.run([compiler, *bench, '-march=armv4t', '-marm', '-Os', '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fshort-wchar', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                    '-nostdlib', '-static', f'-Wl,-T,{source / "ce_minimal.ld"}', '-o', elf,
                    source / 'ce_aa_virtual_phone_probe.c', imports, '-lc', '-lgcc'],
                   check=True, timeout=40)
    return bytes(pe_image(*native_sections(elf), api=API))


def test_picture(yuv=(81, 90, 240)):
    encoder = av.CodecContext.create('libx264', 'w')
    encoder.width, encoder.height, encoder.pix_fmt = 800, 480, 'yuv420p'
    encoder.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline'}
    frame = av.VideoFrame(800, 480, 'yuv420p')
    for plane, color in zip(frame.planes, yuv):
        plane.update(bytes([color]) * plane.buffer_size)
    return b''.join(bytes(packet) for packet in (*encoder.encode(frame), *encoder.encode(None)))


class VirtualPhone:
    """An AOA accessory with a mutual TLS server and one H.264 source."""

    control_packet_size = 64
    device_descriptor = bytes.fromhex('1201000200000040d118002d000100000001')
    config_descriptor = bytes.fromhex('09022000010100c0320904000002ff0000000705810200020007050102000200')

    def __init__(self, context, frame, *, close_after_frame=True):
        self.controller = HostMusb(self)
        self.context = context
        self.tls = TlsRecords(context, server=True)
        self.reader, self.reassembler = FrameReader(), Reassembler()
        self.outgoing = bytearray()
        self.frame = frame
        self.close_after_frame = close_after_frame
        self.version = self.discovery = self.audio_released = False
        self.acks = 0
        self.transfers = []
        self.reset()

    def reset(self):
        self.configuration = 0

    def reconnect(self):
        self.controller.set_cable(True, high_speed=True)

    def poll(self):
        return False

    def control(self, setup, _payload):
        request_type, request, value, _, length = setup
        if request_type == 0x80 and request == 6:
            return {1: self.device_descriptor, 2: self.config_descriptor}.get(value >> 8, b'')[:length]
        if request_type == 0x80 and request == 8:
            return bytes([self.configuration])
        if request_type == 0 and request == 9:
            self.configuration = value
        return bytes(min(length, 2)) if request == 0 else b''

    def read(self, address, size):
        if address != 0x81:
            raise UsbTransferError('Unknown virtual phone IN endpoint')
        packet = bytes(self.outgoing[:size])
        del self.outgoing[:size]
        if len(self.transfers) < 125:
            self.transfers.append(('in', len(packet)))
        return packet

    def write(self, address, data):
        if address != 1:
            raise UsbTransferError('Unknown virtual phone OUT endpoint')
        if len(self.transfers) < 125:
            self.transfers.append(('out', len(data)))
        for frame in self.reader.feed(data):
            plain = self.tls.decrypt(frame.payload) if frame.flags & ENCRYPTED else frame.payload
            message = self.reassembler.push(frame, plain)
            if message:
                self.handle(message)

    def send(self, code, data=b'', *, channel=0, flags=ENCRYPTED, fragment_size=0x4000):
        encrypt = self.tls.encrypt if flags & ENCRYPTED else None
        for frame in encode(Message(channel, flags, code, data), encrypt, fragment_size):
            self.outgoing.extend(frame)

    def handle(self, message):
        channel, code, data = message.channel, message.code, message.payload
        if channel == 0 and code == 1 and data == bytes.fromhex('00010006'):
            self.version = True
            self.send(2, bytes.fromhex('000100070000'), flags=0)
        elif channel == 0 and code == 3:
            reply = self.tls.handshake(data)
            if reply:
                self.send(3, reply, flags=0)
        elif channel == 0 and code == 4 and data == b'\x08\x00' and self.tls.ready:
            self.send(5, b'\x2a\x04Test')
        elif channel == 0 and code == 6:
            services = schema.parse(schema.CTL + 'ServiceDiscoveryResponse', data)
            self.discovery = [item.id for item in services.channels] == [3]
            if self.discovery:
                self.send(18, b'\x08\x01')
        elif channel == 0 and code == 15:
            self.send(16)
        elif channel == 0 and code == 19 and data == b'\x08\x03\x10\x00':
            self.audio_released = True
            self.send(7, b'\x08\x00\x10\x03', channel=3, flags=CONTROL | ENCRYPTED)
        elif channel == 3 and code == 8 and data == b'\x08\x00':
            self.send(0x8000, b'\x08\x03', channel=3)
        elif channel == 3 and code == 0x8003 and data == bytes((8, 2, 16, 1, 26, 1, 0)):
            self.send(0x8001, b'\x08\x23\x10\x00', channel=3)
            self.send(0x8007, b'\x10\x01', channel=3)
        elif channel == 3 and code == 0x8008 and data == b'\x08\x01\x10\x00':
            self.send(0, bytes(8) + self.frame, channel=3, fragment_size=1200)
        elif channel == 3 and code == 0x8004 and data == b'\x08\x23\x10\x01':
            self.acks += 1
            if self.close_after_frame:
                self.send(15, b'\x08\x01')
            else:
                self.send(11, b'\x08\x01')
        elif channel == 0 and code == 12 and not self.close_after_frame:
            self.send(11, b'\x08\x01')
        elif channel != 0 or code != 16:
            raise ProtocolError(f'Unexpected virtual phone response {channel}:{code:#x}')


class GuestVideoRun(WindowedRun):
    pixels = None

    def projection_pixels(self):
        layout, _ = self.display.layout(self.display.active, self.contains_ram)
        if layout is None:
            return None
        base, width, height, stride, _ = layout
        if (width, height) != (800, 480):
            return None
        colors = []
        for x, y in ((400, 240), (200, 120), (600, 360)):
            address = base + y * stride + x * 2
            color, = struct.unpack('<H', self.cpu.mem_read(address, 2))
            colors.append(list(RGB565[color]))
        return colors

    def inspect_projection(self):
        self.next_frame_time = monotonic() + 0.2
        uart = self.uart.output
        if any(message in uart for message in (
                b'probe clock setup failed.', b'probe window registration failed.', b'probe window creation failed.',
                b'probe could not start the USB client.', b'probe found no stock foreground owner.',
                b'i30 CE projection window did not receive foreground.')) or (
                b'Projection setup is pending.' in uart and FIRST_FRAME not in uart):
            self.closing.set()
        if FIRST_FRAME not in uart or not self.phone_port.acks:
            return
        self.pixels = self.projection_pixels()
        if self.pixels and all(red > 210 and green < 35 and blue < 35 for red, green, blue in self.pixels):
            self.closing.set()

    def publish_frame(self):
        if self.auto_calibrate and b'created the test window.' not in self.uart.output:
            return super().publish_frame()
        self.inspect_projection()


class NativeMenuVideoRun(GuestVideoRun):
    """Drive the stock MICOM and touch paths in the normal navigation process."""

    consent_tap_sent = False
    menu_requested = False
    menu_retry_at = None
    menu_retried = False
    menu_touch_at = None
    projection_tap_sent = False

    def tap(self, x, y):
        for _ in range(12):
            self.pointer.put((x, y, True))
        self.pointer.put((x, y, False))

    def publish_frame(self):
        if FIRST_FRAME in self.uart.output:
            self.inspect_projection()
            return
        WindowedRun.publish_frame(self)
        if not self.consent_tap_sent and b'Showing NAVI AGREE BUTTON' in self.uart.output:
            # The stock disabled button has grey text at these glyph positions.
            enabled = ((367, 420, b'\0\0\0'), (395, 430, b'\0\0\0'), (431, 440, b'\0\0\0'),
                       (400, 409, b'\xce\xd7\xde'), (400, 379, b'\x08\x18\x31'))
            if self.display.scanout_matches(800, 480, enabled):
                self.tap(400, 430)
                self.consent_tap_sent = True
        if self.navigation_ready and not self.menu_requested:
            self.menu_requested = True
            self.menu_button.set()
        if self.menu_requested and not self.projection_tap_sent:
            now = monotonic()
            if b'CShotMngr::CreateShot(24)' in self.uart.output:
                if self.menu_touch_at is None:
                    self.menu_touch_at = now + 2
            elif NAVIGATION_MENU_ACK in self.uart.output and not self.menu_retried:
                if self.menu_retry_at is None:
                    self.menu_retry_at = now + 8
                elif now >= self.menu_retry_at:
                    # The first NAVIMENU key can finish bringing the stock map forward.
                    self.menu_button.set()
                    self.menu_retried = True
            if self.menu_touch_at is not None and now >= self.menu_touch_at:
                self.tap(399, 439)
                self.projection_tap_sent = True


class ReplugNativeMenuRun(NativeMenuVideoRun):
    detach_offset = None
    attach_offset = None
    attach_at = None
    replug_pixels = None

    def inspect_projection(self):
        self.next_frame_time = monotonic() + 0.2
        uart = self.uart.output
        if self.detach_offset is None:
            colors = self.projection_pixels()
            if self.phone_port.acks and colors and all(r > 210 and g < 35 and b < 35 for r, g, b in colors):
                self.pixels = colors
                self.detach_offset = len(uart)
                self.phone_port.controller.set_cable(False)
            return
        if self.attach_offset is None:
            if DISPLAY_RELEASED not in uart[self.detach_offset:]:
                return
            if self.attach_at is None:
                self.attach_at = monotonic() + 3
                return
            if monotonic() < self.attach_at:
                return
            self.attach_offset = len(uart)
            controller = self.phone_port.controller
            self.phone_port = VirtualPhone(self.phone_port.context, test_picture((145, 54, 34)),
                                           close_after_frame=False)
            self.phone_port.controller = controller
            controller.transport = self.phone_port
            self.phone_port.reconnect()
            return
        if FIRST_FRAME in uart[self.attach_offset:] and self.phone_port.acks:
            colors = self.projection_pixels()
            if colors and all(r < 35 and g > 210 and b < 35 for r, g, b in colors):
                self.replug_pixels = colors
                self.closing.set()


def verify(args):
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    kernel.VIRTUAL_CPU_UNITS_PER_SECOND = round(args.boot_clock_mhz * 1_000_000)
    with (TemporaryDirectory(prefix='gd13my-virtual-phone-', dir=args.output.parent) as staging,
          test_identity(args.openssl) as (cert, key, ctx)):
        staging = Path(staging)
        patch = staging / 'virtual-phone.img'
        shutil.copyfile(args.image, patch)
        startup = None if args.native_menu else build_probe(
            args.compiler, staging, args.lcd_bench, args.owned_window, args.calibrate)
        with PyFatFS(str(patch), offset=PARTITION_OFFSET, preserve_case=True) as files:
            if startup is not None:
                files.remove('/Application/uComH_New.exe')
                files.writebytes('/Application/uComH_New.exe', startup)
            navi = '/Application/NAVI/'
            files.writebytes(navi + 'i30-ca.pem', cert.read_bytes())
            files.writebytes(navi + 'i30-client.pem', cert.read_bytes())
            files.writebytes(navi + 'i30-client-key.pem', key.read_bytes())
            files.writebytes(navi + 'i30-peer.txt', b'i30-mock.local\n')
        phone = VirtualPhone(ctx, test_picture(), close_after_frame=not args.native_menu)
        with args.disk.open('rb') as disk, patch.open('rb') as app:
            media = AppPartitionOverlay(disk, app)
            media.enable_host_utc(manifest['emulator_utc_offset'])
            card = ReadOnlyHsMmc(media, first_lba=DISK_START_LBA, writable_lbas=(
                DISK_START_LBA, DISK_START_LBA + args.disk.stat().st_size // 512))
            output = args.output / 'virtual-phone'
            output.with_suffix('.serial.log').write_bytes(b'')
            runner = (ReplugNativeMenuRun if args.replug_after_frame else
                      NativeMenuVideoRun if args.native_menu else GuestVideoRun)
            run = runner(args.rom.read_bytes(), card, SimpleQueue(), SimpleQueue(), Event(), Event(),
                         output, phone_port=phone, auto_calibrate=args.calibrate or args.native_menu is not None,
                         usb_clock_units=round(args.usb_clock_mhz * 1_000_000),
                         **({'display_mode': 2, 'assist_navi_start': True, 'assist_touch_calibration': True}
                            if args.native_menu else {}))
            renderer = GuestGL(run, args.native_menu) if args.native_menu else None
            started = monotonic()
            try:
                report = run.run_window(args.seconds)
            finally:
                if renderer is not None:
                    renderer.close()
            status = {'stop': report['stop'], 'version': phone.version, 'mutual_tls': phone.tls.ready,
                      'foreground_confirmed': b'i30 virtual phone probe acquired foreground.' in run.uart.output,
                      'video_service': phone.discovery, 'audio_released': phone.audio_released,
                      'media_acks': phone.acks, 'lcd_pixels_rgb': run.pixels,
                      'boot_clock_mhz': args.boot_clock_mhz,
                      'usb_clock_mhz': kernel.VIRTUAL_CPU_UNITS_PER_SECOND / 1_000_000,
                      'transfers': phone.transfers, 'wall_seconds': round(monotonic() - started, 3)}
            if args.native_menu:
                status.update(stock_navigation=run.navigation_ready, stock_menu=NAVIGATION_MENU_ACK in run.uart.output,
                              stock_consent=b'BUTTON_PUSH_AGREE_ON' in run.uart.output,
                              projection_tap_sent=run.projection_tap_sent,
                              stock_display_publisher=b'i30 OEM MICOM display publisher ready.' in run.uart.output,
                              native_z_order=b'i30 native projection placed immediately above the stock map.' in run.uart.output)
            if args.replug_after_frame:
                status.update(cable_detached=run.detach_offset is not None,
                              display_released=run.attach_offset is not None,
                              replug_tls=run.attach_offset is not None and run.phone_port.tls.ready,
                              replug_media_acks=run.phone_port.acks if run.attach_offset is not None else 0,
                              replug_pixels_rgb=run.replug_pixels)
    (args.output / 'virtual-phone.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(status, indent=2))
    video_rendered = bool(status['media_acks'] and status['lcd_pixels_rgb'] and all(
        red > 210 and green < 35 and blue < 35 for red, green, blue in status['lcd_pixels_rgb']))
    return video_rendered and (not args.replug_after_frame or bool(status['replug_pixels_rgb'])) and (
        not args.native_menu or all(status[key] for key in
        ('stock_consent', 'stock_navigation', 'stock_menu', 'projection_tap_sent',
         'stock_display_publisher', 'native_z_order')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--disk', type=Path, required=True)
    parser.add_argument('--rom', type=Path, default=kernel.ROM_PATH)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--openssl', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seconds', type=int, default=230)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--lcd-bench', action='store_true', help='Use the display in the isolated LCD test')
    mode.add_argument('--owned-window', action='store_true', help='Exercise the native window handoff using the current foreground owner')
    mode.add_argument('--native-menu', type=Path, metavar='STOCK_GDDNAVI',
                      help='Use the patched stock menu with the original navigation PE as the GLES reference')
    parser.add_argument('--calibrate', action='store_true', help='Complete the stock touch calibration before creating the test window')
    parser.add_argument('--replug-after-frame', action='store_true',
                        help='Disconnect after the first native frame and verify a fresh projected session')
    parser.add_argument('--usb-clock-mhz', type=float, default=64)
    parser.add_argument('--boot-clock-mhz', type=float, default=4.5)
    args = parser.parse_args()
    if args.native_menu and not json.loads(args.manifest.read_text(encoding='utf-8-sig')).get('stock_display_sha256'):
        parser.error('--native-menu requires an image with the stock display publisher')
    if args.replug_after_frame and not args.native_menu:
        parser.error('--replug-after-frame requires --native-menu')
    if not 4.5 <= args.usb_clock_mhz <= 100:
        parser.error('--usb-clock-mhz must be between 4.5 and 100')
    if not 1 <= args.boot_clock_mhz <= 64:
        parser.error('--boot-clock-mhz must be between 1 and 64')
    if args.calibrate and (args.owned_window or args.lcd_bench):
        parser.error('--calibrate applies to the test window only')
    sys.exit(0 if verify(args) else 1)


if __name__ == '__main__':
    main()
