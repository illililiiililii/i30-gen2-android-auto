import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
ROM = ROOT / 'firmware/extracted/GD13MY/BSP/0002dfc7_kernel'
sys.path.insert(0, str(ROOT / 'tools'))
HAS_UNICORN = importlib.util.find_spec('unicorn') is not None


@unittest.skipUnless(HAS_UNICORN and ROM.is_file(), 'Requires Unicorn and the extracted GD13MY kernel')
class Gd13myBootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from emulate_gd13my import KernelRun

        image = ROM.read_bytes()
        cls.evm = KernelRun(image, 'evm', 'uart').run()
        cls.native = KernelRun(image, 'gd13my', 'boot', guest_exceptions=True, empty_mmc=True,
                               virtual_timer=True, boot_trace=True).run(instructions=20_000_000, seconds=15)

    def test_oem_table_and_evm_control_isolate_the_high_ram_failure(self):
        self.assertEqual(self.native['oem_table_va'], '0x8400ab7c')
        self.assertEqual(len(self.native['oem_windows']), 13)
        self.assertEqual(self.native['oem_windows'][0],
                         {'virtual': '0x84000000', 'physical': '0x80000000', 'size_mib': 256})
        self.assertEqual(self.evm['fault']['pc'], '0x8400b0b0')
        self.assertEqual(self.evm['fault']['address'], '0x8ff00000')
        self.assertFalse(self.evm['high_ram_1mib_zeroed_at_return'])
        self.assertTrue(self.native['high_ram_1mib_zeroed_at_return'])
        descriptors = {row['virtual']: row for row in self.native['page_table_samples']}
        self.assertEqual(descriptors['0x93f00000']['descriptor'], '0x8ff0040e')
        self.assertEqual(descriptors['0xb3f00000']['descriptor'], '0x8ff00402')
        self.assertIn('OEMGetExtensionDRAM: returning 0x0b400000 bytes of ram at 0x88800000', self.native['serial'])

    def test_stock_exception_handlers_map_pages_and_reach_filesys(self):
        events = self.native['exceptions']
        first_abort = next(event for event in events if event.get('address') == '0xc0042000')
        self.assertEqual(first_abort['delivered_vector'], '0xffff0010')
        self.assertIsNone(first_abort['before']['physical'])
        self.assertIsNotNone(first_abort['translation_at_stop']['physical'])

        filesys_write = next(event for event in events if event.get('address') == '0xd00f00e8')
        self.assertEqual(filesys_write['rom_module']['name'], 'filesys.dll')
        self.assertEqual(filesys_write['fault_status'], '0x0000000f')
        self.assertNotEqual(filesys_write['before']['l2'], filesys_write['translation_at_stop']['l2'])

        prefetch = next(event for event in events if event.get('address') == '0xf100add0')
        self.assertEqual(prefetch['delivered_vector'], '0xffff000c')
        self.assertEqual(prefetch['fault_status'], '0x000000f9')
        self.assertIsNone(self.native['fault'])

    def test_virtual_timer_reaches_power_manager(self):
        names = {event.get('rom_module', {}).get('name') for event in self.native['exceptions']}
        self.assertIn('pm.dll', names)
        self.assertGreater(self.native['mmio_devices']['HSMMC1']['writes'], 0)

    def test_missing_public_rom_read_delivers_synchronous_data_abort(self):
        from collections import Counter
        from unicorn import UC_MEM_READ_UNMAPPED
        from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R1
        from emulate_gd13my import KernelRun
        from gd13my_arm import Translation, cp15

        run = KernelRun(ROM.read_bytes(), 'gd13my', 'boot', guest_exceptions=True)
        pc, address, physical = 0xc08e4e04, 0xd50900bc, 0x400140bc
        run.cpu.reg_write(UC_ARM_REG_CPSR, 0x13)
        run.cpu.reg_write(UC_ARM_REG_PC, pc)
        run.cpu.reg_write(UC_ARM_REG_R1, address)
        run.cpu.cpr_write(15, 0, 1, 0, 0, 0, False, cp15(run.cpu, 1) | (1 << 13))
        run.fault = {'address': hex(physical), 'access': UC_MEM_READ_UNMAPPED}
        with (patch('emulate_gd13my.instruction', return_value=0xe5910000),  # ldr r0, [r1]
              patch('emulate_gd13my.translate', return_value=Translation(physical, 0))):
            self.assertEqual(run.unavailable_public_rom(Counter()), 0xffff0010)

        self.assertIsNone(run.fault)
        self.assertEqual(run.cpu.reg_read(UC_ARM_REG_LR), pc + 8)
        self.assertEqual(cp15(run.cpu, 5), 8)
        self.assertEqual(cp15(run.cpu, 6), address)
        self.assertEqual(run.guest_exceptions.events[-1]['physical'], hex(physical))

    def test_boot_trace_verifies_device_manager_entry(self):
        trace = self.native['boot_trace']
        entry = trace['milestones']['device.dll!DevMainEntry']
        self.assertEqual((entry['pc'], entry['physical']), ('0xc0251060', '0x80286060'))
        self.assertEqual(trace['milestones']['devmgr.dll!StartDeviceManager']['pc'], '0xc0262334')
        self.assertTrue(any(event.get('path') == 'device.dll' and event['symbol'] == 'LoadLibraryW'
                            for event in trace['recent_calls']))

    def test_prefetch_guard_distinguishes_consecutive_ce_api_arguments(self):
        from unicorn import UC_ARCH_ARM, UC_MODE_ARM, Uc
        from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R1
        from gd13my_arm import GuestExceptions, PREFETCH_ABORT, Translation

        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.reg_write(UC_ARM_REG_CPSR, 0x10)
        cpu.reg_write(UC_ARM_REG_PC, 0xf100afac)
        cpu.reg_write(UC_ARM_REG_LR, 0x4002e840)
        tracker = GuestExceptions(cpu, deliver=True)
        with (patch('gd13my_arm.instruction', return_value=None),
              patch('gd13my_arm.translate', return_value=Translation(0xafac, 0x1f2)),
              patch('gd13my_arm.abort_status', return_value=0xf9),
              patch('gd13my_arm.exception_entry', return_value=0xffff000c)):
            for index in range(6):
                cpu.reg_write(UC_ARM_REG_R1, index)
                tracker.interrupt(cpu, PREFETCH_ABORT, None)
                self.assertFalse(tracker.stopped)
            for _ in range(6):
                tracker.observe_prefetch_return(cpu, 0x4002e840)
                tracker.interrupt(cpu, PREFETCH_ABORT, None)
                self.assertFalse(tracker.stopped)
            for _ in range(4):
                tracker.interrupt(cpu, PREFETCH_ABORT, None)

        self.assertTrue(tracker.stopped)
        self.assertEqual(tracker.events[5]['arguments'][1], '0x00000005')
        self.assertEqual(tracker.events[-1]['delivery_stopped'], 'repeated_abort')

    def test_disabled_vfp_instruction_uses_guest_undefined_vector(self):
        from unicorn import UC_ARCH_ARM, UC_MODE_ARM, Uc
        from unicorn.arm_const import (UC_ARM_REG_CPSR, UC_ARM_REG_FPEXC, UC_ARM_REG_LR, UC_ARM_REG_PC,
                                       UC_ARM_REG_SP, UC_CPU_ARM_CORTEX_A8)
        from gd13my_arm import GuestExceptions

        cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
        cpu.reg_write(UC_ARM_REG_CPSR, 0x1f)
        cpu.reg_write(UC_ARM_REG_FPEXC, 0)
        cpu.reg_write(UC_ARM_REG_PC, 0xc0996344)
        cpu.reg_write(UC_ARM_REG_SP, 0xd049fafc)
        cpu.reg_write(UC_ARM_REG_LR, 0xc019cb64)
        tracker = GuestExceptions(cpu, deliver=True)
        with patch('gd13my_arm.instruction', return_value=0xee000a10):
            self.assertTrue(tracker.invalid_instruction(cpu, None))

        event = tracker.events[-1]
        self.assertEqual(event['kind'], 'vfp_access_trap')
        self.assertEqual(cpu.reg_read(UC_ARM_REG_PC), int(event['delivered_vector'], 16))

        cpu.reg_write(UC_ARM_REG_CPSR, 0x1f)
        tracker.observe_vfp_retry(cpu, 0xc0996344, 4)
        self.assertIn(0xc0996344, tracker.vfp_retries)
        tracker.observe_vfp_retry(cpu, 0xc0996348, 8)
        self.assertFalse(tracker.vfp_retries)
        self.assertFalse(tracker.repeats)

        cpu.reg_write(UC_ARM_REG_PC, 0xc0996344)
        with patch('gd13my_arm.instruction', return_value=0xee000a10):
            self.assertTrue(tracker.invalid_instruction(cpu, None))
        cpu.reg_write(UC_ARM_REG_CPSR, 0x1f)
        cpu.reg_write(UC_ARM_REG_FPEXC, 1 << 30)
        tracker.observe_vfp_retry(cpu, 0xc0996344, 4)
        self.assertTrue(tracker.repeats)
        tracker.observe_vfp_retry(cpu, 0xc0996344, 12)
        self.assertFalse(tracker.vfp_retries)
        self.assertFalse(tracker.repeats)
