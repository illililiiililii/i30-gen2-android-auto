import ctypes as C
import os
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


def native_clock_library():
    configured = os.environ.get('GD13MY_CLOCK_DLL')
    if configured == 'off':
        return None
    path = (Path(configured) if configured else ROOT / 'build' / 'gd13my-block-clock.dll')
    if not path.is_file():
        return None
    library = C.CDLL(str(path.resolve()))
    if not hasattr(library, 'gd13my_gptimer_read'):
        return None
    return library


@unittest.skipUnless(native_clock_library(), 'Requires a native block-clock DLL with GPTimer read support')
class NativeGpTimerTests(unittest.TestCase):
    def test_counter_matches_python_bank_at_multiple_guest_times(self):
        from gd13my_block_clock import BlockClock, GpTimerRead
        from gd13my_mmio import GpTimer

        library = native_clock_library()
        read_native = library.gd13my_gptimer_read
        read_native.restype = C.c_uint64
        read_native.argtypes = (C.c_void_p, C.c_uint64, C.c_uint, C.c_void_p)

        rate = 4_500_000
        hz = 32_768
        clock = BlockClock.__new__(BlockClock)
        clock.units = 0
        ticks = lambda: clock.units * hz // rate
        timer = GpTimer(ticks)
        timer.write(0x28, 4, 0x12340000)
        timer.write(0x24, 4, 1)
        state = GpTimerRead(clock, timer, rate, hz)

        for units in (0, 1, 27, 450, 4_500, 100_000, 900_000, 4_500_000):
            with self.subTest(units=units):
                clock.units = units
                for width in (1, 2, 4):
                    actual = read_native(None, 0x28, width, C.byref(state))
                    expected = timer.counter() & ((1 << (8 * width)) - 1)
                    self.assertEqual(actual, expected)

        timer.write(0x10, 4, 2)
        state.sync(timer, rate, hz)
        self.assertEqual(read_native(None, 0x28, 4, C.byref(state)), timer.counter())


if __name__ == '__main__':
    unittest.main()
