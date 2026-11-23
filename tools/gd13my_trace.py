"""Read-only execution probes for the GD13MY ROM's boot and launch code."""

from collections import deque

from unicorn import UC_HOOK_CODE, UcError
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_R0, UC_ARM_REG_R1

from gd13my_arm import hx, translate
from phase1_rom import module_details


EXPORTS = {
    'device.dll': ('DevMainEntry',),
    'devmgr.dll': ('StartDeviceManager',),
    'gwes.dll': ('GwesMain',),
    'ddi.dll': ('DrvEnableDriver', 'DisplayInit'),
    'gps.dll': ('GPS_Init',),
    'rtc.dll': ('RTC_Init',),
    'dbg_log.dll': ('DBG_Init',),
}
CORE_EXPORTS = ('SignalStarted', 'CreateProcessW', 'LoadLibraryW', 'LoadLibraryExW', 'CreateFileW',
                'ActivateDeviceEx', 'WaitForAPIReady', 'WaitForSingleObject', 'WaitForMultipleObjects')
PATH_ARGUMENT = {'CreateProcessW', 'LoadLibraryW', 'LoadLibraryExW', 'CreateFileW', 'ActivateDeviceEx'}
WAIT_ARGUMENT = {'WaitForAPIReady', 'WaitForSingleObject', 'WaitForMultipleObjects'}
INIT_LAUNCH_IDS = {0, 20, 25, 30, 60, 100}
BOOT_PATHS = {'device.dll', 'avnsysinit.exe', 'servicesstart.exe', 'gwes.dll', 'ddi.dll', 'autostartup.exe',
              'dsp_bridge.dll', 'touch_calib.exe', 'ucomh_new.exe', 'gddnavi.exe'}


def guest_wide_string(cpu, address, contains_ram, *, max_bytes=512):
    """Read a bounded UTF-16LE string across mapped guest pages."""
    if not address or address & 1:
        return None
    data = bytearray()
    while len(data) < max_bytes:
        target = translate(cpu, address)
        if target is None or target.physical is None:
            return None
        size = min(max_bytes - len(data), 0x1000 - (address & 0xfff))
        if not contains_ram(target.physical, size):
            return None
        try:
            page = cpu.mem_read(target.physical, size)
        except UcError:
            return None
        for offset in range(0, len(page), 2):
            if page[offset:offset + 2] == b'\0\0':
                data.extend(page[:offset])
                return data.decode('utf-16le', errors='replace')
        data.extend(page)
        address += size
    return None


class BootTrace:
    def __init__(self, cpu, rom, read, clock, contains_ram):
        self.clock = clock
        self.contains_ram = contains_ram
        self.milestones = {}
        self.recent = deque(maxlen=512)
        alias = int(rom['address_alias_delta'], 16)
        for row in rom['contents']:
            name = row['name']
            if name in ('k.coredll.dll', 'coredll.dll'):
                symbols = CORE_EXPORTS
            elif name in EXPORTS:
                symbols = EXPORTS[name]
            else:
                continue
            module = module_details(row, read)
            for item in module['exports']:
                symbol = item['name']
                if symbol not in symbols:
                    continue
                rva = int(item['rva'], 16) & ~1
                for section in module['sections']:
                    offset = rva - int(section['rva'], 16)
                    flags = int(section['flags'], 16)
                    length = min(section['size'], section['stored_bytes'])
                    if 0 <= offset < length and flags & 0x20000000 and not flags & 0x2000:
                        address = int(section['runtime_va'], 16) + offset
                        physical = int(section['stored_va'], 16) - alias + offset
                        cpu.hook_add(UC_HOOK_CODE, self.record, (name, symbol, physical),
                                     begin=address, end=address)
                        break

    def record(self, cpu, address, _size, target):
        module, symbol, physical = target
        mapping = translate(cpu, address)
        if mapping is None or mapping.physical != physical:
            return
        r0 = cpu.reg_read(UC_ARM_REG_R0)
        r1 = cpu.reg_read(UC_ARM_REG_R1)
        event = {'module': module, 'symbol': symbol, 'pc': hx(address), 'physical': hx(physical),
                 'caller': hx(cpu.reg_read(UC_ARM_REG_LR)), 'clock_ticks': self.clock(), 'r0': hx(r0), 'r1': hx(r1)}
        if symbol == 'SignalStarted':
            event['launch_id'] = r0
            if r0 in INIT_LAUNCH_IDS:
                self.milestones.setdefault(f'SignalStarted({r0})', event)
        elif symbol in PATH_ARGUMENT:
            pointer = (r0 or r1) if symbol == 'CreateProcessW' else r0
            path = event['path'] = guest_wide_string(cpu, pointer, self.contains_ram)
            if path:
                normalized = path.casefold()
                if (normalized.rsplit('\\', 1)[-1] in BOOT_PATHS or
                        symbol == 'CreateProcessW' and normalized.startswith('\\diska\\application\\')):
                    self.milestones.setdefault(f'{symbol} {path}', event)
        elif symbol not in WAIT_ARGUMENT:
            self.milestones.setdefault(f'{module}!{symbol}', event)
        self.recent.append(event)

    def report(self):
        return {'milestones': self.milestones, 'recent_calls': list(self.recent)}
