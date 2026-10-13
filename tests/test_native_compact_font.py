"""Compare the actual HAL glyph renderer before/after lossless packing."""
import importlib.util
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / 'firmware/third_party/dinghy'
spec = importlib.util.spec_from_file_location('compact_font', ROOT / 'tools/native/compact_font.py')
font = importlib.util.module_from_spec(spec)
spec.loader.exec_module(font)


@pytest.mark.parametrize('chunk', range(16))
def test_original_and_packed_pixels_match(tmp_path, chunk):
    compiler = shutil.which('cc')
    if not compiler:
        pytest.skip('C compiler required')
    header = (PLATFORM / 'gen/felucca_font.h').read_text()
    gfx = (PLATFORM / 'src/gfx.c').read_text()
    harness = '''#include <stdint.h>
#include <stdio.h>
static void lcd_sync(void) {}
static void lcd_blit(uint32_t x,uint32_t y,uint32_t w,uint32_t h,const uint16_t *p) {}
#include "gfx.c"
int main(void) {
  const uint16_t colors[] = {0,1,0x1234,0x7bef,0xffff,0xf800,0x07e0,0x001f};
  for (int face=0;face<2;face++)
    for (int ch=CHUNK;ch<256;ch+=16)
      for (unsigned c=0;c<8;c++)
        for(int clip=0;clip<3;clip++) {
          char text[2]={(char)ch,0};
          cv_begin(80,40,0x3186);
          cv_text(clip==0?-3:clip==1?75:8,clip==0?-4:clip==1?35:2,
                  face?&FONT_L:&FONT_S,text,colors[c]);
          if(fwrite(cv_px,sizeof(uint16_t),80*40,stdout)!=80*40)return 2;
        }
  return 0;
}
'''.replace('CHUNK', str(chunk))
    outputs = []
    for packed in (False, True):
        directory = tmp_path / str(packed)
        directory.mkdir()
        (directory / 'felucca_font.h').write_text(font.compact_header(header) if packed else header)
        (directory / 'gfx.c').write_text(font.compact_gfx(gfx) if packed else gfx)
        (directory / 'test.c').write_text(harness)
        binary = directory / 'test'
        subprocess.run([compiler, '-std=c99', '-O2', str(directory / 'test.c'),
                        '-o', str(binary)], check=True, capture_output=True)
        outputs.append(subprocess.check_output([str(binary)]))
    assert outputs[0] == outputs[1]


def test_rejects_changed_alpha_and_decoder():
    header = (PLATFORM / 'gen/felucca_font.h').read_text()
    with pytest.raises(ValueError, match='non-binary'):
        font.compact_header(header.replace('0x0f', '0x0e', 1))
    with pytest.raises(ValueError, match='decoder'):
        font.compact_gfx('changed upstream')
