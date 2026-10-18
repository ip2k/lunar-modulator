# FM1 failure onset: interrupted application write, not logged bootloader overwrite

Owner question: did anything overwrite the flash portion storing UBOOT when
this failure started? This is a fresh offline recheck of retained evidence;
there has been no physical post-failure flash readback.

## State immediately before and at failure

[verified: recorded campaign; rechecked archive] The unit was in mask-ROM USB
recovery on bench01, bound as ROM113/4c4a:8057. A RAM recovery loader was used
for the new stage7 profiling diagnostic installation. Earlier Lunar firmware
had run but failed the owner's audio/performance acceptance; this was a new
profiling image, not a completed stock restore or release.

The fresh paired1MiB prewrite reads matched SHA256
`28483c411f23d7d5fba09b4770dd29b3c66b1a154138e493e6e079e54dcf400f`.
Their first0x4000 bytes match the original archivedFM1_092 dump, as does the
intended target's prefix. This rules out a pre-existing prefix difference in
that particular prewrite backup, not every possible hardware fault.

[verified: retained host logs; owner report] USB disconnected2026-10-15 at
15:13:08Pacific during programming; owner initially reported a cable change,
then confirmed power was also interrupted. Subsequent blank display/no USB
attach is recorded. Power loss invalidated any retained RAM-loader session.

## Fresh command-log reconstruction

Archive SHA256:
`c56f4f2944a643f5bf50faa77596decdab1b25f86e318c3dd41caa2c1a2ae67a`.
The original offline replay script was copied to a new scratch directory and
rerun against that hash-checked archive without altering historical evidence.
It verified15,923 sequential submit/completion pairs, successful status fields,
allowlisted command shapes and program-payload hashes, matching paired backups
and sealed target. Reconstructed expected image SHA256 remains
`3fdaaebd73159132f7338db0f7c544935533d914fc59411cc27fe2326bbbb270`.

| Evidence | Observed in retained log |
|---|---|
| Sector erases |144, addresses0x5000 through0x94000 |
| Page programs |2294, addresses0x5000 through0x94500 |
| Next journal intent |program0x94600; no matching submission |
| Mutations below0x5000 |zero |
| Boot-directory commit sector0x4000 |not erased/programmed |
| Prefix0..0x4000 |baseline/target/original092 equal; replay preserves it |
| Protected tail0xD7000..end |target/baseline equal; replay preserves it |

New receipt: [sanitized forensic receipt](2026-10-18-fm1-interrupted-write-forensics.json).
Private replay/source/expected bytes stay under ignored
`scratch/fm1-failure-forensics-20261018/`. No vendor binary/dump is published.

## Interpretation and limits

[verified: NOR-layout/source review] The preserved first16KiB contains the
stock flash-resident boot prefix/SPL associated withuboot.boot. No logged
command in the interrupted campaign erased or programmed it. Separately, the
chip's mask ROM implementing forced USB entry is not NOR flash and cannot be
overwritten by these NOR erase/program commands. Do not confuse that ROM,
flash-resident SPL, OTA loader or a temporary RAM recovery loader.

[inferred: strongest current explanation] In-place app replacement left a
mixture of the new application, incompletely programmed sector and old app.
Keeping the boot directory until last does not make single-bank in-place code
replacement atomic: the old directory can still refer into code already changed.
A nonbooting app and absent application USB are therefore consistent with the
observed interruption while the stock boot prefix remains intact. This does
not prove the exact SPL failure branch or rule out power/reset/hardware faults.

[known validation gap] Power-on recovery via an independent hardware key had
not been demonstrated on this unit before this in-place campaign. RAM-loader
availability was insufficient to cover power loss. Subsequent Cynthion trials
have not established ROM entry. Unit-test interruption recovery is not physical
power-loss acceptance; the current physical fault must not be declared resolved
from reconstruction or a dongle DONE indication.

Answer: retained evidence supports **no UBOOT/SPL overwrite**; it supports an
interrupted application installation. Current flash bytes remain unverified
until forced-entry recovery permits fresh paired full reads. Prioritize the
Pico trial/ordered forced-download adapter; after genuine ROM identity, freshly
bound reads and a reviewed stock restore are the path back to normal operation.
Owner will connect Pico tomorrow; no device action is running tonight.

Sources: [original campaign record](2026-10-15-restart-resumed-integration.md#usb-interruption-during-stage7-install--2026-10-15),
[recovery preparation after power loss](2026-10-15-cynthion-usb-key-recovery.md),
[official/Pico research and next test](2026-10-18-jieli-official-pico-recovery-research.md).
