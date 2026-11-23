"""Validate all stock MAP zlib chunks and their headers without writing map data."""

import hashlib
import json
import struct
import zlib

from inspect_firmware import ROOT

INPUT_BYTES = 1024 * 1024
MAX_UNPACKED_BYTES = 32 * 1024 * 1024


def check_streams(path, header, volume):
    base = 0
    buffer = b""
    with path.open("rb") as handle:
        while base < path.stat().st_size:
            decoder = zlib.decompressobj()
            digest = hashlib.md5()
            compressed = 0
            unpacked = 0
            while not decoder.eof:
                if not buffer:
                    buffer = handle.read(INPUT_BYTES)
                    if not buffer:
                        raise ValueError(f"Truncated map stream at {path.name}+{base:#x}")
                data = decoder.decompress(buffer, MAX_UNPACKED_BYTES - unpacked + 1)
                digest.update(data)
                unpacked += len(data)
                if unpacked > MAX_UNPACKED_BYTES:
                    raise ValueError(f"Oversized map stream at {path.name}+{base:#x}")
                unused = decoder.unused_data if decoder.eof else decoder.unconsumed_tail
                compressed += len(buffer) - len(unused)
                buffer = unused
            descriptor = digest.digest() + struct.pack("<4I", volume, base, unpacked, compressed)
            location = header.find(descriptor, 0x128)
            if location < 0:
                raise ValueError(f"No matching descriptor for {path.name}+{base:#x}")
            yield {"volume": path.name, "offset": hex(base), "header_offset": hex(location),
                   "bytes": unpacked, "packed_bytes": compressed, "md5": digest.hexdigest()}
            base += compressed


def main():
    common = ROOT / "firmware/original/COMMON"
    header = (common / "MAP.hdr").read_bytes()
    if hashlib.md5(header[0x38:]).digest() != header[0x28:0x38]:
        raise ValueError("MAP header MD5 mismatch")
    streams = []
    for volume, path in enumerate(sorted(common.glob("MAP.spd.*"))):
        rows = list(check_streams(path, header, volume))
        streams.extend(rows)
        print(f"{path.name}: {len(rows)} checked streams, {sum(row['bytes'] for row in rows)} decoded bytes", flush=True)
    evidence = ROOT / "research/evidence/map-streams.json"
    evidence.write_text(json.dumps(streams, indent=2), encoding="utf-8")
    print(f"{len(streams)} streams matched the MAP header. Output: {evidence}")


if __name__ == "__main__":
    main()
