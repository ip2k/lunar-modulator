# Expanded transport receipt boundary review

Date: 2026-10-14
Task branch: codex/2026-10-14-transport-review-fix
Base: 49ede4e1755ed588bbef09f75802342081cff337

## Change

The expanded transport manifest now requires the exact runtime configuration emitted by runtime_mode for song-diagnostic (120 seconds and release_accepted=false), a linked production SAVE service with every storage/runtime/hardware-admission flag strictly boolean false, and compact-writer codec metadata showing a distinct freshly compiled object replacing exactly one cached object. It validates source/cached/fresh SHA-256 fields, the exact writer compile definition appearing once in compile_flags, and valid verification/artifact receipt digests. The output carries the checked runtime, disarmed SAVE summary, codec hashes/replacement result, and the upstream verification/artifact digests. Existing installable, hardware-admitted, physical-writer-ready and migration/recovery claims remain false.

Positive fixture coverage preserves both the historical 12-voice flash-Plaits profile and the separately reviewed Shapes8 compressed-RAM profile. Negative mutations cover 120-second mode/duration, SAVE linkage/arming, codec mode/replacement/definition/hash/flags, and verification/artifact digest format.

## Receipt hash interpretation

The retained Shapes8 receipts' embedded candidate/image digests are canonical-JSON digests, while their file digests pin the raw serialized files. Independent calculation matched the embedded values to canonical JSON, so this was not a correspondence mismatch. The manifest records canonical receipt digests per its generator. Do not compare those embedded values directly to raw-file SHA-256.

## Validation and limits

Focused test command ran in a network-disabled container from the pinned Hera image lunar-preload-tests:20261014 (image sha256:1e6a3bc97b299a40f572ab38972a114e2f9ab0f4daaf96e2ae970f488ac34313), docker-batch.slice, 1 CPU, 2 GiB memory and equal swap, 128 PIDs, read-only checkout/venv and bounded writable /tmp. Command:

    pytest -q -p no:cacheprovider tests/test_expanded_transport_manifest.py tests/test_native_demo_image_controller.py

Exit status: 0; 80 collected tests across the manifest and image-controller suites passed. py_compile and git diff --check also passed. No device I/O or physical/installable admission was performed.

Serena's active project and Rarefaction's Python root both reported the Mac primary checkout (/Users/likwid/Developer/mvave-fm1-firmware), not this Hera worker checkout. I did not switch shared semantic-tool selection; source was inspected directly in the isolated assigned worktree. This is not a semantic-index validation claim.

## Remaining boundary

The transport validator consumes the image receipt and checks its structure and digests, but does not independently reopen and hash the separately referenced verification/artifact files. It preserves their receipt digests in its output for downstream correspondence. Root's later campaign wrapper must bind those objects to the exact selected build/candidate. These checks do not prove storage admission, migration, rollback, native writer safety, target transport, or hardware acceptance.
