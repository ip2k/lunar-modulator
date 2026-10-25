"""Detail instrumentation must preserve the real engines' render-loop flow."""
import importlib.util
from pathlib import Path
import re
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def preparer():
    spec = importlib.util.spec_from_file_location(
        'renderer_prepare', ROOT / 'tools/jieli/prepare-renderer-devkit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('engine,name', [(0, 'mi_macro'), (1, 'drums')])
def test_hooks_preserve_actual_pull_loop(tmp_path, engine, name):
    if not shutil.which('c++'):
        pytest.skip('C++ compiler unavailable')
    source = (ROOT / f'engines/src/{name}.cc').read_text()
    body, = re.findall(r'  void Render\(float \*out_lr, uint32_t frames\) \{.*?\n  \}', source, re.S)
    observed = preparer().instrument_engine_profile(body, engine)
    declaration, observed = observed.split('\n', 1)
    # Compile the actual loop against a deterministic pull source. The
    # callback must cover every output, not just calls that generate input.
    harness = r'''
#include <stdint.h>
#include <assert.h>
static unsigned calls[4], frames_seen[4], depth[4];
extern "C" void lunar_devkit_engine_profile(unsigned r, unsigned n, int entering) {
    assert(r < 4);
    if (entering) { assert(!depth[r]); depth[r] = 1; }
    else { assert(depth[r]); depth[r] = 0; ++calls[r]; frames_seen[r] += n; }
}
struct RS { unsigned need, value; RS() : need(2), value(0) {} };
static unsigned fm1_resampler_needed(RS *r) { return r->need; }
static unsigned fm1_resampler_push(RS *r, const float *, unsigned n) { r->need -= n; return n; }
static float fm1_resampler_pop(RS *r) { assert(!r->need); r->need = 2; return float(++r->value); }
struct Original {
    enum { kBlockSize = 12 };
    RS resampler_; unsigned pending_ = 0, generated = 0; float mix_[kBlockSize];
    void RenderBlock() { ++generated; }
    ORIGINAL
};
struct Observed {
    enum { kBlockSize = 12 };
    RS resampler_; unsigned pending_ = 0, generated = 0; float mix_[kBlockSize];
    void RenderBlock() { ++generated; }
    OBSERVED
};
int main() {
    Original a; Observed b;
    unsigned total = 0;
    for (unsigned n : {0u, 1u, 63u, 128u, 7u}) {
        float x[256] = {}, y[256] = {};
        a.Render(x, n); b.Render(y, n); total += n;
        for (unsigned i = 0; i < 2*n; ++i) assert(x[i] == y[i]);
        assert(a.pending_ == b.pending_ && a.generated == b.generated);
        assert(calls[GENERATE] == b.generated && frames_seen[GENERATE] == b.generated * 12);
        assert(calls[POP] == total && frames_seen[POP] == total);
        for (unsigned i = 0; i < 4; ++i) assert(!depth[i]);
    }
}
'''.replace('ORIGINAL', body).replace('OBSERVED', observed)
    harness = '#include <initializer_list>\n' + harness
    harness = harness.replace('GENERATE', str(engine * 2)).replace('POP', str(engine * 2 + 1))
    cpp = tmp_path / 'pull.cc'
    cpp.write_text(harness)
    exe = tmp_path / 'pull'
    subprocess.run(['c++', '-std=c++11', '-O2', str(cpp), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)


@pytest.mark.parametrize('anchor', ['          RenderBlock();', 'fm1_resampler_pop(&resampler_);'])
def test_changed_pull_loop_refuses_instrumentation(anchor):
    text = (ROOT / 'engines/src/mi_macro.cc').read_text()
    with pytest.raises(ValueError, match='render loop'):
        preparer().instrument_engine_profile(text.replace(anchor, '', 1), 0)
