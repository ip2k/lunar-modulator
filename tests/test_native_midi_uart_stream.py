"""Host tests for the bounded UART DMA-ring to maintained MIDI parser adapter."""
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.engine_helpers import ROOT
from tests.native_test_flags import native_no_pie_flags


@pytest.fixture(scope="session")
def uart_stream_check(tmp_path_factory):
    compiler = shutil.which("c++")
    c_compiler = shutil.which("cc")
    if not compiler or not c_compiler:
        pytest.skip("C and C++ compilers are required")
    out = tmp_path_factory.mktemp("midi-uart-stream")
    source = out / "check.cpp"
    source.write_text(r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "midi_stream.h"
#include "midi_uart_stream.h"
static uint8_t status[8], data1[8], data2[8];
static unsigned events;
static void emit(void *, uint8_t s, uint8_t a, uint8_t b) {
    assert(events < 8); status[events]=s; data1[events]=a; data2[events]=b; ++events;
}
int main() {
    volatile uint8_t ring[8] = {};
    uint32_t cursor=0, pending=0;
    lunar_midi_stream_reset();
    ring[0]=0x92; ring[1]=60; ring[2]=100; ring[3]=61; ring[4]=110;
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,5,2,emit,0)==2);
    assert(events==0 && cursor==2 && pending==3);
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,0,2,emit,0)==2);
    assert(events==1 && status[0]==0x92 && data1[0]==60 && data2[0]==100);
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,0,2,emit,0)==1);
    assert(events==2 && data1[1]==61 && data2[1]==110 && pending==0);

    /* A message may cross the ring boundary while retaining running status. */
    cursor=6; ring[6]=0x90; ring[7]=64; ring[0]=90;
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,3,8,emit,0)==3);
    assert(events==3 && status[2]==0x90 && data1[2]==64 && data2[2]==90);

    /* Overrun discards queued bytes and resets parser state before resync. */
    ring[1]=0x90; ring[2]=65; ring[3]=0x90; ring[4]=67; ring[5]=100;
    cursor=1;
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,2,8,emit,0)==2);
    assert(events==3);
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,9,8,emit,0)==-1);
    assert(pending==0);
    ring[cursor]=100;
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,1,8,emit,0)==1);
    assert(events==3); /* no partial pre-overrun event */
    ring[cursor]=0x90; ring[(cursor+1)%8]=67; ring[(cursor+2)%8]=100;
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,3,8,emit,0)==3);
    assert(events==4 && status[3]==0x90 && data1[3]==67 && data2[3]==100);

    /* Previously queued bytes also advance the DMA head on overflow. */
    cursor=0; pending=5;
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,4,8,emit,0)==-1);
    assert(cursor==1 && pending==0);
    /* Put a complete fresh event at the real head, with stale bytes elsewhere. */
    ring[1]=0x91; ring[2]=70; ring[3]=99;
    ring[4]=ring[5]=ring[6]=0;
    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,3,8,emit,0)==3);
    assert(events==5 && status[4]==0x91 && data1[4]==70 && data2[4]==99);

    /* Realtime transport is emitted in order without clearing running status. */
    lunar_midi_stream_reset(); cursor=0; pending=0; events=0;
    const uint8_t interleaved[] = {
        0x92,60,100,0xfa,61,110,0xfb,0xf8,62,120,0xfc
    };
    for (unsigned i=0; i<sizeof interleaved; ++i) {
        ring[cursor]=interleaved[i];
        assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,1,1,emit,0)==1);
    }
    assert(events==6);
    assert(status[0]==0x92 && data1[0]==60 && data2[0]==100);
    assert(status[1]==0xfa);
    assert(status[2]==0x92 && data1[2]==61 && data2[2]==110);
    assert(status[3]==0xfb);
    assert(status[4]==0x92 && data1[4]==62 && data2[4]==120);
    assert(status[5]==0xfc);

    assert(lunar_midi_uart_drain(ring,8,&cursor,&pending,0,1,0,0)==-1);
    return 0;
}
''')
    helper_obj = out / "midi_uart_stream.o"
    subprocess.run([c_compiler, "-std=c99", "-Wall", "-Wextra", "-Werror",
                    "-I", str(ROOT / "firmware/native"), "-c",
                    str(ROOT / "firmware/native/midi_uart_stream.c"), "-o",
                    str(helper_obj)], check=True)
    binary = out / "check"
    subprocess.run([compiler, "-std=c++11", "-O1", "-g", "-Wall", "-Wextra",
                    "-Werror", "-fno-exceptions", "-fno-rtti",
                    *native_no_pie_flags(),
                    "-I" + str(ROOT / "firmware/native"),
                    "-I" + str(ROOT / "firmware/third_party/arduino-midi/src"),
                    str(source), str(ROOT / "firmware/native/midi_stream.cpp"),
                    str(helper_obj), "-o", str(binary)], check=True)
    return binary


def test_uart_ring_adapter_bounds_wrap_and_resynchronizes(uart_stream_check):
    subprocess.run([str(uart_stream_check)], check=True)
