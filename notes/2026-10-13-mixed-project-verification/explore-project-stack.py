# Exploratory disassembly inventory, not a hardware admission gate.
import bisect, hashlib, json, pathlib, re, sys
sys.path.insert(0, sys.argv[1] + '/tools/jieli')
from audit_link import Elf
elf_path, dis_path = map(pathlib.Path, sys.argv[2:4])
e = Elf(elf_path.read_bytes())
ins = []
for line in dis_path.read_text().splitlines():
    m = re.match(r'\s*([0-9a-f]+):\s+((?:[0-9a-f]{2} )+)\s*(.*)', line)
    if m: ins.append((int(m[1], 16), len(m[2].split()), m[3]))
ins.sort(); addresses = [x[0] for x in ins]
f = {x['name']: x for x in e.symbols if x['type'] == 2 and x['size']}
a = {x['value']: n for n, x in f.items()}
edges, unresolved, frames, stack_ops = {}, [], {}, {}
# Historical SET callback hints are incomplete for PROJECT startup.
# Unresolved callbacks and recursion prevent treating this as a bound.
callback_targets = {'bemit': ['set_record'], 'cs_get': ['read_bytes'],
    'in_byte': ['cs_src'], 'cs_src': ['read_bytes'], 'ib': ['pull_byte'],
    'tflush': ['line_text'], 'kv_each': ['info_kv', 'proj_kv', 'view_kv', 'setg_kv', 'level_kv']}
for n, x in f.items():
    lines = ins[bisect.bisect_left(addresses, x['value']):bisect.bisect_left(addresses, x['value'] + x['size'])]
    calls, frame, ops = [], 0, []
    for addr, size, t in lines:
        m = re.search(r'\bcall (-?\d+)', t)
        if m:
            dest = addr + size + int(m[1]); target = a.get(dest)
            if target: calls.append(target)
            else: unresolved.append((n, hex(addr), 'direct', hex(dest)))
        elif re.search(r'\bgoto (-?\d+)', t):
            m = re.search(r'\bgoto (-?\d+)', t)
            dest = addr + size + int(m[1])
            if not x['value'] <= dest < x['value'] + x['size']:
                target = a.get(dest)
                if target: calls.append(target)
                else: unresolved.append((n, hex(addr), 'external-goto', hex(dest)))
        elif re.search(r'\b(?:call|goto) r\d+', t):
            if n in callback_targets: calls.extend(callback_targets[n])
            else: unresolved.append((n, hex(addr), 'indirect', t))
        if re.search(r'\bsp\b', t): ops.append((hex(addr), t))
        frame += sum(int(v) for v in re.findall(r'\bsp \+= -(\d+)', t))
        if '[--sp]' in t:
            m = re.search(r'\[--sp\] = (.*)', t)
            registers = m[1].strip('{} ').split(',')
            for reg in registers:
                reg = reg.strip(); rng = re.fullmatch(r'r(\d+)-r(\d+)', reg)
                if rng: frame += (abs(int(rng[1])-int(rng[2]))+1)*4
                elif reg in ('rets',) or re.fullmatch(r'r\d+', reg): frame += 4
                else: unresolved.append((n,hex(addr),'stack-save',reg))
    edges[n], frames[n], stack_ops[n] = calls, frame, ops
seen, todo = set(), ['lunar_project_start']
while todo:
    n = todo.pop()
    if n in seen: continue
    seen.add(n); todo.extend(edges[n])
cycles = []
def depth(n, path=()):
    if n in path: cycles.append(path + (n,)); return 0, [n]
    options = [depth(child, path + (n,)) for child in edges[n]]
    cost, chain = max(options, default=(0, []), key=lambda x:x[0])
    return frames[n]+cost, [n]+chain
cost, chain = depth('lunar_project_start')
r = dict(scope='PROJECT exploration; legacy SET callback hints incomplete; no control-flow, recursion, dynamic-stack or ABI proof; not admitted', root='lunar_project_start',
    elf_sha256=hashlib.sha256(e.data).hexdigest(), callback_targets=callback_targets,
    reachable_functions=len(seen), unresolved=[u for u in unresolved if u[0] in seen],
    cycles=cycles, estimated_loader_chain_bytes=cost, estimated_loader_chain=chain,
    caller_frame_estimate=frames['fm1_cstart'], activation_frame_estimate=frames['lunar_content_activate_set'],
    stack_instructions={n:stack_ops[n] for n in sorted(seen) if stack_ops[n]})
pathlib.Path(sys.argv[4]).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps({k:v for k,v in r.items() if k!='stack_instructions'},indent=2))
