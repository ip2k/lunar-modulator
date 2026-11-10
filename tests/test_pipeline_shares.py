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

Two kinds of writable symbol are exempt, each named below: tables that are
written only while an engine is created (at a drained barrier, nothing in
flight), and arrays the compiler places in writable data because they are
arrays of pointers, never written. notes/2026-11-10-soft-locks.md."""
import collections
import platform
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Written only by create (fm1_msfa_dx7 create: the rate, the LFO and pitch
# envelope units, the table pointers), which the app calls at a drained
# barrier (fm1_app_select's PIPELINE_GUARD), always with the same values.
CREATE_ONLY = {
    '_ZN3fm13dx79g_rate_hzE', '_ZN8fm1_msfa11fm1_exp2tabE', '_ZN8fm1_msfa11fm1_freqlutE',
    '_ZN8fm1_msfa3Lfo5unit_E', '_ZN8fm1_msfa8PitchEnv5unit_E',
}
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
        for m in re.finditer(r'fm1_engine_t\s+\w+\s*=\s*\{[^"{}]*?"([a-z0-9-]+)"', src.read_text()):
            ids[m.group(1)] = o
    closures = {i: closure(o) for i, o in ids.items()}
    reach = {i: set().union(*(wdata[x] for x in c)) for i, c in closures.items()}
    return objs, undef, closures, reach


def table():
    src = (ROOT / 'sim/web/src/fm1_app.c').read_text()
    body = src[src.index('static unsigned pipeline_shares('):]
    body = body[:body.index('};')]
    return {i: s for i, s in re.findall(r'\{\s*"([a-z0-9-]+)",\s*(SHARE_\w+)\s*\}', body)}


def shared(reach):
    return {s for s in reach if s not in CREATE_ONLY and not NEVER_WRITTEN.match(s)}


def test_every_engine_with_shared_state_is_in_the_table(engines):
    _, _, _, reach = engines
    t = table()
    assert len(reach) >= 30, sorted(reach)      # the descriptors were found
    assert set(t) <= set(reach), set(t) - set(reach)
    for i, r in sorted(reach.items()):
        s = shared(r)
        assert bool(s) == (i in t), (i, sorted(s), t.get(i))


def test_engines_whose_state_meets_share_a_bit(engines):
    _, _, _, reach = engines
    t = table()
    ids = sorted(reach)
    for n, a in enumerate(ids):
        for b in ids[n + 1:]:
            meet = shared(reach[a]) & shared(reach[b])
            if meet:
                assert t[a] == t[b], (a, b, sorted(meet))


def test_nothing_outside_the_engines_touches_their_state(engines):
    objs, undef, closures, reach = engines
    inside = set().union(*closures.values())
    state = set().union(*(shared(r) | (r & CREATE_ONLY) for r in reach.values()))
    for o in objs:
        if o not in inside:
            assert not (undef[o] & state), (o.name, sorted(undef[o] & state))


def test_macro_reaches_no_shared_state(engines):
    """Macro's Chip arpeggiator kept its random walk in stmlib::Random's one
    global until 2026-11-10 (engines/third_party/mutable/UPSTREAM.md); Macro
    can now run on CPU1 beside Drums on CPU0."""
    _, _, _, reach = engines
    assert not shared(reach['macro'])
    assert 'macro' not in table()
