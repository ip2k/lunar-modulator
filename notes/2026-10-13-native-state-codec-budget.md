# Native song/set codec budget

The default thirteen-engine image and selectable engine/effect/song/set builder
remain the release objective. This measurement evaluates reuse of the existing
C99 streaming codec; it does not enable content loading or change flash layout.

## Target measurements

`tools/native/measure_state_codecs.py` compiles eight codec translation units
with `-Os` and `-Oz`, distributed across sixteen independent Hera containers.
It uses the pinned pi32v2 compiler, `-mcpu=r3 -mfprev1`, freestanding function
and data sections, and the target headers. It emits assembly, object sections,
undefined symbols and source/tool/output hashes. No closed SDK archive is used.
All sixteen final chunks exited zero without OOM [verified].

| Measurement | `-Os` | `-Oz` |
| --- | ---: | ---: |
| Binary reader fixed entry frame, including register saves | 8,244 B | 8,268 B |
| JSON convenience reader fixed entry frame | 1,592 B | 1,588 B |
| Binary writer workspace, target ABI | 284,884 B | 284,884 B |
| JSON writer workspace, target ABI | 476,632 B | 476,632 B |

These are emitted target values [verified]. The frame recognizer reports only
the leading fixed stack reservation. Nested functions, source/sink callbacks,
interrupt overlap, dynamic reservations and the caller's frame are **not**
included. Unrecognized/no-reservation prologues remain unmeasured, not zero.
The writer sizes are caller-provided workspaces, not their function frames.
The existing host `test_reader_state_is_small` bounds the tokenizer, JSON-reader
structure and inflater separately; it is not a target stack high-water test.

The current native linker map reserves 24,320 B for the user/main stack and
7,936 B for the supervisor stack [verified: `firmware/native/app.ld`]. The
binary reader alone exceeds the smaller stack by 332 B at `-Oz`; do not call
it from the interrupt path. Main-stack suitability still needs the complete
loading call path, callback budget, interrupt separation and hardware guard /
high-water verification. The remaining 16,052 B after the reader frame is not
an established safe margin.

## Reader-only link

The five `-Oz` objects (binary container, inflater, Movy item codec, numbers and
names/CRC) were combined with the pinned linker:

```sh
pi32v2/bin/ld -r --gc-sections --undefined=fm1_state_bin_read \
  shard-08/codec.o shard-09/codec.o shard-10/codec.o \
  shard-11/codec.o shard-12/codec.o -o binary-reader-only-v2.o
```

The resulting relocatable component has 15,335 B of `.text*` plus `.rodata*`
and zero `.data*` / `.bss*` / `.sdata*` / `.sbss*` bytes [verified]. Symbol
inspection confirms that `fm1_state_bin_write`, `fm1_state_bin_writer`,
`fm1_movy1_encode` and `fm1_deflate` are absent [verified]. This is not a final
application link; runtime helper cost, final alignment and LTO may change it.

Its remaining imports are exactly:

```text
__adddf3 __divdf3 __divdi3 __floatsidf __ltdf2 __moddi3 __muldf3 __truncdfsf2
memcmp memcpy memset strcmp strlen
```

No heap, stdio, registry or SDK import remains in this component [verified].
The native application must supply and verify the above runtime dependencies.

## Evidence and limits

Private measurement files are under
`build/native-external-arenas-16-20261012/state-codecs-v3/`, mirrored from
`/home/claude/mvave-fm1/native-external-arenas-16-20261012/out/` on Hera.

- Final sixteen-chunk receipt: `state-codecs-v3-verification.json`, SHA-256
  `e3cf67614f4495187b20ddd6e691ec3e79245915d459d336776286767f5fc726`.
- Reader-only corrected section-summary receipt:
  `state-codecs-v3/binary-reader-only-v2-report.json`, SHA-256
  `708de63c5dccd1886188591a909c4bad037699db9cbe6c63eb3b1358adf2d17b`.
- Reader-only object SHA-256:
  `c733064d8aaf7662ec958e8c690b3db911e8d9ea43736644ab68905ba52ee634`.

The initial campaign retained successful compiler outputs but failed reporting
because this toolchain has no `pi32v2/bin/size`; the corrected tool uses its
existing `common/bin/objdump`. The first scratch link summary used a whitespace
expression which crossed an empty section row and omitted a 40-byte section;
the corrected `v2` link summary restricts parsing to one section row. Earlier
receipts are retained but are not the measurements quoted here.

Next native integration must use the reader with CRC checking enabled, validate
engine/module availability and allocator/rate admission before mutating the
application, and validate sequencer semantics independently. The streaming
Movy item reader preserves raw unknown items; successful decoding does not
prove the sequencer accepts their meaning. The browser writer/check workspaces
must not be imported into the FM1 application. No hardware command, flash write,
reset, recovery-loader upload or partition-policy change was performed here.
