from elftools.elf.elffile import ELFFile
import struct

binary_path = r"F:\i30-gen2-android-auto\research\genesis-premium-gen2\extracted\essentials\decrypt\DecryptToFile"

with open(binary_path, "rb") as f:
    elf = ELFFile(f)
    got = elf.get_section_by_name(".got.plt") or elf.get_section_by_name(".got")
    # In LGUGetKeyData, ebx = 0x80497bf + 0x24622 = 0x806dde1
    ebx = 0x80497bf + 0x24622
    target_addr = ebx - 0x44
    print(f"ebx = 0x{ebx:x}, target_addr = 0x{target_addr:x}")
    
    # Read rodata or data at target_addr
    for sec in elf.iter_sections():
        saddr = sec['sh_addr']
        ssize = sec['sh_size']
        if saddr <= target_addr < saddr + ssize:
            offset = target_addr - saddr
            val = struct.unpack("<I", sec.data()[offset:offset+4])[0]
            print(f"Value at 0x{target_addr:x} in {sec.name}: 0x{val:x} ({val})")
