# Diagnostic install and first physical boot trial

Personal, non-commercial. The active milestone remains a diagnostic application
that boots, displays its probe and retains verified recovery. The earlier
complete install/readback/stock-restore/readback rehearsal and subsequent
stock identity response are verified separately in the SDK rehearsal note.

[verified: physical entry, pre-transport backup failure] A fresh identity/key
attempt returned the exact known `FM-1_092` identity and entered same-port
ROM device 25. The fixed backup adapter stopped while discovering an SG node:
Linux had enumerated USB before creating that node. Its complete two-event
log contains `campaign_prepared` and `campaign_stopped_ambiguous`, with no SG
intent or completion. Outer and backup child exits were 1; the entry child
exited 0. No backup manifest or dump was published. Preserve the consumed
entry marker and failed receipt; do not rerun the original campaign.

Private failure archive `build/diagnostic-boot-physical/fresh-pretransport-failure.tar.gz`
has SHA `7a322730f0b21538330bdeb028afa084c3cb931a3cad1d50c21dc95a1d91c7fa`;
entry `91f7bd4761889acec1061955e1981e5046550d1f8781ebffb913b1d4b3321f66`;
failed campaign `a990f0ff879e7c3ddafcedea45cbe59917b76da57ddbee57e368548764e0f146`;
failed log `96a637fbaed6564c62d45532e5e9c84acb5d74f24d1908849aff6ac3b573e2f1`;
capture `c45977567a700b26e6886cf91e14d463e12042d309602a8a2268028544191e1d`.
The owned capture was stopped and fsynced. The later SG node's ancestry was
observed passively on the same device-25 ROM connection. This is not loader
upload, backup, image installation or diagnostic boot evidence.

[verified: reviewed continuation and complete fresh backup]
A distinct private one-use wrapper continued only this proven discovery
failure. It pins the failed entry/campaign/log/capture, requires zero ROM bulk
traffic in that capture, verifies terminated original processes and unchanged
live ROM/SG binding, and retains the unchanged 600-second entry-age gate.
It preserves the original marker and adds a parent-scoped continuation marker
before creating a separate private receipt parent. It uses the unchanged
fixed backup adapter and its exact command envelope, without another identity
request, soft key, reset or NOR write. Its concrete source and final verdict
were independently reviewed before activation. A partial upload or ambiguous SG request
does not qualify for this continuation.

Wrapper `333a71295c773781341b2e39d5462155666b9a38834284147116a5af0eff022b`
ran once. The backup child exited zero, followed by the owned capture stop.
Both complete 1 MiB dumps match the original stock image
`96006a51917750743d7adc68461f1289e82adc004a75bd2bbd5da40ecc44c4e4`.
Independent replay verified all 8,757 vendor requests and their ordered BOT
CBW/data/CSW completions, upload prefixes against the fixed loader, and all
8,192 flash pages against the dumps. The final completion was 557.912 seconds
after entry, inside the unchanged 600-second gate. Eighteen standard kernel
requests were separated from the vendor transcript. Usbmon text carries only
32-byte payload prefixes; this is not a full-payload wire comparison.

Private continuation archive
`build/diagnostic-boot-physical/continuation-v1.tar.gz` has SHA
`006d722587698eca71e3b123b50fe0af01abcba1b99bf5773ecbf718c31a7cc9`.
The independent acceptance is `build/fixed-backup-physical-preflight.md`, SHA
`3c99af4b24109681e1b44dafbd2f5c2a818be133a9808bdcc382b98fe3fd49c5`.
No NOR write or reset occurred in this backup. Its original failed receipt and
marker remain intact. Same-session no-later-device-command attestation is
still a separate operator precondition for installation.

The fresh install-only packet has been prepared and passed actual staged-file
preflight without opening hardware. Archive SHA
`9c8a342e941678ca39d76d08a4644026a6a5de728a15bde1330594e096f83379`;
install campaign
`59bf948503e6084f1672b485a497a20d18ad5179a6e132b7e16ce65fb02b6067`;
one-use capture wrapper
`f59b80714a2abf9b636911ad4270bdfd3560ff97b3327ae5a478d52ce4ea4629`.
Independent concrete review accepted the packet and its copied actual
staged-file preflight receipt. The wrapper then ran exactly once and both it
and the install child exited zero. The final full 1 MiB readback matches
`df6c963ecd37b334f393c5bc92c2780b6094181308822a03c8190b016a4e97db`.
Thirty sectors were erased/programmed, with directory sector `0x4000` last.
The owned USB capture remained alive through child exit and was stopped and
fsynced. No reset or diagnostic application execution has occurred yet.

[verified: independent physical install replay] The complete private archive
`build/sdk-install-physical.tar.gz` has SHA
`b25de51ad107d60cd67e4e13765985ed3130837686486fe325b93ebda7789b6f`.
Independent review accepted all 22,546 transcript events, 10,747 vendor
requests, 30 erases, 480 programs and final 4,096 full-image page hashes;
the journal/result and outer receipt chronology agree. One hundred standard
kernel requests (50 TEST UNIT READY and 50 REQUEST SENSE) were counted
separately. Capture prefixes are limited to 32 bytes. The accepted report is
`build/sdk-install-independent-review.md`, SHA
`7cce401033cb21dd3546308523c3a7fd3be65ae96c6f2ed1394fd1d0af96d1a3`.

A separate target reset packet passed independent concrete review and actual
staged-file preflight, without opening hardware. Archive SHA
`8da6e1dbf7c74a58608d9f4435a052e6db2202b1a6b483a7818c8ed8ed291058`;
campaign `6d7bf62825b117dd21537499bc4dfd41d397c98d804f59c205863d3d6d862778`;
wrapper `ce7129a4ab980f8f41915b865993f42e83c26d5e5cb56a21b728d281c2f54e85`.
The final review is `build/fixed-target-reset-review.md`, SHA
`fe53152557514d7d38fc4e2005ace7153c9d279f5fa2dbb4a7b5eb5309ec82f8`.
It binds this exact completed install and retains the original one-use
markers. Its wrapper records passive USB/SG sysfs re-enumeration after one
reset request; it sends no further device command, even when reset completion
is ambiguous. Target reboot and the pre-upload diagnostic RAM witness remain
pending, separately from the accepted NOR installation. Activation awaits the
separate fixed two-request native ROM probe's testing and concrete packet
review, so a fresh short-lived ROM snapshot can be used promptly. No device
command has been sent after the verified install.

[verified: source-only staging] The successful-reset-only ROM probe template
archive `e10b4184c55d2433c0b3a3066ed16204f7631110e7efbf346c7a1ec17c2a1864`
contains five regular files with checked hashes. Root staged only injected
probe `ff593853…`, native adapter `13d7c647…`, and one-use wrapper `47952f07…`
under the existing private install stage, preserving all original packet files.
No factory or native child was run, and no device was opened. The independently
checked staging receipt is retained under
`build/diagnostic-stage-bench-template/staged-source-receipt.json`.
This wrapper requires a successful reset receipt. A detached, ambiguous reset
must use a distinct reviewed policy and preserve its original status; neither
policy may refresh away the initial ROM snapshot or upload before stage capture.

[verified: native transport evidence] Independent review accepted source
`13d7c647…`, tests `4c6fddea…`, all 79 exact planned Hera cases and a separate
actual-private modeled factory smoke, without failures, errors or skips. All
18 containers exited zero without OOM and were removed; evidence proves modeled
transport behavior and input validation, not physical ROM command semantics.
The modeled factory took 1.603 seconds. Report
`build/diagnostic-stage-sg-independent-review.md`, SHA
`53285fdfb31e41899f6e362bb87464850a3975a95d4ebc2662c95370185578a4`.
The successful-only wrapper's finalized independent review is
`build/diagnostic-stage-wrapper-independent-review.md`, SHA
`118a6374d2df847e5efbf1458eb67ea32d650cb621f871056df7ef61d30da238`.

[verified: public/private CI boundary] GitHub run
38188020648 passed its browser and C/C++ jobs but failed both Python jobs
because the exact private rehearsal fixture required files unavailable in
public CI. The fixture now skips only when all three private path environment
variables are absent and strict mode is disabled. Set
`LUNAR_REQUIRE_PRIVATE_FIXTURES=1` for required private verification; partial,
empty or invalid configuration still fails. Production sources and their
reviewed hashes are unchanged. Seven selector boundary tests and the four
importing test modules passed their strict-private Hera gate: 287 cases in
16 chunks, no skips. The same public lane passed 244 and explicitly skipped
43 optional private-fixture cases. Independent retained-evidence review accepted
both lanes; report `build/sdk-ci-private-fixture-review.md`, SHA
`ccfbba14400af1b8b12a8443b75efe7311639291455ce56ce39a6edbc60da1f1`.
Fresh GitHub run 38191069382 passed all thirteen jobs on exact selector
checkpoint `22cae292f2b689e08e67cdc425bc2005df17e680`; later source checkpoints
require fresh CI.

Next: separately review/execute the installed target's one-shot reset; establish actual
boot/display/recovery evidence; restore and verify stock with a fresh recovery
binding. No diagnostic application behavior has been accepted yet.


## Returned-ROM preparation checkpoint

[verified: files only] Source staging V2 completed with exit zero on bench01,
without importing a device opener, opening USB/SG, or issuing a command. It wrote
31 pinned source/template files, rechecked the original 35-member install packet
and all 45 required source dependencies, and preserved completed install journal
`0d797332…` in a separate input evidence file. The recovery executor still has
`EXECUTION_POLICY_SHA = None`; its preparer's own journal snapshot remains absent
until actual preparation. The first staging attempt stopped before mutation
because build-support dependencies were absent; its failure is retained.

Private evidence is `build/returned-recovery-source-staging-v2/`: script
`cab94dbc4a3db25be10e5763da47c7bcb4f2d262521db8800a7a935bc30ea997`,
durable receipt `7ea7bfbdb364bd1d323d7ce3eacbcacd1168578617bca336c9753197480f8745`,
and two-member evidence archive
`bb34cb34cbe598b5a732c240ab5ac80d63c612b50e228018abe06150a5428df4`.
Independent retained receipt review accepted
`2bbe8c016462398ec7f455691379053a68d4129f677b75b9b674608a60fcc8d7`.
These checks prove file staging and receipt consistency, not target execution
or recovery. The final genuine composed runtime gate and concrete activation
policies remain pending. No target reset or diagnostic-stage probe has run.

### Accepted returned-recovery and reset source checkpoint

[verified: offline] The genuine composed recovery gate accepted 182 unique
cases with explicit mixed-version provenance: 179 V3 cases in 16 Hera chunks
and three unchanged passing V2 actual cases. Aggregate `87848de7…`, independent
review `4d3076dc…`; fixture failures remain preserved. The root stock-return
reset source now pins restore verifier `f5835237…` and has SHA-256
`7af061b09ce90fe94c8698d591102147cf997570bf21266ad6a6d8b27ea59343`.
Its focused gate passed 58 unique cases in 16 Hera chunks plus a separate modeled
smoke, with 18 isolated containers removed, no failures/errors/skips/OOM;
aggregate `18f544dd…`, independent review `f7e508a6…`. Actual device syscalls,
USB/reset/capture and NOR operations remain modeled in these gates.

[verified] GitHub run 38197006075 passed all thirteen jobs at checkpoint
`4391433161f6fe61d30d54a8b79b53c67362177b`. These later source/document changes
require a new exact-head CI run. No target reset/probe, returned-ROM physical
backup or returned-stock reset has executed at this checkpoint.

### Stock-return source staging and first-boot prerequisites

[verified: files only] Six additional reviewed files were staged once on
bench01 at timestamp `1791775304.3124843`, without a device import, child,
USB/SG open or command. Four closed templates occupy the distinct static
`returned-stock-reset-source-v1` directory; the reset adapter `7af061b0…`
and identity decoder `684342b0…` are fresh files under `tools/`. The future
execution directory `returned-stock-reset-v1` remains absent. All eight
wrapper activation placeholders and all four actual completed-restore pins
remain unset. The original 35-member packet, completed install journal,
45 existing sources and eight existing templates were checked before writing;
the prospective source inventory contains exactly 47 files.

The source-only archive is
`ea0d669e3a5cb715357384170551c9ef2b07552b1e6077505639ada2d7d2d062`.
Retained private evidence in `build/returned-stock-reset-source-staging-v1/`
includes script `a76d1b4a…` and actual durable receipt
`e60e3f8b10a858216131165fd1a724680d894dafdef940f186cf4e807e7175e6`.
Independent source review `813e676f…` permits only this staging; it does not
authorize preparation or execution from incomplete restore evidence.

[verified: offline] The corrected closed wrapper/preparer gate has 60 passing
unique cases, no failures/errors/skips, with explicit mixed provenance: one
unchanged genuine V3 composed smoke and 59 V4 cases in 16 Hera chunks.
Aggregate `af33d115…`, checker `5be5e700…`, cleanup `6ea796f3…`;
independent retained-evidence acceptance remains pending at this entry.
The incorrect V3 inner runner and earlier actual fixture's `speed` field
failure are retained separately. Production sources are unchanged by those
harness repairs. GitHub run 38199299324 is checking exact pushed checkpoint
`20284ce7ed0543038c5861e935f345e7b4257a2c`; it is not yet accepted as green.
Passive sysfs at timestamp `1791775290.8227494` still reported port `3-2`,
bus 3/device 25, `4c4a:8057`, `WL80UBOOT1.00`. At this entry, target reset,
diagnostic execution/display and the new physical recovery path remain pending.

### First physical target reset and guarded probe stop

[verified: physical wire/sysfs, stage not yet read] The reviewed target reset
wrapper `ce7129a4…` ran once. Owned USBmon capture opened at
`1791775830.3765495`, remained alive after the child and stopped with owned
SIGTERM at `1791775855.3926494`. The command log records one exact FC0C argument
1 intent at `1791775833.548683`; post-ioctl binding discovery failed while the
USB device detached. Child status is 1, not completed-reset status. Passive
sysfs found a new same-port ROM device 26, replacing 25, and recorded its original
snapshot at `1791775855.3214695`. No reset was retried.

The immediate chooser consumed its own marker and selected the detached route.
Historical capture replay then rejected a new-ROM standard CDB
`1e0000000100` (PREVENT/ALLOW MEDIUM REMOVAL) outside its existing allowlist.
The chooser stopped at `1791775865.1165452` before launching either probe
wrapper or opening SG. Independent wire review `a514eff1…` accepted the paired
transfers and failed media-lock/illegal-field sense as Linux-compatible;
the issuing process and ROM internals remain unproved. A distinct admission
is required. The consumed chooser cannot be reused, and the original snapshot
cannot be reused as fresh transport authority or refreshed; it remains historical
evidence alongside a distinct current witness. The approximately 20-second return timing is consistent
with the diagnostic design [inferred], but does not prove diagnostic stage,
display pixels or the cause of the ROM return.

Private retained evidence is `build/target-boot-physical-v1/`: four staged
wrapper directories in archive
`78706bab00684047f2b812832ee697ce5e6611e7cbc62134ebda32e36f25835e`,
reset log `1cf360bd8871e141613ed191a621e0bbd1e5906a7c0fe6b648283945ca665fc7`,
capture `c5223ee8795534695d4471500c11ebc5be4787e116bdfdd2e7b2878d9d9b264d`,
original ROM snapshot `e79dcad1…`. No recovery-loader upload, NOR operation or
RAM stage probe followed this reset.

[verified: private files only] A read-only export of the complete original bench
tree is retained at `build/target-boot-physical-v1/private-bench-tree/`;
archive SHA `bc6e21ed13f235fb00c96c887e71915dddadfb88799ea2600ed898340c2dc00e`.
It preserves all original reset/chooser markers, source files, journals and
captures for the successor's actual-file factory check. The separate marker
and negative-absence receipt records no hardware access and no snapshot change.

[verified: offline/source-only] Independent review accepted the corrected
60-case wrapper gate as `715e4236…` and actual six-source staging receipt as
`ad6ad938…`. The new closed interrupted-restore evidence kernel passed 55
cases in 16 Hera chunks and independent review `e0401d94…`; it does not yet
admit a genuine stopped campaign or provide an opener.
