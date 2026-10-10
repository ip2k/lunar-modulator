# DX7 native import counter saturation

Audit follow-up: batch 40, P3, in
[the full audit](2026-10-07-full-code-audit.md).

The public parser stores every voice in concatenated dumps, but its report
uses 16-bit counts. Exactly 2,048 VMEM banks store 65,536 voices and previously
returned zero. The instance importer uses a positive return to invalidate
patch/LFO caches, so a successful bank replacement could skip that work
[verified: first-party parser and `msfa_dx7.cc` call flow]. Browser imports
are capped at 64 KiB and cannot reach this particular case.

The fix saturates all 16-bit report counters at 65,535 while parsing and
storing continue. Public struct layout, slot mapping, accepted data and
vendored msfa source remain unchanged. Native callers receive a positive
return after any successful store; a saturated report is a lower bound,
not an exact total. The C header documents this contract.

`tests/test_dx7_counter_bounds.py` compiles the real parser with the existing
msfa namespace wrapper and unmodified upstream `patch.cc`. Five regressions
exercise 2,048 banks, 65,537 single-voice messages with bad checksums, and
65,537 foreign, truncated or wrong-size messages. The tests verify continued
stores and the final voice/slot, saturated reports, and exact small imports.

Validation [verified, aeon, bounded Docker `lunar-asan:ubuntu-24.04`]:

- Before the fix: all five regression cases fail.
- After the fix: five pass under AddressSanitizer and UndefinedBehaviorSanitizer.
- No device traffic or hardware validation was performed.

Branch: `fix/2026-10-09@dx7-counter-saturation`. This note is the recovery
pointer for this bounded follow-up; CI and merge remain separate gates.
