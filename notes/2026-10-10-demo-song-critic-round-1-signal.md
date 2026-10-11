# Round 1 rendered-signal addendum

[verified] Parent rendered unmodified full-song Wasm output for canonical asset `27939c784be6d8bacb19bc8b5eaba6bb34583ea2`, corresponding to the musical score at `9a2d099`. This addendum reads the parent receipt and aggregates its per-second RMS. No audio perception or listening was performed.

Receipt SHA256: `7ea3e939e30393b842d36a5f040ad747b6f24c3f51140d4d00172aa3a56a7ce5`. Sample rate: 44118 Hz. Source path: `scratch/demo-song-review/round-1/results.json` in the integration worktree.

Duration-weighted mean square of provided per-second RMS, using nominal scene boundaries; fractional seconds assume stationary energy inside that one-second window. Approximate section RMS only, not LUFS, perceived loudness, or sample-exact boundaries.

Source score remains unchanged. Signal evidence demonstrates macro energy contrast despite duplicated returning scenes; an exact event/lock duplicate need not have identical samples because free LFOs and effect state continue across the song. This distinction tempers any claim that repetition is sonically static.

## Afterglow Relay

[verified] Peak 0.7546; full capture RMS 0.0776; dropped events 0; project-loader RAM 67%; round-trip True; Stop 198.268s versus nominal 198.261s.

| Bars | Scene | Approx RMS | Δ dB from previous entry |
| --- | --- | --- | --- |
| 1–4 | Intro | 0.0720 | — |
| 5–12 | Verse | 0.0678 | -0.51 |
| 13–20 | Verse | 0.0664 | -0.19 |
| 21–24 | Lift | 0.0799 | +1.62 |
| 25–32 | Hook | 0.0880 | +0.84 |
| 33–40 | Hook | 0.0876 | -0.04 |
| 41–48 | Bridge | 0.0730 | -1.58 |
| 49–56 | Vrs2 | 0.0676 | -0.67 |
| 57–64 | Hook2 | 0.0886 | +2.36 |
| 65–72 | Hook2 | 0.0876 | -0.10 |
| 73–76 | Outro | 0.0649 | -2.60 |

[inferred] First peak averages +2.26 dB above the first verse; the contrast scene averages -1.62 dB relative to that peak. The final peak changes only +0.06 dB from the first peak. These measurements support an energy arc, while the source-based critique concerns missing phrase development and promised layer changes; louder is not automatically better.

## Event Horizon

[verified] Peak 0.8684; full capture RMS 0.0694; dropped events 0; project-loader RAM 69%; round-trip True; Stop 193.339s versus nominal 193.333s.

| Bars | Scene | Approx RMS | Δ dB from previous entry |
| --- | --- | --- | --- |
| 1–4 | Intro | 0.0580 | — |
| 5–8 | Intro | 0.0558 | -0.33 |
| 9–16 | Verse | 0.0565 | +0.10 |
| 17–24 | Verse | 0.0562 | -0.04 |
| 25–28 | Build | 0.0694 | +1.83 |
| 29–36 | Drop | 0.0786 | +1.08 |
| 37–44 | Drop | 0.0781 | -0.06 |
| 45–52 | Drop | 0.0788 | +0.08 |
| 53–60 | Drop | 0.0785 | -0.03 |
| 61–64 | Break | 0.0558 | -2.97 |
| 65–72 | Vrs2 | 0.0566 | +0.12 |
| 73–80 | Vrs2 | 0.0560 | -0.09 |
| 81–88 | Drop2 | 0.0787 | +2.96 |
| 89–96 | Drop2 | 0.0784 | -0.04 |
| 97–104 | Drop2 | 0.0778 | -0.06 |
| 105–112 | Drop2 | 0.0786 | +0.09 |
| 113–116 | Outro | 0.0537 | -3.31 |

[inferred] First peak averages +2.87 dB above the first verse; the contrast scene averages -2.98 dB relative to that peak. The final peak changes only +0.01 dB from the first peak. These measurements support an energy arc, while the source-based critique concerns missing phrase development and promised layer changes; louder is not automatically better.

## Packet Bloom

[verified] Peak 0.7532; full capture RMS 0.0741; dropped events 0; project-loader RAM 54%; round-trip True; Stop 188.578s versus nominal 188.571s.

| Bars | Scene | Approx RMS | Δ dB from previous entry |
| --- | --- | --- | --- |
| 1–4 | Intro | 0.0684 | — |
| 5–12 | A-side | 0.0671 | -0.17 |
| 13–20 | A-side | 0.0671 | +0.01 |
| 21–24 | Build | 0.0752 | +0.99 |
| 25–32 | Bloom | 0.0813 | +0.68 |
| 33–40 | Bloom | 0.0815 | +0.02 |
| 41–48 | Bloom | 0.0806 | -0.09 |
| 49–52 | Glitch | 0.0768 | -0.42 |
| 53–60 | B-side | 0.0669 | -1.21 |
| 61–68 | B-side | 0.0678 | +0.12 |
| 69–76 | Bloom2 | 0.0803 | +1.46 |
| 77–84 | Bloom2 | 0.0810 | +0.09 |
| 85–88 | Outro | 0.0636 | -2.11 |

[inferred] First peak averages +1.67 dB above the first verse; the contrast scene averages -0.49 dB relative to that peak. The final peak changes only -0.12 dB from the first peak. These measurements support an energy arc, while the source-based critique concerns missing phrase development and promised layer changes; louder is not automatically better.

## Neon Transit

[verified] Peak 0.8459; full capture RMS 0.0728; dropped events 0; project-loader RAM 67%; round-trip True; Stop 208.007s versus nominal 208.000s.

| Bars | Scene | Approx RMS | Δ dB from previous entry |
| --- | --- | --- | --- |
| 1–4 | Intro | 0.0582 | — |
| 5–8 | Intro | 0.0594 | +0.17 |
| 9–16 | Verse | 0.0697 | +1.39 |
| 17–24 | Verse | 0.0701 | +0.05 |
| 25–28 | Pre | 0.0669 | -0.41 |
| 29–36 | Chorus | 0.0800 | +1.55 |
| 37–44 | Chorus | 0.0805 | +0.05 |
| 45–52 | Chorus | 0.0795 | -0.10 |
| 53–56 | Bridge | 0.0657 | -1.66 |
| 57–64 | Vrs2 | 0.0707 | +0.64 |
| 65–72 | Vrs2 | 0.0701 | -0.07 |
| 73–80 | Chor2 | 0.0794 | +1.08 |
| 81–88 | Chor2 | 0.0800 | +0.06 |
| 89–96 | Chor2 | 0.0808 | +0.08 |
| 97–100 | Outro | 0.0593 | -2.68 |
| 101–104 | Outro | 0.0577 | -0.23 |

[inferred] First peak averages +1.20 dB above the first verse; the contrast scene averages -1.70 dB relative to that peak. The final peak changes only -0.06 dB from the first peak. These measurements support an energy arc, while the source-based critique concerns missing phrase development and promised layer changes; louder is not automatically better.

## Limits

RAM percent is a reported project-loader statistic, not measured total hardware SRAM headroom or an FM-1 deployment result. Zero event drops does not establish absence of synth voice stealing or masking. Peak/RMS do not measure spectral balance, pitch clarity, spatial impression or listener fatigue. Those issues remain scoped to source inference and owner listening. The source report already traces every transition; this addendum quantifies each entry without turning energy into a musical score.

## Native and actual browser state

[verified] Read full native and browser receipts. Every song has zero skipped/repaired fields, refused locks and dropped events. Native sequencer events total 11,786 / 19,394 / 14,254 / 16,650 respectively. Independently compared actual browser Save files: `master`, `mod` and `dx7` objects are identical; the `set` command multiset is preserved with serialization ordering changes. Sounds are identical after removing only newly serialized disabled default arp objects from previously empty MIDI-FX arrays. This is semantic preservation, not byte identity. Parent browser receipt records preload, play, download and fresh-context Open passing all four with no page exceptions. JSON retains receipt hashes, Wasm hash, load reports and native counters. This strengthens runtime evidence without changing musical judgments.
