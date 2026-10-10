"""Large native imports must not look empty after modifying the user bank."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def reader(tmp_path_factory):
    compiler = shutil.which("c++")
    if not compiler:
        pytest.skip("no C++ compiler")
    work = tmp_path_factory.mktemp("dx7-counts")
    source = work / "check.cc"
    source.write_text(r'''
#include "fm1_dx7.h"
#include <cassert>
#include <cstring>
#include <string>
#include <vector>
struct Stores { unsigned count = 0, last_slot = 99; uint8_t last_name = 0; };
static void store(void *ctx, unsigned slot, const uint8_t *voice) {
  Stores &s = *static_cast<Stores *>(ctx);
  ++s.count; s.last_slot = slot; s.last_name = voice[145];
}
int main(int argc, char **argv) {
  assert(argc == 2);
  const std::string mode(argv[1]);
  std::vector<uint8_t> message;
  unsigned repeats = 65537, expected_stores = 0;
  uint8_t voice[FM1_DX7_VCED_BYTES] = {};
  std::memset(voice + 145, 'A', FM1_DX7_NAME_BYTES);
  if (mode == "bank") {
    message.resize(FM1_DX7_BANK_SYSEX_BYTES);
    const uint8_t *voices[FM1_DX7_USER_SLOTS];
    for (unsigned i = 0; i < FM1_DX7_USER_SLOTS; ++i) voices[i] = voice;
    fm1_dx7_write_bank(voices, 0, message.data());
    repeats = 2048; expected_stores = 65536;
  } else if (mode == "voice") {
    message.resize(FM1_DX7_VOICE_SYSEX_BYTES);
    fm1_dx7_write_voice(voice, 0, message.data());
    message[message.size() - 2] ^= 1; // count accepted bad checksums too
    expected_stores = repeats;
  } else if (mode == "foreign") message = {0xf0, 0x01, 0xf7};
  else if (mode == "truncated") message = {0xf0};
  else if (mode == "wrong") message = {0xf0, 0x43, 0, 0, 0, 0, 0, 0xf7};
  else return 2;
  std::vector<uint8_t> data;
  data.reserve(message.size() * repeats + FM1_DX7_VOICE_SYSEX_BYTES);
  for (unsigned i = 0; i < repeats; ++i)
    data.insert(data.end(), message.begin(), message.end());
  if (mode == "bank") {
    Stores exact;
    fm1_dx7_sysex_result_t exact_result;
    assert(fm1_dx7_read_sysex(data.data(), data.size(), 7, store, &exact,
                             &exact_result) == 65535);
    assert(exact.count == 65536 && exact_result.messages == 2048);
  }
  if (expected_stores) {
    // The last voice must still store after report saturation.
    voice[145] = 'Z';
    uint8_t final_voice[FM1_DX7_VOICE_SYSEX_BYTES];
    fm1_dx7_write_voice(voice, 0, final_voice);
    data.insert(data.end(), final_voice, final_voice + sizeof(final_voice));
    ++expected_stores;
  }
  Stores stores;
  fm1_dx7_sysex_result_t result;
  const int n = fm1_dx7_read_sysex(data.data(), data.size(), 7, store, &stores, &result);
  assert(stores.count == expected_stores);
  assert(n == (expected_stores ? 65535 : 0));
  assert(result.voices == n);
  if (expected_stores) {
    assert(stores.last_name == 'Z');
    assert(stores.last_slot == (mode == "bank" ? 7u : 8u));
    assert(result.messages == (mode == "bank" ? 2049 : 65535));
    assert(result.bad_checksums == (mode == "bank" ? 0 : 65535));
    assert(result.skipped == 0);
  } else {
    assert(result.skipped == 65535);
    assert(result.foreign == (mode == "foreign" ? 65535 : 0));
    assert(result.truncated == (mode == "truncated" ? 65535 : 0));
    assert(result.wrong_size == (mode == "wrong" ? 65535 : 0));
  }
  // Small imports retain their exact counts and normal slot mapping.
  Stores small;
  fm1_dx7_read_sysex(message.data(), message.size(), 7, store, &small, &result);
  assert(small.count == (mode == "bank" ? 32u : mode == "voice" ? 1u : 0u));
  assert(result.voices == small.count);
  assert(result.skipped == (expected_stores ? 0 : 1));
  return 0;
}
''')
    binary = work / "check"
    command = [compiler, "-std=c++11", "-O1", "-g", "-fno-exceptions", "-fno-rtti",
               "-I", str(ROOT / "engines/include"), "-I", str(ROOT / "engines/src"),
               "-I", str(ROOT / "engines/third_party/msfa"),
               '-DFM1_MSFA_UNIT="patch.cc"', str(source),
               str(ROOT / "engines/src/dx7_voice.cc"),
               str(ROOT / "engines/src/msfa_unit.cc"), "-o", str(binary)]
    if os.environ.get("FM1_COUNTER_SANITIZE"):
        command[1:1] = ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
    subprocess.run(command, check=True, capture_output=True, text=True)
    return binary


@pytest.mark.parametrize("mode", ["bank", "voice", "foreign", "truncated", "wrong"])
def test_large_import_counters_saturate_without_stopping(reader, mode):
    subprocess.run([str(reader), mode], check=True, timeout=30)
