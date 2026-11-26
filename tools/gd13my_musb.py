"""OMAP MUSB host-mode port for a single selected USB device."""

from dataclasses import dataclass, field
import struct

from gd13my_mmio import ResetBank

POWER, INTRTX, INTRRX, TX_ENABLE, RX_ENABLE, INTRUSB, USB_ENABLE = 1, 2, 4, 6, 8, 10, 11
INDEX, DEVCTL = 0x0e, 0x60
CONNECT, DISCONNECT = 0x10, 0x20
SESSION, HOST_MODE, VBUS_VALID, FULL_SPEED = 0x01, 0x04, 0x18, 0x40
RX_READY, EP0_TX_READY, EP0_SETUP, REQUEST, EP0_STATUS, EP0_FLUSH = 1, 2, 8, 0x20, 0x40, 0x100
DMA_INTR, DMA_CONTROL, DMA_STRIDE, DMA_CHANNELS = 0x200, 0x204, 0x10, 8
DMA_ENABLE, DMA_TRANSMIT, DMA_MODE1, DMA_IRQ_ENABLE, DMA_BUS_ERROR = 1, 2, 4, 8, 0x100
TX_FIFO_NOT_EMPTY, RX_AUTO_REQUEST, RX_AUTO_CLEAR = 2, 0x4000, 0x8000


class UsbTransferError(Exception):
    """The backend could not complete a guest USB request."""


class UsbTransferPending(Exception):
    """The device has not answered a bulk IN token yet."""


@dataclass
class Endpoint:
    regs: bytearray = field(default_factory=lambda: bytearray(16))
    output: bytearray = field(default_factory=bytearray)
    input: bytearray = field(default_factory=bytearray)
    fifo_config: bytearray = field(default_factory=lambda: bytearray(6))

    def read(self, offset, size=2):
        return int.from_bytes(self.regs[offset:offset + size], 'little')

    def write(self, offset, value, size=2):
        self.regs[offset:offset + size] = value.to_bytes(size, 'little')


class HostMusb(ResetBank):
    def __init__(self, transport):
        super().__init__(0x404, 0x408)
        self.transport = transport
        self.connected = False
        self.high_speed = False
        self.endpoints = [Endpoint() for _ in range(16)]
        self.setup = None
        self.control_data = bytearray()
        self.pending_reads = set()
        self.dma_memory = None

    def interrupt(self, reg, bits):
        size = 1 if reg == INTRUSB else 2
        super().write(reg, size, super().read(reg, size) | bits)

    def irq_pending(self):
        read = super().read
        return any(read(status, size) & read(enable, size)
                   for status, enable, size in ((INTRTX, TX_ENABLE, 2), (INTRRX, RX_ENABLE, 2),
                                                (INTRUSB, USB_ENABLE, 1)))

    def dma_irq_pending(self):
        return bool(self.data[DMA_INTR])

    def set_cable(self, connected, high_speed=False):
        if self.connected == connected:
            return
        self.connected, self.high_speed = connected, high_speed
        self.setup = None
        self.control_data.clear()
        self.pending_reads.clear()
        for endpoint in self.endpoints:
            endpoint.input.clear()
            endpoint.output.clear()
            for reg in (2, 6, 8):
                endpoint.write(reg, 0)
        if not connected:
            super().write(INTRTX, 2, 0)
            super().write(INTRRX, 2, 0)
            self.data[DMA_INTR:DMA_INTR + DMA_STRIDE * DMA_CHANNELS] = bytes(DMA_STRIDE * DMA_CHANNELS)
        if self.data[DEVCTL] & SESSION:
            self.interrupt(INTRUSB, CONNECT if connected else DISCONNECT)

    def endpoint_offset(self, offset):
        if 0x10 <= offset < 0x20:
            return self.data[INDEX] & 15, offset - 0x10
        if 0x100 <= offset < 0x200:
            return divmod(offset - 0x100, 16)
        return None

    def read(self, offset, size):
        if 0x20 <= offset < 0x60:
            endpoint = self.endpoints[(offset - 0x20) // 4]
            data = endpoint.input[:size]
            del endpoint.input[:size]
            if (not endpoint.input and offset >= 0x24 and endpoint.read(6) & RX_AUTO_CLEAR and
                    endpoint.read(8) == (endpoint.read(4) & 0x7ff)):
                endpoint.write(6, endpoint.read(6) & ~RX_READY)
            return int.from_bytes(data, 'little')
        if offset == DEVCTL and size == 1:
            # The dedicated host port keeps ID grounded when the downstream cable is removed.
            role = (HOST_MODE | VBUS_VALID) if self.data[DEVCTL] & SESSION else 0
            if role and self.connected and not self.high_speed:
                role |= FULL_SPEED
            return (self.data[offset] & 3) | role
        if offset == POWER and size == 1:
            return self.data[POWER] | (0x10 if self.connected and self.high_speed else 0)
        if 0x62 <= offset and offset + size <= 0x68:
            endpoint = self.endpoints[self.data[INDEX] & 15]
            return int.from_bytes(endpoint.fifo_config[offset - 0x62:offset - 0x62 + size], 'little')
        address = self.endpoint_offset(offset)
        if address is not None:
            number, reg = address
            if reg == 15 and size == 1:
                return 0x05 if number == 0 else 0x99
            return self.endpoints[number].read(reg, size)
        if offset == 0x78 and size == 1:
            return 0xff  # Fifteen TX and RX endpoints plus EP0.
        if offset == 0x79 and size == 1:
            return 12
        value = super().read(offset, size)
        for status, count in ((INTRTX, 2), (INTRRX, 2), (INTRUSB, 1), (DMA_INTR, 1)):
            for byte in range(max(offset, status), min(offset + size, status + count)):
                self.data[byte] = 0
        return value

    def write(self, offset, size, value):
        if 0x20 <= offset < 0x60:
            endpoint = self.endpoints[(offset - 0x20) // 4]
            endpoint.output.extend(value.to_bytes(size, 'little'))
            return
        if offset == DEVCTL and size == 1:
            if self.connected and value & SESSION and not self.data[offset] & SESSION:
                self.interrupt(INTRUSB, CONNECT)
            super().write(offset, size, value & 3)
            return
        if offset == POWER and size == 1:
            if self.data[POWER] & 8 and not value & 8:
                self.transport.reset()
            super().write(offset, size, value & ~0x10)
            return
        if 0x62 <= offset and offset + size <= 0x68:
            endpoint = self.endpoints[self.data[INDEX] & 15]
            endpoint.fifo_config[offset - 0x62:offset - 0x62 + size] = value.to_bytes(size, 'little')
            return
        if offset == 0x76 and size == 1 and value & 1:
            super().write(offset, size, value & ~1 | 2)  # Complete the ULPI register handshake.
            return
        address = self.endpoint_offset(offset)
        if address is not None:
            number, reg = address
            endpoint = self.endpoints[number]
            endpoint.write(reg, value, size)
            if reg in (2, 3) and number == 0:
                self.control(endpoint)
            elif reg in (2, 3, 6, 7) and number:
                self.bulk(endpoint, number, reg < 6)
            return
        super().write(offset, size, value)
        if DMA_CONTROL <= offset < DMA_CONTROL + DMA_STRIDE * DMA_CHANNELS:
            channel, reg = divmod(offset - DMA_CONTROL, DMA_STRIDE)
            if reg < 2 and self.data[DMA_CONTROL + DMA_STRIDE * channel] & DMA_ENABLE:
                self.service_dma(channel)
        if offset == self.reset and value & 2:
            self.endpoints = [Endpoint() for _ in range(16)]
            self.setup = None
            self.control_data.clear()
            self.pending_reads.clear()

    def retry_bulk_reads(self):
        pending = self.pending_reads.copy()
        for number in pending:
            if number in self.pending_reads:
                self.bulk(self.endpoints[number], number, out=False)
        return bool(pending - self.pending_reads)

    def service_dma(self, channel):
        reg = DMA_CONTROL + DMA_STRIDE * channel
        control = super().read(reg, 2)
        address, count = super().read(reg + 4, 4), super().read(reg + 8, 4)
        number = (control >> 4) & 15
        out = bool(control & DMA_TRANSMIT)
        endpoint = self.endpoints[number]
        csr = endpoint.read(2 if out else 6)
        packet_size = endpoint.read(0 if out else 4) & 0x7ff
        # WinCE can start mode-zero DMA for a USB zero-length receive packet.
        empty_packet = not out and not count and csr & RX_READY and endpoint.read(8) == 0
        fault = (not self.connected or not number or bool(control & DMA_MODE1) or self.dma_memory is None or
                 (not 0 < count <= packet_size and not empty_packet) or address & 3)
        if not fault and not empty_packet:
            contains, read, write = self.dma_memory
            fault = not contains(address, count)
        if fault:
            control |= DMA_BUS_ERROR
        elif out:
            # In DMA mode 0 the driver sets TXPKTRDY after the FIFO is filled.
            endpoint.output.extend(read(address, count))
            endpoint.write(2, csr | TX_FIFO_NOT_EMPTY)
            address, count = address + count, 0
        elif csr & RX_READY:
            data = endpoint.input[:count]
            del endpoint.input[:len(data)]
            if data:
                write(address, bytes(data))
            address, count = address + len(data), count - len(data)
            if not endpoint.input:
                received = endpoint.read(8)
                if received < packet_size:
                    csr &= ~(RX_AUTO_REQUEST | REQUEST)
                # DMA unloads words. A short packet outside the final word needs a software ACK.
                if csr & RX_AUTO_CLEAR and (received + 3) // 4 == (packet_size + 3) // 4:
                    csr &= ~RX_READY
                endpoint.write(6, csr)
        else:
            return
        super().write(reg, 2, control & ~DMA_ENABLE)
        super().write(reg + 4, 4, address)
        super().write(reg + 8, 4, count)
        if control & DMA_IRQ_ENABLE:
            super().write(DMA_INTR, 1, self.data[DMA_INTR] | (1 << channel))

    def control(self, endpoint):
        flags = endpoint.read(2)
        if flags & EP0_FLUSH:
            endpoint.input.clear()
            endpoint.output.clear()
            endpoint.write(2, flags & ~(EP0_FLUSH | RX_READY | EP0_TX_READY))
            return
        if not flags & (REQUEST | EP0_TX_READY):
            return
        result = flags & 0x0e00
        try:
            if not self.connected:
                raise UsbTransferError('USB device is disconnected')
            if flags & EP0_SETUP and flags & EP0_TX_READY:
                if len(endpoint.output) != 8:
                    raise UsbTransferError('Invalid USB setup packet size')
                self.setup = struct.unpack('<BBHHH', endpoint.output)
                endpoint.output.clear()
                endpoint.input.clear()
                self.control_data.clear()
                if self.setup[0] & 0x80 or self.setup[4] == 0:
                    self.control_data.extend(self.transport.control(self.setup, b''))
            elif flags & EP0_STATUS:
                endpoint.output.clear()
                endpoint.input.clear()
                endpoint.write(8, 0)
                if flags & REQUEST:
                    result |= RX_READY
                self.setup = None
            elif flags & REQUEST and self.setup is not None:
                size = self.transport.control_packet_size
                endpoint.input[:] = self.control_data[:size]
                del self.control_data[:size]
                endpoint.write(8, len(endpoint.input))
                result |= RX_READY
            elif flags & EP0_TX_READY and self.setup is not None:
                self.control_data.extend(endpoint.output)
                endpoint.output.clear()
                if len(self.control_data) >= self.setup[4]:
                    self.transport.control(self.setup, bytes(self.control_data))
                    self.control_data.clear()
            else:
                raise UsbTransferError('USB control transfer has no setup stage')
        except UsbTransferError:
            result |= 0x10  # Host ERROR.
        endpoint.write(2, result)
        self.interrupt(INTRTX, 1)

    def bulk(self, endpoint, number, out):
        reg, packet, flush = (2, 1, 8) if out else (6, REQUEST, 16)
        if not out:
            self.pending_reads.discard(number)
        flags = endpoint.read(reg)
        if flags & flush:
            (endpoint.output if out else endpoint.input).clear()
            endpoint.write(reg, flags & ~(flush | packet | RX_READY))
            return
        if not flags & packet:
            return
        result = flags & ~packet
        try:
            target_type = endpoint.read(10 if out else 12, 1)
            if not self.connected or (target_type >> 4) & 3 != 2 or not target_type & 15:
                raise UsbTransferError('This host model supports connected bulk endpoints')
            address = (target_type & 15) | (0 if out else 0x80)
            if out:
                self.transport.write(address, bytes(endpoint.output))
                endpoint.output.clear()
                result &= ~TX_FIFO_NOT_EMPTY
            else:
                size = endpoint.read(4) & 0x7ff
                endpoint.input[:] = self.transport.read(address, size)
                endpoint.write(8, len(endpoint.input))
                if len(endpoint.input) < size:
                    result &= ~RX_AUTO_REQUEST
                result |= RX_READY
        except UsbTransferPending:
            self.pending_reads.add(number)
            return  # Preserve REQPKT and wait for data or cancellation by the guest.
        except UsbTransferError:
            result |= 4  # Host ERROR.
            endpoint.output.clear()
        endpoint.write(reg, result)
        self.interrupt(INTRTX if out else INTRRX, 1 << number)
        if not out and result & RX_READY:
            for channel in range(DMA_CHANNELS):
                control = super().read(DMA_CONTROL + DMA_STRIDE * channel, 2)
                if control & DMA_ENABLE and not control & DMA_TRANSMIT and (control >> 4) & 15 == number:
                    self.service_dma(channel)
