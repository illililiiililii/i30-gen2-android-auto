from elftools.elf.elffile import ELFFile
import capstone

binary_path = r"G:\AppUpgrade"

with open(binary_path, "rb") as f:
    elf = ELFFile(f)
    rodata = elf.get_section_by_name(".rodata")
    r_addr = rodata['sh_addr']
    r_data = rodata.data()
    
    text_sec = elf.get_section_by_name(".text")
    t_addr = text_sec['sh_addr']
    t_data = text_sec.data()

    start_va = 0x8077280
    end_va = 0x8077850
    code = t_data[start_va - t_addr : end_va - t_addr]
    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
    print(f"=== Disassembly 0x{start_va:x} to 0x{end_va:x} ===")
    for insn in md.disasm(code, start_va):
        extra = ""
        for op in insn.op_str.split(","):
            op = op.strip()
            if op.startswith("0x80d") or op.startswith("0x80e"):
                try:
                    val = int(op, 16)
                    off = val - r_addr
                    if 0 <= off < len(r_data):
                        end = r_data.find(b"\x00", off)
                        s = r_data[off:end].decode('latin1')
                        extra += f" ; [{s}]"
                except:
                    pass
        if "call" in insn.mnemonic or extra != "":
            print(f"0x{insn.address:x}: {insn.mnemonic}\t{insn.op_str}{extra}")
