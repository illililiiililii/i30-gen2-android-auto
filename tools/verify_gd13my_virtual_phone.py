"""Send an Android Auto test frame over the GD13MY guest's virtual USB port."""

import argparse
from fractions import Fraction
from io import BytesIO
import json
from pathlib import Path
from queue import SimpleQueue
import re
import shutil
import struct
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Event
from time import monotonic, process_time

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
from view_gd13my import AppPartitionOverlay, DISK_START_LBA, NAVIGATION_MENU_ACK, NAVIGATION_MENU_PACKET, WindowedRun

sys.path.insert(0, str(kernel.ROOT / 'src'))
from i30_receiver import schema
from i30_receiver.mock import test_identity
from i30_receiver.protocol import INPUT, INPUT_CHANNEL, input_code
from i30_receiver.tls import TlsRecords
from i30_receiver.wire import CONTROL, ENCRYPTED, FrameReader, Message, ProtocolError, Reassembler, encode

API = ('GetModuleHandleW', 'RegisterClassW', 'CreateWindowExW', 'DefWindowProcW', 'SetForegroundWindow',
       'GetForegroundWindow', 'ShowWindow', 'SetWindowPos', 'GetMessageW', 'DispatchMessageW',
       'CreateProcessW', 'CloseHandle', 'WaitForSingleObject', 'OutputDebugStringW', 'ExitThread', 'Sleep')
FIRST_FRAME = b'i30 CE projection frame presented.'
DISPLAY_RELEASED = b'i30 CE projection released the display.'
LCD_SIZE = (800, 480)
LCD_RGB_ERROR_LIMIT = 8
GUEST_TICKS_PER_SECOND = 32768
VIDEO_CHANNEL = 3


def build_probe(compiler, scratch, lcd_bench, owned_window, calibrate, audio_query=False):
    source = kernel.ROOT / 'src/ce'
    imports, elf = scratch / 'probe.S', scratch / 'probe.elf'
    api = (*API, 'waveOutOpen', 'waveInOpen', 'waveOutGetNumDevs', 'waveInGetNumDevs',
           'waveOutGetDevCaps', 'waveInGetDevCaps') if audio_query else API
    imports.write_text(import_assembly(rom_exports(), api), encoding='ascii')
    bench = ['-DI30_VIRTUAL_LCD_BENCH'] if lcd_bench else []
    if owned_window:
        bench.append('-DI30_TEST_OWNED_WINDOW')
    if calibrate:
        bench.append('-DI30_WAIT_FOR_CALIBRATION')
    if audio_query:
        bench.append('-DI30_TEST_WAVE_QUERY')
    subprocess.run([compiler, *bench, '-march=armv4t', '-marm', '-Os', '-Wall', '-Wextra', '-Werror',
                    '-ffreestanding', '-fshort-wchar', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                    '-nostdlib', '-static', f'-Wl,-T,{source / "ce_minimal.ld"}', '-o', elf,
                    source / 'ce_aa_virtual_phone_probe.c', imports, '-lc', '-lgcc'],
                   check=True, timeout=40)
    return bytes(pe_image(*native_sections(elf), api=api))


def test_picture(yuv=(81, 90, 240), *, frame=None):
    encoder = av.CodecContext.create('libx264', 'w')
    encoder.width, encoder.height = LCD_SIZE
    encoder.pix_fmt = 'yuv420p'
    encoder.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline'}
    if frame is None:
        frame = av.VideoFrame(*LCD_SIZE, 'yuv420p')
        for plane, color in zip(frame.planes, yuv):
            plane.update(bytes([color]) * plane.buffer_size)
    else:
        frame = frame.reformat(format='yuv420p')
    return b''.join(bytes(packet) for packet in (*encoder.encode(frame), *encoder.encode(None)))


def read_lcd_image(source):
    with av.open(source) as image:
        frame = next(image.decode(video=0), None)
    if frame is None or (frame.width, frame.height) != LCD_SIZE:
        raise ValueError('Expected a decodable 800×480 image')
    return frame


def packed_rgb(frame):
    plane = frame.reformat(format='rgb24').planes[0]
    raw = memoryview(plane)
    pitch = plane.line_size
    return b''.join(raw[row * pitch:row * pitch + frame.width * 3] for row in range(frame.height))


class VirtualPhone:
    """An AOA accessory with a mutual TLS server and one H.264 source."""

    control_packet_size = 64
    device_descriptor = bytes.fromhex('1201000200000040d118002d000100000001')
    config_descriptor = bytes.fromhex('09022000010100c0320904000002ff0000000705810200020007050102000200')

    def __init__(self, context, frame, *, close_after_frame=True, interleave_control=False):
        self.controller = HostMusb(self)
        self.context = context
        self.tls = TlsRecords(context, server=True)
        self.reader, self.reassembler = FrameReader(), Reassembler()
        self.outgoing = bytearray()
        self.frame = frame
        self.close_after_frame = close_after_frame
        self.interleave_control = interleave_control
        self.version = self.discovery = self.audio_released = False
        self.acks = 0
        self.pongs = 0
        self.input_advertised = self.input_bound = False
        self.touches = []
        self.focus = 0
        self.focus_history = []
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

    def send(self, code, data=b'', *, channel=0, flags=ENCRYPTED, fragment_size=0x4000, interleave_ping=False):
        encrypt = self.tls.encrypt if flags & ENCRYPTED else None
        if interleave_ping and len(data) + 2 <= fragment_size:
            raise ValueError('Interleaved control test requires a fragmented video frame')
        for index, frame in enumerate(encode(Message(channel, flags, code, data), encrypt, fragment_size)):
            self.outgoing.extend(frame)
            if index == 0 and interleave_ping:
                self.send(11, b'\x08\x7b')

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
            self.discovery = VIDEO_CHANNEL in [item.id for item in services.channels]
            touch = next((item.input_source_service for item in services.channels if item.id == INPUT_CHANNEL), None)
            if touch is not None:
                assert [(item.width, item.height) for item in touch.touchscreen] == [LCD_SIZE]
                assert not touch.keycodes_supported
                self.input_advertised = True
                self.send(7, b'\x08\x00\x10\x01', channel=INPUT_CHANNEL, flags=CONTROL | ENCRYPTED)
            if self.discovery:
                self.send(18, b'\x08\x01')
        elif channel == INPUT_CHANNEL and code == 8 and data == b'\x08\x00':
            self.send(input_code('KEY_BINDING_REQUEST'), channel=INPUT_CHANNEL)
        elif channel == INPUT_CHANNEL and code == input_code('KEY_BINDING_RESPONSE') and data == b'\x08\x00':
            self.input_bound = True
        elif channel == INPUT_CHANNEL and code == input_code('INPUT_REPORT') and self.input_bound:
            report = schema.parse(INPUT + 'message.InputReport', data)
            touch = report.touch_event
            if not report.HasField('touch_event') or touch.action_index != 0 or len(touch.pointer_data) != 1:
                raise ProtocolError('Expected a single-pointer touch report')
            point, = touch.pointer_data
            if (point.pointer_id or not 0 <= point.x < LCD_SIZE[0] or not 0 <= point.y < LCD_SIZE[1] or
                    (self.touches and report.timestamp <= self.touches[-1]['timestamp_us'])):
                raise ProtocolError('Invalid touch coordinates, pointer ID or timestamp')
            event = {'action': touch.action, 'x': point.x, 'y': point.y, 'timestamp_us': report.timestamp}
            self.touches.append(event)
            self.touch_report(event)
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
        elif channel == VIDEO_CHANNEL and code == 0x8008 and data in (b'\x08\x01\x10\x00', b'\x08\x01\x10\x01',
                                                                     b'\x08\x02\x10\x00', b'\x08\x02\x10\x01'):
            self.focus = data[1]
            self.focus_history.append(self.focus)
            self.video_focus()
        elif channel == 3 and code == 0x8004 and data == b'\x08\x23\x10\x01':
            self.video_ack()
        elif channel == 0 and code == 12 and data == b'\x08\x7b' and self.interleave_control:
            self.pongs += 1
        elif channel == 0 and code == 12 and not self.close_after_frame:
            self.send(11, b'\x08\x01')
        elif channel != 0 or code != 16:
            raise ProtocolError(f'Unexpected virtual phone response {channel}:{code:#x}')

    def touch_report(self, _event):
        pass

    def video_focus(self):
        if self.focus == 1:
            self.send(0, bytes(8) + self.frame, channel=VIDEO_CHANNEL, fragment_size=1200,
                      interleave_ping=self.interleave_control)

    def video_ack(self):
        self.acks += 1
        if self.close_after_frame:
            self.send(15, b'\x08\x01')
        else:
            self.send(11, b'\x08\x01')


class StreamingPhone(VirtualPhone):
    """Paced H.264 source that updates the next frame on a received touch-up."""

    def __init__(self, context, frames, fps):
        super().__init__(context, None, close_after_frame=False)
        self.frames, self.fps = frames, fps
        self.clock = lambda: 0
        self.encoder = av.CodecContext.create('libx264', 'w')
        self.encoder.width, self.encoder.height = LCD_SIZE
        self.encoder.pix_fmt = 'yuv420p'
        self.encoder.time_base = Fraction(1, fps)
        self.encoder.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline',
                                'g': str(fps), 'sc_threshold': '0'}
        self.sent = 0
        self.next_tick = 0
        self.ping_tick = 0
        self.feedback = False
        self.feedback_frame = None
        self.timing = []
        self.in_flight = None
        self.on_touch = None

    def touch_report(self, event):
        if self.on_touch is not None:
            self.on_touch(event)
        if event['action'] == 1:
            self.feedback = True
            if self.feedback_frame is None and self.sent == self.frames:
                self.frames += 1

    def handle(self, message):
        if message.channel == 0 and message.code == 12:
            self.pongs += 1
        else:
            super().handle(message)

    def video_focus(self):
        self.poll()

    def video_ack(self):
        if self.in_flight is None:
            raise ProtocolError('Received an ACK without a pending video frame')
        start, ticks, size, keyframe = self.in_flight
        self.timing.append({'ack_ms': round(1000 * (monotonic() - start), 3), 'guest_ticks': self.clock() - ticks,
                            'bytes': size, 'keyframe': keyframe})
        self.in_flight = None
        self.acks += 1

    def poll(self):
        if not self.tls.ready or not self.discovery:
            return False
        ticks = self.clock()
        if self.focus == 1 and self.in_flight is None and self.sent < self.frames and ticks >= self.next_tick:
            frame = av.VideoFrame(*LCD_SIZE, 'yuv420p')
            values = (145, 54, 34) if self.feedback else (81, 90, 240)
            for plane, color in zip(frame.planes, values):
                plane.update(bytes((color,)) * plane.buffer_size)
            # A moving 64x32 marker changes P-frames without obscuring the LCD sample points.
            luma = memoryview(frame.planes[0])
            x = self.sent * 11 % (LCD_SIZE[0] - 64)
            for row in range(16, 48):
                pos = row * frame.planes[0].line_size + x
                luma[pos:pos + 64] = b'\xeb' * 64
            frame.pts = self.sent
            packets = self.encoder.encode(frame)
            data = b''.join(bytes(packet) for packet in packets)
            if not data:
                raise ProtocolError('The low-latency test encoder buffered a frame')
            self.sent += 1
            if self.feedback and self.feedback_frame is None:
                self.feedback_frame = self.sent
            self.in_flight = monotonic(), ticks, len(data), any(packet.is_keyframe for packet in packets)
            self.next_tick = ticks + GUEST_TICKS_PER_SECOND // self.fps
            self.send(0, struct.pack('>Q', ticks * 1_000_000 // GUEST_TICKS_PER_SECOND) + data,
                      channel=VIDEO_CHANNEL, fragment_size=1200)
            return True
        if ticks >= self.ping_tick:
            self.ping_tick = ticks + GUEST_TICKS_PER_SECOND // 2
            self.send(11, b'\x08\x01')
            return True
        return False


class GuestVideoRun(WindowedRun):
    pixels = None
    reference_rgb = None
    lcd_mean_error = None

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
        if self.reference_rgb is not None:
            report, frame = self.display.capture(self.cpu.mem_read, self.contains_ram)
            if not frame or report['uniform'] or (report['width'], report['height']) != LCD_SIZE:
                return
            actual = packed_rgb(read_lcd_image(BytesIO(frame)))
            self.lcd_mean_error = sum(abs(a - b) for a, b in zip(actual, self.reference_rgb)) / len(actual)
            if self.lcd_mean_error <= LCD_RGB_ERROR_LIMIT:
                self.output.with_suffix('.png').write_bytes(frame)
                self.closing.set()
            return
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


class NativeIntegrationRun(NativeMenuVideoRun):
    """Use actual guest touch sampling, a changing stream and USB re-enumeration."""

    def __init__(self, *args, cycles, camera, restore_map, **kwargs):
        super().__init__(*args, **kwargs)
        self.cycles = cycles
        self.camera = camera
        self.restore_map = restore_map
        self.map_returned = False
        self.map_offset = None
        self.completed = []
        self.stage = 'frame'
        self.stream_start = None
        self.detached_at = None
        self.restore_at = None
        self.camera_sent_tick = None
        self.camera_focus_tick = None
        self.camera_resumed_tick = None
        self.camera_touch_count = None
        self.camera_touch_suppressed = None
        self.camera_error = None
        self.red = self.green = None
        self.phone_port.on_touch = self.log_touch

    def log_touch(self, event):
        with self.output.with_suffix('.touch.jsonl').open('a', encoding='utf-8') as log:
            print(json.dumps({'session': len(self.completed) + 1, **event}), file=log)

    def log_milestone(self, stage, **evidence):
        with self.output.with_suffix('.progress.jsonl').open('a', encoding='utf-8') as log:
            print(json.dumps({'stage': stage, 'guest_ticks': self.clock_ticks(), **evidence}), file=log)

    def contact(self, points):
        for x, y, samples in points:
            for _ in range(samples):
                self.pointer.put((x, y, True))
        self.pointer.put((x, y, False))

    def send_gestures(self):
        self.contact(((400, 240, 10),))
        if not self.completed:
            self.contact(((701, 430, 20),))
            self.contact(((75, 75, 3), (250, 170, 3), (550, 350, 3), (735, 430, 3)))
            self.contact(((5, 5, 6),))
            self.contact(((794, 474, 6),))

    @staticmethod
    def touches_valid(touches, first):
        pressed = False
        starts, ends, moves = [], [], []
        for event in touches:
            if event['action'] == 0 and not pressed:
                pressed = True
                starts.append(event)
            elif event['action'] == 2 and pressed:
                moves.append(event)
            elif event['action'] == 1 and pressed:
                pressed = False
                ends.append(event)
            else:
                return False
        if pressed or len(starts) < (5 if first else 1):
            return False
        if abs(starts[0]['x'] - 400) > 2 or abs(starts[0]['y'] - 240) > 2:
            return False
        if not first:
            return True
        return (ends[1]['timestamp_us'] - starts[1]['timestamp_us'] >= 500_000 and
                len(moves) >= 2 and min(p['x'] for p in (starts[3], starts[4])) <= 8 and
                max(p['x'] for p in (starts[3], starts[4])) >= 791)

    def capture_evidence(self, suffix):
        _, image = self.display.capture(self.cpu.mem_read, self.contains_ram)
        if image:
            self.output.with_name(f'{self.output.name}-{suffix}').with_suffix('.png').write_bytes(image)

    def inspect_projection(self):
        self.next_frame_time = monotonic() + 0.15
        uart = self.uart.output
        phone = self.phone_port
        ticks = self.clock_ticks()
        if self.stage == 'map-button' and monotonic() >= self.restore_at:
            self.tap(400, 345)
            self.map_offset = len(uart)
            self.stage = 'map-close'
        elif self.stage == 'map-close' and b'Android Auto projection listener stopped.' in uart[self.map_offset:]:
            self.map_offset = len(uart)
            self.micom.reply(NAVIGATION_MENU_PACKET)
            self.stage = 'map-menu'
        elif self.stage == 'map-menu' and NAVIGATION_MENU_ACK in uart[self.map_offset:]:
            self.map_returned = True
            self.log_milestone('stock-menu-after-close')
            self.capture_evidence('restored-stock')
            self.closing.set()
        if self.stage.startswith('map-'):
            return
        if self.stage == 'detached':
            if DISPLAY_RELEASED not in uart[self.detached_at:]:
                return
            if self.restore_at is None:
                self.completed[-1]['display_released'] = True
                self.log_milestone('display-released', session=len(self.completed))
                if len(self.completed) == self.cycles:
                    if self.restore_map:
                        self.stage = 'map-button'
                        self.restore_at = monotonic() + 1.5
                    else:
                        self.closing.set()
                    return
                self.restore_at = monotonic() + 3
            if monotonic() < self.restore_at:
                return
            controller = phone.controller
            self.phone_port = StreamingPhone(phone.context, min(phone.frames, 4), phone.fps)
            self.phone_port.clock = self.clock_ticks
            self.phone_port.on_touch = self.log_touch
            self.phone_port.controller = controller
            controller.transport = self.phone_port
            self.phone_port.reconnect()
            self.restore_at = None
            self.stage = 'frame'
            return
        pixels = self.projection_pixels()
        if self.stage == 'frame' and phone.acks and pixels and all(r > 210 and g < 35 and b < 35 for r, g, b in pixels):
            self.red = pixels
            self.stream_start = process_time(), self.clock_ticks(), monotonic()
            self.log_milestone('first-frame', session=len(self.completed) + 1)
            if not self.completed:
                self.capture_evidence('before-touch')
            self.send_gestures()
            self.stage = 'touch'
        elif self.stage == 'touch':
            feedback = phone.feedback_frame is not None and phone.acks >= phone.feedback_frame
            if feedback and not self.green and pixels and all(r < 35 and g > 210 and b < 35 for r, g, b in pixels):
                self.green = pixels
                self.log_milestone('touch-feedback', session=len(self.completed) + 1, frame=phone.feedback_frame)
                if not self.completed:
                    self.capture_evidence('after-touch')
            cases_valid = self.green and self.touches_valid(phone.touches, not self.completed)
            if not cases_valid and ticks - self.stream_start[1] < 30 * GUEST_TICKS_PER_SECOND:
                return
            if self.camera and not self.completed and self.green:
                self.camera_sent_tick = ticks
                self.micom.report_rear_view(True)
                self.stage = 'camera'
            else:
                self.stage = 'drain'
        elif self.stage == 'camera' and phone.focus == 2:
            self.camera_focus_tick = ticks
            self.log_milestone('camera-preempted')
            self.camera_touch_count = len(phone.touches)
            self.contact(((600, 260, 6),))
            self.stage = 'camera-hold'
        elif self.stage == 'camera' and ticks - self.camera_sent_tick >= 10 * GUEST_TICKS_PER_SECOND:
            self.camera_error = 'No native focus response to virtual reverse gear'
            self.micom.report_rear_view(False)
            self.stage = 'drain'
        elif self.stage == 'camera-hold' and ticks - self.camera_focus_tick >= GUEST_TICKS_PER_SECOND // 2:
            self.camera_touch_suppressed = self.camera_touch_count == len(phone.touches)
            phone.frames = max(phone.frames, phone.sent + 2)
            self.micom.report_rear_view(False)
            self.stage = 'camera-return'
        elif self.stage == 'camera-return' and phone.focus == 1:
            self.camera_resumed_tick = ticks
            self.log_milestone('camera-returned', touch_suppressed=self.camera_touch_suppressed)
            self.stage = 'drain'
        elif self.stage == 'camera-return' and ticks - self.camera_focus_tick >= 12 * GUEST_TICKS_PER_SECOND:
            self.camera_error = 'Projection did not regain focus after virtual reverse gear ended'
            self.closing.set()
        if self.stage == 'drain' and phone.acks == phone.frames:
            started_cpu, started_guest, started_wall = self.stream_start
            self.completed.append({
                'version': phone.version, 'mutual_tls': phone.tls.ready, 'video_service': phone.discovery,
                'input_bound': phone.input_bound, 'frames_sent': phone.sent, 'frames_acked': phone.acks,
                'feedback_frame': phone.feedback_frame, 'before_rgb': self.red, 'after_rgb': self.green,
                'touches': phone.touches, 'frame_timing': phone.timing, 'focus': phone.focus_history,
                'touch_cases_passed': self.touches_valid(phone.touches, not self.completed),
                'stream_guest_seconds': (self.clock_ticks() - started_guest) / GUEST_TICKS_PER_SECOND,
                'stream_wall_seconds': round(monotonic() - started_wall, 3),
                'stream_host_cpu_seconds': round(process_time() - started_cpu, 3),
            })
            self.green = None
            self.log_milestone('stream-drained', session=len(self.completed), frames=phone.acks)
            self.detached_at = len(uart)
            phone.controller.set_cable(False)
            self.stage = 'detached'


def verify(args):
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(args.manifest.read_text(encoding='utf-8-sig'))
    image = read_lcd_image(str(args.frame_image)) if args.frame_image else None
    kernel.VIRTUAL_CPU_UNITS_PER_SECOND = round(args.boot_clock_mhz * 1_000_000)
    with (TemporaryDirectory(prefix='gd13my-virtual-phone-', dir=args.output.parent) as staging,
          test_identity(args.openssl) as (cert, key, ctx)):
        staging = Path(staging)
        patch = staging / 'virtual-phone.img'
        shutil.copyfile(args.image, patch)
        startup = None if args.native_menu else build_probe(
            args.compiler, staging, args.lcd_bench, args.owned_window, args.calibrate, args.audio_query)
        with PyFatFS(str(patch), offset=PARTITION_OFFSET, preserve_case=True) as files:
            if startup is not None:
                files.remove('/Application/uComH_New.exe')
                files.writebytes('/Application/uComH_New.exe', startup)
            navi = '/Application/NAVI/'
            files.writebytes(navi + 'i30-ca.pem', cert.read_bytes())
            files.writebytes(navi + 'i30-client.pem', cert.read_bytes())
            files.writebytes(navi + 'i30-client-key.pem', key.read_bytes())
            files.writebytes(navi + 'i30-peer.txt', b'i30-mock.local\n')
        phone = (StreamingPhone(ctx, args.stream_frames, args.fps) if args.stream_frames else
                 VirtualPhone(ctx, test_picture(frame=image), close_after_frame=not args.native_menu,
                              interleave_control=args.interleave_control))
        with args.disk.open('rb') as disk, patch.open('rb') as app:
            media = AppPartitionOverlay(disk, app)
            media.enable_host_utc(manifest['emulator_utc_offset'])
            card = ReadOnlyHsMmc(media, first_lba=DISK_START_LBA, writable_lbas=(
                DISK_START_LBA, DISK_START_LBA + args.disk.stat().st_size // 512))
            output = args.output / 'virtual-phone'
            output.with_suffix('.serial.log').write_bytes(b'')
            runner = (NativeIntegrationRun if args.stream_frames else ReplugNativeMenuRun if args.replug_after_frame else
                      NativeMenuVideoRun if args.native_menu else GuestVideoRun)
            run = runner(args.rom.read_bytes(), card, SimpleQueue(), SimpleQueue(), Event(), Event(),
                         output, phone_port=phone, auto_calibrate=args.calibrate or args.native_menu is not None,
                         usb_clock_units=round(args.usb_clock_mhz * 1_000_000),
                         **({'cycles': args.cycles, 'camera': args.camera, 'restore_map': args.restore_map}
                            if args.stream_frames else {}),
                         **({'display_mode': 2, 'assist_navi_start': True, 'assist_touch_calibration': True}
                            if args.native_menu else {}))
            if image is not None:
                run.reference_rgb = packed_rgb(image)
            if args.stream_frames:
                phone.clock = run.clock_ticks
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
            if image is not None:
                status['source_image'] = str(args.frame_image)
                status['lcd_rgb_mean_absolute_error'] = run.lcd_mean_error
            if args.interleave_control:
                status['interleaved_control_pongs'] = phone.pongs
            if args.audio_query:
                status['wave_format_query'] = {direction.decode(): int(result, 16) for direction, result in
                                               re.findall(rb'i30 WAVE query (OUT|IN): ([a-f0-9]{8})', run.uart.output)}
                status['wave_device_count'] = {direction.decode(): int(result, 16) for direction, result in
                                               re.findall(rb'i30 WAVE devices (OUT|IN): ([a-f0-9]{8})', run.uart.output)}
                status['wave_caps_return'] = {direction.decode(): int(result, 16) for direction, result in
                                               re.findall(rb'i30 WAVE caps (OUT|IN): ([a-f0-9]{8})', run.uart.output)}
                status['wave_caps_data'] = {direction.decode(): result.decode() for direction, result in
                                            re.findall(rb'i30 WAVE data (OUT|IN): ([a-f0-9]{192})', run.uart.output)}
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
            if args.stream_frames:
                status.update(cycles=run.completed, integration_stage=run.stage,
                              last_touches=run.phone_port.touches, last_focus=run.phone_port.focus_history,
                              nominal_fps=args.fps, camera_sent_tick=run.camera_sent_tick,
                              camera_focus_tick=run.camera_focus_tick, camera_resumed_tick=run.camera_resumed_tick,
                              camera_touch_suppressed=run.camera_touch_suppressed, camera_error=run.camera_error,
                              stock_ui_restored=run.map_returned,
                              guest_instructions=report.get('instructions'))
    (args.output / 'virtual-phone.json').write_text(json.dumps(status, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(status, indent=2))
    if args.interleave_control and status['interleaved_control_pongs'] != 1:
        return False
    if args.audio_query and any(set(status[key]) != {'OUT', 'IN'} for key in
                                ('wave_format_query', 'wave_device_count', 'wave_caps_return')):
        return False
    if args.stream_frames:
        return (len(status['cycles']) == args.cycles and
                all(c.get('display_released') and c['after_rgb'] and c['touch_cases_passed'] for c in status['cycles']) and
                (not args.restore_map or status['stock_ui_restored']) and
                (not args.camera or (status['camera_resumed_tick'] is not None and status['camera_touch_suppressed'])))
    if image is not None:
        return bool(status['mutual_tls'] and status['media_acks'] and run.lcd_mean_error is not None and
                    run.lcd_mean_error <= LCD_RGB_ERROR_LIMIT)
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
    parser.add_argument('--frame-image', type=Path, help='Project an 800×480 local image during an isolated LCD test')
    parser.add_argument('--interleave-control', action='store_true',
                        help='Send a control ping between fragments of a video frame during an isolated LCD test')
    parser.add_argument('--audio-query', action='store_true', help='Probe PCM formats in the isolated WinCE LCD bench')
    parser.add_argument('--seconds', type=int, default=230)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--lcd-bench', action='store_true', help='Use the display in the isolated LCD test')
    mode.add_argument('--owned-window', action='store_true', help='Exercise the native window handoff using the current foreground owner')
    mode.add_argument('--native-menu', type=Path, metavar='STOCK_GDDNAVI',
                      help='Use the patched stock menu with the original navigation PE as the GLES reference')
    parser.add_argument('--calibrate', action='store_true', help='Complete the stock touch calibration before creating the test window')
    parser.add_argument('--replug-after-frame', action='store_true',
                        help='Disconnect after the first native frame and verify a fresh projected session')
    parser.add_argument('--stream-frames', type=int, default=0,
                        help='Drive native touches during this many 800x480 H.264 frames')
    parser.add_argument('--fps', type=int, choices=(15, 24, 30), default=15)
    parser.add_argument('--cycles', type=int, default=1, help='Repeat native USB attach, input and display release')
    parser.add_argument('--camera', action='store_true', help='Inject the OEM reverse-gear event during the first stream')
    parser.add_argument('--restore-map', action='store_true', help='Tap the stock map button after the last USB detach')
    parser.add_argument('--usb-clock-mhz', type=float, default=64)
    parser.add_argument('--boot-clock-mhz', type=float, default=4.5)
    args = parser.parse_args()
    if args.frame_image and not args.lcd_bench:
        parser.error('--frame-image requires --lcd-bench')
    if args.interleave_control and not args.lcd_bench:
        parser.error('--interleave-control requires --lcd-bench')
    if args.audio_query and not args.lcd_bench:
        parser.error('--audio-query requires --lcd-bench')
    if args.native_menu and not json.loads(args.manifest.read_text(encoding='utf-8-sig')).get('stock_display_sha256'):
        parser.error('--native-menu requires an image with the stock display publisher')
    if args.replug_after_frame and not args.native_menu:
        parser.error('--replug-after-frame requires --native-menu')
    if args.stream_frames and (not args.native_menu or args.replug_after_frame or args.stream_frames < 12):
        parser.error('--stream-frames requires --native-menu and at least 12 frames')
    if args.cycles < 1 or (not args.stream_frames and (args.camera or args.restore_map or args.cycles != 1)):
        parser.error('--cycles, --camera and --restore-map require the native streaming test')
    if not 4.5 <= args.usb_clock_mhz <= 100:
        parser.error('--usb-clock-mhz must be between 4.5 and 100')
    if not 1 <= args.boot_clock_mhz <= 64:
        parser.error('--boot-clock-mhz must be between 1 and 64')
    if args.calibrate and (args.owned_window or args.lcd_bench):
        parser.error('--calibrate applies to the test window only')
    sys.exit(0 if verify(args) else 1)


if __name__ == '__main__':
    main()
