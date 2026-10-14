# UART1 MIDI overflow fix and source provenance review

Reviewed exact commit `66196f54f3295cfdec14a2924c767235bbd5cc2c` on `coordinator-uart-overflow-fix-20261014`. Review is source and host-test only. No target build or device action was performed.

## Overflow correction

[verified] The prior defect is corrected in `firmware/native/midi_uart_stream.c`: the overflow path advances to `(cursor + pending + newly_received) % ring_bytes` using a 64-bit intermediate, clears pending bytes, resets parser state, and refuses the current drain. This uses the complete count of bytes since the previous cursor position and handles the caller-validated upper bounds without 32-bit addition overflow.

[verified] `tests/test_native_midi_uart_stream.py` adds the capacity-8 counterexample: cursor 0, pending 5, newly received 4 gives cursor 1 and pending 0; a fresh complete MIDI event at index 1 is consumed and emitted. That distinguishes the corrected head from the stale cursor the old expression produced. The change is narrowly scoped to the software ring accounting. I approve this bounded source fix and its regression.

## Provenance boundary

[verified] `tools/native/compile_catalogue.py::source_manifest()` is specifically a cached engine/catalogue input manifest. Its roots are `engines`, `sim/web/src`, `sim/web/mk`, plus `tools/jieli/objects.mk` and `compile_catalogue.py`. A direct check against the current function confirmed that it does not include `firmware/native/midi_stream.cpp`, `midi_stream.h`, `midi_uart_stream.c`, `midi_uart_stream.h`, `midi_input.h`, `app_probe.c`, or the Dinghy `hal/fm1_uart.h` and `src/platform.c` paths.

[verified] The Dinghy inventory separately pins `hal/fm1_uart.h` and records the local `src/platform.c` modification. It is not an inventory for first-party `firmware/native` sources. `build_application_probe.py` compiles the MIDI adapter C file and C++ parser directly, and its verification report hashes linked objects and records the MIDI build configuration. The `catalogue_source_freshness_verified` flag only establishes the cached catalogue check; it does not by itself pin these extra source inputs. Reproduction and attribution of UART behavior therefore need the enclosing clean source snapshot/commit and corresponding build provenance, in addition to the linked-object hashes. Do not broaden the catalogue manifest and imply that doing so would replace the full source-tree pin.

## Validation and remaining limits

The exact focused four-file host suite passed (10 tests): UART ring adapter, MIDI parser, builder option, diagnostic readout, and Trio pulse tests. This verifies host compilation/linkage and modeled behavior, not pi32v2 code generation or target registers.

The fix does not settle the HAL's documented polled receive-count limitation. `fm1_uart1_rx_take()` may miss a byte; the software has no explicit lost-byte counter. Exact HRXCNT/RDC/pending semantics, PH8 electrical behavior, DMA concurrency, input under rendering load, and audible performance remain target/hardware checks. No physical acceptance is inferred.

The separate full review note remains at `notes/2026-10-14-uart1-midi-review.md`; it contains the C/C++ linkage, initialization, pulse gating, ADC, HAL and source-freshness details. Serena/Rarefaction were not retargeted to this isolated Hera worktree because their active project selection is the Mac checkout.
