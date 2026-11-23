"""Collect PE import/export names and bounded evidence for OEM interfaces."""

import json
import re
import struct

from inspect_firmware import ROOT, pe, strings


def interfaces(data):
    info = pe(data)
    if info is None or info["optional_magic"] != "0x10b":
        return {}
    optional_header = info["pe_offset"] + 24
    directories = optional_header + 96

    def raw(rva):
        for section in info["sections"]:
            delta = rva - section["rva"]
            if 0 <= delta < section["raw_size"]:
                return delta + section["raw_pointer"]
        raise ValueError(f"PE RVA outside file sections: {rva:#x}")

    def name_at(offset):
        end = data.index(b"\0", offset, min(len(data), offset + 512))
        return data[offset:end].decode("ascii", "replace")

    exports = []
    export_rva = struct.unpack_from("<I", data, directories)[0]
    if export_rva:
        offset = raw(export_rva)
        base_ordinal, function_count, name_count, functions, names, ordinals = struct.unpack_from("<6I", data, offset + 16)
        if name_count > 20000:
            raise ValueError("Unexpected PE export count")
        if name_count:
            names_offset = raw(names)
            functions_offset = raw(functions)
            ordinals_offset = raw(ordinals)
            for index in range(name_count):
                offset = raw(struct.unpack_from("<I", data, names_offset + 4 * index)[0])
                ordinal_index = struct.unpack_from("<H", data, ordinals_offset + 2 * index)[0]
                if ordinal_index >= function_count:
                    raise ValueError("PE export ordinal outside function table")
                address = struct.unpack_from("<I", data, functions_offset + 4 * ordinal_index)[0]
                exports.append({"name": name_at(offset), "name_offset": hex(offset),
                                "ordinal": base_ordinal + ordinal_index, "rva": hex(address)})

    imports = {}
    import_rva = struct.unpack_from("<I", data, directories + 8)[0]
    if import_rva:
        descriptor = raw(import_rva)
        for index in range(1024):
            lookup, _, _, name, thunk = struct.unpack_from("<5I", data, descriptor + 20 * index)
            if not name:
                break
            lib = name_at(raw(name))
            target = raw(lookup or thunk)
            imports[lib] = []
            for item in range(12000):
                value = struct.unpack_from("<I", data, target + item * 4)[0]
                if not value:
                    break
                symbol = f"ordinal:{value & 0xffff}" if value & 0x80000000 else name_at(raw(value) + 2)
                imports[lib].append(symbol)
    return {"pe": info, "imports": imports, "exports": exports}


def main():
    evidence = ROOT / "research/evidence"
    source = ROOT / "firmware/original"
    firmware_paths = [source / name for name in ("install.exe", "AVNRecovery.exe")]
    app_paths = list((ROOT / "firmware/extracted/GD13MY/APP").glob("*"))
    results = {}
    for path in [*firmware_paths, *app_paths]:
        if path.suffix.lower() not in {".exe", ".dll"}:
            continue
        entry = interfaces(path.read_bytes())
        if entry:
            results[path.relative_to(ROOT).as_posix()] = entry
    (evidence / "pe-interfaces.json").write_text(json.dumps(results, indent=2), encoding="utf-8")

    boot = ROOT / "firmware/extracted/GD13MY/BSP"
    key = re.compile(r'\b(?:Windows (?:Embedded |Mobile )?CE|OMAP\w{0,18}|TI OMAP\w*|Texas Instruments|ARM Cortex|ARM11\w*|ARM9\w*|SDRAM|NAND|OneNAND|GPMC|Build (?:[0-9]+|Date)|EBOOT|XLDR|U-Boot|H\.264|H264|AVC Decoder|IVA2\w*)\b', re.I)
    matches = []
    for path in sorted(boot.iterdir()):
        if "logo" in path.name:
            continue
        for offset, encoding, value in strings(path.read_bytes()):
            if key.search(value):
                matches.append({"name": path.name, "offset": hex(offset), "encoding": encoding, "text": value[:220]})
    (evidence / "bsp-markers.json").write_text(json.dumps(matches, indent=2), encoding="utf-8")
    print(f"Read imports/exports for {len(results)} PE files and found {len(matches)} BSP markers")


if __name__ == "__main__":
    main()
