"""Read-only staged layout-7 Cynthion key register capture; never arms or writes."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from apollo_fpga import ApolloDebugger

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    parser.error('output already exists')
read = ApolloDebugger().registers.register_read
started = datetime.now(timezone.utc).isoformat()
regs = {1: read(1), 2: read(2)}
if regs != {1: 0x4C554E52, 2: 7}:
    raise SystemExit('Expected LUNR layout7; refusing unknown register map')
regs[3] = read(3)
if regs[3] & 0xE000 != 0xC000:
    raise SystemExit("Expected staged profile with CONTROL-only target power")
for address in (*range(4, 21), *range(0x20, 0x65)):
    regs[address] = read(address)
after = {address: read(address) for address in (3, 4, 12, 19)}
result = {
    'schema': 'lunar-key-readonly-staged-layout7-capture-v1',
    'started_utc': started,
    'completed_utc': datetime.now(timezone.utc).isoformat(),
    'registers': regs,
    'after_sweep': after,
    'atomic': False,
    'hardware_write_or_arm': False,
    'state': regs[3] & 15,
    'output_enables': (regs[4] >> 4) & 3,
    'state_gpio_terminal_ring_unchanged': all(regs[k] == v for k, v in after.items()),
}
with args.output.open('x') as output:
    json.dump(result, output, sort_keys=True, indent=2)
    output.write('\n')
print(json.dumps({k: v for k, v in result.items() if k not in ('registers', 'after_sweep')}, sort_keys=True))
