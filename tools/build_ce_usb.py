"""Build the GD13MY Windows CE USB client, settings, and native navigation module."""

import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile
import pefile

from build_ce_minimal import IMAGE_BASE, PAGE, align, import_assembly, native_sections, pe_image
from inspect_ce_pe import inspect, rom_exports
from inspect_firmware import ROOT

DRIVER_API = ('CreateEventW', 'GetLastError', 'EventModify', 'CloseHandle', 'WaitForSingleObject', 'GetTickCount', 'Sleep',
              'OutputDebugStringW')
TLS_API = ('CreateFileW', 'ReadFile', 'LocalAlloc', 'LocalFree',
           'CeGenRandom', 'GetSystemTimeAsFileTime', 'GetFileAttributesW')
VIDEO_API = ('FindWindowW', 'GetForegroundWindow', 'GetDC', 'ReleaseDC', 'StretchDIBits',
             'GetProcessHeap', 'HeapAlloc', 'HeapFree', 'GetDCEx', 'GetClipBox',
             'GetWindow', 'IsWindowVisible', 'GetWindowLongW', 'GetClientRect', 'SendMessageTimeout')
SESSION_API = ('GetFileAttributesW', 'RegCreateKeyExW', 'RegSetValueExW', 'RegCloseKey', 'RegDeleteKeyW',
               'CreateEventW', 'GetLastError', 'EventModify', 'CloseHandle', 'WaitForSingleObject',
               'WaitForMultipleObjects', 'OutputDebugStringW')
SETTINGS_API = ('GetFileAttributesW', 'RegCreateKeyExW', 'RegSetValueExW', 'RegCloseKey', 'RegDeleteKeyW',
                'CreateEventW', 'GetLastError', 'EventModify', 'CloseHandle', 'WaitForSingleObject',
                'WaitForMultipleObjects', 'OutputDebugStringW', 'ExitThread', 'CreateFileW', 'ReadFile', 'DeleteFileW',
                'GetModuleHandleW', 'GetDlgItem', 'SendMessageW', 'SetWindowPos', 'EndDialog',
                'DialogBoxIndirectParamW', 'GetCommandLineW', 'SetDlgItemTextW', 'UpdateWindow', 'SetSystemTime',
                'GetForegroundWindow', 'GetWindowLongW', 'SetWindowLongW', 'SetTimer', 'CreateThread', 'GetTickCount')
NATIVE_API = (*SESSION_API, 'GetProcessHeap', 'HeapAlloc', 'HeapFree', 'CreateThread',
              'GetWindow', 'GetParent', 'IsWindow', 'IsWindowVisible', 'GetWindowLongW', 'SetWindowLongW',
              'GetClientRect', 'ClientToScreen', 'ScreenToClient', 'WindowFromPoint', 'GetWindowThreadProcessId', 'SetWindowPos',
              'RegisterClassW', 'GetClassInfoW', 'GetStockObject', 'DefWindowProcW', 'CreateWindowExW',
              'DestroyWindow', 'FindWindowW', 'SendMessageW', 'SetTimer', 'KillTimer',
              'InterlockedIncrement', 'InterlockedDecrement', 'InterlockedExchange', 'InterlockedCompareExchange',
              'InvalidateRect', 'ValidateRect', 'GetDCEx', 'ReleaseDC', 'CreateFontIndirectW', 'SelectObject',
              'DeleteObject', 'FillRect', 'DrawTextW', 'SetBkMode', 'SetTextColor')
DRIVER = 'i30usb.dll'
NAVIGATION_MODULE = 'i30nav.dll'


def export_directory(rva, target, entries):
    module = target.encode('ascii') + b'\0'
    count = len(entries)
    functions, names, ordinals, strings = (rva + offset for offset in (40, 40 + 4 * count,
                                                                       40 + 8 * count, 40 + 10 * count))
    base = struct.pack('<IIHH7I', 0, 0, 0, 0, strings, 1, count, count, functions, names, ordinals)
    text = bytearray(module)
    offsets = []
    for name in entries:
        offsets.append(strings + len(text))
        text += name.encode('ascii') + b'\0'
    return (base + struct.pack(f'<{count}I', *entries.values()) + struct.pack(f'<{count}I', *offsets) +
            struct.pack(f'<{count}H', *range(count)) + text)


def dll_sections(path, sections, target, names):
    pages = defaultdict(list)
    with path.open('rb') as stream:
        elf = ELFFile(stream)
        symbols = elf.get_section_by_name('.symtab')
        entries = {name: symbols.get_symbol_by_name(name)[0]['st_value'] - IMAGE_BASE for name in sorted(names)}
        for section in elf.iter_sections():
            if section['sh_type'] != 'SHT_REL':
                continue
            relocated = elf.get_section(section['sh_info'])
            if relocated.name == '.idata':
                continue  # This builder emits import RVAs and ordinals there.
            if relocated.name not in {kind for kind, _, _ in sections}:
                continue
            data = relocated.data()
            for reloc in section.iter_relocations():
                kind = reloc['r_info_type']
                if kind in (1, 3, 28, 29, 40, 42):
                    continue  # PC-relative calls, jumps and ARMv4T branch metadata.
                if kind != 2:
                    raise ValueError(f'Unrecognized ARM relocation {kind}')
                va = reloc['r_offset']
                addend, = struct.unpack_from('<I', data, va - relocated['sh_addr'])
                if not any(start <= addend - IMAGE_BASE < start + len(content)
                           for _, start, content in sections):
                    raise ValueError(f'Absolute relocation target outside the PE image: {addend:#x}')
                rva = va - IMAGE_BASE
                pages[rva & -PAGE].append(0x3000 | (rva % PAGE))
    if not pages:
        raise ValueError(f'{target} has no base relocations')
    reloc_bytes = bytearray()
    for page, items in sorted(pages.items()):
        if len(items) % 2:
            items.append(0)
        reloc_bytes.extend(struct.pack('<II', page, 8 + len(items) * 2))
        reloc_bytes.extend(struct.pack(f'<{len(items)}H', *items))
    start = max(align(rva + len(data), PAGE) for _, rva, data in sections)
    exported = export_directory(start, target, entries)
    return [*sections, ('.edata', start, exported), ('.reloc', align(start + len(exported), PAGE), reloc_bytes)]


def build_library(compiler, source, work, options, name, extra, run_tool):
    units = sorted(source.rglob('*.c'))
    if not units:
        raise ValueError(f'{name} source tree is empty')
    archiver = compiler.with_name(compiler.name.replace('gcc', 'ar'))

    def compile_unit(unit):
        filename = '_'.join(unit.relative_to(source).parts)
        target = work / (name + '_' + filename + '.o')
        run_tool([compiler, *options, '-Wno-error', *extra, '-ffunction-sections', '-fdata-sections',
                  '-c', unit, '-o', target])
        return target.name

    with ThreadPoolExecutor(max_workers=4) as workers:
        objects = list(workers.map(compile_unit, units))
    archive = work / (name + '.a')
    run_tool([archiver, 'rcs', archive.name, *objects])
    return archive


def build_bearssl(compiler, source, work, options, run_tool):
    if not (source / 'inc/bearssl.h').is_file() or not (source / 'LICENSE.txt').is_file():
        raise ValueError('Expected extracted BearSSL release with headers and license')
    platform = ('-DBR_USE_UNIX_TIME=0', '-DBR_USE_WIN32_TIME=0', '-DBR_USE_URANDOM=0', '-DBR_USE_WIN32_RAND=0')
    return build_library(compiler, source / 'src', work, options, 'bearssl',
                         (f'-I{source / "inc"}', f'-I{source / "src"}', *platform), run_tool)


def build(compiler, output, bearssl_source=None, h264_source=None, virtual_lcd_bench=False):
    source = ROOT / 'src/ce'
    exports = rom_exports()
    options = ('-march=armv4t', '-marm', '-Os', '-Wall', '-Wextra', '-Werror', '-ffreestanding', '-fshort-wchar',
               '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-nostdlib', '-static')
    report, artifacts = {}, {}
    output.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=output.parent.resolve(), prefix='i30-ce-usb-') as directory:
        work = Path(directory)
        environment = dict(os.environ, TEMP=directory, TMP=directory, TMPDIR=directory)

        def run_tool(command):
            subprocess.run(command, check=True, cwd=work, env=environment, timeout=45)

        tls_library = build_bearssl(compiler, bearssl_source, work, options, run_tool) if bearssl_source is not None else None
        decoder = None
        if h264_source is not None:
            decoder = build_library(compiler, h264_source / 'src', work, options, 'h264',
                                    (f'-I{h264_source / "src"}', '-O2'), run_tool)
        for target, unit, api, is_dll in (
                (DRIVER, 'ce_aa_usb_client.c', DRIVER_API, True),
                ('i30aa.exe', 'ce_aa_usb_settings.c', SETTINGS_API, False),
                (NAVIGATION_MODULE, 'ce_aa_native_display.cpp', NATIVE_API, True)):
            tls = target == DRIVER and tls_library is not None
            if tls:
                api = (*api, *TLS_API)
            video = tls and h264_source is not None
            if video:
                api = (*api, *VIDEO_API)
            asm = work / 'imports.S'
            asm.write_text(import_assembly(exports, api), encoding='ascii')
            elf = work / (target + '.elf')
            units = [asm]
            if target == DRIVER:
                units.extend((source / unit, source / 'aa_wire.c'))
            else:
                units.append(source / 'ce_aa_usb_session.c')
                if target == NAVIGATION_MODULE:
                    native = work / 'navigation.o'
                    run_tool([compiler, *options, '-fno-exceptions', '-fno-rtti', '-c', source / unit, '-o', native])
                    units.extend((native, '-lc'))
                else:
                    units.append(source / unit)
            if tls:
                units.extend(('-DI30_NATIVE_TLS', f'-I{bearssl_source / "inc"}', source / 'ce_aa_tls.c'))
                if video:
                    units.extend(('-DI30_NATIVE_VIDEO', f'-I{h264_source / "src"}', source / 'ce_aa_video.c',
                                  source / 'ce_aa_projection.c', decoder))
                    if virtual_lcd_bench:
                        units.append('-DI30_VIRTUAL_LCD_BENCH')
                units.extend((tls_library, '-lc', '-lgcc'))
            linker = f'-Wl,--emit-relocs,-T,{source / "ce_minimal.ld"}'
            keep_usb_entry = ('-Wl,--gc-sections,-u,USBDeviceAttach',) if video else ()
            run_tool([compiler, *options, linker, *keep_usb_entry, '-o', elf, *units])
            sections, entry, directory_rva, iat = native_sections(elf)
            if is_dll:
                names = ('USBDeviceAttach',) if target == DRIVER else (
                    'I30RouteProjectionTouch', 'I30StockDisplayChanged', 'I30ToggleProjection')
                sections = dll_sections(elf, sections, target, names)
            image = pe_image(sections, entry, directory_rva, iat, api=api, dll=is_dll)
            exe = work / target
            exe.write_bytes(image)
            report[target] = inspect(exe, exports)
            if video:
                sample_symbols = {'h264bsdDecode', 'h264bsdNextOutputPictureBGRA'}
                with elf.open('rb') as linked:
                    symbols = ELFFile(linked).get_section_by_name('.symtab')
                    report[target]['video_profile_rvas'] = {
                        symbol.name: symbol['st_value'] - IMAGE_BASE for symbol in symbols.iter_symbols()
                        if symbol.name in sample_symbols
                    }
            if [entry['name'] for entry in report[target]['imports']] != list(api):
                raise ValueError('Unexpected CE imports')
            if is_dll:
                program = pefile.PE(data=bytes(image))
                if not program.is_dll() or not program.DIRECTORY_ENTRY_BASERELOC or [
                        symbol.name.decode('ascii') for symbol in program.DIRECTORY_ENTRY_EXPORT.symbols] != list(names):
                    raise ValueError(f'Invalid CE DLL exports for {target}')
                report[target]['exports'] = {symbol.name.decode('ascii'): hex(symbol.address)
                                             for symbol in program.DIRECTORY_ENTRY_EXPORT.symbols}
                if target == DRIVER:
                    report[target]['export'] = report[target]['exports']['USBDeviceAttach']
            report[target]['sha256'] = sha256(image).hexdigest()
            artifacts[target] = image
    output.mkdir(parents=True, exist_ok=False)
    for target, data in artifacts.items():
        (output / target).write_bytes(data)
    if bearssl_source is not None:
        (output / 'BearSSL-LICENSE.txt').write_bytes((bearssl_source / 'LICENSE.txt').read_bytes())
    if h264_source is not None:
        (output / 'h264bsd-LICENSE.md').write_bytes((h264_source / 'LICENSE.md').read_bytes())
    (output / 'abi.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--bearssl-source', type=Path, help='Include the native TLS stage from an extracted BearSSL release')
    parser.add_argument('--h264-source', type=Path, help='Include the guest video channel and decoder for an authorized surface')
    parser.add_argument('--virtual-lcd-bench', action='store_true', help='Use the LCD in an isolated virtual-phone test image')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.h264_source and (not args.bearssl_source or not (args.h264_source / 'src/h264bsd_decoder.h').is_file() or
                             not (args.h264_source / 'LICENSE.md').is_file()):
        parser.error('--h264-source needs an h264bsd source tree and --bearssl-source')
    if args.virtual_lcd_bench and not args.h264_source:
        parser.error('--virtual-lcd-bench requires --h264-source')
    report = build(args.compiler.resolve(strict=True), args.output,
                   args.bearssl_source.resolve(strict=True) if args.bearssl_source else None,
                   args.h264_source.resolve(strict=True) if args.h264_source else None, args.virtual_lcd_bench)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
