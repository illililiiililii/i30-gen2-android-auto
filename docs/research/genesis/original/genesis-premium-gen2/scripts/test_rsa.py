import struct

def test_rsa_decrypt(path):
    with open(path, "rb") as f:
        data_128k = f.read(0x20000)

    # Loop 1: extracted to buf1 (0x200 bytes)
    val0 = struct.unpack("<I", data_128k[0:4])[0]
    rem0 = val0 % 0x78
    stride0 = rem0 + 4
    buf1 = bytearray()
    curr0 = rem0
    for i in range(0x200):
        buf1.append(data_128k[curr0 + 8])
        curr0 += stride0

    # Loop 2: extracted to buf2 (0x206 bytes)
    val1 = struct.unpack("<I", data_128k[0x10000:0x10004])[0]
    rem1 = val1 % 0x73
    stride1 = rem1 + 4
    buf2 = bytearray()
    curr1 = rem1
    for i in range(0x206):
        buf2.append(data_128k[0x10000 + curr1 + 8])
        curr1 += stride1

    # buf2[:0x200] is N
    N = int.from_bytes(buf2[:0x200], byteorder="big")
    E = int.from_bytes(buf2[0x200:0x206], byteorder="big")
    C = int.from_bytes(buf1[:0x200], byteorder="big")

    print(f"N bit length: {N.bit_length()}")
    print(f"E: {E} (0x{E:x})")

    # M = C^E mod N
    M = pow(C, E, N)
    m_bytes = M.to_bytes(0x200, byteorder="big")
    print("M bytes (first 32):", m_bytes[:32].hex())
    print("M bytes (last 32):", m_bytes[-32:].hex())

    # PKCS#1 v1.5 decryption:
    # 00 01 FF FF ... FF 00 [Key] (for sign/public decrypt) or 00 02 [random] 00 [Key]
    if m_bytes[0] == 0 and m_bytes[1] in (1, 2):
        idx = m_bytes.find(b"\x00", 2)
        if idx != -1:
            key = m_bytes[idx+1:]
            print(f"Successfully recovered key ({len(key)} bytes): {key.hex()} (ASCII: {key})")
            return key
    else:
        print("M bytes didn't start with 00 01/02, let's inspect:", m_bytes[:16].hex())

print("Testing on update.tar:")
test_rsa_decrypt(r"F:\i30-gen2-android-auto\research\genesis-premium-gen2\extracted\essentials\update.tar")
