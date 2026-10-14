# NOR writer caller and stack closure review

Date: 2026-10-14
Branch: `codex/2026-10-14-nor-closure-completeness`
Source worktree HEAD before this change: `24299750c22c74293d8fd15b59bf24577d714681` (includes the reviewed watchdog prototype). The retained audit ELF was built from an earlier source snapshot, but its `firmware/third_party/dinghy/hal/fm1_flash.h` exactly matches this worktree at SHA-256 `3e9ba8a117c3786bb229b8ce9d86823f36b1e58e3280fd6e635098db0b3ca291`. This was a read-only re-analysis of the ELF, not a fresh link of the complete current tree.

## Concrete linked facts

Target ELF: `/home/claude/mvave-fm1/nor-watchdog-target-closure-20261014/nor-closure-analysis-v2/linked/lunar-app-probe.elf`, SHA-256 `c0429a5f8849f1afa17043953fca4fc5582a4466a75934c2e4ff939bb895e2c6`. Vendor objdump listing `full-disassembly.txt`, SHA-256 `ffbd0369d44965e422a334e071625cbe4d83ea6f4eb8cf86281e25f152f3ca36`; symbol listing SHA-256 `1df928e4e89a6eda17989fe9487ae738ba25e32dcb17654f52ca93be4fde3c00`.

The listing and symbol table establish the following linked call/argument chain:

- `fl_erase4k` at `0x0204e9d8` loads `fl_erase4k_ram` at `0x01c00000` into `r0` (`0x0204ea32`), calls pointer-preserving `fl_far` (`0x0204ea38`), then dispatches through `r2` (`0x0204ea3e`).
- `fl_write` at `0x0204ea5e` loads `fl_prog_ram` at `0x01c00580` into `r8` (`0x0204eab4`). It copies each source byte (`0x0204eacc`/`0x0204ead2`) to page buffer `SP+4` before IRQ masking and WDT stop (`0x0204eadc` onward), moves the RAM target through `r0`/`fl_far` and dispatches via `r7` (`0x0204eafc`). It passes `SP+4` as the RAM program source pointer and `SP+260` as elapsed-time output (`0x0204eaf2`/`0x0204eaf4`). The stack frame is 264 bytes.
- The only linked production direct wrapper callers are `ota_erase` -> `fl_erase4k` and `ota_prog` -> `fl_write`; an analysis-only force-retain function is separately reported and not counted as production. `ota_erase` supplies its elapsed-time pointer as its own `SP+0` (`0x02050bda`). `ota_prog` forwards caller source pointer through `r5` to `fl_write` (`0x02050bea` and `0x02050bf6`); `fl_write` copies bytes to its page buffer before dispatching into RAM.
- RAM entry arguments therefore resolve to scalar erase/program addresses and lengths, stack-backed elapsed outputs, and a stack-backed page buffer for program. The RAM erase/program code itself has no direct call target in the retained linked listing.

The checker now verifies the exact target-register loads, the staged-page sequence, `fl_far` pointer preservation, the two indirect dispatch registers, the direct caller inventory, and the stack-relative output/source setup. Negative fixtures mutate target and pointer evidence to ensure the checks fail closed.

## Remaining unresolved evidence

The listing only gives offsets from the pi32v2 stack pointer. It does not prove the live stack base, bounds, or SRAM region at the moment `fl_write` and `ota_erase` execute. Consequently, `SP+4`, `SP+260`, and `ota_erase SP+0` are structurally stack-relative but not proven physically resident in SRAM while XIP is unavailable. The API-level `ota_prog` source pointer is caller supplied; it is read before the RAM handoff, then copied to the stack page buffer, but this audit does not prove its wider lifetime or caller allocation.

The checker deliberately leaves `runtime_stack_address_in_sram_proven=false` and does not set whole static-data or control-flow closure true. No XIP-off runtime, watchdog behavior, physical NOR timing, interrupted write recovery, SAVE admission, or hardware result is established. Storage remains disarmed.

## Validation

On Hera worktree `/home/claude/worktrees/nor-closure-completeness`:

- `python3 -m unittest tests.test_native_nor_writer_closure -q` — 17 tests passed.
- Directly loaded the checker and ran `audit_writer_callers()` against the retained full disassembly and symbols — passed with the exact caller/argument facts above and runtime stack residency false.
- No rebuild or hardware/device operation was performed.
