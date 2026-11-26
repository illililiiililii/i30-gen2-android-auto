"""Count Unicorn blocks in C while the WinCE scheduler remains in Python."""

from ctypes import (CDLL, CFUNCTYPE, Structure, byref, c_size_t,
                    c_uint, c_uint8, c_uint32, c_uint64, c_void_p, cast)
from os import environ
from pathlib import Path

from unicorn import UC_HOOK_BLOCK, UcError
from unicorn.unicorn_py3.unicorn import MMIO_READ_CFUNC
NO_DEADLINE = (1 << 64) - 1
BLOCK_HOOK = CFUNCTYPE(None, c_void_p, c_uint64, c_uint32, c_void_p)


class MmcFifo(Structure):
    _fields_ = [('payload', c_void_p), ('length', c_uint64), ('position', c_uint64),
                ('words_read', c_uint64), ('read', MMIO_READ_CFUNC)]


class BlockClock(Structure):
    _fields_ = [('units', c_uint64), ('service_at', c_uint64), ('prefetch_pc', c_uint64),
                ('watch_vfp', c_uint64), ('service', BLOCK_HOOK)]


    def __init__(self, cpu, service, library):
        from unicorn.unicorn_py3.unicorn import uccallback, uclib

        # Unicorn's Python hook wrapper would reacquire the GIL for every block.
        # Register the C callback with the same engine through the public C API.
        self.library = CDLL(str(library))
        self.library.gd13my_clock_abi.restype = c_uint
        if self.library.gd13my_clock_abi() != 1:
            raise ValueError(f'Unsupported GD13MY clock ABI in {library}')
        self.callback = uccallback(cpu, BLOCK_HOOK)(service)
        super().__init__(0, 0, NO_DEADLINE, 0, self.callback)
        handle = c_size_t()
        status = uclib.uc_hook_add(cpu._uch, byref(handle), UC_HOOK_BLOCK,
                                  self.library.gd13my_clock_block, byref(self),
                                  c_uint64(1), c_uint64(0))
        if status:
            raise UcError(status)
        cpu._callbacks[handle.value] = self

    def map_mmc(self, cpu, base, size, read, write, target):
        from unicorn.unicorn_py3.unicorn import MMIO_WRITE_CFUNC, uccallback, uclib

        if not hasattr(self.library, 'gd13my_mmc_read'):
            return None
        fifo = MmcFifo()

        @uccallback(cpu, MMIO_READ_CFUNC)
        def read_cb(engine, offset, width, _):
            return read(engine, offset, width, target)

        @uccallback(cpu, MMIO_WRITE_CFUNC)
        def write_cb(engine, offset, width, value, _):
            write(engine, offset, width, value, target)

        fifo.read = read_cb
        status = uclib.uc_mmio_map(cpu._uch, base, size, self.library.gd13my_mmc_read, byref(fifo), write_cb, None)
        if status:
            raise UcError(status)
        cpu._mmio_callbacks[base, base + size] = (read_cb, write_cb)
        return fifo

    def map_gptimer(self, cpu, base, size, write, target, timer, units_per_second,
                    ticks_per_second):
        from unicorn.unicorn_py3.unicorn import MMIO_WRITE_CFUNC, uccallback, uclib

        if not hasattr(self.library, 'gd13my_gptimer_read'):
            return None
        state = GpTimerRead(self, timer, units_per_second, ticks_per_second)
        read_cb = self.library.gd13my_gptimer_read
        read_cb.restype = c_uint64
        read_cb.argtypes = (c_void_p, c_uint64, c_uint, c_void_p)

        @uccallback(cpu, MMIO_WRITE_CFUNC)
        def write_cb(engine, offset, width, value, _):
            write(engine, offset, width, value, target)

        status = uclib.uc_mmio_map(cpu._uch, base, size, read_cb, byref(state), write_cb, None)
        if status:
            raise UcError(status)
        cpu._mmio_callbacks[base, base + size] = (state, state.data_buffer, write_cb)
        return state


class GpTimerRead(Structure):
    _fields_ = [('data', c_void_p), ('clock_units', c_void_p), ('epoch', c_uint64),
                ('units_per_second', c_uint64), ('reads', c_uint64),
                ('ticks_per_second', c_uint32), ('running', c_uint32)]

    def __init__(self, clock, timer, units_per_second, ticks_per_second):
        self.data_buffer = (c_uint8 * len(timer.data)).from_buffer(timer.data)
        super().__init__(cast(self.data_buffer, c_void_p),
                         cast(byref(clock, BlockClock.units.offset), c_void_p),
                         0, 0, 0, 0, 0)
        self.sync(timer, units_per_second, ticks_per_second)

    def sync(self, timer, units_per_second, ticks_per_second):
        self.epoch = timer.epoch or 0
        self.units_per_second = units_per_second
        self.ticks_per_second = ticks_per_second
        self.running = int(timer.epoch is not None)


def install_block_clock(cpu, service):
    configured = environ.get('GD13MY_CLOCK_DLL')
    if configured == 'off':
        return None
    library = (Path(configured) if configured else
               Path(__file__).resolve().parents[1] / 'build' / 'gd13my-block-clock.dll')
    if not configured and not library.is_file():
        return None
    return BlockClock(cpu, service, library.resolve())
