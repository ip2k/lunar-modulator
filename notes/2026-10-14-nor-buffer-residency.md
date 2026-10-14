# NOR program source residency

Date: 2026-10-14. This is a host-side source fix for the latent caller-buffer hazard in Dinghy's NOR writer. It does not bind SAVE, change its admission state, or establish that the NOR path is safe to use on hardware.

At base 8d103100dbecfe079a65068d5bbc4676a160b89c, fl_write passed its caller's pointer directly to fl_prog_ram. That RAM routine dereferences the pointer while XIP is disabled. The production SAVE service is still unadmitted and has no bound program callback; project_store can nevertheless provide stack-backed buffers to a future callback, so pointer residency needs to be an explicit property of the HAL boundary.

fl_write now validates the complete source span before the first write, copies each at-most-256-byte chunk to an aligned stack page while XIP is available, and passes only that page to fl_prog_ram. The validator accepts ordinary SRAM [0x01C00000,0x01C80000) and the actual FM1 XIP mapping [0x02000000,0x020FC000). It rejects null nonempty spans, integer wrap, spans crossing either boundary, SFR/MMIO, invalid destination arithmetic, and an XIP source overlapping the flash destination (a streaming page copy cannot preserve later source pages if earlier writes overwrite them). Zero-length writes are accepted without dereference. No status polling, interrupt, watchdog, or storage-admission policy was changed.

Evidence checked: fm1_xip.h defines the mapped XIP address as 0x02000000 + physical_offset - 0x4000, so the 1 MiB flash end maps to 0x020FC000; firmware/native/app.ld reserves RAM through 0x01C74000 within the accepted SRAM window; fm1_sys.h has the same broad RAM/XIP readability ceiling. Repository search found fl_prog_ram called only by fl_write; platform.c calls fl_write for store and settings writes. These address checks are a source-level target policy, not evidence that arbitrary runtime pointers are valid on every possible build.

The host fixture tests SRAM/XIP boundaries, MMIO, pointer and destination overflow, overlap, zero length, and a 300-byte multi-page write whose exact bytes are captured by the NOR mock. It proves the shim passes the copied payload through the modeled path; it is not target ABI or hardware evidence.

Changed-file SHA-256:
- firmware/third_party/dinghy/hal/fm1_flash.h: 318aa33c7560e1710a5d79a3e5b43016254a24b8ffea25938de32f2d7d409f6d (base file: c592536796274b0ca49cfad2fc1e8e3e0350cc6f115f27120fe582c5743cbe7d).
- tests/native/test_dinghy_flash_transport.c: 834713c83857be1cdda98b7af5f0f152c5f8ece0626b9fb9667dc2357c43f407.

Checks: pytest -q tests/test_dinghy_flash_transport.py passed (1 test); direct GCC C harness compile with -std=gnu11 -Wall -Wextra -Werror -Wno-unused-function -Wno-int-to-pointer-cast and execution passed; git diff --check passed. ASan/UBSan could not link in this Hera environment because libasan.so.8.0.0 and libubsan.so.1.0.0 are absent. No target link/disassembly was rerun for this change, and no hardware was accessed.

Remaining gates: re-run a pinned pi32v2 link/map or stack analysis to quantify the 256-byte local buffer and verify the generated loop remains self-contained; independently resolve the pre-existing WIP/watchdog/IRQ contract and SAVE callback admission before considering any target execution. The build remains noninstallable and storage admission remains false.
