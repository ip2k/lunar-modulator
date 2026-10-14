# UART1 TRS MIDI diagnostic review

Review base: `f18738055026b2a1859da93d2fe2853a42485743` (`codex/2026-10-14-uart1-midi-input`). This is a source and host-test review only; no target build or device operation was performed.

## Findings

- **[verified] Ring overflow cursor math is incorrect when unread bytes are already pending.** `lunar_midi_uart_drain()` detects `pending + newly_received > ring_bytes`, clears pending bytes and resets parser state, but advances `cursor` by only `newly_received`. The DMA head after overflow is `(cursor + pending + newly_received) % ring_bytes`; omitting the old pending count resumes at stale ring data. Concrete case: capacity 256, cursor 0, pending 10, newly_received 250 means the head is 4, while the reviewed code sets cursor to 250. If the next snapshot reports 3 bytes, DMA wrote indices 4–6 but the consumer reads from 250. A focused regression uses capacity 8, cursor 0, pending 5 and newly_received 4: overflow should reset parser state and leave cursor 1; a subsequent byte at index 1 must be consumed from index 1. The current four-file host suite passes but did not cover this cursor value. This review did not edit implementation code.
- **[verified] C/C++ boundary and build flags match.** `midi_uart_stream.h` and `midi_stream.h` declare their APIs with `extern "C"` under C++; the test compiles the adapter as C and links it with `midi_stream.cpp` and the Arduino MIDI parser using the target's no-exception/no-RTTI conventions. This proves host linkage and parser-adapter behavior, not pi32v2 code generation or device ABI.
- **[verified] Initialization order matches the HAL's stated constraint.** `fm1_cstart()` initializes audio and USB, calls the compile-time guarded UART initializer, then starts TIMER5 and enables interrupts. UART setup itself enables RX DMA last and enables no UART interrupt. The application polls from its normal main loop; USB MIDI remains first and independently bounded to 32 messages per pass, followed by at most 32 UART bytes.
- **[verified] Pulse is opt-in and constrained.** The C4 pulse requires `song-diagnostic`, an empty prepared content profile, no project or SET startup, explicit TRS MIDI mode, and all 13 production engines selected. It emits one note-on in the 3-5 second interval and one note-off at/after 5 seconds; if first polled after 5 seconds it emits nothing. This is a bounded diagnostic stimulus, not musical acceptance.
- **[verified] The direct ADC diagnostic is observational.** The new raw ADC value is copied to `lunar_master_adc_raw` and displayed in the fixed-width footer. It is not used to calculate `master_q12`; the builder keeps its existing probe unity-gain assignment and separately preserves the existing app master-control path. This does not claim the probe's master behavior is stock-equivalent.
- **[verified] Dinghy inventory hashes match.** All 33 current files listed in `firmware/third_party/dinghy/inventory.json` match their recorded SHA-256 values. Its local-modification map lists `src/platform.c` for the compile-time guarded pre-TIMER5 hook; `hal/fm1_uart.h` is inventory-pinned at `482da9e67231a7b42bff63362dec60aa8f43ca6e8d4962df57f8be6f9ea5d8c9`. The added parser/adapter sources are first-party under `firmware/native` and are not Dinghy inventory entries.

## Limits and follow-up

- **[verified] The HAL documents a receive-count limitation:** `fm1_uart1_rx_take()` is a polled tally that can miss a byte. The application consumes that tally and clears receive/timeout pending bits; the visible counters report processed bytes, accepted note-ons and rejected messages, but there is no explicit lost-byte/overrun counter. The parser resets on software-detected ring overrun, but a missed hardware count that stays below ring capacity is not observable as an overrun by this layer. This is a target-validation gap, not proof that the current UART hardware loses bytes. Before relying on TRS input, verify HRXCNT/RDC/pending semantics against the exact SoC documentation or instrument a bounded hardware stress test that measures byte loss and parser resynchronization.
- **[verified] The confirmed software overrun cursor defect needs correction before target validation.** Advance to the current DMA head using old pending plus newly reported bytes (wide arithmetic before modulo), clear pending, and reset parser state. Re-run the focused suite with the regression above; also test repeated wraps and overflow with a nonzero cursor. The coordinator has since reported implementing this correction and a regression on a separate source change; this review note describes the reviewed base, not proof that the corrected target was rebuilt.
- **[verified] Builder source-freshness scope is narrower than the entire native image.** `compile_catalogue.source_manifest()` binds the cached engine/catalogue compilation inputs, not `firmware/native/app_probe.c`, `midi_uart_stream.c`, `midi_stream.cpp`, `firmware/third_party/dinghy/hal/fm1_uart.h`, or `src/platform.c`. The target report hashes linked objects, while full source identity must come from the enclosing immutable source commit/archive provenance. Do not treat `catalogue_source_freshness_verified` alone as a source pin for UART behavior; retain the outer clean-source snapshot/commit binding when reproducing a target link.
- The software tests do not exercise UART registers, PH8 electrical behavior, DMA concurrency, MIDI throughput under rendering load, or audible response. The implementation and pulse remain diagnostic and `hardware_tested=false`.
- Serena and Rarefaction were not used on the isolated Hera worktree: their active selections were the Mac repository root; neither was retargeted to avoid disturbing shared sessions. Direct source inspection plus focused pytest was used instead.

## Checks

On Hera, with `/home/claude/.cache/lunar-host-set-fixtures-venv/bin/pytest`:

```text
pytest -q -p no:cacheprovider --basetemp=/tmp/uart1-midi-review-pytest \
  tests/test_native_midi_uart_stream.py \
  tests/test_native_midi_builder_option.py \
  tests/test_native_midi_diagnostic_readout.py \
  tests/test_native_trio_diagnostic_pulse.py
10 passed
```

No source files were edited in this review. The review note and coordination handoff are the only intended changes.
