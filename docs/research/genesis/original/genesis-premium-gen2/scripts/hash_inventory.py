import os
import hashlib
import time

def hash_file(path, max_bytes=None):
    h = hashlib.sha256()
    size = os.path.getsize(path)
    read_total = 0
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            read_total += len(chunk)
            if max_bytes and read_total >= max_bytes:
                break
    return h.hexdigest(), size

files_to_hash = [
    r"G:\GENESIS_G80_DIS_Bluelink.ver",
    r"G:\.lge.upgrade.xml",
    r"G:\.lge.upgrade_enc.xml",
    r"G:\AppUpgrade",
    r"G:\essentials",
    r"G:\BIN\APPNAVI",
    r"G:\BIN\TPEGSERVICE",
    r"G:\BIN\QML\DHAVN_APPNAVI_MAIN.qml",
    r"G:\LIB\LIBTPEGDECODER.so",
    r"G:\LIB\LIBMGDIQTYPE.so",
    r"G:\LIB\LIBREDRELAY_1.so",
    r"G:\LIB\LIBREDENGINE3D.so",
    r"G:\LIB\LIBIENGINE1.so",
    r"G:\HU\images\boot.img",
    r"G:\IBOX.tar"
]

print("Computing SHA-256 hashes...")
for p in files_to_hash:
    if os.path.exists(p):
        t0 = time.time()
        # For very large files (>1GB) like rootfs.img or vr.img, we can note size or compute if needed
        sha, sz = hash_file(p)
        dt = time.time() - t0
        print(f"{os.path.basename(p)} | {sz:,} bytes | {sha} | {dt:.1f}s")
    else:
        print(f"Missing: {p}")
