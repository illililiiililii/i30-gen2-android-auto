"""Run the GD13MY ARM USB client against a selected physical USB port at the CE API boundary."""

import argparse
import json
from pathlib import Path
import struct
import sys
from time import monotonic, sleep

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from emulate_ce_usb import UsbClient
from i30_receiver.cli import libusb_path
from i30_receiver.transport import Disconnected, InterfaceNotReady, Timeout, TransportError
from i30_receiver.usb_pc import PyUsb

SAMSUNG = (0x04e8, 0x6860)
ACCESSORIES = {(0x18d1, 0x2d00), (0x18d1, 0x2d01)}
DEFAULT_DLL = Path(__file__).resolve().parents[1] / 'build/ce-aa-usb-v6/i30usb.dll'


def identity(device):
    return device.vendor, device.product


class LiveUsbClient(UsbClient):
    timeout_us = 5_000_000

    def __init__(self, dll, backend, device, configuration, link=None):
        super().__init__(dll, 'version' if link else 'switch')
        self.backend, self.phone, self.link = backend, device, link
        self.transfer_error = None
        self.wire_reads = []
        self.started = monotonic()
        raw = backend.get_device(device)
        desc = bytearray(18)
        desc[:2] = bytes((18, 1))
        desc[4] = raw.bDeviceClass
        struct.pack_into('<HH', desc, 8, device.vendor, device.product)
        interfaces = list(configuration)
        if not 1 <= len(interfaces) <= 32:
            raise TransportError('The active USB configuration exceeds the .061 interface limit')
        selected = 0
        endpoints = []
        if link is not None:
            selected = next((i for i, item in enumerate(interfaces)
                             if (item.bInterfaceNumber, item.bAlternateSetting) == (0, 0)), None)
            if selected is None:
                raise TransportError('Accessory interface 0 is missing')
            endpoints = [struct.pack('<BBBBHB', 7, 5, item.bEndpointAddress, item.bmAttributes,
                                     item.wMaxPacketSize, item.bInterval) for item in interfaces[selected]]
            if len(endpoints) != 2:
                raise TransportError('The .061 USB client requires two accessory endpoints')
        records = [bytes((9, 4, item.bInterfaceNumber, item.bAlternateSetting, item.bNumEndpoints,
                          item.bInterfaceClass, item.bInterfaceSubClass, item.bInterfaceProtocol, 0))
                   for item in interfaces]
        self.load_descriptors(desc, records, selected, endpoints)

    def GetTickCount(self, *_):
        return int((monotonic() - self.started) * 1000)

    def io_timeout(self, limit):
        remaining = 3000 - self.GetTickCount()
        if remaining <= 0:
            raise Timeout('The .061 driver USB deadline elapsed')
        return min(limit, remaining)

    def vendor(self, device, callback, context, flags, setup, buffer, physical):
        request_type, code, value, index, size = struct.unpack('<BBHHH', self.cpu.mem_read(setup, 8))
        if self.link is not None or device != 123 or any((callback, context, physical, value)):
            raise ValueError('Unexpected ARM vendor transfer arguments')
        self.vendor_calls.append(code)
        try:
            timeout = self.io_timeout(1000)
            if (request_type, code, index, size, flags) == (0xc0, 51, 0, 2, 0x180):
                data = self.backend.control_in(self.phone, code, size, timeout)
                if len(data) > size:
                    raise TransportError('AOA protocol response exceeded the buffer')
                self.cpu.mem_write(buffer, data)
                return self.issue(len(data))
            if request_type == 0x40 and flags == 0x100:
                if code == 52 and 0 <= index < 4 and 0 < size <= 255:
                    data = bytes(self.cpu.mem_read(buffer, size))
                    self.backend.control_out(self.phone, code, index, data, timeout)
                    return self.issue(size)
                if (code, index, size, buffer) == (53, 0, 0, 0):
                    try:
                        self.backend.control_out(self.phone, code, index, b'', timeout)
                    except Disconnected:
                        pass
                    return self.issue(0)
            raise ValueError('Unexpected ARM AOA request')
        except TransportError as error:
            self.transfer_error = f'AOA request {code}: {error}'
            return 0

    def bulk(self, pipe, callback, context, flags, size, buffer, physical):
        if self.link is None or any((callback, context, physical)) or not 0 < size <= 16:
            raise ValueError('Unexpected ARM bulk transfer arguments')
        try:
            timeout = self.io_timeout(3000)
            if (pipe, flags) == (self.link.input_endpoint, 0x180):
                data = self.link.read(timeout, size=size)
                if len(data) > size:
                    raise TransportError('Bulk input exceeded the ARM buffer')
                self.wire_reads.append(data.hex())
                self.cpu.mem_write(buffer, data)
                return self.issue(len(data))
            if (pipe, flags) == (self.link.output_endpoint, 0x100):
                data = bytes(self.cpu.mem_read(buffer, size))
                self.link.write(data, timeout)
                self.wire_writes.append(data.hex())
                return self.issue(size)
            raise ValueError('Unexpected ARM accessory endpoint')
        except TransportError as error:
            self.transfer_error = f'Bulk endpoint {pipe:#x}: {error}'
            return 0


def attach(backend, device, dll, log):
    raw = backend.get_device(device)
    link = None
    try:
        if identity(device) == SAMSUNG:
            backend.control(device)
        else:
            link = backend.open_accessory(device)
        config = backend.active_configuration(raw)
        client = LiveUsbClient(dll, backend, device, config, link)
        result = client.attach()
        log('arm_usb_attach', **result, version_response_packets=client.wire_reads,
            transfer_error=client.transfer_error)
        if client.transfer_error:
            raise TransportError(client.transfer_error)
        return result
    finally:
        if link is not None:
            link.close()
        else:
            backend.release_control(device)


def run_probe(backend, port, dll, log):
    def on_port():
        matches = [item for item in backend.devices() if item.port == port]
        if len(matches) > 1:
            raise TransportError('Physical USB port is ambiguous')
        return matches[0] if matches else None

    device = on_port()
    if device is None:
        raise TransportError('No device on the selected physical USB port')
    if device.mass_storage or identity(device) not in ({SAMSUNG} | ACCESSORIES):
        raise TransportError('Device is outside the .061 Android Auto test allowlist')
    log('windows_usb_enumerated', port=port, vid=f'{device.vendor:04x}', pid=f'{device.product:04x}')
    log('opening_windows_usb')
    result = attach(backend, device, dll, log)
    if identity(device) == SAMSUNG:
        if 'Switch' not in result['signals'] or not result['accepted']:
            raise TransportError('The ARM driver did not start the AOA switch')
        deadline = monotonic() + 8
        last_error = None
        while monotonic() < deadline:
            device = on_port()
            if device is not None and identity(device) in ACCESSORIES and not device.mass_storage:
                if last_error is None:
                    log('aoa_reenumerated', port=port, pid=f'{device.product:04x}')
                try:
                    result = attach(backend, device, dll, log)
                except (Disconnected, InterfaceNotReady) as exc:
                    last_error = exc
                else:
                    break
            elif device is not None and identity(device) != SAMSUNG:
                raise TransportError('A different USB device appeared on the selected port')
            sleep(0.1)
        else:
            if last_error is not None:
                raise Timeout('Accessory reenumerated, but its data interface did not become ready') from last_error
            raise Timeout('The phone did not reenumerate as an AOA accessory')
    if not result['accepted'] or 'Ready' not in result['signals']:
        raise TransportError('The ARM driver did not receive a valid plain Android Auto version response')
    log('arm_aa_version_verified', projection=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--list', action='store_true', help='List supported device IDs and ports without opening them')
    modes.add_argument('--device', metavar='BUS-PORT', help='Run AOA and the version exchange on this port')
    parser.add_argument('--libusb', type=Path, default=libusb_path())
    parser.add_argument('--dll', type=Path, default=DEFAULT_DLL)
    args = parser.parse_args()

    def log(event, **fields):
        print(json.dumps({'event': event, **fields}), flush=True)

    try:
        backend = PyUsb(args.libusb)
        if args.list:
            for row in backend.devices():
                if identity(row) in ({SAMSUNG} | ACCESSORIES):
                    log('windows_usb_enumerated', port=row.port, vid=f'{row.vendor:04x}', pid=f'{row.product:04x}')
        else:
            if not args.dll.is_file():
                raise ValueError(f'Build the ARM CE client first: {args.dll}')
            run_probe(backend, args.device, args.dll, log)
        return 0
    except (TransportError, ValueError, OSError) as error:
        log('probe_failed', message=str(error), projection=False)
        return 1


if __name__ == '__main__':
    sys.exit(main())
