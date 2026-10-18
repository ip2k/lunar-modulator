# Cynthion terminal telemetry erratum

This addendum corrects interpretation outside the immutable
[review packet](reviews/2026-10-18-cynthion-recovery/README.md).
Its checksum-covered contents must not be edited.

[verified: bitwise decode] Historical attempt 5
([trace review](reviews/2026-10-18-cynthion-recovery/evidence/coordinator/cynthion-usb-key-20261016/event-history/attempt5-trace-review.md))
and attempt 6
([source review](reviews/2026-10-18-cynthion-recovery/evidence/coordinator/cynthion-usb-key-20261016/event-history/attempt6-source-review.md))
incorrectly describe `0x18d` as ACK-confirm=1. The actual register-0x0e decode
is receiver-live=1, transient ACK predicate=0, ACK ticks=99:
`0x18d & 1 = 1`, `(0x18d >> 1) & 1 = 0`, `0x18d >> 2 = 99`.
The independent WAIT_DP transition/history bit30 still records a **local
candidate**, which is distinct from the transient predicate and is not proof
of a target or ROM ACK. This correction does not erase that history evidence.

[verified: source] History phase bits18–28 and terminal KEY phase bits8–23
are microsecond phase indices, not 60 MHz USB clock cycles. RXCMD age register
0x63 really is in USB clock cycles; that separate unit is unchanged.

[verified: implementation] Layout9 adds register0x67 (valid bit0, persistent
local candidate bit1). Register0x0e retains its historical transient semantics;
layouts7/8 cannot establish persistent candidate absence from bit1=0. Current
offline decoder returns unknown for that missing field. The repeat profile
bypasses candidate-based progression, so its zero candidate latch is not a
negative target response. No waveform, polarity, pin, resistor or PHY setting
is changed by the telemetry repair. Startup readback, disconnected loopback,
terminal schedule completion and physical recovery remain separate claims.
