"""Classify actual CE artifacts, resolve PE imports and find Ghidra marker RVAs."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from inspect_firmware import ROOT, strings
from inspect_interfaces import interfaces

MACHINES = {0x014c: "x86", 0x01c0: "ARM", 0x01c2: "ARM Thumb",
            0x01c4: "ARMNT", 0x8664: "x86-64", 0xaa64: "ARM64"}
MARKERS = {
    "ucomh_new.exe": r"HandleOfIsv Touch|Starting Upgrade using install|request current display|Create.*application|Dev_.*MIM|RAcc_Off|PowerOff|\\windows\\Touch_Calib|systemCfg",
    "libusb.dll": r"USBInsertThread.*(?:Signal|not USB)|DismountEvtTimerProc|MountCntlThread.*(?:MOUNT|DRIVER)|USB_EJECT_Thread.*USB OFF|%s.*(?:MP3|AVI)|USB_POWER_(?:UP|DOWN)",
    "libvideo.dll": r"REAR.?VIEW|rear.?camera|video authority|RGB|NTSC|PAL",
    "libmmcodec.dll": r"TS.*H264|H264\(H263\)|Cannot open VideoDev|DeviceIoControl|VID\d:|DDrawInit successful|waveOutClose",
    "gddtdmb.exe": r"Video H264|H264 Video|Cannot open VideoDev|sharedPhysBuffer|VID\d:",
    "videodev.dll": r"h264d\.framesInDisplayOrder|VID DECODE|VID ENCODE|DspBridge|DSP\d:|platform.*3530",
    "gddvoicehandler.exe": r"waveIn|Record|Mediazen|Micom|VoiceStart|Microphone",
    "libsound.dll": r"Sound Authority|AVC Status|volume|Mute",
    "libcomm.dll": r"MICOM|MIM[12]:|WM_COPYDATA|COM[1-9]:",
    "default.hv": r"Launch(?:20|25|30|50|60|100)\b|Launch\d+\w|digen_touch|saf7730|musbhcd|musbotg|videodev|dsp_bridge|omap2430_micommgr|PrefixHCD|USBDISK6",
}


def module_name(path):
    return re.sub(r"^[0-9a-f]{8}_", "", path.name, flags=re.I).casefold()


def offset_rva(info, at):
    for section in info["sections"]:
        distance = at - section["raw_pointer"]
        if 0 <= distance < section["raw_size"]:
            return section["rva"] + distance
    return None


def classify(data, pe):
    if pe:
        machine = int(pe["machine"], 16)
        return f"{'Windows CE ' if pe['subsystem'] == 9 else ''}PE {MACHINES.get(machine, hex(machine))}"
    if data.startswith(b"B000FF\n"):
        return "Windows CE BIN"
    if data.startswith(b"HACO STDAVN UPGRADE IMAGE"):
        return "HACO update header"
    if data.startswith(b"BM"):
        return "BMP"
    if data[8:12] == b"EKIM":
        return "CE registry hive"
    return "unclassified data"


def resolver(artifacts, rom):
    known = defaultdict(lambda: defaultdict(set))

    def add(name, exports):
        for row in exports:
            known[name][row["ordinal"]].add(row["name"])

    for name, module in rom["modules"].items():
        add(name.casefold(), module.get("exports", []))
    for name, record in rom["files"].items():
        if record["interfaces"]:
            add(name.casefold(), record["interfaces"]["exports"])
    for path, record in artifacts.items():
        if record["interfaces"]:
            add(module_name(Path(path)), record["interfaces"]["exports"])
    return {name: {ordinal: next(iter(names)) for ordinal, names in entries.items() if len(names) == 1}
            for name, entries in known.items()}


def scan(paths, rom):
    artifacts = {}
    for path in sorted(set(paths)):
        data = path.read_bytes()
        inspection = interfaces(data) if data.startswith(b"MZ") else {}
        pe = inspection.get("pe")
        pattern = MARKERS.get(module_name(path))
        matches = []
        if pattern:
            for position, encoding, value in strings(data):
                if re.search(pattern, value, re.I):
                    value = " ".join(value.split())[:155]
                    rva = offset_rva(pe, position) if pe else None
                    matches.append({"offset": hex(position), "rva": None if rva is None else hex(rva),
                                    "text": value, "encoding": encoding})
        wrapper = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        artifacts[wrapper.replace("\\", "/")] = {
            "format": classify(data, pe), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "interfaces": inspection, "markers": matches,
        }

    index = resolver(artifacts, rom)
    for record in artifacts.values():
        resolved_imports = {}
        for library, symbols in record["interfaces"].get("imports", {}).items():
            exports = index.get(library.casefold(), {})
            resolved_imports[library] = [
                {"raw": symbol, "name": exports.get(int(symbol.split(":")[1])) if symbol.startswith("ordinal:") else symbol}
                for symbol in symbols
            ]
        record["resolved_imports"] = resolved_imports
    return artifacts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", type=Path, help="Specific local input files")
    parser.add_argument("--output", type=Path, default=ROOT / "research/evidence/phase1-scan.json")
    args = parser.parse_args()
    rom = json.loads((ROOT / "research/evidence/phase1-rom.json").read_text(encoding="utf-8"))
    extracted = ROOT / "firmware/extracted/GD13MY"
    paths = args.paths or [*extracted.glob("APP/*"), *extracted.glob("BSP/*"), *extracted.glob("ROM/*")]
    records = scan([path.resolve() for path in paths], rom)
    args.output.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.paths:
        marker_path = args.output.with_name("phase1-markers.tsv")
        with marker_path.open("w", encoding="utf-8") as out:
            for path, record in records.items():
                for marker in record["markers"]:
                    if marker["rva"] is not None:
                        print(Path(path).name, marker["rva"][2:], marker["offset"], marker["text"],
                              sep="\t", file=out)
    print(dict(Counter(record["format"] for record in records.values())))


if __name__ == "__main__":
    main()
