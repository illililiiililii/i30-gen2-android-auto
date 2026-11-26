with open(r"G:\AppUpgrade", "rb") as f:
    data = f.read()

import re
matches = [m.start() for m in re.finditer(b"genesis.keystore", data)]
for idx in matches:
    start = max(0, idx - 200)
    end = min(len(data), idx + 200)
    print("=== Match at 0x%x ===" % idx)
    snippet = data[start:end]
    # filter readable strings
    words = re.findall(b"[\x20-\x7e]{3,}", snippet)
    for w in words:
        print("  ", w.decode('latin1'))
