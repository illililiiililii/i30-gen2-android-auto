import os, collections
def blocks(path, n=8*1024*1024):
    d=open(path,"rb").read(n)
    return d
a=blocks(r"G:\IBOX.tar"); b=blocks(r"G:\HU\images\boot.img")
# periodicity of the shared run
run_a=a[20799:20799+7938]
per=None
for p in range(1,65):
    if all(run_a[i]==run_a[i%p] for i in range(len(run_a))):
        per=p; break
print("shared_run_period:", per)
print("run first 64:", run_a[:64].hex())
# block repeat counts (16-byte)
def rep(d, bs=16):
    c=collections.Counter(d[i:i+bs] for i in range(0,len(d)-bs+1,bs))
    top=c.most_common(3)
    return len(c), top
for name,d in [("IBOX",a),("boot",b)]:
    u,top=rep(d)
    print(f"{name}: blocks={len(d)//16} unique={u} top={[(k.hex()[:32],v) for k,v in top]}")
# where do IBOX and boot match in 16-byte blocks at same offset?
n=min(len(a),len(b)); nb=n//16
match=sum(1 for i in range(nb) if a[i*16:i*16+16]==b[i*16:i*16+16])
print(f"same-offset identical 16B blocks: {match}/{nb} = {match/nb:.4f}")
