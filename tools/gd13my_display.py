"""Capture OMAP35x DISPC LCD scanout for the GD13MY RGB565 planes."""

from hashlib import sha256
import struct
import zlib

from gd13my_mmio import ResetBank

BASE = 0x48050000  # DSS and DISPC share a 4 KiB host mapping.
DISPC = 0x400
CONTROL = 0x40
CONFIG, TRANS_COLOR = 0x44, 0x54
GFX_DESTINATION_KEY = 1 << 10
KEY_SELECTION_MASK = 3 << 10
GFX_BA0, GFX_POSITION, GFX_SIZE = 0x80, 0x88, 0x8c
GFX_ATTRIBUTES, GFX_ROW_INC, GFX_PIXEL_INC = 0xa0, 0xac, 0xb0
VID1_REGISTERS = (0xbc, 0xc4, 0xc8, 0xcc, 0xd8, 0xdc)
RGB565 = tuple(bytes(((r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)))
               for r in range(32) for g in range(64) for b in range(32))
RED_HIGH = bytes((value & 0xf8) for value in range(256))
GREEN_HIGH = bytes(value >> 5 for value in range(256))
GREEN_LOW = bytes((value << 3) & 0xe0 for value in range(256))
BLUE_LOW = bytes(value >> 3 for value in range(256))
RGB565_RED = bytes(RGB565[value << 8][0] for value in range(256))
RGB565_BLUE = bytes(RGB565[value][2] for value in range(256))
RGB565_GREEN_HIGH = bytes(RGB565[value << 8][1] & 0xe3 for value in range(256))
RGB565_GREEN_LOW = bytes(RGB565[value][1] & 0x1c for value in range(256))
CALIBRATION_POINTS = ((400, 240), (160, 96), (160, 384), (640, 384), (640, 96))
CALIBRATION_CONFIRM = 'c30666c90ba67003b85bc2c71742ef4741c1ddffb037f324718fcca543af53e2'


def png(width, height, rows):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))

    header = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
    # Compress live LCD frames for latency. The decoded pixels are identical.
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', header) +
            chunk(b'IDAT', zlib.compress(rows, level=1)) + chunk(b'IEND', b''))


class LcdDisplay(ResetBank):
    def __init__(self):
        super().__init__(DISPC + 0x10, DISPC + 0x14)
        self.active = None
        self.video = None
        self.color_key = None
        self._last_scanout = None
        self._last_capture = None

    def reg(self, offset):
        return self.read(DISPC + offset, 4)

    def latch(self):
        self.active = tuple(self.reg(r) for r in (GFX_BA0, GFX_POSITION, GFX_SIZE, GFX_ATTRIBUTES,
                                                 GFX_ROW_INC, GFX_PIXEL_INC))
        self.video = tuple(self.reg(r) for r in VID1_REGISTERS)
        config, key = self.reg(CONFIG), self.reg(TRANS_COLOR)
        self.color_key = key if config & KEY_SELECTION_MASK == GFX_DESTINATION_KEY and key <= 0xffff else None

    def write(self, offset, size, value):
        if offset == self.reset and value & 2:
            self.active = None
        if offset == DISPC + 0x18 and size == 4:
            value = self.reg(0x18) & ~value
        if offset == DISPC + CONTROL and size == 4:
            if not value & 1:
                self.active = None
            elif value & (1 << 5) or not self.reg(CONTROL) & 1:
                self.latch()
            value &= ~(1 << 5)  # Latch GOLCD immediately. No scanout interrupts.
        super().write(offset, size, value)

    @staticmethod
    def layout(registers, contains_ram):
        if registers is None:
            return None, 'lcd_disabled_or_unconfigured'
        base, xy, size, attributes, row_inc, pixel_inc = registers
        if not attributes & 1:
            return None, 'graphics_plane_disabled'
        if (attributes >> 1) & 15 != 6 or xy != 0 or pixel_inc != 1 or not 1 <= row_inc <= 16384:
            return None, 'unsupported_graphics_layout'
        width, height = (size & 0x7ff) + 1, ((size >> 16) & 0x7ff) + 1
        stride = width * 2 + row_inc - 1
        span = stride * (height - 1) + width * 2
        if not base or span > 16 * 1024 * 1024 or not contains_ram(base, span):
            return None, 'framebuffer_outside_ram'
        return (base, width, height, stride, span), 'captured'

    def copy_map_to_video(self, rgb, width, height, write_ram, contains_ram):
        if self.active is None or self.color_key is None or len(rgb) != width * height * 3:
            return False
        video, _ = self.layout(self.video, contains_ram)
        if video is None or video[1:3] != (width, height):
            return False
        base, _, _, stride, _ = video
        packed = bytearray(width * height * 2)
        green = rgb[1::3]
        # Combine whole byte lanes in native code. Discarded RGB bits are
        # truncated exactly as in the guest's packed RGB565 layout.
        low = int.from_bytes(green.translate(GREEN_LOW), 'little') | int.from_bytes(
            rgb[2::3].translate(BLUE_LOW), 'little')
        high = int.from_bytes(rgb[::3].translate(RED_HIGH), 'little') | int.from_bytes(
            green.translate(GREEN_HIGH), 'little')
        packed[::2] = low.to_bytes(width * height, 'little')
        packed[1::2] = high.to_bytes(width * height, 'little')
        row_bytes = width * 2
        rows = (packed[start:start + row_bytes]
                for start in range(len(packed) - row_bytes, -1, -row_bytes))
        if stride == row_bytes:
            write_ram(base, b''.join(rows))
        else:
            for row, data in enumerate(rows):
                write_ram(base + row * stride, bytes(data))
        return True

    def capture(self, read_ram, contains_ram):
        layout, status = self.layout(self.active, contains_ram)
        if layout is None:
            self._last_scanout = self._last_capture = None
            return {'status': status}, None
        base, width, height, stride, span = layout
        source = bytes(read_ram(base, span))
        video, _ = self.layout(self.video, contains_ram)
        backdrop = None
        if video is not None and video[1:3] == (width, height) and self.color_key is not None:
            backdrop = bytes(read_ram(video[0], video[4]))
        scanout = (layout, source, video if backdrop is not None else None, backdrop, self.color_key)
        if scanout == self._last_scanout:
            report, frame = self._last_capture
            return report.copy(), frame
        row_bytes = width * 2
        if backdrop is None and stride == row_bytes:
            packed = source
        else:
            words = struct.Struct(f'<{width}H')
            key = self.color_key
            key_row = struct.pack('<H', key) * width if backdrop is not None else None
            rows = []
            for row in range(height):
                start = row * stride
                pixels = source[start:start + row_bytes]
                if backdrop is not None:
                    video_start = row * video[3]
                    if pixels == key_row:
                        pixels = backdrop[video_start:video_start + row_bytes]
                    else:
                        front = words.unpack(pixels)
                        if key in front:
                            behind = words.unpack_from(backdrop, video_start)
                            pixels = words.pack(*(v if p == key else p for p, v in zip(front, behind)))
                rows.append(pixels)
            packed = b''.join(rows)
        low, high = packed[::2], packed[1::2]
        green = int.from_bytes(high.translate(RGB565_GREEN_HIGH), 'little') | int.from_bytes(
            low.translate(RGB565_GREEN_LOW), 'little')
        rgb = bytearray(width * height * 3)
        rgb[::3] = high.translate(RGB565_RED)
        rgb[1::3] = green.to_bytes(width * height, 'little')
        rgb[2::3] = low.translate(RGB565_BLUE)
        rgb_row_bytes = width * 3
        png_rows = b''.join(b'\0' + rgb[start:start + rgb_row_bytes]
                           for start in range(0, len(rgb), rgb_row_bytes))
        report = {'status': 'captured', 'base': hex(base), 'width': width, 'height': height,
                  'stride': stride, 'uniform': packed == packed[:2] * (width * height)}
        frame = png(width, height, png_rows)
        self._last_scanout = scanout
        self._last_capture = report.copy(), frame
        return report, frame

    @staticmethod
    def scanout_pixel(scanout, x, y):
        layout, source, video, backdrop, color_key = scanout
        offset = y * layout[3] + x * 2
        value = int.from_bytes(source[offset:offset + 2], 'little')
        if backdrop is not None and value == color_key:
            offset = y * video[3] + x * 2
            return int.from_bytes(backdrop[offset:offset + 2], 'little')
        return value

    def scanout_matches(self, width, height, samples):
        scanout = self._last_scanout
        return bool(scanout and scanout[0][1:3] == (width, height) and all(
            RGB565[self.scanout_pixel(scanout, x, y)] == color for x, y, color in samples))

    def calibration_contact(self, visited):
        """Recognize the stock .061 calibration screens on the LCD scanout."""
        if self._last_scanout is None:
            return None
        _, width, height, _, _ = self._last_scanout[0]
        if (width, height) != (800, 480):
            return None

        def pixel(x, y):
            return self.scanout_pixel(self._last_scanout, x, y)

        if any(pixel(x, y) != 0xffff for x, y in ((18, 18), (18, 461), (781, 461))):
            return None
        if len(visited) == len(CALIBRATION_POINTS):
            digest = sha256()
            for y in range(18, 82):
                for x in range(570, 798):
                    digest.update(RGB565[pixel(x, y)])
            return (400, 230) if digest.hexdigest() == CALIBRATION_CONFIRM else None
        for x, y in CALIBRATION_POINTS:
            if (x, y) in visited:
                continue
            arms = ((x + 12, y), (x - 12, y), (x, y + 12), (x, y - 12))
            if all(pixel(px, py) == 0 for px, py in arms):
                return x, y
        return None
