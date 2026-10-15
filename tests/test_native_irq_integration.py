"""Exercise the production schema-6 C encoder against the host decoder."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from tools.native import diagnostic_telemetry as codec


ROOT = Path(__file__).resolve().parents[1]


def test_schema6_irq_encoder_roundtrips_through_host_decoder(tmp_path):
    compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
    if compiler is None:
        pytest.skip("a C compiler is required for the native telemetry harness")

    source = tmp_path / "irq_wire.c"
    source.write_text(
        r'''
#include "diagnostic_telemetry.h"
#include <assert.h>
#include <stdio.h>

int main(void) {
    const uint32_t values[LUNAR_IRQ_FIELDS] = {
        0u, 1u, 127u, 128u, 16383u, 16384u, 0x0fffffffu,
        0x10000000u, 0x7fffffffu, 0x80000000u, UINT32_MAX,
        24000u, 0x12345678u, 0x87654321u, 0xabcdef01u,
        0x01020304u, 0xfedcba98u, 17u, 0x80000001u,
        0xffffffffu, 0x00008000u, 0u
    };
    assert(LUNAR_IRQ_BYTES == 119u);
    assert(LUNAR_IRQ_PACKETS == 40u);
    assert(LUNAR_IRQ_PACKETS <= 64u);
    for (unsigned i = 0; i < LUNAR_IRQ_PACKETS; ++i) {
        uint32_t packet = lunar_irq_packet(values, i);
        unsigned cin = packet & 15u;
        unsigned n = cin == 4u ? 3u : cin - 4u;
        assert(i + 1u == LUNAR_IRQ_PACKETS ? cin == 6u : cin == 4u);
        for (unsigned j = 0; j < n; ++j)
            putchar((packet >> (8u * (j + 1u))) & 255u);
        if (n < 3u) assert((packet >> (8u * (n + 1u))) == 0u);
    }
    assert(lunar_irq_packet(values, LUNAR_IRQ_PACKETS) == 0u);
    return 0;
}
''',
        encoding="utf-8",
    )
    executable = tmp_path / "irq_wire"
    command = [
        compiler,
        "-std=c99",
        "-Wall",
        "-Wextra",
        "-Werror",
        "-fsanitize=address,undefined",
        "-I",
        str(ROOT / "firmware/native"),
        "-I",
        str(ROOT / "sim/web/src"),
        str(source),
        "-o",
        str(executable),
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)
    wire = subprocess.check_output([str(executable)])

    assert len(wire) == codec.IRQ_PROFILE_FRAME_BYTES == 119
    schema, decoded = codec.decode_any_frame(wire)
    expected = {
        name: value
        for name, value in zip(
            codec.IRQ_PROFILE_FIELDS,
            (
                0,
                1,
                127,
                128,
                16383,
                16384,
                0x0FFFFFFF,
                0x10000000,
                0x7FFFFFFF,
                0x80000000,
                0xFFFFFFFF,
                24000,
                0x12345678,
                0x87654321,
                0xABCDEF01,
                0x01020304,
                0xFEDCBA98,
                17,
                0x80000001,
                0xFFFFFFFF,
                0x00008000,
                0,
            ),
        )
    }
    assert schema == 6
    assert decoded == expected
    assert codec.decode_capture(wire)[0] == {"schema": 6, "values": expected}

