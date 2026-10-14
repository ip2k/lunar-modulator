# Compact binary writer verification, 2026-10-13

[verified] Random-access streaming constructor reuses the existing record encoder
and binary format. Chunks start after a fixed 1,316-byte reserved directory;
the directory and zero padding follow, then the header is written last.
The compact build omits whole-file and compressor buffers; sequential writer
construction is disabled in that profile. Normal build keeps the original API.

[verified] 60 actual-C tests passed across 30 Hera containers under ASan/UBSan.
Both build profiles round-trip all nine golden binary fixtures through the real
reader and canonical record printer. Simulated NOR checks unique byte writes,
1-to-0 programming, capacity bounds, header-last ordering, invalid constructors,
and no writes after errors or finalization. Each profile refuses all 276
callback failure positions of FIRST ORBIT, including final header publication.
Host workspace: normal 284,936 bytes; compact 71,936 bytes.

[verified] All 30 logs, exit states, no-OOM results and four source hashes were
checked. Pinned JieLi clang compilation passed with pi32v2/r3/-mfprev1/Oz,
freestanding/no-builtin/C99 and Wall/Wextra/Werror. Initial compile attempt used
unsupported generic ARM-style float flags; rerun used the actual native builder
flag -mfprev1. Target object retained privately; hash in target-compile.json.

Limits: callback failures are simulated whole-call refusals, not physical partial
page writes. This encoder is not a flash transaction or migration layer. It must
write an inactive area, then undergo full readback and outer transaction commit.
No firmware link, hardware storage operation or persistence acceptance claimed.
Largest legal chunk and full 96-KiB boundary need additional generated fixtures.

Semantic tools: Serena located the current worktree function. Rarefaction returned
the primary checkout baseline instead; its graph was not used to validate edits.
The shared active project was not changed. Test launcher and public summaries
are here; full logs/object remain under ignored build/native-state-stream-20261013/.
