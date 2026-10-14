"""Exclude allocation-site loops in the pinned ISR closures; no CPU entry claim.

Usage: SOURCE ELF DISASSEMBLY STACK_RECEIPT OUTPUT.
"""
import hashlib
import json
import pathlib
import re
import sys


def check_region(start, end, rows):
    """Require straight-line allocations, then no branch back into that prefix."""
    allocations = []
    targets = []
    cursor = start
    branch_seen = False
    for pc, encoded, assembly in rows:
        assert pc == cursor, ('instruction coverage gap', hex(cursor), hex(pc))
        cursor += len(encoded)
        allocation = assembly.startswith('[--sp] = ') or bool(
            re.match(r'sp \+= -[1-9]\d*$', assembly))
        if allocation:
            assert not branch_seen, ('allocation after control flow', hex(pc))
            allocations.append(pc)
        # Reject control transfers not modeled by relative branches or returns.
        assert not re.search(r'\b(?:tb[bh]|rep|swi|syscall|rti|rtx|rte)\b', assembly), (
            'unsupported control flow', hex(pc), assembly)
        assert '<unknown instruction>' not in assembly
        assert not re.search(r'\b(?:goto|call) r\d+', assembly)
        if re.search(r'\bpc\s*=', assembly) or re.search(r'\{pc[,}]', assembly):
            assert '[sp++]' in assembly, ('unsupported PC write', hex(pc))
            branch_seen = True
        if assembly == 'rts':
            branch_seen = True
        branch = re.search(r'\b(goto|call) (-?\d+)', assembly)
        if branch:
            branch_seen = True
            target = cursor + int(branch[2])
            if branch[1] == 'goto':
                assert start <= target < end, ('external branch', hex(pc), hex(target))
                targets.append((pc, target))
    assert cursor == end, ('incomplete function', hex(cursor), hex(end))
    prefix_end = max((pc + len(raw) for pc, raw, _ in rows
                      if pc in allocations), default=start)
    pcs = {pc for pc, _, _ in rows}
    for pc, target in targets:
        assert target in pcs, ('branch into instruction', hex(pc), hex(target))
        assert target >= prefix_end, ('branch into allocation prefix', hex(pc), hex(target))
    return {'allocation_sites': [hex(pc) for pc in allocations],
            'allocation_prefix_end': hex(prefix_end),
            'relative_branch_count': len(targets), 'instruction_count': len(rows),
            'allocation_prefix_cannot_be_reentered_by_local_branches': True}


def main():
    source, elf_path, dis_path, stack_path, output = map(pathlib.Path, sys.argv[1:6])
    digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    sys.path.insert(0, str(source / 'tools/jieli'))
    from audit_link import Elf
    elf = Elf(elf_path.read_bytes())
    stack = json.loads(stack_path.read_text())
    assert digest(elf_path) == stack['elf_sha256']
    profiles = {
        'df358a616de234c0263344cffda7d5fd626a4c1079dd5f352574cfe77fa93a8e':
            ('46ff199b5288a37be1f7e3f155cf93bce765b9cf888d31cb8110648740de6e38',
             'f4ce4f05040df257e418be0b25813a082ab82524d07d049f0dcbe80fdb1e4eec'),
        '4b340d1aa4f67737d102441680df5d28a2740d6a2eaa83feb028ea19a9f49e2b':
            ('6bcbad133dc5bab573c7c5da744032b6c83142f64f00a7403a6c8c44485c61c9', '1e0447f3ad3cda4a67cea74b7d840c53ce7563d613ff97296f7990f25587e531'),
    }
    assert digest(elf_path) in profiles
    assert (digest(dis_path), digest(stack_path)) == profiles[digest(elf_path)]
    closure = set().union(*(handler['frames'] for handler in stack['handlers']))
    symbols = {}
    for symbol in elf.symbols:
        if symbol['type'] == 2 and symbol['shndx'] and symbol['size']:
            address = symbol['value']
            symbols[address] = max(symbols.get(address, 0), symbol['size'])
    instructions = []
    for line in dis_path.read_text().splitlines():
        match = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)', line)
        if match:
            instructions.append((int(match[1], 16), bytes.fromhex(match[2]), match[3]))
    results = {}
    for address in sorted(closure):
        start = int(address, 16)
        end = start + symbols[start]
        rows = [row for row in instructions if start <= row[0] < end]
        for pc, encoded, _ in rows:
            assert elf.read(pc, len(encoded)) == encoded, ('ELF instruction mismatch', hex(pc))
        results[address] = check_region(start, end, rows)
    receipt = {'scope': 'no local branch reentry into ISR allocation prefixes',
               'elf_sha256': digest(elf_path), 'disassembly_sha256': digest(dis_path),
               'stack_receipt_sha256': digest(stack_path), 'functions': results,
               'function_count': len(results), 'hardware_admitted': False,
               'limits': ['conditional on vendor instruction decoding and call inventory',
                          'hardware entry, stack selection, interrupt nesting excluded',
                          'no complete startup stack or target timing admission']}
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'functions': len(results), 'hardware_admitted': False}))


if __name__ == '__main__':
    main()
