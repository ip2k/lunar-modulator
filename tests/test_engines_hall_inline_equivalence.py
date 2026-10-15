"""Bitwise output and complete-state parity for Hall's forced-inline helpers."""

from pathlib import Path
import shutil
import subprocess
import textwrap

import pytest


ROOT = Path(__file__).resolve().parents[1]
ENGINES = ROOT / "engines"


HARNESS = r"""
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

#include "fm1_engine.h"
#include "fx_hall.cc"

namespace {
struct Rng {
  uint32_t state;
  uint32_t Next() { state = state * 1664525u + 1013904223u; return state; }
  float Unit() { return static_cast<float>(Next() >> 8) * (1.0f / 16777216.0f); }
};

struct Event { uint32_t frame; uint16_t param; float value; };

float EdgeValue(const fm1_param_t &p, uint32_t n, Rng *rng) {
  switch (n % 9u) {
    case 0: return NAN;
    case 1: return INFINITY;
    case 2: return -INFINITY;
    case 3: return -1.0e30f;
    case 4: return 1.0e30f;
    case 5: return p.min;
    case 6: return p.max;
    case 7: return p.min + (p.max - p.min) * 0.5f;
    default: return p.min + (p.max - p.min) * rng->Unit();
  }
}

bool Write(const void *p, size_t n) { return std::fwrite(p, 1, n, stdout) == n; }

bool Run(float rate, uint32_t seed) {
  const fm1_engine_t &engine = fm1_engine_hall;
  fm1_host_t host = { FM1_ENGINE_API_VERSION, rate, 64 };
  const size_t bytes = engine.instance_size(&host);
  std::vector<unsigned char> allocation(bytes + 16, 0xa5);
  uintptr_t address = reinterpret_cast<uintptr_t>(&allocation[0]);
  size_t offset = (16u - (address & 15u)) & 15u;
  void *instance = engine.create(&allocation[offset], &host);
  if (!instance || bytes < 40000u) { std::fprintf(stderr, "create/size failure: %p %zu\n", instance, bytes); return false; }
  const uint32_t scenario[] = { 0x48414c4cu, seed, static_cast<uint32_t>(rate), static_cast<uint32_t>(bytes) };
  if (!Write(scenario, sizeof scenario)) return false;

  Rng rng = { seed };
  std::vector<Event> events;
  for (uint32_t i = 0; i < 45; ++i) {
    uint16_t param = static_cast<uint16_t>(i % engine.n_params);
    events.push_back(Event{ 113u + i * 613u, param,
                            EdgeValue(engine.params[param], i + seed, &rng) });
  }
  // Hit both sides of the control-update tick and long feedback periods.
  const uint32_t frames = 18000u;
  size_t next = 0;
  uint32_t pos = 0;
  uint32_t block_rng = seed ^ 0xb5297a4du;
  uint32_t next_snapshot = 4096u;
  uint32_t snapshots = 0;
  std::vector<float> block(128);
  while (pos < frames) {
    while (next < events.size() && events[next].frame <= pos) {
      engine.set_param(instance, events[next].param, events[next].value);
      ++next;
    }
    uint32_t n = 1u + (block_rng = block_rng * 1664525u + 1013904223u) % 64u;
    if (n > frames - pos) n = frames - pos;
    if (next_snapshot > pos && n > next_snapshot - pos) n = next_snapshot - pos;
    if (next < events.size() && events[next].frame > pos && n > events[next].frame - pos)
      n = events[next].frame - pos;
    for (uint32_t f = 0; f < n; ++f) {
      uint32_t x = rng.Next();
      float input = (static_cast<float>(x >> 8) * (1.0f / 16777216.0f) - 0.5f) * 1.75f;
      switch ((pos + f) % 8191u) {
        case 100: input = NAN; break;
        case 200: input = INFINITY; break;
        case 300: input = -INFINITY; break;
        case 400: input = 1.0e30f; break;
        default: break;
      }
      block[2u * f] = input;
      block[2u * f + 1u] = (pos + f) % 3u ? input : -0.5f * input;
    }
    engine.render(instance, block.data(), n);
    if (!Write(block.data(), 2u * n * sizeof(float))) return false;
    pos += n;
    if (pos == next_snapshot || pos == frames) {
      // Instance includes all scalar/filter/modulation state and both delay rings.
      if (!Write(instance, bytes)) return false;
      if (pos == next_snapshot) { ++snapshots; next_snapshot += 4096u; }
    }
  }
  if (snapshots != 4u) { std::fprintf(stderr, "snapshot failure: %u\n", snapshots); return false; }
  engine.destroy(instance);
  return true;
}
}  // namespace

int main() {
  if (!Run(44118.0f, 0x12345678u) || !Run(48000.0f, 0x87654321u) ||
      !Run(96000.0f, 0x0badc0deu)) return 2;
  return 0;
}
"""


@pytest.mark.parametrize("optimization", ["-O0", "-O2"])
def test_forced_inline_matches_noinline_output_and_full_state(optimization, tmp_path):
    compiler = shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        pytest.skip("a C++ compiler is required for the Hall equivalence harness")
    harness = tmp_path / "hall_inline_equivalence.cc"
    harness.write_text(textwrap.dedent(HARNESS))
    outputs = {}
    for mode, define in (("reference", "-DFM1_HALL_TEST_NOINLINE_HELPERS=1"),
                         ("inline", None)):
        exe = tmp_path / f"hall-{mode}"
        command = [compiler, "-std=c++11", optimization, "-fno-fast-math",
                   "-ffp-contract=off", "-I", str(ENGINES / "include"),
                   "-I", str(ENGINES / "src")]
        if define:
            command.append(define)
        command += [str(harness), "-o", str(exe)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        result = subprocess.run([str(exe)], check=True, capture_output=True)
        outputs[mode] = result.stdout
    assert len(outputs["inline"]) > 100_000
    assert outputs["inline"] == outputs["reference"], "rendered samples or full instance bytes differ"


@pytest.mark.parametrize("optimization", ["-O0", "-O2"])
def test_cached_gain_delta_matches_original_output_and_full_state(optimization, tmp_path):
    compiler = shutil.which("clang++") or shutil.which("g++")
    if not compiler:
        pytest.skip("a C++ compiler is required for the Hall equivalence harness")

    harness_text = textwrap.dedent(HARNESS)
    # Include explicit silent spans and resumed signal while retaining the
    # existing randomized parameter transitions, edge values, rates and tails.
    harness_text = harness_text.replace(
        """      switch ((pos + f) % 8191u) {
""",
        """      const uint32_t cycle = (pos + f) % 4096u;
      if (cycle >= 2048u && cycle < 3072u) input = 0.0f;
      switch ((pos + f) % 8191u) {
""",
    )
    # The only expected state difference is the intentionally repurposed
    # gain_lo cache. Zero it only while writing each snapshot, then restore it
    # so the reference and candidate continue from their real state.
    harness_text = harness_text.replace(
        """      // Instance includes all scalar/filter/modulation state and both delay rings.
      if (!Write(instance, bytes)) return false;
""",
        """      // Compare all instance bytes except the repurposed gain cache.
      fm1::hall::Instance *hall = static_cast<fm1::hall::Instance *>(instance);
      float cached_gain[8];
      std::memcpy(cached_gain, hall->gain_lo, sizeof cached_gain);
      std::memset(hall->gain_lo, 0, sizeof hall->gain_lo);
      const bool wrote_state = Write(instance, bytes);
      std::memcpy(hall->gain_lo, cached_gain, sizeof cached_gain);
      if (!wrote_state) return false;
""",
    )
    assert "const uint32_t cycle" in harness_text
    assert "memcpy(hall->gain_lo" in harness_text
    harness = tmp_path / "hall_gain_delta_equivalence.cc"
    harness.write_text(harness_text)

    outputs = {}
    variants = (
        ("reference", "-DFM1_HALL_TEST_GAIN_DELTA_REFERENCE=1"),
        ("cached", None),
    )
    for mode, define in variants:
        exe = tmp_path / f"hall-gain-delta-{mode}"
        command = [compiler, "-std=c++11", optimization, "-fno-fast-math",
                   "-ffp-contract=off", "-I", str(ENGINES / "include"),
                   "-I", str(ENGINES / "src")]
        if define:
            command.append(define)
        command += [str(harness), "-o", str(exe)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        result = subprocess.run([str(exe)], check=True, capture_output=True)
        outputs[mode] = result.stdout
    assert len(outputs["cached"]) > 100_000
    assert outputs["cached"] == outputs["reference"], (
        "rendered samples or normalized full instance bytes differ"
    )
