"""Read a Windows CE BIN image and its ROM table of contents without loading code."""

from bisect import bisect_right
import json
import re
import struct

from inspect_firmware import ROOT, PATTERN, strings


def index_bin(image):
    if not image.startswith(b"B000FF\n"):
        raise ValueError("Not a Windows CE BIN")
    base, image_bytes = struct.unpack_from("<II", image, 7)
    position = 15
    spans = {}
    while position + 12 <= len(image):
        address, size, checksum = struct.unpack_from("<III", image, position)
        position += 12
        if address == 0 and checksum == 0:
            entry = size
            break
        data = image[position:position + size]
        if len(data) != size or sum(data) & 0xffffffff != checksum:
            raise ValueError(f"Windows CE record mismatch at {position - 12:#x}")
        spans[address] = (position, size)
        position += size
    else:
        raise ValueError("Missing final Windows CE record")
    if position != len(image):
        raise ValueError("Unexpected data after final Windows CE record")
    return base, image_bytes, entry, spans


def module_headers(row, read):
    e32, e32_offset = read(row["e32_va"], 110)
    count = struct.unpack_from("<H", e32)[0]
    if not 0 < count <= 32:
        raise ValueError("Unsupported CE module section count")
    sections = []
    for index in range(count):
        raw, offset = read(row["o32_va"] + index * 24, 24)
        sections.append((*struct.unpack("<6I", raw), offset))
    return e32, e32_offset, sections


def inspect_rom(image, *, include_reader=False):
    base, image_bytes, entry, spans = index_bin(image)
    starts = sorted(spans)

    def read(address, count):
        index = bisect_right(starts, address) - 1
        if index < 0:
            raise ValueError(f"Unmapped ROM address {address:#x}")
        start = starts[index]
        offset, size = spans[start]
        delta = address - start
        if count < 0 or delta + count > size:
            raise ValueError(f"Cross-record ROM read at {address:#x}")
        return image[offset + delta:offset + delta + count], offset + delta

    marker, marker_offset = read(base + 0x40, 8)
    if marker[:4] != b"ECEC":
        raise ValueError("Missing ECEC marker")
    rom_address = struct.unpack_from("<I", marker, 4)[0]
    relative_offset = struct.unpack("<I", read(base + 0x48, 4)[0])[0]
    storage_address = base + relative_offset
    alias_delta = rom_address - storage_address
    header, header_offset = read(storage_address, 84)
    fields = struct.unpack("<17I2H3I", header)
    if fields[2] != base + alias_delta:
        raise ValueError("ROM address translation does not match ROMHDR")
    modules, files = fields[4], fields[12]
    if modules > 4096 or files > 8192:
        raise ValueError("Unreasonable ROM table size")
    toc = []
    address = storage_address + len(header)
    for kind, count, length in (("module", modules, 32), ("file", files, 28)):
        for _ in range(count):
            item, offset = read(address, length)
            name_address = struct.unpack_from("<I", item, 16 if kind == "module" else 20)[0] - alias_delta
            name_index = bisect_right(starts, name_address) - 1
            if name_index < 0:
                raise ValueError("Name address below ROM")
            start = starts[name_index]
            raw, name_offset = read(name_address, min(256, start + spans[start][1] - name_address))
            if b"\0" not in raw:
                raise ValueError("Unterminated ROM name")
            row = {"kind": kind, "name": raw.split(b"\0", 1)[0].decode("ascii", "replace"),
                   "record_offset": hex(offset), "name_offset": hex(name_offset)}
            if include_reader:
                if kind == "file":
                    _, _, _, unpacked, packed, _, stored_va = struct.unpack("<7I", item)
                    row.update(unpacked=unpacked, packed=packed, stored_va=stored_va)
                else:
                    row["e32_va"], row["o32_va"], row["load_va"] = struct.unpack_from("<3I", item, 20)
            toc.append(row)
            address += length

    result = {
        "bin_base": hex(base), "bin_declared_span_bytes": image_bytes,
        "entry": hex(entry), "record_count": len(spans), "marker_offset": hex(marker_offset),
        "romhdr_address": hex(rom_address), "romhdr_offset": hex(header_offset),
        "address_alias_delta": hex(alias_delta),
        "machine": hex(fields[17]), "module_count": modules, "file_count": files,
        "ram_start": hex(fields[5]), "ram_free": hex(fields[6]), "ram_end": hex(fields[7]),
        "ram_span_bytes": fields[7] - fields[5], "contents": toc,
    }
    if not include_reader:
        return result

    def read_va(address, count):
        return read(address - alias_delta, count)

    copy_records = []
    for index in range(fields[8]):
        record, offset = read_va(fields[9] + 16 * index, 16)
        source, target, initialized, total = struct.unpack("<4I", record)
        copy_records.append({"source": hex(source), "target": hex(target),
                             "initialized_bytes": initialized, "bytes": total, "rom_offset": hex(offset)})
    result["copy_records"] = copy_records
    result["kernel_flags"] = hex(fields[13])
    return result, read_va


def main():
    evidence = ROOT / "research/evidence"
    rows = json.loads((evidence / "gd13my-streams.json").read_text(encoding="utf-8"))
    roms = {}
    output_path = evidence / "extracted-strings.txt"
    with output_path.open("w", encoding="utf-8") as output:
        for row in rows:
            path = ROOT / row["output"]
            data = path.read_bytes()
            if data.startswith(b"B000FF\n"):
                roms[row["output"]] = inspect_rom(data)
            for offset, encoding, value in strings(data):
                if PATTERN.search(value):
                    output.write(f"{row['output']} {offset:#x} {encoding} {value[:300]}\n")
    (evidence / "ce-rom.json").write_text(json.dumps(roms, indent=2), encoding="utf-8")
    for path, rom in roms.items():
        print(path)
        print({key: value for key, value in rom.items() if key != "contents"})


if __name__ == "__main__":
    main()
