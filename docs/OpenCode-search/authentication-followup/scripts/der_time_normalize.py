#!/usr/bin/env python3
"""Normalize ASN.1 UTCTime/GeneralizedTime values that use a numeric
timezone offset (e.g. "-0700") into the RFC 5280 form ending in "Z".

Why: Google Automotive Link head-unit certificates (DHU 2.1, AASDK/JVC)
encode Validity as e.g. "140704000000-0700".  DER requires "Z", and both
OpenSSL's default verifier and BearSSL's x509 decoder reject the offset
form.  This tool rewrites the *time value only* and recomputes every
enclosing DER length, so the result can be used to prove that the time
encoding (not the chain) is what a parser rejected.

NOTE: rewriting TBS invalidates the certificate signature.  The output is
a parser test vector only, never a usable identity.

Usage:
    python der_time_normalize.py input.der output.der
"""
import sys
from datetime import datetime, timedelta


def parse_tlv(buf, off):
    """Return (tag, header_len, content_len, content_off, end)."""
    if off + 2 > len(buf):
        raise ValueError("truncated TLV")
    tag = buf[off]
    p = off + 1
    first = buf[p]
    p += 1
    if first < 0x80:
        length = first
        header = p - off
    else:
        n = first & 0x7F
        if n == 0 or p + n > len(buf):
            raise ValueError("bad length")
        length = int.from_bytes(buf[p:p + n], "big")
        p += n
        header = p - off
    return tag, header, length, p, p + length


def encode_len(n):
    if n < 0x80:
        return bytes([n])
    body = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(body)]) + body


def normalize_time(raw):
    """raw is the content bytes of a UTCTime/GeneralizedTime."""
    text = raw.decode("ascii", "strict")
    if text.endswith("Z"):
        return raw
    if len(text) < 5 or text[-5] not in "+-":
        return raw
    sign = 1 if text[-5] == "+" else -1
    hh = int(text[-4:-2])
    mm = int(text[-2:])
    digits = text[:-5]
    if len(digits) == 12:
        dt = datetime.strptime(digits, "%y%m%d%H%M%S")
        if dt.year < 1970:
            dt = dt.replace(year=dt.year + 100)
        fmt_len = 2
    elif len(digits) == 14:
        dt = datetime.strptime(digits, "%Y%m%d%H%M%S")
        fmt_len = 4
    else:
        return raw
    dt = dt - sign * timedelta(hours=hh, minutes=mm)
    if fmt_len == 2:
        out = dt.strftime("%y%m%d%H%M%S") + "Z"
    else:
        out = dt.strftime("%Y%m%d%H%M%S") + "Z"
    return out.encode("ascii")


def rebuild(buf, off, end):
    """Recursively rebuild one TLV, normalizing time values."""
    tag, header, length, content_off, tlv_end = parse_tlv(buf, off)
    if tlv_end > end:
        raise ValueError("TLV overruns parent")
    constructed = bool(tag & 0x20)
    if constructed:
        out = bytearray()
        p = content_off
        while p < tlv_end:
            child, p = rebuild(buf, p, tlv_end)
            out += child
        content = bytes(out)
    else:
        content = bytes(buf[content_off:tlv_end])
        if tag in (0x17, 0x18):
            content = normalize_time(content)
    return bytes([tag]) + encode_len(len(content)) + content, tlv_end


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    data = open(sys.argv[1], "rb").read()
    out, end = rebuild(data, 0, len(data))
    if end != len(data):
        raise SystemExit("trailing bytes after certificate")
    open(sys.argv[2], "wb").write(out)
    print(f"wrote {sys.argv[2]} ({len(out)} bytes, input {len(data)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
