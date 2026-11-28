"""Execute the built ARM CE USB client and menu component with WinCE API doubles."""

import argparse
from collections import Counter
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re
import ssl
import statistics
import struct
import subprocess
import sys
from time import monotonic, process_time, time

import pefile
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM, Uc
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP,
                               UC_CPU_ARM_CORTEX_A8)


STUB = 0x70000000
RAM = 0x20000000
MARK = STUB + 0xff0
STACK = RAM + 0xf000
FORMAT = Path(__file__).resolve().parent.parent / 'research/evidence/phase1-rom.json'


def artifact_video_format(path):
    """Read the build-time color path from the ABI report; older artifacts use BGRA."""
    abi = json.loads(path.with_name('abi.json').read_text(encoding='utf-8'))
    return abi.get(path.name, {}).get('video_format', 'bgra')


class Machine:
    timeout_us = 2_000_000
    instruction_limit = 200_000

    def __init__(self, path, base=None):
        self.pe = pefile.PE(data=path.read_bytes())
        self.base = base if base is not None else self.pe.OPTIONAL_HEADER.ImageBase
        image = self.pe.get_memory_mapped_image(ImageBase=self.base)
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
        self.cpu.mem_map(self.base, (len(image) + 0xfff) & ~0xfff)
        self.cpu.mem_write(self.base, image)
        self.cpu.mem_map(STUB, 0x1000)
        self.cpu.mem_map(RAM, 0x10000)
        self.dispatch_hook = self.cpu.hook_add(UC_HOOK_CODE, self.dispatch, begin=STUB, end=MARK - 4)
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
        try:
            handler = getattr(self, name)
        except AttributeError:
            raise AttributeError(f'{type(self).__name__} has no {name}; caller {cpu.reg_read(UC_ARM_REG_LR) - self.base:#x}') from None
        result = handler(*args)
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
        try:
            self.cpu.emu_start(self.base + rva, MARK, timeout=self.timeout_us, count=self.instruction_limit)
        except Exception as error:
            raise RuntimeError(f'{error!s} at PC {self.cpu.reg_read(UC_ARM_REG_PC):#x} '
                               f'(RVA {self.cpu.reg_read(UC_ARM_REG_PC) - self.base:#x})') from error
        if self.cpu.reg_read(UC_ARM_REG_PC) != MARK:
            raise ValueError('ARM test input did not finish')
        return self.cpu.reg_read(UC_ARM_REG_R0)

    def CloseHandle(self, *unused):
        return 1

    def ascii(self, p):
        chars = []
        for _ in range(500):
            byte = bytes(self.cpu.mem_read(p, 1))
            if byte == b'\0':
                return b''.join(chars).decode('ascii')
            chars.append(byte)
            p += 1
        raise ValueError('Unterminated CE ASCII string')


class DdrawDoubleMixin:
    """ARM-side CE6 DirectDraw API doubles.

    This is a mock contract only: it proves the guest's loader calls, CE6 vtable
    slots, descriptor offsets and failure handling. It says nothing about real
    DDRAW.dll surface capabilities, overlay ownership or LCD output.
    """

    DD_MODULE = 0xd0000000
    DD_OBJECT = RAM + 0x4000
    DD_PRIMARY = RAM + 0x4100
    DD_OVERLAY = RAM + 0x4200
    DD_BACK = RAM + 0x4300
    DD_VTABLE = RAM + 0x4400
    SURFACE_VTABLE = RAM + 0x4500
    SURFACE_BASE = 0x40000000
    SURFACE_BYTES = (800 * 2 + 32) * 480
    UYVY_FOURCC = 0x59565955
    SURFACE_LOST = 0x887601c2

    def install_ddraw_double(self, *, flip=False, mode=None, capture=True):
        self.ddraw = {
            'mode': mode, 'flip': bool(flip), 'loads': [], 'frees': 0, 'procs': [], 'creates': [],
            'cooperative': [], 'caps_sizes': [],
            'overlay_caps': 0x80000004 | (1 if flip else 0),
            'refs': {}, 'locks': 0, 'unlocks': 0, 'restores': 0, 'is_lost': 0,
            'enums': 0, 'shows': 0, 'hides': 0, 'show_flags': [], 'src_rects': [],
            'flips': 0, 'flip_status': 0, 'lock_flags': [], 'frame': None,
            'capture': bool(capture),
        }
        self.cpu.mem_map(self.SURFACE_BASE, 0x100000)
        self.cpu.mem_write(self.SURFACE_BASE, bytes([0xa5]) * self.SURFACE_BYTES)
        unused = self.hook('DdrawUnused')
        dd_slots = {
            0x08: self.hook('DdrawRelease'), 0x14: self.hook('DdrawCreateSurface'),
            0x24: self.hook('DdrawGetCaps'), 0x2c: self.hook('DdrawGetFourCCCodes'),
            0x44: self.hook('DdrawSetCooperativeLevel'),
        }
        surface_slots = {
            0x04: self.hook('DdrawAddRef'), 0x08: self.hook('DdrawRelease'),
            0x14: self.hook('DdrawEnumAttached'), 0x1c: self.hook('DdrawFlip'),
            0x34: self.hook('DdrawFlipStatus'), 0x48: self.hook('DdrawIsLost'),
            0x4c: self.hook('DdrawLock'), 0x54: self.hook('DdrawRestore'),
            0x68: self.hook('DdrawUnlock'), 0x6c: self.hook('DdrawUpdateOverlay'),
        }
        for base, slots in ((self.DD_VTABLE, dd_slots), (self.SURFACE_VTABLE, surface_slots)):
            for index in range(32):
                self.put(base + index * 4, unused)
            for offset, address in slots.items():
                self.put(base + offset, address)
        for obj, vtable in ((self.DD_OBJECT, self.DD_VTABLE), (self.DD_PRIMARY, self.SURFACE_VTABLE),
                            (self.DD_OVERLAY, self.SURFACE_VTABLE), (self.DD_BACK, self.SURFACE_VTABLE)):
            self.put(obj, vtable)
            self.ddraw['refs'][obj] = 0

    def reset_ddraw_counts(self):
        """Per-session counters for the same ARM image across USB replugs."""
        if getattr(self, 'ddraw', None) is None:
            return
        for key in ('loads', 'procs', 'creates', 'cooperative', 'caps_sizes', 'show_flags',
                    'src_rects', 'lock_flags'):
            self.ddraw[key].clear()
        for key in ('frees', 'locks', 'unlocks', 'restores', 'is_lost', 'enums', 'shows', 'hides',
                    'flips', 'flip_status'):
            self.ddraw[key] = 0
        self.ddraw['frame'] = None
        self.ddraw['refs'] = {address: 0 for address in self.ddraw['refs']}

    def LoadLibraryW(self, name, *_):
        label = self.text(name)
        self.ddraw['loads'].append(label)
        if getattr(self, 'ddraw', None) is None or self.ddraw['mode'] == 'library':
            return 0
        assert label in ('DDRAW.dll', '\\Windows\\DDRAW.dll')
        return self.DD_MODULE

    def GetProcAddressA(self, module, name, *_):
        label = self.ascii(name)
        self.ddraw['procs'].append(label)
        assert module == self.DD_MODULE and label == 'DirectDrawCreate'
        return 0 if self.ddraw['mode'] == 'proc' else self.hook('DdrawCreate')

    def FreeLibrary(self, module, *_):
        assert module == self.DD_MODULE
        self.ddraw['frees'] += 1
        return 1

    def DdrawUnused(self, *_):
        return 0

    def DdrawCreate(self, _guid, output, _outer, *_):
        if self.ddraw['mode'] == 'create':
            return 0xffffffff
        self.put(output, self.DD_OBJECT)
        self.ddraw['refs'][self.DD_OBJECT] = 1
        return 0

    def DdrawRelease(self, obj, *_):
        refs = self.ddraw['refs']
        refs[obj] = max(0, refs.get(obj, 0) - 1)
        return refs[obj]

    def DdrawAddRef(self, obj, *_):
        refs = self.ddraw['refs']
        refs[obj] = refs.get(obj, 0) + 1
        return refs[obj]

    def DdrawSetCooperativeLevel(self, _obj, window, flags, *_):
        self.ddraw['cooperative'].append((window, flags))
        assert flags == 0  # DDSCL_NORMAL; fullscreen would take the stock map.
        return 0xffffffff if self.ddraw['mode'] == 'cooperative' else 0

    def DdrawGetCaps(self, _obj, caps, _emulation, *_):
        self.ddraw['caps_sizes'].append(self.word(caps))
        if self.ddraw['mode'] == 'caps':
            return 0xffffffff
        self.put(caps + 0x48, self.ddraw['overlay_caps'])
        return 0

    def DdrawGetFourCCCodes(self, _obj, count_pointer, codes, *_):
        if self.ddraw['mode'] == 'fourcc':
            self.put(count_pointer, 0)
            return 0
        if not codes:
            self.put(count_pointer, 3)
        else:
            self.cpu.mem_write(codes, struct.pack('<3I', 0, self.UYVY_FOURCC, 0x56555949))
        return 0

    def DdrawCreateSurface(self, _obj, desc, output, _outer, *_):
        fields = {name: self.word(desc + offset) for name, offset in
                  (('flags', 4), ('height', 8), ('width', 12), ('backbuffers', 24),
                   ('pixel_size', 68), ('pixel_flags', 72), ('fourcc', 76), ('caps', 100))}
        self.ddraw['creates'].append(fields)
        index = len(self.ddraw['creates'])
        surface = self.DD_PRIMARY if index == 1 else self.DD_OVERLAY
        if self.ddraw['mode'] == 'surface' and index == 2:
            return 0xffffffff
        self.put(output, surface)
        self.ddraw['refs'][surface] = 1
        return 0

    def DdrawEnumAttached(self, *_args):
        self.ddraw['enums'] += 1
        context = self.cpu.reg_read(UC_ARM_REG_R3)
        if self.ddraw['flip'] and self.ddraw['mode'] != 'no-back':
            self.put(context, self.DD_BACK)
            refs = self.ddraw['refs']
            refs[self.DD_BACK] = refs.get(self.DD_BACK, 0) + 1
        return 1

    def DdrawIsLost(self, *_):
        self.ddraw['is_lost'] += 1
        mode = self.ddraw['mode']
        if mode == 'lost' and self.ddraw['is_lost'] == 1:
            return self.SURFACE_LOST
        if mode == 'restore':
            return self.SURFACE_LOST
        return 0

    def DdrawRestore(self, *_):
        self.ddraw['restores'] += 1
        return 0xffffffff if self.ddraw['mode'] == 'restore' else 0

    def DdrawLock(self, obj, _rect, desc, flags, _event, *_):
        self.ddraw['locks'] += 1
        self.ddraw['lock_flags'].append(flags)
        if self.ddraw['mode'] == 'lock':
            return 0xffffffff
        pitch = 800 if self.ddraw['mode'] == 'bad-pitch' else 800 * 2 + 32
        x_pitch = -2 if self.ddraw['mode'] == 'bad-xpitch' else 2
        size = 0 if self.ddraw['mode'] == 'zero-fields' else self.SURFACE_BYTES
        if self.ddraw['mode'] == 'zero-fields':
            x_pitch = 0
        self.put(desc, 108)
        self.put(desc + 8, 480)
        self.put(desc + 12, 800)
        self.put(desc + 16, pitch)
        self.put(desc + 20, x_pitch & 0xffffffff)
        self.put(desc + 32, self.SURFACE_BASE)
        self.put(desc + 104, size)
        assert obj in (self.DD_OVERLAY, self.DD_BACK)
        return 0

    def DdrawUnlock(self, *_):
        self.ddraw['unlocks'] += 1
        if self.ddraw['capture'] and self.ddraw['frame'] is None:
            self.ddraw['frame'] = bytes(self.cpu.mem_read(self.SURFACE_BASE, 2 * (800 * 2 + 32)))
            self.cpu.mem_write(self.SURFACE_BASE, bytes([0xa5]) * len(self.ddraw['frame']))
        return 0xffffffff if self.ddraw['mode'] == 'unlock' else 0

    def DdrawUpdateOverlay(self, _obj, src, _dest, _dest_rect, flags, fx, *_):
        assert self.word(fx) == 28
        if flags & 0x400:
            self.ddraw['shows'] += 1
            self.ddraw['show_flags'].append(flags)
            self.ddraw['src_rects'].append(tuple(
                struct.unpack('<4i', self.cpu.mem_read(src, 16))) if src else None)
            if self.ddraw['mode'] == 'overlay':
                return 0xffffffff
            if self.ddraw['mode'] == 'overlay-lost' and self.ddraw['shows'] == 1:
                return self.SURFACE_LOST
        else:
            self.ddraw['hides'] += 1
        return 0

    def DdrawFlip(self, *_):
        self.ddraw['flips'] += 1
        return 0xffffffff if self.ddraw['mode'] == 'flip' else 0

    def DdrawFlipStatus(self, *_):
        self.ddraw['flip_status'] += 1
        return 0xffffffff if self.ddraw['mode'] == 'flip-timeout' else 0


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
        if label in ('Version', 'AuthRequired', 'Approval', 'AuthFailed', 'Media', 'MediaFailed',
                     'VideoActive') and label not in self.events.values():
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
        self.event_error = 2
        return -1  # No TLS identity is enrolled in the baseline USB tests.

    def GetFileAttributesW(self, path, *_):
        assert self.text(path) == r'\DiskA\Application\NAVI\i30-aare.opt'
        return 0x80 if 'i30-aare.opt' in getattr(self, 'files', {}) else 0xffffffff

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
            if self.case == 'version-disconnect':
                return 0
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


class TlsUsbClient(UsbClient, DdrawDoubleMixin):
    timeout_us = 20_000_000
    instruction_limit = 160_000_000
    heap = 0x50000000

    def __init__(self, path, files, context, *, video=None, preempt=False, clock=None, silent=False,
                 video_deadline=False, handshake_reply=None, interleave_control=False, ddraw_mode=None):
        super().__init__(path, 'version')
        self.video_format = artifact_video_format(path)
        self.rgb565 = self.video_format == 'rgb565'
        if self.video_format == 'ddraw':
            self.install_ddraw_double(flip=json.loads(
                path.with_name('abi.json').read_text(encoding='utf-8')).get(
                    path.name, {}).get('ddraw_flip', False), mode=ddraw_mode)
        self.rejected_rgb565 = False
        self.blit_times = []
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
        self.stalled_transfer = 0
        self.handshake_reply = handshake_reply
        self.interleave_control = interleave_control
        self.owner = 0x9000 if video else 0
        self.camera_active = False
        self.projected = 0
        self.video_acks = 0
        self.pongs = 0
        self.focus_history = []
        self.audio_focus_denied = False
        self.allocations = {}
        self.next_heap = self.heap

    def CreateEventW(self, attrs, manual, initial, name, *_):
        label = self.text(name)
        if label.endswith('StockDisplay.Safe.1'):
            self.events[21] = 'StockDisplay.Safe'
            self.event_error = 183
            return 21
        if label.endswith('StockCamera.Active.1'):
            self.events[22] = 'StockCamera.Active'
            self.event_error = 183
            return 22
        return super().CreateEventW(attrs, manual, initial, name, *_)

    def WaitForSingleObject(self, handle, milliseconds, *_):
        if handle in (21, 22):
            return 0 if handle == 21 or self.camera_active else 258
        return super().WaitForSingleObject(handle, milliseconds, *_)

    def painted_frames(self):
        """Count one visible presentation per ACKed frame, including fallback.

        DirectDraw and GDI are alternatives for the same decoded frame. Counting
        both would double-count rejected frames that showed a stale overlay
        before the same-frame BGRA/GDI fallback.
        """
        if self.video_format != 'ddraw':
            return self.projected
        return self.projected or self.ddraw['shows']

    def service_frame(self, message, channel=0, flags=0, *, fragment=None, between=None):
        if fragment is not None:
            for start, stop, flag in ((0, fragment, 1), (fragment, len(message), 2)):
                part = message[start:stop]
                assert self.peer.write(part) == len(part)
                encrypted = self.outbox.read()
                self.pending.extend(struct.pack('>BBH', channel, 8 | flags | flag, len(encrypted)))
                if flag == 1:
                    self.pending.extend(struct.pack('>I', len(message)))
                self.pending.extend(encrypted)
                if flag == 1 and between:
                    self.service_frame(between)
            return
        assert self.peer.write(message) == len(message)
        encrypted = self.outbox.read()
        self.pending.extend(struct.pack('>BBH', channel, 11 | flags, len(encrypted)) + encrypted)

    def dispatch_frame(self, channel, flags, payload):
        if flags & 8:
            self.inbox.write(payload)
            self.dispatch_secure(channel, flags, self.peer.read(0x4000))
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

    def dispatch_secure(self, channel, flags, message):
        if channel == 3:
            assert self.video
            self.video_reply(flags, message)
        elif message.startswith(b'\x00\x06'):
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
        elif message == b'\x00\x0c\x08\x7b':
            self.pongs += 1
        else:
            assert message == b'\x00\x0f\x08\x01'
            self.service_frame(b'\x00\x10')
            self.closed_gracefully = True

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
                ping = b'\x00\x0b\x08\x7b' if self.interleave_control else None
                self.service_frame(bytes(10) + self.video, 3, fragment=11, between=ping)
            elif (focus, unsolicited) == (1, 1):
                assert self.preempt and self.video_acks == 2
                self.service_frame(bytes(10) + self.video, 3)
            else:
                assert (focus, unsolicited) == (2, 1) and self.preempt and self.video_acks == 1
        elif code == 0x8004:
            assert message[2:] == b'\x08\x23\x10\x01'
            self.video_acks += 1
            painted = self.painted_frames()
            if self.video_deadline:
                assert self.video_acks == painted == 1
                self.ms += 20000
                self.service_frame(bytes(10) + self.video, 3)
            elif self.preempt and self.video_acks == 1:
                assert painted == 1
                self.owner = 0x9001
                self.service_frame(bytes(10) + self.video, 3)
            elif self.preempt and self.video_acks == 2:
                # The preemption frame is ACKed before it is shown on the
                # restored surface; the third frame completes the handoff.
                assert painted == 1
                self.owner = 0x9000
            else:
                assert painted == (2 if self.preempt else 1)
                self.service_frame(b'\x00\x0f\x08\x01')
        else:
            raise AssertionError(f'Unexpected video response {code:#x}')

    def CreateFileW(self, name, *_):
        filename = self.text(name).rsplit('\\', 1)[-1]
        if filename not in self.files:
            self.event_error = 2
            return -1
        if self.files[filename] is None:
            self.event_error = 5
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

    def GetWindow(self, window, command, *_):
        assert window == 0x9000 and command in (2, 4)
        return 0x9001

    def IsWindowVisible(self, window, *_):
        assert window in (0x9000, 0x9001)
        return 1

    def GetWindowLongW(self, window, index, *_):
        assert window in (0x9000, 0x9001) and index == 0xffffffec
        return 0

    def GetClientRect(self, window, rect, *_):
        assert window == 0x9000
        self.cpu.mem_write(rect, struct.pack('<iiii', 0, 0, 800, 480))
        return 1

    def GetDCEx(self, window, region, options, *_):
        assert (window, region, options) == (0x9000, 0, 0x12)
        return 11

    def GetClipBox(self, dc, rect, *_):
        assert dc == 11
        self.cpu.mem_write(rect, struct.pack('<iiii', 0, 0, 800, 480))
        return 2

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
        header = struct.unpack('<IiiHH', self.cpu.mem_read(bitmap, 16))
        expected_bits = 16 if self.rgb565 and not self.rejected_rgb565 else 32
        assert header == (40, 800, -480, 1, expected_bits)
        if header[4] == 16 and getattr(self, 'reject_rgb565', False) and not self.rejected_rgb565:
            self.rejected_rgb565 = True
            self.debug.append('fixture rejected 16-bit DIB once')
            return 0
        offset = 2 * (400 + 240 * 800) if header[4] == 16 else 4 * (400 + 240 * 800)
        began = monotonic()
        try:
            if header[4] == 16:
                masks = struct.unpack('<3I', self.cpu.mem_read(bitmap + 40, 12))
                assert masks == (0xf800, 0x07e0, 0x001f)
                pixel, = struct.unpack('<H', self.cpu.mem_read(bits + offset, 2))
                red, green, blue = ((pixel >> 11) & 31, (pixel >> 5) & 63, pixel & 31)
                self.check_pixel(red * 255 // 31, green * 255 // 63, blue * 255 // 31)
            else:
                blue, green, red, _ = self.cpu.mem_read(bits + offset, 4)
                self.check_pixel(red, green, blue)
        finally:
            self.blit_times.append(monotonic() - began)
        self.projected += 1
        return 1

    def check_pixel(self, red, green, blue):
        assert red > 210 and blue < 35 and green < 35

    def CeGenRandom(self, size, output, *_):
        self.cpu.mem_write(output, bytes(range(size)))  # Reproducible test inputs only.
        return 1

    def GetSystemTimeAsFileTime(self, output, *_):
        self.cpu.mem_write(output, struct.pack('<Q', (self.clock + 11644473600) * 10000000))
        return 0

    def complete(self, transfer, *_):
        return 0 if transfer == self.stalled_transfer else super().complete(transfer)

    def bulk(self, pipe, callback, context, flag, size, data, pa):
        if ((flag & 0x80 and size == 12) or (not flag & 0x80 and not self.wire_writes)):
            return super().bulk(pipe, callback, context, flag, size, data, pa)
        if flag & 0x80:
            assert (pipe, size, flag) == (0x81, 512, 0x380)
            if not self.pending:
                if self.silent:
                    self.stalled_transfer = self.issue(0)
                return self.stalled_transfer
            chunk = bytes(self.pending[:size])
            del self.pending[:size]
            self.cpu.mem_write(data, chunk)
            return self.issue(len(chunk))
        assert pipe == 1 and 0 < size <= 512
        self.received.extend(self.cpu.mem_read(data, size))
        while len(self.received) >= 6:
            channel, flags, length = struct.unpack_from('>BBH', self.received)
            assert channel in (0, 1, 3) and flags in (3, 11, 15)
            end = length + 4
            if len(self.received) < end:
                break
            payload = bytes(self.received[4:end])
            del self.received[:end]
            self.dispatch_frame(channel, flags, payload)
        return self.issue(size)


class NativeUsbStress(TlsUsbClient):
    """ARM API doubles for a resident window, single-pointer IPC and repeated close paths."""

    timeout_us = 60_000_000
    instruction_limit = 350_000_000
    gesture = ((0, 0, 0), (2, 400, 240), (2, 799, 479), (1, 799, 479), (0, 20, 20), (1, 20, 20))

    def __init__(self, path, files, context, frames, *, fps=15, soak=False, failure=None, restart=False,
                 empty_receive=None, motion=False):
        super().__init__(path, files, context, video=frames[0])
        self.events[9] = 'VideoActive'
        self.frames, self.fps, self.soak, self.failure = frames, fps, soak, failure
        self.restart = restart
        self.empty_receive = empty_receive
        self.motion = motion
        self.pixel_samples = set()
        self.waiting_read = None
        self.empty_reads = 0
        self.tested_ipc_timeout = False
        self.gesture_index = 0
        self.touch_reports = []
        self.input_bound = False
        self.video_active = False
        self.touch_armed = False
        self.dropped = False
        self.camera_active = False
        self.peak_bytes = 0
        self.frame_times = []
        self.started_video = 0
        self.long_checkpoints = []
        self.goodbye_sent = False
        self.on_frame = None

    def reconnect(self, context):
        assert not (self.allocations or self.pipes or self.transfers or self.video_active or self.touch_armed)
        # Preserve the ARM image, address space and guest clock across connects.
        self.inbox, self.outbox = ssl.MemoryBIO(), ssl.MemoryBIO()
        self.peer = context.wrap_bio(self.inbox, self.outbox, server_side=True)
        for queue in (self.pending, self.received, self.signaled, self.debug, self.wire_writes,
                      self.touch_reports, self.frame_times):
            queue.clear()
        self.reset_ddraw_counts()
        self.gesture_index = self.projected = self.video_acks = self.peak_bytes = 0
        self.services = self.peer_error = None
        self.authenticated = self.closed_gracefully = self.input_bound = self.goodbye_sent = False

    def allocate(self, size, wipe=False):
        handle = super().allocate(size, wipe)
        self.peak_bytes = max(self.peak_bytes, sum(item[0] for item in self.allocations.values()))
        return handle

    def check_pixel(self, red, green, blue):
        if self.motion:
            self.pixel_samples.add((red, green, blue))
        else:
            super().check_pixel(red, green, blue)

    def CreateEventW(self, attrs, manual, initial, name, *_):
        label = self.text(name)
        if label == 'I30.GD13MY.061.StockDisplay.Safe.1':
            self.event_error = 183
            return 21
        if label == 'I30.GD13MY.061.StockCamera.Active.1':
            self.event_error = 183
            return 22
        return super().CreateEventW(attrs, manual, initial, name)

    def EventModify(self, handle, operation, *_):
        if handle == 9:
            assert operation in (2, 3)
            self.video_active = operation == 3
            return 1
        return super().EventModify(handle, operation)

    def WaitForSingleObject(self, handle, milliseconds, *_):
        if handle == 9:
            return 0 if self.video_active else 258
        if handle in (21, 22):
            return 0 if handle == 21 or self.camera_active else 258
        return super().WaitForSingleObject(handle, milliseconds)

    def FindWindowW(self, name, title, *_):
        assert name and not title and self.text(name) == 'I30.GD13MY.NavigationProjection.1'
        return 0x9000

    def GetWindow(self, window, command, *_):
        assert window == 0x9000 and command in (2, 4)
        return 0x9001

    def IsWindowVisible(self, window, *_):
        assert window in (0x9000, 0x9001)
        return 1

    def GetWindowLongW(self, window, index, *_):
        assert window in (0x9000, 0x9001) and index == 0xffffffec
        return 0

    def GetClientRect(self, window, rect, *_):
        assert window == 0x9000
        self.cpu.mem_write(rect, struct.pack('<iiii', 0, 0, 800, 480))
        return 1

    def GetDCEx(self, window, region, options, *_):
        assert (window, region, options) == (0x9000, 0, 0x12)
        return 11

    def GetClipBox(self, dc, rect, *_):
        assert dc == 11
        return 2

    def SendMessageTimeout(self, window, code, request, detail, flags, timeout, result, *_):
        assert (window, code, detail, flags, timeout) == (0x9000, 0x8002, 0, 0, 100)
        sample = 1
        if request == 1:
            self.touch_armed = True
        elif request == 2:
            self.touch_armed = False
        else:
            assert self.touch_armed
            sample = 0
            if self.empty_receive == 'pending' and self.gesture_index == 1 and not self.tested_ipc_timeout:
                self.tested_ipc_timeout = True
                self.ms += timeout
                return 0
            if self.painted_frames() and self.gesture_index < len(self.gesture):
                action, x, y = self.gesture[self.gesture_index]
                self.gesture_index += 1
                sample = (action + 2) << 19 | y << 10 | x
                self.ms += 21
        self.put(result, sample)
        return 1

    def dispatch_frame(self, channel, flags, payload):
        if not flags & 8:
            if (self.failure == 'tls' and payload[:2] == b'\x00\x03' or
                    self.failure == 'auth-complete' and payload[:2] == b'\x00\x04'):
                self.disconnect()
                return
        return super().dispatch_frame(channel, flags, payload)

    def dispatch_secure(self, channel, flags, message):
        from i30_receiver import schema
        from i30_receiver.protocol import INPUT, input_code
        code = int.from_bytes(message[:2], 'big')
        if channel == 1:
            if code == 8 and message[2:] == b'\x08\x00':
                self.service_frame(b'\x80\x02', 1)
            elif code == input_code('KEY_BINDING_RESPONSE') and message[2:] == b'\x08\x00':
                self.input_bound = True
            else:
                assert code == input_code('INPUT_REPORT') and self.input_bound
                report = schema.parse(INPUT + 'message.InputReport', message[2:])
                event = report.touch_event
                point, = event.pointer_data
                assert not point.pointer_id and not event.action_index
                assert not self.touch_reports or report.timestamp > self.touch_reports[-1][3]
                self.touch_reports.append((event.action, point.x, point.y, report.timestamp))
                if self.failure == 'touch':
                    self.disconnect()
                elif not self.soak and self.video_acks == len(self.frames) and len(self.touch_reports) == len(self.gesture):
                    self.end_video()
        elif message.startswith(b'\x00\x06'):
            self.services = schema.parse(schema.CTL + 'ServiceDiscoveryResponse', message[2:])
            assert [item.id for item in self.services.channels] == [3, 1]
            touch = self.services.channels[1].input_source_service
            assert [(entry.width, entry.height) for entry in touch.touchscreen] == [(800, 480)]
            assert not touch.keycodes_supported
            self.service_frame(b'\x00\x07\x08\x00\x10\x01', 1, 4)
            self.service_frame(b'\x00\x12\x08\x01')
        elif message == b'\x00\x0c\x08\x7b' and self.soak:
            self.pongs += 1
            if self.pongs in (6, 30, 90, 180):
                self.long_checkpoints.append(self.pongs * 10)
                self.frame_times.append(monotonic())
                self.service_frame(bytes(10) + self.frames[0], 3)
            else:
                self.advance_soak()
        else:
            super().dispatch_secure(channel, flags, message)

    def disconnect(self):
        self.pending.clear()
        self.dropped = True

    def bulk(self, pipe, callback, context, flag, size, data, pa):
        if self.dropped:
            return 0
        if flag & 0x80 and self.video_active and not self.pending and self.empty_receive:
            transfer = self.issue(0)
            self.empty_reads += 1
            if self.empty_receive == 'pending':
                self.waiting_read = transfer, data, size
            return transfer
        return super().bulk(pipe, callback, context, flag, size, data, pa)

    def complete(self, transfer, *_):
        if self.waiting_read and transfer == self.waiting_read[0]:
            if not self.pending:
                return 0
            _, destination, size = self.waiting_read
            packet = bytes(self.pending[:size])
            del self.pending[:size]
            self.cpu.mem_write(destination, packet)
            self.transfers[transfer] = len(packet)
            self.waiting_read = None
        return super().complete(transfer)

    def advance_soak(self):
        if self.pongs == 180:
            self.end_video()
            return
        self.ms += 10_000
        self.service_frame(b'\x00\x0b\x08\x7b')

    def end_video(self):
        if not self.goodbye_sent:
            self.goodbye_sent = True
            self.service_frame(b'\x00\x0f\x08\x01')

    def send_video(self, index):
        data = self.frames[index]
        if self.motion:
            from i30_receiver.wire import ENCRYPTED, Message, encode

            def encrypt(plaintext):
                assert self.peer.write(plaintext) == len(plaintext)
                return self.outbox.read()

            for frame in encode(Message(3, ENCRYPTED, 0, bytes(8) + data), encrypt, fragment_size=8192):
                self.pending.extend(frame)
        else:
            self.service_frame(bytes(10) + data, 3, fragment=11 if not index else None)

    def video_reply(self, flags, message):
        code = int.from_bytes(message[:2], 'big')
        if code == 0x8008:
            if message[3] == 2 and self.camera_active:
                self.disconnect()
                return
            self.started_video = self.ms
            self.frame_times.append(monotonic())
            self.send_video(0)
            if self.failure == 'fragment':
                del self.pending[80:]
        elif code == 0x8004:
            self.video_acks += 1
            self.frame_times[-1] = 1000 * (monotonic() - self.frame_times[-1])
            if self.on_frame is not None:
                self.on_frame(self.video_acks)
            if self.failure == 'reverse':
                self.camera_active = True
                self.service_frame(b'\x00\x0b\x08\x7b')
            elif self.soak:
                self.advance_soak()
            elif self.restart and self.video_acks == 1:
                self.service_frame(b'\x80\x02', 3)
                self.service_frame(b'\x80\x00\x08\x03', 3)
            elif self.video_acks < len(self.frames):
                self.ms += (self.video_acks * 1000 // self.fps - (self.video_acks - 1) * 1000 // self.fps)
                self.frame_times.append(monotonic())
                self.send_video(self.video_acks)
            else:
                # Give the bidirectional input pump a new read boundary even for a short clip.
                self.ms += 21
                if len(self.touch_reports) == len(self.gesture):
                    self.end_video()
                elif not self.empty_receive:
                    self.service_frame(b'\x00\x0b\x08\x7b')
        else:
            super().video_reply(flags, message)


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


def replace_test_validity(cert, start, end):
    # Test only the local validity parser. The modified certificate is never enrolled at the peer.
    def sequence(body):
        return b'\x30\x82' + len(body).to_bytes(2, 'big') + body

    assert cert[:2] == cert[4:6] == b'\x30\x82'
    tbs_end = 8 + int.from_bytes(cert[6:8], 'big')
    tbs = cert[8:tbs_end]
    validity = re.search(rb'\x30\x1e\x17\x0d[0-9]{12}Z\x17\x0d[0-9]{12}Z', tbs)
    fields = b''.join(bytes((tag, len(value))) + value for tag, value in (start, end))
    tbs = tbs[:validity.start()] + bytes((0x30, len(fields))) + fields + tbs[validity.end():]
    return sequence(sequence(tbs) + cert[tbs_end:])


def test_tls(path, openssl, exercise_projection=False, reject_rgb565=False):
    sys.path.insert(0, str(FORMAT.parents[2] / 'src'))
    from i30_receiver.mock import test_identity

    missing = UsbClient(path, 'version')
    missing.events.update({7: 'Version', 8: 'AuthRequired'})
    result = missing.attach()
    missing_status = ['Switch', 'Version', 'AuthRequired', 'Ready']
    assert result['accepted'] and result['signals'] == missing_status, result

    with test_identity(openssl) as (cert, key, context):
        reference_cipher = 'ECDHE-RSA-AES128-GCM-SHA256'
        context.set_ciphers(reference_cipher)
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
        assert verified.peer.cipher() == (reference_cipher, 'TLSv1.2', 128)
        fingerprint = sha256(verified.peer.getpeercert(binary_form=True)).hexdigest()
        assert fingerprint == sha256(cert_der).hexdigest()
        assert f'i30 CE TLS loaded leaf SHA-256: {fingerprint}' in good['debug'], good
        assert f'i30 CE TLS sent leaf SHA-256: {fingerprint}' in good['debug'], good
        assert f'i30 CE TLS received phone leaf SHA-256: {sha256(cert_der).hexdigest()}' in good['debug'], good
        for stage in ('handshake message received: 2', 'handshake message received: 11',
                      'handshake message received: 13', 'handshake message sent: 15',
                      'ChangeCipherSpec received.', 'negotiated version (decimal): 771'):
            assert f'i30 CE TLS {stage}' in good['debug'], good
        assert 'i30 CE Android Auto AUTH_COMPLETE sent.' in good['debug'], good
        wrong = TlsUsbClient(path, dict(files, **{'i30-peer.txt': b'other.invalid'}), context)
        denied = wrong.attach()
        assert not wrong.authenticated and denied['debug'][-2:] == [
            'i30 CE TLS BearSSL error: 56', 'i30 CE TLS phone certificate hostname does not match.'], denied
        report = {'projection_without_credentials': missing_status,
                  'mutual_tls': good['debug'][-1], 'negotiated_cipher': reference_cipher,
                  'loaded_and_sent_leaf_fingerprint': 'matches certificate independently received by TLS peer',
                  'media_channels': len(verified.services.channels),
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
        assert result['debug'][-1] == 'i30 CE TLS phone rejected the head unit certificate chain (unknown CA).', result
        report['client_chain'] = 'A TLS peer requiring the intermediate accepted the full PEM chain and rejected the leaf alone'

        leaf_der = ssl.PEM_cert_to_DER_cert(leaf.read_text(encoding='ascii'))
        damaged_leaf = ssl.DER_cert_to_PEM_cert(leaf_der[:-1] + bytes((leaf_der[-1] ^ 1,))).encode('ascii')
        for broken_chain in (leaf.read_bytes() + cert.read_bytes() + intermediate.read_bytes(),
                             damaged_leaf + intermediate.read_bytes()):
            guest = TlsUsbClient(path, dict(chain_files, **{'i30-client.pem': broken_chain}), context)
            result = guest.attach()
            assert result['debug'][-1] == 'i30 CE TLS head unit certificate chain invalid.', result
            assert not guest.authenticated and 'i30 CE TLS ClientHello sent.' not in result['debug'], result
        report['bad_client_chain'] = 'Misordered issuer and altered leaf signature rejected before ClientHello'

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
        for overrides, reason in (({}, 'missing'), ({'i30-client.der': None, 'i30-client.pem': pem}, 'unreadable'),
                                  ({'i30-client.der': b'broken', 'i30-client.pem': pem}, 'format invalid')):
            bad_files = dict(pem_files)
            del bad_files['i30-client.pem']
            result = TlsUsbClient(path, dict(bad_files, **overrides), context).attach()
            assert reason in result['debug'][-2], result
            assert 'i30 CE TLS ClientHello sent.' not in result['debug'], result
        report['invalid_identity_files'] = 'Missing or malformed enrollment rejected without sending an alternate identity'

        start = (0x17, b'491231235959Z')
        end = (0x18, b'20500101000000Z')
        midnight = int(datetime(2050, 1, 1, tzinfo=timezone.utc).timestamp())
        for fields, clock, reason in (
                (((0x17, b'491231165959-0700'), end), midnight, 'certificate decoder result: 48'),
                (((0x17, b'490231235959Z'), end), midnight, 'certificate decoder result: 48'),
                ((start, end), midnight - 2, 'certificate is not yet valid'),
                ((start, end), midnight - 1, 'ClientHello sent.'),
                ((start, end), midnight, 'ClientHello sent.'),
                ((start, end), midnight + 1, 'certificate expired')):
            fixture = replace_test_validity(cert_der, *fields)
            guest = TlsUsbClient(path, dict(files, **{'i30-client.der': fixture}), context, clock=clock, silent=True)
            result = guest.attach()
            assert any(reason in entry for entry in result['debug']), result
            assert ('i30 CE TLS ClientHello sent.' in result['debug']) == (reason == 'ClientHello sent.'), result
            assert not guest.authenticated, result
        report['der_validity'] = 'Offset and impossible date rejected; both UTC endpoints accepted across 2049/2050 midnight'

        quiet = TlsUsbClient(path, files, context, silent=True)
        result = quiet.attach()
        assert result['debug'][-1] == 'i30 CE TLS USB read interrupted while waiting for the phone.', result
        assert 'i30 CE USB transfer timed out.' in result['debug'], result
        assert 'i30 CE Android Auto AUTH_COMPLETE sent.' not in result['debug'], result
        report['silent_phone'] = result['debug'][-1]
        incompatible = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        incompatible.load_cert_chain(cert, key)
        incompatible.minimum_version = ssl.TLSVersion.TLSv1_3
        result = TlsUsbClient(path, files, incompatible).attach()
        assert result['debug'][-3:] == ['i30 CE TLS BearSSL error: 326', 'i30 CE TLS peer fatal alert: 70',
                                        'i30 CE TLS phone sent a fatal alert.'], result
        report['tls_alert'] = result['debug'][-3:]
        no_shared_cipher = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        no_shared_cipher.minimum_version = no_shared_cipher.maximum_version = ssl.TLSVersion.TLSv1_2
        no_shared_cipher.load_cert_chain(cert, key)
        no_shared_cipher.set_ciphers('DHE-RSA-AES128-GCM-SHA256')
        cipher_guest = TlsUsbClient(path, files, no_shared_cipher)
        result = cipher_guest.attach()
        assert not cipher_guest.authenticated and cipher_guest.peer_error == 'NO_SHARED_CIPHER', result
        assert 'i30 CE TLS peer fatal alert: 40' in result['debug'], result
        report['no_shared_cipher'] = {'peer_error': cipher_guest.peer_error, 'guest_alert': 40}
        pin_files = {name: data for name, data in files.items() if name != 'i30-peer.txt'}
        pin_files['i30-peer-sha256.txt'] = sha256(cert_der).hexdigest().encode('ascii') + b'\r\n'
        pinned = TlsUsbClient(path, pin_files, context)
        result = pinned.attach()
        assert pinned.authenticated and pinned.closed_gracefully, result
        wrong_pin = TlsUsbClient(path, dict(pin_files, **{'i30-peer-sha256.txt': b'0' * 64}), context)
        result = wrong_pin.attach()
        assert not wrong_pin.authenticated and result['debug'][-2:] == [
            'i30 CE TLS BearSSL error: 62', 'i30 CE TLS phone certificate fingerprint does not match.'], result
        with test_identity(openssl) as (other_cert, other_key, _):
            bad_ca = ssl.PEM_cert_to_DER_cert(other_cert.read_text(encoding='ascii'))
            untrusted = TlsUsbClient(path, dict(pin_files, **{'i30-ca.der': bad_ca}), context)
            result = untrusted.attach()
            assert not untrusted.authenticated and result['debug'][-2:] == [
                'i30 CE TLS BearSSL error: 62', 'i30 CE TLS phone certificate chain has no trusted anchor.'], result
            result = TlsUsbClient(path, dict(pem_files, **{'i30-client-key.pem': other_key.read_bytes()}), context).attach()
            assert result['debug'][-1] == 'i30 CE TLS head unit certificate and RSA key do not match.', result
            report['key_mismatch'] = result['debug'][-1]
        report['fingerprint'] = 'matching chain and pin accepted; mismatched pin or CA rejected'
        aare_files = dict(files, **{'i30-aare.opt': b'1\n', 'i30-aare-ca.der': cert_der,
                                  'i30-aare-client.der': cert_der, 'i30-aare-client-key.der': key_der,
                                  'i30-aare-peer-sha256.txt': pin_files['i30-peer-sha256.txt']})
        aare = TlsUsbClient(path, aare_files, context)
        result = aare.attach()
        assert aare.authenticated and aare.closed_gracefully, result
        for name in ('trust anchor', 'expected phone leaf', 'received phone leaf'):
            assert f'i30 CE TLS {name} SHA-256: {fingerprint}' in result['debug'], result
        refused = TlsUsbClient(path, dict(aare_files, **{'i30-aare-peer-sha256.txt': b'0' * 64}), context)
        result = refused.attach()
        assert refused.peer_error == 'TLSV1_ALERT_ACCESS_DENIED' and not refused.authenticated, result
        with test_identity(openssl) as (other_cert, _, _):
            aare_other_ca = ssl.PEM_cert_to_DER_cert(other_cert.read_text(encoding='ascii'))
            refused = TlsUsbClient(path, dict(aare_files, **{'i30-aare-ca.der': aare_other_ca}), context)
            result = refused.attach()
            assert refused.peer_error == 'TLSV1_ALERT_UNKNOWN_CA' and not refused.authenticated, result
        del aare_files['i30-aare-peer-sha256.txt']
        aare = TlsUsbClient(path, aare_files, context)
        result = aare.attach()
        assert not aare.authenticated and 'i30 CE TLS ClientHello sent.' not in result['debug'], result
        report['aare_profile'] = ('AARE enrollment succeeds; unknown CA and mismatched pin produce fatal alerts; '
                                  'missing AARE pin never falls back to legacy credentials')
        if exercise_projection:
            import av
            codec = av.CodecContext.create('libx264', 'w')
            codec.width, codec.height, codec.pix_fmt = 800, 480, 'yuv420p'
            codec.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline'}
            frame = av.VideoFrame(800, 480, 'yuv420p')
            for plane, value in zip(frame.planes, (81, 90, 240)):
                plane.update(bytes([value]) * plane.buffer_size)
            sample = b''.join(bytes(packet) for packet in (*codec.encode(frame), *codec.encode(None)))
            for mode in ('video', 'display_preemption', 'video_deadline', 'interleaved_control'):
                preempt, deadline = mode == 'display_preemption', mode == 'video_deadline'
                interleaved = mode == 'interleaved_control'
                projected = TlsUsbClient(path, files, context, video=sample, preempt=preempt,
                                         video_deadline=deadline, interleave_control=interleaved)
                result = projected.attach()
                painted = projected.painted_frames()
                assert painted == (2 if preempt else 1) and not projected.allocations, result
                assert projected.video_acks == (3 if preempt else 1)
                assert projected.closed_gracefully != deadline
                assert projected.audio_focus_denied
                assert projected.pongs == int(interleaved), result
                assert projected.ms >= 8900
                assert projected.focus_history == ([(1, 0), (2, 1), (1, 1)] if preempt else [(1, 0)])
                assert 'i30 CE projection frame presented.' in result['debug']
                if projected.video_format == 'ddraw':
                    assert projected.ddraw['shows'] == painted
                    assert projected.ddraw['locks'] == projected.ddraw['unlocks'] == painted
                    assert not projected.blit_times
                    assert all(count == 0 for count in projected.ddraw['refs'].values())
                    report[mode] = {'debug': result['debug'][2:], 'ddraw': {
                        'shows': projected.ddraw['shows'], 'locks': projected.ddraw['locks'],
                        'unlocks': projected.ddraw['unlocks'], 'hides': projected.ddraw['hides'],
                        'live_references': sum(projected.ddraw['refs'].values())}}
                else:
                    assert projected.projected == painted
                    report[mode] = result['debug'][2:]
            if reject_rgb565:
                assert artifact_video_format(path) == 'rgb565', 'fallback fixture requires an RGB565 build'
                fallback = TlsUsbClient(path, files, context, video=sample)
                fallback.reject_rgb565 = True
                result = fallback.attach()
                assert fallback.rejected_rgb565 and fallback.projected == 1 and not fallback.allocations, result
                assert 'i30 CE GDI rejected 16-bit DIB; using BGRA fallback.' in result['debug'], result
                report['rgb565_fallback'] = '16-bit DIB rejection recovered with the validated BGRA blit'
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
        self.wake_posts = 0
        self.keys = [r'Drivers\USB\ClientDrivers' + self.KEY_SUFFIX]
        self.keys.extend(r'Drivers\USB\LoadClients' + '\\' + group + self.KEY_SUFFIX for group in (
            r'6353_11520\Default\255', r'6353_11521\Default\255', r'1256_26720\Default\Default'))

    def GetCommandLineW(self, *_):
        if self.case in ('cancel', 'preferences'):
            value = ''
        elif self.case == 'clock-boot':
            value = '-i30clock'
        elif self.case == 'wake':
            value = '-i30wake'
        elif self.case in ('boot-disabled', 'resident', 'usb-auto'):
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
        assert struct.unpack('<H', self.cpu.mem_read(template + 8, 2))[0] == 6
        title = self.text(template + 22)
        cursor = (template + 24 + len(title.encode('utf-16-le')) + 3) & ~3
        controls = []
        for _ in range(6):
            style, _, _, _, _, _, control, kind, control_type = struct.unpack(
                '<II7H', self.cpu.mem_read(cursor, 22))
            label = self.text(cursor + 22)
            controls.append((control, kind, control_type, style & 15))
            cursor = (cursor + 26 + len(label.encode('utf-16-le')) + 3) & ~3
        assert controls == [(1003, 0xffff, 0x80, 3), (1005, 0xffff, 0x80, 3),
                            (1004, 0xffff, 0x82, 0), (1, 0xffff, 0x80, 1),
                            (2, 0xffff, 0x80, 0), (1002, 0xffff, 0x80, 0)]
        self.dialog = callback - self.base
        return 2

    def GetDlgItem(self, window, control, *_):
        assert window == 20
        return control

    def SetWindowPos(self, window, sibling, x, y, width, height, flags):
        assert (window, sibling, x, y, width, height, flags) == (20, 0, 194, 116, 0, 0, 0x15)
        return 1

    def SendMessageW(self, checkbox, message, selected, reserved, *_):
        assert checkbox in (1003, 1005) and not reserved
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
        path = self.text(name)
        if path in self.files:
            self.files.remove(path)
            return 1
        return 0

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
        if name in (r'\DiskA\i30auto.opt', r'\DiskA\i30boot.opt',
                    r'\DiskA\i30-aa-usb-pending.opt'):
            if self.case == 'resident':
                return 0x80 if name.endswith('i30auto.opt') and self.polls < 3 else 0xffffffff
            if self.case == 'usb-auto':
                return 0x80 if name.endswith('i30auto.opt') or name in self.files else 0xffffffff
            if self.case in ('preferences', 'boot-disabled', 'clock-boot'):
                return 0x80 if name in self.files else 0xffffffff
            return 0x80 if name.endswith('i30auto.opt') else 0xffffffff
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
        if self.case in ('wake', 'usb-auto'):
            return 0x5678
        assert self.case.startswith('owner-'), self.case
        return 0x1234abcd if self.case == 'owner-current' else 0x5678

    def FindWindowW(self, name, title, *_):
        assert self.text(name) == 'I30.GD13MY.NavigationProjection.1' and not title
        return 0x3456 if self.wake_posts >= 2 else 0

    def PostMessageW(self, window, message, wparam, lparam, *_):
        assert self.case in ('wake', 'usb-auto')
        assert (window, message, wparam, lparam) == (0x5678, 0x0200, 0, (479 << 16) | 790)
        self.wake_posts += 1
        return 1

    def GetLastError(self, *_):
        return 183 if self.case == 'already-running' else 0

    def Sleep(self, milliseconds, *_):
        assert self.case in ('wake', 'usb-auto') and milliseconds == 500
        return 0

    def EventModify(self, gate, operation, *_):
        if self.case.startswith('owner-'):
            assert (gate, operation) == (20, 3)
            return 1
        if operation == 2:
            assert self.case in ('resident', 'usb-auto') and gate in (3, 4)
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
        assert (count, wait_all, timeout) == (2, 0, 1000 if self.case in ('resident', 'usb-auto') else 35000)
        assert [self.word(values + i * 4) for i in range(2)] == [3, 4]
        assert set(self.values) == set(self.keys) and all(self.values[key] for key in self.keys[1:])
        if self.case in ('resident', 'usb-auto'):
            if self.case == 'usb-auto':
                return 0
            result = (1, 1, 258)[self.polls]
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
                'result': self.messages[-1] if self.messages else 'skipped', 'status_resets': self.resets,
                'files': sorted(self.files)}

    def exercise_preferences(self):
        self.start()
        assert self.dialog is not None
        self.run(self.dialog, (20, 0x110, 0, 0))
        assert self.checks == {1003: 0, 1005: 0}
        self.checks[1003] = 1
        self.run(self.dialog, (20, 0x111, 1, 0))
        assert self.files == {r'\DiskA\i30auto.opt'}
        self.run(self.dialog, (20, 0x110, 0, 0))
        assert self.checks == {1003: 1, 1005: 0}
        self.checks[1005] = 1
        self.run(self.dialog, (20, 0x111, 1, 0))
        assert self.files == {r'\DiskA\i30auto.opt', r'\DiskA\i30boot.opt'}
        self.run(self.dialog, (20, 0x110, 0, 0))
        assert self.checks == {1003: 1, 1005: 1}
        self.checks[1003] = 0
        self.run(self.dialog, (20, 0x111, 1, 0))
        assert self.files == {r'\DiskA\i30boot.opt'}
        self.run(self.dialog, (20, 0x110, 0, 0))
        assert self.checks == {1003: 0, 1005: 1}
        self.checks[1005] = 0
        self.run(self.dialog, (20, 0x111, 1, 0))
        assert not self.files
        self.run(self.dialog, (20, 0x111, 1002, 0))
        assert 'No supported phone' in self.messages[-1]
        assert not self.values and self.removed == list(reversed(self.registrations))
        return 'Both auto-run flags default off, persist independently, and clear cleanly'


def stress_frames(fps, count=8, width=800, motion=False):
    import av
    codec = av.CodecContext.create('libx264', 'w')
    codec.width, codec.height, codec.pix_fmt = width, 480, 'yuv420p'
    codec.time_base = Fraction(1, fps)
    codec.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline',
                     'g': str(4 if count <= 8 else fps), 'sc_threshold': '0'}
    if motion:
        codec.bit_rate = {15: 384_000, 24: 768_000, 30: 1_500_000}[fps]
        graph = av.filter.Graph()
        source = graph.add('testsrc2', f'size={width}x480:rate={fps}')
        sink = graph.add('buffersink')
        source.link_to(sink)
        graph.configure()
    packets = []
    for index in range(count):
        if motion:
            frame = sink.pull()
        else:
            frame = av.VideoFrame(width, 480, 'yuv420p')
            frame.pts = index
            for plane, value in zip(frame.planes, (81, 90, 240)):
                plane.update(bytes([value]) * plane.buffer_size)
            luma = memoryview(frame.planes[0])
            for row in range(16, 112):
                offset = row * frame.planes[0].line_size + index * 17 % (width - 64)
                luma[offset:offset + 64] = b'\xeb' * 64
        packet, = codec.encode(frame)
        packets.append((bytes(packet), packet.is_keyframe))
    return packets


def test_separate_video_config(path, files, peer, access_unit):
    """Send untimed SPS/PPS before the first timed IDR and again after STOP."""
    starts = list(re.finditer(rb'\x00\x00(?:\x00)?\x01', access_unit))
    units = [(access_unit[marker.end()] & 31,
              access_unit[marker.start():starts[index + 1].start() if index + 1 < len(starts) else len(access_unit)])
             for index, marker in enumerate(starts)]
    assert starts and starts[0].start() == 0
    assert [kind for kind, _ in units if kind in (7, 8)] == [7, 8]
    assert any(kind == 5 for kind, _ in units)
    config = b''.join(nal for kind, nal in units if kind in (7, 8))
    picture = b''.join(nal for kind, nal in units if kind not in (7, 8))

    class SeparateConfig(NativeUsbStress):
        pending_config = False
        config_acks = 0

        def send_video(self, _index):
            assert self.painted_frames() == self.config_acks
            self.pending_config = True
            self.service_frame(b'\x00\x01' + config, 3, fragment=9,
                               between=b'\x00\x0b\x08\x7b')

        def video_reply(self, flags, message):
            if message.startswith(b'\x80\x04'):
                assert flags == 11 and message[2:] == b'\x08\x23\x10\x01'
                if self.pending_config:
                    assert self.painted_frames() == self.config_acks
                    self.pending_config = False
                    self.config_acks += 1
                    self.service_frame(struct.pack('>HQ', 0, self.ms * 1000) + picture, 3, fragment=11)
                    return
            super().video_reply(flags, message)

    guest = SeparateConfig(path, files, peer, [picture] * 2, restart=True)
    result = guest.attach()
    assert guest.authenticated and guest.closed_gracefully and not guest.allocations, result
    assert guest.config_acks == guest.painted_frames() == guest.video_acks == guest.pongs == 2, result
    return {'config_nals': [7, 8], 'config_ack_count': guest.config_acks,
            'timed_idr_ack_count': guest.video_acks, 'painted': guest.painted_frames(),
            'interleaved_pongs': guest.pongs, 'live_allocations_after_close': len(guest.allocations)}


def test_stress(path, openssl, rounds):
    sys.path.insert(0, str(FORMAT.parents[2] / 'src'))
    from i30_receiver.mock import test_identity

    with test_identity(openssl) as (cert, key, peer):
        files = {'i30-ca.pem': cert.read_bytes(), 'i30-peer.txt': b'i30-mock.local',
                 'i30-client.pem': cert.read_bytes(), 'i30-client-key.pem': key.read_bytes()}
        streams = []
        one_frame = None
        for fps in (15, 24, 30):
            packets = stress_frames(fps)
            frames = [item[0] for item in packets]
            one_frame = frames[:1]
            guest = NativeUsbStress(path, files, peer, frames, fps=fps)
            result = guest.attach()
            assert guest.authenticated and guest.closed_gracefully and guest.input_bound, result
            assert guest.painted_frames() == guest.video_acks == len(frames), result
            assert [event[:3] for event in guest.touch_reports] == list(guest.gesture), result
            assert not guest.allocations and not guest.video_active and not guest.touch_armed, result
            streams.append({'nominal_fps': fps, 'sent': len(frames), 'acked': guest.video_acks,
                            'painted': guest.painted_frames(), 'keyframes': sum(item[1] for item in packets),
                            'bytes': sum(map(len, frames)), 'peak_guest_requested_bytes': guest.peak_bytes,
                            'frame_ack_wall_ms': guest.frame_times, 'touches': guest.touch_reports})

        keepalive = NativeUsbStress(path, files, peer, one_frame, soak=True)
        result = keepalive.attach()
        assert keepalive.closed_gracefully and keepalive.pongs == 180, result
        assert keepalive.painted_frames() == keepalive.video_acks == 5 and not keepalive.allocations, result
        assert keepalive.long_checkpoints == [60, 300, 900, 1800], result

        abrupt = {}
        for failure in ('tls', 'auth-complete', 'fragment', 'touch', 'reverse'):
            guest = NativeUsbStress(path, files, peer, one_frame, failure=failure)
            result = guest.attach()
            assert not guest.closed_gracefully and not guest.allocations and not guest.video_active and not guest.touch_armed, result
            assert guest.painted_frames() == (failure in ('touch', 'reverse')), result
            abrupt[failure] = {'painted': guest.painted_frames(), 'touch_reports': len(guest.touch_reports),
                               'cleared_allocations': len(guest.allocations), 'transfers_closed': result['closed_transfers']}

        invalid_video = {
            'oversize': stress_frames(15, 1, width=816)[0][0],
            'idr_without_reference': b'\x00\x00\x00\x01\x05\x80',  # IDR requires nonzero nal_ref_idc.
        }
        rejected_video = {}
        for case, packet in invalid_video.items():
            guest = NativeUsbStress(path, files, peer, [packet])
            result = guest.attach()
            assert guest.authenticated and not guest.closed_gracefully and not guest.video_acks, result
            assert not guest.projected and not guest.allocations and not guest.video_active and not guest.touch_armed, result
            rejected_video[case] = {'displayed': guest.projected, 'acked': guest.video_acks,
                                    'live_allocations_after_close': len(guest.allocations)}
        restarted = NativeUsbStress(path, files, peer, one_frame * 2, restart=True)
        result = restarted.attach()
        assert restarted.closed_gracefully and restarted.painted_frames() == restarted.video_acks == 2, result
        assert not restarted.allocations and not restarted.video_active, result
        separate_config = test_separate_video_config(path, files, peer, one_frame[0])

        idle_input = {}
        for mode in ('pending', 'zlp'):
            guest = NativeUsbStress(path, files, peer, one_frame, empty_receive=mode)
            result = guest.attach()
            assert guest.closed_gracefully and guest.empty_reads and not guest.allocations, result
            assert [event[:3] for event in guest.touch_reports] == list(guest.gesture), result
            idle_input[mode] = {'touch_reports': len(guest.touch_reports), 'usb_reads': guest.empty_reads,
                                'transient_ui_timeout': guest.tested_ipc_timeout}

        peak = set()
        milestones = []
        guest = NativeUsbStress(path, files, peer, one_frame)
        for index in range(1, rounds + 1):
            if index > 1:
                guest.reconnect(peer)
            result = guest.attach()
            assert guest.closed_gracefully and guest.video_acks == guest.painted_frames() == 1, result
            assert [event[:3] for event in guest.touch_reports] == list(guest.gesture), result
            assert not guest.allocations and not guest.video_active and not guest.touch_armed, result
            peak.add(guest.peak_bytes)
            if index in (5, 10, 30) or index == rounds:
                milestones.append(index)
        guest.cpu.hook_del(guest.dispatch_hook)
        return {'streams': streams, 'resident_virtual_seconds': keepalive.long_checkpoints,
                'resident_pongs': keepalive.pongs, 'resident_painted_frames': keepalive.painted_frames(),
                'abrupt_cleanup': abrupt, 'video_oversize_rejected': True, 'video_restart_painted_frames': 2,
                'input_while_phone_idle': idle_input, 'separate_codec_config': separate_config,
                'rejected_video': rejected_video,
                'completed_session_checkpoints': milestones,
                'peak_requested_bytes_across_attaches': sorted(peak), 'live_allocations_after_each_attach': 0}


def arm_video_profile(guest, path):
    abi = json.loads(path.with_name('abi.json').read_text(encoding='utf-8'))[path.name]
    assert sha256(path.read_bytes()).hexdigest() == abi['sha256']
    labels = {'h264bsdDecode': 'decode', 'h264bsdNextOutputPictureBGRA': 'bgra_conversion',
              'h264bsdConvertToBGRA': 'fallback_bgra_conversion',
              'i30_yuv420_to_rgb565': 'rgb565_conversion', 'i30_video_push': 'video_push'}
    started = {}
    returns = {}
    per_frame = []
    cpu = guest.cpu

    def finish(_cpu, address, _size, _data):
        entry = started.pop(address, None)
        if entry is None:
            return
        label, began = entry
        while len(per_frame) <= guest.video_acks:
            per_frame.append({name + '_ms': 0.0 for name in labels.values()})
        per_frame[guest.video_acks][label + '_ms'] += 1000 * (monotonic() - began)

    def begin(driver, _address, _size, label):
        address = driver.reg_read(UC_ARM_REG_LR) & ~1
        if address not in returns:
            returns[address] = driver.hook_add(UC_HOOK_CODE, finish, begin=address, end=address)
            driver.ctl_flush_tb()
        started[address] = label, monotonic()

    for name, label in labels.items():
        rva = abi['video_profile_rvas'].get(name)
        if rva is None:  # The other color path is removed by --gc-sections.
            continue
        address = guest.base + rva
        cpu.hook_add(UC_HOOK_CODE, begin, label, begin=address, end=address)
    return per_frame


def arm_h264_function_profile(guest, path):
    """Aggregate inclusive wall time from GCC -finstrument-functions hooks.

    Only the two compiler hook stubs are trapped, so this ranks functions with
    much lower observer overhead than hooking every decoder call. Nested calls
    are intentionally counted in their parents; exclusive self time is not
    inferred. The fixture cannot imply real-device cycle or millisecond cost.
    """
    abi = json.loads(path.with_name('abi.json').read_text(encoding='utf-8'))[path.name]
    assert sha256(path.read_bytes()).hexdigest() == abi['sha256']
    rvas = abi.get('video_function_rvas', {})
    hooks = abi.get('profile_hook_rvas', {})
    if not rvas or not all(name in hooks for name in ('__cyg_profile_func_enter', '__cyg_profile_func_exit')):
        return {}
    stats = {name: {'calls': 0, 'inclusive_ms': 0.0} for name in rvas}
    names = {guest.base + rva: name for name, rva in rvas.items()}
    stack = []

    def enter(driver, _address, _size, _data):
        name = names.get(driver.reg_read(UC_ARM_REG_R0) & ~1, 'unknown')
        stack.append((name, monotonic()))

    def leave(driver, _address, _size, _data):
        now = monotonic()
        name = names.get(driver.reg_read(UC_ARM_REG_R0) & ~1, 'unknown')
        index = len(stack) - 1
        while index >= 0 and stack[index][0] != name:
            index -= 1
        if index < 0:
            return
        _, began = stack.pop(index)
        row = stats.setdefault(name, {'calls': 0, 'inclusive_ms': 0.0})
        row['calls'] += 1
        row['inclusive_ms'] += 1000 * (now - began)

    for name in ('__cyg_profile_func_enter', '__cyg_profile_func_exit'):
        callback = enter if name.endswith('enter') else leave
        guest.cpu.hook_add(UC_HOOK_CODE, callback, begin=guest.base + hooks[name],
                           end=guest.base + hooks[name])
    return stats


def test_continuous(path, openssl, seconds, fps, progress, motion, profile, internal_profile=False):
    sys.path.insert(0, str(FORMAT.parents[2] / 'src'))
    from i30_receiver.mock import test_identity

    packets = stress_frames(fps, count=seconds * fps, motion=motion)
    frames = [packet for packet, _ in packets]
    with test_identity(openssl) as (cert, key, peer):
        files = {'i30-ca.pem': cert.read_bytes(), 'i30-peer.txt': b'i30-mock.local',
                 'i30-client.pem': cert.read_bytes(), 'i30-client-key.pem': key.read_bytes()}
        guest = NativeUsbStress(path, files, peer, frames, fps=fps, motion=motion)
        # This is a bounded bench execution budget. Guest time is advanced by the sender cadence.
        budget = 300_000_000 if internal_profile else 60_000_000
        guest.timeout_us = max(budget, len(frames) * 1_200_000)
        guest.instruction_limit = 0
        counters = arm_video_profile(guest, path) if profile else []
        function_stats = arm_h264_function_profile(guest, path) if internal_profile else {}
        wall, cpu = monotonic(), process_time()
        if progress is not None:
            checkpoints = {fps * minutes * 60 for minutes in (1, 5, 15, 30)}

            def record(count):
                if count in checkpoints:
                    assert guest.projected == count
                    status = {'frames': count, 'guest_ms': guest.ms - guest.started_video,
                              'host_seconds': round(monotonic() - wall, 3), 'peak_guest_bytes': guest.peak_bytes}
                    with progress.open('a', encoding='utf-8') as ledger:
                        print(json.dumps(status), file=ledger)

            guest.on_frame = record
        result = guest.attach()
        wall, cpu = monotonic() - wall, process_time() - cpu
        assert guest.authenticated and guest.closed_gracefully and guest.input_bound, result
        assert guest.projected == guest.video_acks == len(frames) and not guest.allocations, result
        assert [event[:3] for event in guest.touch_reports] == list(guest.gesture), result
        if profile:
            conversion = 'rgb565_conversion_ms' if guest.rgb565 else 'bgra_conversion_ms'
            assert len(counters) == len(frames) and all(frame['decode_ms'] and frame[conversion]
                                                       for frame in counters)
        functions = []
        if internal_profile:
            assert function_stats and function_stats['h264bsdDecode']['calls'], function_stats
            functions = [{'function': name, **values} for name, values in function_stats.items() if values['calls']]
            functions.sort(key=lambda row: row['inclusive_ms'], reverse=True)
        return {'nominal_stream_seconds': seconds, 'nominal_fps': fps, 'simulated_video_ms': guest.ms - guest.started_video,
                'sent': len(frames), 'acked': guest.video_acks, 'painted': guest.projected,
                'keyframes': sum(keyframe for _, keyframe in packets), 'bytes': sum(map(len, frames)),
                'largest_access_unit_bytes': max(map(len, frames)), 'moving_test_pattern': motion,
                'center_pixel_colors': len(guest.pixel_samples),
                'peak_guest_requested_bytes': guest.peak_bytes, 'live_allocations_after_close': len(guest.allocations),
                'wall_seconds': round(wall, 3), 'host_cpu_seconds': round(cpu, 3),
                'frame_ack_wall_ms': guest.frame_times, 'arm_function_wall_profile': counters,
                'arm_h264_function_profile': functions,
                'gdi_blit_wall_ms': [1000 * value for value in guest.blit_times],
                'median_gdi_blit_ms': round(1000 * statistics.median(guest.blit_times), 3),
                'video_format': 'rgb565' if guest.rgb565 else 'bgra'}


def test_stock_touch_route(path):
    from inspect_ce_pe import rom_exports
    from patch_gd13my_settings import THUNKS

    pe = pefile.PE(str(path))
    base = pe.OPTIONAL_HEADER.ImageBase
    section = next(section for section in pe.sections if section.Name.rstrip(b'\0') == b'.i30nav')
    iat, = pe.DIRECTORY_ENTRY_IMPORT[-1].imports
    dispatch_ordinal = rom_exports()['DispatchMessageW']
    dispatch, = (item for item in pe.DIRECTORY_ENTRY_IMPORT[0].imports if item.ordinal == dispatch_ordinal)
    results = {}
    for case, code, module, claimed in (('before-projection', 0x201, 0, 0), ('covered', 0x201, 1, 0),
                                        ('down', 0x201, 1, 1), ('move', 0x200, 1, 1), ('up', 0x202, 1, 1),
                                        ('popup-down', 0x201, 1, 1), ('popup-up', 0x202, 1, 1),
                                        ('timer-auto', 0x113, 1, 0), ('paint-auto', 0x00f, 1, 0),
                                        ('wake-auto', 0x200, 1, 1),
                                        ('non-pointer', 0x100, 1, 0)):
        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        image = pe.get_memory_mapped_image()
        cpu.mem_map(base, (len(image) + 0xfff) & ~0xfff)
        cpu.mem_write(base, image)
        cpu.mem_map(RAM, 0x10000)
        cpu.mem_map(STUB, 0x1000)
        hwnd, point = 0x1234, (790 | 479 << 16) if case == 'wake-auto' else 400 | 240 << 16
        popup = (hwnd if case.startswith('popup-') else 0x2345) if module else 0
        cpu.mem_write(RAM, struct.pack('<IIII', hwnd, code, 0, point))
        cpu.mem_write(iat.address, struct.pack('<I', STUB))
        cpu.mem_write(dispatch.address, struct.pack('<I', STUB + 8))
        cpu.reg_write(UC_ARM_REG_R0 + 9, RAM)  # ARM sb points to MSG.
        cpu.reg_write(UC_ARM_REG_R0 + 11, 24)  # Active stock navigation menu shot.
        cpu.reg_write(UC_ARM_REG_SP, STACK)
        cpu.reg_write(UC_ARM_REG_LR, MARK)
        calls = []

        def call(cpu, address, _size, _data):
            if address in (THUNKS['stock_resume'], THUNKS['stock_consumed']):
                calls.append('consumed' if address == THUNKS['stock_consumed'] else 'stock')
                cpu.emu_stop()
            elif address in (THUNKS['stock_find_window'], 0x2d030c, STUB, STUB + 4, STUB + 8):
                r0, r1, r2 = (cpu.reg_read(UC_ARM_REG_R0 + index) for index in range(3))
                if address == THUNKS['stock_find_window']:
                    assert bytes(cpu.mem_read(r0, 68)).decode('utf-16le').rstrip('\0') == 'I30.GD13MY.NavigationProjection.1'
                    assert not r1
                    value = popup
                    calls.append('find-window')
                elif address == 0x2d030c:
                    assert bytes(cpu.mem_read(r0, 22)).decode('utf-16le').rstrip('\0') == 'i30nav.dll'
                    value = module
                    calls.append('get-module')
                elif address == STUB:
                    assert r0 == module
                    auto = case in ('timer-auto', 'paint-auto') or (case in ('move', 'wake-auto') and 'auto-start' not in calls)
                    symbol = 'I30AutoStartProjection' if auto else 'I30RouteProjectionTouch'
                    actual_symbol = bytes(cpu.mem_read(r1, 96)).decode('utf-16le').split('\0', 1)[0]
                    assert actual_symbol == symbol, (case, calls, symbol, actual_symbol)
                    value = STUB + 4
                    calls.append('resolve')
                elif address == STUB + 4:
                    auto = case in ('timer-auto', 'paint-auto') or (case in ('move', 'wake-auto') and 'auto-start' not in calls)
                    if auto:
                        assert r0 == hwnd
                    else:
                        assert (r0, r1, r2) == (hwnd, code, point)
                    value = claimed
                    calls.append('auto-start' if auto else 'route')
                else:
                    assert r0 == RAM
                    assert struct.unpack('<IIII', cpu.mem_read(r0, 16)) == (hwnd, code, 0, point)
                    value = 0  # Dispatch returns the popup's WndProc return value.
                    calls.append('dispatch')
                cpu.reg_write(UC_ARM_REG_R0, value)
                cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

        code_hook = cpu.hook_add(UC_HOOK_CODE, call)
        cpu.emu_start(base + section.VirtualAddress, MARK, timeout=1_000_000, count=1000)
        cpu.hook_del(code_hook)
        expected = ['get-module', 'resolve', 'auto-start', 'find-window', 'get-module', 'resolve', 'route'] \
            if case in ('move', 'wake-auto') else (
            ['get-module', 'resolve', 'auto-start'] if case in ('timer-auto', 'paint-auto') else (
            [] if case == 'non-pointer' else ['find-window']))
        if case not in ('timer-auto', 'paint-auto', 'move', 'wake-auto') and popup == hwnd:
            expected.append('dispatch')
        elif expected and case not in ('timer-auto', 'paint-auto', 'move', 'wake-auto'):
            expected.append('get-module')
            if module:
                expected.extend(('resolve', 'route'))
        assert calls == expected + ['consumed' if claimed else 'stock'], (case, calls)
        assert cpu.reg_read(UC_ARM_REG_R0 + 3) == code
        assert cpu.reg_read(UC_ARM_REG_SP) == STACK
        results[case] = calls
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--tls-openssl', type=Path, help='Exercise the native TLS build with an ephemeral test identity')
    parser.add_argument('--projection', action='store_true', help='Run the native USB-to-GDI video and preemption test')
    parser.add_argument('--stress-rounds', type=int, default=0, help='Repeat full ARM projection and resource cleanup')
    parser.add_argument('--continuous-seconds', type=int, default=0, help='Run a nominal-length ARM video stream')
    parser.add_argument('--continuous-fps', type=int, choices=(15, 24, 30), default=15)
    parser.add_argument('--continuous-progress', type=Path, help='Save nominal video checkpoints as JSON lines')
    parser.add_argument('--motion-pattern', action='store_true', help='Use a higher-motion libavfilter source')
    parser.add_argument('--profile-video', action='store_true', help='Time decoder and BGRA functions in the ARM fixture')
    parser.add_argument('--profile-h264-functions', action='store_true',
                        help='Rank linked h264bsd functions by ARM fixture wall time')
    parser.add_argument('--navigation', type=Path, help='Exercise the stock input trampoline in a patched GDdNavi.exe')
    parser.add_argument('--reject-rgb565', action='store_true',
                        help='Reject one 16-bit DIB to verify the BGRA fallback (RGB565 builds only)')
    args = parser.parse_args()
    if not args.tls_openssl and (args.stress_rounds or args.continuous_seconds):
        parser.error('ARM stress and continuous video require --tls-openssl')
    if args.stress_rounds < 0 or args.continuous_seconds < 0:
        parser.error('Test lengths cannot be negative')
    if (args.continuous_progress or args.motion_pattern or args.profile_video or
            args.profile_h264_functions) and not args.continuous_seconds:
        parser.error('Video options require --continuous-seconds')
    client = {case: UsbClient(args.artifacts / 'i30usb.dll', case).attach()
              for case in ('switch', 'version', 'not-armed', 'storage', 'unsupported', 'wrong-interface',
                           'second-pipe-fails', 'timeout', 'version-disconnect')}
    assert client['switch']['accepted'] and client['switch']['controls'] == [51, 52, 52, 52, 52, 53]
    assert client['version']['accepted'] and client['version']['signals'] == ['Switch', 'Ready']
    assert client['version']['inputs'] == ['00030006000100010006']
    for case in ('timeout', 'version-disconnect'):
        assert client[case]['accepted'] and client[case]['signals'] == ['Switch', 'Failure']
    assert all(not client[case]['accepted'] for case in ('not-armed', 'storage', 'unsupported', 'wrong-interface',
                                                        'second-pipe-fails'))
    assert client['timeout']['wait_ms'] == 3000 and client['timeout']['closed_transfers'] == 1
    settings = {case: Settings(args.artifacts / 'i30aa.exe', case).start()
                for case in ('version-ok', 'version-failed', 'timeout', 'no-accessory-reenumeration', 'usb-auto', 'wake',
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
    assert settings['resident']['status_resets'] == [4, 4]
    assert settings['usb-auto']['result'].startswith('Phone answered')
    assert settings['usb-auto']['files'] == [r'\DiskA\i30-aa-usb-pending.opt']
    wake_test = Settings(args.artifacts / 'i30aa.exe', 'wake')
    wake_test.start()
    assert wake_test.wake_posts == 2
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
        report['native_tls'] = test_tls(args.artifacts / 'i30usb.dll', args.tls_openssl, args.projection,
                                        args.reject_rgb565)
    if args.stress_rounds:
        report['native_stress'] = test_stress(args.artifacts / 'i30usb.dll', args.tls_openssl, args.stress_rounds)
    if args.continuous_seconds:
        report['continuous_video'] = test_continuous(args.artifacts / 'i30usb.dll', args.tls_openssl,
                                                    args.continuous_seconds, args.continuous_fps,
                                                    args.continuous_progress, args.motion_pattern, args.profile_video,
                                                    args.profile_h264_functions)
    if args.navigation:
        report['stock_touch_route'] = test_stock_touch_route(args.navigation)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
