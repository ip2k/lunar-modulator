# Continuous-image TRS MIDI requirement

[verified: source inspection] The UART1 PH8 receiver and shared USB/TRS MIDI
Start/Continue/Stop dispatch already exist. The continuous high-level producer
previously omitted --enable-trs-midi; only the fixed song diagnostic enabled
it. A continuous image could therefore pass its receipt policy with TRS disabled.

The high-level continuous build now requests that flag independently of any
diagnostic optimization/telemetry profile. Its checked receipt requires the
exact existing enabled receiver policy (256-byte ring,32bytes/poll,USB preserved,
hardware_tested=false) and one linked object for each UART parser input, with
SHA256 identities. It preserves the checked policy in image.json. Tuple capture
requires the image and lower build policy to match, including JSON boolean types.
Diagnostic mode policy remains unchanged. No device operation or hardware
acceptance is granted.

[verified: focused host suites] Controller/tuple, UART parser/ingress, continuous
wrapper and GPL source bundle suites passed with two skips; diffcheck passed.
Tests exercise actual lower-builder argv, disabled/changed/missing MIDI receipt,
missing/duplicate parser object, malformed digest and boolean/integer substitution.
Independent review and fresh target fit are pending at this checkpoint. This
patch changes the candidate source and binary identities. The preceding exact
source/trace reproduction remains historical evidence for its original tuple;
it must not be relabelled as the new MIDI-enabled candidate.

Serena and Rarefaction still select the sibling primary checkout. Their bounded
absolute-path queries rejected this integration worktree (outside root / only C++
server active); inspection used actual worktree files without retargeting shared
servers. This does not provide semantic index coverage for the patch.


[verified: independent review report] No actionable issue found in the four-file
source/test patch. Import graph and source-export coverage were checked; reviewer
reran diffcheck but did not duplicate host tests. Report SHA256
`64f6efd688096d547d2c881753744cf81947b05d8dcac70ecfdc2e33589d9778`.
Implementation pushed and remote SHA verified:
`e7b65f1a103ac049ff4f898c7980b10433ca2ecb`. Full CI39002512160 was dispatched
for that exact source commit and independently observed with live jobs; success
is not yet claimed. The Aeon worker is preparing a fresh target build from the
exact transferred Git base. Reusing the old catalogue requires an unchanged
catalogue source manifest; it is not permission to reseal changed cached inputs.
Target fit and physical acceptance remain pending.


## Fresh Aeon build result

[verified: canonical output rehash and receipt inspection] Exact source
`e7b65f1a103ac049ff4f898c7980b10433ca2ecb` built successfully on Aeon.
Tuple `continuous-ef8fc7af36a40c874b303435` has SHA256
`1564cfb7716bc51d9ae6afa2f8aa8be6bede4980db6a1a1e079052cb16364ca9`.
App: 854,528 bytes, SHA256
`f91bc8da94ddbf40ef1a75e85bf8802aef28a5b153025ce7f1d420e056907338`;
ELF SHA256 `1f4c007df2216721fd44dd380b242d604930a812be9c813c4ed675ace2e5b132`.
Expanded D7000 budget is 860,644 bytes, leaving 6,116 bytes. All 55 selected
modules, Shapes 8, Event Horizon project and companion SET remain included.
Both MIDI parser object files were independently rehashed and each occurs once
as a LOAD input in the map. USB MIDI is preserved alongside UART1 RX/PH8.
No SDK archives are linked; key and RAM-call audits passed.

[verified: retained terminal container inspection] Exit code 0; 4 CPUs,
8 GiB memory/swap-total, 512 pids, docker-batch.slice, no network, read-only
root and input mounts, cap-drop ALL, no-new-privileges. The receipt records
Docker create with auto_remove=false; the container is now absent. Do not
attribute its removal to --rm. Codec rebuild hash matches the prior retained
binary, but host compiler dependency tracing is not covered.

RAM storage reports RGB565 220,848 bytes, indexed 163,760 bytes and pool
165,376 bytes. Stack-watermark instrumentation is present, not a worst-case
stack proof. SAVE remains linked but disarmed, without storage admission or
live flash binding. Hardware testing, runtime verification, installability
and distribution completeness remain false. The earlier hardware audio
failure is not resolved by a successful build. Prior compiler traces belong
to the old tuple; fresh source closure is the next offline dependency.

Routing: Aeon only while the owner performs RAID/M.2/NIC maintenance on Hera.
No Hera probes or device operations were performed. CI39002512160 for E7
currently has seven successful jobs and eight running, with no failure yet.
