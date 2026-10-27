"""Actual bounded UART parser: noise must not request a ROM transition."""
from pathlib import Path
import subprocess
import importlib.util
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_command_stream(tmp_path):
    harness = tmp_path/'main.c'
    harness.write_text(r'''
#include "boot_command.h"
#include <assert.h>
#include <string.h>
static enum lunar_boot_action line(struct lunar_boot_command *s,
                                   const char *text, uint32_t now) {
    enum lunar_boot_action a = LUNAR_BOOT_NONE;
    while (*text) {
        a = lunar_boot_command_feed(s, (unsigned char)*text++, now);
        if (*text) assert(a == LUNAR_BOOT_NONE);
    }
    return a;
}
int main(void) {
    struct lunar_boot_command s = {0};
    unsigned i;
    assert(line(&s, "LUNAR ENTER UBOOT\n", 0) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR PING\r\n", 0) == LUNAR_BOOT_PONG);
    assert(line(&s, "LUNAR ARM UBOOT\n", 1) == LUNAR_BOOT_ARMED);
    assert(line(&s, "LUNAR ENTER UBOOT\n", 5000) == LUNAR_BOOT_ENTER);
    assert(line(&s, "LUNAR ENTER UBOOT\n", 5001) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR ARM UBOOT\n", 10000) == LUNAR_BOOT_ARMED);
    assert(line(&s, "LUNAR ENTER UBOOT\n", 15000) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR ARM UBOOT\n", UINT32_MAX - 10) == LUNAR_BOOT_ARMED);
    assert(line(&s, "LUNAR ENTER UBOOT\n", 100) == LUNAR_BOOT_ENTER);
    assert(line(&s, "LUNAR ARM UBOOT\n", 200) == LUNAR_BOOT_ARMED);
    assert(line(&s, "garbage\n", 201) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR ENTER UBOOT\n", 202) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR ARM UBOOT\n", 300) == LUNAR_BOOT_ARMED);
    assert(lunar_boot_command_feed(&s, 0, 301) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR ENTER UBOOT\n", 302) == LUNAR_BOOT_NONE);
    /* Overflow cannot turn a suffix into a command. Recover only at newline. */
    for (i = 0; i < 1000; ++i)
        assert(lunar_boot_command_feed(&s, 'x', 400) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR ARM UBOOT\n", 401) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR ENTER UBOOT\n", 402) == LUNAR_BOOT_NONE);
    assert(line(&s, "LUNAR PING\n", 403) == LUNAR_BOOT_PONG);
    /* Deterministic binary noise, including all possible bytes and long runs. */
    for (i = 0; i < 100000; ++i)
        assert(lunar_boot_command_feed(&s, (unsigned char)(i * 17), i + 500)
               != LUNAR_BOOT_ENTER);
    return 0;
}
''')
    binary = tmp_path/'test'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-I'+str(ROOT/'firmware/devkit'),
                    str(harness), str(ROOT/'firmware/devkit/boot_command.c'),
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)


def test_host_handshake_and_default_no_reset():
    spec = importlib.util.spec_from_file_location('boot_control', ROOT/'tools/devkit_boot_control.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class UART:
        def __init__(self):
            self.sent = []
            self.reply = b''

        def write(self, data):
            self.sent.append(data)
            self.reply = {b'LUNAR PING\n': b'LUNAR_CONTROL pong=1\n',
                          b'LUNAR ARM UBOOT\n': b'LUNAR_CONTROL armed=1\n',
                          b'LUNAR ENTER UBOOT\n': b'LUNAR_CONTROL entering=uboot\n'}[data]

        def flush(self): pass
        def read_until(self, *args): return self.reply

    uart = UART()
    module.exchange(uart)
    assert uart.sent == [b'LUNAR PING\n']
    uart = UART()
    module.exchange(uart, enter=True)
    assert uart.sent == [b'LUNAR PING\n', b'LUNAR ARM UBOOT\n', b'LUNAR ENTER UBOOT\n']
    uart = UART()
    with pytest.raises(RuntimeError, match='acknowledgment'):
        module.exchange(uart, enter=True, timeout=0)
    assert uart.sent == [b'LUNAR PING\n']  # Never ARM/ENTER without a response.
