"""Build an experimental DiskA image from the original GD13MY APP update."""

import argparse
from bisect import bisect_right
from collections import Counter
from contextlib import ExitStack
from hashlib import md5
from pathlib import Path, PurePosixPath
import struct
import zlib

from extract_spd import WIDE_NAME, find_header_entry, read_members
from check_map import MAX_UNPACKED_BYTES
from inspect_firmware import ROOT

SOURCE = ROOT / 'firmware/original/GD13MY'
SECTOR_SIZE = 512
PARTITION_LBA = 2048
PARTITION_OFFSET = PARTITION_LBA * SECTOR_SIZE
VOLUME_SIZE = 256 * 1024 * 1024
SETTINGS_SIZE = 64 * 1024 * 1024
MAP_SIZE = 3584 * 1024 * 1024
COMMON = ROOT / 'firmware/original/COMMON'


def app_files(header, payload):
    groups = {}
    for match in WIDE_NAME.finditer(header, 0x128):
        start = match.start()
        name = match.group()[:-2].decode('utf-16le')
        parts = name.split('/')
        if (start % 4 or parts[:2] != ['', 'DiskA'] or any(p in ('', '.', '..') for p in parts[2:])
                or header[start - 4:start - 1] != bytes(3)):
            continue
        count = struct.unpack_from('<I', header, start - 8)[0]
        groups[start] = (PurePosixPath('/', *parts[2:]), count)
    starts = sorted(groups)
    remaining = Counter({k: count for k, (_, count) in groups.items()})
    seen = set()
    for _, _, data, entry, _ in read_members(header, payload):
        index = bisect_right(starts, int(entry['name_offset'], 16)) - 1
        leaf = entry['name']
        if index < 0 or leaf in ('', '.', '..') or any(c in leaf for c in '/\\:'):
            raise ValueError(f'Unexpected APP filename {leaf!r}')
        start = starts[index]
        path = str(groups[start][0] / leaf)
        if remaining[start] == 0 or path.casefold() in seen:
            raise ValueError(f'Unexpected or duplicate APP entry {path}')
        remaining[start] -= 1
        seen.add(path.casefold())
        yield path, data
    if any(remaining.values()):
        raise ValueError('APP directory file counts differ from the header')


def map_files(source, filesystem):
    header = (source / 'MAP.hdr').read_bytes()
    if (not header.startswith(b'HACO STDAVN UPGRADE IMAGE\0')
            or struct.unpack_from('<I', header, 0x24)[0] != len(header)
            or md5(header[0x38:]).digest() != header[0x28:0x38]):
        raise ValueError('Invalid MAP header')
    folders = []
    for match in WIDE_NAME.finditer(header, 0x128):
        start = match.start()
        path = PurePosixPath(match.group()[:-2].decode('utf-16le'))
        if (start % 4 == 0 and path.parts[:2] == ('/', 'DiskA2') and '..' not in path.parts
                and header[start - 4:start - 1] == bytes(3)):
            folders.append((start, match.end(), PurePosixPath('/', *path.parts[2:]),
                            struct.unpack_from('<I', header, start - 8)[0]))

    volumes = sorted(source.glob('MAP.spd.*'))
    offsets = [0] * len(volumes)
    seen = set()
    with ExitStack() as stack:
        media = [stack.enter_context(path.open('rb')) for path in volumes]
        for index, (_, names_start, folder, count) in enumerate(folders):
            end = folders[index + 1][0] if index + 1 < len(folders) else len(header)
            if str(folder) != '/':
                filesystem.makedirs(str(folder), recreate=True)
            for match in WIDE_NAME.finditer(header, names_start, end):
                name_start = match.start()
                tag = header[name_start - 4:name_start]
                descriptor = name_start + 2 * tag[3]
                if (name_start % 4 or not tag[0] or tag[1:3] != bytes(2) or descriptor + 32 * tag[0] > end
                        or not 0 <= descriptor - match.end() <= 6 or any(header[match.end():descriptor])):
                    continue
                entry = find_header_entry(header, descriptor)
                leaf = entry['name']
                path = str(folder / leaf)
                if leaf in ('', '.', '..') or any(c in leaf for c in '/\\:') or path.casefold() in seen:
                    raise ValueError(f'Invalid MAP filename {path}')
                written = 0
                with filesystem.openbin(path, 'w') as target:
                    for chunk in range(entry['chunks']):
                        digest, volume, offset, size, packed = struct.unpack_from('<16s4I', header, descriptor + 32 * chunk)
                        if volume >= len(media) or offset != offsets[volume] or not 0 < size <= MAX_UNPACKED_BYTES:
                            raise ValueError(f'Invalid MAP chunk in {path}')
                        data = media[volume].read(packed)
                        decoder = zlib.decompressobj()
                        decoded = decoder.decompress(data, size + 1)
                        if (len(data) != packed or len(decoded) != size or not decoder.eof
                                or decoder.unused_data or md5(decoded).digest() != digest):
                            raise ValueError(f'MAP chunk mismatch in {path}')
                        target.write(decoded)
                        offsets[volume] += packed
                        written += size
                if written != entry['bytes']:
                    raise ValueError(f'MAP file length mismatch in {path}')
                seen.add(path.casefold())
                count -= 1
            if count:
                raise ValueError(f'MAP file count mismatch in {folder}: {count}')
        if offsets != [path.stat().st_size for path in volumes] or len(seen) != struct.unpack_from('<I', header, 0x104)[0]:
            raise ValueError('MAP package was not fully consumed')
    return len(seen)


def build_image(source, output, *, map_source=None):
    from pyfatfs.PyFat import PyFat
    from pyfatfs.PyFatFS import PyFatFS

    header = (source / 'APP.hdr').read_bytes()
    payload = (source / 'APP.spd.000').read_bytes()
    volumes = [('DiskA', PARTITION_OFFSET, VOLUME_SIZE)]
    if map_source is not None:
        map_offset = PARTITION_OFFSET + VOLUME_SIZE
        volumes.extend((('DiskA2', map_offset, MAP_SIZE), ('DiskA3', map_offset + MAP_SIZE, SETTINGS_SIZE)))
    with output.open('xb') as target:
        target.truncate(volumes[-1][1] + volumes[-1][2])
        mbr = bytearray(SECTOR_SIZE)
        for index, (_, offset, size) in enumerate(volumes):
            struct.pack_into('<B3sB3sII', mbr, 446 + index * 16, 0, b'\xfe\xff\xff', 0x0c, b'\xfe\xff\xff',
                             offset // SECTOR_SIZE, size // SECTOR_SIZE)
        mbr[-2:] = b'\x55\xaa'
        target.write(mbr)
    try:
        for label, offset, size in volumes:
            formatter = PyFat(offset=offset)
            formatter.mkfs(str(output), PyFat.FAT_TYPE_FAT32, size=size, label=label)
            formatter.close()
        count = 0
        with PyFatFS(str(output), offset=PARTITION_OFFSET, preserve_case=True) as fs:
            for path, data in app_files(header, payload):
                fs.makedirs(str(PurePosixPath(path).parent), recreate=True)
                fs.writebytes(path, data)
                count += 1
        if map_source is not None:
            with PyFatFS(str(output), offset=volumes[2][1], preserve_case=True) as fs:
                fs.makedirs('/System')
                fs.makedirs('/TPEG_CH')
            with PyFatFS(str(output), offset=volumes[1][1], preserve_case=True) as fs:
                count += map_files(map_source, fs)
        return count
    except Exception:
        output.unlink()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source', type=Path, default=SOURCE)
    parser.add_argument('--with-map', action='store_true')
    parser.add_argument('--map-source', type=Path, default=COMMON)
    args = parser.parse_args()
    count = build_image(args.source, args.output, map_source=args.map_source if args.with_map else None)
    print(f'{count} stock files written to {args.output}')


if __name__ == '__main__':
    main()
