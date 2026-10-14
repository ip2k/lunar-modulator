# Stock SPL path with invalid application and no valid rescue record

Date: 2026-10-14. Offline, read-only control-flow investigation. No device,
USB, MIDI, flash, power, reset, install, or runtime operation occurred.

## Finding

[verified from pinned bytes and decoded control flow] In the examined FM-1_092
stock SPL, when ordinary application selection fails and the conditional
trailing-record scan reaches its lower bound without finding a valid record,
the path does not branch to mask ROM, a USB updater, or an application entry.
It reaches the helper at SPL file offset 0x07da; that helper's inspected
paths converge on a write to address 0x00010000 followed by an unconditional
self-loop at 0x090c. The caller also has a self-loop at 0x28de after the
helper call, but that continuation is not reached if the helper follows its
observed loop. This is a terminal SPL control-flow path, not proof of a
particular physical symptom (hang, reset, or USB enumeration).

Therefore the SPL record mechanism supplies no software-only fallback where
the app header is invalid and no valid rescue record exists. A rollback
transaction that can enter this state has no demonstrated SPL path back to a
loader or normal application. A separately verified ROM/USB_KEY recovery
route is still required; this disassembly does not establish that route's
availability after this state or its ability to restore the device.

## Evidence and control-flow derivation

[verified] Inputs match the preceding byte review: retained FM-1_092 reference
SPL `reference/top/uboot.boot`, 14,384 bytes, SHA-256
`730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef`;
the existing vendor-decoded file
`/tmp/lunar-spl-record-byte-review/spl-decoded.bin` has the same SHA-256 and
`cmp` reports byte-identical. Its ELF32 pi32v2 listing
`/tmp/lunar-spl-record-byte-review/spl.lst` was produced by pinned JieLi LLVM
4.0.1 pi32v2 vendor objdump, not Ghidra. The prior review documents the
wrapper, toolchain and bounded offline environment. Raw binaries/listings
remain private and are not added to Git.

[verified] The relevant scan and no-record path, using complete-SPL-file
offsets, is:

1. At 0x2e08, bytes `0d f8 b6 00` branch to 0x2f78 if r13 == 0 (ordinary
   app already selected). Otherwise the trailing flash-record loop begins.
2. For the recorded 1 MiB / 4 KiB geometry, the existing byte review derives
   candidate records at boundary - 0x100, from 0xfef00 down to 0x01f00.
   Each candidate must satisfy the signature, CRC, and nonzero-field checks.
3. At 0x2e36, bytes `29 ff 80 7d 7b 02` branch to 0x3332 when the next
   boundary in r7 is <= 0x1000. With every candidate absent or rejected,
   the decrement at 0x2e34 eventually reaches this condition. This is the
   no-valid-record exit after the complete scan, not an assumption based only
   on a string or scan range.
4. At 0x3332, bytes `40 20` set r0 = 0; 0x3334, bytes
   `50 ed a3 00`, store zero at [r10+2]; 0x3338, bytes
   `ff ea cf fa`, branch to 0x28da.
5. At 0x28da, bytes `bf ea 7e ef` call the helper at 0x07da. Inspection of
   that helper shows its validation branches converge at 0x0904, whose bytes
   `60 e0 80 0b` set bit 0x10 at address 0x00010000; 0x090c, bytes
   `f7 9f`, branches to itself. No return from this path is shown.
6. The caller continuation at 0x28de is itself bytes `f7 9f`, also a
   self-branch. Neither branch is a transfer to ROM or the USB updater.

These are SPL file offsets including its 16-byte bank header. The body-to-RAM
mapping documented in `notes/2026-10-11-stock-spl-final-contract.md` is
`0x01c02000 + file_offset - 16`; for example, the no-record branch at file
offset 0x3338 maps to 0x01c05328, helper loop 0x090c to 0x01c028fc, and
caller loop 0x28de to 0x01c048ce.

## Transaction implication

[verified control-flow consequence; inferred transaction risk] If power loss
or a failed restore leaves the application-area header invalid while its
rescue record is absent, corrupt, or already removed, this SPL path does not
supply an automatic software recovery entry. Restoring the last USR sectors
alone is not sufficient to claim rollback safety: if the final phase removes
the last valid rescue record before the app header is valid, the cut point
matches this no-record path. Conversely, retaining a record is only useful if
its referenced payload and header remain valid and its sectors are not being
modified; CRC checking alone is not authentication or transactional proof.

A future rollback design must keep a stock-recognized valid record and its
complete referenced loader intact until the application header and required
state have been validated, or rely on a different independently proven
recovery mechanism. The existing SPL scan is broad and conditional; it does
not grant ownership of any sector. If a transaction cannot guarantee the
record+payload invariant across every erase/program cut point, offline
planning must state that manual ROM/USB_KEY recovery is the fallback and that
software-only rollback is not guaranteed. Do not weaken stock boot-component
protection or reserve sectors based on this finding.

## Limits and next dependency

- The inputs are an old retained matching capture/package and exact SPL bytes,
  not a fresh device observation. No target execution or failure injection
  occurred.
- The terminal control flow is proven in the decoded SPL; the physical result
  of the 0x00010000 write, any independent reset source, watchdog behavior
  under this invalid-app route, and ROM USB_KEY entry are not determined here.
  Do not label the observed loop a physical hang or assert that USB recovery
  cannot work through a separate owner-operated entry path.
- The scan predicates are CRC/signature checks, not cryptographic
  authentication. The analysis assumes all candidate records are absent or
  rejected as specified in the task; it does not claim the saved stock image
  lacks a valid record.
- Exact transaction cutpoints, app-header commit order, referenced-loader
  preservation and physical recovery usability remain separate gates.

Next dependency: design review must choose and test (offline first) an ordered
rollback transaction preserving a complete valid rescue record+loader through
every unsafe app-header interval, or explicitly depend on the separately
reviewed USB_KEY/ROM recovery campaign. Hardware authorization and physical
recovery validation remain with the coordinator.
