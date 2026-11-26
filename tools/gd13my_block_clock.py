"""Count Unicorn blocks in C while the WinCE scheduler remains in Python."""

from ctypes import CDLL, CFUNCTYPE, Structure, byref, c_size_t, c_uint, c_uint32, c_uint64, c_void_p
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


def install_block_clock(cpu, service):
    configured = environ.get('GD13MY_CLOCK_DLL')
    if configured == 'off':
        return None
    library = (Path(configured) if configured else
               Path(__file__).resolve().parents[1] / 'build' / 'gd13my-block-clock.dll')
    if not configured and not library.is_file():
        return None
    return BlockClock(cpu, service, library.resolve())
