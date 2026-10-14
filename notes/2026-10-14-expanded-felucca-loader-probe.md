# Felucca streaming-loader feasibility probe for expanded D9000

This is a host-only feasibility probe of maintained code, not an FM-1 loader, installable package, or recovery claim. It adapts the portable Felucca loader core behind fake NOR hooks to answer whether its sector transaction can honor the recorded FM-1_092 app boundary and directory-last ordering.

## Evidence and source

The reviewed primary source is Felucca v1.6 at pinned upstream commit `1727537624390cc3f9c7dff2456b43b3a8edb005` ([upstream repository](https://github.com/hugelton/Felucca), [portable loader core](https://github.com/hugelton/Felucca/blob/1727537624390cc3f9c7dff2456b43b3a8edb005/firmware/loader/ldr_core.c), GPL-3.0-only). SLOOP's pinned current `ldr_core.c` retains the same `0x93000` app high bound and record scan assumptions. Felucca's target `loader.c` uses a distinct HAL and fixed `FL_RANGE_OK` windows; none of that target adapter or HAL was changed.

The isolated derivative is in `firmware/third_party/felucca-expanded-offline/`. It carries the upstream license and pin in `UPSTREAM.md`. Its source has a compile-time host-probe guard, sets the app high bound to `0xD9000`, walks the app data sectors before sector `0x4000` (the expanded image directory), and omits the host-finish/update-record clearing and flash-record scan. Its test harness provides fake NOR and synthetic OTA bytes, not a live endpoint. The chip-key extraction path is replaced only in this test build with a fixed zero fixture key; therefore these tests do not establish chip-key/package identity handling.

## Measured target footprint context

A separate, unmodified link of Felucca's v1.6 production loader sources with the pinned JieLi toolchain completed in a networkless bounded container. Its linker placed `.text` at `0x01C0A800`, size `0x2018` (8,216 bytes), `.pool` at `0x01C0C818`, size `0x280` (640 bytes), and `.bss` at `0x01C0CAA0`, size `0x2A70` (10,864 bytes). The combined `.text` + `.pool` + `.bss` is 19,720 bytes, within its 80 KiB linker region and just under Dinghy's `0x4E00`/19,968-byte staged-body limit. This is evidence that the original source is compact enough to investigate; it is **not** a link/footprint measurement of the D9000 probe, a stack bound, or evidence that the loader can be staged safely.

## Fake-NOR checks

Command on Hera:

```sh
gcc -std=c99 -O2 -Wall -Wextra -Werror \
  firmware/third_party/felucca-expanded-offline/test_ldr_core.c \
  -o /tmp/felucca-expanded-offline-test
/tmp/felucca-expanded-offline-test
```

Result: `offline core test passed` (12 assertions). The core validates the synthetic whole-image CRC and per-sector consistency, writes within `[0x4000,0xD9000)`, leaves prefix and suffix bytes unchanged, puts the directory sector last, retries a readback mismatch, and the fake host can repeat the transaction after an injected erase/page-program interruption. A second case injects a readback mismatch on the final directory sector. These show behavior of this source copy with deterministic fake hooks only. The retry is explicitly a host restarting the test with the same full target bytes; it does not show that the actual SPL will re-enter the loader or that the device can resume autonomously. The probe also omits real FWSC decryption/identity, SysEx timing, USB endpoint behavior, and every target flash call.

## Blocking target integration constraints

The changed profile needs 213 erase sectors from `0x4000` up to (excluding) `0xD9000`. The current retained expanded layout places VM at `0xD9000..0xE9000`; the standard Dinghy/Felucca staging contract stages the loader in `0xE0000..0xE5000`, which overlaps that bank. The original target loader's record cleanup scans `0x93000..0xFC000` and protects only the old Felucca data band `0x97000..0xE0000`; using it would cross expanded reserved components. The probe deletes that record-clearing behavior, so it cannot complete the device-side transition, clear the persistent update record, or prove boot/recovery after success. No stage allocation or record ownership was established here.

The next concrete engineering dependency is a reviewed, non-overlapping persistent staging/record design for the FM1_092 expanded profile, including exact stock-SPL discovery semantics and power-cut recovery. Once that ownership is evidenced, a separate target adapter can bind an approved staging range and record lifecycle, retain all protected component checks, and then be linked with the exact JieLi toolchain and tested against the actual host package protocol. Until then this artifact is not target-writable, hardware-admitted, installable, or recovery-validated.
