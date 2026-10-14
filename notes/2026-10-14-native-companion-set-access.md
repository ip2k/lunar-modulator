# Native companion SET selection and startup

This branch adds an explicit pre-audio choice for an embedded companion SET while keeping Event Horizon Showcase as the default startup project. The builder derives each SET's parent index from the trusted prepared-selection receipt, embeds that index in the native catalogue, and rejects a SET whose parent does not match the prepared startup project. A project chooser runs first when the image contains multiple projects; the SET chooser then lists only SETs bound to the selected project. Confirm loads the SET through the cold-start staging path. Timeout preserves the selected project's own sequence.

The platform selector is injected only for project-startup images containing multiple projects or at least one companion SET. Both selector polls run before `fm1_audio_init`, scan debounced encoder/button input, feed the watchdog, and use an 8-second timeout. The existing single-project/no-SET image path remains unchanged. This supports explicit selection during cold boot; it does not add hot switching or standalone SET startup.

Companion startup stages the SET into one temporary sequence allocation sized from the initialized app's actual sequence limits, validates its route and parameter locks against the selected parent project's engine plan, activates it into the app sequence, then frees staging before engine allocations. Existing ownership and no-live-pool preconditions remain in force.

Validation on Hera:
- Focused native selection, companion receipt, and project sequence suite: 43 passed, 2 skipped because the generic test image has no JieLi pi32v2 toolchain.
- Selector/receipt tests after the added chooser-order regression: 11 passed.
- Browser-export request interoperability against the committed fixture, using a freshly built `fm1-state` binary and no browser-export environment override: 3 passed (preparation acceptance plus wrong-parent/startup refusals).
- `git diff --check`: passed.

Limits: these are host/parser/sequence tests and a request-to-profile interop check. No target link was run in this task because the assigned Hera checkout had no installed pi32v2 compiler, and no physical device or audio/listening acceptance was performed. The generated selector ordering is covered by a source-level regression; physical control feel, timeout timing on device, and companion audio behavior still require later target and owner acceptance. Device/installability/recovery admission remains false.
