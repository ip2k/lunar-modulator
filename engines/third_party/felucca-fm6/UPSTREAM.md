# Vendored: Felucca's fm6_core.c (the FM6 engine's test oracle)

| | |
| --- | --- |
| Upstream | https://github.com/hugelton/Felucca at `727f272015da26eb2d0291bd652eba28ff57cb37` (Felucca 1.0 source, 2026-10-05), `firmware/src/fm6_core.c` and `LICENSES/Apache-2.0-msfa.txt` |
| What it is | An integer C port of msfa as Dexed carries it (Dexed's `Source/msfa`): envelopes with Dexed's static stages, pitch envelope, LFO, the note set-up and the 32 algorithms, in 32-sample blocks |
| Authors | Google Inc. (2012), Pascal Gauthier (2016-2025), ported by Leo Kuroshita (@kurogedelic), Hügelton Instruments (2026) |
| Licence | Apache-2.0: the file's own SPDX header, and `LICENSE` here is Felucca's `LICENSES/Apache-2.0-msfa.txt`, its notice and the licence text. The rest of Felucca is GPL-3.0-only and is **not** vendored or used; the tables the file expects are computed by our own `engines/test/dx7_felucca.c` |
| Copied by | `vendor.py` (`--check` compares) |
| Local changes | **None.** |
| Used by | `engines/test/dx7_felucca.c` and `fm1-dx7-oracle` (`engines/test/dx7_oracle.cc`), a desktop test tool. It is in no engine and no firmware or browser build. Vendoring it as an oracle was the owner's decision (2026-10-05) |

| File | sha256 |
| --- | --- |
| `fm6_core.c` | `1ced3d7398be5968be7a37d8ad062bdad6aad8004d3d4ac002e58a8e88728325` |
| `LICENSE` | `27dd23b62bc11d0806562397a1e782f86fc7dcacd1ba7a1b58d3c78a54795e62` |

Re-vendoring:

```bash
git clone https://github.com/hugelton/Felucca reference/Felucca
python3 engines/third_party/felucca-fm6/vendor.py reference/Felucca --check
```

## Where it differs from FM6 on purpose (engines/msfa.md, "The oracle")

- Dexed's envelope holds a stage whose level does not move for the time the
  DX7 takes (`ACCURATE_ENVELOPE`); Google's msfa, which FM6 runs, moves on
  at once. The oracle tests use envelopes with no two equal neighbouring
  levels.
- Dexed rounds keyboard level scaling's key groups differently
  (`(offset + 1) / 3`); within 0.4 dB on the tests' voices.
- Its algorithm table has `0xC1` in rows 4 and 6: the sixth operator feeds
  back to itself there. FM6 runs the loop through the fourth or fifth.
- Its amplitude modulation is Dexed's curve, ported with a scale error: the
  factor `pt` comes out 2^14 too large and wraps, so an operator with AMS
  above 0 plays at the top of its range whatever AMD is [verified: a render
  of a voice with AMS 3, 2026-10-05; candidate upstream report]. The tests
  compare no voice with AMS above 0.
