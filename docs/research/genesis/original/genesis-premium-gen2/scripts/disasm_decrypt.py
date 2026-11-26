import capstone
from elftools.elf.elffile import ELFFile

md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

binary_path = r"F:\i30-gen2-android-auto\research\genesis-premium-gen2\extracted\essentials\decrypt\DecryptToFile"

with open(binary_path, "rb") as f:
    elf = ELFFile(f)
    text_sec = elf.get_section_by_name(".text")
    text_addr = text_sec["sh_addr"]
    text_data = text_sec.data()
    
    symtab = elf.get_section_by_name(".symtab")
    syms = {s.name: s for s in symtab.iter_symbols()}
    
    def disasm_func(func_name):
        s = syms.get(func_name)
        if not s:
            print(f"Symbol {func_name} not found")
            return
        addr = s["st_value"]
        size = s["st_size"]
        offset = addr - text_addr
        code = text_data[offset:offset+size]
        print(f"=== {func_name} (0x{addr:x}, {size} bytes) ===")
        for insn in md.disasm(code, addr):
            print(f"0x{insn.address:x}: {insn.mnemonic}\t{insn.op_str}")

    disasm_func("LGUCheckEncryptFile")
    disasm_func("LGUGetKeyForFile")
    disasm_func("LGUGetKeyData")
