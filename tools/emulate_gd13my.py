"""Boot the original GD13MY CE BIN in a bounded, headless Cortex-A8 model."""

import argparse
from collections import Counter, deque
from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import struct
from time import monotonic

from unicorn import (UC_ARCH_ARM, UC_HOOK_BLOCK, UC_HOOK_CODE, UC_HOOK_MEM_INVALID, UC_MEM_READ_UNMAPPED, UC_MODE_ARM, UC_PROT_EXEC,
                     UC_PROT_READ, UC_QUERY_TIMEOUT, Uc, UcError)
from unicorn.arm_const import (UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R10, UC_CPU_ARM_CORTEX_A8)

from gd13my_arm import GuestExceptions, cp15, data_access, exception_entry, hx, instruction, translate, word
from gd13my_display import BASE as DSS_BASE, LcdDisplay
from gd13my_mmio import MMC_BASES, UART3_BASE, DebugUart, OmapSdMa, ReadOnlyHsMmc, boot_devices
from gd13my_trace import BootTrace
from inspect_ce import index_bin, inspect_rom, module_headers
from inspect_firmware import ROOT

MIB = 1024 * 1024
ROM_PATH = ROOT / 'firmware/extracted/GD13MY/BSP/0002dfc7_kernel'
OMAP_PUBLIC_ROM_BASE, OMAP_PUBLIC_ROM_SIZE = 0x40014000, 32 * 1024
SRAM = (0x40208000, 0x8000)
IVA2_RAM = ((0x5c7f8000, 0x18000), (0x5ce00000, 0x8000), (0x5cf04000, 0x14000))
HIGH_RAM_CLEAR = (0x8ff00000, MIB)
OAL_WFI = 0x8401878c
EVM_RAM = ((0x80000000, 128 * MIB), (0xa0000000, 128 * MIB))
VIRTUAL_CPU_UNITS_PER_SECOND = 64_000_000
TIMER_HZ = 32_768
UI_MODULES = {'AVNSysInit.exe', 'gwes.dll', 'ddi.dll', 'AutoStartUp.exe', 'Touch_Calib.exe'}
MAX_INSTRUCTIONS = 2_000_000_000
MAX_SECONDS = 300


@dataclass(frozen=True)
class AddressWindow:
    virtual: int
    physical: int
    megabytes: int

    @property
    def size(self):
        return self.megabytes * MIB

    def report(self):
        return {'virtual': hx(self.virtual), 'physical': hx(self.physical), 'size_mib': self.megabytes}


def oem_addresses(rom, read):
    # GD13MY's entry passes a PC-relative pointer to the page table initialization routine.
    entry = int(rom['entry'], 16) + int(rom['address_alias_delta'], 16)
    instruction = entry + 0x94
    if struct.unpack('<II', read(instruction, 8)[0]) != (0xe28f0004, 0xeb000059):
        raise ValueError('Unsupported GD13MY startup code at the address-table reference')
    address = instruction + 8 + 4
    windows = []
    for index in range(32):
        virtual, physical, size = struct.unpack('<III', read(address + index * 12, 12)[0])
        if (virtual, physical, size) == (0, 0, 0):
            if not windows:
                raise ValueError('The OEM address table is empty')
            return address, windows
        if not 0 < size <= 512 or virtual % MIB or physical % MIB:
            raise ValueError('Unsupported OEM address table row')
        windows.append(AddressWindow(virtual, physical, size))
    raise ValueError('Missing OEM address table terminator')


def executable_sections(rom, read):
    """Index uncompressed executable sections at their physical BIN addresses."""
    alias = int(rom['address_alias_delta'], 16)
    ranges = []
    ui_entrypoints = {}
    for row in rom['contents']:
        if row['kind'] != 'module':
            continue
        try:
            e32, _, sections = module_headers(row, read)
        except ValueError:
            continue  # Unknown module metadata does not prevent loading the kernel.
        name = row['name']
        entry = struct.unpack_from('<I', e32, 4)[0] & ~1
        for size, rva, stored, va, runtime, flags, _ in sections:
            if va and stored and flags & 0x20000000 and not flags & 0x2000:
                length = min(size, stored)
                ranges.append((va - alias, length, name, rva))
                if name in UI_MODULES and rva <= entry < rva + length:
                    offset = entry - rva
                    ui_entrypoints[name] = (runtime + offset, va - alias + offset)
    return ranges, ui_entrypoints


class KernelRun:
    def __init__(self, image, layout, periphery, *, guest_exceptions=False, empty_mmc=False, virtual_timer=False,
                 card=None, slot=1, display=False, timer_irq=False, boot_trace=False, touch=None,
                 omap_public_rom=None, musb=None):
        self.image = image
        self.rom, read = inspect_rom(image, include_reader=True)
        self.table, self.windows = oem_addresses(self.rom, read)
        self.sections, ui_entrypoints = executable_sections(self.rom, read)
        _, _, self.entry, segments = index_bin(image)
        self.cpu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.cpu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A8)
        self.cpu.reg_write(UC_ARM_REG_CPSR, 0xd3)
        self.omap_public_rom_sha256 = None
        if omap_public_rom is not None:
            if len(omap_public_rom) != OMAP_PUBLIC_ROM_SIZE:
                raise ValueError('The OMAP35x public ROM must be exactly 32 KiB')
            self.cpu.mem_map(OMAP_PUBLIC_ROM_BASE, OMAP_PUBLIC_ROM_SIZE, UC_PROT_READ | UC_PROT_EXEC)
            self.cpu.mem_write(OMAP_PUBLIC_ROM_BASE, omap_public_rom)
            self.omap_public_rom_sha256 = sha256(omap_public_rom).hexdigest()
        self.layout, self.periphery = layout, periphery
        self.virtual_timer = virtual_timer
        self.clock_units = 0
        self.irq_controller = None
        self.irq_counts = Counter()
        self.irq_poll_at = 0
        self.idle_wakes = 0
        self.idle_blocked = False
        if virtual_timer or guest_exceptions:
            self.cpu.hook_add(UC_HOOK_BLOCK, self.advance_clock)
        main = next((w for w in self.windows if w.physical <= self.entry < w.physical + w.size), None)
        if main is None:
            raise ValueError('The OEM table has no window for the kernel entry')
        self.ram = EVM_RAM if layout == 'evm' else ((main.physical, main.size),)
        for start, size in self.ram:
            self.cpu.mem_map(start, size)
        if periphery == 'boot':
            for start, size in (SRAM, *IVA2_RAM):
                self.cpu.mem_map(start, size)
        for address, (offset, size) in segments.items():
            if not self.contains_ram(address, size):
                raise ValueError(f'BIN record at {hx(address)} is outside the selected RAM')
            self.cpu.mem_write(address, image[offset:offset + size])

        self.seeded = self.contains_ram(*HIGH_RAM_CLEAR)
        if self.seeded:
            start, size = HIGH_RAM_CLEAR
            if any(start < origin + span and origin < start + size for origin, (_, span) in segments.items()):
                raise ValueError('Refusing to seed RAM over a BIN record')
            self.cpu.mem_write(start, b'\xa5' * size)

        self.uart = DebugUart(trace_limit=4 * MIB)
        self.card, self.slot = card, slot
        self.dma = None
        self.display = LcdDisplay() if display else None
        timer_clock = self.clock_ticks if virtual_timer else None
        if periphery == 'boot':
            memory = (self.contains_ram, self.cpu.mem_read, self.cpu.mem_write)
            if card is not None:
                self.dma = OmapSdMa(card, MMC_BASES[slot - 1] + 0x120, memory)
            if musb is not None:
                musb.dma_memory = memory
            devices = boot_devices(self.uart, empty_mmc=empty_mmc, timer_clock=timer_clock, card=card, slot=slot,
                                   timer_irq=timer_irq, touch=touch, dma=self.dma, musb=musb)
            if timer_irq:
                self.irq_controller = devices[0x48200000][1]
                self.power = devices[0x48306000][1]
                alias = int(self.rom['address_alias_delta'], 16)
                if read(OAL_WFI, 4)[0] == b'\x03\xf0\x20\xe3':
                    for address in (OAL_WFI, OAL_WFI + 0x20000000):
                        self.cpu.hook_add(UC_HOOK_CODE, self.wake_from_idle, OAL_WFI - alias,
                                          begin=address, end=address)
            devices[DSS_BASE] = ('DSS/DISPC', self.display or LcdDisplay())
        else:
            devices = {UART3_BASE: ('UART3', self.uart)}
        self.devices = {name: {'physical': hx(base), 'reads': 0, 'writes': 0} for base, (name, _) in devices.items()}
        for base, (name, bank) in devices.items():
            target = (base, name, bank)
            self.cpu.mmio_map(base, len(bank.data), self.read_mmio, target, self.write_mmio, target)

        self.events = {}
        self.ui_entries = dict.fromkeys(sorted(UI_MODULES))
        self.last_io = deque(maxlen=16)
        self.read_counts = Counter()
        self.fault = None
        self.ttbr0 = None
        self.high_ram_zeroed = False
        targets = {'bin_entry': self.entry, 'oem_table_reference': self.table - 12 - int(self.rom['address_alias_delta'], 16),
                   'set_ttbr0': 0x8000ae24, 'kernel_virtual_entry': 0x8400ae60,
                   'clear_high_ram_call': 0x84017eec, 'clear_high_ram_return': 0x84017ef0}
        for name, address in targets.items():
            self.cpu.hook_add(UC_HOOK_CODE, self.checkpoint, name, begin=address, end=address)
        for name, (address, expected_pa) in ui_entrypoints.items():
            self.cpu.hook_add(UC_HOOK_CODE, self.ui_entry, (name, expected_pa), begin=address, end=address)
        self.cpu.hook_add(UC_HOOK_MEM_INVALID, self.invalid_memory)
        self.guest_exceptions = GuestExceptions(self.cpu, guest_exceptions)
        self.boot_trace = BootTrace(self.cpu, self.rom, read, self.clock_ticks, self.contains_ram) if boot_trace else None

    def contains_ram(self, address, length):
        return any(start <= address and address + length <= start + size for start, size in self.ram)

    def advance_clock(self, cpu, address, size, _data):
        expected = self.guest_exceptions.prefetch_return
        if expected is not None and address == expected[0]:
            self.guest_exceptions.observe_prefetch_return(cpu, address)
        retries = self.guest_exceptions.vfp_retries
        if address in retries or address - 4 in retries:
            self.guest_exceptions.observe_vfp_retry(cpu, address, size)
        if not self.virtual_timer:
            return
        self.clock_units += size // 4
        intc = self.irq_controller
        if intc is None or self.clock_units < self.irq_poll_at:
            return
        self.irq_poll_at = self.clock_units + 1024
        cpsr = cpu.reg_read(UC_ARM_REG_CPSR)
        pending = intc.pending() if not cpsr & 0x80 and intc.active is None else []
        if pending:
            intc.active = pending[0]
            self.irq_counts[intc.active] += 1
            exception_entry(cpu, cpsr, address, vector_offset=0x18, mode=0x12, return_offset=4, mask_async=True)

    def clock_ticks(self):
        return self.clock_units * TIMER_HZ // VIRTUAL_CPU_UNITS_PER_SECOND

    def wake_from_idle(self, cpu, address, _size, physical):
        mapping = translate(cpu, address)
        if mapping is None or mapping.physical != physical:
            return
        intc = self.irq_controller
        if not intc.pending():
            timer = intc.sources[37]
            distance = timer.ticks_to_match()
            if distance is None or not intc.routes_irq(37):
                self.idle_blocked = True
                return
            deadline = self.clock_ticks() + distance
            self.clock_units = (deadline * VIRTUAL_CPU_UNITS_PER_SECOND + TIMER_HZ - 1) // TIMER_HZ
            intc.pending()  # Latch the timer match even when CPSR currently masks IRQ delivery.
        self.idle_wakes += 1
        self.idle_blocked = False
        self.power.wake()
        cpu.reg_write(UC_ARM_REG_PC, address + 4)

    def read_mmio(self, _, offset, size, target):
        base, name, bank = target
        value = bank.read(offset, size)
        self.devices[name]['reads'] += 1
        self.read_counts[base + offset] += 1
        if name != 'UART3' and (offset != 0x120 or not name.startswith('HSMMC')):
            self.last_io.append(['read', name, hx(base + offset), size, hx(value)])
        return value

    def write_mmio(self, _, offset, size, value, target):
        base, name, bank = target
        bank.write(offset, size, value)
        if self.dma is not None and (bank is self.dma or bank is self.card):
            self.dma.service()
        self.devices[name]['writes'] += 1
        if name != 'UART3':
            self.last_io.append(['write', name, hx(base + offset), size, hx(value)])

    def checkpoint(self, cpu, address, _size, name):
        if name in self.events:
            return
        event = self.events[name] = {'pc': hx(address), 'lr': hx(cpu.reg_read(UC_ARM_REG_LR))}
        if name == 'set_ttbr0':
            self.ttbr0 = cpu.reg_read(UC_ARM_REG_R10)
            event['physical_table'] = hx(self.ttbr0)
        elif name == 'clear_high_ram_call':
            event['destination_va'] = hx(cpu.reg_read(UC_ARM_REG_R0))
            event['fill'] = cpu.reg_read(UC_ARM_REG_R1)
            event['bytes'] = cpu.reg_read(UC_ARM_REG_R2)
        elif name == 'clear_high_ram_return':
            self.high_ram_zeroed = self.seeded and not any(cpu.mem_read(*HIGH_RAM_CLEAR))

    def invalid_memory(self, cpu, access, address, size, value, _):
        self.fault = {'access': access, 'address': hx(address), 'size': size, 'value': hx(value),
                      'pc': hx(cpu.reg_read(UC_ARM_REG_PC)), 'lr': hx(cpu.reg_read(UC_ARM_REG_LR))}
        return False

    def ui_entry(self, cpu, address, _size, target):
        name, expected_pa = target
        if self.ui_entries[name] is None:
            translation = translate(cpu, address)
            if translation and translation.physical == expected_pa:
                self.ui_entries[name] = {'pc': hx(address), 'physical': hx(expected_pa)}

    def descriptor(self, virtual):
        if self.ttbr0 is None:
            return None
        entry = self.ttbr0 + (virtual >> 20) * 4
        value = word(self.cpu, entry)
        # Report the observed short-descriptor section. Preserve other descriptor types as raw evidence.
        return {'virtual': hx(virtual), 'descriptor': hx(value),
                'physical_section': hx(value & 0xfff00000) if (value & 3) == 2 and not value & (1 << 18) else None}

    def locate(self, physical):
        matches = [(name, rva + physical - start) for start, size, name, rva in self.sections
                   if start <= physical < start + size]
        if len(matches) == 1:
            name, rva = matches[0]
            return {'name': name, 'rva': hx(rva), 'physical': hx(physical)}
        return None

    def capture_frame(self, path):
        report, data = self.display.capture(self.cpu.mem_read, self.contains_ram)
        if data is not None:
            with path.open('xb') as output:
                output.write(data)
            report['path'] = str(path)
        return report

    def unavailable_public_rom(self, retries):
        """Deliver the SoC bus fault to CE when the public ROM has no backing image."""
        fault = self.fault
        if self.omap_public_rom_sha256 or not self.guest_exceptions.deliver or not fault:
            return None
        physical = int(fault['address'], 16)
        if (fault['access'] != UC_MEM_READ_UNMAPPED or
                not OMAP_PUBLIC_ROM_BASE <= physical < OMAP_PUBLIC_ROM_BASE + OMAP_PUBLIC_ROM_SIZE):
            return None
        cpu = self.cpu
        pc, cpsr = cpu.reg_read(UC_ARM_REG_PC), cpu.reg_read(UC_ARM_REG_CPSR)
        op = None if cpsr & 0x20 else instruction(cpu, pc)
        if op is None:
            return None
        addresses, write = data_access(cpu, pc, op)
        if write:
            return None
        for address in addresses:
            mapping = translate(cpu, address)
            key = (pc, address)
            if mapping is None or mapping.physical != physical or retries[key] >= 4:
                continue
            retries[key] += 1
            cpu.cpr_write(15, 0, 5, 0, 0, 0, False, 8)  # Synchronous external data abort.
            cpu.cpr_write(15, 0, 6, 0, 0, 0, False, address)
            vector = exception_entry(cpu, cpsr, pc, vector_offset=0x10, mode=0x17, return_offset=8, mask_async=True)
            self.guest_exceptions.events.append({'kind': 'public_rom_data_abort', 'pc': hx(pc), 'address': hx(address),
                                                 'physical': hx(physical), 'delivered_vector': hx(vector)})
            self.guest_exceptions.event_count += 1
            self.fault = None
            return vector | ((cp15(cpu, 1) >> 30) & 1)
        return None

    def run(self, *, instructions=3_500_000, seconds=6):
        error = None
        entry, remaining = self.entry, seconds * 1_000_000
        deadline = monotonic() + seconds
        retries = Counter()
        while True:
            try:
                self.cpu.emu_start(entry, 0, timeout=remaining, count=instructions)
                break
            except UcError as exc:
                remaining = int((deadline - monotonic()) * 1_000_000)
                # Resume only when the Unicorn instruction budget is disabled.
                entry = self.unavailable_public_rom(retries) if not instructions and remaining > 0 else None
                if entry is None:
                    error = str(exc)
                    break
        raw_serial = self.uart.output.decode('ascii', errors='replace')
        serial = [line for line in raw_serial.splitlines() if line.strip()]
        if error or self.guest_exceptions.stopped:
            stop = 'guest_error'
        elif self.idle_blocked:
            stop = 'guest_idle'
        else:
            stop = 'time_limit' if self.cpu.query(UC_QUERY_TIMEOUT) else 'instruction_limit'
        pc = self.cpu.reg_read(UC_ARM_REG_PC)
        translation = translate(self.cpu, pc)
        pc_module = self.locate(translation.physical) if translation and translation.physical is not None else None
        exceptions = self.guest_exceptions.report(self.cpu)
        for event in exceptions:
            if 'instruction_pa' in event:
                module = self.locate(int(event['instruction_pa'], 16))
                if module:
                    event['rom_module'] = module
        return {'rom_sha256': sha256(self.image).hexdigest(), 'omap_public_rom_sha256': self.omap_public_rom_sha256,
                'layout': self.layout, 'periphery': self.periphery,
                'limits': {'instructions': instructions, 'seconds': seconds},
                'timer': {'virtual_units_per_second': VIRTUAL_CPU_UNITS_PER_SECOND, 'timer_hz': TIMER_HZ}
                if self.virtual_timer else 'step_per_read',
                'bin_entry_pa': hx(self.entry), 'oem_table_va': hx(self.table),
                'oem_windows': [window.report() for window in self.windows],
                'ram': [{'physical': hx(start), 'size_bytes': size} for start, size in self.ram],
                'romhdr_initial_ram': {key: self.rom[key] for key in ('ram_start', 'ram_free', 'ram_end')},
                'checkpoints': self.events, 'high_ram_1mib_zeroed_at_return': self.high_ram_zeroed,
                'page_table_samples': [self.descriptor(va) for va in (0x84000000, 0x93f00000, 0xb3f00000)],
                'serial': serial, 'stop': stop, 'pc': hx(pc), 'pc_module': pc_module, 'ui_entries': self.ui_entries,
                'stop_context': {'lr': hx(self.cpu.reg_read(UC_ARM_REG_LR)),
                                 'cpsr': hx(self.cpu.reg_read(UC_ARM_REG_CPSR)),
                                 'clock_ticks': self.clock_ticks() if self.virtual_timer else None},
                'boot_trace': self.boot_trace.report() if self.boot_trace is not None else None,
                'error': error,
                'fault': self.fault, 'exceptions': exceptions, 'exception_count': self.guest_exceptions.event_count,
                'timer_irqs': self.irq_counts[37], 'irq_lines': dict(self.irq_counts),
                'idle_wakes': self.idle_wakes,
                'media': {'slot': self.slot, 'sectors': self.card.sectors, 'disk_start_lba': self.card.first_lba,
                          'commands': dict(self.card.commands),
                          'bytes_read': self.card.bytes_read, 'recent_sector_reads': list(self.card.read_requests),
                          'dma_transfers': self.dma.transfers if self.dma is not None else 0,
                          'recent_dma': list(self.dma.recent) if self.dma is not None else []}
                if self.card is not None else None,
                'mmio_devices': self.devices, 'last_mmio': list(self.last_io),
                'most_read_registers': [[hx(address), count] for address, count in self.read_counts.most_common(5)]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', type=Path, default=ROM_PATH)
    parser.add_argument('--omap-public-rom', type=Path, help='32 KiB OMAP35x public ROM at physical 0x40014000')
    parser.add_argument('--layout', choices=('gd13my', 'evm'), default='gd13my')
    parser.add_argument('--periphery', choices=('uart', 'boot'), default='boot')
    parser.add_argument('--guest-exceptions', action='store_true',
                        help='Deliver supported ARM memory aborts and WinCE breakpoints through guest vectors')
    parser.add_argument('--empty-mmc', action='store_true', help='Model HSMMC controllers with no storage media attached')
    parser.add_argument('--disk', type=Path, help='Attach a read-only eMMC sector image')
    parser.add_argument('--disk-start-lba', type=int, default=0, help='Physical sector corresponding to image sector zero')
    parser.add_argument('--mmc-slot', type=int, choices=(1, 2, 3), default=1)
    parser.add_argument('--frame', type=Path, help='Save the enabled LCD RGB565 graphics plane to a new PNG')
    parser.add_argument('--virtual-timer', action='store_true', help='Advance GPTIMER1 with a deterministic CPU block clock')
    parser.add_argument('--timer-irq', action='store_true', help='Deliver modeled GPTIMER1 and I2C interrupts through INTC')
    parser.add_argument('--boot-trace', action='store_true', help='Trace ROM-verified Device Manager and startup API calls')
    parser.add_argument('--instructions', type=int, default=3_500_000)
    parser.add_argument('--seconds', type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.instructions <= MAX_INSTRUCTIONS:
        parser.error(f'Choose 1 to {MAX_INSTRUCTIONS} instructions')
    if not 1 <= args.seconds <= MAX_SECONDS:
        parser.error(f'Choose 1 to {MAX_SECONDS} seconds')
    if (args.empty_mmc or args.virtual_timer or args.disk or args.frame) and args.periphery != 'boot':
        parser.error('MMC, display and virtual timer options require --periphery boot')
    if args.disk and args.empty_mmc:
        parser.error('Choose either --disk or --empty-mmc')
    if args.disk_start_lba < 0 or (args.disk_start_lba and not args.disk):
        parser.error('--disk-start-lba requires a disk and a nonnegative physical sector')
    if args.timer_irq and not args.virtual_timer:
        parser.error('--timer-irq requires --virtual-timer')
    if args.frame and args.frame.exists():
        parser.error('--frame requires a new output path')
    with ExitStack() as stack:
        card = ReadOnlyHsMmc(stack.enter_context(args.disk.open('rb')), first_lba=args.disk_start_lba) if args.disk else None
        run = KernelRun(args.image.read_bytes(), args.layout, args.periphery, guest_exceptions=args.guest_exceptions,
                        empty_mmc=args.empty_mmc, virtual_timer=args.virtual_timer, card=card, slot=args.mmc_slot,
                        display=args.frame is not None, timer_irq=args.timer_irq, boot_trace=args.boot_trace,
                        omap_public_rom=args.omap_public_rom.read_bytes() if args.omap_public_rom else None)
        report = run.run(instructions=args.instructions, seconds=args.seconds)
        if args.frame:
            report['frame'] = run.capture_frame(args.frame)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
