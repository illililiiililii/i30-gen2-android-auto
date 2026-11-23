"""Publish reverse state from the original .061 user-mode display libraries."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory

from inspect_firmware import ROOT

DISPLAY_HASHES = {
    'LibSystem.dll': '7821aa8c5d2f058004f46fbd3be3011e1322d0ec5fd25fe5d1bf0b61c7280e6b',
    'LibVideo.dll': '9a68a11ee3ce40442d38073164745cf82bbc318d898a1ecf8596d081533b3f5c',
}
HOOKS = {
    'LibSystem.dll': (
        (0x101ee4, 0xe5993030, 'stock_before_rear'),
        (0x101ff4, 0xe59f30c8, 'stock_after_rear'),
    ),
    'LibVideo.dll': ((0x101148, 0xe1a01000, 'stock_camera_request'),),
}


def verify_stock_display(name, data):
    if sha256(data).hexdigest() != DISPLAY_HASHES[name]:
        raise ValueError(f'Expected the original .061 {name}')


def patch_display(name, stock, compiler):
    from elftools.elf.elffile import ELFFile
    import pefile

    from build_ce_minimal import align
    from inspect_ce_pe import rom_exports

    verify_stock_display(name, stock)
    program = pefile.PE(data=stock)
    pe = program.OPTIONAL_HEADER
    base, code_rva = pe.ImageBase, pe.SizeOfImage
    data_rva = code_rva + pe.SectionAlignment
    data_va = base + data_rva
    system = name == 'LibSystem.dll'
    section = program.sections[-1].get_file_offset() + 40
    if (section + 80 > program.sections[0].PointerToRawData or any(stock[section:section + 80])):
        raise ValueError(f'Missing PE header padding in {name}')

    imports = None
    data = bytes(4)  # Private event handle. The code references it relative to the image.
    if system:
        descriptors = program.DIRECTORY_ENTRY_IMPORT
        if descriptors[0].dll.lower() != b'coredll.dll':
            raise ValueError('Unexpected LibSystem import order')
        imports = b''.join(item.struct.__pack__() for item in descriptors)
        lookup = data_rva + len(data) + len(imports) + 40
        iat = lookup + 12
        imports += struct.pack('<5I', lookup, 0, 0, descriptors[0].struct.Name, iat) + bytes(20)
        ce = rom_exports()
        table = struct.pack('<3I', 0x80000000 | ce['CreateEventW'], 0x80000000 | ce['EventModify'], 0)
        data += imports + table + table
        symbols = {'stock_debug': 0x1037ec, 'stock_decode_resume': 0x101ee8, 'stock_after_resume': 0x101ff8,
                   'stock_after_literal': 0x1020c4, 'stock_create_iat': base + iat,
                   'stock_modify_iat': base + iat + 4}
    else:
        symbols = {'stock_debug': 0x105ae0, 'stock_create_event': 0x105b40, 'stock_modify_event': 0x1059e0,
                   'stock_camera_resume': 0x10114c}
    symbols['stock_event_handle'] = data_va

    with TemporaryDirectory(prefix='gd13my-display-') as directory:
        elf = Path(directory) / 'display.elf'
        entry = HOOKS[name][0][2]
        addresses = [f'--defsym={key}={value:#x}' for key, value in symbols.items()]
        options = ['-DI30_SYSTEM_DISPLAY'] if system else []
        subprocess.run([compiler, '-march=armv4t', '-marm', '-nostdlib', *options,
                        '-Wl,' + ','.join([f'-Ttext={base + code_rva:#x}', f'-e,{entry}', *addresses]),
                        '-o', elf, ROOT / 'src/ce/gd13my_display_events.S'], check=True, timeout=45)
        with elf.open('rb') as stream:
            built = ELFFile(stream)
            code = built.get_section_by_name('.text').data()
            symtab = built.get_section_by_name('.symtab')
            targets = {label: symtab.get_symbol_by_name(label)[0]['st_value'] for _, _, label in HOOKS[name]}
    if len(code) > pe.SectionAlignment:
        raise ValueError('The OEM display publisher exceeds one PE page')

    patched = bytearray(stock)
    for site, instruction, label in HOOKS[name]:
        offset = program.get_offset_from_rva(site - base)
        delta = (targets[label] - site - 8) // 4
        if struct.unpack_from('<I', stock, offset) != (instruction,) or not -(1 << 23) <= delta < (1 << 23):
            raise ValueError(f'Unexpected ARM hook at {site:#x} in {name}')
        struct.pack_into('<I', patched, offset, 0xea000000 | (delta & 0xffffff))
    patched.extend(bytes(align(len(stock), pe.FileAlignment) - len(stock)))
    for index, (label, flags, rva, payload) in enumerate(
            ((b'.i30disp', 0x60000020, code_rva, code), (b'.i30data', 0xc0000040, data_rva, data))):
        raw_size = align(len(payload), pe.FileAlignment)
        struct.pack_into('<8s6I2HI', patched, section + 40 * index, label, len(payload), rva, raw_size,
                         len(patched), 0, 0, 0, 0, flags)
        patched.extend(payload + bytes(raw_size - len(payload)))
    struct.pack_into('<H', patched, program.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),
                     len(program.sections) + 2)
    for field, value in (('SizeOfImage', align(data_rva + len(data), pe.SectionAlignment)),
                         ('SizeOfCode', pe.SizeOfCode + align(len(code), pe.FileAlignment)),
                         ('SizeOfInitializedData', pe.SizeOfInitializedData + align(len(data), pe.FileAlignment))):
        struct.pack_into('<I', patched, pe.get_field_absolute_offset(field), value)
    if imports is not None:
        struct.pack_into('<II', patched, pe.DATA_DIRECTORY[1].get_file_offset(), data_rva + 4, len(imports))
    return patched


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--compiler', required=True, type=Path)
    args = parser.parse_args()
    source = ROOT / 'firmware/extracted/GD13MY/APP'
    compiler = args.compiler.resolve(strict=True)
    patches = {name: patch_display(name, next(source.glob(f'*_{name}')).read_bytes(), compiler)
               for name in DISPLAY_HASHES}
    args.output.mkdir(parents=True, exist_ok=False)
    for name, data in patches.items():
        (args.output / name).write_bytes(data)
    print(json.dumps({name: sha256(data).hexdigest() for name, data in patches.items()}, indent=2))


if __name__ == '__main__':
    main()
