"""Execute the patched ARM startup path with stock API doubles."""

import argparse
import json
from pathlib import Path
import struct

import pefile
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_MODE_ARM, Uc
from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R5,
                               UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_SP)

from patch_gd13my_startup import STARTUP_HOOK, STOCK

RAM = 0x20000000
HIDE = r'\DiskA\i30agree.opt'
AUTO = r'\DiskA\i30auto.opt'
BOOT_AUTO = r'\DiskA\i30boot.opt'
CLOCK = r'\DiskA\Application\NAVI\i30-emu-utc.bin'


def exercise(pe, flags, mode=2, source=2, requested=0, existing=False, spawn=True, early=False):
    cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    base = pe.OPTIONAL_HEADER.ImageBase
    image = pe.get_memory_mapped_image()
    cpu.mem_map(base, pe.OPTIONAL_HEADER.SizeOfImage)
    cpu.mem_write(base, image)
    cpu.mem_map(RAM, 0x4000)
    cpu.mem_write(RAM + 0x4f4, struct.pack('<I', mode))
    cpu.mem_write(RAM + 0x7c2, bytes([requested]))
    cpu.mem_write(RAM + 0x803, bytes([source]))
    cpu.reg_write(UC_ARM_REG_R9, RAM)
    cpu.reg_write(UC_ARM_REG_R10, RAM + 0x800)
    cpu.reg_write(UC_ARM_REG_R0, 21)
    cpu.reg_write(UC_ARM_REG_SP, RAM + 0x3000)
    calls = []

    def read_text(address):
        data = bytearray()
        while (piece := cpu.mem_read(address, 2)) != b'\0\0':
            data.extend(piece)
            address += 2
        return data.decode('utf-16-le')

    def intercept(_, pc, _size, operation):
        assert operation != 'stock_consent', 'The startup hook must not invoke stock consent'
        if operation in ('stock_entry', 'stock_resume'):
            assert (operation == 'stock_entry') == early
            assert cpu.reg_read(UC_ARM_REG_R0) == 21
            assert cpu.reg_read(UC_ARM_REG_SP) == RAM + 0x3000
            assert cpu.reg_read(UC_ARM_REG_R5) == int(not early)
            cpu.emu_stop()
            return
        args = [cpu.reg_read(UC_ARM_REG_R0 + i) for i in range(4)]
        result = 1
        if operation == 'stock_attributes':
            result = flags.get(read_text(args[0]), 0xffffffff)
        elif operation == 'stock_create_event':
            assert args[:3] == [0, 1, 0] and read_text(args[3]) == 'I30.GD13MY.Startup.1'
            calls.append('event')
            result = 45
        elif operation == 'stock_last_error':
            result = 183 if existing else 0
        elif operation == 'stock_create_process':
            assert read_text(args[0]) == r'\DiskA\Application\NAVI\i30aa.exe'
            expected_command = ('-i30clock' if early else '-i30wake' if flags.get(BOOT_AUTO) else '-i30start')
            assert read_text(args[1]) == expected_command and args[2:] == [0, 0]
            stack = cpu.reg_read(UC_ARM_REG_SP)
            options = struct.unpack('<6I', cpu.mem_read(stack, 24))
            assert options[:5] == (0, 0, 0, 0, 0) and options[5] == stack + 24
            calls.append('start')
            result = int(spawn)
            if spawn:
                cpu.mem_write(options[5], struct.pack('<4I', 61, 62, 0, 0))
        elif operation == 'stock_close':
            calls.append(f'close {args[0]}')
        cpu.reg_write(UC_ARM_REG_R0, result)
        cpu.reg_write(UC_ARM_REG_PC, cpu.reg_read(UC_ARM_REG_LR))

    for name, address in (STOCK | {'stock_consent': 0x15928}).items():
        cpu.hook_add(UC_HOOK_CODE, intercept, name, begin=address, end=address)
    cpu.emu_start(base + pe.OPTIONAL_HEADER.AddressOfEntryPoint if early else STARTUP_HOOK, 0, count=600)
    assert cpu.reg_read(UC_ARM_REG_PC) == STOCK['stock_entry' if early else 'stock_resume']
    assert cpu.mem_read(RAM + 0x803, 1) == bytes([source])
    return calls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path)
    args = parser.parse_args()
    pe = pefile.PE(str(args.image))
    results = {
        'unchanged default': exercise(pe, {}),
        'directory is not an opt-in': exercise(pe, {AUTO: 0x10}),
        'legacy consent flag ignored': exercise(pe, {HIDE: 0x80}),
        'start USB on stock NAVI MAIN acknowledgment': exercise(pe, {AUTO: 0x80}),
        'boot receiver launches a message wake helper': exercise(pe, {BOOT_AUTO: 0x80}),
        'boot receiver avoids duplicate USB owner': exercise(pe, {AUTO: 0x80, BOOT_AUTO: 0x80}),
        'start clock sync before stock startup': exercise(pe, {CLOCK: 0x80}, early=True),
        'stock startup without emulator clock file': exercise(pe, {}, early=True),
        'unrelated acknowledgment': exercise(pe, {AUTO: 0x80}, source=3),
        'mode switch in progress': exercise(pe, {AUTO: 0x80}, requested=3),
        'failed launcher leaves stock running': exercise(pe, {AUTO: 0x80}, spawn=False),
        'duplicate NAVI notification': exercise(pe, {AUTO: 0x80}, existing=True),
        'unrelated AV mode': exercise(pe, {AUTO: 0x80}, mode=3),
    }
    assert results == {
        'unchanged default': [],
        'directory is not an opt-in': [],
        'legacy consent flag ignored': [],
        'start USB on stock NAVI MAIN acknowledgment': ['event', 'start', 'close 61', 'close 62'],
        'boot receiver launches a message wake helper': ['start', 'close 61', 'close 62'],
        'boot receiver avoids duplicate USB owner': ['start', 'close 61', 'close 62'],
        'start clock sync before stock startup': ['start', 'close 61', 'close 62'],
        'stock startup without emulator clock file': [],
        'unrelated acknowledgment': [],
        'mode switch in progress': [],
        'failed launcher leaves stock running': ['event', 'start'],
        'duplicate NAVI notification': ['event', 'close 45'],
        'unrelated AV mode': [],
    }
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
