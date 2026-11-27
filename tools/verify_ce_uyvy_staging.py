"""Verify the ARM I420 handoff, padded UYVY bytes and same-frame BGRA fallback."""

import argparse
import json
from pathlib import Path
from statistics import median
import struct
from time import perf_counter_ns

import av

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP

from emulate_ce_usb import MARK, Machine


PITCH = 800 * 2 + 32
SURFACE_SIZE = PITCH * 480
PADDING = 0xA5


class StagingProbe(Machine):
    instruction_limit = 100_000_000
    timeout_us = 20_000_000

    def __init__(self, path, stream, *, deny_staging=False):
        super().__init__(path)
        self.stream = stream
        self.deny_staging = deny_staging
        self.position = 0
        self.heap_next = 0x21000000
        self.cpu.mem_map(self.heap_next, 0x1000000)
        self.allocations = {}
        self.alloc_count = self.live_bytes = self.peak_bytes = 0
        self.surface = None
        self.blits = []
        self.status = None

    def CreateFileW(self, name, *_):
        assert self.text(name).endswith(r'\NAVI\i30-video.h264')
        return 1

    def ReadFile(self, handle, output, count, actual, overlapped, *_):
        assert handle == 1 and not overlapped
        data = self.stream[self.position:self.position + count]
        if data:
            self.cpu.mem_write(output, data)
        self.position += len(data)
        self.put(actual, len(data))
        return 1

    def GetProcessHeap(self, *_):
        return 1

    def HeapAlloc(self, heap, flags, size, *_):
        assert heap == 1 and not flags
        if size == SURFACE_SIZE and self.deny_staging:
            return 0
        address = self.heap_next
        self.heap_next += (size + 7) & ~7
        self.allocations[address] = size
        self.alloc_count += 1
        self.live_bytes += size
        self.peak_bytes = max(self.peak_bytes, self.live_bytes)
        if size == SURFACE_SIZE:
            self.cpu.mem_write(address, bytes([PADDING]) * size)
        return address

    def HeapFree(self, heap, flags, address, *_):
        assert heap == 1 and not flags
        size = self.allocations.pop(address)
        self.live_bytes -= size
        if size == SURFACE_SIZE:
            self.surface = bytes(self.cpu.mem_read(address, SURFACE_SIZE))
        return 1

    def GetDC(self, window, *_):
        assert not window
        return 2

    def ReleaseDC(self, window, dc, *_):
        assert (window, dc) == (0, 2)
        return 1

    def StretchDIBits(self, dc, x, y, width, height, *_):
        assert (dc, x, y, width, height) == (2, 0, 0, 800, 480)
        stack = self.cpu.reg_read(UC_ARM_REG_SP)
        pixels, info = self.word(stack + 20), self.word(stack + 24)
        header = struct.unpack('<IiiHH', self.cpu.mem_read(info, 16))
        self.blits.append((header, bytes(self.cpu.mem_read(pixels, 4))))
        return height

    def OutputDebugStringW(self, *_):
        return 0

    def ExitThread(self, status, *_):
        self.status = status
        self.cpu.reg_write(UC_ARM_REG_PC, MARK)

    def measure(self, path, names):
        rvas = json.loads(path.with_name('abi.json').read_text(encoding='utf-8'))['video_probe_rvas']
        durations = {}

        def enter(cpu, _address, _size, name):
            return_pc = cpu.reg_read(UC_ARM_REG_LR)

            def leave(cpu, _address, _size, _context):
                durations[name] = (perf_counter_ns() - started) / 1_000_000
                cpu.hook_del(return_hook)

            return_hook = cpu.hook_add(UC_HOOK_CODE, leave, begin=return_pc, end=return_pc)
            started = perf_counter_ns()

        for name in names:
            entry = self.base + rvas[name]
            self.cpu.hook_add(UC_HOOK_CODE, enter, name, begin=entry, end=entry)
        self.run(self.pe.OPTIONAL_HEADER.AddressOfEntryPoint)
        assert self.status == 0 and not self.allocations and self.live_bytes == 0
        assert durations.keys() == set(names), durations
        return {**durations, 'allocations': self.alloc_count, 'peak_bytes': self.peak_bytes}


def sample(width, height):
    codec = av.CodecContext.create('libx264', 'w')
    codec.width, codec.height, codec.pix_fmt = width, height, 'yuv420p'
    codec.options = {'preset': 'ultrafast', 'tune': 'zerolatency', 'profile': 'baseline'}
    frame = av.VideoFrame(width, height, 'yuv420p')
    for plane, value in zip(frame.planes, (81, 90, 240)):
        plane.update(bytes([value]) * plane.buffer_size)
    return b''.join(bytes(packet) for packet in (*codec.encode(frame), *codec.encode(None)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('probe', type=Path)
    parser.add_argument('--compare-bgra', type=Path, help='Measure against the default video probe in ARM Unicorn')
    args = parser.parse_args()
    for width, height in ((800, 480), (798, 478)):
        stream = sample(width, height)
        probe = StagingProbe(args.probe, stream)
        probe.run(probe.pe.OPTIONAL_HEADER.AddressOfEntryPoint)
        assert probe.status == 0 and probe.surface is not None and not probe.blits and not probe.allocations
        row = bytes((90, 81, 240, 81)) * (width // 2)
        expected = row + bytes([PADDING]) * (PITCH - len(row))
        assert probe.surface == expected * height + bytes([PADDING]) * (PITCH * (480 - height))

    fallback = StagingProbe(args.probe, sample(800, 480), deny_staging=True)
    fallback.run(fallback.pe.OPTIONAL_HEADER.AddressOfEntryPoint)
    assert fallback.status == 0 and fallback.surface is None and not fallback.allocations
    [(header, pixel)] = fallback.blits
    assert header == (40, 800, -480, 1, 32) and pixel[:3] == bytes((0, 0, 255))
    print('ARM staging passed: 800x480, cropped 798x478, padding and BGRA fallback')
    if args.compare_bgra:
        stream = sample(800, 480)
        modes = {
            'bgra': (args.compare_bgra, ('i30_video_push', 'h264bsdConvertToBGRA'), False),
            'uyvy': (args.probe, ('i30_video_push', 'stage_uyvy'), False),
            'uyvy_denied': (args.probe, ('i30_video_push', 'stage_uyvy', 'h264bsdConvertToBGRA'), True),
        }
        results = {name: [] for name in modes}
        for _ in range(5):
            for name, (path, functions, deny) in modes.items():
                probe = StagingProbe(path, stream, deny_staging=deny)
                results[name].append(probe.measure(path, functions))
                assert len(probe.blits) == int(name != 'uyvy')
        print(json.dumps({
            'scope': 'ARM fixture wall milliseconds; API doubles; one 800x480 frame per run',
            'median': {name: {key: round(median(row[key] for row in runs), 3) for key in runs[0]}
                       for name, runs in results.items()},
            'runs': results,
        }, indent=2))


if __name__ == '__main__':
    main()
