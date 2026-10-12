# One bare-ROM diagnostic-stage capture

[verified source] `tools/fm1_diagnostic_stage_probe.py` is a distinct, injected-only
policy for the current private SDK diagnostic. It exposes no SG opener, ioctl,
hardware CLI, loader upload, reset, arbitrary address/size, or NOR write. Existing
loader/read/install/reset guards are unchanged. Parent owns hardware, commits,
and integration; this source milestone does not complete physical acceptance.

Before this policy, the fixed loader could read memory only after uploading across
the diagnostic's BSS, destroying its stages. The new policy permits one initial
ROM INQUIRY (`120000002400`, IN 36) and one fixed FD07 transfer
(`fd0701c033d80020ffffffffffffffff`, IN 32, OUT 0), before any loader upload.
No caller-selected command or transfer geometry reaches transport.

[verified source/native] The final ELF has eight contiguous words at
`01c033d8..01c033f8`: stage, signed runtime result, signed SYS/LSB clock reports,
SPI write pointer, elapsed milliseconds, heartbeat, and signed recovery result.
The expected pointer is `02002d82`. The native stage-6 store precedes P33 lock
acquisition; stage 7 follows a returned successful request. The known fixed
loader upload overwrites all eight words in block 9. Source/native evidence and
pins are retained in ignored `build/diagnostic-boot-proof-review.md` and
`build/diagnostic-boot-proof-evidence.json`.

[verified source] Host framing and the WL82 MengLi quirk come from kagaimiq's
[jl-uboot-tool](https://github.com/kagaimiq/jl-uboot-tool/tree/adb3f18889e88ac512ce0a3c4d8cc3d3cb30696a),
specifically `jltech/uboot.py`, `jltech/cipher.py`, `jltech/crc.py`,
`data/chips.yaml`, and `docs/usb-loader-v2.md`. The source carries the
[MIT licence](https://github.com/kagaimiq/jl-uboot-tool/blob/adb3f18889e88ac512ce0a3c4d8cc3d3cb30696a/LICENSE),
copyright 2023 Andrey Grigoryev (kagaimiq). This module independently implements
the protocol facts with Python's CRC primitive and fixed GB2312 magic bytes; it
does not import or copy third-party executable source. Decode exactly one
32-byte transfer once with seed `FFFFFFFF`; retain raw and decoded separately.

[verified source] The factory revalidates the exact current app, ELF, target,
directory-last transaction, full install/readback transcript, original fixed
backup provenance, original consumed install and boot markers, and exact
reviewed source dependencies. It requires a new direct receipt under the
original private backup parent, an exact registered Prepared instance, and a
fresh passive same-port ROM enumeration with a different device/mapping
identity. The snapshot is valid for at most 120 wall-clock seconds; a session
lasts at most 10 monotonic seconds. Binding, FD identity/type, frozen evidence,
and complete SG status/residual/sense/length are checked on both sides of each
exchange. A durable exclusive marker consumes the target-boot session, and each
intent is durable before submission. There is no retry or automatic recovery
action. Close failures, including interrupts, prevent result publication.

[inferred] A coherent capture requires stage 6/recovery 0 or stage 7/recovery 1,
runtime result 0, SYS 24..480 MHz, LSB greater than zero through 60 MHz, the exact
SPI pointer, elapsed at least 20,000 ms, and nonzero heartbeat. It is classified
only as conditional diagnostic execution evidence. Stage 6 alone is insufficient:
it precedes a potentially waiting lock and is reached after failed panel probes
as well. Zero, incoherent, mixed, or missing words are inconclusive.

[reported/inferred limitation] The primary protocol documentation describes
in-place RAM encryption/send/decryption. This FM-1's bare-ROM handler, BSS
retention through P33 reset, and ROM USB initialization writes remain unverified.
The host input-only operation is not proved mutation-free on the target. No
fallback probes are authorized. BSS has no per-boot nonce; coherent words cannot
prove visible pixels, electrical SPI activity, the cause of ROM entry, or resist
deliberate spoofing. The result keeps all those physical claims false.

[verified policy limitation] This first factory requires the exact four-event,
successful target-reset request receipt and exit status zero. Request completion
is never boot proof. Earlier stock-return FC0C detached after a transmitted CBW
and was recorded ambiguous; the target may behave similarly. Such a receipt is
rejected here. A follow-on factory must be separately reviewed: pin the exact
install/target-reset campaign and wrapper capture, require one transmitted exact
CBW with no retry, a terminal ambiguous outcome, and a fresh same-port passive ROM
return. It must preserve reset/core-success uncertainty, rather than treating
arbitrary ambiguity as permission. That envelope is a separate next dependency owned by the parent; the
injected policy remains unchanged.

[verification status] Focused tests include an independent codec vector, every
changed FD07 byte, wrong direction/length/data/order, all SG error fields,
pre/post binding/FD drift, stale windows, evidence changes before submission,
copied authority, close/durability failures, and exact real private ELF/install
factory replay with modeled reset and capture. The frozen injected source
`ff593853` and tests `93aaaa1a` passed 126 unique cases across 16 Hera chunks,
plus a separate actual-private-fixture smoke with no skips. Independent review accepted the 126-case evidence (`705da0ef` review
report); a fresh structured label lookup confirms no containers remain.
Eighteen exact-image container inspections show exit zero, no OOM, four CPUs, 4 GiB, no network, no
devices, and all removed. Evidence is retained in ignored
`build/diagnostic-stage-probe-test/`. No physical device was passed to containers.


[verified source] `tools/fm1_diagnostic_stage_sg.py` supplies a separate Linux-only
`--campaign` CLI and native SG transport. Its own strict envelope pins the entire
injected campaign and frozen source `ff593853`, backup discovery `79bbe99c`, and
SG structure `28317ee5`. It opens the exact character-device identity once with
NOFOLLOW/CLOEXEC/NONBLOCK and an exclusive advisory flock only inside the durable
one-use runner. The SG interface is fixed to 64-bit Linux, IN direction, sense
buffer 32, timeout 3,000 ms, and the exact two operations. Structured replies
return to the pinned outer policy for durable status/sense/data-hash logging and
rejection before another request; syscall/post-binding failures close and stop.
A private consumed opener permit cannot be reused. There is no upload, reset,
flash command, arbitrary transfer, or retry. Kernel flock is advisory; private
source/interpreter ancestry and absence of competing device commands remain
caller premises. The 10-second session bound is checked before and after each
ioctl; it is not a cancellation guarantee for a stalled kernel syscall.

[verification status] Native source `13d7c647` and tests `4c6fddea` are independently
source reviewed. Its 79-case Hera smoke/chunk evidence is pending under
`build/diagnostic-stage-sg-test/`, including real app/ELF factory validation and
mocked sysfs/FD/SG ioctl. No native CLI or hardware command has been executed by
this lane. The parent must review a concrete campaign and activation packet
before execution. A factory duration is retained separately from the long
modeled flash-install test; the short passive ROM snapshot must be fresh at actual
preflight and both exchanges.
