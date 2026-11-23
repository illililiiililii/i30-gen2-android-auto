"""Patch the exact GD13MY .061 system manager to read the opt-in startup settings."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory

from inspect_firmware import ROOT

STOCK_APP = 'uComH_New.exe'
STOCK_SHA = 'be9fbee622233b65a6f6c5775cee98fa93017ccf115ab53beb181a2ca6b3c029'
STARTUP_HOOK = 0x1ffdc
STOCK = {
    'stock_entry': 0x38cd8,
    'stock_resume': STARTUP_HOOK + 4,
    'stock_attributes': 0x38528,
    'stock_create_event': 0x38648,
    'stock_last_error': 0x38358,
    'stock_create_process': 0x38588,
    'stock_close': 0x38318,
}


def verify_stock_startup(stock):
    if sha256(stock).hexdigest() != STOCK_SHA:
        raise ValueError('Expected the original GD13MY Korean .061 system manager')


def patch_startup(stock, compiler):
    from elftools.elf.elffile import ELFFile
    import pefile

    from build_ce_minimal import align

    verify_stock_startup(stock)
    pe = pefile.PE(data=stock)
    image = pe.OPTIONAL_HEADER
    base = image.ImageBase
    rva = image.SizeOfImage
    storage = align(len(stock), image.FileAlignment)
    offset = pe.get_offset_from_rva(STARTUP_HOOK - base)
    section = pe.sections[-1].get_file_offset() + 40
    if (base + image.AddressOfEntryPoint != STOCK['stock_entry'] or
            struct.unpack_from('<I', stock, offset)[0] != 0xe3a05001 or
            section + 40 > pe.sections[0].PointerToRawData or any(stock[section:section + 40])):
        raise ValueError('Unexpected stock startup hook or section-header padding')
    with TemporaryDirectory(prefix='i30-startup-') as directory:
        compiled = Path(directory) / 'startup.elf'
        source = ROOT / 'src' / 'ce' / 'gd13my_startup_prefs.S'
        addresses = [f'-Wl,--defsym,{name}={address:#x}' for name, address in STOCK.items()]
        subprocess.run([compiler, '-march=armv4t', '-marm', '-nostdlib', '-static',
                        f'-Wl,-Ttext,{base + rva:#x},--entry,startup_prefs', *addresses,
                        '-o', compiled, source], check=True, timeout=45)
        with compiled.open('rb') as stream:
            executable = ELFFile(stream)
            code = executable.get_section_by_name('.text').data()
            clock_entry = executable.get_section_by_name('.symtab').get_symbol_by_name('clock_entry')[0]['st_value']
            if executable.header.e_entry != base + rva or not base + rva <= clock_entry < base + rva + len(code):
                raise ValueError('The startup patch entry did not link at the expected address')
    new = bytearray(stock)
    branch = (base + rva - STARTUP_HOOK - 8) // 4
    if not -(1 << 23) <= branch < (1 << 23):
        raise ValueError('ARM startup patch is outside branch range')
    struct.pack_into('<I', new, offset, 0xea000000 | (branch & 0xffffff))
    raw_size = align(len(code), image.FileAlignment)
    struct.pack_into('<8s6I2HI', new, section, b'.i30boot', len(code), rva, raw_size, storage,
                     0, 0, 0, 0, 0x60000020)
    struct.pack_into('<H', new, pe.FILE_HEADER.get_field_absolute_offset('NumberOfSections'), len(pe.sections) + 1)
    struct.pack_into('<I', new, image.get_field_absolute_offset('AddressOfEntryPoint'), clock_entry - base)
    struct.pack_into('<I', new, image.get_field_absolute_offset('SizeOfCode'), image.SizeOfCode + raw_size)
    struct.pack_into('<I', new, image.get_field_absolute_offset('SizeOfImage'),
                     align(rva + len(code), image.SectionAlignment))
    new.extend(bytes(storage - len(stock)) + code + bytes(raw_size - len(code)))
    return bytes(new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--compiler', type=Path, required=True)
    args = parser.parse_args()
    stock = ROOT / 'firmware' / 'extracted' / 'GD13MY' / 'APP' / '0001565b_uComH_New.exe'
    result = patch_startup(stock.read_bytes(), args.compiler.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('xb') as out:
        out.write(result)
    print(json.dumps({'file': str(args.output), 'sha256': sha256(result).hexdigest(),
                      'stock_hook': hex(STARTUP_HOOK)}, indent=2))


if __name__ == '__main__':
    main()
