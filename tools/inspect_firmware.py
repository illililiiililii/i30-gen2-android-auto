"""Static format, strings, PE and compression evidence. Never executes firmware."""
import collections, hashlib, json, math, re, struct, zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PATTERN=re.compile(r'GD13|SOP|Windows|WinCE|CE [0-9]|Telechips|TCC[0-9]|ARM|MIPS|iMX|i\.MX|Freescale|Samsung|S3C|Linux|NK\.bin|EBOOT|BOOT|H264|H\.264|AVC|USB|OHCI|EHCI|DirectDraw|DirectShow|WaveOut|waveIn|Touch|CAN|MICOM|Bluetooth|DiskA|NAND|SDRAM|DDR|RSA|SHA|MD5|AES|Crypto|Signature|Decrypt|Compress|Decompress',re.I)

def strings(data):
    for m in re.finditer(rb'[\x20-\x7e]{5,}',data): yield m.start(),'ascii',m.group().decode('ascii')
    for m in re.finditer(rb'(?:[\x20-\x7e]\x00){5,}',data): yield m.start(),'utf16le',m.group().decode('utf-16le')

def pe(data,at=0):
    try:
        off=at+struct.unpack_from('<I',data,at+0x3c)[0]
        if data[off:off+4]!=b'PE\0\0': return None
        machine,nsec,stamp,_,_,optsize,flags=struct.unpack_from('<HHIIIHH',data,off+4)
        opt=off+24; magic=struct.unpack_from('<H',data,opt)[0]
        sections=[]
        for i in range(nsec):
            s=opt+optsize+i*40; name=data[s:s+8].split(b'\0')[0].decode('ascii','replace');vs,va,rs,rp=struct.unpack_from('<IIII',data,s+8)
            sections.append(dict(name=name,virtual_size=vs,rva=va,raw_size=rs,raw_pointer=rp))
        return dict(pe_offset=off,machine=hex(machine),sections=sections,optional_magic=hex(magic),entry_rva=hex(struct.unpack_from('<I',data,opt+16)[0]),image_base=hex(struct.unpack_from('<I',data,opt+28)[0]) if magic==0x10b else None,os_version=struct.unpack_from('<HH',data,opt+40),subsystem_version=struct.unpack_from('<HH',data,opt+48),subsystem=struct.unpack_from('<H',data,opt+68)[0],security_directory=struct.unpack_from('<II',data,opt+(96 if magic==0x10b else 112)+32))
    except (struct.error,IndexError): return None

def main():
    evidence=ROOT/'research/evidence';evidence.mkdir(parents=True,exist_ok=True)
    out=[]
    files=[p for p in (ROOT/'firmware/original').rglob('*') if p.is_file() and p.stat().st_size<100_000_000]
    for p in sorted(files):
        d=p.read_bytes(); c=collections.Counter(d[:1024*1024]); n=sum(c.values()); entropy=-sum((v/n)*math.log2(v/n) for v in c.values()) if n else 0
        ss=[dict(offset=hex(o),encoding=e,text=s[:1000]) for o,e,s in strings(d) if PATTERN.search(s)]
        sigs={k:[hex(m.start()) for m in re.finditer(re.escape(v),d)][:80] for k,v in {'PE_DOS':b'MZ','ELF':b'\x7fELF','gzip':b'\x1f\x8b\x08','zip':b'PK\x03\x04','WinCE_BIN':b'B000FF\n','ROMHDR_ECEC':b'\x45\x43\x45\x43','uimage':b'\x27\x05\x19\x56','squashfs':b'hsqs','zlib_789c':b'\x78\x9c','zlib_78da':b'\x78\xda'}.items()}
        row=dict(path=p.relative_to(ROOT/'firmware/original').as_posix(),size=len(d),sha256=hashlib.sha256(d).hexdigest(),head_hex=d[:256].hex(' '),entropy_first_mib=entropy,pe=pe(d),signatures=sigs,strings=ss)
        out.append(row); print(row['path'],len(d),'PE=',row['pe'],'strings=',len(ss),'entropy=',round(entropy,3),flush=True)
    (evidence/'static-initial.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
    with (evidence/'strings-initial.txt').open('w',encoding='utf-8') as f:
        for row in out:
            for s in row['strings']:f.write(f"{row['path']} {s['offset']} {s['encoding']} {s['text']}\n")

if __name__=='__main__':main()
