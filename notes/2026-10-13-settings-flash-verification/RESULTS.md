# Bounded native settings flash adapter

[verified] `firmware/native/settings_flash.h` adapts journal-relative offsets to
absolute NOR addresses, accepting only FC000 or FD000 bases and exactly two
sectors. Subtraction-based bounds reject overflow; erase requires sector
alignment, program requests are bounded to the journal's 256-byte maximum.
Callbacks are checked before dispatch. The context starts disarmed; the native
layout/build must independently allocate and admit the exact region.

[verified] Every write checks flash readiness and that audio is stopped (exact
success value 1). Nonzero HAL read/erase/program results latch uncertainty;
subsequent writes are refused while readback remains possible. No automatic
retry or uncertainty reset is exposed. Caller recovery decisions precede
context reconstruction. Audio must remain stopped across the transaction;
per-callback checking is an additional guard, not a scheduler lock.

[verified] The real C journal plus this adapter passed 30 cases in 30 parallel
Hera containers with ASan/UBSan. Verified all logs, exits/no-OOM and four source
hashes. Coverage includes both bases, disarmed access, readiness/audio failures,
uncertain acknowledgements, old-settings preservation when audio resumes after
erase, offset/length overflow, missing callbacks and failed initialisation.
The read-error latch is implemented but this campaign does not inject a HAL
read failure; no complete fault-coverage claim is made for the adapter.

[verified] Pinned JieLi clang compiled the target wrapper with pi32v2/r3,
-mfprev1 -Oz -ffreestanding -fno-builtin -std=c99 -Wall -Wextra -Werror.
Remote source hashes match the local target sources. Object/source hashes are
in target-compile.json. This is compilation, not a firmware link or hardware
persistence acceptance.

[verified] No app build enables this adapter, no physical flash was modified,
and OTA staging/cleanup permission remains disabled. Next integrate the native
layout allocation and real NOR/audio callbacks, keep the stock storage archive
for rollback, and prepare a concrete hardware persistence trial. Whole-project
SAVE requires a compact serializer and a larger transactional store; the
settings journal alone does not fulfill that release requirement.
