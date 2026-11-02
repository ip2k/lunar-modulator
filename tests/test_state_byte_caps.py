"""Complete JSON byte caps, including whitespace and inflated launch links.

The C parity fixture builds only the four small codec translation units; no
renderer, engine registry, target compiler or device is involved.
"""
import base64
import json
from pathlib import Path
import shutil
import subprocess
import zlib

import pytest

from tools import lunar_state as ls

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = {
    "settings": {"settings": {}},
    "fx": {"chain": []},
    "mods": {"mod": {"seed": 1, "rack": [], "cables": []}},
    "project": {"sounds": [{"engine": "unknown"}, None, None, None]},
}


@pytest.fixture(scope="module")
def names():
    return ls.Names({"kind": "metadata", "engines": [], "known_ids": [],
                     "mod": {"kinds": [], "sources": [], "host": []}})


@pytest.fixture(scope="module")
def c_reader(tmp_path_factory):
    cc = shutil.which("cc")
    if not cc:
        pytest.skip("C byte-cap parity requires a host C compiler")
    stage = tmp_path_factory.mktemp("state-byte-cap-c")
    source = stage / "reader.c"
    source.write_text(r'''
#include "fm1_state.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned char data[FM1_STATE_CAP_PROJECT + 1];
static size_t length, piece;
static uint32_t read_bytes(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
  (void)ctx;
  if (off >= length) return 0;
  if (n > piece) n = (uint32_t)piece;
  if (n > length - off) n = (uint32_t)(length - off);
  memcpy(out, data + off, n);
  return n;
}
static int sink(void *ctx, const fm1_rec_t *rec) {
  (void)ctx; (void)rec; return 1;
}
int main(int argc, char **argv) {
  fm1_state_report_t report;
  piece = argc == 2 ? (size_t)strtoul(argv[1], NULL, 10) : 256;
  if (!piece) return 2;
  length = fread(data, 1, sizeof(data), stdin);
  if (ferror(stdin)) return 2;
  fm1_state_report_init(&report);
  int ok = fm1_state_json_read(NULL, read_bytes, NULL, sink, NULL, &report);
  puts(ok ? "OK" : fm1_state_code_name(report.code));
  return 0;
}
''')
    binary = stage / "reader"
    codec = ROOT / "engines/state"
    subprocess.run([cc, "-std=c99", "-O0", "-I" + str(codec),
                    "-I" + str(ROOT / "engines/include"), str(source),
                    *(str(codec / f) for f in ("fm1_json.c", "fm1_num.c",
                                               "state_names.c", "state_json_read.c")),
                    "-o", str(binary)], check=True, capture_output=True, timeout=30)
    return binary


def document(kind, size=None):
    # Unknown Unicode metadata is valid and skipped, but its UTF-8 bytes count.
    text = json.dumps({"lunar": "1.0", "kind": kind, "extra": "é🛰",
                       **DOCUMENTS[kind]}, ensure_ascii=False, separators=(",", ":"))
    raw = text.encode("utf-8")
    if size is not None:
        assert size >= len(raw)
        padding = b" \t\r\n" * ((size - len(raw) + 3) // 4)
        raw += padding[:size - len(raw)]
    return raw


def code(read):
    try:
        read()
        return "OK"
    except ls.Refused as exc:
        return exc.code


def fragment(raw):
    compressor = zlib.compressobj(wbits=-15)
    compressed = compressor.compress(raw) + compressor.flush()
    return "#lunar=" + base64.urlsafe_b64encode(compressed).rstrip(b"=").decode("ascii")


@pytest.mark.parametrize("kind", DOCUMENTS)
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_json_byte_boundary_matches_c(c_reader, names, kind, delta):
    raw = document(kind, ls.KIND_CAP[ls.KINDS.index(kind)] + delta)
    expected = "TOO_BIG" if delta > 0 else "OK"
    for piece in (1, 7, 256):
        result = subprocess.run([str(c_reader), str(piece)], input=raw,
                                check=True, capture_output=True, timeout=10)
        assert result.stdout.decode().strip() == expected
    # A str input must be measured after encoding, not by character count.
    assert len(raw.decode("utf-8")) < len(raw)
    for value in (raw, raw.decode("utf-8")):
        assert code(lambda: ls.read_json(value, names)) == expected
    if expected == "OK":
        assert ls.read_json(raw, names)[0] == ls.read_json(document(kind), names)[0]


@pytest.mark.parametrize("kind", DOCUMENTS)
@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_inflated_link_obeys_selected_json_byte_cap(names, kind, delta):
    raw = document(kind, ls.KIND_CAP[ls.KINDS.index(kind)] + delta)
    link = fragment(raw)
    assert len(link.removeprefix("#lunar=")) < ls.LINK_CAP
    assert code(lambda: ls.read_link(link, names)) == ("TOO_BIG" if delta > 0 else "OK")
    if delta <= 0:
        assert ls.read_link(link, names)[0] == ls.read_json(document(kind), names)[0]


def test_global_cap_refuses_before_json_parse(names, monkeypatch):
    monkeypatch.setattr(ls, "_parse", lambda *_: pytest.fail("must refuse before parsing"))
    with pytest.raises(ls.Refused) as error:
        ls.read_json(b" " * (ls.KIND_CAP[1] + 1), names)
    assert error.value.code == "TOO_BIG"


def test_valid_canonical_links_still_round_trip(names):
    for kind in DOCUMENTS:
        records, _ = ls.read_json(document(kind), names)
        canonical, _ = ls.write_json(records, names)
        records, _ = ls.read_json(canonical, names)  # writer fills document defaults
        assert ls.write_json(records, names)[0] == canonical
        assert ls.read_link(ls.link_fragment(records, names), names)[0] == records


@pytest.mark.parametrize("extra", [b"trailing", b"\0"])
def test_link_trailing_compressed_data_still_refused(names, extra):
    link = fragment(document("settings"))
    raw = base64.urlsafe_b64decode(link[7:] + "=" * (-len(link[7:]) % 4)) + extra
    link = "#lunar=" + base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    assert code(lambda: ls.read_link(link, names)) == "BAD"
