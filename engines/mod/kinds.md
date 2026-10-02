# engines/mod/kinds — the glue modules (docs/16 stage MG2)

Thirteen module kinds join MG1's LFO, Envelope and Chance
([README.md](README.md#the-kinds)): the twelve of docs/16 §8's MG2 and a
**Filter** the owner asked for on 2026-10-02. They run on the MG1 runtime
unchanged, desktop only: `fm1-render --mod` plays them, and nothing in the
simulator shows them yet (MG3).

```bash
make -C engines                                   # fm1-render, fm1-mod-kinds-test, fm1-mod-mi-ref
engines/build/fm1-render --list-mod               # every kind's parameters, uids, ports, sizes
printf 'mod 1 filter cutoff=0.5 res=0.8\nslot 1 trig > flt1.ping\nslot 2 flt1.bp > snd:Timbre amt=40\n' > /tmp/w.mod
engines/build/fm1-render --engine macro --note 0.1:60:100:1.5 --seconds 1.6 --mod /tmp/w.mod --out /tmp/w.wav
engines/build/fm1-mod-kinds-test                  # behaviours, the Filter's response, fills, fuzz
engines/build/fm1-mod-mi-ref                      # the Peaks and Braids ports against the originals
python -m pytest tests/test_engines_mod_kinds.py  # all of it, golden traces, block sizes, chains
python3 engines/mod/gen_mi_tables.py --check      # mod_mi_tables.c is current
```

| Kind (id, abbr) | Code | In (gates; INPUT parameters) | Out | Bytes (arm64) |
| --- | --- | --- | --- | --- |
| Function (`function`, FUN) | own | TRIG (normal TRIG), GATE (normal KEY), CYCLE, HOLD; IN | OUT, INV, UP, DOWN, EOR, EOC | 64 |
| Bounce (`bounce`, BNC) | port of Peaks | TRIG (normal TRIG) | OUT, HIT | 36 |
| Register (`register`, REG) | own, on `fm1_mp` | CLOCK (normal CLOCK), WRITE | CV, BIT, PITCH (SEMI) | 88 |
| Coin (`coin`, COI) | own | IN (normal TRIG) | A, B | 24 |
| Divide (`divide`, DIV) | own | CLOCK (normal CLOCK), RESET (normal START) | OUT1, OUT2 | 192 |
| Burst (`burst`, BST) | port of Peaks, plus ours | TRIG (normal TRIG), CLOCK | OUT, GATE, DONE | 312 |
| Slew (`slew`, SLW) | own | THRU; IN | OUT, OUT2–OUT6 | 144 |
| Quantize (`quantize`, QNT) | port of Braids | CLOCK; IN | PITCH (SEMI), CHG | 28 |
| Compare (`compare`, CMP) | own | —; A, B | GATE, NOT, RISE, FALL, ABOVE, MID, BELOW | 44 |
| Logic (`logic`, LOG) | own | A, B | OUT, NOT | 12 |
| Calc (`calc`, CLC) | own | —; A, B | OUT, INV | 12 |
| Mix (`mix`, MIX) | own | —; IN1–IN4 | SUM, AVG, INV | 4 |
| Filter (`filter`, FLT) | own | PING; IN | OUT, LP, BP, HP | 40 |

- **Sizes** are `fm1-render --list-mod` on arm64 macOS [verified]; a
  `gcc -m32` build gives the same or less (its `uint64_t` aligns to 4)
  [verified 2026-10-02 in a container]. Every kind is under 256 B but
  Burst, which ports Peaks' 32-pulse buffer whole. The sixteen kinds'
  instances add up to 1,396 B, so any rack of eight fits the 8 KB arena
  with room to spare.
- **Uids** are pinned in `tests/fixtures/mod-uids.json`, 1 upwards in
  table order. Gate inputs and parameters never share a name, since a
  script names both the same way (`flt1.ping`) [verified: test].
- **Normals.** A gate input with a normal reads that system source until a
  cable reaches it (README.md, "Gate cables"): with no cable, Function and
  Bounce follow the notes, Divide and Register the sequencer's steps.
- **Licences.** Everything here is MIT. The three ports carry Emilie
  Gillet's MIT notice (`mod_mi.c`, `mod_mi_tables.c`); the rest is ours,
  written from published behaviour. Branches' firmware (GPL-3) was not read.
  Mutable module names appear only as credited sources.

## The kinds

Times marked "knob" use Peaks' knob-to-time curve, 0.5 ms to 8 s
(`fm1_mp_env_time_from_knob`). "Rounded" FLOATs hold whole numbers;
modulation moves them in steps.

### Function (FUN)

A function generator: OUT rises from wherever it is to Level in Rise, then
falls to the floor in Fall; the floor is Floor + IN. After Make Noise's
Maths, Joranalogue's Contour 1, Serge's DUSG and Befaco's Rampage
(behaviour only; Rampage's VCV code is GPL and was not used).

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Rise | 0–1 | knob time of a rise |
| 2 | Fall | 0–1 | knob time of a fall |
| 3 | Shape | −1–1 | −1 fast start (Peaks' exponential), 0 linear, +1 slow start (Peaks' quartic) |
| 4 | Mode | AD, AR, Cycle, Slew, Gated | AD: TRIG starts rise then fall. AR: rises while GATE is high, holds at Level. Cycle: for ever, TRIG restarts. Slew: OUT glides to Floor + IN, Rise and Fall per full-scale move. Gated: cycles while GATE is high |
| 5 | Level | 0–1 | the top |
| 6 | Floor | 0–1 | the bottom (plus IN) |
| 7 | Retrig | 0–1 | how far through its cycle a TRIG is taken: 1 always, 0.5 from the fall (Maths), 0 only idle |
| 8 | Sync | Off, 4 Bars … 1/8D | the cycle is that division of the tempo, Rise and Fall sharing it in the ratio of their knobs; Start restarts it |
| 9 | In | INPUT | adds to the floor; the slew target |

- **A segment takes its whole time** from wherever it starts (Contour 1's
  way; Maths keeps its slope). A retrigger rises from the current value.
- **CYCLE** high makes any mode but Slew cycle; **HOLD** high freezes it.
- **Outputs:** OUT (0..1), INV (1 − OUT), UP and DOWN (gates while rising
  and falling), EOR and EOC (triggers at the end of a rise and of a fall),
  all at their own frames. Turning Rise or Fall acts on the running
  segment at the next tick.
- **Checked** [verified: `fm1-mod-kinds-test`]: EOR and EOC fall one rise
  and one fall after the trigger, to a frame plus 0.2 %; a cycle's period;
  Retrig 0 and 1; HOLD; AR's sustain and release; Slew's glide time and
  its shapes at the midpoint; a synced cycle of exactly one beat at 120 BPM
  (22,059 frames, ± 2).

### Bounce (BNC)

Peaks' bouncing ball: a TRIG drops it from Height with Velocity; it falls
with Gravity and keeps Bounce of its speed at each bounce.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Gravity | 0–1 | Peaks' gravity pot turned round, so up is heavier: a fall from full height takes 0.97 s at 0 and 5.3 ms at 1 [verified: test] |
| 2 | Bounce | 0–1 | 0 dead, 1 elastic |
| 3 | Height | 0–1 | where it drops from |
| 4 | Velocity | −1–1 | a throw down or up |

- **OUT** is its height (0..1) after the tick's last 48 kHz sample. **HIT**
  (ours) is a trigger at each bounce whose rebound would rise above 1 % of
  full height, at its frame.
- **Light and elastic, it never settles:** Peaks' integer rebound,
  `-(v >> 12) × loss`, rounds small speeds up, so the ball keeps bouncing a
  few percent high and HIT keeps firing, as on the original [verified:
  test]. Heavy, it comes to rest.

### Register (REG)

A looping random shift register after Music Thing Modular's Turing Machine
(Tom Whitwell), on `fm1_mp_turing_t`.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Change | −1–1 | +1 locks the loop, 0 is fresh random, −1 locks a loop of twice the length, its second half inverted |
| 2 | Length | 1–32, rounded | the loop's length in steps |
| 3 | Level | −1–1 | scales CV |
| 4 | Offset | −1–1 | added to CV |
| 5 | Span | 0–60 semitones | PITCH's range |
| 6 | Slew | 0–1 | CV's linear glide: 0 off, else a knob time per full-scale move |

CLOCK (normal CLOCK) shifts it; a rising WRITE flips the next bit to come
back. CV is the low 8 bits as 0..1 × Level + Offset; BIT is the newest bit
AND CLOCK; PITCH is the 8-bit value over Span, in whole semitones (SEMI).
One draw per clock whatever Change is [verified: test, loops of L and 2L].

### Coin (COI)

A Bernoulli gate, from the published behaviour of Mutable Instruments'
Branches (its GPL-3 firmware was not read).

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Prob | 0–1 | Direct: the chance of B (0 always A, 1 always B). Toggle: the chance of switching sides |
| 2 | Mode | Direct, Toggle | |
| 3 | Latch | Off, On | Off: the chosen side follows IN. On: it stays high, and the other low, until a toss picks the other side |

Edges keep IN's frames; one draw per rise from the instance's own
generator [verified: test, 4,000 tosses at 0, 0.25 and 1].

### Divide (DIV)

Two channels of division, multiplication, Euclidean rhythm and probability
on a clock. After Phazerville's ClockDivider, ProbabilityDivider, Shuffle
and GateDelay applets and Piqued's Euclidean filter (MIT; no code taken).

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1, 5 | Mode1, Mode2 | Div, Mult, Euclid, Prob | |
| 2, 6 | Value1, Value2 | 1–16, rounded | Div: every Nth step. Mult: N per clock period. Euclid: the loop's length |
| 3, 7 | Fill1, Fill2 | 0–1 | Euclid: hits = Fill × Value. Prob: the chance of a step |
| 4, 8 | Rot1, Rot2 | 0–15, rounded | Div and Euclid: steps of rotation |
| 9 | Swing | 0–1 | every second trigger of a channel late by Swing × half its period (1: three quarters of the way) |
| 10 | Delay | 0–1,000 ms | every trigger later |

- CLOCK normal CLOCK, RESET normal START; at one frame RESET goes first,
  so a Start's first step is step 0.
- Mult measures the period between the last two clocks; each clock
  restarts its run. Euclid is Bjorklund's pattern in its Bresenham form:
  step p hits when (p × hits) mod length < hits (3 of 8 is x..x..x.).
- Up to 8 triggers wait per channel. Prob draws once per step and channel
  in every mode [verified: test, exact frames for Div, Euclid, Mult, Swing,
  Delay and RESET].

### Burst (BST)

Ratchets, delays and random repeats: Peaks' pulse shaper and pulse
randomizer.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Mode | Burst, Delay, Random | Burst: Count pulses. Delay: the same after a pre-delay. Random: Peaks' randomizer |
| 2 | Count | 1–8, rounded | pulses per trigger |
| 3 | Spacing | 0–1 | the gap (Random: the average gap) |
| 4 | Length | 0–1 | each pulse's length |
| 5 | Delay | 0–1 | Delay mode's pre-delay |
| 6 | Accel | −1–1 | ours: each gap after the first × 2^(−Accel / 2); 0 is Peaks |
| 7 | Accept | 0–1 | Random: the chance a trigger is taken |
| 8 | Repeat | 0–1 | Random: the chance of another repeat |
| 9 | Jitter | 0–1 | Random: how much the gap varies |

- Spacing, Length and Delay follow Peaks' delay table: 5 to 60,000 calls,
  0.42 ms to 5 s. The table was built for 1 ms to 10 s at 6 kHz; Peaks
  calls its processors at 12 kHz [verified: `lookup_tables.py` and
  `io_buffer.h`].
- **CLOCK** (ours): with a cable in, the repeats share the measured clock
  period, period / Count apart.
- **OUT** is Peaks' output, as a gate; **GATE** is high while a burst runs
  (to the end of its last gap); **DONE** is a trigger when it ends.
  Changing Mode starts the new processor empty.

### Slew (SLW)

A slew limiter with six outputs. Linear: a full 0 → 1 move takes the
knob's time. Expo: a one-pole lag with that time constant, landing
exactly.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Up | 0–1 | knob time, rising |
| 2 | Down | 0–1 | knob time, falling |
| 3 | Type | Linear, Expo | |
| 4 | Spread | −1–1 | output j (OUT is 0) takes the time × (1 + Spread × j), or ÷ (1 − Spread × j) below 0: OUT6 six times slower at +1, six times faster at −1 |
| 5 | In | INPUT | |

THRU high: every output follows IN at once; so does an output whose time
is under a tick (0.73 ms). IN changes once a tick, so the
limiter steps a tick at a time with exact 32-sample steps, in Q4.28 as
`fm1_mp_slew` [verified: test, linear times to a tick, 1 − 1/e after the
time constant, spread ×6 and ÷6].

### Quantize (QNT)

Braids' quantiser and its 49 scales. IN × 12 × Range semitones is the
pitch above or below middle C; Range 5 (the default) makes IN the SEMI unit,
so a pitch source passes in tune.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Scale | Off, Semitones, Ionian … Jogeshwari (49) | Braids' scales: church modes, blues, pentatonics, world and quarter-tone scales, 29 ragas |
| 2 | Root | C … B | |
| 3 | Range | 0–5 octaves | IN's span |
| 4 | Trans | −24–24 semitones (SEMI), rounded | added after quantising |
| 5 | In | INPUT | |

Braids' hysteresis holds a note a little past the midpoint. PITCH is SEMI;
CHG is a trigger when the note changes. With a cable into CLOCK it takes IN
only at CLOCK's rises, CHG at their frame. On a scale change the held cell
goes (Braids keeps it until the input moves) [verified: test, every output
in the scale, monotonic on a rising sweep, the clocked frame].

### Compare (CMP)

Gates from comparing: d = A − (B + Thresh), or in Trend mode A's slope
(1.0 = a change of 10 per second) minus (B + Thresh).

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Mode | A>B, Window, Trend | GATE: d above 0; \|d\| under Width; the slope above B + Thresh |
| 2 | Thresh | −1–1 | added to B |
| 3 | Hyst | 0–1 | the Schmitt band: rises above +Hyst/2, falls below −Hyst/2 |
| 4 | Width | 0–1 | the window's half-width; ABOVE, MID, BELOW in every mode |
| 5, 6 | A, B | INPUT | |

An edge sits at the frame where the straight line between the last tick's
d and this tick's crosses the threshold, so Compare is the sample-accurate
way to turn a CV into a gate (a CV cable into a gate input switches at the
tick's first frame) [verified: test]. NOT inverts GATE; RISE and FALL are
triggers at its edges.

### Logic (LOG)

Gates A and B in, OUT and NOT out, at every edge in frame order (A before B
at one frame): AND, OR, XOR, NAND, NOR, XNOR; SR (A sets, B resets, B wins
a tie); D (B's rise copies A); Toggle (A flips, B resets). Op (uid 1) takes
modulation, rounded [verified: test, every edge's frame for AND, OR, XOR,
NOR, SR, D and Toggle].

### Calc (CLC)

OUT = clamp(Amount × op(A, B) + Offset), INV = −OUT.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Op | Sum, Diff, Mult, Min, Max, Mean, Abs, Rect, Neg, Fade, Log, Root, Square, Slope | Log, Root and Square through the matrix's sign-preserving curve tables; Slope is A's rate of change, 1.0 = 10 per second |
| 2 | Amount | −1–1 | |
| 3 | Offset | −1–1 | |
| 4 | Snap | Off, Semi | rounds Offset to whole semitones (1/60) |
| 5 | Fade | 0–1 | Fade's mix, A to B |
| 6, 7 | A, B | INPUT | |

### Mix (MIX)

SUM = clamp(Σ Gain_i × IN_i + Offset); AVG divides the sum by the inputs
with a cable; INV = −SUM. Gain1–4 (uids 1–4) run −2..2; Offset is uid 5;
IN1–4 (uids 6–9) are INPUTs.

### Filter (FLT)

The owner's request (2026-10-02): a filter for control signals whose
outputs are matrix sources, which a gate can strike into a resonant
wobble.

| Uid | Parameter | Range | What it does |
| --- | --- | --- | --- |
| 1 | Cutoff | 0–1, log | 0.05 Hz × 2^(13 × Cutoff): 0.05 to 409.6 Hz, 0.5 is 4.5 Hz; held under 0.3 × the tick rate |
| 2 | Res | 0–1 | damping k = 2 (1 − Res)²: Q 0.5 at 0, undamped at 1 |
| 3 | Blend | 0–1 | OUT: LP at 0, BP at 0.5, HP at 1, crossfaded |
| 4 | Level | −1–1 | scales every output |
| 5 | Strike | 0–1 | what a rising PING adds to the band-pass state |
| 6 | In | INPUT | |

- **The design** is the trapezoidal (topology-preserving) state-variable
  filter as Andrew Simper (Cytomic) published it, written here, one sample
  per tick (1,378.7 Hz). g = tan(π fc / rate) from Taylor polynomials of
  sine and cosine (no libm), so the cutoff is exact; it is stable for every
  cutoff below Nyquist and every damping above 0, also while they move; at
  k = 0 its poles sit on the unit circle and it rings for ever. The state
  is limited to ±8.
- **Why Cutoff is not in Hz:** the matrix adds amount × range to a
  parameter, linear in its units. On a 0–1 log scale a cable moves the
  cutoff by octaves, as LFO's Rate does.
- **Strike:** the filter rings at its cutoff with an amplitude near Strike
  on every output (about 0.80 for 0.8 [verified: test]), decaying as Res sets;
  PING lands at the tick it falls in.
- **How it differs from Slew.** Slew limits the rate of change, or lags
  with one pole: it never overshoots and has no notion of frequency.
  Filter is frequency-selective: LP smooths at 12 dB per octave and can
  overshoot and ring; BP and HP take out the slow part, so they centre a
  drifting signal and keep only its movement; a strike makes it an
  oscillator.
- **Checked numerically** [verified: `fm1-mod-kinds-test`]:
  - the LP, BP and HP gains at 0.25, 0.5, 1, 2 and 4 × the cutoff, at
    cutoffs near 1, 10 and 100 Hz and dampings Q 0.5, 0.707 and 1.02, are
    the analog prototype's at the prewarped frequency
    (|1 / (1 − Ω² + jkΩ)|, Ω = tan(πf / rate) / g), within 1 % (135
    gains, by a least-squares sine fit after the transient);
  - Res 0.1591 (k = √2, Butterworth) is −3 dB at the cutoff;
  - DC: LP 1, BP and HP 0;
  - struck at Res 1, it rings at the cutoff within 0.2 % and keeps its
    amplitude within 0.1 % over 20,000 ticks; at Res 0.9 the envelope
    decays by the poles' radius, √((1 − kg + g²) / (1 + kg + g²)) per tick,
    within 1 %;
  - 200,000 ticks of random cutoff, damping, input and strikes: nothing
    non-finite, every output in range.

## The ports of Mutable Instruments code

`mod_mi.c` holds C ports of Peaks' `BouncingBall`, `PulseShaper` and
`PulseRandomizer` (Emilie Gillet, 2013, MIT) and Braids' `Quantizer` (2015,
MIT), statement for statement in the same integer types, with upstream's
MIT notice. `mod_mi_tables.c` carries Peaks' `lut_delay_times` and
`lut_gravity` and Braids' 49 scales, written by `gen_mi_tables.py` from the
vendored originals. What differs is only how they are held:

- plain structs the kinds embed, no C++;
- the randomizer's `stmlib::Random` is a per-instance state, seeded from
  the preset and position, so instances never share a stream;
- Braids' 128-entry codebook is computed per entry when needed (a
  quantiser holds 16 B, not 256);
- the ball's position and velocity start at 0 (upstream leaves them to its
  static object's zero fill); its negative velocity is multiplied by 16
  where upstream shifts left by 4, which C leaves undefined.

**Rates.** Peaks runs at 48 kHz [reported: docs/16 §2.6; its TIM1
handler's comment says "DAC refresh at 48kHz"] and hands its processors
blocks of 4 samples [verified: `io_buffer.h` `kBlockSize`]. The ball steps
per sample; the pulse processors count calls, 12,000 a second. Each tick
runs the native steps that fall inside it, n(F) = ⌊F × rate / 44,118⌋
(docs/16 §2.6 (b)): a trigger at frame F is step n(F), and an output
change made by step a lands at the boundary after it, ⌈(a + 1) × 44,118 /
rate⌉. A rise on a host frame whose step belongs to the next tick waits for
that tick's first step.

**Checked against the originals** [verified 2026-10-02:
`fm1-mod-mi-ref`, the vendored eurorack 08460a6 compiled with the
vendored-code flags into the test tool only]:
- the tables, element by element, and `Interpolate88`;
- the ball, 2,880,000 samples; the shaper and the randomizer, 4,500,000
  calls each; the quantiser, 1,200,000 calls: random knobs reconfigured as
  they run, random triggers and pitches, every output identical (the
  randomizer on `stmlib::Random` seeded with the port's state, and its
  state equal after every call);
- Bounce as a kind through the runtime at host blocks of 64 with notes at
  random frames: OUT at all 47,988 ticks is the original ball's output
  after the last 48 kHz sample before the tick;
- Burst as a kind (Burst and Delay modes): its OUT edges sit exactly where
  the original shaper's output changes, 1,288 edges over 12 runs.

## Tests

`tests/test_engines_mod_kinds.py` [verified 2026-10-02, macOS arm64 clang;
Linux x86-64 gcc, gcc `-m32` and clang ASan + UBSan in containers]:
- the two C tools above;
- **golden traces:** for each kind a scripted patch of several instances
  for 1 s; the SHA-256 of every tick's parameters, outputs and edges, and
  every 173rd tick's outputs, in `tests/fixtures/mod-golden.json`
  (`FM1_UPDATE_GOLDEN=1` rewrites it). The hashes are the same on every
  build above;
- **block sizes:** two racks of the new kinds (eight positions each,
  fourteen cables, into the sound, an effect, PITCH and AMP, with the
  sequencer playing) give the same WAV and tick log at host blocks of 1, 7
  and 64, and from fills of 0x00, 0xA5 and 0xFF;
- **chains:** LFO → Mix → Calc (Neg) → Calc (Neg) → Timbre, entered with the
  LFO at the bottom of the rack, writes what a direct cable writes, in the
  same ticks; LFO WRAP → Logic → Coin → Divide → an Envelope's gate starts
  it at the frames a direct cable does;
- **feedback:** Mix's SUM into its own IN1 plus 0.01 adds 0.01 a tick, in
  float, exactly; Slew → Compare → NOT → Slew is a relaxation oscillator
  whose period repeats to the frame;
- the owner's case: a note strikes a resonant Filter whose BP moves Timbre
  at 4.5 Hz and dies away;
- `fm1-mod-kinds-test` also builds every kind from fills of 0x00, 0xA5 and
  0xFF (identical ticks), and runs each for 5,000 ticks with random and with
  extreme bases (±1e30, ±∞, NaN): no output was ever replaced as non-finite;
- `nm -u`: no allocator, stdio or libm in any kind or port
  (`test_no_heap_no_stdio_no_libm` in the runtime's tests).

## What MG2 leaves for later

- **The simulator** (MG3) shows none of these yet.
- **Owner decisions:** the kinds' names (docs/16 §9 question 13: only LFO,
  Envelope and Chance are answered) and whether the first wave stands as
  built (question 14).
- **A Function with Maths' constant slope** (a retrigger that keeps the
  slope rather than the time) would be another Mode.
- **A sub-tick strike.** Filter takes a PING at its tick, not its frame.
