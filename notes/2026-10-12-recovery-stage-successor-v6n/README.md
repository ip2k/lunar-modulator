# Historical capture identity regression and corrected successor

[verified] Source review rejected V6k before integration or hardware activation. Its global SHA replacement mapped the historical install wrapper identity `7d2cec8584bc274c534046d490f3c319bd7e0c13dec6d1f654323e9c9aa8dd8b` to the current identity `59b8e8c23f494f0ac6c89585786f72a9b408d5692e2a5fbf66c2c0376945c52d`, changing both the recovery policy and its fixture assertion. V6k/L/M passing results therefore do not establish preservation of historical evidence support. Retain their evidence, but do not integrate or activate V6k.

[verified] V6n starts from immutable V6g, installs the current RAM reader and strict fixture, excludes the historical identity from transitive dependency replacement, and AST-checks the two distinct policy constants. It includes all lifecycle Python sources and the independently pinned historical wrapper; the 16O campaign adds the previously omitted allowlist and outer lifecycle tests. The 16P campaign requires all 71 native fixture checks. Both campaigns and the full heavy model are running on Hera, not yet accepted. No device operations were issued for this correction.

Archive SHA256: `4592dc9faeedc28915d8ac7c1e8330ff7c03f388750de446018514d6365c3e85`.
Runner SHA256: `ebfc57e4a95960de98535c4bcfd4d7d1d3e2817d2f048c7cd7678d0a373e25bb`.
Private outputs remain under ignored `build/`; source-delta.json records the exact closure. Production policy still preserves both hashes and has not been replaced with the proposed closure.

Next: verify complete 16O/16P and heavy terminal evidence, inspect semantic changes, integrate corrected pins, run exact-head CI, and prepare a fresh physical campaign retaining stock SPL/OTA/cfg and dual-backup safeguards. A model pass does not prove physical boot, display, USB reset, or recovery.
