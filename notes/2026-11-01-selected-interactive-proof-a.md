# Selected Trio interactive checkpoint A

Personal, non-commercial. Source base `ca45926a0cfdbfc6ebf45573446c80b270ea2b92`.

[verified] Initial interface checkpoint adds an opt-in actual selected-app owner,
caller-owned SPSC queues, injected startup facade and nonblocking host SPI model.
Accepted scanner hooks default to no-op; default diagnostic selection is unchanged.
No shared builder, target profile, MMIO adapter or hardware activation is added.

[verified] Small host tests pass: 11 SPI cases (all 240 rows, delayed/immediate
completion, stopped clock, error, timeout, lease and ticket wrap) and the actual
imported scanner (93 accepted events, all 41 matrix IDs and seven detents,
debounce/bounce/order). System Python lacked pytest; repository venv succeeded.

WIP: actual fixed-Trio app PCM/control/draw oracle, composition failures, sanitizer
runs and frame inspection remain. Do not integrate this checkpoint as accepted.
Parent reserved Aeon CPUs 0–3 / max 4 CPU / 6 GiB for focused host tests only.
Products stay under this worktree's scratch or a uniquely owned remote stage;
retain small logs/frame/receipt and remove reproducible build products on exit.
No device, service, reset, ROM, storage, CPU1 or target authority is implied.
