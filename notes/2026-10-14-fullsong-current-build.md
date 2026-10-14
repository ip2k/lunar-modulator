# All-55 Event Horizon song-diagnostic link (2026-10-14)

## Result

The production `tools/native/build_demo_image.py` controller completed an offline private diagnostic link from the integrated source base `b3a9c34baac68b710062a02d217859fb01568ccb`. It selected all 55 production catalogue modules and prepared exactly one Event Horizon Showcase project at startup index 0. The image is explicitly marked `linked-private-diagnostic`, `installable: false`, `hardware_admitted: false`, and `hardware_tested: false`; SAVE is linked but `save_service_armed: false`, `storage_admitted: false`, and `flash_io_bound: false`. This is build/link evidence only, not runtime, storage, installability, or physical acceptance.

## Reproduction and bounded execution

The production controller was run with `--runtime-mode song-diagnostic` in pinned container image `sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`. Container exit was 0, `OOMKilled` false. Docker inspect records `docker-batch.slice`, 4 CPUs, 4 GiB memory and equal swap cap, pids 256, network `none`, UID:GID `1001:1001`, read-only root, read-only source/catalogue/toolchain/state/request mounts, and only the task output mounted writable. Container start/finish: `2026-10-14T14:04:03.549198957Z` / `2026-10-14T14:04:15.948609309Z`.

Exact command:

```sh
python3 tools/native/build_demo_image.py \
  --request /input/request.json \
  --state-tool /state/fm1-state \
  --toolchain /opt/jieli \
  --catalogue /catalogue \
  --out /out/result \
  --runtime-mode song-diagnostic
```

The production controller itself links `LUNAR_PROJECT_SAVE_SERVICE=1` and verifies its own SAVE-service receipt; no test wrapper or task-local flag injection was used. The project was not flashed and no device was connected or accessed.

## Exact inputs and receipts

- Request bytes: `/home/claude/mvave-fm1/fullsong-current-build-20261014/input/request.json`, SHA-256 `3d84b13fbe6d5bb37c1cfc2edae50c739d65e8c926d3cf52dc22fbede9db70d3`.
- Controller canonical request SHA-256: `0a3b172639a849aa95d0e97519fc67c2dafc674c17bdde053c48f04be84afe7a` (different serialization from raw JSON bytes; both are recorded deliberately).
- Prepared profile SHA-256: `b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46`.
- State tool SHA-256: `7a3cf4155c6642bd14fb69de25e2c1415b423ce9fa193006a3ef70f55d55fb77`.
- Fresh source manifest SHA-256: `0fc5d2b70476025085bd02f20f20794bded6a06c93fc0c26d8166f30ae91967e`; all 16 catalogue-z shard reports matched that manifest. Catalogue source freshness receipt is true.
- Toolchain compiler SHA-256: `42b94f9e11140b0fcab8f807b2872ad245b8eeca03a2d792f8706c5a3a35d34c`.
- Project source SHA-256: `22bf4e768ec1e55a9a92ebb7b2ef1ed5d5967703d226fca7798f0c67b441d24f`. Prepared compressed content: 4,345 bytes, SHA-256 `b6ca5a034c93e1093c88a8b284b9df6fde110b07de30e4836da5c76563eba163` (5,100 source bytes, 755 bytes saved).
- `result/image.json` records only project id `replacement-showcase-candidate-event-horizon`, startup index 0, runtime `song-diagnostic`, return-to-ROM 120 seconds, and `runtime_hook_linked: false` (the one-project diagnostic path does not enable that hook).
- `result/link/verification.json`: exact requested 55 modules; `-Oz`/LTO catalogue provenance; compressed Braids wave table (33,024 raw / 24,159 packed bytes); indexed TFT true; flash Plaits wavetables true; Shapes voices 12; stack-watermark linked true; flash write range `empty`; SAVE linked true but disarmed/unadmitted/unbounded and runtime-unverified; catalogue freshness verified true. Key audit passes with zero failures/pending checks. The `worst_case_stack_bound` remains false.
- `result/link/artifact/artifact.json`: combined RAM layout passed, flash layout `expanded-d9000`, app budget 868,836 bytes, linked app size 862,296 bytes (6,540 bytes below that stated app budget), ELF SHA-256 `f370fdb840b723e78388b81f56a076d30a130ad560485281fbe6c2ad406d294a`, app SHA-256 `b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956`; `installable`, `hardware_admitted`, and `hardware_tested` all false.

## Comparison and limits

Compared with the earlier retained 120-second song-diagnostic app (`/home/claude/mvave-fm1/song-runtime-link-20261014/link-v2/artifact/app.bin`, 862,272 bytes, SHA-256 `264a35311828d7269aca10f8f8c65e5429ead5df23162a9d781d1f36e5e4980d`), this fresh integrated-base app is 24 bytes larger and has a different digest. The current build therefore does not establish byte identity with that earlier artifact. The earlier ELF was 994,536 bytes; the current ELF is 994,540 bytes. Both are diagnostic link outputs only.

The semantic server roots were not confirmed for this Hera worktree; Rarefaction reported the Mac primary checkout for C, and Serena config showed a project name without proving the Hera absolute root. They were not switched because that could disturb another active session. This notes evidence comes from direct source/instruction inspection and the production controllers verifiable receipts. The build says nothing about device boot, audio quality, storage SAVE correctness, migration, rollback, stock package validity, installability, or release admission.

## Durable artifacts

Build output, stdout/stderr, exit marker, and Docker inspect are retained under `/home/claude/mvave-fm1/fullsong-current-build-20261014/`. No generated firmware binary is committed. A coordinator must review this note and receipts before using this private diagnostic image as an input to any later guarded acceptance stage.
