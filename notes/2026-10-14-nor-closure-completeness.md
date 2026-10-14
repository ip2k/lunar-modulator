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

## Follow-up: exact wrapper ordering and runtime stack check proposal

The caller audit now requires the observed instruction order in `fl_write`: read
caller bytes, copy them to `SP+4`, call `irq_save`, call
`fm1_wdt_stop_checked`, load/dispatch the RAM entry through `fl_far`, then pass
`SP+4` and `SP+260`. The fixture rejects a page store moved after IRQ save.
The `fl_far` audit now requires exactly these five target instructions:
`sp += -4`, `[sp] = r0`, `r0 = [sp]`, `sp += 4`, `rts`. A negative fixture
inserts an `r0` clobber and is rejected. These checks establish the linked
sequence, not global register/stack ABI correctness.

For the exact retained link, `app.ld` SHA-256 is
`6a9f41205e482fbdf2d24dc418416e45a3a8e1781d3e594279d751335af8942a` and
`crt0.S` SHA-256 is
`2212471c4a70e94022ba24ef65a4b208fadd5f7e33f80745c5f5e8b9f4aa840c`; both
match the retained source overlay byte-for-byte. The linker declares user stack
bounds `_ustack_lo=0x01C74100` to `_ustack_top=0x01C7A000` and supervisor bounds
`_sstack_lo=0x01C7A100` to `_sstack_top=0x01C7C000`, leaving the guard gap
`0x01C7A000..0x01C7A100`. `crt0.S` sets `sp` to `_ustack_top` and `ssp` to
`_sstack_top` before calling `fm1_cstart`; the target listing confirms
`fm1_cstart` descends its SP by 3052 bytes. `fl_write` descends its current SP
by a 264-byte local frame after saving registers. `ota_erase` also reserves
four local bytes before passing `SP+0` to the RAM writer. The corresponding
source hashes do not make the active stack at the eventual OTA callback known:
`fm1_guard.h` explicitly applies one broad stack window because it does not
know which EMU stack applies in supervisor main-loop context.

A bounded future guard should run before IRQ masking/WDT stop and before the RAM
dispatch: read the active `sp`, require it to lie in exactly one linker-declared
stack interval (never the gap), and require enough downward headroom for the
maximum audited post-check frame/call depth. It must account for the already
allocated caller and `fl_write` frames, plus any helper frame introduced by the
check. A page-buffer pointer check alone is insufficient. This proposal is not
yet proven against the pi32v2 active-SP/interrupt ABI, concurrent interrupt
stack use, or worst-case nested call depth; do not set
`runtime_stack_address_in_sram_proven` until a target runtime check and linked
call-depth bound establish those points.

The follow-up focused suite passes 17 tests. Direct execution of
`audit_writer_callers()` against the retained full disassembly and symbol dump
passes, reports the ordered page-copy/IRQ/WDT sequence and five-op far shim,
and leaves runtime stack residency false. No rebuild, hardware operation, or
SAVE admission occurred.
