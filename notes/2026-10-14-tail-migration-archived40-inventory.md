# Archived device40 storage trailer inventory

[verified: offline archive analysis] The coordinator ran
`analyze_first_format()` against the two saved full-flash reads in the private
`build/event120-repeat40-private.tar` archive. Both match SHA-256
`145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`.
The caller identity was explicitly labelled `archived-device40-event120`;
this is not a fresh current-device acquisition or admission receipt.

Of the 24 proposed mapped sectors, eight have non-erased final 256-byte pages:
`0xEA000`, `0xEB000`, `0xEC000`, `0xED000`, `0xEE000`, `0xEF000`,
`0xF0000`, and `0xF1000`. No mapped page currently matches the modeled SPL
outer-record or retained cleanup-record predicate. The analyzer nevertheless
reports `record_page_precondition_refused`: current invalid records do not
prove their behavior throughout a partial erase.

The complete analysis JSON remains private at
`build/browser-set-review/device40-tail-analysis-private.json`. No stock
bytes, vendor binary or raw page data are published in this note. Analysis
used the existing local archive; the only bench access listed directory
metadata. No USB, MIDI, flash, reset or power command was issued.

This identifies actual archived hazards for the next migration/recovery
design. It does not establish semantic stock migration, interrupted first
format safety, physical rollback, or project SAVE admission. Ten focused
planner tests pass locally. The full native/web release goal remains active.
