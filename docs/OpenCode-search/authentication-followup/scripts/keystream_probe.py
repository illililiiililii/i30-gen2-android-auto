import os
a = r"G:\IBOX.tar"; b = r"G:\HU\images\boot.img"
N = 8*1024*1024
da = open(a,"rb").read(N); db = open(b,"rb").read(N)
n = min(len(da),len(db))
same = sum(1 for i in range(n) if da[i]==db[i])
print(f"compared={n} identical_bytes={same} rate={same/n:.5f} (random=0.00391)")
# longest identical run
best=cur=0; start=0; beststart=0
for i in range(n):
    if da[i]==db[i]:
        if cur==0: start=i
        cur+=1
        if cur>best: best=cur; beststart=start
    else: cur=0
print(f"longest_identical_run={best} at offset {beststart}")
# show the run
if best>=16:
    print("a:", da[beststart:beststart+min(best,64)].hex())
    print("b:", db[beststart:beststart+min(best,64)].hex())
# xor entropy
import collections, math
x = bytes(da[i]^db[i] for i in range(min(n,1024*1024)))
c=collections.Counter(x); e=-sum((v/len(x))*math.log2(v/len(x)) for v in c.values())
print(f"xor_first1M_entropy={e:.3f}")
