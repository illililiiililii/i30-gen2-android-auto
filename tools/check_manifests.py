"""Compare the stock checksums to the recorded inventory and analysis copy."""

import hashlib
import json
import zlib
from pathlib import Path

from inspect_firmware import ROOT


def crc32(path, block_bytes=None):
    with path.open("rb") as handle:
        if block_bytes is not None:
            return [f"{zlib.crc32(block):08x}" for block in iter(lambda: handle.read(block_bytes), b"")]
        checksum = 0
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            checksum = zlib.crc32(block, checksum)
        return [f"{checksum:08x}"] if path.stat().st_size else []


def main():
    evidence = ROOT / "research/evidence"
    source = ROOT / "firmware/original"
    files = {row["path"]: row for row in json.loads((evidence / "inventory.json").read_text(encoding="utf-8"))}
    version_manifest = []
    for line in (source / "i30_2013.ver").read_text(encoding="ascii").splitlines()[1:]:
        location, name, _, signed_crc, size, _ = line.split("|")
        relative = location.removeprefix("i30_2013").replace("\\", "/").strip("/")
        path = f"{relative}/{name}" if relative else name
        observed = files[path]
        crc = f"{int(signed_crc) & 0xffffffff:08x}"
        version_manifest.append({"path": path, "crc32": crc,
                                 "match": crc == observed["crc32"] and int(size) == observed["size"]})

    crc_manifest = []
    for line in (source / "GD13MY/install.crc").read_text(encoding="ascii").splitlines()[1:]:
        name, size, *expected = line.split("\t")
        relative = (Path("GD13MY") / name)
        copy = (source / relative).resolve()
        relative = copy.relative_to(source.resolve()).as_posix()
        expected = [value for value in expected if value]
        if len(expected) > 1:
            observed = crc32(copy, 32 * 1024 * 1024)
        else:
            observed = [files[relative]["crc32"]] if int(size) else []
        crc_manifest.append({"path": relative, "blocks": len(expected), "match":
                             expected == observed and int(size) == copy.stat().st_size})

    md5 = hashlib.md5((source / "install.exe").read_bytes()).hexdigest()
    md5_match = md5 == (source / "install.md5").read_bytes().hex()
    results = {"version_manifest": version_manifest, "crc_manifest": crc_manifest,
               "install_md5": md5, "install_md5_match": md5_match}
    path = evidence / "manifest-checks.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    failed = [row["path"] for row in version_manifest + crc_manifest if not row["match"]]
    print(f".ver entries: {len(version_manifest)}, .crc entries: {len(crc_manifest)}, installer MD5: {md5_match}")
    if failed or not md5_match:
        raise SystemExit(f"Checksum differences: {failed}")


if __name__ == "__main__":
    main()
