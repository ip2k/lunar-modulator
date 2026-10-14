# Continuous tuple FWSC composition attempt

The coordinator-approved offline `package_bytes` call was attempted in memory
only, using the externally anchored continuous build tuple. It returned no
package: strict tuple validation refused before receipt, catalogue, protected
component, or FWSC transformation checks could run. No FWSC or report file was
written; no build, Docker, device, USB, MIDI, flash, or power operation occurred.

Before the call, the retained files were rehashed. Tuple SHA-256
`9c246fb70bfb04cb6a6adbaf845fe71a882ba0228317b286f648b502b2e66ec4`, provenance
`2d8c80fd69df3dd5015fa1d64866d29f7035b0ba0fe8204ea5bac25ba66b5094`, capture
receipt `b82b9cf2dd606f19778fc6dd8b37a1efed6d80152da036cd83664f9f7d6a7943`,
catalogue manifest `af1462fc04d6a6614c4b2d5b417e43c2670361095ea1484a8b7b03e2e5fd0429`,
source-tree manifest `ed9c5ae33deaee9c91826e4fc0ea883fdab7397b33e9a7bf4ba9b1990dd7710e`,
image receipt `d116b2a19986c189cb8dae0501dc7d4534456e6e0c44d2f0f0e82b01802544a6`,
app `0a7a2fecbd730586b8792e7da6c9a6cf35fa26ae4fb77798b93b5f30e9922f02`, ELF
`7c79e47b0261f0a8ac7bdbf80ff61a3250dedac04503df0efa9b9ca75c887e9d`, artifact
receipt `7526411bf043ea7e962f02de21f9186a84cbd02e00b3cedc9981e7f6c8987482`, build
receipt `2a66c7cff2f1433cf7b1025c4cb84ef73cfea73a3fd471029d8e469ec6fc18f5`, request
`a089835b668a07d711ee13a2a4bd58aa96f483925aaf2f47767fa2be6e0e9a07`, prepared
profile `af37827fa09a5925864bfebe01d800f8b37ffcda8ce4f42bf533ea9e774c4f30`, and
source profile `51b25d822ac7853565fb2f657d759185532edba433f99a01d1660a1d3513501e`.
The source FWSC at
`/home/claude/.local/share/codex-worktrees/092-package-model/scratch/092-package-model/FM-1_092.fwsc`
hashes to `ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80`,
matching `model_092_app_replacement.SOURCE_SHA256`. The selected reference tree
contains all five required paths checked (`top/isd_config.ini`,
`top/uboot.boot`, `files/cfg`, `files/cfg_tool.bin`, `files/app.bin`). The first
preflight used the tuple-capture digest for `image.json`; it stopped before
composition, the files were rehashed individually, and the retry used the
actual image receipt digest above.

Exact failure from the corrected call:

```text
ValueError: build tuple fields differ (missing=[], extra=['toolchain_tree_sha256'])
```

This is an exact schema mismatch, not a bad tuple hash: the tuple digest matches
the external anchor and every key required by the current packager is present.
The capture added `toolchain_tree_sha256` to the tuple, and provenance carries
the same digest `41e95ab855ad2bcd1346e9a89aa7d30bed28d660e0b9053d4ce1dc43e236dede`.
The current packager's `TUPLE_KEYS`/`HASH_FIELDS` and provenance cross-check
loop omit that field. The next change should admit it as a required 64-character
hash and require provenance equality to the tuple value, with positive and
missing/altered-field refusal tests. Do not strip the tuple field, change its
bytes/digest, or weaken the external trust anchor.

No package integrity result exists. All hardware/installability flags in the
captured tuple remain false; no release or device claim follows from this
attempt. After the schema/test correction is reviewed, rerun the exact in-memory
call against the same unchanged inputs and tuple digest.


## Strict schema correction and in-memory retry

The offline schema now requires `toolchain_tree_sha256` as a tuple field,
validates its lowercase 64-hex format, and cross-checks the value against the
independently hashed build-provenance receipt. Tests reject a tuple with the
field missing, an invalid digest, and provenance with the field missing or
changed. The real positive-path fixture now uses the current continuous D7000
tuple; the retained earlier companion diagnostic tuple predates this required
provenance field and is intentionally no longer accepted by this tuple schema.

The same externally anchored tuple and retained raw inputs were composed in
memory. Focused package tests: 8 passed, 0 skipped. The separate in-memory
validation returned 978,484 bytes (SHA-256
`0ca847469d7d05e48aba6a8b526b2087029a8e07f9fb48c9c958a3ba87f89dcf`); the
report says `package_returned_in_memory=true`, `file_written=false`, and
`hardware_admitted`, `hardware_tested`, and `installable` are all false. It
retains application identity `FM-1_500` and recovery identity `FM-1_000`; the
measured nested stage slack in this model is 13,964 bytes. These are offline
model results only, not evidence of stock-loader acceptance, device install,
recovery, or runtime/perceptual acceptance. No package file was written.
