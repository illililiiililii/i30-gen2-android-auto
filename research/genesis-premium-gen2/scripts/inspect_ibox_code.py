import capstone
from elftools.elf.elffile import ELFFile
import struct

binary_path = r"G:\AppUpgrade"

with open(binary_path, "rb") as f:
    elf = ELFFile(f)
    text_sec = elf.get_section_by_name(".text")
    text_addr = text_sec["sh_addr"]
    text_data = text_sec.data()
    
    rodata_sec = elf.get_section_by_name(".rodata")
    rodata_addr = rodata_sec["sh_addr"]
    rodata_data = rodata_sec.data()
    
    # Search for string
    target_str = b"decryptIboxFiles() Start!"
    idx = rodata_data.find(target_str)
    if idx != -1:
        str_va = rodata_addr + idx
        print(f"Found string '{target_str.decode()}' at VA 0x{str_va:x}")
        
        # Search for references to str_va in .text
        packed = struct.pack("<I", str_va)
        md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        
        ref_offsets = []
        pos = 0
        while True:
            p = text_data.find(packed, pos)
            if p == -1:
                break
            ref_offsets.append(p)
            pos = p + 1
            
        print(f"Found {len(ref_offsets)} direct references in .text")
        for off in ref_offsets:
            insn_va = text_addr + off
            print(f"=== Reference at 0x{insn_va:x} ===")
            start_off = max(0, off - 32)
            end_off = min(len(text_data), off + 128)
            code = text_data[start_off:end_off]
            for insn in md.disasm(code, text_addr + start_off):
                print(f"0x{insn.address:x}: {insn.mnemonic}\t{insn.op_str}")
