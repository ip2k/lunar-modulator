# engines/ — the FM-1 engine platform, stage A

Swappable sound engines behind one C API, built and tested on a desktop first
(docs/11 §8, stage A). Nothing here runs on the FM-1 yet. The same sources are
meant to build with JieLi's toolchain for the AC79 dev board (stage B) and,
later, the FM-1.

```bash
make -C engines                                  # build/fm1-render
engines/build/fm1-render --list                  # engines and parameters (JSON)
engines/build/fm1-render --engine macro --param Model=4 \
    --note 0:57:100:1 --note 0:60:100:1 --note 0:64:100:1 \
    --seconds 2 --out chord.wav                  # A minor, "VA Pair"
python -m pytest tests/test_engines.py           # 69 tests
```

## Layout

| Path | What |
| --- | --- |
| `include/fm1_engine.h` | The engine API. C, no heap: the host asks `instance_size`, provides that memory, and the engine constructs itself in it. Typed parameters, four to a page (the FM-1 has four free parameter knobs) |
| `include/fm1_mix_limiter.h` | The host's mix-bus limiter. Twelve voices started in phase can exceed full scale; the bus holds the output under 0.98 |
| `src/registry.cc` | The static engine registry (tier 0 in docs/11 §5.2) |
| `src/mi_macro.cc` | **Macro**: 12-voice engine from Plaits' light engines (VA+Filter, PhaseDist, Terrain, Chip, VA Pair, Shaper, 2-op FM, Wavetable) with Plaits' own decay envelope, low-pass gate and post-processor |
| `src/mi_shapes.cc` | **Shapes**: 12-voice engine from Braids' macro-oscillator (all 47 shapes reachable from Braids' META mode), fixed point, with an attack/release envelope |
| `src/test_sine.cc` | **Test Sine**: a plain sine engine used to test the host and the analysis |
| `host/render.cc` | `fm1-render`: plays a note script through an engine in 64-frame blocks at 44,118 Hz, applies the bus limiter, writes a WAV, prints JSON |
| `third_party/mutable/` | Mutable Instruments code, MIT, unmodified; see `UPSTREAM.md` |

Build flags match the FM-1 toolchain profile: `-std=c++11 -fno-exceptions
-fno-rtti`. CI builds and tests on Linux and macOS, and builds a 32-bit
(`-m32`) binary on Linux to catch pointer-size assumptions before pi32v2 does.

## What stage A has found so far

- **Tuning survives the rate change.** Both Mutable engines stay within
  ±5 cents at A2, A4 and A6 at 44,118 Hz without touching their sources.
- **Memory per 12 voices, 64-bit desktop:**
  - Macro is about 30 KB. On 32-bit it should be about 18 KB, because most
    of the arena is pointer tables.
  - Shapes is **206 KB**. Each Braids `MacroOscillator` carries about 17 KB
    of state for its physical models, too much for 12 voices on the FM-1.
    Either cap Shapes at 4–6 voices there, or give the physical-model shapes
    a separate, smaller engine.
- **One upstream bug:** Plaits' `WavetableEngine` writes past its arena
  allocation (`third_party/mutable/UPSTREAM.md`).
- **Relative cost, desktop only** (Apple M1 Max, 12 voices held, share of
  the 1.451 ms block):

  | Engine | Share of block |
  | --- | --- |
  | Macro, most models | 1.0–1.8 % |
  | Macro, 2-op FM | 4.9 % |
  | Shapes | 0.2–0.6 % |

  pi32v2 is a much narrower core and these figures do not transfer. What
  they do say is that 2-op FM will need a lower voice cap than its siblings,
  and that Braids is cheap in CPU even though it is heavy in RAM. Stage B
  measures the real numbers.

## Next in stage A

- A Schwung v2 shim (docs/11 §3) and two MIT Schwung modules built through it.
- Heavier Plaits engines (string, modal, particle, six-op) as their own
  engines with lower voice caps.
- Mutable's effects (reverb, chorus, ensemble) as the first audio-FX engines.
