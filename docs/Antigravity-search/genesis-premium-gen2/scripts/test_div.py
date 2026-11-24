import ctypes

def calc_rem0(ecx):
    ecx = ctypes.c_int32(ecx).value
    # imul edx where edx = 0x88888889 (as signed: -2004318071)
    edx_const = ctypes.c_int32(0x88888889).value
    prod = ecx * edx_const
    edx = prod >> 32 # top 32 bits
    eax = ecx >> 31  # sar eax, 0x1f
    edx = (edx + ecx) & 0xffffffff
    edx = ctypes.c_int32(edx).value >> 6
    edx = edx - eax
    edx = edx * 0x78
    rem = ecx - edx
    return rem

def calc_rem1(ecx):
    ecx = ctypes.c_int32(ecx).value
    edx_const = ctypes.c_int32(0x473c1ab7).value
    prod = ecx * edx_const
    edx = prod >> 32
    eax = ecx >> 31
    edx = (edx) & 0xffffffff
    edx = ctypes.c_int32(edx).value >> 5
    edx = edx - eax
    edx = edx * 0x73
    rem = ecx - edx
    return rem

with open(r"F:\i30-gen2-android-auto\research\genesis-premium-gen2\extracted\essentials\update.tar", "rb") as f:
    data = f.read(0x20000)

import struct
val0 = struct.unpack("<i", data[0:4])[0]
val1 = struct.unpack("<i", data[0x10000:0x10004])[0]

r0 = calc_rem0(val0)
r1 = calc_rem1(val1)
print(f"val0=0x{val0 & 0xffffffff:x}, r0={r0}, python % 120 = {(val0 & 0xffffffff) % 120}, signed % 120 = {val0 % 120}")
print(f"val1=0x{val1 & 0xffffffff:x}, r1={r1}, python % 115 = {(val1 & 0xffffffff) % 115}, signed % 115 = {val1 % 115}")
