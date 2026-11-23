"""Read-only source inventory and byte-for-byte verified analysis copy. No target code execution."""
import argparse, csv, hashlib, json, shutil, zlib
from datetime import datetime, timezone
from pathlib import Path

ROOT_FILES = ('AVNRecovery.exe','i30_2013.ver','install.exe','install.md5')
ROOT_DIRS = ('COMMON','GD','GD13MY','GD14MY')

def digest(path):
    sha = hashlib.sha256(); md5 = hashlib.md5(); crc = 0
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024), b''):
            sha.update(b); md5.update(b); crc = zlib.crc32(b, crc)
    return sha.hexdigest(), md5.hexdigest(), f'{crc:08x}'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source',default='F:/'); ap.add_argument('--verify-only',action='store_true'); a=ap.parse_args()
    root=Path(__file__).resolve().parents[1]; source=Path(a.source).resolve(); dest=root/'firmware/original'; out=root/'research/evidence'; out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for p in sorted([source/n for n in ROOT_FILES]+[p for n in ROOT_DIRS for p in (source/n).rglob('*') if p.is_file()]):
        rel=p.relative_to(source); target=dest/rel; before=p.stat(); sha,md5,crc=digest(p)
        if not a.verify_only:
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists():
                if digest(target)[0] != sha: raise RuntimeError(f'Existing copy differs: {target}')
            else: shutil.copy2(p,target)
        if not target.exists() or digest(target)[0]!=sha: raise RuntimeError(f'Copy mismatch: {rel}')
        after=p.stat()
        if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns): raise RuntimeError(f'Source changed: {rel}')
        rows.append(dict(path=rel.as_posix(),name=p.name,extension=p.suffix,size=before.st_size,mtime_utc=datetime.fromtimestamp(before.st_mtime,timezone.utc).isoformat(),sha256=sha,md5=md5,crc32=crc,copy_verified=True))
        print(f'{rel}: {before.st_size} bytes verified',flush=True)
    name='inventory-verify' if a.verify_only else 'inventory'
    (out/f'{name}.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
    with (out/f'{name}.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f'{len(rows)} files, {sum(r["size"] for r in rows)} bytes; all copies verified')

if __name__=='__main__': main()
