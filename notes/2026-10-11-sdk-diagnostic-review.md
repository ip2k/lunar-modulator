# Independent SDK diagnostic review — 2026-10-11

Outcome: [verified] no actionable source/native defect found in the frozen private SDK diagnostic within this review scope. This clears an offline candidate-review dependency, not hardware installation or recovery acceptance. `hardware_ready = false`. Root owns packaging, checks, commits/push and hardware. This review made no source change, device operation or test rerun.

## Exact frozen evidence

Local directory `build/sdk-diagnostic-final/`; Hera source of native output `/home/claude/mvave-fm1/sdk-diagnostic-final-20261011/`. [verified] Independently hashed locally:

- app: 120432 bytes, `991b569df7d131320e42ef34c1b619de586d2a7ba6236c0ea1c089731eb61fa9`
- ELF: `8832aa4677a7da3aa7871da58a092e5c3e69d766b31d5e67744301ce437979e2`
- native listing: `79c87e8c1bdecaa8fec8b352c5116a2fa82b40b666e87e5777ef562184b23143`
- map: `c645c087e860c0930fce328b06e093fc795d98275f8a09269d03ca720e96512b`
- manifest: `c54bdbfe99a0f8bfb8c69a655f1005af361c8baa44f3fae5c0e42f62198a2396`
- key audit: `4bbcab9a920f0a6fed65313784b31220def96a0eb871d81ae3cf5359810fd0af`
- SDK audit: `f33fad51caa0f0740bd28d290ffc97d21ed07152e98657c037a1a4e962489597`

[verified] `build/sdk-diagnostic-independent-evidence.json` records every output hash, independent raw table decoding and current owned-source hashes; all manifest-owned sources match current bytes. Source HEAD/manifest baseline is `bdbf2d397226e9dbc5711d411f916af6d00ab0da` plus exactly pinned additions. A later commit-only manifest refresh does not require a native-byte re-review, but must retain the app/ELF/listing and source hashes above. SDK pin is `e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d`. Manifest records the staged inventory, archive and 20250324.1 compiler/tool hashes. No vendor binary belongs in Git or a distributed release.

## Startup, exception and integrity review

[verified against vendor listing] At `0x02000120` the native branch reaches `chip_entry 0x0200018a`; it assigns CPU0 normal/exception stacks before the bridge. The bridge `0x02002c68` reserves 92 bytes, copies exactly six incoming words, zeroes words 6..22, calls the untouched SDK `boot_info_init`, and returns. Startup clears/copies the SDK RAM sections, sets caches/memory, reads update result, and enters SDK `main`. CPU1 start `0x02000224` initializes its USP/SP and returns through `cpu1_main 0x0200086c`; normal SDK dual-core interrupt/scheduler lifecycle is retained. This reduces our independent early-startup assumptions; it does not prove the stock SPL will boot this app on FM-1_092.

[verified] The exception handler `0x02000238` saves special registers and r15..r0, passes the saved frame to SDK `exception_analyze`, then halts. SDK exception auto-fix is forbidden by this profile. Exception recovery is not claimed.

[verified] Independent ELF table reads, rather than relying solely on the new audit, resolve exactly: early `app_version_check, sys_event_init, thread_fork_init, sdfile_init`; platform `syscfg_tools_init`; init `app_update_init`; module `wait_completion_init`; late `sdk_meky_check`. In `app_task_handler 0x020018d2`, SDK timer tasks initialize, these groups execute, the stock-derived board power initialization runs, `app_main` is called, and control reaches `os_task_pend` / event dispatch.

[verified] `sdk_meky_check 0x0201a7c6` registers IRQ123 for each core with `isr_check_key`, preserves its vendor timer scheduling, and calls `sys_timeout_add`; that function uses current app task and `_mkey_check`, with 8000 ms. `_mkey_check` preserves the `puk == 0xf36c3698` no-registration return branch at `0x0201a902..90c`. The key-audit JSON's single scheduling `pending` item is resolved for these exact frozen bytes by this native review. Other key/mailbox/eFuse claims rely on the existing audited scanner plus pinned dormant SDK contract; this review does not independently disassemble every possible ROM instruction. No key-check stub was introduced.

[verified] `app_main 0x020016f0` creates `diagnostic_worker`, records status, and returns. The worker yields every 256 successful output bytes and during its 20-second measured soak. This preserves the cooperative timer/event opportunity needed by the vendor integrity callback. Actual scheduling/timer advancement on hardware is still unverified. SDK delay calls themselves assume a functioning scheduler; finite application loop counts do not make a failed kernel bounded.

## Automatic NOR mutation trace

[verified] The sole 28-byte syscfg registration at `0x0201ae84` is `[syscfg_file_init, syscfg_bin_check_id, syscfg_bin_read, 0, 0, syscfg_bin_group_read, syscfg_bin_ptr_read]`. VM/BTIF registration sections are discarded. `syscfg_tools_init 0x02005c00` invokes the registered initializer. `syscfg_file_init 0x020063a6` opens/reads config headers, checks CRC, stores RAM state and closes; error branches return an error, not a format/repair path. The file open mode literal is SDK `dr`; no generic C `rb` semantics are assumed.

[verified] `sdfile_init 0x02008e48` reads stock boot/partition data, opens NOR and calls `norflash_ioctl` command 205. Its directory CRC failure skips normal mount; absent required directory enters the SDK assertion path. Neither path erases or repairs the directory. For command205, the native jump table (`0x020067cc`, table starts `0x020067ce`, entry byte0x21 => `0x02006810`) selects boot-info/SFC configuration and RAM copy, not the command200/201 erase branch at `0x020067d6` or command13 write-protect branch. This distinction is material: destructive handlers remain linked.

[verified] NOR open calls `flash_write_protect_init 0x01c00758`, whose traced body reads status and records masks in RAM. The distinct `flash_write_protect 0x01c006d4` can call `norflash_write_sr` through the explicit ioctl path; its similar name is not evidence that startup writes the status register.

[verified] Normal mount selects the `sdfile` VFS entry at `0x0201ac84`, mount callback `0x02007982`; this allocates/copies partition descriptions in RAM. The other linked `nor_sdfile`, FAT and extension handlers are not selected on this traced path. `app_update_init 0x02001ae0` calls `update_module_init 0x02015a44`, which allocates/zeros callback state. `update_result_get` reads/conditionally clears RAM update flags in the configured build. `app_version_check`, `thread_fork_init` and `wait_completion_init` initialize metadata/queues without a flash mutation call in their traced bodies.

[verified] No native direct call to `syscfg_vm_init` remains. The retained LP table's VM callback is `vm_idle_query 0x02006c18`, a RAM busy-byte query. `vm_init_check 0x02007506` also only reads RAM state; it does not lazily initialize or repair VM. Other retained NOR and systimer idle-query callbacks likewise read state. VM erase/reset functions remain because the SDK VFS/LP data keeps storage machinery linked; their presence is not evidence of execution.

[inferred from the verified registrations and reachable bodies] There is no automatic NOR format/erase/repair path in ordinary diagnostic startup and the owned worker. This is a bounded reachable-path result for this exact profile, not a whole-program proof that closed SDK storage APIs can never write, or that arbitrary external input / memory corruption cannot reach them. The empty device registration and absence of an application update service reduce those entry points. Preserve these callback tables and config flags in subsequent builds; re-review any changed registry, filesystem or update service.

## Reset and limits

[verified] SDK `p33_lock 0x01c00e86` disables local IRQ through nested per-core counters, takes the shared initialized-RAM TESTSET byte `0x01c025ec`, and executes synchronization. `p33_unlock 0x01c00eb6` releases it and balances that IRQ nesting. Acquiring this vendor lock is unbounded if its owner stalls. Existing SDK P33 transfer routines also have unbounded BUSY waits; this diagnostic uses the owned bounded transfer after acquiring the shared lock.

[verified] Worker native instructions at `0x02002b34` lock once, check no existing P33/RTC selection, poll at most4096 per idle phase, write/verify the 16-byte mailbox at `0x01c7fd80`, then send only OR opcode0x20/address0xa0/reset bit0x10. Return/failure paths unlock at `0x02002b70`; no scheduler operation occurs while owning P33. Select changes clear START rather than replaying a transfer strobe. The marker is excluded from linked allocation by the native image audit. Success means a transmitted request, not observed reset or UBOOT. Cold boot, cross-core runtime, actual clocks/rails, visible panel, observed recovery enumeration and stock restore remain physical gates.

[verified] No GPL HAL or GPL engine is compiled into this candidate; reusable owned code is MIT and the two fm1-nes bridge/power components retain Apache attribution. This private SDK image includes proprietary libraries and SDK FreeRTOS exception material; do not label it generally GPL-free or distribute it on this review's authority.

## Follow-up dependency

Root should build and independently review a distinct SDK raw application profile retaining the owner baseline's stock SPL/OTA/cfg/other partitions, with exact app reconstruction and directory CRC/geometry, then review the fixed-loader opener separately. Do not make the existing non-SDK emitter accept this app by relaxing its pinned profile. Directory-last install/restore review is saved separately in `build/diagnostic-directory-last-review.md`; it improves order but does not promise an atomic update or a bootable interrupted image. Review two fresh matching full backups against the recorded baseline through the exact fixed loader before any authorized erase/program. Hardware plan must explicitly account for a kernel fault before the cooperative P33 recovery attempt, and distinguish full stock readback from proof of restored normal operation.

Checks: source/native inspection, local SHA256 verification, independent ELF table decoding, and exact current-source comparison. [reported: startup_resolution]18 focused SDK tests passed on Hera including real-ELF mutation cases; parent owns that execution evidence. Rarefaction/Serena could not provide an isolated active worktree semantic connection for this review lane; no shared project selection was changed, and source/native inspection is the stated fallback. Nothing was committed or pushed by this lane; parent owns report integration/backups.
