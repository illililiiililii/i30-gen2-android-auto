import os, math, collections
for p in [r"G:\HU\images\NP\rootfs.img"]:
    sz=os.path.getsize(p)
    with open(p,"rb") as f:
        head=f.read(64); f.seek(0); d=f.read(4*1024*1024)
    c=collections.Counter(d); e=-sum((v/len(d))*math.log2(v/len(d)) for v in c.values())
    print(p, "size=",sz, "entropy4M=",round(e,3))
    print("head_hex=",head.hex())
    print("head_ascii=","".join(chr(b) if 32<=b<127 else "." for b in head))
    print("magic16=",head[:16].hex())
