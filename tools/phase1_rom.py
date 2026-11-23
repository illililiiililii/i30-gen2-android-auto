"""Inspect the observed GD13MY CE6 XIP layout and extract selected ROM files."""

import argparse
from functools import cache
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import struct

from inspect_ce import inspect_rom, module_headers
from inspect_firmware import ROOT, strings
from inspect_interfaces import interfaces

LAYOUT_ERROR = "Unsupported CE module layout"
MAX_DATA = 8 * 1024 * 1024
MODULES = {"nk.exe", "kernel.dll", "coredll.dll", "device.dll", "udevice.exe", "gwes.dll",
           "AutoStartUp.exe", "AVNSysInit.exe", "usbd.dll", "musbhcd.dll", "musbotg.dll",
           "usbmsc.dll", "usbdisk6.dll", "waveapi.dll", "saf7730wav.dll", "digen_touch.dll",
           "ddraw.dll", "camera.dll", "ddi.dll", "omap2430_micommgr_cdp.dll", "uart.dll"}
FILES = {"videodev.dll", "dsp_bridge.dll", "AComH_New.exe", "boot.hv", "default.hv", "user.hv"}
MODULE_MARKERS = {
    "AutoStartUp.exe": r"\.exe|Signaled|CreateProcess|Disk[A-Z]|\bOEM\b",
    "AVNSysInit.exe": r"\.exe|CreateProcess|Disk[A-Z]|\.dll|\bOEM\b",
    "musbhcd.dll": r"High.?Speed|Full.?Speed|USB.*(attach|connect|enumerat)|MUSB",
    "ddi.dll": r"800.?480|display|\bbpp\b|overlay|pixel",
    "saf7730wav.dll": r"Audio|Mixer|wave|capture",
}


@cache
def decoder():
    path = ROOT / "tools/vendor/wince-decompr/wincedecompr.py"
    digest = hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    if digest != "42693ba5e756f664d2405bdaa2f6f9bc5671b5956439aeed581c8e7e89f2e72d":
        raise ValueError("Use the pinned, reviewed wince-decompr source")
    spec = importlib.util.spec_from_file_location("wincedecompr", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CEDecompressROM


def expand(data, expected):
    if not 0 < expected <= MAX_DATA or len(data) < 6 or len(data) >= expected:
        raise ValueError("Invalid compressed CE block dimensions")
    size = int.from_bytes(data[:3], "little")
    count = (size + 4095) // 4096
    table_end = (count + 1) * 3
    if not count or not size <= expected or table_end > len(data):
        raise ValueError("Invalid CE block table")
    boundaries = [table_end]
    boundaries.extend(int.from_bytes(data[i:i + 3], "little") for i in range(3, table_end, 3))
    if boundaries[-1] > len(data) or any(b <= a for a, b in zip(boundaries, boundaries[1:])):
        raise ValueError("Invalid CE block boundaries")
    output = bytearray(expected)
    actual = decoder()(data, len(data), output, expected, 0, 1, 4096)
    if actual != expected:
        raise ValueError(f"CE decode size mismatch: {actual} != {expected}")
    return bytes(output)


def module_details(row, read):
    e32, e32_offset, sections = module_headers(row, read)
    _, _, entry, base, major, minor, stack, virtual_size = struct.unpack_from("<HHIIHHII", e32)
    export_rva, export_size = struct.unpack_from("<II", e32, 0x24)
    if not virtual_size or export_rva + export_size > virtual_size:
        raise ValueError(LAYOUT_ERROR)

    @cache
    def section_data(index):
        size, _, packed, data_va, _, flags, _ = sections[index]
        compressed = bool(flags & 0x2000)
        data, position = read(data_va, packed if compressed else min(size, packed))
        if not compressed:
            return data, position
        initialized = int.from_bytes(data[:3], "little")
        if initialized > size:
            raise ValueError("Initialized section exceeds virtual span")
        return expand(data, initialized), None

    def view(rva, size):
        for index, (span, start, packed, *_) in enumerate(sections):
            if 0 <= rva - start < span and packed:
                data, position = section_data(index)
                delta = rva - start
                data = data[delta:delta + size]
                return data, None if position is None else position + delta
        raise ValueError(f"Unmapped RVA {rva:#x} in {row['name']}")

    exports = []
    if export_size >= 40:
        offset = view(export_rva, 40)[0]
        start, table_size, name_count, table, names, ordinals = struct.unpack_from("<6I", offset, 16)
        if table_size > 20000 or name_count > table_size:
            raise ValueError("Invalid ROM export count")
        if name_count:
            functions = view(table, table_size * 4)[0]
            names = view(names, name_count * 4)[0]
            ordinals = view(ordinals, name_count * 2)[0]
            for index in range(name_count):
                ordinal = struct.unpack_from("<H", ordinals, index * 2)[0]
                name_rva = struct.unpack_from("<I", names, index * 4)[0]
                name, name_offset = view(name_rva, 256)
                if b"\0" not in name or ordinal >= table_size:
                    raise ValueError("Invalid ROM export name or ordinal")
                address = struct.unpack_from("<I", functions, ordinal * 4)[0]
                exports.append({"name": name.split(b"\0", 1)[0].decode("ascii"),
                                "ordinal": start + ordinal, "rva": hex(address),
                                "name_offset": None if name_offset is None else hex(name_offset)})
    markers = []
    if row["name"] in MODULE_MARKERS:
        pattern = re.compile(MODULE_MARKERS[row["name"]], re.I)
        for index, (size, rva, packed, *_) in enumerate(sections):
            if not packed:
                continue
            data, offset = section_data(index)
            for local, encoding, value in strings(data):
                if pattern.search(value):
                    markers.append({"rva": hex(rva + local), "encoding": encoding,
                                    "offset": None if offset is None else hex(offset + local), "text": value[:160]})
    return {"name": row["name"], "e32_offset": hex(e32_offset), "subsystem_version": [major, minor],
            "virtual_base": hex(base), "entry_rva": hex(entry), "stack_reserve_bytes": stack,
            "virtual_size": virtual_size, "exports": exports, "markers": markers[:160],
            "sections": [{"size": size, "rva": hex(rva), "stored_bytes": packed, "stored_va": hex(data),
                          "runtime_va": hex(runtime), "flags": hex(flags), "o32_offset": hex(at)}
                         for size, rva, packed, data, runtime, flags, at in sections]}


def collect(image, output):
    rom, read = inspect_rom(image, include_reader=True)
    details = {"rom": {k: v for k, v in rom.items() if k != "contents"}, "modules": {}, "files": {}}
    output.mkdir(parents=True, exist_ok=True)
    for row in rom["contents"]:
        name = row["name"]
        if row["kind"] == "module" and name in MODULES:
            try:
                details["modules"][name] = module_details(row, read)
            except (ValueError, struct.error) as error:
                details["modules"][name] = {"error": str(error), "record_offset": row["record_offset"]}
        if row["kind"] == "file" and name in FILES:
            data, offset = read(row["stored_va"], row["packed"])
            if row["packed"] != row["unpacked"]:
                data = expand(data, row["unpacked"])
            target = output / name
            if target.exists() and target.read_bytes() != data:
                raise ValueError(f"Different ROM extraction already exists: {target}")
            if not target.exists():
                target.write_bytes(data)
            details["files"][name] = {
                "toc_offset": row["record_offset"], "stored_offset": hex(offset),
                "decoded_bytes": len(data), "stored_bytes": row["packed"],
                "sha256": hashlib.sha256(data).hexdigest(), "interfaces": interfaces(data),
            }
    return details


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=ROOT / "firmware/extracted/GD13MY/BSP/0002dfc7_kernel")
    args = parser.parse_args()
    output = ROOT / "firmware/extracted/GD13MY/ROM"
    evidence = ROOT / "research/evidence/phase1-rom.json"
    rom = collect(args.rom.read_bytes(), output)
    evidence.write_text(json.dumps(rom, indent=2), encoding="utf-8")
    print(f"{len(rom['modules'])} selected modules, {len(rom['files'])} extracted files: {evidence}")


if __name__ == "__main__":
    main()
