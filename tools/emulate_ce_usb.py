"""Execute the built ARM CE USB client and menu component with WinCE API doubles."""

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import ssl
import struct
import subprocess
import sys
from time import time

import pefile
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM, Uc
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP


STUB = 0x70000000
RAM = 0x20000000
MARK = STUB + 0xff0
STACK = RAM + 0xf000
FORMAT = Path(__file__).resolve().parent.parent / 'research/evidence/phase1-rom.json'


class Machine:
    timeout_us = 2_000_000
    instruction_limit = 200_000

    def __init__(self, path, base=None):
        self.pe = pefile.PE(data=path.read_bytes())
        self.base = base if base is not None else self.pe.OPTIONAL_HEADER.ImageBase
        image = self.pe.get_memory_mapped_image(ImageBase=self.base)
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.cpu.mem_map(self.base, (len(image) + 0xfff) & ~0xfff)
        self.cpu.mem_write(self.base, image)
        self.cpu.mem_map(STUB, 0x1000)
        self.cpu.mem_map(RAM, 0x10000)
        self.cpu.hook_add(UC_HOOK_CODE, self.dispatch, begin=STUB, end=MARK - 4)
        self.hooks = {}
        self.calls = Counter()
        rom = json.loads(FORMAT.read_text(encoding='utf-8'))['modules']['coredll.dll']['exports']
        names = {e['ordinal']: e['name'] for e in rom}
        for entry in self.pe.DIRECTORY_ENTRY_IMPORT[0].imports:
            # pefile applies image relocation after materializing imported symbol metadata.
            rva = entry.address - self.pe.OPTIONAL_HEADER.ImageBase
            self.put(self.base + rva, self.hook(names[entry.ordinal]))

    def word(self, p):
        return struct.unpack('<I', self.cpu.mem_read(p, 4))[0]

    def put(self, p, v):
        self.cpu.mem_write(p, struct.pack('<I', v & 0xffffffff))

    def text(self, p):
        chars = []
        for _ in range(500):
            unit = bytes(self.cpu.mem_read(p, 2))
            if unit == bytes(2):
                return b''.join(chars).decode('utf-16-le')
            chars.append(unit)
            p += 2
        raise ValueError('Unterminated CE string')

    def hook(self, name):
        address = STUB + len(self.hooks) * 4
        self.hooks[address] = name
        return address

    def dispatch(self, cpu, address, _size, _data):
        name = self.hooks[address]
        self.calls[name] += 1
        sp = cpu.reg_read(UC_ARM_REG_SP)
        args = [cpu.reg_read(UC_ARM_REG_R0 + i) for i in range(4)] + [
            self.word(sp + i * 4) for i in range(5 if name == 'RegCreateKeyExW' else 3)]
        result = getattr(self, name)(*args)
        if result is not None:
            cpu.reg_write(UC_ARM_REG_R0, result & 0xffffffff)
            cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    def run(self, rva, args=()):
        self.cpu.reg_write(UC_ARM_REG_LR, MARK)
        self.cpu.reg_write(UC_ARM_REG_SP, STACK)
        for i, arg in enumerate(args):
            if i < 4:
                self.cpu.reg_write(UC_ARM_REG_R0 + i, arg)
            else:
                self.put(STACK + 4 * (i - 4), arg)
        self.cpu.emu_start(self.base + rva, MARK, timeout=self.timeout_us, count=self.instruction_limit)
        if self.cpu.reg_read(UC_ARM_REG_PC) != MARK:
            raise ValueError('ARM test input did not finish')
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def CloseHandle(self, *unused):
        return 1


class UsbClient(Machine):
    def __init__(self, path, case):
        super().__init__(path, base=0x30000000)
        self.case = case
        self.ms = 0
        self.vendor_calls = []
        self.pipes = []
        self.signaled = []
        self.transfers = {}
        self.next_transfer = 0x80000
        self.wire_writes = []
        self.debug = []
        self.kind = 'mtp' if case in ('switch', 'storage', 'unsupported') else 'accessory'
        self.interfaces = RAM + 0x2000
        self.device = RAM + 0x400
        self.config = RAM + 0x440
        self.endpoint = RAM + 0x480
        self.attach_interface = self.interfaces
        self.events = {4: 'Ready', 5: 'Failure', 6: 'Switch'}
        self.table = RAM + 0x1000
        self.put(self.table, 0xac)
        for offset, name in ((0x34, 'info'), (0x38, 'vendor'), (0x5c, 'open_pipe'), (0x68, 'close_pipe'),
                             (0x74, 'bulk'), (0x80, 'complete'), (0x84, 'status'), (0x90, 'close_transfer')):
            self.put(self.table + offset, self.hook(name))
        vendor, product = (0x04e8, 0x6860) if self.kind == 'mtp' else (0x18d1, 0x2d00)
        desc = bytearray(18)
        desc[:2] = bytes((18, 1))
        struct.pack_into('<HH', desc, 8, vendor, product)
        cls = 8 if case == 'storage' else 6 if self.kind == 'mtp' else 0xff
        interface = bytes((9, 4, int(case == 'wrong-interface'), 0, 2, cls, 0, 0, 0))
        endpoints = [bytes((7, 5, suffix, 2, 0, 2, 0)) for suffix in (0x81, 0x01)]
        self.load_descriptors(desc, [interface], 0, endpoints)

    def load_descriptors(self, device, interfaces, selected, endpoints):
        assert 0 < len(interfaces) <= 32 and 0 <= selected < len(interfaces)
        self.put(self.device, 0x20)
        self.cpu.mem_write(self.device + 4, bytes(device))
        self.put(self.device + 0x1c, self.config)
        self.put(self.config, 0x20)
        self.put(self.config + 0x14, len(interfaces))
        self.put(self.config + 0x18, self.interfaces)
        for i, desc in enumerate(interfaces):
            address = self.interfaces + i * 0x1c
            self.put(address, 0x1c)
            self.cpu.mem_write(address + 4, bytes(desc))
            self.put(address + 0x14, self.endpoint if i == selected else 0)
        self.attach_interface = self.interfaces + selected * 0x1c
        for i, desc in enumerate(endpoints):
            addr = self.endpoint + i * 20
            self.put(addr, 20)
            self.cpu.mem_write(addr + 4, bytes(desc))

    def OpenEventW(self, access, inherit, name, *_):
        label = self.text(name).split('.')[-1]
        if label == 'Gate':
            return 0 if self.case == 'not-armed' else 3
        return next(k for k, value in self.events.items() if value == label)

    def CreateEventW(self, attrs, manual, initial, name, *_):
        assert not attrs and manual == 1 and not initial
        label = self.text(name).split('.')[-1]
        if label in ('Version', 'AuthRequired', 'VideoActive') and label not in self.events.values():
            self.event_error = 0  # The standalone driver fixture has no navigation listener.
            return 1
        self.event_error = 0 if label == 'Gate' and self.case == 'not-armed' else 183
        return 3 if label == 'Gate' else next(handle for handle, event in self.events.items() if event == label)

    def GetLastError(self, *_):
        return self.event_error

    def EventModify(self, handle, operation, *_):
        assert operation == 3
        self.signaled.append(self.events[handle])
        return 1

    def Sleep(self, ms, *_):
        self.ms += ms
        return 0

    def GetTickCount(self, *_):
        return self.ms

    def CreateFileW(self, *_):
        return -1  # No TLS identity is enrolled in the baseline USB tests.

    def OutputDebugStringW(self, message, *_):
        self.debug.append(self.text(message).strip())
        return 0

    def WaitForSingleObject(self, handle, milliseconds, *_):
        assert handle == 3 and not milliseconds
        return 258

    def info(self, *_):
        return self.device

    def issue(self, length):
        self.next_transfer += 4
        self.transfers[self.next_transfer] = length
        return self.next_transfer

    def vendor(self, device, callback, context, flag, setup, data, pa):
        kind, code, value, index, size = struct.unpack('<BBHHH', self.cpu.mem_read(setup, 8))
        assert not value and not pa and not callback and not context
        self.vendor_calls.append(code)
        if code == 51:
            assert (kind, flag, size) == (0xc0, 0x180, 2)
            self.cpu.mem_write(data, struct.pack('<H', 0 if self.case == 'unsupported' else 2))
        elif code == 52:
            assert (kind, flag) == (0x40, 0x100) and 0 <= index < 4
            text = bytes(self.cpu.mem_read(data, size))
            assert text == [b'i30 Research\0', b'Android Auto\0', b'i30 GD13MY USB test\0', b'1.0\0'][index]
        else:
            assert code == 53 and not size and not data
        return self.issue(size)

    def bulk(self, pipe, callback, context, flag, size, data, pa):
        assert not callback and not context and not pa
        if flag & 0x80:
            assert pipe == 0x81 and size == 12
            frame = bytes.fromhex('00 03 00 08 00 02 00 01 00 07 00 00')
            self.cpu.mem_write(data, frame)
        else:
            assert pipe == 1
            self.wire_writes.append(bytes(self.cpu.mem_read(data, size)).hex())
        return self.issue(size)

    def open_pipe(self, device, desc, *_):
        address = self.cpu.mem_read(desc + 2, 1)[0]
        if address == 1 and self.case == 'second-pipe-fails':
            return 0
        self.pipes.append(address)
        return address

    def close_pipe(self, pipe, *_):
        self.pipes.remove(pipe)
        return 1

    def complete(self, *_):
        return int(self.case != 'timeout')

    def status(self, transfer, length, error, *_):
        self.put(length, self.transfers[transfer])
        self.put(error, 0)
        return 1

    def close_transfer(self, transfer, *_):
        del self.transfers[transfer]
        return 1

    def attach(self):
        address = self.pe.DIRECTORY_ENTRY_EXPORT.symbols[0].address
        interface = self.attach_interface if self.kind == 'accessory' else 0
        result = self.run(address, (123, self.table, interface, 0, RAM, 0, 0))
        assert self.word(RAM) == result
        assert not self.transfers and not self.pipes
        return {'accepted': bool(result), 'controls': self.vendor_calls, 'inputs': self.wire_writes,
                'signals': self.signaled, 'wait_ms': self.ms, 'closed_transfers': self.calls['close_transfer'],
                'debug': self.debug}


class TlsUsbClient(UsbClient):
    timeout_us = 20_000_000
    instruction_limit = 160_000_000
    heap = 0x50000000

    def __init__(self, path, files, context, *, video=None, preempt=False, clock=None, silent=False,
                 video_deadline=False, handshake_reply=None):
        super().__init__(path, 'version')
        self.files = files
        self.positions = {}
        self.inbox, self.outbox = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.peer = context.wrap_bio(self.inbox, self.outbox, server_side=True)
        self.pending, self.received = bytearray(), bytearray()
        self.authenticated = False
        self.peer_error = None
        self.services = None
        self.closed_gracefully = False
        self.video = video
        self.preempt = preempt
        self.video_deadline = video_deadline
        self.clock = int(time()) if clock is None else clock
        self.silent = silent
        self.handshake_reply = handshake_reply
        self.owner = 0x9000 if video else 0
        self.projected = 0
        self.video_acks = 0
        self.focus_history = []
        self.audio_focus_denied = False
        self.allocations = {}
        self.next_heap = self.heap

    def service_frame(self, message, channel=0, flags=0, *, fragment=None):
        if fragment is not None:
            for start, stop, flag in ((0, fragment, 1), (fragment, len(message), 2)):
                part = message[start:stop]
                assert self.peer.write(part) == len(part)
                encrypted = self.outbox.read()
                self.pending.extend(struct.pack('>BBH', channel, 8 | flags | flag, len(encrypted)))
                if flag == 1:
                    self.pending.extend(struct.pack('>I', len(message)))
                self.pending.extend(encrypted)
            return
        assert self.peer.write(message) == len(message)
        encrypted = self.outbox.read()
        self.pending.extend(struct.pack('>BBH', channel, 11 | flags, len(encrypted)) + encrypted)

    def dispatch_frame(self, channel, flags, payload):
        if flags & 8:
            self.inbox.write(payload)
            message = self.peer.read(0x4000)
            if channel == 3:
                assert self.video
                self.video_reply(flags, message)
                return
            if message.startswith(b'\x00\x06'):
                from i30_receiver import schema
                self.services = schema.parse(schema.CTL + 'ServiceDiscoveryResponse', message[2:])
                if self.video:
                    assert len(self.services.channels) == 1 and self.services.channels[0].id == 3
                    self.service_frame(b'\x00\x12\x08\x01')
            elif message == b'\x00\x13\x08\x03\x10\x00':
                assert self.video
                self.audio_focus_denied = True
                self.service_frame(b'\x00\x11\x08\x01')  # Optional voice notification without a microphone channel.
                self.service_frame(b'\x00\x07\x08\x00\x10\x03', 3, 4)
            elif message == b'\x00\x10':
                assert self.video
                self.closed_gracefully = True
            else:
                assert message == b'\x00\x0f\x08\x01'
                self.service_frame(b'\x00\x10')
                self.closed_gracefully = True
            return
        code, = struct.unpack_from('>H', payload)
        if code == 4:
            assert self.authenticated and payload[2:] == b'\x08\x00'
            if self.video:
                self.ms += 7900  # Discovery finishes just before the authentication budget expires.
            self.service_frame(b'\x00\x05\x2a\x04Test')
            return
        assert code == 3
        if self.silent:
            return
        self.inbox.write(payload[2:])
        try:
            self.peer.do_handshake()
            self.authenticated = True
        except ssl.SSLWantReadError:
            pass
        except ssl.SSLError as error:
            self.peer_error = error.reason
        outgoing = self.outbox.read()
        if outgoing:
            if self.handshake_reply:
                self.pending.extend(self.handshake_reply(outgoing))
            else:
                self.pending.extend(struct.pack('>BBHH', 0, 3, 2 + len(outgoing), 3) + outgoing)

    def video_reply(self, flags, message):
        code, = struct.unpack_from('>H', message)
        if code == 8:
            assert flags == 15 and message[2:] == b'\x08\x00'
            self.service_frame(b'\x80\x00\x08\x03', 3)
        elif code == 0x8003:
            assert flags == 11 and message[2:] == bytes((8, 2, 16, 1, 26, 1, 0))
            self.ms += 1000  # Video begins past the original shared eight-second deadline.
            self.service_frame(b'\x80\x01\x08\x23\x10\x00', 3)
            self.service_frame(b'\x80\x07\x10\x01', 3)
        elif code == 0x8008:
            assert flags == 11
            focus, unsolicited = message[3], message[5]
            assert message[2::2] == b'\x08\x10'
            self.focus_history.append((focus, unsolicited))
            if (focus, unsolicited) == (1, 0):
                self.service_frame(bytes(10) + self.video, 3, fragment=11)
            elif (focus, unsolicited) == (1, 1):
                assert self.preempt and self.video_acks == 2
                self.service_frame(bytes(10) + self.video, 3)
            else:
                assert (focus, unsolicited) == (2, 1) and self.preempt and self.video_acks == 1
        elif code == 0x8004:
            assert message[2:] == b'\x08\x23\x10\x01'
            self.video_acks += 1
            if self.video_deadline:
                assert self.video_acks == self.projected == 1
                self.ms += 20000
                self.service_frame(bytes(10) + self.video, 3)
            elif self.preempt and self.video_acks == 1:
                assert self.projected == 1
                self.owner = 0x9001
                self.service_frame(bytes(10) + self.video, 3)
            elif self.preempt and self.video_acks == 2:
                assert self.projected == 1
                self.owner = 0x9000
            else:
                assert self.projected == (2 if self.preempt else 1)
                self.service_frame(b'\x00\x0f\x08\x01')
        else:
            raise AssertionError(f'Unexpected video response {code:#x}')

    def CreateFileW(self, name, *_):
        filename = self.text(name).rsplit('\\', 1)[-1]
        if filename not in self.files:
            return -1
        handle = 0x100 + list(self.files).index(filename)
        self.positions[handle] = (filename, 0)
        return handle

    def ReadFile(self, handle, buffer, size, length, *_):
        filename, offset = self.positions[handle]
        data = self.files[filename][offset:offset + size]
        if data:
            self.cpu.mem_write(buffer, data)
        self.positions[handle] = (filename, offset + len(data))
        self.put(length, len(data))
        return 1

    def CloseHandle(self, handle, *_):
        self.positions.pop(handle, None)
        return 1

    def allocate(self, size, wipe=False):
        assert 0 < size <= 4 * 1024 * 1024
        mapped = (size + 0xfff) & ~0xfff
        address = self.next_heap
        self.next_heap += mapped
        self.cpu.mem_map(address, mapped)
        self.allocations[address] = (size, mapped, wipe)
        return address

    def LocalAlloc(self, flags, size, *_):
        assert flags in (0, 0x40)
        return self.allocate(size, wipe=flags == 0x40)

    def LocalFree(self, handle, *_):
        size, mapped, wipe = self.allocations.pop(handle)
        if wipe:
            assert not any(self.cpu.mem_read(handle, size))
        self.cpu.mem_unmap(handle, mapped)
        return 0

    def GetProcessHeap(self, *_):
        return 0x8000

    def HeapAlloc(self, heap, flags, size, *_):
        assert (heap, flags) == (0x8000, 0)
        return self.allocate(size)

    def HeapFree(self, heap, flags, pointer, *_):
        assert (heap, flags) == (0x8000, 0)
        self.LocalFree(pointer)
        return 1

    def FindWindowW(self, name, title, *_):
        if not name:
            assert self.text(title) == 'Android Auto · i30'
            return 0
        assert not title
        if self.text(name) == 'I30.GD13MY.NavigationProjection.1':
            return 0  # This fixture exercises the legacy foreground surface.
        assert self.text(name) == 'I30.GD13MY.VideoSurface.1'
        return 0x9000 if self.video else 0

    def GetForegroundWindow(self, *_):
        return self.owner

    def GetDC(self, window, *_):
        assert window == self.owner == 0x9000
        return 11

    def ReleaseDC(self, window, dc, *_):
        assert (window, dc) == (0x9000, 11)
        return 1

    def StretchDIBits(self, dc, x, y, width, *_):
        assert (dc, x, y, width) == (11, 0, 0, 800)
        sp = self.cpu.reg_read(UC_ARM_REG_SP)
        _, _, _, _, _, bits, bitmap = struct.unpack('<7I', self.cpu.mem_read(sp, 28))
        assert struct.unpack('<IiiHH', self.cpu.mem_read(bitmap, 16)) == (40, 800, -480, 1, 32)
        blue, green, red, _ = self.cpu.mem_read(bits + 4 * (400 + 240 * 800), 4)
        assert red > 210 and blue < 35 and green < 35
        self.projected += 1
        return 1

    def CeGenRandom(self, size, output, *_):
        self.cpu.mem_write(output, bytes(range(size)))  # Reproducible test inputs only.
        return 1

    def GetSystemTimeAsFileTime(self, output, *_):
        self.cpu.mem_write(output, struct.pack('<Q', (self.clock + 11644473600) * 10000000))
        return 0

    def bulk(self, pipe, callback, context, flag, size, data, pa):
        if ((flag & 0x80 and size == 12) or (not flag & 0x80 and not self.wire_writes)):
            return super().bulk(pipe, callback, context, flag, size, data, pa)
        if flag & 0x80:
            assert (pipe, size, flag) == (0x81, 512, 0x380)
            if not self.pending:
                return 0
            chunk = bytes(self.pending[:size])
            del self.pending[:size]
            self.cpu.mem_write(data, chunk)
            return self.issue(len(chunk))
        assert pipe == 1 and 0 < size <= 512
        self.received.extend(self.cpu.mem_read(data, size))
        while len(self.received) >= 6:
            channel, flags, length = struct.unpack_from('>BBH', self.received)
            assert channel in (0, 3) and flags in (3, 11, 15)
            end = length + 4
            if len(self.received) < end:
                break
            payload = bytes(self.received[4:end])
            del self.received[:end]
            self.dispatch_frame(channel, flags, payload)
        return self.issue(size)


def issue_test_certificate(openssl, base, issuer, issuer_key, name, extensions):
    request, cert, key, ext = (base / f'{name}.{suffix}' for suffix in ('csr', 'pem', 'key', 'ext'))
    ext.write_text('\n'.join(extensions) + '\n', encoding='ascii')
    for command in (
            ('req', '-new', '-newkey', 'rsa:2048', '-nodes', '-subj', f'/CN={name}',
             '-out', request, '-keyout', key),
            ('x509', '-req', '-in', request, '-CA', issuer, '-CAkey', issuer_key,
             '-CAcreateserial', '-days', '1', '-extfile', ext, '-out', cert)):
        subprocess.run([openssl, *command], check=True, capture_output=True, timeout=20)
    return cert, key


def fragmented_tls_reply(outgoing, total_adjustment=0):
    message = b'\x00\x03' + outgoing
    return (struct.pack('>BBHI', 0, 1, 1, len(message) + total_adjustment) + message[:1] +
            struct.pack('>BBH', 0, 0, 4) + message[1:5] +
            struct.pack('>BBH', 0, 2, len(message) - 5) + message[5:])


def test_tls(path, openssl, exercise_projection=False):
    sys.path.insert(0, str(FORMAT.parents[2] / 'src'))
    from i30_receiver.mock import test_identity

    missing = UsbClient(path, 'version')
    missing.events.update({7: 'Version', 8: 'AuthRequired'})
    result = missing.attach()
    missing_status = ['Version', 'AuthRequired', 'Ready']
    assert result['accepted'] and result['signals'] == missing_status, result

    with test_identity(openssl) as (cert, key, context):
        cert_der = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding='ascii'))
        key_der = subprocess.check_output([openssl, 'pkey', '-in', key, '-outform', 'DER'], timeout=10)
        files = {'i30-ca.der': cert_der, 'i30-peer.txt': b'i30-mock.local',
                 'i30-client.der': cert_der, 'i30-client-key.der': key_der}
        verified = TlsUsbClient(path, files, context)
        good = verified.attach()
        assert verified.authenticated and good['debug'][-1] == (
            'i30 CE authenticated service discovery completed.'), (good, verified.peer_error)
        assert verified.services.headunit_info.head_unit_model == 'GD13MY'
        assert not verified.services.channels and verified.closed_gracefully
        wrong = TlsUsbClient(path, dict(files, **{'i30-peer.txt': b'other.invalid'}), context)
        denied = wrong.attach()
        assert not wrong.authenticated and denied['debug'][-2:] == [
            'i30 CE TLS BearSSL error: 56', 'i30 CE TLS phone certificate trust or peer identity rejected.'], denied
        report = {'projection_without_credentials': missing_status,
                  'mutual_tls': good['debug'][-1], 'media_channels': len(verified.services.channels),
                  'graceful_close': verified.closed_gracefully, 'wrong_hostname': denied['debug'][-2:]}
        fragmented = TlsUsbClient(path, files, context, handshake_reply=fragmented_tls_reply)
        result = fragmented.attach()
        assert fragmented.authenticated and fragmented.services and fragmented.closed_gracefully, result
        malformed = TlsUsbClient(path, files, context,
                                 handshake_reply=lambda data: fragmented_tls_reply(data, total_adjustment=1))
        result = malformed.attach()
        assert not malformed.authenticated and result['debug'][-1] == (
            'i30 CE TLS invalid Android Auto handshake frame.'), result
        report['fragmented_handshake'] = 'Split message ID and TLS record accepted; inconsistent total rejected'
        pem = cert.read_bytes()
        pem_files = {'i30-ca.pem': pem, 'i30-peer.txt': files['i30-peer.txt'], 'i30-client.pem': pem.rstrip(),
                     'i30-client-key.pem': key.read_bytes()}
        pem_client = TlsUsbClient(path, pem_files, context)
        assert pem_client.attach()['debug'][-1] == good['debug'][-1] and pem_client.authenticated
        report['pem'] = 'PEM CA, client certificate and key accepted'

        intermediate, intermediate_key = issue_test_certificate(openssl, cert.parent, cert, key, 'test-intermediate', (
            'basicConstraints=critical,CA:TRUE,pathlen:0', 'keyUsage=critical,keyCertSign,cRLSign'))
        leaf, leaf_key = issue_test_certificate(openssl, cert.parent, intermediate, intermediate_key, 'test-head-unit', (
            'basicConstraints=critical,CA:FALSE', 'keyUsage=critical,digitalSignature', 'extendedKeyUsage=clientAuth'))
        chain_files = dict(pem_files, **{'i30-client.pem': leaf.read_bytes() + intermediate.read_bytes(),
                                        'i30-client-key.pem': leaf_key.read_bytes()})
        chain_client = TlsUsbClient(path, chain_files, context)
        assert chain_client.attach()['debug'][-1] == good['debug'][-1] and chain_client.authenticated
        leaf_only = TlsUsbClient(path, dict(chain_files, **{'i30-client.pem': leaf.read_bytes()}), context)
        result = leaf_only.attach()
        assert not leaf_only.authenticated and 'i30 CE TLS peer fatal alert: 48' in result['debug'], result
        report['client_chain'] = 'A TLS peer requiring the intermediate accepted the full PEM chain and rejected the leaf alone'

        clock_errors = (
            (-11644473600, 'guest UTC unavailable or invalid'),
            (verified.clock - 86400, 'head unit certificate is not yet valid at guest UTC'),
            (verified.clock + 2 * 86400, 'head unit certificate expired at guest UTC'),
        )
        report['clock'] = []
        for clock, expected in clock_errors:
            guest = TlsUsbClient(path, files, context, clock=clock)
            result = guest.attach()
            assert not guest.authenticated and result['debug'][-1] == f'i30 CE TLS {expected}.', result
            report['clock'].append(result['debug'][-1])
        bad_pem = dict(pem_files, **{'i30-client.pem': pem + b'-----BEGIN CERTIFICATE-----\nQUJD\n'})
        result = TlsUsbClient(path, bad_pem, context).attach()
        assert result['debug'][-1] == 'i30 CE TLS head unit certificate missing, unreadable or invalid.', result
        quiet = TlsUsbClient(path, files, context, silent=True)
        result = quiet.attach()
        assert result['debug'][-1] == 'i30 CE TLS USB read interrupted while waiting for the phone.', result
        report['silent_phone'] = result['debug'][-1]
        incompatible = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        incompatible.load_cert_chain(cert, key)
        incompatible.minimum_version = ssl.TLSVersion.TLSv1_3
        result = TlsUsbClient(path, files, incompatible).attach()
        assert result['debug'][-3:] == ['i30 CE TLS BearSSL error: 326', 'i30 CE TLS peer fatal alert: 70',
                                        'i30 CE TLS phone sent a fatal alert.'], result
        report['tls_alert'] = result['debug'][-3:]
        pin_files = {name: data for name, data in files.items() if name != 'i30-peer.txt'}
        pin_files['i30-peer-sha256.txt'] = sha256(cert_der).hexdigest().encode('ascii') + b'\r\n'
        pinned = TlsUsbClient(path, pin_files, context)
        result = pinned.attach()
        assert pinned.authenticated and pinned.closed_gracefully, result
        wrong_pin = TlsUsbClient(path, dict(pin_files, **{'i30-peer-sha256.txt': b'0' * 64}), context)
        result = wrong_pin.attach()
        assert not wrong_pin.authenticated and result['debug'][-2:] == [
            'i30 CE TLS BearSSL error: 62', 'i30 CE TLS phone certificate trust or peer identity rejected.'], result
        with test_identity(openssl) as (other_cert, other_key, _):
            bad_ca = ssl.PEM_cert_to_DER_cert(other_cert.read_text(encoding='ascii'))
            untrusted = TlsUsbClient(path, dict(pin_files, **{'i30-ca.der': bad_ca}), context)
            result = untrusted.attach()
            assert not untrusted.authenticated and result['debug'][-2:] == [
                'i30 CE TLS BearSSL error: 62', 'i30 CE TLS phone certificate trust or peer identity rejected.'], result
            result = TlsUsbClient(path, dict(pem_files, **{'i30-client-key.pem': other_key.read_bytes()}), context).attach()
            assert result['debug'][-1] == 'i30 CE TLS head unit certificate and RSA key do not match.', result
            report['key_mismatch'] = result['debug'][-1]
        report['fingerprint'] = 'matching chain and pin accepted; mismatched pin or CA rejected'
        if exercise_projection:
            import av
            codec = av.CodecContext.create('libx264', 'w')
            codec.width, codec.height, codec.pix_fmt = 800, 480, 'yuv420p'
            codec.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline'}
            frame = av.VideoFrame(800, 480, 'yuv420p')
            for plane, value in zip(frame.planes, (81, 90, 240)):
                plane.update(bytes([value]) * plane.buffer_size)
            sample = b''.join(bytes(packet) for packet in (*codec.encode(frame), *codec.encode(None)))
            for mode in ('video', 'display_preemption', 'video_deadline'):
                preempt, deadline = mode == 'display_preemption', mode == 'video_deadline'
                projected = TlsUsbClient(path, files, context, video=sample, preempt=preempt, video_deadline=deadline)
                result = projected.attach()
                assert projected.projected == (2 if preempt else 1) and not projected.allocations, result
                assert projected.video_acks == (3 if preempt else 1)
                assert projected.closed_gracefully != deadline
                assert projected.audio_focus_denied
                assert projected.ms >= 8900
                assert projected.focus_history == ([(1, 0), (2, 1), (1, 1)] if preempt else [(1, 0)])
                assert 'i30 CE projection frame presented.' in result['debug']
                report[mode] = result['debug'][2:]
            report['stock_audio'] = 'projection audio focus denied; video remained active'
        return report


class Settings(Machine):
    KEY_SUFFIX = r'\I30AA_GD13MY_061_USB_1'

    def __init__(self, path, case):
        super().__init__(path)
        self.case = case
        self.messages = []
        self.events = []
        self.registrations = []
        self.removed = []
        self.values = {}
        self.handles = {}
        self.disabled = False
        self.dialog = None
        self.projection_owner = None
        self.checks = {}
        self.files = set()
        self.polls = 0
        self.resets = []
        self.keys = [r'Drivers\USB\ClientDrivers' + self.KEY_SUFFIX]
        self.keys.extend(r'Drivers\USB\LoadClients' + '\\' + group + self.KEY_SUFFIX for group in (
            r'6353_11520\Default\255', r'6353_11521\Default\255', r'1256_26720\Default\Default'))

    def GetCommandLineW(self, *_):
        if self.case in ('cancel', 'preferences'):
            value = ''
        elif self.case == 'clock-boot':
            value = '-i30clock'
        elif self.case in ('boot-disabled', 'resident'):
            value = '-i30start'
        elif self.case.startswith('owner-'):
            value = '-i30run:1234abcd'
        else:
            value = '-i30run'
        self.cpu.mem_write(RAM + 0x800, (value + '\0').encode('utf-16-le'))
        return RAM + 0x800

    def GetModuleHandleW(self, *_):
        return self.base

    def DialogBoxIndirectParamW(self, module, template, owner, callback, data, *_):
        if self.case == 'owner-current':
            assert module == self.base and owner == 0x1234abcd and data and callback
            assert self.text(template + 22) == 'Android Auto · i30'
            self.projection_owner = owner
            return 0
        assert module == self.base and not owner and not data
        assert struct.unpack('<H', self.cpu.mem_read(template + 8, 2))[0] == 5
        cursor = template + 48
        controls = []
        for _ in range(5):
            style, _, _, _, _, _, control, kind, control_type = struct.unpack(
                '<II7H', self.cpu.mem_read(cursor, 22))
            label = self.text(cursor + 22)
            controls.append((control, kind, control_type, style & 15))
            cursor = (cursor + 26 + len(label.encode('utf-16-le')) + 3) & ~3
        assert controls == [(1003, 0xffff, 0x80, 3), (1004, 0xffff, 0x82, 0),
                            (1, 0xffff, 0x80, 1), (2, 0xffff, 0x80, 0), (1002, 0xffff, 0x80, 0)]
        self.dialog = callback - self.base
        return 2

    def GetDlgItem(self, window, control, *_):
        assert window == 20
        return control

    def SetWindowPos(self, window, sibling, x, y, width, height, flags):
        assert (window, sibling, x, y, width, height, flags) == (20, 0, 194, 116, 0, 0, 0x15)
        return 1

    def SendMessageW(self, checkbox, message, selected, reserved, *_):
        assert checkbox == 1003 and not reserved
        if message == 0xf1:
            self.checks[checkbox] = selected
            return 0
        assert message == 0xf0
        return self.checks[checkbox]

    def CreateFileW(self, name, flags, share, security, disposition, attrs, template):
        if flags == 0x80000000:
            assert self.text(name) == r'\DiskA\Application\NAVI\i30-emu-utc.bin'
            assert (share, security, disposition, attrs, template) == (1, 0, 3, 0x80, 0)
            return 201 if self.case == 'clock-boot' else -1
        assert (flags, share, security, disposition, attrs, template) == (0x40000000, 0, 0, 2, 0x80, 0)
        self.files.add(self.text(name))
        return 200

    def ReadFile(self, handle, out, length, consumed, overlapped, *_):
        assert (handle, length, overlapped) == (201, 24, 0)
        self.cpu.mem_write(out, struct.pack('<8s8H', b'I30UTC01', 2026, 11, 1, 23, 0, 52, 0, 0))
        self.put(consumed, length)
        return 1

    def SetSystemTime(self, value, *_):
        assert self.case == 'clock-boot'
        assert struct.unpack('<8H', self.cpu.mem_read(value, 16)) == (2026, 11, 1, 23, 0, 52, 0, 0)
        return 1

    def DeleteFileW(self, name, *_):
        self.files.remove(self.text(name))
        return 1

    def EndDialog(self, window, selection, *_):
        assert (window, selection) == (20, 1)
        return 1

    def SetDlgItemTextW(self, window, control, status, *_):
        assert (window, control) == (20, 1004)
        self.messages.append(self.text(status))
        return 1

    def UpdateWindow(self, window, *_):
        assert window == 20
        return 1

    def GetFileAttributesW(self, path, *_):
        name = self.text(path)
        if name == r'\DiskA\i30auto.opt':
            if self.case == 'resident':
                return 0x80 if self.polls < 3 else 0xffffffff
            if self.case in ('preferences', 'boot-disabled', 'clock-boot'):
                return 0x80 if name in self.files else 0xffffffff
            return 0x80
        if self.case.startswith('owner-') and name.endswith(r'\NAVI\i30-ca.der'):
            return 0x80
        assert name.endswith(r'\NAVI\i30usb.dll')
        return 0xffffffff if self.case == 'missing-driver' else 0x80

    def CreateEventW(self, security, manual, initial, name, *_):
        assert not security and manual and not initial
        if self.case.startswith('owner-'):
            assert not name
            return 20
        self.events.append(self.text(name).split('.')[-1])
        return len(self.events)

    def GetForegroundWindow(self, *_):
        assert self.case.startswith('owner-')
        return 0x1234abcd if self.case == 'owner-current' else 0x5678

    def GetLastError(self, *_):
        return 183 if self.case == 'already-running' else 0

    def EventModify(self, gate, operation, *_):
        if self.case.startswith('owner-'):
            assert (gate, operation) == (20, 3)
            return 1
        if operation == 2:
            assert self.case == 'resident' and gate in (3, 4)
            self.resets.append(gate)
            return 1
        assert gate == 1 and operation == 3
        self.disabled = True
        return 1

    def RegCreateKeyExW(self, root, path, reserved, class_name, options, access, security, output, disposition):
        assert root == 0x80000002 and not any((reserved, class_name, options, access, security))
        key = self.text(path)
        assert key == self.keys[len(self.registrations)] and not self.handles
        if self.case == 'create-failure' and key == self.keys[-1]:
            return 5
        exists = self.case == 'existing-key' and key == self.keys[2]
        if not exists:
            self.registrations.append(key)
            self.values[key] = None
        handle = 100 + self.keys.index(key)
        self.handles[handle] = key
        self.put(output, handle)
        self.put(disposition, 2 if exists else 1)
        return 0

    def RegSetValueExW(self, handle, name, reserved, kind, data, size, *_):
        key = self.handles[handle]
        assert key in self.values and key != self.keys[0]
        path = self.text(data)
        assert (self.text(name), reserved, kind, path) == ('DLL', 0, 1, r'\DiskA\Application\NAVI\i30usb.dll')
        assert size == len(path.encode('utf-16-le')) + 2
        if self.case == 'write-failure' and key == self.keys[-1]:
            return 5
        self.values[key] = path
        return 0

    def RegCloseKey(self, handle, *_):
        del self.handles[handle]
        return 0

    def RegDeleteKeyW(self, root, path, *_):
        key = self.text(path)
        assert root == 0x80000002 and self.disabled and not self.handles
        del self.values[key]
        self.removed.append(key)
        return 0

    def WaitForMultipleObjects(self, count, values, wait_all, timeout, *_):
        assert (count, wait_all, timeout) == (2, 0, 1000 if self.case == 'resident' else 35000)
        assert [self.word(values + i * 4) for i in range(2)] == [3, 4]
        assert set(self.values) == set(self.keys) and all(self.values[key] for key in self.keys[1:])
        if self.case == 'resident':
            result = (0, 1, 258)[self.polls]
            self.polls += 1
            return result
        return {'version-ok': 0, 'version-failed': 1}.get(self.case, 258)

    def WaitForSingleObject(self, handle, *_):
        assert handle == 2
        return 0 if self.case == 'no-accessory-reenumeration' else 258

    def OutputDebugStringW(self, message, *_):
        value = self.text(message)
        if value != '\r\n' and not value.startswith('i30 USB attach ready'):
            self.messages.append(value)
        return 0

    def ExitThread(self, result, *_):
        self.cpu.reg_write(UC_ARM_REG_R0, result)
        self.cpu.reg_write(UC_ARM_REG_PC, MARK)

    def start(self):
        assert not self.run(self.pe.OPTIONAL_HEADER.AddressOfEntryPoint)
        assert self.removed == list(reversed(self.registrations))
        assert not self.values and not self.handles
        return {'registrations': self.registrations, 'registered_then_removed': self.removed,
                'result': self.messages[-1] if self.messages else 'skipped', 'status_resets': self.resets}

    def exercise_preferences(self):
        self.start()
        assert self.dialog is not None
        self.run(self.dialog, (20, 0x110, 0, 0))
        assert self.checks == {1003: 0}
        self.checks[1003] = 1
        self.run(self.dialog, (20, 0x111, 1, 0))
        assert self.files == {r'\DiskA\i30auto.opt'}
        self.run(self.dialog, (20, 0x110, 0, 0))
        assert self.checks == {1003: 1}
        self.checks[1003] = 0
        self.run(self.dialog, (20, 0x111, 1, 0))
        assert not self.files
        self.run(self.dialog, (20, 0x111, 1002, 0))
        assert 'No supported phone' in self.messages[-1]
        assert not self.values and self.removed == list(reversed(self.registrations))
        return 'Default off, setting and clearing the boot flag, and inline USB test verified'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--tls-openssl', type=Path, help='Exercise the native TLS build with an ephemeral test identity')
    parser.add_argument('--projection', action='store_true', help='Run the native USB-to-GDI video and preemption test')
    args = parser.parse_args()
    client = {case: UsbClient(args.artifacts / 'i30usb.dll', case).attach()
              for case in ('switch', 'version', 'not-armed', 'storage', 'unsupported', 'wrong-interface',
                           'second-pipe-fails', 'timeout')}
    assert client['switch']['accepted'] and client['switch']['controls'] == [51, 52, 52, 52, 52, 53]
    assert client['version']['accepted'] and client['version']['signals'] == ['Ready']
    assert client['version']['inputs'] == ['00030006000100010006']
    assert all(not result['accepted'] for name, result in client.items() if name not in ('switch', 'version'))
    assert client['timeout']['wait_ms'] == 3000 and client['timeout']['closed_transfers'] == 1
    settings = {case: Settings(args.artifacts / 'i30aa.exe', case).start()
                for case in ('version-ok', 'version-failed', 'timeout', 'no-accessory-reenumeration',
                             'cancel', 'missing-driver', 'already-running', 'create-failure', 'write-failure',
                             'existing-key', 'boot-disabled', 'clock-boot', 'resident')}
    assert 'Phone answered' in settings['version-ok']['result']
    assert 'No supported phone' in settings['timeout']['result']
    assert len(settings['create-failure']['registrations']) == 3
    assert len(settings['write-failure']['registrations']) == 4
    assert len(settings['existing-key']['registrations']) == 2
    assert not settings['already-running']['registrations'] and not settings['missing-driver']['registrations']
    assert not settings['boot-disabled']['registrations']
    assert not settings['clock-boot']['registrations']
    assert settings['clock-boot']['result'] == 'i30 CE clock set from emulator UTC.\r\n'
    assert settings['resident']['result'] == 'Android Auto auto-connect stopped.'
    assert settings['resident']['status_resets'] == [3, 4]
    preferences = Settings(args.artifacts / 'i30aa.exe', 'preferences').exercise_preferences()
    owners = {}
    for case in ('owner-current', 'owner-replaced'):
        settings_test = Settings(args.artifacts / 'i30aa.exe', case)
        settings_test.start()
        owners[case] = settings_test.projection_owner
    assert owners == {'owner-current': 0x1234abcd, 'owner-replaced': None}
    report = {'method': 'Relocated ARM PE with WinCE USB and coredll API doubles',
              'client': client, 'settings': settings, 'preferences': preferences, 'projection_owner': owners}
    if args.tls_openssl:
        report['native_tls'] = test_tls(args.artifacts / 'i30usb.dll', args.tls_openssl, args.projection)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
