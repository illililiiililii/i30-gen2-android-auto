"""Small OMAP35x register models for the first GD13MY CE kernel stages."""

from collections import Counter, deque
from functools import reduce
from operator import xor
from os import fstat
import struct
from types import SimpleNamespace

PAGE = 0x1000
UART3_BASE = 0x49020000
MMC_BASES = (0x4809c000, 0x480b4000, 0x480ad000)
MMC_IRQS = (83, 86, 94)


class RegisterBank:
    def __init__(self, pages=1):
        self.data = bytearray(PAGE * pages)

    def read(self, offset, size):
        return int.from_bytes(self.data[offset:offset + size], 'little')

    def write(self, offset, size, value):
        self.data[offset:offset + size] = value.to_bytes(size, 'little')


class ResetBank(RegisterBank):
    """Complete the module's documented soft-reset handshake without elapsed hardware time."""

    def __init__(self, reset, status, *, reset_mask=2):
        super().__init__()
        self.reset, self.status, self.reset_mask = reset, status, reset_mask
        super().write(status, 4, 1)

    def write(self, offset, size, value):
        if offset == self.reset and value & self.reset_mask:
            self.data[:] = bytes(len(self.data))
            super().write(self.status, 4, 1)
            value &= ~self.reset_mask
        super().write(offset, size, value)


class DebugUart(ResetBank):
    def __init__(self, trace_limit=32 * 1024):
        super().__init__(reset=0x54, status=0x58)
        self.trace_limit = trace_limit
        self.output = bytearray()
        self.divisor_low = 0

    def read(self, offset, size):
        if offset == 0x00:
            return self.divisor_low if self.data[0x0c] & 0x80 else 0
        if offset == 0x14:
            return 0x60  # The trace sink drains transmit bytes immediately.
        if offset == 0x08 and self.data[0x0c] != 0xbf:
            return 1  # No UART interrupt pending.
        return super().read(offset, size)

    def write(self, offset, size, value):
        if offset == 0x00:
            if self.data[0x0c] & 0x80:
                self.divisor_low = value & 0xff
            elif len(self.output) < self.trace_limit:
                self.output.append(value & 0xff)
            return
        super().write(offset, size, value)


class OmapUart(DebugUart):
    """OMAP UART byte transport with receive and transmit-empty interrupts."""

    def __init__(self):
        super().__init__()
        self.input = deque()
        self.tx_empty = True
        self.peer = None

    def interrupt_id(self):
        enable = self.data[0x04]
        if self.input and enable & 1:
            return 4
        if self.tx_empty and enable & 2:
            return 2
        return 1

    def irq_pending(self):
        return self.interrupt_id() != 1

    def read(self, offset, size):
        if offset == 0 and self.input and not self.data[0x0c] & 0x80:
            return self.input.popleft()
        if offset == 0x08 and self.data[0x0c] != 0xbf:
            result = self.interrupt_id()
            if result == 2:
                self.tx_empty = False
            return result
        if offset == 0x14:
            return 0x60 | bool(self.input)
        return super().read(offset, size)

    def write(self, offset, size, value):
        if offset == 0x00 and not self.data[0x0c] & 0x80:
            self.tx_empty = True
            if self.peer is not None:
                self.peer(value & 0xff)
        elif offset == 0x04 and not self.data[0x0c] & 0x80 and value & 2 and not self.data[0x04] & 2:
            self.tx_empty = True
        super().write(offset, size, value)


class MicomCdp:
    """Virtual bench MICOM for the GD13MY CDP start-up exchange."""

    def __init__(self, uart, *, display_mode=3):
        self.uart = uart
        self.display_mode = display_mode
        self.buffer = bytearray()
        self.sequence = 0
        self.last_request = None
        self.exchanges = deque(maxlen=32)
        self.navigation_volume = 8

    def reply(self, payload):
        body = bytes((self.sequence,)) + payload
        self.uart.input.extend(bytes((0x16,)) + body + bytes((reduce(xor, body),)))
        self.sequence = (self.sequence + 1) & 0xff

    def report_rear_view(self, reverse_gear=False):
        # LibSystem .061 decodes bit 2 of SYS 0x95 before its rear-view branch.
        self.reply(bytes((0xe0, 3, 0x95, 4 if reverse_gear else 0, 0)))

    def set_navigation_volume(self, level):
        # GDdNavi .061 accepts navigation volume levels 0 through 18 in its D1/D2 handlers.
        self.navigation_volume = min(18, max(0, level))
        self.reply(bytes((0xd0, 2, 0xd1, self.navigation_volume)))
        return self.navigation_volume

    def receive(self, value):
        if not self.buffer and value != 0x16:
            return
        self.buffer.append(value)
        if len(self.buffer) < 4:
            return
        device = self.buffer[2]
        control = device in (1, 6)
        length = 4 if control else self.buffer[3] + 5
        if len(self.buffer) < length:
            return
        _, serial, _, *rest = self.buffer
        valid = reduce(xor, self.buffer[1:]) == 0
        self.buffer.clear()
        if not valid or control:
            return
        self.uart.input.extend((0x16, serial, 6, serial ^ 6))
        request = bytes((device, *rest[:-1]))
        if (serial, request) == self.last_request:
            return
        self.last_request = serial, request
        self.exchanges.append(request.hex(' '))
        if request == b'\xe0\x01\x03':  # AN_SYS_ALIVE
            self.reply(b'\xe0\x02\x12\x00')
            self.reply(b'\xe0\x01\x13')
        elif request == b'\xe0\x01\x02':  # AN_SYS_ACC_ON
            self.reply(bytes((0xe0, 0x02, 0x1a, self.display_mode)))
            self.reply(b'\xe0\x05\x14\0\0\0\0')  # AN_SYS_RPWR_ON for the virtual bench.
        elif request == b'\xd0\x01\xc2':  # GDdNavi::SendGetVolume.
            self.reply(bytes((0xd0, 2, 0xd2, self.navigation_volume)))
        elif len(request) == 5 and request[:3] == b'\xd0\x03\xc1' and request[4] == 1:
            self.set_navigation_volume(request[3])


class ExternalUart(DebugUart):
    """Disconnected 16550-style DUART port with registers on two-byte boundaries."""

    def read(self, offset, size):
        return super().read(offset * 2, size) if offset < 16 and offset % 2 == 0 else 0

    def write(self, offset, size, value):
        if offset < 16 and offset % 2 == 0:
            super().write(offset * 2, size, value)


class PadControl(RegisterBank):
    def write(self, offset, size, value):
        super().write(offset, size, value)
        if offset == 0x270 and value & 2:
            # CONTROL_PADCONF_OFF.STARTSAVE latches GENERAL_PURPOSE_STATUS.SAVEDONE.
            super().write(0x2f4, 4, self.read(0x2f4, 4) | 1)


class ClockManager(RegisterBank):
    """Model IVA2 DPLL lock and the always-clocked virtual CORE interconnect."""

    IVA2_PLL_ENABLE, IVA2_PLL_STATUS, CORE_STATUS = 0x04, 0x24, 0xa4c

    def __init__(self):
        super().__init__(2)

    def read(self, offset, size):
        if offset == self.IVA2_PLL_STATUS:
            return int((super().read(self.IVA2_PLL_ENABLE, 4) & 7) == 7)
        if offset == self.CORE_STATUS:
            return 3  # L3 and L4 retain clocks while the CPU accesses the emulated bus.
        return super().read(offset, size)

    def write(self, offset, size, value):
        if offset not in (self.IVA2_PLL_STATUS, self.CORE_STATUS):
            super().write(offset, size, value)


class PowerRegisters(RegisterBank):
    """Record the retained domains after a host-assisted idle wake."""

    PREVIOUS_STATE = (0x9e8, 0xae8)  # MPU and CORE PRM_PREPWSTST.

    def __init__(self):
        super().__init__(2)

    def wake(self):
        for offset in self.PREVIOUS_STATE:
            self.write(offset, 4, 3)  # This model retains both domains in the ON state.


class DisconnectedMusb(ResetBank):
    """OMAP MUSB register initialization with ID high and no VBUS."""

    DEVCTL = 0x60
    EP0_CSR = 0x102

    def __init__(self):
        super().__init__(reset=0x404, status=0x408)

    def read(self, offset, size):
        value = super().read(offset, size)
        return value | 0x80 if offset == self.DEVCTL else value

    def write(self, offset, size, value):
        if offset == self.DEVCTL and size == 1:
            value &= 0x03  # SESSION and HOSTREQ are writable. Cable status is read-only.
        elif offset == self.EP0_CSR and size == 2:
            value &= ~0x100  # FLUSHFIFO completes immediately on the empty endpoint.
        elif offset == self.EP0_CSR + 1 and size == 1:
            value &= ~1
        super().write(offset, size, value)


class DisconnectedIsp1582(RegisterBank):
    """Register-level ISP1582 startup over the GD13MY's spaced byte lanes."""

    MODE_LOW, MODE_HIGH = 0x18, 0x1a
    ID = {0xe0: 0x30, 0xe2: 0x82, 0xe4: 0x15}
    INTERRUPT = (0x30, 0x32, 0x34, 0x36)

    def read(self, offset, size):
        if size == 1 and offset in self.ID:
            return self.ID[offset]
        return super().read(offset, size)

    def write(self, offset, size, value):
        if size != 1 or offset & 1 or offset in self.ID:
            return
        if offset == self.MODE_LOW and self.data[offset] & 0x10 and not value & 0x10:
            self.data[:] = bytes(len(self.data))
            value = 0
        elif offset == self.MODE_HIGH:
            value &= 2  # DMACLKON is writable, VBUSSTAT stays low without a cable.
        elif offset in self.INTERRUPT:
            value = self.data[offset] & ~value
        super().write(offset, size, value)


class EmptyMcSpi(ResetBank):
    """McSPI with an optional display MCU on channel 3."""

    FIRST, STRIDE, CHANNELS = 0x2c, 0x14, 4
    CONF, STAT, CTRL, TX, RX = (0, 4, 8, 12, 16)
    RXS, TXS, EOT = 1, 2, 4

    def __init__(self, touch=None):
        super().__init__(reset=0x10, status=0x14)
        self.touch = touch

    def irq_pending(self):
        return bool(self.read(0x18, 4) & self.read(0x1c, 4))

    def read(self, offset, size):
        value = super().read(offset, size)
        if self.FIRST <= offset < self.FIRST + self.STRIDE * self.CHANNELS and size == 4:
            register = (offset - self.FIRST) % self.STRIDE
            if register == self.RX:
                status = offset - self.RX + self.STAT
                super().write(status, 4, super().read(status, 4) & ~self.RXS)
        return value

    def write(self, offset, size, value):
        if offset == 0x18 and size == 4:
            super().write(offset, size, self.read(offset, size) & ~value)
            return
        if self.FIRST <= offset < self.FIRST + self.STRIDE * self.CHANNELS and size == 4:
            register = (offset - self.FIRST) % self.STRIDE
            base = offset - register
            if register in (self.STAT, self.RX):
                return
            if register == self.CTRL:
                super().write(base + self.STAT, 4, self.TXS if value & 1 else 0)
            elif register == self.TX and super().read(base + self.CTRL, 4) & 1:
                config = super().read(base + self.CONF, 4)
                status = self.TXS | self.EOT
                if (config >> 12) & 3 != 2:  # TX-only mode does not capture a word.
                    width = ((config >> 7) & 31) + 1
                    reply = (1 << width) - 1
                    if base == 0x68 and self.touch is not None and width == 32:
                        reply = self.touch.transfer(value)
                    super().write(base + self.RX, 4, reply)
                    rx_full = 4 << (4 * ((base - self.FIRST) // self.STRIDE))
                    super().write(0x18, 4, self.read(0x18, 4) | rx_full)
                    status |= self.RXS
                super().write(base + self.STAT, 4, status)
        super().write(offset, size, value)


class OmapGpio(ResetBank):
    """GPIO interrupt bank with an externally driven input."""

    def __init__(self, attached_pins):
        super().__init__(reset=0x10, status=0x14)
        self.attached_pins = attached_pins
        self.inputs = 0

    def set_input(self, pin, high):
        before = self.inputs
        self.inputs = before | pin if high else before & ~pin
        edges = ~before & self.inputs & self.read(0x48, 4)
        edges |= before & ~self.inputs & self.read(0x4c, 4)
        super().write(0x18, 4, super().read(0x18, 4) | edges)

    def read(self, offset, size):
        if offset == 0x38 and size == 4:
            return self.inputs
        value = super().read(offset, size)
        if offset == 0x18 and size == 4:
            value |= self.attached_pins & (
                (~self.inputs & self.read(0x40, 4)) | (self.inputs & self.read(0x44, 4)))
        return value

    def write(self, offset, size, value):
        if size == 4:
            if offset == 0x18:
                value = super().read(offset, size) & ~value
            elif offset == 0x60:
                offset, value = 0x1c, self.read(0x1c, 4) & ~value
            elif offset == 0x64:
                offset, value = 0x1c, self.read(0x1c, 4) | value
        super().write(offset, size, value)

    def irq_pending(self):
        return bool(self.read(0x18, 4) & self.read(0x1c, 4))


class TouchController:
    """GD13MY display MCU contact messages on McSPI1 CS3 and GPIO118."""

    PIN = 1 << (118 % 32)

    def __init__(self):
        self.gpio = OmapGpio(self.PIN)
        self.gpio.set_input(self.PIN, True)
        self.pending = None
        self.consumed = 0
        self.commands = Counter()
        self.last_reply = 0

    def submit(self, x, y, down):
        self.pending = (0xc1000000 if down else 0xc0000000) | (
            (x & 0x300) << 12) | ((y & 0x300) << 8) | ((x & 0xff) << 8) | (y & 0xff)
        self.gpio.set_input(self.PIN, False)

    def transfer(self, word):
        self.commands[word] += 1
        if word != 0x80000000 or self.pending is None:
            return 0
        self.last_reply = self.pending
        self.pending = None
        self.consumed += 1
        self.gpio.set_input(self.PIN, True)
        return self.last_reply


class SgxRegisters(RegisterBank):
    """Expose the OMAP35x SGX530 revision without executing GPU commands."""

    CORE_REVISION = 0x14

    def __init__(self):
        super().__init__(4)
        super().write(self.CORE_REVISION, 4, 0x00010201)

    def write(self, offset, size, value):
        if not self.CORE_REVISION <= offset < self.CORE_REVISION + 4:
            super().write(offset, size, value)


class EmptyI2c(ResetBank):
    """An OMAP I2C controller without any devices on its bus."""

    def __init__(self):
        super().__init__(reset=0x20, status=0x10)

    def write(self, offset, size, value):
        if offset == 0x08:
            value = self.read(0x08, 2) & ~value
        elif offset == 0x24 and value & 0x8001 == 0x8001:
            super().write(0x08, 2, self.read(0x08, 2) | 6)  # NACK and ARDY.
            value &= ~3  # START and STOP are consumed by the controller.
        super().write(offset, size, value)

    def irq_pending(self):
        return bool(self.data[0x08] & self.data[0x04] & 6)


class GpTimer(ResetBank):
    def __init__(self, clock=None):
        super().__init__(reset=0x10, status=0x14)
        self.clock = clock
        self.epoch = None
        self.previous = 0

    def counter(self):
        count = super().read(0x28, 4)
        if self.epoch is not None:
            count += self.clock() - self.epoch
        return count & 0xffffffff

    def read(self, offset, size):
        if offset == 0x28:
            if self.clock is not None:
                return self.counter() & ((1 << (8 * size)) - 1)
            if self.data[0x24] & 1:
                # The minimal model advances the running counter only when sampled.
                super().write(0x28, 4, (self.counter() + 1) & 0xffffffff)
        return super().read(offset, size)

    def write(self, offset, size, value):
        if offset == 0x18:
            value = self.read(0x18, 4) & ~value
        if self.clock is not None:
            if offset == 0x24:
                super().write(0x28, 4, self.counter())
                self.epoch = self.clock() if value & 1 else None
            elif offset in (0x28, 0x30) and self.epoch is not None:
                self.epoch = self.clock()
            elif offset == 0x10 and value & 2:
                self.epoch = None
        if offset == 0x30:
            super().write(0x28, 4, self.read(0x2c, 4))
        super().write(offset, size, value)
        if offset in (0x10, 0x24, 0x28, 0x30, 0x38):
            self.previous = self.counter()

    def irq_pending(self):
        count = self.counter()
        elapsed = (count - self.previous) & 0xffffffff
        distance = (self.read(0x38, 4) - self.previous) & 0xffffffff
        if self.data[0x24] & 0x41 == 0x41 and 0 < distance <= elapsed:
            super().write(0x18, 4, self.read(0x18, 4) | 1)
        self.previous = count
        return bool(self.read(0x18, 4) & self.read(0x1c, 4) & 1)

    def ticks_to_match(self):
        if self.epoch is not None and (self.data[0x24] & 0x41) == 0x41 and self.data[0x1c] & 1:
            distance = (self.read(0x38, 4) - self.counter()) & 0xffffffff
            return distance or None
        return None


class OmapIntc(ResetBank):
    """Route level interrupts from the three OMAP3 interrupt banks."""

    def __init__(self, sources):
        super().__init__(reset=0x10, status=0x14)
        self.sources = sources
        self.masks = [0xffffffff] * 3
        self.active = None

    def read(self, offset, size):
        if offset == 0x40:
            return self.active if self.active is not None else 0xffffff80
        if 0x80 <= offset < 0xe0:
            bank, register = divmod(offset - 0x80, 0x20)
            if register == 4:
                return self.masks[bank]
            if register == 0x18:
                return sum(1 << (irq % 32) for irq in self.pending() if irq // 32 == bank)
        return super().read(offset, size)

    def write(self, offset, size, value):
        if 0x80 <= offset < 0xe0:
            bank, register = divmod(offset - 0x80, 0x20)
            if register == 4:
                self.masks[bank] = value
            elif register == 8:
                self.masks[bank] &= ~value
            elif register == 0xc:
                self.masks[bank] |= value
        elif offset == 0x10 and value & 2:
            self.masks[:], self.active = [0xffffffff] * 3, None
        elif offset == 0x48 and value & 1:
            self.active = None
        super().write(offset, size, value)

    def pending(self):
        return [irq for irq, source in self.sources.items() if source.irq_pending() and self.routes_irq(irq)]

    def routes_irq(self, irq):
        return not self.masks[irq // 32] & (1 << (irq % 32)) and not self.read(0x100 + 4 * irq, 4) & 1


class EmptyHsMmc(ResetBank):
    """HSMMC register startup with no media or DMA backend attached."""

    def __init__(self):
        super().__init__(reset=0x10, status=0x14)

    def write(self, offset, size, value):
        if offset == 0x12c:
            value = (value & ~0x07000002) | ((value & 1) << 1)  # Resets complete and ICE drives ICS.
        elif offset == 0x130:
            value = self.read(0x130, 4) & ~value  # STAT is write-one-to-clear.
        elif offset == 0x10c:
            status = 0x18000 if value & 0x30000 else 1  # CTO|ERRI or command complete without a response.
            super().write(0x130, 4, self.read(0x130, 4) | status)
        super().write(offset, size, value)


class ReadOnlyHsMmc(EmptyHsMmc):
    """Sector-addressed eMMC with a read-only backing file and optional volatile writes."""

    SECTOR = 512
    CC, TC, BWR, BRR, CTO, DTO, ERRI = 1, 2, 1 << 4, 1 << 5, 1 << 16, 1 << 20, 1 << 15

    def __init__(self, image, *, first_lba=0, writable_lbas=None):
        super().__init__()
        self.image = image
        length = fstat(image.fileno()).st_size
        self.first_lba = first_lba
        self.sectors = first_lba + length // self.SECTOR
        if length < self.SECTOR or length % self.SECTOR or first_lba < 0 or self.sectors >= 2**32:
            raise ValueError('MMC image must contain a whole number of 512-byte sectors')
        self.commands = Counter()
        self.read_requests = deque(maxlen=32)
        self.bytes_read = 0
        self.writable_lbas = writable_lbas
        self.overlay = {}
        self.write_lba = None
        self.write_payload = bytearray()
        self.position = 0
        self.payload = b''
        self.rca = 0
        self.state = 0
        self.dma_enabled = False

    def set_status(self, bits):
        RegisterBank.write(self, 0x130, 4, self.read(0x130, 4) | bits)

    def irq_pending(self):
        return bool(self.read(0x130, 4) & self.read(0x134, 4) & self.read(0x138, 4))

    def read(self, offset, size):
        if offset == 0x124:
            present = (1 << 16) | (1 << 17) | (1 << 18)
            if self.write_lba is not None:
                present |= 1 << 10
            return present | ((1 << 11) if self.payload else 0)
        if offset == 0x140:
            return 1 << 25  # 3.0 V signaling.
        if offset == 0x120 and self.payload and size == 4:
            return int.from_bytes(self.read_data(4), 'little')
        return super().read(offset, size)

    def read_data(self, size):
        data = self.payload[self.position:self.position + size]
        self.position += len(data)
        self.bytes_read += len(data)
        if self.position == len(self.payload):
            self.payload = b''
            self.set_status(self.TC)
        elif self.position % self.SECTOR == 0:
            self.set_status(self.BRR)
        return data

    def write_data(self, data):
        self.write_payload[self.position:self.position + len(data)] = data
        self.position += len(data)
        if self.position == len(self.write_payload):
            for index in range(0, self.position, self.SECTOR):
                sector = self.write_lba + index // self.SECTOR
                self.overlay[sector] = bytes(self.write_payload[index:index + self.SECTOR])
            self.write_lba = None
            self.write_payload = bytearray()
            self.set_status(self.TC)
        elif self.position % self.SECTOR == 0:
            self.set_status(self.BWR)

    def write(self, offset, size, value):
        if offset == 0x120 and size == 4 and self.write_lba is not None:
            self.write_data(value.to_bytes(4, 'little'))
            return
        if offset == 0x10 and value & 2:
            self.position, self.payload, self.state, self.rca = 0, b'', 0, 0
            self.write_lba = None
            self.write_payload = bytearray()
        if offset != 0x10c or size != 4:
            super().write(offset, size, value)
            return
        RegisterBank.write(self, offset, size, value)
        command = (value >> 24) & 63
        argument = self.read(0x108, 4)
        self.commands[command] += 1
        response = self.command(command, argument, value)
        self.dma_enabled = bool(value & 1 and response is not None and (self.payload or self.write_lba is not None))
        if response is None:
            self.set_status(self.CTO | self.ERRI)
            return
        for register in range(4):
            RegisterBank.write(self, 0x110 + 4 * register, 4, (response >> (32 * register)) & 0xffffffff)
        self.set_status(self.CC | (self.BRR if self.payload else 0) |
                        (self.BWR if self.write_lba is not None else 0))

    def command(self, command, argument, flags):
        match command:
            case 0:
                self.position, self.payload, self.state, self.rca = 0, b'', 0, 0
                self.write_lba = None
                self.write_payload = bytearray()
                return 0
            case 1:
                self.state = 1
                return 0xc0ff8000  # Ready, sector addressing and supported voltage range.
            case 2:
                self.state = 2
                return int.from_bytes(b'\x01\x00\x00GD13MY\x10\x00\x00\x00\x01\x21\x01', 'big') >> 8
            case 3:
                self.rca = argument >> 16
                self.state = 3
            case 7:
                self.state = 4 if argument >> 16 == self.rca else 3
            case 9:
                return ((3 << 126) | (4 << 122) | (0x32 << 96) | (0x5b5 << 84) |
                        (9 << 80) | (0xfff << 62) | (7 << 47) | (9 << 22)) >> 8
            case 8 if self.state == 4 and flags & (1 << 21):
                ext_csd = bytearray(self.SECTOR)
                ext_csd[192] = 5  # EXT_CSD revision 1.5 (MMC 4.41).
                ext_csd[196] = 1  # 26 MHz card type.
                struct.pack_into('<I', ext_csd, 212, self.sectors)
                self.payload, self.position = ext_csd, 0
            case 17 | 18 if self.state == 4 and flags & (1 << 21):
                block = self.read(0x104, 4)
                count = (block >> 16) if command == 18 else 1
                if (block & 0xfff) != self.SECTOR or not count or argument + count > self.sectors:
                    self.set_status(self.DTO | self.ERRI)
                    return (1 << 31) | (self.state << 9)  # Out of range.
                padding = min(count, max(0, self.first_lba - argument))
                self.image.seek(max(0, argument - self.first_lba) * self.SECTOR)
                data = bytes(padding * self.SECTOR) + self.image.read((count - padding) * self.SECTOR)
                if len(data) != count * self.SECTOR:
                    self.set_status(self.DTO | self.ERRI)
                    return (1 << 19) | (self.state << 9)
                if self.overlay:
                    data = bytearray(data)
                    for index in range(count):
                        sector = self.overlay.get(argument + index)
                        if sector is not None:
                            start = index * self.SECTOR
                            data[start:start + self.SECTOR] = sector
                self.payload, self.position = data, 0
                self.read_requests.append((argument, count))
            case 24 | 25 if self.state == 4 and flags & (1 << 21) and self.writable_lbas is not None:
                block = self.read(0x104, 4)
                count = (block >> 16) if command == 25 else 1
                start, end = self.writable_lbas
                if (block & 0xfff) != self.SECTOR or not count:
                    return (1 << 29) | (self.state << 9)  # BLOCK_LEN_ERROR.
                if not start <= argument < argument + count <= end:
                    return (1 << 26) | (self.state << 9) | (1 << 8)
                self.write_lba, self.position = argument, 0
                self.payload = b''
                self.write_payload = bytearray(count * self.SECTOR)
            case 12:
                self.payload, self.position = b'', 0
                self.write_lba = None
                self.write_payload = bytearray()
            case 6 | 13 | 16 | 23:
                pass
            case 24 | 25 | 28 | 29 | 38:
                return (1 << 26) | (self.state << 9) | (1 << 8)  # WP_VIOLATION.
            case _:
                return None
        return (self.state << 9) | (1 << 8)


class SdMaIrq:
    def __init__(self, dma, line):
        self.dma, self.line = dma, line

    def irq_pending(self):
        return bool(self.dma.read(0x08 + 4 * self.line, 4) & self.dma.read(0x18 + 4 * self.line, 4))


class OmapSdMa(ResetBank):
    """DMA4 transfers between the active HSMMC data register and physical RAM."""

    CHANNEL, STRIDE, ENABLE = 0x80, 0x60, 1 << 7
    STATUS_COMPLETE = (1 << 3) | (1 << 4) | (1 << 5)

    def __init__(self, card, port, memory):
        super().__init__(reset=0x2c, status=0x28)
        self.card, self.port = card, port
        self.contains_ram, self.read_ram, self.write_ram = memory
        self.enabled = set()
        self.recent = deque(maxlen=32)
        self.transfers = 0

    def write(self, offset, size, value):
        if size == 4:
            if 0x08 <= offset <= 0x14 or offset >= self.CHANNEL and (offset - self.CHANNEL) % self.STRIDE == 0x0c:
                value = self.read(offset, 4) & ~value
            elif offset == self.reset and value & 2:
                self.enabled.clear()
            elif self.CHANNEL <= offset < self.CHANNEL + 32 * self.STRIDE and (offset - self.CHANNEL) % self.STRIDE == 0:
                if value & self.ENABLE:
                    self.enabled.add(offset)
                else:
                    self.enabled.discard(offset)
        super().write(offset, size, value)

    def service(self):
        card = self.card
        if not self.enabled or not card.dma_enabled:
            return
        for base in sorted(self.enabled):
            control, _, interrupt, _, config, elements, frames, source, destination = struct.unpack_from('<9I', self.data, base)
            kind = config & 3
            length = (elements & 0xffffff) * (frames & 0xffff) * (1 << kind)
            mode = (control >> 12) & 15
            if not 0 < length <= 2048 * card.SECTOR or kind == 3:
                continue
            if (source == self.port and mode == 4 and length <= len(card.payload) - card.position
                    and self.contains_ram(destination, length)):
                self.write_ram(destination, bytes(card.read_data(length)))
            elif (destination == self.port and mode == 1 and length <= len(card.write_payload) - card.position
                    and self.contains_ram(source, length)):
                card.write_data(self.read_ram(source, length))
            else:
                continue
            channel = (base - self.CHANNEL) // self.STRIDE
            self.recent.append({'channel': channel, 'ccr': hex(control), 'cicr': hex(interrupt),
                                'source': hex(source), 'destination': hex(destination), 'bytes': length})
            self.transfers += 1
            self.enabled.remove(base)
            super().write(base, 4, control & ~self.ENABLE)
            super().write(base + 0x0c, 4, self.read(base + 0x0c, 4) | self.STATUS_COMPLETE)
            if interrupt & self.STATUS_COMPLETE:
                for line in range(4):
                    if self.read(0x18 + 4 * line, 4) & (1 << channel):
                        offset = 0x08 + 4 * line
                        super().write(offset, 4, self.read(offset, 4) | (1 << channel))


class SyncTimer(RegisterBank):
    COUNTER = 0x10

    def __init__(self, clock=None):
        super().__init__()
        self.clock = clock
        self.poll_ticks = 0

    def read(self, offset, size):
        if not self.COUNTER <= offset < self.COUNTER + 4:
            return super().read(offset, size)
        if self.clock is None:
            self.poll_ticks += 1
        ticks = self.poll_ticks if self.clock is None else self.clock()
        bits = (ticks & 0xffffffff) >> (8 * (offset - self.COUNTER))
        return bits & ((1 << (size * 8)) - 1)


def boot_devices(uart, *, empty_mmc=False, timer_clock=None, card=None, slot=1, timer_irq=False,
                 touch=None, dma=None, musb=None):
    timer = GpTimer(timer_clock)
    i2c = {irq: EmptyI2c() for irq in (56, 57, 61)}
    spi = EmptyMcSpi(touch)
    spi2 = EmptyMcSpi()
    uart1 = OmapUart()
    sources = {37: timer, **i2c, 66: spi2, 72: uart1}
    if touch is not None:
        sources.update({32: touch.gpio, 65: spi})
    if dma is not None:
        sources.update({12 + line: SdMaIrq(dma, line) for line in range(4)})
    if card is not None:
        sources[MMC_IRQS[slot - 1]] = card
    if musb is not None:
        sources[92] = musb
        sources[93] = SimpleNamespace(irq_pending=musb.dma_irq_pending)
    intc = OmapIntc(sources) if timer_irq else ResetBank(0x10, 0x14)
    devices = {UART3_BASE: ('UART3', uart), 0x4806a000: ('UART1', uart1), 0x4806c000: ('UART2', DebugUart()),
               0x20000000: ('ISP1582', DisconnectedIsp1582()),
               0x18000000: ('QUART probe', RegisterBank()),
               0x18200000: ('DUART A', ExternalUart()), 0x18400000: ('DUART B', ExternalUart()),
               0x48002000: ('SCM', PadControl()),
               0x48004000: ('CM', ClockManager()), 0x48306000: ('PRM', PowerRegisters()),
               0x48200000: ('INTC', intc), 0x48318000: ('GPTIMER1', timer),
               0x49036000: ('GPTIMER4', GpTimer(timer_clock)),
               0x48320000: ('SYNCTIMER32K', SyncTimer(timer_clock)), 0x48056000: ('SDMA', dma or RegisterBank()),
               0x48094000: ('Mailbox', ResetBank(0x10, 0x14)),
               0x48098000: ('McSPI1', spi),
               0x4809a000: ('McSPI2', spi2),
               0x480b8000: ('McSPI3', EmptyMcSpi()),
               0x480ab000: ('MUSB OTG', musb if musb is not None else DisconnectedMusb()),
               0x50000000: ('SGX530 registers', SgxRegisters()),
               0x5d000000: ('IVA2 MMU', ResetBank(0x10, 0x14)),
               0x6c000000: ('SMS', RegisterBank()), 0x6d000000: ('SDRC', RegisterBank()),
               0x6e000000: ('GPMC', ResetBank(0x10, 0x14))}
    for index, (irq, base) in enumerate(zip(i2c, (0x48070000, 0x48072000, 0x48060000)), 1):
        devices[base] = (f'I2C{index}', i2c[irq])
    for index, base in enumerate((0x48310000, 0x49050000, 0x49052000, 0x49054000, 0x49056000, 0x49058000), 1):
        devices[base] = (f'GPIO{index}', touch.gpio if touch is not None and index == 4 else RegisterBank())
    for index, base in enumerate((0x48074000, 0x49022000, 0x49024000, 0x49026000, 0x48096000), 1):
        devices[base] = (f'McBSP{index} registers', RegisterBank())
    if empty_mmc or card is not None:
        for index, base in enumerate(MMC_BASES, 1):
            devices[base] = (f'HSMMC{index}', card if card is not None and index == slot else EmptyHsMmc())
    return devices
