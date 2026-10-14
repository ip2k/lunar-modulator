"""Exercise the actual native input loop with decoded USB-MIDI packets."""
import re
import shutil
import subprocess

import pytest

from tests.engine_helpers import ROOT


@pytest.fixture(scope="session")
def midi_loop(tmp_path_factory):
    compiler = shutil.which("cc")
    if not compiler:
        pytest.skip("no host C compiler")
    source = (ROOT / "firmware/native/app_probe.c").read_text()
    match = re.search(r"static void incoming_midi\(void\)\n\{.*?\n\}", source, re.S)
    assert match, "native input entry point changed"
    handler = re.search(
        r"static void apply_midi_event\([^\n]+\)\n\{.*?\n\}", source, re.S)
    assert handler, "shared MIDI event handler changed"
    directory = tmp_path_factory.mktemp("native-midi")
    harness = directory / "check.c"
    harness.write_text(r'''
#include <assert.h>
#include <stdlib.h>
#include "midi_input.h"
typedef struct { struct { uint8_t midi_in_channel; } settings; } App;
static App app;
static volatile uint32_t lunar_midi_usb_messages, lunar_midi_accepted_noteons;
static volatile uint32_t lunar_midi_rejected_messages;
static unsigned on, off, panic, bends, read_at, count;
static float bend;
static uint8_t messages[64][3];
static int midi_get(uint8_t *s, uint8_t *a, uint8_t *b) {
    if (read_at == count) return 0;
    *s=messages[read_at][0]; *a=messages[read_at][1]; *b=messages[read_at++][2];
    return 1;
}
static void fm1_app_note_on(App *a, int n, int v) {
    assert(a==&app && n==60 && v==100); ++on;
}
static void fm1_app_note_off(App *a, int n) {
    assert(a==&app && n==60); ++off;
}
static void fm1_app_all_notes_off(App *a) { assert(a==&app); ++panic; }
static void fm1_app_pitch_bend(App *a, float value) {
    assert(a==&app); bend=value; ++bends;
}
''' + handler.group() + '\n' + match.group() + r'''
static void send(uint8_t status, uint8_t a, uint8_t b) {
    read_at=0; count=1;
    messages[0][0]=status; messages[0][1]=a; messages[0][2]=b;
    incoming_midi(); assert(read_at==1);
}
int main(int argc, char **argv) {
    assert(argc==2); unsigned selected=(unsigned)atoi(argv[1]);
    assert(selected<16); app.settings.midi_in_channel=selected+1;
    for (unsigned c=0;c<16;++c) send(0x90+c,60,100);
    assert(on==1 && panic==0);
    send(0x90+selected,60,0); send(0x80+selected,60,0); assert(off==2);
    send(0xe0+selected,0,0); assert(bends==1 && bend==-2.0f);
    send(0xe0+selected,127,127); assert(bends==2 && bend>1.999f && bend<2.0f);
    send(0xb0+selected,123,0); send(0xb0+selected,120,0); assert(panic==2);
    for (unsigned s=0;s<256;++s) {
        unsigned family=s>>4;
        if (family!=8 && family!=9 && family!=11 && family!=14) send(s,60,100);
    }
    for (unsigned b=128;b<256;++b) {
        send(0x90+selected,60,b); send(0x90+selected,b,100);
    }
    assert(on==1 && off==2 && bends==2 && panic==2);
    app.settings.midi_in_channel=0;
    send(0x90+selected,60,100); assert(panic==3);
    for (unsigned c=0;c<16;++c) send(0x90+c,60,100);
    assert(on==18 && panic==3);
    count=64; read_at=0;
    for(unsigned i=0;i<64;++i) {
        messages[i][0]=0x90; messages[i][1]=60; messages[i][2]=100;
    }
    incoming_midi(); assert(read_at==32 && on==50);
    incoming_midi(); assert(read_at==64 && on==82);
    app.settings.midi_in_channel=17;
    send(0x90+selected,60,100); assert(on==82 && panic==4);
    return 0;
}
''')
    binary = directory / "check"
    subprocess.run([compiler, "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(ROOT / "firmware/native"), str(harness),
                    "-o", str(binary)], check=True)
    return binary


@pytest.mark.parametrize("channel", range(16))
def test_native_input_channel_routing_and_poll_budget(midi_loop, channel):
    subprocess.run([str(midi_loop), str(channel)], check=True)
