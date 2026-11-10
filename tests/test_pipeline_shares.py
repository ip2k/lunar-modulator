"""The pipelined app's sharing table (pipeline_shares in sim/web/src/fm1_app.c)
against the engines' objects.

The pipeline renders Sound 2's chain on CPU1 while CPU0 renders the other
sounds, but only when Sound 2's engine and inserts share no writable state
with anything on CPU0 (pipeline_admit). Engines do not declare what they
share, so the app keeps a table of the engines whose code reaches writable
globals. This test builds every engine (GPL modules on), follows each
engine descriptor's link closure through the objects' symbol tables, and
collects the writable data (.data/.bss/common) it can reach. Then:

- an engine is in the table exactly when its closure reaches such state;
- two engines whose closures meet have a share bit in common, so they never
  run on different cores;
- no object outside every engine's closure refers to that state. The build
  is the engines' own (fm1-render and its renderer), not the app: the app's
  objects in sim/web/src are not checked here, and reach engines only
  through their descriptors.

Three kinds of writable symbol are exempt, each named below: rate units
written only by the first create (at a drained barrier, nothing in flight),
msfa's frequency-table pointer, which every DX7 block stores with the same
value on the FM-1, and pointers or arrays of pointers placed in writable data
but never written. notes/2026-11-10-soft-locks.md."""
import collections
import json
import platform
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Written only by the first DX7 create (msfa_dx7.cc SharedInit: the rate and
# the LFO and pitch-envelope units); later creates only compare the rate. The
# app creates engines at a drained barrier (fm1_app_select's PIPELINE_GUARD).
CREATE_ONLY = {'_ZN3fm13dx79g_rate_hzE', '_ZN8fm1_msfa3Lfo5unit_E', '_ZN8fm1_msfa8PitchEnv5unit_E'}
# Stored at the top of every DX7 RenderBlock (fm1_freqlut = Lut()), so two
# DX7s on two cores both write it. At 44,118 Hz every instance stores the
# address of the one ROM table (kFreqLut44118), the same word each time:
# test_freqlut_rate_is_the_fm1_rate pins that rate to the FM-1's. At any other
# host rate each instance points it at a table of its own (equal contents,
# different address), which is only safe while one core renders DX7s.
SAME_EVERY_BLOCK = {'_ZN8fm1_msfa11fm1_freqlutE'}
# Initialised to a const table's address and never assigned (msfa_tables.cc).
NEVER_ASSIGNED = {'_ZN8fm1_msfa11fm1_exp2tabE', '_ZN8fm1_msfa10fm1_sintabE'}
EXEMPT = CREATE_ONLY | SAME_EVERY_BLOCK | NEVER_ASSIGNED
# Braids' tables of pointers: not const, never written.
NEVER_WRITTEN = re.compile(r'^_ZN6braids(\d+\w+_table|\d+\w+9fn_table_)E$')


def symbols(obj):
    """(kind, name): U undefined; W/w writable data (global/local); D/d other."""
    if platform.system() == 'Darwin':
        out = subprocess.run(['nm', '-m', str(obj)], capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            m = re.search(r'(\(undefined\)|\((__\w+),(__\w+)\)) (?:weak )?(?:private )?'
                          r'(external|non-external)(?: \[[^\]]*\])* (\S+)', line)
            if not m:
                continue
            name = m.group(5)[1:] if m.group(5).startswith('_') else m.group(5)
            if m.group(1) == '(undefined)':
                yield 'U', name
                continue
            w = m.group(2) == '__DATA' and m.group(3) in ('__data', '__bss', '__common')
            kind = 'w' if w else 'd'
            yield (kind.upper() if m.group(4) == 'external' else kind), name
    else:
        out = subprocess.run(['objdump', '-t', str(obj)], capture_output=True, text=True, check=True).stdout
        for line in out.splitlines():
            m = re.match(r'^[0-9a-f]+ (.)(.{6}) (\S+)\s+[0-9a-f]+\s+(?:\.hidden\s+)?(\S+)$', line)
            if not m:
                continue
            scope, flags, sec, name = m.groups()
            if name == sec or name.startswith('.'):     # section and file symbols
                continue
            if sec == '*UND*':
                yield 'U', name
                continue
            w = 'F' not in flags and (sec == '*COM*' or (sec.startswith(('.data', '.bss'))
                                                        and not sec.startswith('.data.rel.ro')))
            kind = 'w' if w else 'd'
            yield (kind.upper() if scope in 'gu' else kind), name


@pytest.fixture(scope='module')
def engines(tmp_path_factory):
    cc, cxx = shutil.which('clang') or shutil.which('gcc'), shutil.which('clang++') or shutil.which('g++')
    tool = 'nm' if platform.system() == 'Darwin' else 'objdump'
    if not cc or not cxx or not shutil.which('make') or not shutil.which(tool):
        pytest.skip('native toolchain unavailable')
    out = tmp_path_factory.mktemp('shares')
    subprocess.run(['make', '-s', '-C', str(ROOT / 'engines'), f'BUILD={out}', 'FM1_GPL_MODS=1',
                    f'CC={cc}', f'CXX={cxx}', '-j4', str(out / 'fm1-render')],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    objs = sorted(out.rglob('*.o'))
    defs, undef, wdata = {}, collections.defaultdict(set), collections.defaultdict(set)
    for o in objs:
        for kind, name in symbols(o):
            if kind == 'U':
                undef[o].add(name)
                continue
            if kind.isupper():
                defs.setdefault(name, o)
            if kind in 'wW' and not name.startswith(('ltmp', 'l_', '.L')):
                # a local is its object's own: two objects' statics of one name are two
                wdata[o].add(name if kind == 'W' else f'{o.name}:{name}')

    def closure(o):
        seen, todo = {o}, [o]
        while todo:
            for s in undef[todo.pop()]:
                d = defs.get(s)
                if d is not None and d not in seen:
                    seen.add(d)
                    todo.append(d)
        return seen

    ids = {}                                   # engine id -> the object defining its descriptor
    for o in objs:
        rel = o.relative_to(out).parts
        src = ROOT / 'engines/src' / (o.stem + '.cc')
        if rel[:2] != ('our', 'src') or not src.exists():
            continue
        text = src.read_text()
        for m in re.finditer(r'fm1_engine_t\s+\w+\s*=\s*\{[^"{}]*?"([a-z0-9-]+)"', text):
            ids[m.group(1)] = o
        # mi_fx.cc defines its three descriptors through a macro
        for m in re.finditer(r'^FM1_MI_FX\(\s*\w+,\s*\w+,\s*"([a-z0-9-]+)"', text, re.M):
            ids[m.group(1)] = o
    # Every sound engine and audio effect the build registers, as fm1-render
    # lists them: a descriptor the patterns above miss fails here, rather
    # than leaving that engine's shared state unchecked.
    listed = json.loads(subprocess.run([str(out / 'fm1-render'), '--list'], capture_output=True,
                                       text=True, check=True).stdout)
    registered = {e['id'] for e in listed if e['kind'] in ('sound', 'audio_fx')}
    assert set(ids) == registered, (sorted(registered - set(ids)), sorted(set(ids) - registered))
    closures = {i: closure(o) for i, o in ids.items()}
    reach = {i: set().union(*(wdata[x] for x in c)) for i, c in closures.items()}
    kinds = {e['id']: e['kind'] for e in listed}
    return objs, undef, closures, reach, kinds


def table():
    src = (ROOT / 'sim/web/src/fm1_app.c').read_text()
    body = src[src.index('static unsigned pipeline_shares('):]
    body = body[:body.index('};')]
    return {i: s for i, s in re.findall(r'\{\s*"([a-z0-9-]+)",\s*(SHARE_\w+)\s*\}', body)}


def shared(reach):
    return {s for s in reach if s not in EXEMPT and not NEVER_WRITTEN.match(s)}


def test_every_engine_with_shared_state_is_in_the_table(engines):
    _, _, _, reach, _ = engines
    t = table()
    assert len(reach) >= 40, sorted(reach)      # the descriptors were found
    assert set(t) <= set(reach), set(t) - set(reach)
    for i, r in sorted(reach.items()):
        s = shared(r)
        assert bool(s) == (i in t), (i, sorted(s), t.get(i))


def test_engines_whose_state_meets_share_a_bit(engines):
    _, _, _, reach, _ = engines
    t = table()
    ids = sorted(reach)
    for n, a in enumerate(ids):
        for b in ids[n + 1:]:
            meet = shared(reach[a]) & shared(reach[b])
            if meet:
                assert t[a] == t[b], (a, b, sorted(meet))


def test_nothing_outside_the_engines_touches_their_state(engines):
    objs, undef, closures, reach, _ = engines
    inside = set().union(*closures.values())
    state = set().union(*(shared(r) | (r & EXEMPT) for r in reach.values()))
    for o in objs:
        if o not in inside:
            assert not (undef[o] & state), (o.name, sorted(undef[o] & state))


def test_macro_reaches_no_shared_state(engines):
    """Macro's Chip arpeggiator kept its random walk in stmlib::Random's one
    global until 2026-11-10 (engines/third_party/mutable/UPSTREAM.md); Macro
    can now run on CPU1 beside Drums on CPU0."""
    _, _, _, reach, _ = engines
    assert not shared(reach['macro'])
    assert 'macro' not in table()


def test_freqlut_rate_is_the_fm1_rate():
    """The SAME_EVERY_BLOCK exemption holds only while msfa's ROM frequency
    table is for the rate the FM-1 image runs the engines at."""
    msfa = (ROOT / 'engines/src/msfa.h').read_text()
    live = (ROOT / 'firmware/fm1/fm1_live.h').read_text()
    a = int(re.search(r'kFreqLutRateHz\s*=\s*(\d+)', msfa).group(1))
    b = int(re.search(r'#define\s+LUNAR_FM1_RATE\s+(\d+)u?', live).group(1))
    assert a == b == 44118, (a, b)


def test_no_device_master_effect_shares_state(engines):
    """pipeline_admit fails closed (a park, exit 72 on the host) when a master
    effect shares a group with CPU0, because the masters always run on CPU1.
    No audio effect the device image registers is in the table, so no master
    pick can reach that park; adding one must change the masters' core first."""
    *_, kinds = engines
    mk = (ROOT / 'tools/jieli/devkit-renderer-sdk.mk').read_text()
    modules = re.search(r'^LUNAR_MODULES \?= (\S+)', mk, re.M).group(1).split(',')
    t = table()
    fx = [m for m in modules if kinds.get(m) == 'audio_fx']
    assert fx, modules
    assert not [m for m in fx if m in t], [(m, t[m]) for m in fx if m in t]
