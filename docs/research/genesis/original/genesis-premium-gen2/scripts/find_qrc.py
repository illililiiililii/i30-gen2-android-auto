with open(r"G:\AppUpgrade", "rb") as f:
    data = f.read()

import re

# Look for occurrences of "genesis.keystore"
for m in re.finditer(b"genesis\.keystore", data):
    print("Found 'genesis.keystore' at offset 0x%x" % m.start())

# In Qt resources, filenames are UTF-16BE strings prefixed with length and hash
# Let's search for "genesis" in UTF-16BE or UTF-8
for m in re.finditer(b"genesis", data):
    print("Found 'genesis' at 0x%x: %s" % (m.start(), data[m.start():m.start()+30]))
