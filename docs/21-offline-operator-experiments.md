# 21 — Reversible operator experiments without a device

`tools.fm1_pi32.run_operator_experiment` applies an exact-byte patch to a
verified V15 application and executes the changed operator routine in the
bounded Python interpreter. This connects a specific firmware edit to
reproducible numerical observations and a reversible manifest.

The experiment is entirely in memory. It does not write a file, start a
vendor runtime, access a device, or establish how a changed image behaves
on hardware. The interpreter's parallel-packet timing remains inferred;
see [17 — Operator ABI](17-operator-abi.md).

## Exact source and limited patch scope

**[verified]** The original application must have SHA-256
`306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203`.
The existing `run_operator_kernel` entry point continues to accept only that
exact stock image.

Every patch uses the [rebuild contract](14-firmware-rebuild.md): exact source
hash, exact expected bytes, equal-size replacement, no overlapping ranges and
preserved version identity. The complete patch range must fit inside one of:

| Decoded-application file range | Permitted experiment content |
| --- | --- |
| `0x85064 <= offset < 0x85284` | Verified three-operator kernel |
| `0x89f8e <= offset < 0x8af8e` | Adjacent exponent and log-sine lookup tables |

**[verified]** Startup, caller code and the rest of the application remain
byte-identical. The interpreter maps the changed kernel as readable/executable,
the changed tables as read-only, and synthetic state, stack and output as
readable/writable. Unsupported instructions, illegal memory, ambiguous
packets and exhausted instruction budgets stop execution.

## API

```python
from tools.fm1_pi32 import run_operator_experiment

patches = [{
    "offset": 0x85256,
    "expected_hex": "c0f10df0",
    "replacement_hex": "c0f10cf0",
    "label": "Offline final operator output shift 13 to 12",
}]

# Four words per row: prior attenuation, new level, phase increment, phase.
# Two quiet positive modulators and a positive-quarter carrier.
operators = (
    (16384, 0, 0, 0),
    (16384, 0, 0, 0),
    (1, 16383 << 14, 16 << 12, 0),
)

result = run_operator_experiment(
    original_application_bytes,
    patches,
    operators,
    feedback=(0, 0),
    kernel_feedback_shift=16,
    instruction_budget=20000,
)
```

The result includes `samples`, `feedback`, final `operator_words`, instruction
count, `source_sha256`, `executed_image_sha256`, and the reversible `manifest`.
Its `status` is `experimental`, `experimental` is true, and
`hardware_behavior_verified` is false. The report includes the patch ranges;
it does not return a complete application image.

To reconstruct or roll back the image in memory, use `rebuild_application`
and `rollback_application` with that manifest. File export remains an explicit
separate operation under the rebuild workflow.

## Verified half-scale experiment

**[verified]** At file `0x85256`, the original instruction shifts `r0` left
13 bits into `r15`, paired with the following frequency load. The replacement
changes the shift to 12 and preserves the packet marker, destination register
and source register. Exactly one application byte changes.

For the states above, **all 64 output samples and both final feedback words
are exactly half the stock interpreter result**. The quiet positive modulators
remain zero when the feedback changes, so this vector isolates the carrier's
final scale. It does not imply every voice or feedback configuration will
simply halve: the altered output also feeds subsequent feedback calculations.

| Observation | Stock execution | Experimental execution |
| --- | --- | --- |
| First four samples | `49152, 1687552, 3334144, 4980736` | `24576, 843776, 1667072, 2490368` |
| Final feedback words | `66928640, 67018752` | `33464320, 33509376` |
| Instructions executed | 6070 | 6070 |

The executed application SHA-256 is
`f4420e28a1e4e7892bd696e10592329b1d23846cd279146dbb55281f8509a2f8`.
With the label shown above, the manifest SHA-256 is
`a1e2e53ae1e978df4828e9e6b67fff79ab372cabebaeeb079e8cd788a25a6a0c`.
The original input remains unchanged, and manifest rollback recovers every
original byte. The strict stock entry point rejects the modified image.

## Validation boundary

**[verified]** The focused interpreter suite passes 41 tests with the private
V15 application configured: 38 synthetic cases and three private-image tests.
The experiment tests cover exact allowed-range boundaries, crossing-boundary
rejection, wrong originals, wrong expected bytes, unsupported changed code,
the half-scale vector and byte-exact rollback. The earlier stock execution
comparison covers 19 blocks against the separate integer reference.

Run the private tests with `FM1_V15_APPLICATION` pointing to a locally
extracted exact V15 application:

```powershell
$env:FM1_V15_APPLICATION = "C:\private-evidence\v15-app.bin"
python -m pytest tests/test_fm1_pi32.py
```

This demonstrates the stated behavior under the reconstructed instruction
semantics. Independent confirmation of packet timing, complete CPU behavior,
audio equivalence and any installation/recovery procedure remain separate
work. No vendor application image is distributed with these tests.
