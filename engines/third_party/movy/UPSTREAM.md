# Movy (schwung-movy) — the sequencer the core replicates

The sequencer core in `engines/seq/` and `engines/include/fm1_seq.h` is a C99
rewrite of Movy's `seq-core` crate: [schwung-movy](https://github.com/DimaDake/schwung-movy)
by megadake, MIT licensed (`LICENSE` here is its notice, which the derived
files carry by reference). No Movy source is vendored: the C files are new code
that follows the Rust logic, each naming the Rust file and lines it follows.

Pinned at commit `9190e79a2f461e71d2bf0a9fa77042011945021e` (main, 2026-10-01;
`module.json` says 0.34.0, ENGINE_VERSION 0.81.0). The files read, by git blob:

| Movy file (`engine/crates/seq-core/src/`) | Blob | C counterpart |
| --- | --- | --- |
| `lib.rs` | `8d583b0c46d43f99db3ad48d894bead767a9fbf6` | `fm1_seq.h` constants |
| `clock.rs` | `e9edef4e5b8c8a9f7ca62566058e25bb33a508a7` | `seq_engine.c` |
| `track.rs` | `252f88a8b28a2d424946c31e730554aaab56dbf6` | `seq_int.h`, `seq_engine.c` |
| `clip.rs` | `7e969b5cc2d540fa348085d577d8faa4f5b9ee5b` | `seq_clip.c` |
| `engine.rs` | `832aaa6502332863646acba34db10a9b41977433` | `seq_engine.c`, `seq_capture.c` |
| `command.rs` | `2eb680224dfd1fbf7e1e8d992504f6b3c6aeec38` | `seq_cmd.c` |
| `persist.rs` | `d9834169437356056d150d031b867e96de2215ba` | `seq_persist.c` |
| `capture.rs` | `f18d7da2fb35ec7dafbefd2ed30f2325d966d462` | `seq_capture.c` |

Not ported: `undo.rs` (stage M4), the Move transport link and MovePlay inject,
and the status strings. Credit line for About and the README (docs/13 §8):
"Sequencer design and logic after Movy by megadake (MIT),
github.com/DimaDake/schwung-movy". The UI calls it "Sequencer".
