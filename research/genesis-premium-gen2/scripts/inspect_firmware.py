import os
import re
from elftools.elf.elffile import ELFFile

def inspect_appupgrade():
    with open(r"G:\AppUpgrade", "rb") as f:
        elf = ELFFile(f)
        symtab = elf.get_section_by_name(".symtab")
        if symtab:
            for sym in symtab.iter_symbols():
                name = sym.name
                if any(w in name.lower() for w in ["decrypt", "ibox", "essential", "key"]):
                    print(f"Symbol: {name} @ 0x{sym['st_value']:x}")
        else:
            print("AppUpgrade has no .symtab (stripped)")

inspect_appupgrade()
