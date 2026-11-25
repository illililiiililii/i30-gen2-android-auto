#!/usr/bin/env python3
"""Deep certificate / PKCS#7 / TLS-identity scan for a firmware tree.

Searches for DER-encoded OIDs, PEM armour, PKCS#7 SignedData, and
Android Auto identity strings.  Large images are scanned in chunks.

Usage:
    python scan_firmware_certs.py G:\\  [--max-full 67108864] [--json out.json]

Design notes:
  * OID byte patterns are long enough that random hits in encrypted data
    are negligible, so an OID hit is real evidence of ASN.1 content.
  * The script never writes to the scanned tree.
"""
import argparse
import json
import os
import sys

PEM = b"-----BEGIN "

OIDS = {
    "rsaEncryption": bytes.fromhex("06092a864886f70d010101"),
    "sha1WithRSA": bytes.fromhex("06092a864886f70d010105"),
    "sha256WithRSA": bytes.fromhex("06092a864886f70d01010b"),
    "signedData": bytes.fromhex("06092a864886f70d010702"),
    "pkcs7_data": bytes.fromhex("06092a864886f70d010701"),
    "commonName": bytes.fromhex("0603550403"),
    "organizationName": bytes.fromhex("060355040a"),
    "countryName": bytes.fromhex("0603550406"),
    "subjectKeyIdentifier": bytes.fromhex("0603551d0e"),
    "authorityKeyIdentifier": bytes.fromhex("0603551d23"),
    "basicConstraints": bytes.fromhex("0603551d13"),
    "extKeyUsage": bytes.fromhex("0603551d25"),
    "serverAuth": bytes.fromhex("06082b06010505070301"),
    "clientAuth": bytes.fromhex("06082b06010505070302"),
}

STRINGS = [
    b"Google Automotive Link",
    b"Android-Auto-Internal",
    b"CarService",
    b"AndroidAuto",
    b"Android Auto",
    b"Google Automotive",
    b"headunit",
    b"HEADUNIT",
    b"mbedtls_x509",
    b"X509_verify_cert",
    b"SSL_CTX_use_certificate",
    b"TLSv1.2",
    b"clientAuth",
    b"PKCS7",
    b"pkcs7",
]

CHUNK = 32 * 1024 * 1024
OVERLAP = 64


def scan_blob(data, base, hits, path):
    for name, pat in OIDS.items():
        start = 0
        while True:
            i = data.find(pat, start)
            if i < 0:
                break
            hits["oids"].append({"file": path, "oid": name, "offset": base + i})
            start = i + 1
            if len(hits["oids"]) > 5000:
                return
    i = data.find(PEM)
    if i >= 0:
        hits["pem"].append({"file": path, "offset": base + i})
    for s in STRINGS:
        start = 0
        while True:
            i = data.find(s, start)
            if i < 0:
                break
            hits["strings"].append(
                {"file": path, "string": s.decode("latin1"), "offset": base + i}
            )
            start = i + 1
            if len(hits["strings"]) > 5000:
                return


def scan_file(path, size, full_limit, hits):
    with open(path, "rb") as f:
        if size <= full_limit:
            scan_blob(f.read(), 0, hits, path)
            return
        carry = b""
        base = 0
        while True:
            buf = f.read(CHUNK)
            if not buf:
                break
            data = carry + buf
            scan_blob(data, base - len(carry), hits, path)
            carry = data[-OVERLAP:]
            base += len(buf)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--max-full", type=int, default=64 * 1024 * 1024)
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    hits = {"oids": [], "pem": [], "strings": [], "files": 0, "bytes": 0}
    for dirpath, dirnames, filenames in os.walk(args.root):
        dirnames[:] = [d for d in dirnames if d.lower() != "system volume information"]
        for fn in filenames:
            path = os.path.join(dirpath, fn)
            try:
                size = os.path.getsize(path)
            except OSError:
                continue
            hits["files"] += 1
            hits["bytes"] += size
            try:
                scan_file(path, size, args.max_full, hits)
            except OSError as exc:
                print(f"ERR {path}: {exc}", file=sys.stderr)

    print(f"files={hits['files']} bytes={hits['bytes']}")
    print(f"pem_hits={len(hits['pem'])} oid_hits={len(hits['oids'])} string_hits={len(hits['strings'])}")
    for name in ("pem", "oids", "strings"):
        for h in hits[name][:60]:
            print(name, h)
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(hits, f, indent=1)
        print("json:", args.json)


if __name__ == "__main__":
    raise SystemExit(main())
