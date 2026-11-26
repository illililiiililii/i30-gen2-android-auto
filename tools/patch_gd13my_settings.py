"""Build the version-locked GD13MY .061 Navigation Menu and Settings patch."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory

from inspect_firmware import ROOT

RESOURCE = 'nfdNaviGui_lit.gcf'
NAVIGATION = 'GDdNavi.exe'
STOCK_HASHES = {
    RESOURCE: 'ee0260fe6a97651b34dfebc3fbbe7bfaafef50dc8daa2a84e75f53d1f93afeeb',
    NAVIGATION: '9bd1cc489d56ae93f0c169e58111a9f94e5a8f297e2c03169253f73d76152056',
}
FONT = {
    'A': (14, 17, 17, 31, 17, 17, 17), 'n': (0, 0, 14, 9, 9, 9, 9),
    'd': (1, 1, 7, 9, 9, 9, 7), 'r': (0, 0, 6, 9, 8, 8, 8),
    'o': (0, 0, 6, 9, 9, 9, 6), 'i': (2, 0, 2, 2, 2, 2, 2),
    'u': (0, 0, 9, 9, 9, 9, 7), 't': (4, 4, 14, 4, 4, 4, 2),
    ' ': (0, 0, 0, 0, 0, 0, 0),
}
TITLE = 'Android Auto'
SHOT = 'IDC_SHOT_NMN09'
MENU_SHOT = 'NMN01'
BUTTON_ID = 31
BUTTON_X, BUTTON_Y = 658, 155
MENU_X, MENU_Y = 335, 412
THUNKS = {
    'stock_resume': 0xab8dc, 'stock_consumed': 0xabdf4, 'stock_create_process': 0x284198,
    'stock_close_handle': 0x283f18, 'stock_find_window': 0x283ea8,
    'stock_foreground': 0x284338,
}


def verify_stock(name, content):
    if sha256(content).hexdigest() != STOCK_HASHES[name]:
        raise ValueError(f'Unsupported stock GD13MY file: {name}')


def label_button(resource):
    resource = bytearray(resource)
    data_offset = struct.unpack_from('<I', resource, 21)[0] + 11
    width, height, planes, bpp, flags = struct.unpack_from('<iiHHI', resource, 29)
    masks = struct.unpack_from('<III', resource, 65)
    if (resource[:3] != b'RC\x01' or resource[11:13] != b'BM'
            or (width, height, planes, bpp, flags, masks) != (129, 53, 1, 16, 3, (0xf800, 0x7e0, 0x1f))):
        raise ValueError('Unexpected GCF RGB565 button resource')
    stride = (width * 2 + 3) & ~3
    scale = 2
    x = (width - len(TITLE) * 5 * scale) // 2
    y = (height - 7 * scale) // 2
    for char in TITLE:
        for row, pattern in enumerate(FONT[char]):
            for col in range(5):
                if pattern & (16 >> col):
                    for dy in range(scale):
                        position = data_offset + (height - 1 - y - row * scale - dy) * stride + (x + col * scale) * 2
                        resource[position:position + scale * 2] = bytes(scale * 2)
        x += 5 * scale
    return resource


def patch_resources(stock):
    verify_stock(RESOURCE, stock)
    shots, shot_count, resources, resource_count, shot_start, resource_start = struct.unpack_from('<4H2I', stock, 12)
    if resources != shots + shot_count * 20 or shot_start != resources + resource_count * 20:
        raise ValueError('Unexpected GCF index layout')
    targets = {
        45: (MENU_SHOT, MENU_X, MENU_Y, 29, 9264),
        91: (SHOT, BUTTON_X, BUTTON_Y, 28, 6265),
    }
    # Item 8 on the Other tab is the RGB565 style template for both buttons.
    template = 0xd2f19
    button = bytearray(stock[template:template + 86])
    if struct.unpack_from('<B11x4hI', button) != (8, 658, 412, 129, 53, 8):
        raise ValueError('Unexpected stock GCF button template')
    struct.pack_into('<I', button, 20, BUTTON_ID)
    button[0x4a] = 2  # The label is included in the RGB565 resources.
    old_ids = [
        stock[template + 149 + i:template + 165 + i] for i in range(0, 64, 16)
    ]
    index = {stock[i:i + 16]: struct.unpack_from('<I', stock, i + 16)[0]
             for i in range(resources, shot_start, 20)}
    appended_index = bytearray()
    appended_resources = bytearray()
    new_ids = {}
    for key in old_ids:
        if key not in new_ids:
            original = resource_start + index[key]
            data_length, = struct.unpack_from('<I', stock, original + 3)
            guid = sha256(b'GD13MY .061 Android Auto settings' + key).digest()[:16]
            if guid in index:
                raise ValueError('GCF resource ID collision')
            new_ids[key] = guid
            appended_index.extend(guid + struct.pack('<I', len(stock) - resource_start + len(appended_resources)))
            appended_resources.extend(label_button(stock[original:original + 7 + data_length]))
        button.extend(new_ids[key])
    delta_index = len(appended_index)
    prefix = bytearray(stock[:shot_start])
    appended_shots = bytearray()
    consumed = shot_start
    growth = 0
    for number in range(shot_count):
        entry = shots + number * 20
        relative, = struct.unpack_from('<I', stock, entry + 16)
        struct.pack_into('<I', prefix, entry + 16, relative + growth)
        if number not in targets:
            continue
        title, x, y, expected_count, expected_size = targets[number]
        pos = shot_start + relative
        count, size = struct.unpack_from('<HI', stock, pos + 2)
        title_bytes = title.encode('utf-16-le')
        if (stock[pos:pos + 2] != b'ST' or (count, size) != (expected_count, expected_size)
                or stock[pos + 87:pos + 87 + len(title_bytes)] != title_bytes or pos < consumed):
            raise ValueError(f'Unexpected GD13MY stock shot: {title}')
        end = pos + 8 + size
        struct.pack_into('<hh', button, 12, x, y)
        appended_shots.extend(stock[consumed:pos + 2])
        appended_shots.extend(struct.pack('<HI', count + 1, size + len(button)))
        appended_shots.extend(stock[pos + 8:end])
        appended_shots.extend(button)
        consumed = end
        growth += len(button)
    struct.pack_into('<HII', prefix, 18, resource_count + len(new_ids),
                     shot_start + delta_index, resource_start + delta_index + growth)
    return prefix + appended_index + appended_shots + stock[consumed:] + appended_resources


def patch_navigation(stock, compiler, *, native_projection=False):
    import pefile
    from elftools.elf.elffile import ELFFile
    from build_ce_minimal import align

    verify_stock(NAVIGATION, stock)
    program = pefile.PE(data=stock)
    image = program.OPTIONAL_HEADER
    base = image.ImageBase
    rva = image.SizeOfImage
    trampoline = base + rva
    section = program.sections[-1].get_file_offset() + 40
    header_size = 80 if native_projection else 40
    if (section + header_size > program.sections[0].PointerToRawData or
            any(stock[section:section + header_size])):
        raise ValueError('Missing space for the GD13MY menu section header')
    thunks = dict(THUNKS)
    if native_projection:
        from inspect_ce_pe import rom_exports

        # Leave all existing import descriptors, lookup tables and IAT slots intact.
        # The additional ordinal has its own writable loader slot.
        imports = b''.join(descriptor.struct.__pack__() for descriptor in program.DIRECTORY_ENTRY_IMPORT)
        import_rva = rva + image.SectionAlignment
        lookup_rva = import_rva + len(imports) + 40
        slot_rva = lookup_rva + 8
        library_rva = program.DIRECTORY_ENTRY_IMPORT[0].struct.Name
        if program.DIRECTORY_ENTRY_IMPORT[0].dll.lower() != b'coredll.dll':
            raise ValueError('Unexpected GD13MY system library descriptor')
        exports = rom_exports()
        ordinal = 0x80000000 | exports['GetProcAddressW']
        dispatch_slot, = (item.address for item in program.DIRECTORY_ENTRY_IMPORT[0].imports
                           if item.ordinal == exports['DispatchMessageW'])
        imports += struct.pack('<5I', lookup_rva, 0, 0, library_rva, slot_rva) + bytes(20)
        directory_size = len(imports)
        imports += struct.pack('<4I', ordinal, 0, ordinal, 0)
        thunks.update(stock_get_module=0x2d030c, stock_load_library=0x2cf114,
                      stock_get_proc_iat=base + slot_rva, stock_dispatch_iat=dispatch_slot)
    with TemporaryDirectory(prefix='gd13my-android-auto-') as directory:
        elf = Path(directory) / 'menu.elf'
        linker = [f'--defsym={symbol}={address:#x}' for symbol, address in thunks.items()]
        defines = ['-DI30_NATIVE_PROJECTION'] if native_projection else []
        subprocess.run([str(compiler), '-marm', '-march=armv4t', '-nostdlib',
                        *defines, '-Wl,' + ','.join([f'-Ttext={trampoline:#x}', *linker]), '-o', str(elf),
                        str(ROOT / 'src/ce/gd13my_aa_menu.S')], check=True, timeout=30)
        with elf.open('rb') as executable:
            data = ELFFile(executable).get_section_by_name('.text').data()
    site = 0xab8d8
    offset = program.get_offset_from_rva(site - base)
    branch = (trampoline - site - 8) // 4
    if not -(1 << 23) <= branch < (1 << 23) or struct.unpack_from('<I', stock, offset) != (0xe5993004,):
        raise ValueError('Stock touch path or ARM branch range differs')
    patch = bytearray(stock)
    struct.pack_into('<I', patch, offset, 0xea000000 | (branch & 0xffffff))
    storage = align(len(stock), image.FileAlignment)
    raw_size = align(len(data), image.FileAlignment)
    struct.pack_into('<8s6I2HI', patch, section, b'.i30nav', len(data), rva, raw_size, storage, 0, 0, 0, 0, 0x60000020)
    end_rva = rva + len(data)
    patch.extend(bytes(storage - len(stock)) + data + bytes(raw_size - len(data)))
    if native_projection:
        if end_rva > import_rva:
            raise ValueError('The native menu code exceeds one PE page')
        import_raw = align(len(imports), image.FileAlignment)
        struct.pack_into('<8s6I2HI', patch, section + 40, b'.i30imp', len(imports), import_rva,
                         import_raw, len(patch), 0, 0, 0, 0, 0xc0000040)
        struct.pack_into('<II', patch, image.DATA_DIRECTORY[1].get_file_offset(), import_rva, directory_size)
        struct.pack_into('<I', patch, image.get_field_absolute_offset('SizeOfInitializedData'),
                         image.SizeOfInitializedData + import_raw)
        patch.extend(imports + bytes(import_raw - len(imports)))
        end_rva = import_rva + len(imports)
    struct.pack_into('<H', patch, program.FILE_HEADER.get_field_absolute_offset('NumberOfSections'),
                     len(program.sections) + header_size // 40)
    struct.pack_into('<I', patch, image.get_field_absolute_offset('SizeOfCode'), image.SizeOfCode + raw_size)
    struct.pack_into('<I', patch, image.get_field_absolute_offset('SizeOfImage'),
                     align(end_rva, image.SectionAlignment))
    return patch, trampoline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--compiler', type=Path, required=True)
    parser.add_argument('--native-projection', action='store_true', help='Use the navigation-process DLL on the menu tap')
    args = parser.parse_args()
    source = ROOT / 'firmware/extracted/GD13MY/APP'
    gcf = patch_resources((source / ('00f3c40a_' + RESOURCE)).read_bytes())
    exe, addr = patch_navigation((source / ('00d12869_' + NAVIGATION)).read_bytes(),
                                 args.compiler.resolve(strict=True), native_projection=args.native_projection)
    args.output.mkdir(parents=True, exist_ok=False)
    report = {'target': 'GD13MY.KOR.SOP.00.061', 'shots': [MENU_SHOT, SHOT], 'item': BUTTON_ID,
              'trampoline': hex(addr), 'native_projection': args.native_projection, 'original': STOCK_HASHES,
              'modified': {}}
    for name, payload in ((RESOURCE, gcf), (NAVIGATION, exe)):
        (args.output / name).write_bytes(payload)
        report['modified'][name] = sha256(payload).hexdigest()
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
