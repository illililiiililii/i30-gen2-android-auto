"""Cross-compile the freestanding ARMv4T probe and link a Windows CE 6 PE image."""

import argparse
import json
from pathlib import Path
import shutil
import struct
import subprocess
from tempfile import TemporaryDirectory

from elftools.elf.elffile import ELFFile

from inspect_ce_pe import inspect, rom_exports
from inspect_firmware import ROOT

IMAGE_BASE = 0x10000
PAGE = 0x1000
FILE_ALIGNMENT = 0x200
SECTION_FLAGS = {'.text': 0x60000020, '.rdata': 0x40000040, '.idata': 0xc0000040, '.data': 0xc0000040,
                 '.edata': 0x40000040, '.reloc': 0x42000040}
API = ('OutputDebugStringW', 'CreateFileW', 'ReadFile', 'CloseHandle', 'GetProcessHeap', 'HeapAlloc',
       'HeapFree', 'CreateThread', 'WaitForSingleObject', 'GetExitCodeThread', 'GetModuleFileNameW',
       'GetTickCount', 'ExitThread')
DDRAW_LOADER_API = ('LoadLibraryW', 'GetProcAddressA', 'FreeLibrary')


def align(value, boundary):
    return (value + boundary - 1) & -boundary


def import_assembly(exports, api=API):
    lines = ['.syntax unified', '.arch armv4t', '.arm', '.section .text.ce_api,"ax"']
    for name in api:
        lines.extend((f'.global {name}', f'.type {name},%function', f'{name}:', 'ldr ip, 1f',
                      'ldr ip, [ip]', 'bx ip', f'1: .word ce_slot_{name}'))
    lines.extend(('.section .ce_import,"aw"', '.balign 4', '.global ce_directory', 'ce_directory:',
                  '.word ce_lookup - 0x10000, 0, 0, ce_dll - 0x10000, ce_iat - 0x10000', '.space 20',
                  'ce_lookup:'))
    lines.extend(f'.word {0x80000000 | exports[name]:#x}' for name in api)
    lines.extend(('.word 0', '.global ce_iat', 'ce_iat:'))
    lines.extend(f'ce_slot_{name}: .word {0x80000000 | exports[name]:#x}' for name in api)
    lines.extend(('.word 0', 'ce_dll: .asciz "COREDLL.dll"'))
    return '\n'.join(lines) + '\n'


def native_sections(elf_path):
    with elf_path.open('rb') as stream:
        elf = ELFFile(stream)
        if elf.elfclass != 32 or not elf.little_endian or elf['e_machine'] != 'EM_ARM':
            raise ValueError('Compiler did not produce ARM32 little-endian code')
        if any(segment['p_type'] in ('PT_DYNAMIC', 'PT_INTERP') for segment in elf.iter_segments()):
            raise ValueError('Unexpected dynamic ELF runtime dependency')
        sections = []
        for section in elf.iter_sections():
            if not section['sh_flags'] & 2 or not section['sh_size']:
                continue
            if section.name not in SECTION_FLAGS or section['sh_type'] != 'SHT_PROGBITS':
                raise ValueError(f'Unexpected initialized section {section.name}')
            sections.append((section.name, section['sh_addr'] - IMAGE_BASE, section.data()))
        symbols = {sym.name: sym['st_value'] - IMAGE_BASE
                   for sym in elf.get_section_by_name('.symtab').iter_symbols()}
        return sections, elf['e_entry'] - IMAGE_BASE, symbols['ce_directory'], symbols['ce_iat']


def pe_image(sections, entry, directory, iat, api=API, *, dll=False):
    sections = sorted(sections, key=lambda section: section[1])
    if sections[0][:2] != ('.text', PAGE) or entry % 4 or not PAGE <= entry < PAGE + len(sections[0][2]):
        raise ValueError('ARM entry must be inside the first code section')
    raw_start = align(0x80 + 4 + 20 + 224 + 40 * len(sections), FILE_ALIGNMENT)
    result = bytearray(raw_start)
    result[:2] = b'MZ'
    struct.pack_into('<I', result, 0x3c, 0x80)
    result[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HHIIIHH', result, 0x84, 0x01c2, len(sections), 0, 0, 0, 224, 0x2102 if dll else 0x103)
    opt = 0x98
    init = sum(align(len(data), FILE_ALIGNMENT) for name, _, data in sections if name != '.text')
    struct.pack_into('<HBBIIIIII', result, opt, 0x10b, 0, 0, align(len(sections[0][2]), FILE_ALIGNMENT),
                     init, 0, entry, PAGE, sections[1][1])
    struct.pack_into('<III6H', result, opt + 28, IMAGE_BASE, PAGE, FILE_ALIGNMENT, 4, 0, 0, 0, 6, 0)
    struct.pack_into('<III', result, opt + 52, 0, align(sections[-1][1] + len(sections[-1][2]), PAGE), raw_start)
    struct.pack_into('<IHHIIIIII', result, opt + 64, 0, 9, 0, 0x10000, 0x1000, 0x10000, 0x1000, 0, 16)
    struct.pack_into('<II', result, opt + 96 + 8, directory, 40)
    struct.pack_into('<II', result, opt + 96 + 12 * 8, iat, 4 * (len(api) + 1))
    last_rva = PAGE
    for index, (name, rva, data) in enumerate(sections):
        if rva % PAGE or rva < last_rva:
            raise ValueError('Overlapping or unaligned PE sections')
        last_rva = align(rva + len(data), PAGE)
        size = align(len(data), FILE_ALIGNMENT)
        struct.pack_into('<8sIIIIIIHHI', result, opt + 224 + index * 40, name.encode('ascii'), len(data),
                         rva, size, len(result), 0, 0, 0, 0, SECTION_FLAGS[name])
        result.extend(data + bytes(size - len(data)))
        if dll and name in ('.edata', '.reloc'):
            directory_index = 0 if name == '.edata' else 5
            struct.pack_into('<II', result, opt + 96 + directory_index * 8, rva, len(data))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path, required=True, help='arm-none-eabi-gcc executable')
    variant = parser.add_mutually_exclusive_group()
    variant.add_argument('--settings', action='store_true', help='Build the interactive Android Auto settings test')
    variant.add_argument('--h264-source', type=Path, help='Build a CE video output probe with this h264bsd source tree')
    uyvy = parser.add_mutually_exclusive_group()
    uyvy.add_argument('--uyvy-staging', action='store_true',
                      help='Pack decoded I420 into memory in the standalone video probe')
    uyvy.add_argument('--uyvy-ddraw', action='store_true',
                      help='Route decoded I420 through the opt-in DirectDraw backend')
    parser.add_argument('--ddraw-flip', action='store_true',
                        help='With --uyvy-ddraw, request a back buffer and use Flip/GetFlipStatus')
    args = parser.parse_args()
    if (args.uyvy_staging or args.uyvy_ddraw) and not args.h264_source:
        parser.error('UYVY probes require --h264-source')
    if args.ddraw_flip and not args.uyvy_ddraw:
        parser.error('--ddraw-flip requires --uyvy-ddraw')
    compiler = args.compiler.resolve(strict=True)
    archiver = compiler.with_name(compiler.name.replace('gcc', 'ar')).resolve(strict=True)
    if archiver == compiler:
        parser.error('Use the Arm GNU arm-none-eabi-gcc toolchain')
    source = ROOT / 'src/ce'
    output = ROOT / ('build/ce-aa-settings' if args.settings else 'build/ce-minimal')
    artifact_name = 'i30-aa-settings' if args.settings else 'i30-ce-probe'
    api = (*API, 'MessageBoxW') if args.settings else API
    output.mkdir(parents=True, exist_ok=True)
    exports = rom_exports()
    if args.h264_source:
        decoder = args.h264_source.resolve(strict=True)
        headers = decoder / 'src'
        if not (headers / 'h264bsd_decoder.h').is_file() or not (decoder / 'LICENSE.md').is_file():
            parser.error('Expected the h264bsd repository with source and license')
        output_name = ('gd13my-ce-uyvy-staging' if args.uyvy_staging else
                       'gd13my-ce-uyvy-ddraw' if args.uyvy_ddraw else 'gd13my-ce-video')
        output = ROOT / ('build/' + output_name)
        output.mkdir(parents=True, exist_ok=True)
        api = ('CreateFileW', 'ReadFile', 'CloseHandle', 'GetProcessHeap', 'HeapAlloc', 'HeapFree',
               'GetDC', 'ReleaseDC', 'StretchDIBits', 'OutputDebugStringW', 'ExitThread')
        if args.uyvy_ddraw:
            api = (*api, *DDRAW_LOADER_API)
        with TemporaryDirectory(prefix='i30-ce-video-') as scratch:
            staging = Path(scratch)
            assembly = staging / 'ce_api.S'
            assembly.write_text(import_assembly(exports, api), encoding='ascii')
            elf = staging / 'i30video.elf'
            defines, extra_units = [], []
            if args.uyvy_staging:
                defines = ['-DI30_VIDEO_UYVY_STAGING']
            elif args.uyvy_ddraw:
                defines = ['-DI30_VIDEO_UYVY_DIRECTDRAW']
                if args.ddraw_flip:
                    defines.append('-DI30_DDRAW_FLIP')
                extra_units = [source / 'ce_aa_uyvy_ddraw.c']
            subprocess.run([compiler, '-march=armv4t', '-marm', '-Os', '-ffreestanding', '-fshort-wchar',
                            '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                            '-ffunction-sections', '-fdata-sections', f'-I{headers}', '-nostdlib', '-static',
                            *defines, f'-Wl,--gc-sections,-T,{source / "ce_minimal.ld"}', '-o', elf, assembly,
                            source / 'ce_aa_video.c', source / 'ce_aa_video_probe.c', *extra_units,
                            *sorted(headers.glob('*.c')), '-lc', '-lgcc'], check=True, cwd=staging, timeout=90)
            probe = output / 'i30video.exe'
            probe.write_bytes(pe_image(*native_sections(elf), api=api))
            abi = inspect(probe, exports)
            abi['video_probe_format'] = ('uyvy-staging' if args.uyvy_staging else
                                         'ddraw' if args.uyvy_ddraw else 'bgra')
            abi['ddraw_flip'] = args.ddraw_flip
            names = {'i30_video_push', 'stage_uyvy', 'h264bsdConvertToBGRA', 'i30_ddraw_open',
                     'i30_ddraw_present', 'i30_ddraw_hide', 'i30_ddraw_close'}
            with elf.open('rb') as stream:
                abi['video_probe_rvas'] = {
                    symbol.name: symbol['st_value'] - IMAGE_BASE
                    for symbol in ELFFile(stream).get_section_by_name('.symtab').iter_symbols()
                    if symbol.name in names
                }
            (output / 'abi.json').write_text(json.dumps(abi, indent=2) + '\n', encoding='utf-8')
            shutil.copyfile(decoder / 'LICENSE.md', output / 'h264bsd-LICENSE.md')
            print(probe)
        return
    with TemporaryDirectory(prefix='i30-ce-minimal-') as scratch:
        staging = Path(scratch)
        assembly = staging / 'ce_api.S'
        assembly.write_text(import_assembly(exports, api), encoding='ascii')
        options = ['-march=armv4t', '-marm', '-Os', '-Wall', '-Wextra', '-Werror', '-ffreestanding',
                   '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables']
        if args.settings:
            options.extend(('-DI30_AA_SETTINGS', '-fshort-wchar'))
        wire = staging / 'aa_wire.o'
        library = staging / 'libi30_aa_wire.a'
        subprocess.run([compiler, *options, '-c', source / 'aa_wire.c', '-o', wire],
                       check=True, cwd=staging, timeout=40)
        subprocess.run([archiver, 'rcs', library, wire], check=True, cwd=staging, timeout=20)
        elf = staging / (artifact_name + '.elf')
        subprocess.run([compiler, *options, '-nostdlib', '-static', f'-Wl,-T,{source / "ce_minimal.ld"}',
                        '-o', elf, source / 'ce_minimal_probe.c', assembly, library],
                       check=True, cwd=staging, timeout=40)
        probe = staging / (artifact_name + '.exe')
        probe.write_bytes(pe_image(*native_sections(elf), api=api))
        report = inspect(probe, exports)
        if [row['name'] for row in report['imports']] != list(api):
            raise ValueError('Static import report differs from the probe ABI')
        for artifact in (elf, probe, library):
            shutil.copyfile(artifact, output / artifact.name)
    (output / 'abi.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(output / probe.name)


if __name__ == '__main__':
    main()
