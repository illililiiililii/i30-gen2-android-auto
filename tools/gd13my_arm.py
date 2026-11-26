"""Trace ARMv7 short-descriptor faults and deliver observed CE exceptions."""

from collections import Counter, deque
from dataclasses import dataclass
import struct

from unicorn import UC_HOOK_INSN_INVALID, UC_HOOK_INTR, UcError
from unicorn.arm_const import (UC_ARM_REG_CPSR, UC_ARM_REG_FPEXC, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
                               UC_ARM_REG_SP, UC_ARM_REG_SPSR)

RM = tuple(UC_ARM_REG_R0 + n for n in range(13)) + (UC_ARM_REG_SP, UC_ARM_REG_LR)
WINCE_ARM_BREAK = 0xe6000010
DATA_ABORT = 4  # Unicorn's ARM exception number
PREFETCH_ABORT = 3
MAX_EXCEPTIONS = 4096


def hx(value):
    return f'0x{value:08x}'


def cp15(cpu, crn, opc2=0):
    return cpu.cpr_read(15, 0, crn, 0, opc2, 0, False)


def word(cpu, address):
    return struct.unpack('<I', cpu.mem_read(address, 4))[0]


@dataclass(frozen=True)
class Translation:
    physical: int | None
    l1: int
    l2: int | None = None
    fault_status: int | None = None

    def report(self):
        return {'physical': hx(self.physical) if self.physical is not None else None, 'l1': hx(self.l1),
                'l2': hx(self.l2) if self.l2 is not None else None, 'translation_fault_status': self.fault_status}


def translate(cpu, va):
    """Read the live ARMv7 short-descriptor tables without changing their permissions."""
    ttbcr = cp15(cpu, 2, 2)
    if ttbcr & (1 << 31) or not cp15(cpu, 1) & 1:
        return None
    n = ttbcr & 7
    high = bool(n and va >> (32 - n))
    if ttbcr & (0x20 if high else 0x10):
        return None
    base = cp15(cpu, 2, int(high)) & ~((1 << (14 if high else 14 - n)) - 1)
    try:
        l1 = word(cpu, base + (va >> 20) * 4)
        match l1 & 3:
            case 0:
                return Translation(None, l1, fault_status=5)
            case 1:
                l2 = word(cpu, (l1 & 0xfffffc00) + ((va >> 12) & 255) * 4)
                if l2 & 2:
                    return Translation((l2 & 0xfffff000) | (va & 0xfff), l1, l2)
                if not l2 & 3:
                    return Translation(None, l1, l2, fault_status=7)
            case 2 if not l1 & (1 << 18):
                return Translation((l1 & 0xfff00000) | (va & 0xfffff), l1)
    except UcError:
        return None
    return None  # Other descriptor formats are outside the diagnostic scope.


def instruction(cpu, pc):
    target = translate(cpu, pc)
    if target and target.physical is not None:
        try:
            return word(cpu, target.physical)
        except UcError:
            return None
    return None


def address_offset(cpu, pc, op):
    """Decode the immediate-shift register offset of an A32 single transfer."""
    rm = op & 15
    value = pc + 8 if rm == 15 else cpu.reg_read(RM[rm])
    amount = (op >> 7) & 31
    match (op >> 5) & 3:
        case 0:
            return (value << amount) & 0xffffffff
        case 1:
            return value >> (amount or 32)
        case 2:
            signed = value if value < 0x80000000 else value - (1 << 32)
            return (signed >> (amount or 32)) & 0xffffffff
        case 3 if amount:
            return ((value >> amount) | (value << (32 - amount))) & 0xffffffff
        case 3:
            carry = (cpu.reg_read(UC_ARM_REG_CPSR) >> 29) & 1
            return (carry << 31) | (value >> 1)


def data_access(cpu, pc, op):
    """Return observed A32 single and block-transfer addresses in transfer order."""
    if op >> 28 == 0xf:
        return (), False
    rn = (op >> 16) & 15
    address = pc + 8 if rn == 15 else cpu.reg_read(RM[rn])
    before = bool(op & (1 << 24))
    ascending = bool(op & (1 << 23))
    write = not bool(op & (1 << 20))
    match op & 0x0e000000:
        case 0x04000000 | 0x06000000 if not (op & (1 << 25) and op & (1 << 4)):
            if before:
                offset = address_offset(cpu, pc, op) if op & (1 << 25) else op & 0xfff
                address += offset if ascending else -offset
            return (address & 0xffffffff,), write
        case 0x08000000 if rn != 15 and not op & (1 << 22):
            count = (op & 0xffff).bit_count()
            if ascending:
                address += 4 if before else 0
            else:
                address -= 4 * (count if before else count - 1)
            return tuple((address + i * 4) & 0xffffffff for i in range(count)), write
    extra = op & 0x0e0000f0
    if extra == 0x000000b0 or (not write and extra in (0x000000d0, 0x000000f0)):
        # LDRH/STRH and sign-extending loads. The doubleword stores are outside this path.
        if before:
            rm = op & 15
            if op & (1 << 22):
                offset = ((op >> 4) & 0xf0) | rm
            else:
                offset = pc + 8 if rm == 15 else cpu.reg_read(RM[rm])
            address += offset if ascending else -offset
        return (address & 0xffffffff,), write
    return (), False


def abort_status(cpu, translation, cpsr, *, write, fetch):
    if translation.fault_status == 5:
        return 5
    domain = (translation.l1 >> 5) & 15
    domain_mode = (cp15(cpu, 3) >> (2 * domain)) & 3
    section = translation.l1 & 3 == 2
    if domain_mode in (0, 2):
        return (0x09 if section else 0x0b) | (domain << 4)
    if translation.fault_status:
        return translation.fault_status | (domain << 4)
    if domain_mode != 1 or cp15(cpu, 1) & (1 << 29):
        return None  # Only the observed client-domain, no-access-flag profile.
    if translation.l2 is None:
        ap = ((translation.l1 >> 13) & 4) | ((translation.l1 >> 10) & 3)
        xn = bool(translation.l1 & (1 << 4))
    else:
        ap = ((translation.l2 >> 7) & 4) | ((translation.l2 >> 4) & 3)
        xn = bool(translation.l2 & 1)
    if ap == 4:  # Reserved.
        return None
    user = cpsr & 0x1f == 0x10
    if write:
        permitted = ap == 3 or (not user and ap in (1, 2))
    else:
        permitted = ap in (2, 3, 6, 7) or (not user and ap in (1, 5))
    return None if permitted and not (fetch and xn) else (0x0d if section else 0x0f) | (domain << 4)


def exception_entry(cpu, cpsr, pc, *, vector_offset, mode, return_offset, mask_async=False):
    sctlr = cp15(cpu, 1)
    vector = 0xffff0000 if sctlr & (1 << 13) else cp15(cpu, 12) & ~31
    thumb = (sctlr >> 30) & 1
    endian = (sctlr >> 25) & 1
    updated = (cpsr & ~0x0700fe3f) | (endian << 9) | (thumb << 5) | 0x80 | mode
    if mask_async:
        updated |= 0x100
    cpu.reg_write(UC_ARM_REG_CPSR, updated)
    cpu.reg_write(UC_ARM_REG_SPSR, cpsr)
    cpu.reg_write(UC_ARM_REG_LR, (pc + return_offset) & 0xffffffff)
    cpu.reg_write(UC_ARM_REG_PC, (vector + vector_offset) | thumb)
    return vector + vector_offset


class GuestExceptions:
    def __init__(self, cpu, deliver):
        self.deliver = deliver
        self.events = deque(maxlen=MAX_EXCEPTIONS)
        self.event_count = 0
        self.stopped = False
        self.repeats = Counter()
        self.last_abort = None
        self.consecutive_aborts = 0
        self.prefetch_return = None
        self.vfp_retries = {}
        self.watch_changed = None
        cpu.hook_add(UC_HOOK_INTR, self.interrupt)
        cpu.hook_add(UC_HOOK_INSN_INVALID, self.invalid_instruction)

    def observe_prefetch_return(self, cpu, address):
        expected = self.prefetch_return
        if expected and address == expected[0]:
            mode = cpu.reg_read(UC_ARM_REG_CPSR) & 0x1f
            if (mode, cpu.reg_read(UC_ARM_REG_SP)) == expected[1:]:
                self.last_abort = None
                self.prefetch_return = None

    def observe_vfp_retry(self, cpu, address, block_size):
        mode = cpu.reg_read(UC_ARM_REG_CPSR) & 0x1f
        lr, sp = cpu.reg_read(UC_ARM_REG_LR), cpu.reg_read(UC_ARM_REG_SP)
        context = (lr, sp, mode)
        for pc in (address - 4, address):
            pending = self.vfp_retries.get(pc)
            if pending is None or context not in pending:
                continue
            if address == pc and (block_size <= 4 or not cpu.reg_read(UC_ARM_REG_FPEXC) & (1 << 30)):
                # An invalid instruction ends the Unicorn block at that instruction.
                continue
            # CE can also complete the instruction and return to its successor.
            self.repeats.pop((pc, lr, sp), None)
            pending.remove(context)
            if not pending:
                del self.vfp_retries[pc]

    def interrupt(self, cpu, number, _):
        cpsr = cpu.reg_read(UC_ARM_REG_CPSR)
        pc = cpu.reg_read(UC_ARM_REG_PC)
        lr = cpu.reg_read(UC_ARM_REG_LR)
        op = None if cpsr & 0x20 else instruction(cpu, pc)
        event = {'kind': 'arm_exception', 'number': number, 'pc': hx(pc), 'lr': hx(lr), 'cpsr': hx(cpsr),
                 'opcode': hx(op) if op is not None else None}
        source = translate(cpu, pc)
        if op is not None and source and source.physical is not None:
            event['instruction_pa'] = hx(source.physical)
        self.events.append(event)
        self.event_count += 1
        addresses, write = (), False
        if number == DATA_ABORT and op is not None:
            addresses, write = data_access(cpu, pc, op)
        elif number == PREFETCH_ABORT:
            addresses = (pc,)
        for address in addresses:
            translation = translate(cpu, address)
            if not translation:
                continue
            data = number == DATA_ABORT
            status = abort_status(cpu, translation, cpsr, write=write, fetch=not data)
            if not status:
                continue
            event.update(address=hx(address), access=('write' if write else 'read') if data else 'fetch',
                         before=translation.report(), fault_status=hx(status))
            sp = cpu.reg_read(UC_ARM_REG_SP)
            key = (number, pc, address, lr, sp, translation)
            if not data:
                # CE API calls share a trap address and stub return PC across distinct calls.
                arguments = tuple(cpu.reg_read(register) for register in RM[:4])
                key += arguments
                event['arguments'] = [hx(value) for value in arguments]
            self.consecutive_aborts = self.consecutive_aborts + 1 if key == self.last_abort else 1
            self.last_abort = key
            if self.deliver and self.consecutive_aborts <= (1 if data else 4):
                fsr = status | ((1 << 11) if write else 0)
                cpu.cpr_write(15, 0, 5, 0, 0 if data else 1, 0, False, fsr)
                cpu.cpr_write(15, 0, 6, 0, 0 if data else 2, 0, False, address)
                vector = exception_entry(cpu, cpsr, pc, vector_offset=0x10 if data else 0x0c, mode=0x17,
                                         return_offset=8 if data else 4, mask_async=True)
                event['delivered_vector'] = hx(vector)
                if not data:
                    self.prefetch_return = (lr & ~1, cpsr & 0x1f, sp)
                    if self.watch_changed is not None:
                        self.watch_changed()
                return
            if self.deliver:
                event['delivery_stopped'] = 'repeated_abort'
            break
        self.stopped = True
        cpu.emu_stop()

    def invalid_instruction(self, cpu, _):
        cpsr = cpu.reg_read(UC_ARM_REG_CPSR)
        pc = cpu.reg_read(UC_ARM_REG_PC)
        op = None if cpsr & 0x20 else instruction(cpu, pc)
        lr = cpu.reg_read(UC_ARM_REG_LR)
        event = {'kind': 'wince_arm_breakpoint' if op == WINCE_ARM_BREAK else 'invalid_instruction',
                 'pc': hx(pc), 'lr': hx(lr), 'opcode': hx(op) if op is not None else None}
        is_coprocessor = op is not None and ((op >> 25) & 7 == 6 or (op >> 24) & 15 == 14)
        coprocessor = (op >> 8) & 15 if is_coprocessor else None
        if coprocessor in (10, 11):
            cpacr, fpexc = cp15(cpu, 1, 2), cpu.reg_read(UC_ARM_REG_FPEXC)
            access = (cpacr >> (coprocessor * 2)) & 3
            allowed = access == 3 or (access == 1 and cpsr & 0x1f != 0x10)
            event.update(cpacr=hx(cpacr), fpexc=hx(fpexc))
            if not allowed or not fpexc & (1 << 30):
                event['kind'] = 'vfp_access_trap'
        self.events.append(event)
        self.event_count += 1
        key = (pc, lr, cpu.reg_read(UC_ARM_REG_SP))
        if (self.deliver and event['kind'] in ('wince_arm_breakpoint', 'vfp_access_trap')
                and self.repeats[key] < 4):
            self.repeats[key] += 1
            if event['kind'] == 'vfp_access_trap':
                self.vfp_retries.setdefault(pc, set()).add((lr, key[2], cpsr & 0x1f))
                if self.watch_changed is not None:
                    self.watch_changed()
            vector = exception_entry(cpu, cpsr, pc, vector_offset=4, mode=0x1b, return_offset=4)
            event['delivered_vector'] = hx(vector)
            return True
        return False

    def report(self, cpu):
        for event in self.events:
            if 'address' in event and 'delivered_vector' in event:
                after = translate(cpu, int(event['address'], 16))
                event['translation_at_stop'] = after.report() if after else None
        return list(self.events)
