"""Held-key compaction preserves ordering and inactive bytes, including bounds."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("sanitize", [False, True])
def test_held_key_state_matches_stable_compaction(tmp_path, sanitize):
    compiler = shutil.which(os.environ.get("CXX", "clang++"))
    if not compiler:
        pytest.skip("C++ compiler unavailable")
    source = tmp_path / "held.cc"
    source.write_text(r'''
#include "glide.h"
#include <cassert>
#include <cstring>
int main() {
  using fm1::glide::Held;
  for (unsigned count=0; count<256; ++count) {
    for (unsigned pattern=0; pattern<32; ++pattern) {
      for (unsigned key=0; key<32; ++key) {
        Held actual;
        actual.n=static_cast<uint8_t>(count);
        for (int i=0; i<Held::kMaxHeld; ++i)
          actual.key[i]=static_cast<uint8_t>((i*pattern+pattern)%32);
        Held expected=actual;
        // Original stable compaction is the compatibility oracle. Compare
        // inactive trailing bytes too: they remain part of the held state.
        int end=0;
        for (int i=0; i<expected.n && i<Held::kMaxHeld; ++i)
          if (expected.key[i]!=key) expected.key[end++]=expected.key[i];
        expected.n=static_cast<uint8_t>(end);
        actual.Remove(static_cast<uint8_t>(key));
        assert(actual.n==expected.n);
        assert(!std::memcmp(actual.key,expected.key,sizeof actual.key));
      }
    }
  }
}
''')
    binary = tmp_path / "held"
    flags = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"] if sanitize else []
    subprocess.run([compiler, "-std=c++11", "-O2", *flags,
                    "-I"+str(ROOT/"engines/src"), "-I"+str(ROOT/"engines/include"),
                    str(source), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
