"""Compatibility for the stock GD13MY .061 MUSB host driver."""

from unicorn import UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_PC

from gd13my_arm import RM, instruction


DMA_RX_MORE = 0xc08c9c38
DMA_RX_DONE = 0xc08c9c48
DMA_RX_BRANCH = (0xe1530002, 0x2a000002, 0xe3510000)


def finish_short_bulk_in(cpu, address, _size, musb):
    # The stock mode-zero completion path requests another IN token whenever the
    # buffer is still short. In bulk IN, a short packet terminates the transfer.
    if not musb.connected or cpu.reg_read(RM[10]) != 10:
        return
    endpoint = musb.endpoints[cpu.reg_read(RM[5]) & 15]
    received = cpu.reg_read(RM[1])
    if (not received or endpoint.short_dma_count != received or
            (endpoint.read(12, 1) >> 4) & 3 != 2 or
            cpu.reg_read(RM[3]) >= cpu.reg_read(RM[2])):
        return
    if tuple(instruction(cpu, address + offset) for offset in (-4, 0, 4)) != DMA_RX_BRANCH:
        return
    endpoint.short_dma_count = 0
    cpu.reg_write(UC_ARM_REG_PC, DMA_RX_DONE)


def install_short_bulk_in(cpu, musb):
    cpu.hook_add(UC_HOOK_CODE, finish_short_bulk_in, musb, begin=DMA_RX_MORE, end=DMA_RX_MORE)
