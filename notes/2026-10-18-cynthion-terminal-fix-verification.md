# Offline terminal telemetry repair — implementation checkpoint

Base1499f3238531160f06d1aa23a34e05bce13232e7, existing feature stream.
[verified: source review] Core exports the existing persistent candidate latch;
no FSM/output assignment changes. Top uses UsbKeyTerminalSnapshot for its actual
one-shot capture, retains0x0e, adds0x67 and identifies all profiles as layout9.
Existing layout7/8 fields remain unchanged. No tracked hardware register reader
consumes LUNR; private scratch readers pin layout8 and must not be used with9.
The new decoder is pure offline and preserves unknown legacy candidate status.

[verified: local simulation] Existing eight modules plus new terminal module:
126passed,200warnings,21.87s. Production60MHz tests cover earlier candidate
with WAIT timeout/FAULT, earlier candidate with SOF/DONE, no-candidate packet
limit/FAULT, stable terminal retention, domain reset and preterminal validity.
Counters/profile lengths are shortened to bound simulation, not the divider.
A temporary mutation replacing the new persistent snapshot input with the old
transient input fails both candidate cases; no-candidate passes. Restored source
before full suite. This demonstrates sensitivity to the reviewed defect; it is
not a device or analog oracle.

Command: PYTHONPATH=/Users/likwid/.local/share/uv/tools/cynthion/lib/python3.12/site-packages
/tmp/lunar-installer-service-test-venv/bin/python -m pytest -o addopts=
-p no:cacheprovider [the eight modules in the implementation handoff]
tests/test_cynthion_usb_key_terminal.py.
Exact logs and mutation driver: scratch/cynthion-terminal-fix-20261018/.

WIP dependency: fresh pinned Aeon synthesis/routing evidence and final review
are pending. The original checksum-covered packet is untouched. Scope plan
uses owner-reported RigolDS1054Z,4stockprobes,4x50ohmterminators,two6pinUSBC
breakouts and two4wireUSB-C/DuPont cables. Fixture continuity/CC/ground and
capture memory remain unresolved; no physical operation authorized or executed.
Recovery remains unproven. Preserve unrelateduv.lock; do not merge this stream.
