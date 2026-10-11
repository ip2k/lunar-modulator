# Packet Bloom replacement composition — 2026-10-11

This is original music built from the owner's vapor/twitch direction and
reference titles (INZO, Medasin, Flips and Flops/Drips and Drops, Alina Baraz &
Galimatias). No reference audio was accessible or heard; no resemblance claim
is made. The owner rejected the original Packet Bloom as too similar to
Afterglow. `packet-bloom.lunar` stays untouched as a legacy example. The new
project is `packet-bloom-showcase.lunar`.

The freeze is 82 BPM, five distinct chained scenes of 8/10/6/12/4 bars: Mist,
Packets, Hinge, Bloom, Dissolve. E Dorian replaces the other songs' minor/pop
harmony. Crater supplies sparse kick/snare and uneven quiet hats; Phase Bend
Double Sine provides rounded low notes; Macro Heavy Modal supplies a fixed
original modal call with a silent third bar, not transposed chord-root runs;
Sophie supplies carefully tuned short accents rather than a sustained chord
bed. The hinge replaces the main call with an exposed F-sharp/D texture; the
final bloom shifts the call down an octave and the tail leaves room to decay.
Hats/snare/pitched pickups use separate deterministic tick nudges, while the
project swing remains neutral. This deliberately differs from Satellite's
straight 124 BPM Comet dance pulse, clipped Shapes hook and organ chord stabs.

Sophie pitches select pad indices; the generator explicitly tunes those pads.
Macro Heavy Modal shares implementation lineage with Afterglow's Macro, but is
not its VA oscillator/filter timbre. Source separation does not prove audible
separation; the collection still needs owner comparison and independent critique.

`tools/showcase_songs.py` emits both new projects deterministically. Registry
bounds/enums, per-pad placement/defaults, metadata caps, scene boundaries and
same-pitch overlaps across pitched-slot tracks pass source checks. Serena found
`build_packet` and its actual `main` caller; diagnostics returned no warnings or
errors. Rarefaction is limited to the main checkout and was not reconfigured.

Runtime is blocked: bounded SSH to `claude@192.168.1.25` returned `Host is down`.
No infrastructure changes were attempted. Native/Wasm load/save admission,
full finite renders, browser file flow and owner listening remain pending.
Root owns the generic harness/catalog integration. No merge or hardware test
has occurred.
