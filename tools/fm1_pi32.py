"""Bounded interpreter for the integer instructions used by the V15 FM kernel.

Parallel packet operands are read before either instruction commits writes.
That timing is inferred from static evidence, not independently established CPU
behavior. Unsupported instructions, ambiguous packets and unmapped memory fail
closed. No native runtime, subprocess, device access or mathematical DSP model
is used by this interpreter.
"""

from dataclasses import dataclass
import hashlib
import struct

try:
    from .fm1_decode import decode_instruction, instruction_size
    from .fm1_rebuild import RebuildError, rebuild_application
except ImportError:
    from fm1_decode import decode_instruction, instruction_size
    from fm1_rebuild import RebuildError, rebuild_application


MAX_MEMORY = 16 * 1024 * 1024
MAX_REGIONS = 64
MAX_INSTRUCTIONS = 1_000_000
V15_SHA256 = '306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203'
KERNEL_START = 0x01C01124
KERNEL_END = 0x01C01344
EXPERIMENT_RANGES = ((0x85064, 0x85284), (0x89F8E, 0x8AF8E))


class Pi32Error(ValueError):
    """The bounded instruction or memory contract was violated."""


def _word(value):
    if type(value) is not int or not -(1 << 31) <= value < (1 << 32):
        raise Pi32Error('register values must be signed or unsigned 32-bit integers')
    return value & 0xFFFFFFFF


def _signed(value, bits=32):
    value &= (1 << bits) - 1
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


@dataclass
class _Region:
    address: int
    data: bytearray
    permissions: str
    name: str


class Memory:
    """Sparse, nonoverlapping mappings with explicit read/write/execute access."""

    def __init__(self):
        self._regions = []
        self._size = 0

    def map(self, address, data, permissions='r', name='region'):
        if (type(address) is not int or not isinstance(data, (bytes, bytearray))
                or not data or not 0 <= address < 1 << 32 or address + len(data) > 1 << 32):
            raise Pi32Error('invalid memory mapping')
        if not isinstance(permissions, str) or not permissions or set(permissions) - set('rwx'):
            raise Pi32Error('memory permissions must contain r, w and/or x')
        if self._size + len(data) > MAX_MEMORY or len(self._regions) >= MAX_REGIONS:
            raise Pi32Error('memory mapping limit exceeded')
        if any(address < region.address + len(region.data) and region.address < address + len(data)
               for region in self._regions):
            raise Pi32Error('overlapping memory mappings')
        self._regions.append(_Region(address, bytearray(data), permissions, str(name)))
        self._size += len(data)

    def _locate(self, address, size, access):
        if (type(address) is not int or type(size) is not int or size < 1
                or address < 0 or address + size > 1 << 32):
            raise Pi32Error('invalid memory access')
        for region in self._regions:
            if region.address <= address and address + size <= region.address + len(region.data):
                if access not in region.permissions:
                    raise Pi32Error(f'{access} access denied at 0x{address:08x} ({region.name})')
                return region, address - region.address
        raise Pi32Error(f'unmapped {access} access at 0x{address:08x}, size {size}')

    def read(self, address, size, *, access='r'):
        if access not in ('r', 'x'):
            raise Pi32Error('memory reads require read or execute permission')
        region, offset = self._locate(address, size, access)
        return bytes(region.data[offset:offset + size])

    def write(self, address, data):
        if not isinstance(data, bytes) or not data:
            raise Pi32Error('memory writes require nonempty bytes')
        region, offset = self._locate(address, len(data), 'w')
        region.data[offset:offset + len(data)] = data


class Pi32Machine:
    """Subset interpreter; every instruction fetch is bounded and permission checked."""

    def __init__(self, memory, *, registers=None, instruction_budget=20000):
        if not isinstance(memory, Memory):
            raise Pi32Error('Memory is required')
        if type(instruction_budget) is not int or not 1 <= instruction_budget <= MAX_INSTRUCTIONS:
            raise Pi32Error(f'instruction budget must be in 1..{MAX_INSTRUCTIONS}')
        self.memory = memory
        self.registers = {f'r{i}': 0 for i in range(16)} | {'sp': 0, 'rets': 0}
        if registers is not None:
            if not isinstance(registers, dict) or set(registers) - self.registers.keys():
                raise Pi32Error('unknown register')
            self.registers.update({name: _word(value) for name, value in registers.items()})
        self.instruction_budget = instruction_budget
        self.instructions = 0
        self.pc = None

    def _fetch(self, address):
        if address & 1:
            raise Pi32Error('unaligned instruction address')
        first = int.from_bytes(self.memory.read(address, 2, access='x'), 'little')
        raw = self.memory.read(address, instruction_size(first), access='x')
        instruction = decode_instruction(raw, 0, address)
        if not instruction['supported']:
            raise Pi32Error(f'unsupported instruction at 0x{address:08x}: {raw.hex()}')
        return instruction

    def _skip_one(self, address):
        instruction = self._fetch(address)
        if instruction.get('parallel_pair'):
            raise Pi32Error('predicated parallel packet semantics are not established')
        return (address + instruction['size']) & 0xFFFFFFFF

    def _effect(self, instruction, registers):
        writes, stores = {}, []
        next_pc = None
        mnemonic = instruction['mnemonic']
        destination = instruction.get('register')

        def reg(name):
            if name not in registers:
                raise Pi32Error(f'unsupported register {name}')
            return registers[name]

        def assign(name, value):
            if name not in registers or name in writes:
                raise Pi32Error('ambiguous or unsupported register write')
            writes[name] = value & 0xFFFFFFFF

        def store(address, size, value):
            if address % size:
                raise Pi32Error('unaligned data access is outside the supported subset')
            self.memory._locate(address, size, 'w')
            stores.append((address, (value & ((1 << (size * 8)) - 1)).to_bytes(size, 'little')))

        def load(address, size):
            if address % size:
                raise Pi32Error('unaligned data access is outside the supported subset')
            return int.from_bytes(self.memory.read(address, size), 'little')

        if 'memory' in instruction:
            if mnemonic not in ('lw', 'lhu', 'lbu', 'sw', 'sh', 'sb'):
                raise Pi32Error(f'memory instruction semantics are not implemented: {mnemonic}')
            operand = instruction['memory']
            base = reg(operand['base'])
            offset = ((reg(operand['index']) << operand['index_shift']) if 'index' in operand
                      else operand['offset'])
            address = (base + offset) & 0xFFFFFFFF
            update = operand.get('update')
            if update == 'pre':
                assign(operand['base'], address)
            elif update:
                if not update.startswith('post '):
                    raise Pi32Error('unsupported memory update')
                assign(operand['base'], base + int(update.split()[1]))
            if operand['access'] == 'write':
                store(address, operand['width'], reg(destination))
            else:
                assign(destination, load(address, operand['width']))
        elif mnemonic == 'nop':
            pass
        elif mnemonic == 'mov':
            assign(destination, reg(instruction['source_register']) if 'source_register' in instruction else instruction['immediate'])
        elif mnemonic in ('add', 'sub', 'reverse_sub', 'or', 'xor', 'and', 'and_not', 'mul'):
            if 'source_registers' in instruction:
                left, right = (reg(name) for name in instruction['source_registers'])
            elif 'immediate' in instruction:
                left, right = reg(instruction.get('source_register', destination)), instruction['immediate']
            else:
                left, right = reg(destination), reg(instruction['source_register'])
            value = {'add': lambda: left + right, 'sub': lambda: left - right,
                     'reverse_sub': lambda: right - left, 'or': lambda: left | right,
                     'xor': lambda: left ^ right, 'and': lambda: left & right,
                     'and_not': lambda: left & ~right, 'mul': lambda: left * right}[mnemonic]()
            assign(destination, value)
        elif mnemonic in ('lsl', 'lsr', 'asr'):
            value = reg(instruction['source_register'])
            shift = reg(instruction['shift_register']) if 'shift_register' in instruction else instruction['immediate']
            if not 0 <= shift <= 31:
                raise Pi32Error('shift count outside established 0..31 semantics')
            assign(destination, (value << shift) if mnemonic == 'lsl' else
                   (_signed(value) >> shift) if mnemonic == 'asr' else (value >> shift))
        elif mnemonic in ('uxtb', 'sxtb', 'uxth', 'sxth'):
            bits = 8 if mnemonic.endswith('b') else 16
            value = reg(instruction['source_register'])
            assign(destination, _signed(value, bits) if mnemonic.startswith('s') else value & ((1 << bits) - 1))
        elif mnemonic == 'uextra':
            position, length = instruction['position'], instruction['length']
            if not 0 <= position < 32 or not 1 <= length <= 32 - position:
                raise Pi32Error('bit extraction outside one word has unestablished semantics')
            assign(destination, (reg(instruction['source_register']) >> position) & ((1 << length) - 1))
        elif mnemonic in ('jz', 'jnz'):
            take = (reg(destination) == 0) == (mnemonic == 'jz')
            if take:
                next_pc = instruction['target']
        elif mnemonic in ('branch_if', 'predicate_next'):
            condition = instruction['condition'] if mnemonic == 'branch_if' else instruction['predicate']
            skipped_pc = None
            if mnemonic == 'predicate_next':
                if condition.get('instruction_count') != 1:
                    raise Pi32Error('unsupported predicate extent')
                # Both predicate outcomes use the same supported-subset rule.
                # Do not accidentally allow a true predicate to run a packet
                # whose extent would be ambiguous for a false predicate.
                skipped_pc = self._skip_one(instruction['address'] + instruction['size'])
            left = reg(condition['register'])
            right = condition['immediate']
            if condition.get('signed'):
                left, right = _signed(left), _signed(right)
            else:
                right &= 0xFFFFFFFF
            take = {'==': left == right, '!=': left != right, '<': left < right,
                    '<=': left <= right, '>': left > right, '>=': left >= right}[condition['comparison']]
            if mnemonic == 'branch_if' and take:
                next_pc = instruction['target']
            elif mnemonic == 'predicate_next' and not take:
                next_pc = skipped_pc
        elif mnemonic == 'goto':
            next_pc = instruction['target']
        elif mnemonic == 'push':
            saved = instruction['registers']
            sp = (reg('sp') - 4 * len(saved)) & 0xFFFFFFFF
            for index, name in enumerate(reversed(saved)):
                store(sp + index * 4, 4, reg(name))
            assign('sp', sp)
        elif mnemonic in ('pop', 'pop_pc'):
            restored = instruction.get('registers', ['pc'])
            sp = reg('sp')
            for index, name in enumerate(reversed(restored)):
                value = load(sp + index * 4, 4)
                if name == 'pc':
                    next_pc = value
                else:
                    assign(name, value)
            assign('sp', sp + 4 * len(restored))
        else:
            raise Pi32Error(f'instruction semantics are not implemented: {mnemonic}')
        return writes, stores, next_pc

    def step(self):
        if self.pc is None:
            raise Pi32Error('program counter has not been initialized')
        first = self._fetch(self.pc)
        packet = [first]
        following = (self.pc + first['size']) & 0xFFFFFFFF
        if first.get('parallel_pair'):
            second = self._fetch(following)
            if second.get('parallel_pair'):
                raise Pi32Error('nested parallel packets are ambiguous')
            forbidden = {'push', 'pop', 'pop_pc', 'goto', 'jz', 'jnz', 'branch_if', 'predicate_next'}
            if first['mnemonic'] in forbidden or second['mnemonic'] in forbidden:
                raise Pi32Error('control flow inside a parallel packet is unsupported')
            packet.append(second)
            following = (following + second['size']) & 0xFFFFFFFF
        if self.instructions + len(packet) > self.instruction_budget:
            raise Pi32Error('instruction budget exhausted')
        effects = [self._effect(instruction, self.registers) for instruction in packet]
        writes, stores, next_pc = {}, [], following
        for register_writes, memory_writes, target in effects:
            if writes.keys() & register_writes.keys():
                raise Pi32Error('parallel instructions write the same register')
            writes.update(register_writes)
            for address, data in memory_writes:
                if any(address < previous + len(payload) and previous < address + len(data)
                       for previous, payload in stores):
                    raise Pi32Error('overlapping packet memory writes')
                stores.append((address, data))
            if target is not None:
                next_pc = target
        for address, data in stores:
            self.memory.write(address, data)
        self.registers.update(writes)
        self.pc = next_pc
        self.instructions += len(packet)

    def run(self, entry, *, stop_address):
        self.pc = _word(entry)
        stop_address = _word(stop_address)
        while self.pc != stop_address:
            self.step()
        return {'registers': dict(self.registers), 'pc': self.pc, 'instructions': self.instructions,
                'packet_timing': 'inferred read-before-write; not independently proven CPU behavior'}


def run_operator_kernel(application, operator_words, feedback=(0, 0), *,
                        kernel_feedback_shift=16, instruction_budget=20000):
    """Execute exact V15 kernel bytes with synthetic memory and real app LUTs.

    operator_words contains three (previous_attenuation, level, increment,
    phase) rows. Only the caller's first-operator preparation is modeled here;
    all kernel arithmetic and table access executes through decoded operands.
    The exact source hash keeps inferred addresses from applying to other code.
    """
    _require_stock_application(application)
    return _execute_operator_image(application, operator_words, feedback,
                                   kernel_feedback_shift=kernel_feedback_shift,
                                   instruction_budget=instruction_budget)


def _require_stock_application(application):
    if (not isinstance(application, bytes) or len(application) != 581564
            or hashlib.sha256(application).hexdigest() != V15_SHA256):
        raise Pi32Error('exact verified FM-1_015 application is required')


def _check_experiment_ranges(normalized_patches):
    """Check complete ranges after fm1_rebuild validates and normalizes patches."""
    for patch in normalized_patches:
        start = patch['offset']
        end = start + len(patch['expected_hex']) // 2
        if not any(lower <= start < end <= upper for lower, upper in EXPERIMENT_RANGES):
            raise Pi32Error('experiment patches must fit entirely within the verified operator kernel or lookup tables')


def run_operator_experiment(original_application, patches, operator_words, feedback=(0, 0), *,
                            kernel_feedback_shift=16, instruction_budget=20000):
    """Rebuild and execute a reversible, narrowly scoped V15 experiment in memory.

    The original must be exact stock V15. Patches use fm1_rebuild's source-hash,
    expected-byte, same-size and reversible-manifest contract; every full range
    must lie in the known kernel or its lookup tables. Other mapped context
    therefore retains the original bytes. This returns execution observations
    and a manifest, never a firmware image or a hardware-compatibility claim.
    Unsupported instructions and illegal memory still terminate execution.
    """
    _require_stock_application(original_application)
    try:
        modified, manifest = rebuild_application(original_application, patches,
                                                  expected_source_sha256=V15_SHA256)
    except RebuildError as error:
        raise Pi32Error(f'experiment patch validation failed: {error}') from error
    _check_experiment_ranges(manifest['patches'])
    result = _execute_operator_image(modified, operator_words, feedback,
                                     kernel_feedback_shift=kernel_feedback_shift,
                                     instruction_budget=instruction_budget)
    result.update(kind='fm1-operator-experiment', status='experimental', experimental=True,
                  source_sha256=V15_SHA256, executed_image_sha256=manifest['result_sha256'],
                  manifest=manifest, execution_environment='bounded offline Python interpreter',
                  hardware_behavior_verified=False)
    return result


def _execute_operator_image(application, operator_words, feedback, *,
                            kernel_feedback_shift, instruction_budget):
    """Internal execution after the public entry point establishes provenance."""
    if not isinstance(operator_words, (tuple, list)) or len(operator_words) != 3:
        raise Pi32Error('three operator word rows are required')
    rows = []
    for row in operator_words:
        if not isinstance(row, (tuple, list)) or len(row) != 4:
            raise Pi32Error('each operator requires four words')
        values = [_word(value) for value in row]
        if values[0] > 16384 or values[1] > 16384 << 14:
            raise Pi32Error('operator start/level is outside the established domain')
        rows.append(values)
    if not isinstance(feedback, (tuple, list)) or len(feedback) != 2:
        raise Pi32Error('two feedback words are required')
    history = [_word(value) for value in feedback]
    if type(kernel_feedback_shift) is not int or not 2 <= kernel_feedback_shift <= 16:
        raise Pi32Error('kernel feedback shift must be in 2..16')
    start = rows[0][0] or 16383
    target = 16384 - (_signed(rows[0][1]) >> 14)
    rows[0][1] = target
    state_address, feedback_address, output_address = 0x10000, 0x11000, 0x12000
    stack_address, entry_sp, returned = 0x20000, 0x20400, 0xFFFFFF00
    memory = Memory()
    memory.map(KERNEL_START, application[0x85064:0x85284], 'rx', 'V15 operator code')
    memory.map(0x01C0604E, application[0x89F8E:0x8AF8E], 'r', 'V15 operator lookup tables')
    memory.map(state_address, struct.pack('<12I', *(value for row in rows for value in row)), 'rw', 'operator state')
    memory.map(feedback_address, struct.pack('<2I', *history), 'rw', 'feedback')
    memory.map(output_address, bytes(64 * 4), 'rw', 'output')
    memory.map(stack_address, bytes(0x800), 'rw', 'stack')
    memory.write(entry_sp, struct.pack('<2I', feedback_address, kernel_feedback_shift))
    initial = {f'r{i}': 0xABC00000 + i for i in range(4, 16)}
    initial.update(r0=output_address, r1=state_address, r2=start, r3=target, sp=entry_sp, rets=returned)
    machine = Pi32Machine(memory, registers=initial, instruction_budget=instruction_budget)
    execution = machine.run(KERNEL_START, stop_address=returned)
    if machine.registers['sp'] != entry_sp or any(machine.registers[f'r{i}'] != initial[f'r{i}'] for i in range(4, 16)):
        raise Pi32Error('kernel did not restore stack and callee-saved registers')
    words = struct.unpack('<12I', memory.read(state_address, 48))
    return {'samples': tuple(struct.unpack('<64i', memory.read(output_address, 256))),
            'feedback': tuple(struct.unpack('<2i', memory.read(feedback_address, 8))),
            'operator_words': tuple(tuple(words[index:index + 4]) for index in (0, 4, 8)),
            'instructions': execution['instructions'], 'packet_timing': execution['packet_timing'],
            'application_sha256': hashlib.sha256(application).hexdigest(), 'device_io_performed': False}
