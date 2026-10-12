# Resumed diagnostic startup and recovery review

[verified: bounded source inspection] Five complete files are recorded with
hashes and line counts in `2026-10-12-diagnostic-startup-review.json`. This is
root inspection, not independent acceptance or completion of the overdue
whole-repository audit. Vendor runtime instruction review and hardware
behavior remain separate requirements.

- `app_main` creates the diagnostic worker and returns. Clock/GPIO/SPI setup
  failures and positive panel errors all reach the soak and recovery attempt.
  The soak bounds its iteration count, but every scheduler delay still requires
  a functioning scheduler. The worker yields during the full display transfer.
- SPI completion waits have finite read budgets, reject stale completion,
  disable SPI before releasing chip select on failure, and latch the failed
  transport. Successful return is a protocol result, not observed pixels.
- Recovery verifies all sixteen mailbox bytes before the fixed P33 reset
  operation. It consumes the attempt before I/O and does not automatically
  retry after failure. Mailbox contents can remain after a failed transfer.
  Successful transmission does not prove reset or UBOOT enumeration.
- P33 lock acquisition can wait indefinitely if another core halts while
  holding the lock. These source properties support healthy-runtime recovery,
  not recovery from arbitrary CPU/scheduler faults. Cynthion's USB power switch
  is not established as a battery-powered FM-1 CPU power-cycle mechanism.
- The RAM trace uses odd/even publication, barriers, a phase complement and
  an image nonce. It records reset intent and software state; it cannot prove
  visible display output, reset cause or RAM retention by itself.

[verified: documentation correction] `firmware/recovery/README.md` previously
claimed no boot image linked this component. It now distinguishes the earlier
SDK-free profile from the private SDK diagnostic, whose builder lists
`request.c` and whose worker calls the request. No firmware source or image
changed in this documentation correction.

Next: finish the current-reader V6k retained model verification; review its
exact source closure and a fresh one-use hardware recovery plan. Keep consumed
campaigns and their timestamps unchanged. On ambiguous hardware replies,
observe enumeration and preserve evidence before considering another action.
An interrupted physical write, arbitrary hang rescue and the diagnostic
image's visible display acceptance remain unproven.
