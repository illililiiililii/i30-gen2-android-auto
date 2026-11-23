"""Desktop WinMM backend. Wave buffers stay owned until WinMM returns them."""

import ctypes as ct
from ctypes import wintypes as wt

from .audio import MUSIC


class WaveFormat(ct.Structure):
    _pack_ = 1
    _fields_ = [('tag', wt.WORD), ('channels', wt.WORD), ('samples_sec', wt.DWORD),
                ('bytes_sec', wt.DWORD), ('alignment', wt.WORD), ('bits', wt.WORD), ('extra', wt.WORD)]


class WaveHeader(ct.Structure):
    _fields_ = [('data', ct.c_void_p), ('length', wt.DWORD), ('recorded', wt.DWORD),
                ('user', ct.c_size_t), ('flags', wt.DWORD), ('loops', wt.DWORD),
                ('next', ct.c_void_p), ('reserved', ct.c_size_t)]


class WaveInCaps(ct.Structure):
    _fields_ = [('manufacturer', wt.WORD), ('product', wt.WORD), ('version', wt.UINT),
                ('name', wt.WCHAR * 32), ('formats', wt.DWORD), ('channels', wt.WORD), ('reserved', wt.WORD)]


class WaveOutCaps(ct.Structure):
    _fields_ = WaveInCaps._fields_ + [('support', wt.DWORD)]


DONE, IN_QUEUE = 1, 16


def wave_devices():
    dll = ct.WinDLL('winmm.dll')
    for direction, cls in (('In', WaveInCaps), ('Out', WaveOutCaps)):
        count = getattr(dll, f'wave{direction}GetNumDevs')()
        caps = getattr(dll, f'wave{direction}GetDevCapsW')
        caps.argtypes = (ct.c_size_t, ct.POINTER(cls), wt.UINT)
        for index in range(count):
            info = cls()
            if caps(index, ct.byref(info), ct.sizeof(info)) == 0:
                yield {'direction': 'capture' if direction == 'In' else 'playback', 'device': index, 'name': info.name}


class WaveStream:
    def __init__(self, direction, device, fmt=MUSIC):
        if device < 0 or device > 0xFFFFFFFE:
            raise ValueError("Use a device index from audio-devices")
        self.direction = direction
        self.device = device
        self.format = fmt
        self.dll = ct.WinDLL('winmm.dll')
        self.handle = wt.HANDLE()
        self.buffers = []
        self.cursor = 0

    def call(self, name, types, *args):
        function = getattr(self.dll, 'wave' + self.direction + name)
        function.argtypes = types
        result = function(*args)
        if result:
            raise OSError(f'wave{self.direction}{name} returned MMRESULT {result}')

    def control(self, name):
        self.call(name, (wt.HANDLE,), self.handle)

    def header_call(self, name, header):
        self.call(name, (wt.HANDLE, ct.POINTER(WaveHeader), wt.UINT),
                  self.handle, ct.byref(header), ct.sizeof(header))

    def start(self):
        if self.handle:
            raise OSError('Wave device is already open')
        fmt = self.format
        spec = WaveFormat(1, fmt.channels, fmt.rate, fmt.rate * fmt.frame_bytes, fmt.frame_bytes, 16, 0)
        self.call('Open', (ct.POINTER(wt.HANDLE), wt.UINT, ct.POINTER(WaveFormat), ct.c_size_t, ct.c_size_t, wt.DWORD),
                  ct.byref(self.handle), self.device, ct.byref(spec), 0, 0, 0)
        self.cursor = 0
        try:
            for _ in range(3):
                storage = ct.create_string_buffer(fmt.block_bytes())
                header = WaveHeader(data=ct.addressof(storage), length=len(storage))
                self.header_call('PrepareHeader', header)
                self.buffers.append((storage, header))
                if self.direction == 'In':
                    self.header_call('AddBuffer', header)
            if self.direction == 'In':
                self.control('Start')
        except BaseException:
            self.close()
            raise

    def close(self):
        if not self.handle:
            return
        self.control('Reset')
        while self.buffers:
            self.header_call('UnprepareHeader', self.buffers[-1][1])
            self.buffers.pop()
        self.control('Close')
        self.handle = wt.HANDLE()


class WavePlayback(WaveStream):
    def __init__(self, device):
        super().__init__('Out', device)

    def ready(self):
        return not self.buffers[self.cursor][1].flags & IN_QUEUE

    def write(self, data):
        storage, header = self.buffers[self.cursor]
        if len(data) != len(storage) or not self.ready():
            raise OSError('Wave output buffer is unavailable or has the wrong size')
        storage.raw = data
        self.header_call('Write', header)
        self.cursor = (self.cursor + 1) % len(self.buffers)


class WaveCapture(WaveStream):
    def __init__(self, device):
        super().__init__('In', device)

    def read(self):
        chunks = []
        for _ in self.buffers:
            storage, header = self.buffers[self.cursor]
            if not header.flags & DONE:
                break
            chunks.append(storage[:header.recorded])
            self.header_call('AddBuffer', header)
            self.cursor = (self.cursor + 1) % len(self.buffers)
        return b''.join(chunks)
