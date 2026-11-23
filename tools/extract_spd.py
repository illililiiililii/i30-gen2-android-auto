"""Extract stock GD13MY files for offline analysis. There is no package writer."""

import hashlib
import json
import re
import struct
import zlib
from pathlib import Path

from inspect_firmware import ROOT, pe

MAX_MEMBER = 96 * 1024 * 1024
WIDE_NAME = re.compile(rb"(?:[\x20-\x7e]\0){1,160}\0\0")


def read_members(header, payload):
    if not header.startswith(b"HACO STDAVN UPGRADE IMAGE\0"):
        raise ValueError("Unrecognized header")
    if struct.unpack_from("<I", header, 0x24)[0] != len(header):
        raise ValueError("Header length mismatch")
    if hashlib.md5(header[0x38:]).digest() != header[0x28:0x38]:
        raise ValueError("Header digest mismatch")

    expected_files = struct.unpack_from("<I", header, 0x104)[0]
    file_count = 0
    remaining = 0
    entry = None
    chunks = []
    offset = 0
    while offset < len(payload):
        decoder = zlib.decompressobj()
        data = decoder.decompress(payload[offset:], MAX_MEMBER + 1)
        if len(data) > MAX_MEMBER or not decoder.eof:
            raise ValueError(f"Incomplete or oversized stream at {offset:#x}")
        packed = len(payload) - offset - len(decoder.unused_data)
        descriptor = hashlib.md5(data).digest() + struct.pack("<4I", 0, offset, len(data), packed)
        position = header.find(descriptor, 0x128)
        if position < 0:
            raise ValueError(f"No checked descriptor for zlib stream at {offset:#x}")
        if remaining == 0:
            entry = find_header_entry(header, position)
            remaining = entry["chunks"]
            if not 1 <= remaining <= 32:
                raise ValueError("Unreasonable file chunk count")
        elif position != chunks[-1][2] + len(descriptor):
            raise ValueError("Noncontiguous file chunk descriptors")
        chunks.append((offset, packed, position, data))
        remaining -= 1
        if remaining == 0:
            combined = b"".join(chunk[3] for chunk in chunks)
            if len(combined) != entry["bytes"]:
                raise ValueError(f"Unpacked file size mismatch: {entry['name']}")
            yield chunks[0][0], sum(chunk[1] for chunk in chunks), combined, entry, [
                {"offset": hex(start), "packed_bytes": compressed, "bytes": len(decoded),
                 "header_md5_offset": hex(digest_offset), "md5": hashlib.md5(decoded).hexdigest()}
                for start, compressed, digest_offset, decoded in chunks
            ]
            chunks.clear()
            file_count += 1
        offset += packed
    if remaining or file_count != expected_files:
        raise ValueError(f"Expected {expected_files} complete files, found {file_count}")


def find_header_entry(header, position):
    for match in WIDE_NAME.finditer(header, max(0x128, position - 328), position):
        start = match.start()
        if start < 8 or start % 4:
            continue
        size = struct.unpack_from("<I", header, start - 8)[0]
        tag = header[start - 4:start]
        if tag[:2] == b"\0\0" or tag[1:3] != b"\0\0":
            continue
        if start + 2 * tag[3] == position:
            return {"name": match.group()[:-2].decode("utf-16le"), "name_offset": hex(start),
                    "md5_offset": hex(position), "chunks": tag[0], "bytes": size}
    raise ValueError(f"No file name for descriptor at {position:#x}")


def main():
    source = ROOT / "firmware/original/GD13MY"
    output = ROOT / "firmware/extracted/GD13MY"
    evidence = ROOT / "research/evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    records = []
    for kind in ("APP", "BSP", "MICOM", "ACC"):
        header = (source / f"{kind}.hdr").read_bytes()
        payload = (source / f"{kind}.spd.000").read_bytes()
        folder = output / kind
        folder.mkdir(parents=True, exist_ok=True)
        for offset, packed, data, entry, chunks in read_members(header, payload):
            name = entry["name"]
            if not re.fullmatch(r"[A-Za-z0-9_.+ ()-]+", name):
                name = "member.bin"
            path = folder / f"{offset:08x}_{name}"
            if path.exists():
                if path.read_bytes() != data:
                    raise ValueError(f"Existing extraction differs: {path}")
            else:
                with path.open("xb") as file:
                    file.write(data)
            records.append({
                "package": kind, "offset": hex(offset), "packed_bytes": packed,
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "md5": hashlib.md5(data).hexdigest(), "header_entry": entry, "chunks": chunks,
                "output": path.relative_to(ROOT).as_posix(), "magic": data[:16].hex(" "),
                "pe": pe(data) if data.startswith(b"MZ") else None,
            })
        print(f"{kind}: {sum(row['package'] == kind for row in records)} files", flush=True)
    path = evidence / "gd13my-streams.json"
    path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(f"Verified {len(records)} files and {sum(len(row['chunks']) for row in records)} zlib streams. Evidence: {path}")


if __name__ == "__main__":
    main()
