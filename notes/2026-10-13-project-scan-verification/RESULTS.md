# Complete-format recovery selection

[verified] Production project_store.h now requires a validator during scan.
After an outer CRC match it validates the complete inner file without applying
records. Zero accepts, positive rejects a malformed candidate, negative refuses
the scan because validation is uncertain (including read transport failure).
Unknown/unsupported versions should return negative when validity cannot be
established; they must not be treated as permission to overwrite saved data.
Begin propagates refusal and blocks write/commit without erasing any sector.

[verified] 96 cases across 30 Hera containers passed ASan/UBSan, C99
Wall/Wextra/Werror. Thirty complete logs, paired exits, no-OOM state and eleven
source hashes checked independently. Final test session33563 terminal0.
Existing generation and max-payload transaction suites remain green.
Complete-codec stream tests exercised 975 callbacks for FIRST ORBIT replacement;
every callback position across reject/half-torn/full-but-lost-ack modes was
followed by reconstructed recovery: 2,925 failures. Older slot remains exact.

[verified] Nine golden-file variants additionally corrupt the latest inner
file magic and recompute both outer payload/header CRCs. The real format parser
rejects the latest file; startup selects the old file with matching canonical
records; begin selects the malformed slot for replacement and preserves old.
Six isolated cases cover malformed latest, malformed old, both malformed,
uncertain latest validation, uncertain old validation and absent validator.
Uncertainty/missing-validator cases make zero erase/program calls and preserve
both complete slots. All-invalid returns empty; no write is attempted by that
test. This does not establish semantic applicability to an engine catalogue.

[verified] Updated core target wrapper compiled on Hera using pinned
pi32v2/r3/-mfprev1/-Oz/freestanding C99 flags; compile session exited0.
Compiler/source/header/object evidence in target-compile.json. No production
application link, hardware operation or physical persistence claim. Simulator
source wrapper now explicitly distinguishes malformed files from read failure.

Current store callback contract is a required integration boundary: future
production validator must be read-only, track short/failed transport reads,
and classify unsupported versions conservatively. No storage allocation or
device flash permission follows from these tests. Capacity, production SAVE
bridge, migration, physical rollback and watched all13 boot remain pending.
