#!/usr/bin/env python3
"""Bounded original-vs-candidate resampler experiment; no device access.

Reference comes from the immutable pre-experiment Git object, not a second
implementation of the FIR. Requires that commit in local history. On Darwin
only the ELF section spelling is adapted; noinline/always_inline are retained.
"""
import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

BASE = 'd168869b5aa77385ccbecaaf32dbaa2379d65887'
ROOT = Path(__file__).resolve().parents[2]
HEADER = 'engines/include/fm1_resampler.h'

HARNESS = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
namespace original {
#include "original.h"
}
UNDEFINES
namespace candidate {
#include "candidate.h"
}
static unsigned comparisons, wraps, tails;
static uint32_t bits(float x) { uint32_t b; memcpy(&b,&x,4); return b; }
static float sample(unsigned pattern, unsigned n) {
  uint32_t b=0;
  switch(pattern) {
  case 0: break; // initial and sustained zero
  case 1: b=0x80000000u; break; // negative zero
  case 2: b=(n&1)?0x80000000u:0; break;
  case 3: return n==0 ? 1.f:0.f; // impulse and complete decay to silence
  case 4: return n<500 ? .25f:0.f; // nonzero, then FIR tail
  case 5: return (float)((int)(n*1664525u+1013904223u)%65536)/65536.f;
  case 6: return (n&1)?1.f:-1.f;
  case 7: b=n==7?0x7fc12345u:0; break; // quiet NaN and retirement
  case 8: b=n==7?0x7f800000u:0; break;
  case 9: b=n==7?0xff800000u:0; break;
  case 10: b=(n%127==0)?0x00800000u:0x80000001u; break; // tiny normal/subnormal
  case 11: b=(n%61==0)?0x7f7fffffu:0xff7fffffu; break;
  }
  float x; memcpy(&x,&b,4); return x;
}
int main() {
  // Both Drums and SixOp use the same corrected 47,872.34 Hz rate.
  // Native rate plus other supported hosts and ratio endpoints exercise
  // different phase/tap schedules; rejected and pass-through modes too.
  const float rates[][2]={{47872.34f,44118.f},{47872.34f,44117.6f},
    {47872.34f,24000.f},{96000.f,44118.f},{176472.f,44118.f},
    {47872.34f,47872.34f},{0.f,44118.f},{44118.f,96000.f}};
  for(unsigned rate=0;rate<sizeof(rates)/sizeof(rates[0]);++rate)
    for(unsigned pattern=0;pattern<12;++pattern) {
      original::fm1_resampler_t a;
      candidate::fm1_resampler_t b;
      static_assert(sizeof(a)==sizeof(b),"state layout changed");
      memset(&a,0x5a,sizeof(a)); memset(&b,0x5a,sizeof(b));
      int ia=original::fm1_resampler_init(&a,rates[rate][0],rates[rate][1]);
      int ib=candidate::fm1_resampler_init(&b,rates[rate][0],rates[rate][1]);
      if(ia!=ib || memcmp(&a,&b,sizeof(a))) return 1;
      unsigned input=0;
      for(unsigned out=0;out<6000;++out) {
        unsigned need=original::fm1_resampler_needed(&a);
        if(need!=candidate::fm1_resampler_needed(&b)) return 2;
        while(need) {
          // Alternate partial, one-sample and whole readiness pushes.
          unsigned count=(out%3==0)?1:need;
          float values[64];
          for(unsigned j=0;j<count;++j) values[j]=sample(pattern,input++);
          unsigned pa,pb;
          if(out&1) {
            pa=original::fm1_resampler_push_ready_(&a,values,count);
            pb=candidate::fm1_resampler_push_ready_(&b,values,count);
          } else {
            pa=original::fm1_resampler_push(&a,values,count);
            pb=candidate::fm1_resampler_push(&b,values,count);
          }
          if(pa!=pb || memcmp(&a,&b,sizeof(a))) return 3;
          need=original::fm1_resampler_needed(&a);
          if(need!=candidate::fm1_resampler_needed(&b)) return 4;
        }
        unsigned old=a.mid_w;
        float x=(out&1)?original::fm1_resampler_pop_ready_(&a):original::fm1_resampler_pop(&a);
        float y=(out&1)?candidate::fm1_resampler_pop_ready_(&b):candidate::fm1_resampler_pop(&b);
        if(bits(x)!=bits(y) || memcmp(&a,&b,sizeof(a))) {
          fprintf(stderr,"mismatch rate=%u pattern=%u output=%u bits=%08x/%08x state=%d\n",
            rate,pattern,out,bits(x),bits(y),memcmp(&a,&b,sizeof(a))); return 5;
        }
        ++comparisons; if(a.mid_w<old) ++wraps;
        if(a.in_nonzero==0 && a.mid_nonzero!=0) ++tails;
      }
    }
  printf("{\"outputs_and_full_states\":%u,\"mid_wraps\":%u,\"tail_states\":%u}\n",
    comparisons,wraps,tails);
}
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--compiler', default='c++')
    ap.add_argument('--opt', default='-O2')
    ap.add_argument('--sanitize', action='store_true')
    args = ap.parse_args()
    original = subprocess.check_output(['git', 'show', f'{BASE}:{HEADER}'], cwd=ROOT, text=True)
    candidate = (ROOT / HEADER).read_text()
    undefs = '\n'.join('#undef ' + name for name in
                       sorted(set(re.findall(r'^#define\s+(\w+)', original, re.M))))
    with tempfile.TemporaryDirectory(prefix='fm1-resampler-inline-') as tmp:
        directory = Path(tmp)
        for name, source in [('original', original), ('candidate', candidate)]:
            if sys.platform == 'darwin':
                source = source.replace('section(".ram_dsp")', 'section("__TEXT,__ram_dsp")')
            (directory / f'{name}.h').write_text(source)
        (directory / 'compare.cc').write_text(HARNESS.replace('UNDEFINES', undefs))
        flags = ['-std=c++11', args.opt, '-ffp-contract=off', '-DFM1_HOT_DSP_RAM=1',
                 '-D__ELF__=1', '-Wall', '-Wextra', '-Werror']
        if args.sanitize:
            flags += ['-fsanitize=address,undefined', '-fno-sanitize-recover=all']
        subprocess.run([args.compiler, *flags, str(directory / 'compare.cc'),
                        '-o', str(directory / 'compare')], check=True)
        subprocess.run([str(directory / 'compare')], check=True)


if __name__ == '__main__':
    main()
