from elftools.elf.elffile import ELFFile
import capstone
import struct

binary_path = r"G:\AppUpgrade"

with open(binary_path, "rb") as f:
    elf = ELFFile(f)
    rodata = elf.get_section_by_name(".rodata")
    r_addr = rodata['sh_addr']
    r_data = rodata.data()
    
    text_sec = elf.get_section_by_name(".text")
    t_addr = text_sec['sh_addr']
    t_data = text_sec.data()

    md = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)

    targets = [b"DecryptToFile", b"DecryptToPIPE", b"ibox_decrypt", b"IBOX.tar", b"IBOX file count"]
    for t in targets:
        pos = 0
        while True:
            idx = r_data.find(t, pos)
            if idx == -1:
                break
            str_va = r_addr + idx
            print(f"Target '{t.decode()}' at VA 0x{str_va:x}")
            pos = idx + 1
            
            # Find in text
            packed = struct.pack("<I", str_va)
            t_pos = 0
            while True:
                p = t_data.find(packed, t_pos)
                if p == -1:
                    break
                ref_va = t_addr + p
                print(f"  Referenced at 0x{ref_va:x}")
                t_pos = p + 1
                
                # disassemble around ref
                start = max(0, p - 20)
                end = min(len(t_data), p + 60)
                for insn in md.disasm(t_data[start:end], t_addr + start):
                    print(f"    0x{insn.address:x}: {insn.mnemonic}\t{insn.op_str}")
