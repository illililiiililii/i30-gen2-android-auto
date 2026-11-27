with open(r"G:\BIN\APPNAVI", "rb") as f:
    data = f.read()

import re
matches = [m.start() for m in re.finditer(b"Provisioning", data, re.IGNORECASE)]
for idx in matches:
    start = max(0, idx - 150)
    end = min(len(data), idx + 150)
    print("=== Match at 0x%x ===" % idx)
    words = re.findall(b"[\x20-\x7e]{3,}", data[start:end])
    for w in words:
        print("  ", w.decode('latin1'))
