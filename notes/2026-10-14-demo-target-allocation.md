# Demo project target allocation: bounded offline evidence

This note asks whether the host startup refusals for Satellite Hearts and Afterglow Relay Showcase imply target pool exhaustion. Work is offline and compile-only; there was no device, MIDI, USB, flash, power, reboot, or runtime test. Source base is f3779b78082cceec74852120306efcaca15abcf4.

## What is measured

The matched all-production full-song target link receipt is notes/2026-10-14-all13-fullsong-link-comparison/chunk-codec-followup/target-verification.json (retained in the successful build tree at /home/claude/mvave-fm1/all13-fullsong-link-comparison-v1/chunk-codec-followup-v1/target-link/build/verification.json). Its release-config pool is **216,064 B**, computed as 192,000 base + 57,088 indexed-TFT app credit - 33,024 B raw wavetable storage. The JSON identifies the wavetable record as compressed and the all-production catalogue; its startup project remains runtime-unverified. This is link/configuration evidence, not a guarantee that a specific project starts.

Compile-time sizeof constants emitted by the real pi32v2 JieLi clang on current source give: Shapes 206,904 B, Macro 19,872 B, Drums 7,648 B, Echo 65,744 B. The equivalent Macro host sizeof is 32,736 B. Full object hashes and retained artifacts are in notes/2026-10-14-demo-target-allocation/current-evidence.txt. These are instance payload sizes, not complete project totals. lunar_instance_pool_alloc adds a 16 B header, and all allocations are rounded to 16-byte boundaries. Thus a Shapes allocation consumes 206,920 B and leaves just **9,144 B gross** from the configured pool before TLSF overhead or any coexisting engine.

## Interpretation by project

**Satellite Hearts:** its project contains Shapes plus Comet and two Drawbar units. Shapes alone leaves only 9,144 B gross. Follow-up accounting records Comet 10,240 B and Drawbar 5,072 B target payloads. Shapes + Comet + two Drawbars plus four 16-byte pool headers total 232,424 B, already 16,360 B above the 216,064 B gross pool before Hall/Limit or allocator overhead. This static comparison does not establish a runtime refusal site or device startup. See remaining-unit-sizes.txt for evidence limits.

**Afterglow Relay Showcase:** it contains Drums, two Macro units, DX7, and filter/drive/echo effect units. The measured target subtotal of Drums + two Macro + Echo is 113,136 B payload (at least 113,200 B including three 16 B headers), leaving about 102,864 B gross for DX7, Filter and Drive plus other project overhead. This subtotal suggests that the host refusal cannot be carried over directly: host Macro is larger (32,736 B versus 19,872 B target), and the host harness used a fixed 192,000 B pool. However, the exact target sizes of DX7/Filter/Drive and exact all-unit total were not computed, so target fit is **unresolved**, not confirmed. Target Echo's 65,744 B happens to equal the host test's recorded largest request for Afterglow, but the host metric is a maximum across all observed requests and does not identify a failed allocation or module.

The retained host rerun reports Afterglow refusal code 5 and Satellite refusal code 5 with largest-request metrics; that test's fixed 192,000 B 64-bit host pool is not the release target pool. Do not interpret those maximum-request fields as the failing request. The host harness is useful for refusal/cleanup invariants only.

## Scope and limitations

Target sizes came from compiler-emitted constants, not execution. Some probes required compile-only header shims because the staged Hera SDK standard C++ headers were absent; those shims supplied declarations only, did not substitute project types or alter the source structs. The target compiler's object layout is relevant evidence, but native-runtime allocation, TLSF fragmentation, module constructor success, audio behavior and actual FM-1 startup remain untested. The successful link is marked installable=false, hardware_candidate=false, hardware_tested=false, and startup_project.runtime_verified=false.

No project acceptance, supported-state reduction, engine removal, pool-size change, or storage-layout change is authorized by these measurements.

## Next step

Run targeted compile-only probes inside the documented JieLi SDK header container for Hall/Limit at 44,118 Hz and Crater/Phase Bend/Macro Heavy/Sophie; include Sophie module arena. The earlier direct compile failed because SDK libc++ headers were absent in sizes_SHAPES.log. Use tools/jieli/analyze.py to extract only size constants, not linked-image disassembly. Static totals are not runtime acceptance.

