"""Check a CE 6 ARM/Thumb probe against the exports from the GD13MY CE ROM."""

import argparse
import json
from pathlib import Path

import pefile

from inspect_firmware import ROOT

ROM_EVIDENCE = ROOT / 'research/evidence/phase1-rom.json'


def rom_exports(path=ROM_EVIDENCE):
    exports = json.loads(path.read_text(encoding='utf-8'))['modules']['coredll.dll']['exports']
    return {entry['name']: entry['ordinal'] for entry in exports if entry['name'] and int(entry['rva'], 16)}


def inspect(path, exports):
    program = pefile.PE(data=path.read_bytes())
    header = program.OPTIONAL_HEADER
    if (program.FILE_HEADER.Machine, header.Magic, header.Subsystem,
            header.MajorSubsystemVersion, header.MinorSubsystemVersion) != (0x1c2, 0x10b, 9, 6, 0):
        raise ValueError('Expected PE32 machine 0x01c2 and Windows CE subsystem 6.0')
    entry = header.AddressOfEntryPoint
    section = program.get_section_by_rva(entry)
    if entry % 4 or section is None or not section.IMAGE_SCN_MEM_EXECUTE:
        raise ValueError('Expected an aligned ARM entry point in an executable PE section')
    tables = getattr(program, 'DIRECTORY_ENTRY_IMPORT', [])
    if [table.dll.lower() for table in tables] != [b'coredll.dll']:
        raise ValueError('Probe expects exactly one import module, coredll.dll')
    name_by_ordinal = {ordinal: name for name, ordinal in exports.items()}
    imported = []
    for symbol in tables[0].imports:
        name = name_by_ordinal.get(symbol.ordinal)
        rva = symbol.address - header.ImageBase
        slot = program.get_section_by_rva(rva)
        if name is None or slot is None or not slot.IMAGE_SCN_MEM_WRITE or slot.IMAGE_SCN_MEM_EXECUTE:
            raise ValueError(f'Unresolved or incorrectly mapped coredll IAT entry at {rva:#x}')
        imported.append({'ordinal': symbol.ordinal, 'name': name, 'iat_rva': hex(rva)})
    if not imported or len({row['ordinal'] for row in imported}) != len(imported):
        raise ValueError('Missing or repeated coredll ordinals')
    directory = header.DATA_DIRECTORY[12]
    if directory.VirtualAddress != tables[0].struct.FirstThunk or directory.Size != 4 * (len(imported) + 1):
        raise ValueError('PE IAT directory does not match the import descriptor')
    return {'file': path.name, 'machine': '0x01c2', 'subsystem': 9, 'version': '6.0', 'entry_rva': hex(entry),
            'image_base': hex(header.ImageBase), 'image_size': header.SizeOfImage, 'imports': imported}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('exe', type=Path)
    parser.add_argument('--rom-evidence', type=Path, default=ROM_EVIDENCE)
    args = parser.parse_args()
    print(json.dumps(inspect(args.exe, rom_exports(args.rom_evidence)), indent=2))


if __name__ == '__main__':
    main()
