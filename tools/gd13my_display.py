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
        for row in range(height):
            start = (height - row - 1) * width * 3  # OpenGL readback starts at the bottom.
            packed = bytearray(width * 2)
            for index, (r, g, b) in enumerate(struct.iter_unpack('BBB', rgb[start:start + width * 3])):
                struct.pack_into('<H', packed, index * 2, ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3))
            write_ram(base + row * stride, bytes(packed))
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
        unpack = struct.Struct(f'<{width}H').unpack_from
        rgb = bytearray()
        first = None
        uniform = True
        for row in range(height):
            pixels = unpack(source, row * stride)
            if backdrop is not None and self.color_key in pixels:
                behind = unpack(backdrop, row * video[3])
                pixels = tuple(v if p == self.color_key else p for p, v in zip(pixels, behind))
            if uniform:
                if first is None:
                    first = pixels[0]
                uniform = pixels.count(first) == width
            rgb.append(0)  # No PNG row filter.
            rgb.extend(b''.join(map(RGB565.__getitem__, pixels)))
        report = {'status': 'captured', 'base': hex(base), 'width': width, 'height': height,
                  'stride': stride, 'uniform': uniform}
        frame = png(width, height, rgb)
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
