# Cynthion candidate ACK duration resets at packet gaps

## Change

`tools/cynthion_usb_key/gateware.py` now clears `ack_ticks` on the final KEY
bit's transition into GAP. Candidate duration therefore cannot sum SE0 time on
opposite sides of the released inter-packet interval. The change deliberately
preserves `receiver_live`, `line_state_valid`, and the cached RXCMD line state.
The receiver still requires its matching high-phase witness, and event-on-change
RXCMD is not treated as a periodic sampler.

## Regression coverage

`tests/test_cynthion_usb_key_ack_gap_reset.py` verifies that (1) 99 candidate
ticks before GAP cannot combine with the next packet to produce an immediate
ACK, (2) a held cached SE0 can still confirm after 100 KEY microseconds in the
next packet without synthetic periodic updates, and (3) cached SE0 without the
high-phase receiver witness never confirms and terminates at the configured
packet limit.

Verification used a temporary `uv run --no-project --with pytest --with
'amaranth>=0.5,<0.6'` environment; no project environment was changed. The new
tests plus `tests/test_cynthion_usb_key_protocol_review.py` passed: 7 passed.
Amaranth emitted only the pre-existing `reset=` deprecation warning. The
repository `.venv` lacks Amaranth, so its direct pytest attempt collected zero
tests due module skip. No FPGA/bitstream build or device operation was run.

## Limits and tool coverage

These are RTL simulations of counter/FSM semantics, not evidence of continuous
USB3343 sampling, electrical ACK validity, ROM recognition, or FM-1 behavior.
Rarefaction's configured workspace root is the separate primary checkout, and
its API rejected this worktree as outside that root. Serena's current project
selection belonged to the unrelated `offline-audio-budget-audit` worktree; it
was not retargeted to avoid changing another active session. Source/test
references were checked directly against this exact commit's files.

## Handoff

- Exact base: `3f183ef0909d499f7b0750e0c058138d885c4703`
- Branch: `fix/2026-10-15@ack-gap-duration-reset`
- Worktree: `/Users/likwid/.codex/worktrees/cynthion-ack-gap-reset`
- State: implementation, focused tests, and note are committed; the explicit
  branch push to authorized `origin` was verified against the same remote SHA.
- Next: root reviews and chooses the integration point; no hardware/build action
  is part of this change.
