"""Bounded jack-stream adapter using the pinned upstream MIDI parser."""
import shutil
import subprocess

import pytest
from tests.engine_helpers import ROOT


@pytest.fixture(scope="session")
def stream_check(tmp_path_factory):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("no C++ compiler")
    directory = tmp_path_factory.mktemp("midi-stream")
    source = directory / "check.cpp"
    source.write_text(r'''
#include <assert.h>
#include <stdlib.h>
#include "midi_stream.h"
static uint8_t s,a,b;
static int feed(unsigned byte) { return lunar_midi_stream_feed(byte,&s,&a,&b); }
int main(int argc,char **argv) {
    assert(argc==2); unsigned c=atoi(argv[1]); assert(c<16);
    lunar_midi_stream_reset();
    for(unsigned d=0;d<128;++d) assert(!feed(d));
    assert(!feed(0x90+c)); assert(!feed(60)); assert(!feed(0xf8));
    assert(feed(100)); assert(s==0x90+c && a==60 && b==100);
    assert(!feed(61)); assert(!feed(0xfe)); assert(feed(110));
    assert(s==0x90+c && a==61 && b==110);
    assert(!feed(60)); assert(feed(0)); assert(s==0x80+c && a==60 && b==0);
    assert(!feed(0xb0+c)); assert(!feed(64)); assert(feed(127));
    assert(s==0xb0+c && a==64 && b==127);
    assert(!feed(0xe0+c)); assert(!feed(0)); assert(feed(64));
    assert(s==0xe0+c && a==0 && b==64);
    assert(!feed(0xc0+c)); assert(feed(7)); assert(s==0xc0+c && a==7);
    assert(feed(8)); assert(s==0xc0+c && a==8);
    assert(!feed(0xf0));
    for(unsigned i=0;i<4096;++i) { assert(!feed(i%128)); if(i%17==0)assert(!feed(0xf8)); }
    assert(!feed(0xf7));
    for(unsigned d=0;d<128;++d) assert(!feed(d));
    assert(!feed(0x90+c)); assert(!feed(60)); assert(feed(100));
    assert(!feed(61)); lunar_midi_stream_reset(); assert(!feed(100));
    assert(!feed(0x90+c)); assert(!feed(60)); assert(!feed(0x80+c));
    assert(!feed(60)); assert(feed(0)); assert(s==0x80+c && a==60);
    for(unsigned i=0;i<100000;++i) feed((i*37u+19u)&255u);
    lunar_midi_stream_reset();
    assert(!feed(0x90+c)); assert(!feed(60)); assert(feed(100));
    assert(s==0x90+c && a==60 && b==100);
    assert(!lunar_midi_stream_feed(0x90+c,0,&a,&b));
    return 0;
}
''')
    binary = directory / "check"
    subprocess.run([compiler, "-std=c++11", "-O2", "-Wall", "-Wextra",
                    "-fno-exceptions", "-fno-rtti", "-fsanitize=address,undefined",
                    "-fno-pie", "-no-pie",
                    "-I" + str(ROOT / "firmware/native"),
                    "-I" + str(ROOT / "firmware/third_party/arduino-midi/src"),
                    str(source), str(ROOT / "firmware/native/midi_stream.cpp"),
                    "-o", str(binary)], check=True)
    return binary


@pytest.mark.parametrize("channel", range(16))
def test_jack_stream_running_status_realtime_and_resync(stream_check, channel):
    subprocess.run([str(stream_check), str(channel)], check=True)
