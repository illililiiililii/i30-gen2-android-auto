"""Back the .061 emulated MUSB port with a selected physical Android phone."""

from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path
from struct import unpack_from
import sys
from time import monotonic

from gd13my_musb import HostMusb, UsbTransferError, UsbTransferPending

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from i30_receiver.cli import libusb_path
from i30_receiver.transport import Disconnected, Timeout, TransportError
from i30_receiver.usb_pc import PyUsb


PHONE_IDS = {(0x04e8, 0x6860), (0x18d1, 0x2d00), (0x18d1, 0x2d01)}
VERSION_REQUEST = bytes.fromhex('00030006000100010006')
VERSION_PREFIX = b'\x00\x03\x00\x08\x00\x02'


class PhonePort:
    def __init__(self, port, library, status, trace=None, *, wait_for_test=False):
        self.requested_port = port
        self.port = port
        try:
            self.backend = PyUsb(library or libusb_path())
        except TransportError as error:
            raise ValueError(str(error)) from error
        self.status = status
        self.trace = trace or status
        self.last_status = None
        self.device = self.raw = self.link = None
        self.config = 0
        self.version_input = None
        self.version_packet = None
        self.control_packet_size = 64
        self.next_poll = float('inf') if wait_for_test else 0
        self.next_bulk_retry = 0
        self.bulk_reader = None
        self.bulk_input = None
        self.controller = HostMusb(self)
        if wait_for_test:
            self.notify(f'물리 USB {self.port} · CE 시험 시작 대기')

    def notify(self, text):
        if text != self.last_status:
            self.status(text)
            self.last_status = text

    def reset(self):
        pending, self.bulk_input = self.bulk_input, None
        if pending is not None and not pending.cancel():
            wait((pending,))
        self.config = 0
        self.version_input = self.version_packet = None

    def close_device(self):
        self.reset()
        if self.bulk_reader is not None:
            self.bulk_reader.shutdown()
            self.bulk_reader = None
        if self.link is not None:
            self.link.close()
        if self.raw is not None and (self.link is None or self.raw is not self.link.device):
            self.backend.dispose(self.raw)
        self.device = self.raw = self.link = None
        self.controller.set_cable(False)

    def reconnect(self):
        self.close_device()
        self.port = self.requested_port
        self.next_poll = monotonic() + 0.75
        self.notify(f'물리 USB {self.port} · 가상 포트 다시 연결 중')

    def take_projection_link(self):
        """Give the already-open handle to the receiver once CE releases its pipes."""
        if self.link is None or self.version_packet is None:
            return None
        claimed = self.link, self.version_packet
        self.device = self.raw = self.link = None
        self.reset()
        self.controller.set_cable(False)
        self.next_poll = float('inf')
        return claimed

    def poll(self):
        now = monotonic()
        if now < self.next_poll:
            if self.controller.pending_reads and now >= self.next_bulk_retry:
                self.next_bulk_retry = now + 0.005
                return self.controller.retry_bulk_reads()
            return False
        self.next_poll = now + 0.25
        try:
            devices = self.backend.devices()
            if self.port == 'auto':
                matches = [item for item in devices if item.port and
                           (item.vendor, item.product) in PHONE_IDS and not item.mass_storage]
                if len(matches) > 1:
                    self.notify('호환 폰이 여러 대입니다. 실행 시 -UsbPort로 포트를 지정하세요.')
                    return False
            else:
                matches = [item for item in devices if item.port == self.port]
            candidate = matches[0] if len(matches) == 1 else None
            if self.device is not None and candidate != self.device:
                self.close_device()
                self.next_poll = now + 0.75
                self.notify('기기 분리 · USB 재열거 대기')
                return True
            if candidate is None:
                self.notify(f'물리 USB {self.port} 연결 대기')
                return False
            if candidate == self.device:
                return False
            if (candidate.vendor, candidate.product) not in PHONE_IDS or candidate.mass_storage:
                self.notify(f'USB {self.port} · 지원 대상 외 기기')
                return False
            raw = self.backend.get_device(candidate)
            try:
                config = self.backend.active_configuration(raw)
                if any(item.bInterfaceClass == 8 for item in config):
                    raise TransportError('USB mass storage interface is present')
                if raw.speed is not None and raw.speed > 3:
                    raise TransportError('The selected device requires a USB 2.0 link for this host model')
            except TransportError:
                self.backend.dispose(raw)
                raise
            packet_size = raw.bMaxPacketSize0
            if packet_size not in (8, 16, 32, 64):
                self.backend.dispose(raw)
                raise TransportError('Unsupported endpoint zero packet size')
            # A newly enumerated accessory can still be waiting for WinUSB.
            # Keep the guest disconnected until the data interface is usable.
            link = self.backend.open_accessory(candidate, raw=raw) if candidate.accessory else None
            self.device, self.raw, self.link = candidate, raw, link
            self.port = candidate.port
            self.active_config = config.bConfigurationValue
            self.control_packet_size = packet_size
            self.controller.set_cable(True, raw.speed == 3)
            self.notify(f'물리 USB {self.port} · {candidate.vendor:04x}:{candidate.product:04x} 가상 포트 연결')
            return True
        except TransportError as error:
            self.notify(f'Windows USB 접근 실패 · {error}')
            return False

    def exchange(self, label, function, *args, **kwargs):
        try:
            return self.backend.invoke(function, *args, **kwargs)
        except TransportError as error:
            self.transfer_failed(label, error)

    def transfer_failed(self, label, error, pending_on_timeout=False):
        if isinstance(error, Disconnected):
            self.close_device()
            self.next_poll = monotonic() + 0.75
            self.notify('물리 USB 재열거 대기')
        elif pending_on_timeout and isinstance(error, Timeout):
            raise UsbTransferPending from error
        else:
            self.notify(f'{label} 실패 · {error}')
        raise UsbTransferError(str(error)) from error

    def control(self, setup, data):
        kind, request, value, index, length = setup
        if self.raw is None or (not kind & 0x80 and len(data) != length):
            raise UsbTransferError('Invalid USB control payload')
        if (kind, request, index, length) == (0, 5, 0, 0) and value <= 127:
            self.trace(f'WinCE USB SET_ADDRESS {value}')
            return b''  # The guest USB address belongs to the emulated bus.
        if (kind, request, index, length) == (0x80, 8, 0, 1):
            return bytes((self.config,))
        if (kind, request, index, length) == (0, 9, 0, 0):
            if value not in (0, self.active_config):
                raise UsbTransferError('The requested configuration is not active on Windows')
            self.config = value
            self.trace(f'WinCE USB SET_CONFIGURATION {value}')
            return b''
        try:
            label = f'USB 제어 요청 {kind:02x}/{request:02x}/{value:04x}/{index:04x}'
            result = self.exchange(label, self.raw.ctrl_transfer, kind, request, value, index,
                                   length if kind & 0x80 else data, timeout=750)
        except UsbTransferError:
            if (kind, request, value, index, length) == (0x40, 53, 0, 0, 0) and self.device is None:
                self.trace('WinCE AOA START · USB 재열거 시작')
                return b''  # A phone can change modes before returning the control status.
            raise
        if kind & 0x80:
            data = bytes(result)
            if kind == 0x80 and request == 6 and value >> 8 in (1, 2):
                self.trace(f'WinCE USB GET_DESCRIPTOR {value >> 8} · {len(data)}바이트')
            if (kind, request, value, index, length) == (0xc0, 51, 0, 0, 2) and len(data) == 2:
                self.notify(f'WinCE에서 실폰 AOA {int.from_bytes(data, "little")} 응답 수신')
            return data
        if result != length:
            raise UsbTransferError('Short USB control write')
        if kind == 0x40 and request in (52, 53):
            self.trace(f'WinCE AOA 요청 {request} · 설정 번호 {index} · {length}바이트')
        return b''

    def accessory_link(self):
        if self.device is None or not self.config or not self.device.accessory:
            raise UsbTransferError('The guest has not configured the accessory interface')
        if self.link is None:
            try:
                # Polling replaces inventory objects. WinUSB can deny another handle to the same interface.
                self.link = self.backend.open_accessory(self.device, raw=self.raw)
            except TransportError as error:
                self.notify(f'USB bulk 인터페이스 열기 실패 · {error}')
                raise UsbTransferError(str(error)) from error
        return self.link

    def write(self, address, data):
        link = self.accessory_link()
        if address != link.output_endpoint:
            raise UsbTransferError('Unknown accessory output endpoint')
        written = self.exchange('USB bulk 출력', link.device.write, address, data, timeout=500)
        if written != len(data):
            raise UsbTransferError('Short USB bulk write')
        if data == VERSION_REQUEST:
            self.version_input = bytearray()
            self.version_packet = None
            self.trace(f'WinCE Android Auto 버전 요청 · 엔드포인트 {address:#04x}')

    def read(self, address, size):
        link = self.accessory_link()
        if address != link.input_endpoint or not 0 < size <= 512:
            raise UsbTransferError('Unknown accessory input endpoint or packet size')
        data = self.read_bulk_packet(link, address, size)
        if self.version_input is not None:
            self.version_input.extend(data)
            if len(self.version_input) >= 12:
                packet = bytes(self.version_input)
                self.version_input = None
                if len(packet) == 12 and packet.startswith(VERSION_PREFIX):
                    major, minor, status = unpack_from('>HHh', packet, 6)
                    if major == 1 and minor >= 6 and status == 0:
                        self.version_packet = packet
                        self.notify(f'WinCE에서 실폰 Android Auto 버전 응답 수신 · {packet.hex()}')
        return data

    def read_bulk_packet(self, link, address, size):
        # Keep CE timers and IRQs running while WinUSB waits for the phone to send data.
        if self.bulk_input is None:
            if self.bulk_reader is None:
                self.bulk_reader = ThreadPoolExecutor(max_workers=1, thread_name_prefix='gd13my-usb-in')
            self.bulk_input = self.bulk_reader.submit(self.backend.invoke, link.device.read, address, size, timeout=15)
        if not self.bulk_input.done():
            raise UsbTransferPending
        pending, self.bulk_input = self.bulk_input, None
        try:
            return bytes(pending.result())
        except TransportError as error:
            self.transfer_failed('USB bulk 입력', error, pending_on_timeout=True)
