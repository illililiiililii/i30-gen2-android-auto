import os, math, collections
paths = [r"G:\IBOX.tar", r"G:\HU\images\rootfs.img", r"G:\HU\images\boot.img", r"G:\HU\images\vr.img", r"G:\essentials"]
for p in paths:
    try:
        sz = os.path.getsize(p)
    except OSError as e:
        print(p, "ERR", e); continue
    with open(p, "rb") as f:
        head = f.read(64)
        f.seek(0)
        data = f.read(min(sz, 4*1024*1024))
    cnt = collections.Counter(data)
    ent = -sum((c/len(data))*math.log2(c/len(data)) for c in cnt.values())
    printable = sum(1 for b in head if 32 <= b < 127)
    print(f"{p}\n  size={sz} entropy_first4M={ent:.3f} printable_head={printable}/64")
    print("  head_hex=", head.hex())
    print("  head_ascii=", "".join(chr(b) if 32<=b<127 else "." for b in head))
