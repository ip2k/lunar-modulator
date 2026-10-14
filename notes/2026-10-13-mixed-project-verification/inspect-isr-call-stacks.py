"""Conservative explicit-frame costs for the pinned native ISR call graphs.

Usage: SOURCE INVENTORY INTERRUPT_RECEIPT OUTPUT. No hardware nesting claim.
"""
import hashlib
import json
import pathlib
import re
import sys

source, inventory_path, interrupts_path, output = map(pathlib.Path, sys.argv[1:5])
digest = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
inventory = json.loads(inventory_path.read_text())
interrupts = json.loads(interrupts_path.read_text())
assert inventory['elf_sha256'] == interrupts['elf_sha256']
assert inventory['disassembly_sha256'] == interrupts['disassembly_sha256']
assert digest(inventory_path) == '58fbd7c36e570db6b55f413f7912f9c82841fb5b31a2d68d6664e247b4e9c48b'
graph = inventory['functions']

def saved_words(text):
    registers = set()
    for item in text.strip('{}').split(','):
        item = item.strip()
        match = re.fullmatch(r'r(\d+)-r(\d+)', item)
        if match:
            hi, lo = map(int, match.groups())
            assert 15 >= hi >= lo >= 0
            registers.update(f'r{i}' for i in range(lo, hi + 1))
        else:
            assert item == 'rets' or re.fullmatch(r'r\d+', item), item
            registers.add(item)
    return len(registers)

def frame(row):
    # Sum every allocation, even mutually exclusive ones: a conservative bound
    # provided no allocation lies on a loop. That property needs separate review.
    total = 0
    for operation in row['stack']:
        text = operation['instruction']
        if text.startswith('[--sp] = '):
            total += saved_words(text.split(' = ', 1)[1]) * 4
        elif text.startswith('sp += '):
            change = int(text[6:])
            if change < 0:
                total -= change
        elif '[sp++]' in text or re.search(r'\[sp(?:[+\]])', text):
            pass  # Restores or fixed-frame accesses do not allocate.
        else:
            raise AssertionError(('unclassified stack operation', operation))
    return total

campaign = []
for root, count in [('0x204daae', 15), ('0x204de8a', 5)]:
    seen = set()
    pending = [root]
    while pending:
        address = pending.pop()
        if address in seen:
            continue
        seen.add(address)
        row = graph[address]
        assert not row['unresolved'] and not row['decoding_limits'], address
        for callee in row['direct']:
            assert callee in graph, ('missing callee', address, callee)
            pending.append(callee)
    assert len(seen) == count, (root, len(seen))
    visiting, memo = set(), {}
    def longest(address):
        if address in memo:
            return memo[address]
        assert address not in visiting, ('recursive ISR graph', address)
        visiting.add(address)
        children = [longest(callee) for callee in graph[address]['direct']]
        child_bytes, child_path = max(children, default=(0, []), key=lambda x: x[0])
        result = frame(graph[address]) + child_bytes, [address] + child_path
        visiting.remove(address)
        memo[address] = result
        return result
    cost, path = longest(root)
    campaign.append({
        'root': root, 'name': graph[root]['names'][0], 'reachable_functions': count,
        'explicit_c_chain_bytes': cost, 'wrapper_bytes': 28,
        'explicit_chain_with_wrapper_bytes': cost + 28,
        'longest_candidate_path': [{'address': a, 'names': graph[a]['names'],
                                    'frame_bytes': frame(graph[a])} for a in path],
        'frames': {a: frame(graph[a]) for a in sorted(seen)},
    })
receipt = {
    'scope': 'direct acyclic ISR graph and explicit software frame accounting',
    'elf_sha256': inventory['elf_sha256'],
    'inventory_sha256': digest(inventory_path),
    'interrupt_receipt_sha256': digest(interrupts_path), 'handlers': campaign,
    'limits': ['stack allocation sites must be checked not to accumulate in loops',
               'table branches and instruction inventory completeness remain separate gates',
               'hardware entry overhead, CPU stack selection and nesting are excluded',
               'no whole startup stack, timing or hardware admission conclusion'],
    'hardware_admitted': False,
}
output.write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps(campaign))
