"""Run the generated ARM probe with explicit test doubles for its CE imports."""

import argparse
import json
from pathlib import Path
import struct

import pefile
from unicorn import (UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_ARM,
                     UC_PROT_EXEC, UC_PROT_READ, UC_PROT_WRITE, Uc)
from unicorn.arm_const import (UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_SP, UC_CPU_ARM_TI925T)

from inspect_ce_pe import inspect, rom_exports

SHIMS = 0x00200000
DATA = 0x00300000
STACK = 0x00400000
WORKER_STACK = STACK + 0x8000
MAIN_STACK = STACK + 0x10000
THREAD_RETURN = SHIMS + 0x0ffc
PAGE = 0x1000
ARGUMENT_REGISTERS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
FILE_HANDLE, HEAP_HANDLE, THREAD_HANDLE = 0x31, 0x32, 0x33
FILENAME = r'\i30-ce-probe.exe'


class ProbeMachine:
    def __init__(self, path, *, deny_file=False, deny_thread=False, cancel_settings=False):
        self.data = path.read_bytes()
        self.pe = pefile.PE(data=self.data)
        imports = inspect(path, rom_exports())['imports']
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.cpu.ctl_set_cpu_model(UC_CPU_ARM_TI925T)
        header = self.pe.OPTIONAL_HEADER
        base = header.ImageBase
        self.cpu.mem_map(base, header.SizeOfImage, UC_PROT_READ | UC_PROT_WRITE)
        self.cpu.mem_write(base, self.pe.get_memory_mapped_image())
        self.cpu.mem_map(SHIMS, PAGE, UC_PROT_READ | UC_PROT_EXEC)
        for address, size in ((DATA, PAGE), (STACK, 0x10000)):
            self.cpu.mem_map(address, size, UC_PROT_READ | UC_PROT_WRITE)
        self.shims = {}
        for index, symbol in enumerate(imports):
            address = SHIMS + index * 4
            self.write32(base + int(symbol['iat_rva'], 16), address)
            self.shims[address] = symbol['name']
        self.cpu.mem_protect(base, header.SizeOfImage, UC_PROT_READ)
        for section in self.pe.sections:
            flags = UC_PROT_READ
            if section.IMAGE_SCN_MEM_EXECUTE:
                flags |= UC_PROT_EXEC
            if section.IMAGE_SCN_MEM_WRITE:
                flags |= UC_PROT_WRITE
            span = max(section.Misc_VirtualSize, section.SizeOfRawData)
            if span:
                self.cpu.mem_protect(base + section.VirtualAddress, (span + PAGE - 1) & -PAGE, flags)
        self.cpu.reg_write(UC_ARM_REG_SP, MAIN_STACK - 8)
        self.cpu.hook_add(UC_HOOK_CODE, self.handle_code, begin=SHIMS, end=THREAD_RETURN)
        self.cpu.hook_add(UC_HOOK_MEM_WRITE, self.track_stack, begin=STACK, end=MAIN_STACK - 1)
        self.entry = base + header.AddressOfEntryPoint
        self.deny_file = deny_file
        self.deny_thread = deny_thread
        self.cancel_settings = cancel_settings
        self.exit_status = None
        self.alloc = False
        self.file = False
        self.worker = None
        self.worker_context = None
        self.worker_result = None
        self.ticks = 1000
        self.calls = []
        self.logs = []
        self.dialogs = []
        self.stack_bytes = {'main': 0, 'worker': 0}
        self.peak_heap_bytes = 0

    def track_stack(self, _cpu, _access, address, _size, _value, _context):
        name, top = ('worker', WORKER_STACK) if address < WORKER_STACK else ('main', MAIN_STACK)
        self.stack_bytes[name] = max(self.stack_bytes[name], top - 8 - address)

    def write32(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value))

    def read32(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def utf16(self, address):
        data = bytearray()
        for offset in range(0, 520, 2):
            pair = self.cpu.mem_read(address + offset, 2)
            if pair == b'\0\0':
                return data.decode('utf-16-le')
            data.extend(pair)
        raise ValueError('Unterminated probe string')

    def handle_code(self, _, address, __, ___):
        if address == THREAD_RETURN:
            self.worker_result = self.cpu.reg_read(UC_ARM_REG_R0)
            self.cpu.context_restore(self.worker_context)
            self.worker_context = None
            self.return_to_probe(0)
            return
        name = self.shims.get(address)
        if name is None:
            raise ValueError(f'Unknown API shim address {address:#x}')
        self.calls.append(name)
        arguments = [self.cpu.reg_read(reg) for reg in ARGUMENT_REGISTERS]
        arguments.extend(self.read32(self.cpu.reg_read(UC_ARM_REG_SP) + offset) for offset in (0, 4, 8))
        value = getattr(self, name)(*arguments)
        if value is not None:
            self.return_to_probe(value)

    def return_to_probe(self, value):
        self.cpu.reg_write(UC_ARM_REG_R0, value)
        self.cpu.reg_write(UC_ARM_REG_PC, self.cpu.reg_read(UC_ARM_REG_LR))

    def OutputDebugStringW(self, text, *_):
        self.logs.append(self.utf16(text).rstrip())
        return 0

    def GetModuleFileNameW(self, module, output, capacity, *_):
        if module or capacity < len(FILENAME) + 1:
            return 0
        self.cpu.mem_write(output, (FILENAME + '\0').encode('utf-16-le'))
        return len(FILENAME)

    def CreateFileW(self, path, access, share, security, creation, flags, template):
        if self.deny_file or (self.utf16(path), access, share, security, creation, flags, template) != (
                FILENAME, 0x80000000, 1, 0, 3, 0x80, 0):
            return 0xffffffff
        self.file = True
        return FILE_HANDLE

    def ReadFile(self, handle, output, count, actual, overlapped, *_):
        if not self.file or handle != FILE_HANDLE or overlapped or count > len(self.data):
            return 0
        self.cpu.mem_write(output, self.data[:count])
        self.write32(actual, count)
        return 1

    def CloseHandle(self, handle, *_):
        if handle == FILE_HANDLE and self.file:
            self.file = False
            return 1
        if handle == THREAD_HANDLE and self.worker is not None and self.worker_result is not None:
            self.worker = None
            return 1
        return 0

    def GetProcessHeap(self, *_):
        return HEAP_HANDLE

    def HeapAlloc(self, heap, flags, size, *_):
        if heap != HEAP_HANDLE or flags or size != 4 or self.alloc:
            return 0
        self.alloc = True
        self.peak_heap_bytes = max(self.peak_heap_bytes, size)
        return DATA

    def HeapFree(self, heap, flags, pointer, *_):
        if (heap, flags, pointer) != (HEAP_HANDLE, 0, DATA) or not self.alloc or self.worker is not None:
            return 0
        self.alloc = False
        return 1

    def CreateThread(self, security, stack, routine, context, flags, thread_id, *_):
        if self.deny_thread or self.worker is not None or (security, stack, context, flags, thread_id) != (0, 0, DATA, 0, 0):
            return 0
        self.worker = routine, context
        return THREAD_HANDLE

    def WaitForSingleObject(self, handle, deadline, *_):
        if handle != THREAD_HANDLE or self.worker is None or not deadline:
            return 0xffffffff
        routine, context = self.worker
        self.worker_context = self.cpu.context_save()
        self.cpu.reg_write(UC_ARM_REG_R0, context)
        self.cpu.reg_write(UC_ARM_REG_SP, WORKER_STACK - 8)
        self.cpu.reg_write(UC_ARM_REG_LR, THREAD_RETURN)
        self.cpu.reg_write(UC_ARM_REG_PC, routine)

    def GetExitCodeThread(self, handle, output, *_):
        if handle != THREAD_HANDLE or self.worker_result is None:
            return 0
        self.write32(output, self.worker_result)
        return 1

    def GetTickCount(self, *_):
        self.ticks += 1
        return self.ticks

    def ExitThread(self, code, *_):
        self.exit_status = code
        self.cpu.emu_stop()

    def MessageBoxW(self, _, message, title, style, *_unused):
        self.dialogs.append({'title': self.utf16(title), 'text': self.utf16(message), 'style': style})
        return 2 if self.cancel_settings and (style & 0xf) == 1 else 1

    def run(self):
        self.cpu.emu_start(self.entry, 0, timeout=2_000_000, count=100_000)
        if self.exit_status is None or self.file or self.alloc or self.worker is not None:
            raise ValueError('Probe exceeded its instruction budget or left an emulated resource open')
        report = {'mode': 'ARMv4T instructions with coredll test doubles', 'exit_status': self.exit_status,
                  'calls': self.calls, 'logs': self.logs, 'thread_callback_exit': self.worker_result,
                  'mapped_image_bytes': self.pe.OPTIONAL_HEADER.SizeOfImage,
                  'stack_write_depth_bytes': self.stack_bytes, 'peak_probe_heap_bytes': self.peak_heap_bytes}
        if self.dialogs:
            report['dialogs'] = self.dialogs
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    failure = parser.add_mutually_exclusive_group()
    failure.add_argument('--deny-file', action='store_true', help='Exercise the probe file-open failure branch')
    failure.add_argument('--deny-thread', action='store_true', help='Exercise resource cleanup when CreateThread fails')
    failure.add_argument('--cancel-settings', action='store_true', help='Cancel from the settings prompt')
    args = parser.parse_args()
    report = ProbeMachine(args.exe, deny_file=args.deny_file, deny_thread=args.deny_thread,
                          cancel_settings=args.cancel_settings).run()
    print(json.dumps(report, indent=2))
    return 0 if report['exit_status'] == (2 if args.deny_thread else int(args.deny_file)) else 1


if __name__ == '__main__':
    raise SystemExit(main())
