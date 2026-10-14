# SAVE compact-codec builder and controller validation

Status: implemented on an isolated Hera branch; production controller completed an offline private diagnostic link. No hardware, device I/O, packaging, installability, storage admission, or playback acceptance.

## Builder change

tools/native/build_application_probe.py now enables both LUNAR_PROJECT_SAVE_SERVICE=1 and FM1_STATE_BIN_COMPACT_WRITER=1 only for explicit --link-project-save-service opt-in. After checked_catalogue() has verified all 16 source-fresh object shards and hashes, the SAVE path requires exactly one state/state/state_bin.o, compiles engines/state/state_bin.c with the same pi32v2/r3/fprev1, -Oz, -flto, freestanding, C99, indexed-TFT and Shapes-voices settings, and replaces that one cached object in place. It never appends a duplicate codec. The default path adds no flags and retains the cached catalogue object unchanged.

verification.json records codec mode, source/cache/fresh paths and SHA-256 digests, exact compile flags, and exact-one replacement status. The fresh object is present once in linked_objects; the cached object is recorded for provenance and is absent from the link list.

## Focused checks

Ran in the pinned, network-isolated Hera container (sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc, user 1001:1001, 4 CPUs, 4 GiB memory and equal swap, docker-batch.slice):

- python3 -B -m unittest -v tests.test_build_application_probe_save_service: 8 tests passed. Coverage includes default-off flags, explicit writer/service defines and disarmed receipt, strict boolean validation, catalogue target flags, actual one-object replacement/hash receipt, missing/duplicate-object rejection, CLI strictness, and production app binding.
- git diff --check: passed.
- Full production tools/native/build_demo_image.py link described below passed, including the target compile, link, SDK-free audit, stack-watermark instrumentation check, artifact/layout checks, and controller identity checks.

## Fresh all-module diagnostic link

Controller output is retained at /home/claude/mvave-fm1/save-codec-controller-validation-20261014/run/. Request source was /home/claude/mvave-fm1/all13-event-showcase-link-v1/request.json. The checked catalogue was /home/claude/mvave-fm1/all13-fullsong-link-comparison-v1/catalogue-z/; rechecked 16/16 shard source manifests against the current 536-entry manifest. Toolchain compiler SHA-256: 42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c. State tool SHA-256: 7a3cf4155c6642bd14fb69de25e2c1415b423ce9fa193006a3ef70f55d55fb77.

The prepared profile selected all 55 production modules and the sole project replacement-showcase-candidate-event-horizon at startup index 0. The project payload is 4,345 packed bytes (b6ca5a034c93e1093c88a8b284b9df6fde110b07de30e4836da5c76563eba163). Selection request SHA-256 is 0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a; prepared profile SHA-256 is b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46.

- Fresh compact codec object SHA-256: 2aa865fa3df98541a7a73b6f140721459c39601fc7ffb48262abba8cb038d0ca. It matches both the object file and its sole linked-object receipt.
- Cached codec SHA-256: 30965f4c27df7d3c8db0b1d53948fde937103ca34bb95bca26c0bd90a8c779db. It appears only as the replaced-object provenance field and is not linked.
- ELF SHA-256: 450464d66f6f4621af7016832671034ae8bbd79f9b2013e1f7a363998086fc15. App image is 862,320 bytes within the 868,836-byte expanded-d9000 link budget; layout_passed=true.
- Verification receipt SHA-256: d3a9b6b72e8be5fec80dfa67c44f4a00ad75142733173f847f9b0f6a62b0e4f6. Artifact receipt SHA-256: b8c366a2f8b63871d0f489f0e018d505077d09e064580a4e556c44c12030f11f.

The combined RAM linker script places .pool in the 432 KiB RAM window; .pool is 420,512 bytes (0x66aa0) from 0x01c0cc50 to 0x01c736f0, and is NOLOAD. The reported instance_pool_bytes=216,064 describes only the engine instance arena allocation, not all .pool storage. A passed linker assertion or section map does not establish startup initialization, runtime capacity, timing, or hardware admission.

All controller receipts explicitly keep installable, hardware_admitted, hardware_tested, storage admission, flash-I/O binding, SAVE armed state, runtime verification, and full_song_default_accepted false. The diagnostic probe's return-to-ROM period is 20 seconds. This is link evidence only, not proof that the project is a full song, starts or plays on hardware, or should become the default selection.

## Branch and next step

Branch: feature/2026-10-14@save-codec-builder from assigned base a0206835f388e29ae43c5b022fafd5b7c6850fe4. The assigned files and this note will be committed and pushed to Hera's bare repo; the coordinator must back up the returned commit to GitHub and review/integrate it. The controller's image.json binds the complete verification file by digest but currently does not copy the new state_bin_codec block; propagate that codec block in the controller receipt if downstream consumers need direct access.
