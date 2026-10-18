# Offline terminal telemetry repair — verified offline milestone

Base1499f3238531160f06d1aa23a34e05bce13232e7, existing feature stream.
[verified: source review] Core exports the existing persistent candidate latch;
no FSM/output assignment changes. Top uses UsbKeyTerminalSnapshot for its actual
one-shot capture, retains0x0e, adds0x67 and identifies all profiles as layout9.
Existing layout7/8 fields remain unchanged. No tracked hardware register reader
consumes LUNR; private scratch readers pin layout8 and must not be used with9.
The new decoder is pure offline and preserves unknown legacy candidate status.

[verified: local simulation] Existing eight modules plus new terminal module:
130 passed,348 warnings,24.70s. Production60MHz tests cover earlier candidate
with WAIT timeout/FAULT, earlier candidate with SOF/DONE, no-candidate packet
limit/FAULT, stable terminal retention, domain reset and preterminal validity.
Counters/profile lengths are shortened to bound simulation, not the divider.
Four actual board-top/profile elaborations also check layout9, legacy addresses
and the new persistent receipt mapping. Focused module:11 passed/167 warnings.
A temporary mutation replacing the new persistent snapshot input with the old
transient input fails both candidate cases; no-candidate passes. Restored source
before full suite. This demonstrates sensitivity to the reviewed defect; it is
not a device or analog oracle.

Command: PYTHONPATH=/Users/likwid/.local/share/uv/tools/cynthion/lib/python3.12/site-packages
/tmp/lunar-installer-service-test-venv/bin/python -m pytest -o addopts=
-p no:cacheprovider [the eight modules in the implementation handoff]
tests/test_cynthion_usb_key_terminal.py.
Exact logs and mutation driver: scratch/cynthion-terminal-fix-20261018/.

[verified: fresh offline Aeon builds] Source pin
13cca5c117e5024a07c2544d42da63f4bf3d22b5; six actual synthesis inputs still
match current files. Both isolated builds exited0 without OOM. Final routed
60/120MHz results: operation66.22/201.29MHz; pico-repeat69.70/187.16MHz,
all PASS. Earlier placement estimates failed; final routing passed without
allow-fail flags. Neither image was loaded. Exact pins, timing, generated
constraints/commands, project bitstreams, test/mutation logs and container
policy receipts are in [the new packet](reviews/2026-10-18-cynthion-terminal-fix/README.md).

[verified: coordinator review] Reviewed changed core/top/decoder/tests,
legacy compatibility, persistent latch/reset/one-shot semantics, unchanged
waveform/FSM/PHY/power settings, pins and final routed results. This is not a
new independent approval. Rarefaction and Serena selected the separate primary
checkout; real-file queries failed there. Direct worktree source inspection was
used, without retargeting another active session's shared semantic server.

[verified: archive integrity] All401 historical packet checksums pass; no
change under that packet since1499f323. The external erratum preserves the
historical0x18d narratives unchanged. Preserve unrelated untrackeduv.lock.

The [scope preparation](2026-10-18-cynthion-ds1054z-scope-plan.md) incorporates
the owner's RigolDS1054Z/probes and pictured six-pin breakout. Its likely5.1kΩ
CC sink resistors require continuity verification; cable colours are insufficient.
Second-board wiring, continuity-meter availability, scope interface and grounding
remain dependencies. The scope cannot promise the audit's continuous56s record
at≥1MS/s with3channels. A two-window alternative requires independent review,
explicit coverage approval and separately authorized scope-only qualification.
No gateware load, device readout, probing, power cycle, flash or infrastructure
change occurred during this milestone. Recovery remains unproven. No merge of
the unfinished firmware stream is authorized by these offline receipts.

[verified: reference source inspected via GitHub API,2026-10-18]
The [Pico example](https://gist.github.com/czietz/9a94cf3c3e68f2ceb45fab682e1cbbd5)
loops3000 SPI writes at nominal50kHz and then2s of1kHz PWM before repeating.
SPI construction/deinitialization adds unmeasured gaps; it is not uninterrupted
key transmission. Current gateware uses explicit160µs gaps and2s PWM:
3.44s/cycle,16cycles=55.04s. Neither schedule is established as sufficient for
this unit. Faster repetition or watching a line-state change is a future
hypothesis, not a justified waveform change or proof of ROM entry; enumeration
needs an isolated host handoff. No protocol change was made in response.
