"""Repack only the audited .061 APP archive for GD13MY bench verification."""

import argparse
from hashlib import md5, sha256
import json
from pathlib import Path
import struct
import zlib

from build_gd13my_aa_lab import NATIVE_SETTINGS_PATH, NATIVE_USB_PATH, STARTUP_PATH, read_ce_app
from build_gd13my_diska import SOURCE, app_files
from extract_spd import MAX_MEMBER, read_members
from patch_gd13my_settings import STOCK_HASHES, verify_stock
from patch_gd13my_startup import STOCK_APP, verify_stock_startup

ARCHIVE_NAMES = ('APP.hdr', 'APP.spd.000')
ARCHIVE_HASHES = (
    '1aaac7c063ce65b480bb67a05e49838aefd0af2026609216efc1b8aa86438bf7',
    '491ddb63c33d7c83a954a3d3e4096053837f9c85415ed440187bb81578938d61',
)
NAVI_DIR, NEXT_DIR = 0x1c58, 0x22b8


def descriptor(data, offset, compressed_size):
    return md5(data).digest() + struct.pack('<4I', 0, offset, len(data), compressed_size)


def repack(header, payload, patch_dir, launcher, *, usb_client=None, startup_patch=None):
    if tuple(sha256(data).hexdigest() for data in (header, payload)) != ARCHIVE_HASHES:
        raise ValueError('Expected the original GD13MY Korean .061 APP archive')
    patches = {name.casefold(): (patch_dir / name).read_bytes() for name in STOCK_HASHES}
    additions = {NATIVE_SETTINGS_PATH: launcher}
    if usb_client is not None:
        additions[NATIVE_USB_PATH] = usb_client
    stock_files = dict(app_files(header, payload))
    for name in STOCK_HASHES:
        verify_stock(name, stock_files['/Application/NAVI/' + name])
    if startup_patch is not None:
        if usb_client is None:
            raise ValueError('The startup patch requires the native USB settings app')
        verify_stock_startup(stock_files[STARTUP_PATH])
    new_header = bytearray(header)
    new_payload = bytearray()
    directory_size, directory_entries_size, count = struct.unpack_from('<3I', header, NAVI_DIR)
    if NAVI_DIR + directory_size != NEXT_DIR or count != 22:
        raise ValueError('Unexpected stock NAVI directory')
    unpacked = 0
    extra = None
    for _, _, original, entry, records in read_members(header, payload):
        leaf = entry['name'].casefold()
        name_address = int(entry['name_offset'], 16)
        changed = leaf in patches and NAVI_DIR < name_address < NEXT_DIR
        content = patches[leaf] if changed else original
        if startup_patch is not None and leaf == STOCK_APP.casefold():
            verify_stock_startup(original)
            content, changed = startup_patch, True
        unpacked += len(content)
        if changed:
            struct.pack_into('<I', new_header, name_address - 8, len(content))
        begin = 0
        for i, record in enumerate(records):
            end = len(content) if i == len(records) - 1 else begin + record['bytes']
            data = content[begin:end]
            if not data or len(data) > MAX_MEMBER:
                raise ValueError('Patched APP member does not fit its stock chunk layout')
            prior = int(record['offset'], 16)
            stream = zlib.compress(data, 9) if changed else payload[prior:prior + record['packed_bytes']]
            address = int(record['header_md5_offset'], 16)
            new_header[address:address + 32] = descriptor(data, len(new_payload), len(stream))
            new_payload.extend(stream)
            begin = end
        if int(records[-1]['header_md5_offset'], 16) + 32 == NEXT_DIR:
            extra = bytearray()
            for path, data in additions.items():
                stream = zlib.compress(data, 9)
                name = (Path(path).name + '\0').encode('utf-16-le')
                name += bytes((-len(name)) % 4)
                extra.extend(struct.pack('<I4B', len(data), 1, 0, 0, len(name) // 2) + name
                             + descriptor(data, len(new_payload), len(stream)))
                new_payload.extend(stream)
                unpacked += len(data)
    if extra is None:
        raise ValueError('Missing end of the stock NAVI archive directory')
    new_header[NEXT_DIR:NEXT_DIR] = extra
    struct.pack_into('<3I', new_header, NAVI_DIR,
                     directory_size + len(extra), directory_entries_size + len(extra), count + len(additions))
    total, = struct.unpack_from('<I', header, 0x104)
    struct.pack_into('<I', new_header, 0x24, len(new_header))
    struct.pack_into('<I', new_header, 0x104, total + len(additions))
    struct.pack_into('<I', new_header, 0x110, unpacked)
    struct.pack_into('<I', new_header, 0x118, len(new_payload))
    new_header[0x28:0x38] = md5(new_header[0x38:]).digest()

    expected = stock_files.copy()
    for name in STOCK_HASHES:
        expected['/Application/NAVI/' + name] = patches[name.casefold()]
    if startup_patch is not None:
        expected[STARTUP_PATH] = startup_patch
    expected.update(additions)
    if dict(app_files(new_header, new_payload)) != expected:
        raise ValueError('Repacked archive did not round-trip to the expected filesystem')
    return new_header, new_payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch_dir', type=Path)
    parser.add_argument('launcher', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--usb-client', type=Path)
    parser.add_argument('--startup-patch', type=Path)
    args = parser.parse_args()
    header, payload = ((SOURCE / name).read_bytes() for name in ARCHIVE_NAMES)
    driver = read_ce_app(args.usb_client, dll=True) if args.usb_client else None
    startup = args.startup_patch.read_bytes() if args.startup_patch else None
    rebuilt = repack(header, payload, args.patch_dir, read_ce_app(args.launcher), usb_client=driver,
                     startup_patch=startup)
    args.output.mkdir(parents=True, exist_ok=False)
    for name, content in zip(ARCHIVE_NAMES, rebuilt):
        (args.output / name).write_bytes(content)
    report = {'purpose': 'APP archive bench inspection', 'files': {
        name: sha256(content).hexdigest() for name, content in zip(ARCHIVE_NAMES, rebuilt)
    }, 'changed_stock_files': list(STOCK_HASHES), 'added': NATIVE_SETTINGS_PATH}
    if driver is not None:
        report['usb_client'] = NATIVE_USB_PATH
    if startup is not None:
        report['changed_stock_files'].append(STARTUP_PATH)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
