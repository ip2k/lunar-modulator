# Native settings journal checkpoint, 2026-10-13

[verified] Actual portable C two-sector journal implemented in
`firmware/native/settings_journal.h`. It retains the previous committed sector,
programs the replacement header and payload before its final commit marker,
binds schema/generation/length/payload with CRC32 and verifies readback. It
refuses read failures, ambiguous generation ordering, oversized payloads and
missing callbacks before mutation. Identical saves avoid erasure. No automatic
retry follows uncertain write acknowledgements. Loads leave the destination
and length unchanged on failure. Explicit byte encoding avoids host/target
struct padding and endianness dependencies.

[verified] Thirty cases passed in thirty Hera containers with ASan/UBSan,
strict C99 warnings, all logs/exits/no-OOM checked and three input source hashes
matched to current files. Eight cases exhaustively interrupt every erase and
program byte for payload lengths 0,1,2,7,63,128,255,256: **33,680 interruption
points** total, including fully written commit with lost acknowledgement.
The target slot starts with an older valid record; the latest committed sector
must remain byte-identical. Each interruption reloads old settings unless the
complete replacement commit exists. Other cases cover all header field and
payload corruption, generation wrap, equal/conflicting and half-range
ambiguity, capacity/read failure without output mutation, unchanged-save wear,
missing callbacks, repeated rotation and empty initial storage.

[verified] Separate production-interface wrapper compiles to a real pi32v2/r3
object using pinned JieLi clang, `-mfprev1 -Oz -ffreestanding -fno-builtin
-std=c99 -Wall -Wextra -Werror`. Compiler command equivalent:
`clang -target pi32v2 -mcpu=r3 -mfprev1 -Oz -ffreestanding -fno-builtin
-std=c99 -Wall -Wextra -Werror -I firmware/native -isystem
<toolchain>/pi32v2/include -c tests/native/settings_journal_target.c`.
Source and private object hashes: `target-compile.json`. No application link
or physical execution is claimed.

## Integration and migration still required

The module accepts offsets relative to an independently admitted 8 KiB storage
window; it deliberately contains no physical address or flash permission.
Maximum payload is 256 bytes, matching the inherited bounded settings callback;
this is device settings storage, not project/song storage. Saves must occur
while audio is stopped because inherited NOR operations mask interrupts.
Callbacks must separately enforce exact sector/page bounds, serialize access
and preserve protected components. Flash gates remain empty in current builds.

Stock V15 VM occupies 0x93000..0xE9000; the expanded VM starts at 0xD9000.
Existing stock bytes cannot be blindly truncated or overwritten to allocate
this journal. Next inspect/export complete original VM, establish a verified
stock format or explicit retained external backup/migration path, and identify
a safe dedicated journal reservation. Preserve both original full dumps and
stock rollback image, including settings. Unknown non-erased bytes are data
until proved otherwise. A successful journal simulation does not establish
stock VM semantic migration, physical recovery or retained song/set storage.

Hera source snapshot: `settings-journal-source-v1` under
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/`.
Private logs/object: local `build/native-settings-journal-20261013/`, remote
`out/settings-journal-v1/`. Test launcher is retained alongside public receipts.
All workers terminal exit zero; no hardware commands issued in this checkpoint.

Serena inspected the inherited settings_save body at the actual worktree path.
Rarefaction remains rooted at the primary checkout with fallback flags and no
compilation database; its primary clangd state does not prove this worktree's
pi32v2 ABI. Actual pinned target compilation provides the compiler evidence.
