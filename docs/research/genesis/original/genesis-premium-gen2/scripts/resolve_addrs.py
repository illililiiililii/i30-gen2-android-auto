from elftools.elf.elffile import ELFFile

binary_path = r"F:\i30-gen2-android-auto\research\genesis-premium-gen2\extracted\essentials\decrypt\DecryptToFile"

with open(binary_path, "rb") as f:
    elf = ELFFile(f)
    symtab = elf.get_section_by_name(".symtab")
    addrs = {0x8057840, 0x80556d0, 0x8050af0, 0x8055d50, 0x8056bb0, 0x8056780, 0x8059c90, 0x80575c0, 0x8056af0, 0x8048c10, 0x8048c40, 0x8048c50, 0x8048d70, 0x8048cc0}
    for sym in symtab.iter_symbols():
        val = sym['st_value']
        if val in addrs:
            print(f"0x{val:x} -> {sym.name}")
