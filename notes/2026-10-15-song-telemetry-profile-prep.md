# Fresh Event Horizon + companion SET preparation

This checkpoint prepares the exact committed source selection for the coordinator's subsequent firmware link. It is build-input preparation only: no native firmware link, package, device operation, or hardware/runtime acceptance is claimed.

## Source and command

- Source commit: 6a8a11d6828a47cff2109e352c55d9a2d75ac981
- Source tree: 2865ed58f01dc99eabbc1433dc80bb906127e595
- Checkout: /home/claude/.local/share/codex-worktrees/lunar-song-telemetry-profile-prep
- Pinned build image: sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc
- Fixture: tests/fixtures/browser-event-horizon-set-request.json, raw SHA-256 ef4ce3b330162abe9d4487c5b81bd170defa2c30cf0f00bca21f143f62da55f0
- The container built a fresh fm1-state with FM1_GPL_MODS=1 and FM1_MODULES=all, then ran tools/native/prepare_demo_selection.py against that fixture with --recompress-content.
- Container ran without network, with a read-only source mount, bounded at 4 CPUs, 8 GiB memory/swap, 256 PIDs, dropped capabilities, read-only rootfs, and task label lunar-song-telemetry-profile-prep-20261015. Pre/post inspections are retained in the private output.

## Prepared selection

Private output: /home/claude/mvave-fm1/song-telemetry-current-profile-20261015

- Request SHA-256: a089835b668a07d711ee13a2a4bd58aa96f483925aaf2f47767fa2be6e0e9a07
- Fresh fm1-state SHA-256: fc47f7b91d5eade8b6cd3807498eb2f28e5018abfb26f8be088a73ed18104b50
- selection.json SHA-256: bf8bf47385901432c277f27e3892f7e41c43d78204eed30323556855756db45c
- Prepared profile.json raw SHA-256: fd68a478ea594ab9c3a7f34a604e23f99614e707bb9840b8a91947b07e547738; embedded profile digest: 51b25d822ac7853565fb2f657d759185532edba433f99a01d1660a1d3513501e
- Prepared module header SHA-256: 2c54555e8026299cde5bf896e19b600421480acd402886519f55ef22e8de8a18
- Content row 0 is the Event Horizon project replacement-showcase-candidate-event-horizon; packed output is 4,345 bytes, SHA-256 b6ca5a034c93e1093c88a8b284b9df6fde110b07de30e4836da5c76563eba163.
- Content row 1 is companion SET replacement-showcase-event-horizon-companion-set, parented to that project; packed output is 1,887 bytes, SHA-256 7c850fcf8fda9ea513c8d1f14a414f638c8c1cc931156f7b000c757e7cfd0625.
- Source payload hashes: project 22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f; SET cfc53ae471b9541adaf817180de721e268e2a43adaeea77154c8ec9a6bb6b7f3.
- The profile records successful native-record equality for recompressed content. Selected modules are 54 total: 13 engines, 23 audio effects, 2 MIDI effects, and 16 modulation modules. Test-only modules are not selected.
- Startup index is 0 and startup project is Event Horizon. The SET is ordered second and references the same parent project.
- installable, native_link_verified, native_ram_verified, and hardware_tested remain false.

Container exited 0 with OOMKilled=false; no matching container remains. The generated request/profile/payloads are retained outside Git and were not published. The next step is for the coordinator to consume these exact prepared inputs in the authorized target-link pipeline, then independently verify the resulting target receipt and audits.
