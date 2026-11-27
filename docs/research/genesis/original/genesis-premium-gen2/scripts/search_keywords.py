import os
import re

search_dirs = [r"G:\BIN", r"G:\LIB", r"G:\HU"]
keywords = [
    b"androidauto", b"android auto", b"gal", b"aap", b"phoneprojection",
    b"carplay", b"aoa", b"accessory", b"cinemo", b"allgo", b"motrex",
    b"projection", b"authcomplete", b"servicediscovery"
]

results = {}

for sdir in [r"G:\BIN", r"G:\LIB", r"G:"]:
    for fname in os.listdir(sdir):
        fpath = os.path.join(sdir, fname)
        if os.path.isfile(fpath) and os.path.getsize(fpath) < 50 * 1024 * 1024:
            try:
                with open(fpath, "rb") as f:
                    content = f.read()
                content_lower = content.lower()
                for kw in keywords:
                    if kw in content_lower:
                        if fname not in results:
                            results[fname] = []
                        # Find occurrences
                        for m in re.finditer(kw, content_lower):
                            start = max(0, m.start() - 30)
                            end = min(len(content), m.end() + 30)
                            snippet = content[start:end].replace(b"\n", b" ").replace(b"\r", b" ")
                            results[fname].append((kw.decode(), snippet))
                            if len(results[fname]) > 5:
                                break
            except Exception as e:
                pass

for fname, matches in results.items():
    print(f"=== File: {fname} ===")
    for kw, snip in matches[:5]:
        print(f"  [{kw}] {snip}")
