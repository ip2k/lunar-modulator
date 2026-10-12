# First retained diagnostic RAM read on the owner's FM-1

Personal bench experiment. Root alone operated the device. This records the
distinct successor after the original target reset and stopped chooser; neither
was repeated. The agreed diagnostic-image goal remains active.

## Actual operation

[verified: executed wrapper and retained native receipt] The independently
reviewed source `70d57d7a3294794ebc84647666bd22f195822027a0c96c22a3ed8495fbe53279`
ran once under concrete wrapper
`77098101427ac6c5a5c4ae64e7730a081ffa22eebb14a1cc1816e85147b264dd`.
The separate passive witness was observed at `1791778215.7622702` for the same
ROM bus 3/device 26 and exact `/dev/sg0` identities. It preserved the original
snapshot bytes and time. The wrapper exited zero and closed its owned capture
with SIGTERM; no reset, loader upload or NOR operation was sent.

[verified: native request log] Exactly two native requests completed, with zero
status, host, driver, residual, info and sense fields: INQUIRY36, followed by
`fd0701c033d80020ffffffffffffffff` IN32/OUT0. Their intents were recorded at
`1791778274.3294735` and `1791778274.4593654`. The record read completed at
`1791778274.585474`.

## Decoded record and boundary

[verified: saved decoder output] The eight 32-bit words are stage6, result0,
sys_hz360000000, lsb_hz60000000, raw_write0x02002d82, elapsed_ms20000,
heartbeat1976 and recovery_result0. Raw SHA256:
`6c802e2ee31cd445beba59540b6208d816e1b47cfea8da2d4aa6ca20e1e43ed1`;
decoded SHA256:
`74ca8bcc3a585b784f954a031f8ee6da5147ce370d78b435621027313a2c5085`.

[inferred] The coherent stage, native pointer, elapsed timer and heartbeat
support execution of this exact installed diagnostic before the ROM read.
Stage6 is stored at native `0x02002b2e` before `p33_lock()` at
`0x02002b34`. The recovery result is assigned only after the request returns,
at `0x02002b6e`; stage7/8 is stored later at `0x02002b7e`. The observed stage6
and recovery_result0 therefore do not prove lock acquisition or transmission
of the recovery request. This is conditional execution evidence: the record does not independently prove RAM retention,
the ROM handler implementation, successful reset completion, recovery cause,
visible pixels or the current CPU state. No camera was available at the bench.
The physical display and completed recovery restoration remain outstanding.

[verified: pinned source and native listing] The timer starts before panel
setup and rendering; elapsed20000 is total worker duration, not an additional
twenty-second display soak. Heartbeat increments after each 256 transmitted
data bytes and each soak tick, so1976 is neither a soak-tick count nor current
liveness. `clk_get()` returns SDK stored state rather than measuring frequency.
The reported sys360MHz differs from the recorded stock240MHz; pinned SDK
`clock.h` permits a24..396MHz switch range. The retained startup configuration
responsible for that report remains unresolved. LSB60MHz and divider4 imply
nominal SPI6MHz under the driver contract, without electrical measurement.

## Durable evidence and next step

[verified] Private artifacts are under
`build/diagnostic-stage-resume-source-staging-v1/actual-two-read-v1/`.
The original export `actual-two-read-evidence.tar` hashes
`b2666a89ba8bdc66b6c6df2a831a7540bb8d6b31899b401e1297aa3bde1174de`.
It contains the new run's eleven owned capture hashes, raw/decoded/result and
structured command log, and its distinct consumed marker. The USB capture
hash is `088a707022379ae2c7078a894055a12e75674fb3b34c02f4842f6dbec3d58320`.
Concrete packet/source-runtime acceptance is retained in
`build/diagnostic-stage-resume-independent-review.md`,
`7a5047ced1653daf39270e1f4d08dc6cecfea948c436037d6f7160f140a94ce7`.
Independent actual capture review accepted the retained evidence,
`build/diagnostic-stage-resume-physical-independent-review.md`,
`99d3c4da28dd5a705d98ee436696b6226649f09e2a83375b0f7748eae43d05f9`.
It independently checked all21 exported files, eleven owned hashes, six
structured events,32 paired bulk events and six BOT commands, including the
exact FD07 payload, tags and zero-residue CSW. The record and native source
interpretation is separately retained in
`build/diagnostic-stage-actual-review/native-interpretation.md`,
`2f6090d485d4ae0f393a4cffdfb9e676400727aa4288a1313236d411d284fec0`.
Both accept the bounded conditional execution claim, with the limits above.

The next hardware dependency is distinct recovery admission for this completed
read lineage. Validate its owned terminal capture, obtain two fresh matching
full target backups with the reviewed loader, then restore stock and verify
all 1 MiB plus normal identity. Preserve every historical marker and receipt;
the old returned-ROM helper remains frozen and still rejects this lineage.
Interrupted/corrupted application recovery remains independently modeled;
warm-reset rescue of such an application and physical USB_KEY are unproved.
