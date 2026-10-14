# Demo project target allocation: bounded offline evidence

This note evaluates whether host startup refusals for Satellite Hearts and Afterglow Relay Showcase imply target pool exhaustion. Work was compile-only and static arithmetic; no device, MIDI, USB, flash, power, reboot, or runtime startup test occurred. Target source base is f3779b78082cceec74852120306efcaca15abcf4.

## Pool and measurements

The retained all-production full-song target link configures a **216,064 B** pool: 192,000 + 57,088 indexed-TFT credit - 33,024 raw wavetable storage. This is link/configuration evidence only; the linked candidate says installable=false, hardware_candidate=false, hardware_tested=false, startup_project.runtime_verified=false.

Unit type sizes were emitted as constants by JieLi pi32v2 clang 4.0.1 and decoded with tools/jieli/analyze.py. Rate-dependent Hall and Limit requests were calculated from their checked MakeLayout formulas at 44,118 Hz using their target-compiler-measured Instance sizes. Exact values, object hashes, formulas, compiler flags, and pool calculations are in [remaining-unit-sizes.txt](2026-10-14-demo-target-allocation/remaining-unit-sizes.txt).

The nominal model is round16(payload)+16 bytes per request; this is not the exact TLSF charge because the call path does not itself round to 16 and TLSF adds internal overhead/fragmentation. Modeled project charges, in canonical sound-unit, insert, then master-effect order:

| Project | Modeled charge | Gross pool result |
|---|---:|---:|
| Satellite Hearts | 289,232 B | 73,168 B over |
| Afterglow Relay Showcase | 192,208 B | 23,856 B left |
| Packet Bloom Showcase | 222,160 B | 6,096 B over |

Satellite cumulative modeled reservation crosses the pool at Shapes (222,272 B), before its second Drawbar and master effects. Packet Bloom crosses at Limit. Those are static sums, not observed runtime refusal sites. Afterglow static gross sum leaves room, but this does not prove runtime fit because fragmentation, other pool clients, constructor failures, and simultaneous allocations are not measured. The legacy packet-bloom.lunar is a different selection and was not separately totaled.

The host harness used a fixed 192,000 B pool and 64-bit objects; host Macro is 32,736 B versus 19,872 B on target. Its largest_allocation_request is the maximum across all observed allocations, not the proven failed request, so it cannot identify a failing unit. Sequencer staging is freed before engine reservations and is not part of the later simultaneous engine total.

## Limits and next step

Compile-time layout plus source-formula evaluation does not execute target functions, test TLSF fragmentation, prove constructors succeed, or validate audio/startup on an FM-1. No supported states/features or physical flash layout changed.

Next, use the bounded native target startup harness to compare these static predictions with actual allocator/constructor behavior. Keep that evidence separate from device acceptance, which requires the owner explicitly authorized hardware stage.
