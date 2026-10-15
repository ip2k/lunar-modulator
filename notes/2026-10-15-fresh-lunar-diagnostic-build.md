# Fresh 9ec846 diagnostic link

[verified] A fresh private native diagnostic link was produced from source
commit 9ec846b0f4745345ab1d4da9700933be48e3d50e, tree
16150837d87cd76eacec5c5076db2f8874bac310. The exact source archive is
/home/claude/.local/share/codex-private/fresh-lunar-diagnostic-build-20261014/run1/source.tar
(SHA256 c42f9d38e1ce0a59bcfd3c1c7495628f926566695df286e51a3572a7ac23950e).
The source manifest is SHA256
a8616b44a4359478b6a0bf8a6f2a3594f533e1eef562e591a9279a78374a5bc1.

[verified] The 16-shard catalogue contains 167 objects, zero failed objects,
536 source files, and every shard reports the same source manifest. The linked
profile was deliberately set to the exact 54-module contract expected by the
current diagnostic transaction policy: all thirteen production engines remain
selected; compared with the initial 55-module profile, the only omitted entry
is the plate effect. This is a prepared profile choice, not a change to the
all-thirteen-engine requirement. Profile SHA256 is
c93f73a29b6e7df951046f345ee6ff750e2df3dcb9b740d1a277da51bf0be100; generated
module header SHA256 is 2c54555e8026299cde5bf896e19b600421480acd402886519f55ef22e8de8a18.

[reported] The build used the pinned pi32v2 toolchain tree manifest
41e95ab855ad2bcd1346e9a89aa7d30bed28d660e0b9053d4ce1dc43e236dede and
container image ID
sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc.
The requested link configuration was explicit FM-1_500, song-diagnostic,
expanded-d7000, stack watermark, SAVE linked but disarmed, TRS MIDI enabled,
compressed wavetables, Shapes 8 voices, and the one-shot Trio C4 pulse.
The build command is recorded in the private evidence receipt. The recorded
resource limits were docker-batch.slice, 2 CPUs, 8 GiB memory, 16 GiB memory
plus swap ceiling, 512 pids, network disabled, read-only rootfs and a bounded
/tmp tmpfs.

[verified] build_application_probe.py completed its link and audits. The
ELF is 936,220 bytes, SHA256
ce98f0fdf20e051ed5d9beedce9f601fd806ec1dc28cccaf5224667eee7947da; the
application is 807,740 bytes, SHA256
18d6bb321b2dfb3a42e25c9bb37fc4eeb3b92c13ac3c494d52c1b7bbc55fc0db. Its
860,644-byte application budget leaves 52,904 bytes. The verification record
is SHA256 9e94a853b02641e3efd3cdcbca67a8f0a95b284455ecb0a96e69022c67f56890.
The key audit passed; the RAM-call audit contains only the allowlisted
fl_jedec_ram -> fl_jedec_checked_ram call. The build records app identity
FM-1_500 and recovery identity FM-1_000 explicitly.

[verified] Telemetry is gated by LUNAR_DIAGNOSTIC_TRIO_PULSE=1; the receipt
specifies one note 60 / velocity 100 pulse from 3000 to 5000 ms and states
hardware-tested false. Watermark patterns cover 24,320 user-stack bytes and
7,936 system-stack bytes, but worst_case_stack_bound is false. This link
therefore gives no measured stack margin, telemetry delivery, runtime, audio,
perceptual, updater or installability result. hardware_admitted,
hardware_tested, and installable all remain false. No device operation was
performed by this task.

[verified] generic_diagnostic_flash._check_build() accepted the exact linked
artifacts and the 54-module/all-thirteen profile when run against the private
build evidence record. This is an artifact-contract check; it is not a live
read, install authorization, or physical acceptance.

[verified] Private evidence is under
/home/claude/.local/share/codex-private/fresh-lunar-diagnostic-build-20261014/run1/.
The compatible evidence record is
writable-v2/build-evidence-record.json (SHA256
b5840092dd0ee0faa7cbad8e11428f0cd7d14c604f172ae262c54a66a2a4b87f), and
its build receipt is
writable-v2/frozen-build-input-receipt.json (SHA256
fd93f75315b0f0b9023340b68c6c264dfac7763e65b23ad4556bf8988c4ddff8). These
were assembled retrospectively from retained source, manifest, catalogue,
profile, verification and output files to satisfy the current receipt schema.
The container create/inspect transcript was not retained, so the receipt
states that its execution configuration is not independently attested; the
resource parameters above are the recorded task run settings, not a retained
Docker inspect proof. Do not describe this receipt as having been frozen before
linking or as a standard build_tuple.json / image.json.

## Next dependency

Coordinator review must decide whether this retrospective provenance is
sufficient for the private offline candidate pipeline or whether a new build
must persist container inspection evidence at execution time. Any later
hardware test remains a separate coordinator-owned admission and listening
step; this note does not authorize it.
