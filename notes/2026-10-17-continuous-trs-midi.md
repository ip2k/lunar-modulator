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
