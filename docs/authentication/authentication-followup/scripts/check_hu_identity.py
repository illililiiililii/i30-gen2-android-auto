#!/usr/bin/env python3
"""Check whether a head-unit certificate/key pair is usable as an Android Auto
TLS client identity.

Reports, for one certificate:

  * subject / issuer / serial / validity / SHA-256 fingerprint
  * the ASN.1 time encoding (``Z`` vs a numeric offset such as ``-0700``)
  * whether the chain verifies strictly against a given root
  * whether the certificate and private key belong together
  * a plain-language verdict

Why this exists: BearSSL 0.6 (and OpenSSL's verifier) reject UTCTime values that
end in a numeric offset.  Google Automotive Link head-unit certificates from
2014-2018 use ``-0700``; the DHU reference certificate uses ``Z``.  A pair that
"looks fine" in ``openssl x509 -text`` can therefore fail to load at all.

Usage:
    python check_hu_identity.py CERT KEY ROOT [--openssl PATH]

Exit status: 0 if the chain verifies strictly, the key matches and every time
value ends in ``Z``; 1 otherwise.
"""
import argparse
import re
import shutil
import subprocess
import sys

DEFAULT_OPENSSL = r"C:\Program Files\Git\usr\bin\openssl.exe"


def run(openssl, *args):
    proc = subprocess.run(
        [openssl, *args], capture_output=True, text=True, errors="replace"
    )
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def field(text, name):
    match = re.search(rf"^{name}\s*=\s*(.+)$", text, re.MULTILINE)
    return match.group(1).strip() if match else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cert")
    ap.add_argument("key")
    ap.add_argument("root")
    ap.add_argument("--openssl", default=None)
    args = ap.parse_args()

    openssl = args.openssl or shutil.which("openssl") or DEFAULT_OPENSSL
    if not shutil.which(openssl) and not __import__("os").path.exists(openssl):
        print(f"openssl not found: {openssl}", file=sys.stderr)
        return 2

    ok = True

    rc, text = run(openssl, "x509", "-in", args.cert, "-noout",
                   "-subject", "-issuer", "-serial", "-dates",
                   "-fingerprint", "-sha256")
    print("== certificate ==")
    print(text.strip())
    if rc != 0:
        print("certificate could not be parsed", file=sys.stderr)
        return 2

    rc, text = run(openssl, "asn1parse", "-in", args.cert, "-i")
    times = re.findall(r"(UTCTIME|GENERALIZEDTIME)\s*:\s*(\S+)", text)
    print("\n== time encoding ==")
    if not times:
        print("no UTCTIME/GENERALIZEDTIME found")
        ok = False
    for kind, value in times:
        offset = bool(re.search(r"[+-]\d{4}$", value))
        state = "OFFSET (BearSSL rejects)" if offset else "Z (ok)"
        print(f"  {kind:16} {value:20} {state}")
        if offset:
            ok = False

    print("\n== chain ==")
    rc, text = run(openssl, "verify", "-CAfile", args.root, args.cert)
    strict = rc == 0
    print("  strict:       ", "OK" if strict else "FAILED")
    if not strict:
        for line in text.strip().splitlines():
            print("    " + line)
        rc2, _ = run(openssl, "verify", "-no_check_time",
                     "-CAfile", args.root, args.cert)
        print("  -no_check_time:", "OK" if rc2 == 0 else "FAILED")
    if not strict:
        ok = False

    print("\n== key pair ==")
    _, cert_mod = run(openssl, "x509", "-in", args.cert, "-noout", "-modulus")
    _, key_mod = run(openssl, "rsa", "-in", args.key, "-noout", "-modulus")
    pair = cert_mod.strip() and cert_mod.strip() == key_mod.strip()
    print("  modulus match:", "YES" if pair else "NO")
    if not pair:
        ok = False

    print("\n== verdict ==")
    if ok:
        print("  USABLE with unmodified BearSSL 0.6 ce_aa_tls.c configure()")
    else:
        print("  NOT loadable as-is: fix the parser or choose another pair")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
