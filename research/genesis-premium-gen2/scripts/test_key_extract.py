import struct

def extract_key_from_header(path):
    with open(path, "rb") as f:
        data_128k = f.read(0x20000)
    
    if len(data_128k) < 0x20000:
        print("File too short")
        return

    # Section 1: N and E extraction?
    # Let's inspect LGUGetKeyData logic:
    # 0x804aa3a: ecx = dword ptr [eax] (offset 0)
    # edx = 0x88888889
    # imul edx -> division by 0x78
    # ecx = ecx % 0x78
    # stride = ecx + 4
    # loop 0x200 times:
    #   cl = byte ptr [edx + 8]
    #   edx += stride
    #   buf[i] = cl
    val0 = struct.unpack("<I", data_128k[0:4])[0]
    rem0 = val0 % 0x78
    stride0 = rem0 + 4
    print(f"val0=0x{val0:x}, rem0={rem0}, stride0={stride0}")
    
    extracted1 = bytearray()
    curr = rem0
    for i in range(0x206): # 0x200 for N, 6 for E?
        if curr + 8 >= 0x10000:
            print(f"Index out of range in sec 1 at i={i}, curr={curr}")
            break
        extracted1.append(data_128k[curr + 8])
        curr += stride0
    
    print(f"extracted1 len={len(extracted1)}")
    
    # Section 2: at offset 0x10000
    val1 = struct.unpack("<I", data_128k[0x10000:0x10004])[0]
    rem1 = val1 % 0x73
    stride1 = rem1 + 4
    print(f"val1=0x{val1:x}, rem1={rem1}, stride1={stride1}")
    
    extracted2 = bytearray()
    curr1 = rem1
    for i in range(0x206):
        if 0x10000 + curr1 + 8 >= 0x20000:
            print(f"Index out of range in sec 2 at i={i}, curr={curr1}")
            break
        extracted2.append(data_128k[0x10000 + curr1 + 8])
        curr1 += stride1
    print(f"extracted2 len={len(extracted2)}")
    
    return extracted1, extracted2

print("=== update.tar ===")
extract_key_from_header(r"F:\i30-gen2-android-auto\research\genesis-premium-gen2\extracted\essentials\update.tar")
