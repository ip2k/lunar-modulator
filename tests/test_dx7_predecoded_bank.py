"""Generated note-on cache bytes must equal the runtime decoder, independently."""
import os
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('sanitize', [False, True])
def test_predecoded_bank_matches_runtime_decoder(tmp_path, sanitize):
    cxx = shutil.which(os.environ.get('CXX', 'clang++'))
    if not cxx:
        pytest.skip('C++ compiler unavailable')
    src = tmp_path / 'bank.cc'
    src.write_text(r'''
#include "dx7_bank.h"
#include "dx7_voice.h"
#include <cassert>
#include <cstring>
namespace fm1_msfa {
#include "patch.cc"
}
int main() {
  for (int p=0;p<fm1::dx7::kBankSize;++p) {
    unsigned char decoded[156];
    fm1::dx7::FromPacked(fm1::dx7::kBank[p], decoded);
    assert(!std::memcmp(decoded, fm1::dx7::kBankUnpacked[p], sizeof decoded));
  }
}
''')
    exe = tmp_path / 'bank'
    flags = ['-fsanitize=address,undefined', '-fno-omit-frame-pointer'] if sanitize else []
    subprocess.run([cxx, '-std=c++11', '-O2', *flags,
                    '-I'+str(ROOT/'engines/src'), '-I'+str(ROOT/'engines/include'),
                    '-I'+str(ROOT/'engines/third_party/msfa'), str(src),
                    str(ROOT/'engines/src/dx7_voice.cc'), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True, timeout=10)
