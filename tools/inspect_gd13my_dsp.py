"""Inventory .061 DSP payloads and interpret a captured OEM version response offline."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import struct

import pefile


BRIDGE_SHA256 = '4e70275cd88034a63710cf863b663fb29d863811bf717b35a9bd2e70b9f665ae'
TABLE_VA = 0x10254410
SEGMENTS = 50
H264_TYPE6_MASK = 0x000C1001


def inventory(image):
    """Describe the segments copied by the stock InitShuttle path."""
    digest = sha256(image).hexdigest()
    if digest != BRIDGE_SHA256:
        raise ValueError('expected the GD13MY .061 dsp_bridge.dll SHA-256')
    pe = pefile.PE(data=image, fast_load=True)
    base = pe.OPTIONAL_HEADER.ImageBase
    table_bytes = (SEGMENTS + 1) * 12
    table = list(struct.iter_unpack('<III', pe.get_data(TABLE_VA - base, table_bytes)))
    if len(table) != SEGMENTS + 1 or table[-1] != (0, 0, 0):
        raise ValueError('incomplete DSP image table')
    segments = []
    for destination, size, source in table[:-1]:
        data = pe.get_data(source - base, size)
        if not size or len(data) != size:
            raise ValueError(f'incomplete segment at PE VA {source:#x}')
        segments.append({'destination': f'{destination:#010x}', 'source_va': f'{source:#010x}',
                         'size_bytes': size, 'sha256': sha256(data).hexdigest()})
    return {'bridge_sha256': digest, 'table_va': f'{TABLE_VA:#x}', 'segment_count': len(segments),
            'payload_bytes': sum(segment['size_bytes'] for segment in segments), 'segments': segments}


def version_response(packet):
    """Parse the 64-byte prefix at videodev!0x1000da38 (r0) after command 0x3c."""
    if len(packet) != 64:
        raise ValueError('capture exactly 64 bytes at r0 on entry to the OEM version parser')
    major, minor, point = struct.unpack_from('<HBB', packet, 0x0c)
    mask, = struct.unpack_from('<I', packet, 0x14)
    return {'version': {'major': major, 'minor': minor, 'point': point},
            'capability_word': f'{mask:#010x}',
            'h264_type6_gate_bits': f'{mask & H264_TYPE6_MASK:#010x}',
            'h264_type6_gate_open': bool(mask & H264_TYPE6_MASK)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bridge', type=Path, help='Unmodified .061 ROM dsp_bridge.dll')
    parser.add_argument('--version-response', type=Path,
                        help='Raw 64-byte response prefix captured from the stock ARM parser')
    args = parser.parse_args()
    try:
        report = inventory(args.bridge.read_bytes())
        if args.version_response:
            with args.version_response.open('rb') as stream:
                report['captured_response'] = version_response(stream.read(65))
    except (OSError, ValueError, pefile.PEFormatError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
