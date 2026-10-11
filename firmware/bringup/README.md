# Offline display/recovery composition

[verified: source] `bringup.c` joins the existing panel protocol emitter and
recovery requester. It accepts already initialized `lunar_panel_transport` and
`lunar_recovery` references; it does not initialize hardware. No boot image,
raw-flash staging profile or package profile includes it. `hardware_ready=false`.

Use zero-initialized controller storage, software-only `lunar_bringup_bind`,
then at most one `lunar_bringup_run`. Bind validates both interfaces, all required
callbacks, recovery state/poll bounds and dwell 0–1000 ms without callbacks.
References and contexts must remain valid and exclusively owned throughout the
run. Arbitrary dangling pointers cannot be validated in C. The caller must not
alter or reset a used controller or concurrently change its components.

Run latches `attempted` before effects and revalidates interfaces. A malformed
interface causes no callbacks or mailbox marker. A valid run calls the actual
`lunar_panel_probe`; successful display may dwell through the same transport's
`wait_ms`. Failed display skips dwell. It calls the transport's `end` before
exactly one `lunar_recovery_request`, including display, transfer and timer
failures. Second run and attempted-controller rebind cause no I/O. It never
clears the marker, erases flash or retries the recovery request.

`display`, `dwell`, `recovery_requested` and `request_transmitted` are separate
results. COMPLETE denotes finished software orchestration even on failure.
The request's transmission result does not prove reset, USB enumeration or
usable recovery. A failed request may leave a retained marker: inspect the
recorded state and follow the existing recovery plan, never replay this handle.

[verified: host simulation] `tests/test_bringup.py` compiles actual panel, SPI1,
TIMER4 and recovery C with warnings as errors. Its C register simulator routes
actual SPI1 `wait_ms` through `lunar_timer_delay`. Simulated setup/pixel completion
loss, stuck completion clear, timer failure, mailbox corruption and P33 timeout
exercise finite callbacks, cleanup-before-request and non-replay. The simulation
performs SPI configuration against arrays solely to model an initialized bus.

Native object compilation checks code generation and dependencies only. Neither
host tests nor target compilation establish the current core, IRQ/exception/SSP
contract, clock rates, power, exclusive peripherals, watchdog behavior, retained
mailbox semantics or PA2's electrical role. No bootstrap or activation permit is
introduced. Native activation and actual display/USB recovery remain open gates.
