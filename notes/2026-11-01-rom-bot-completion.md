# Pico ROM BOT completion correction — 2026-11-01

This source-only correction applies to kurogedelic's MIT FM-1-transporter at
`a7fb5e8ac692c528f8ed29e325911a3f4b8111d6`, after our existing RP2350
`0001` patch. It is stored as `tools/fm1-transporter/0002-exact-bot-completion.patch`.
The ignored local reference checkout was read, not edited. The normal
`build.sh`, generic `fm1t.py`, V15 shim and prior Pico UF2 are unchanged.
No Pico build, flash, USB, device operation, download or protected extraction
occurred. This does not admit the W01 optical witness or the separate
return-only candidate to hardware.

## Why and what changed

Before this patch, `pio_host.c::bot_cmd` accepted TinyUSB `SUCCESS` after a
short CBW, short data stage or short CSW; it also accepted a successful CSW
with nonzero residue. `jieli_uboot.c::cmd_exec` could interpret an incomplete
16-byte response. An FB06 upload could therefore report `OK` without exact
wire completion. The patched functions require CBW 31 bytes, data exactly the
requested length, CSW 13 bytes with current signature/tag/status zero/residue
zero, and a full 16-byte command response before reading its echo. Compile
time assertions bind the TinyUSB CBW/CSW struct sizes to the wire sizes.

The `got` output contract is preserved: when a data stage is attempted, it
receives that stage's actual byte count even if the later CSW fails; if CBW
fails or the command has no data stage, it remains untouched. Callers that
pass `NULL` still get exact-length validation. Invalid CDB lengths and a
nonzero data length with a null buffer are refused before copying or I/O.

## Causal host test

`tests/test_fm1_transporter_bot_completion.py` materializes only the pinned
upstream source files from the existing local reference Git object into an
owned ignored temporary directory. It applies tracked `0001` then `0002`,
extracts the **actual** `bot_cmd`, `cmd_exec`, ROM FB06 write and `do_memw`
function bodies (plus their source helpers), and compiles them with the fake
TinyUSB endpoint in `tests/fixtures/fm1_transporter_bot_harness.c`. It also
compiles the patched wire-size assertions. The source checkout is explicit via
`FM1_TRANSPORTER_SOURCE`; absent source skips this optional local integration
gate rather than reporting a pass. No network or target compiler is involved.

Command from this branch, with project-owned disposable test products:

```sh
PYTHONDONTWRITEBYTECODE=1 \
FM1_TRANSPORTER_SOURCE=/Users/likwid/Developer/mvave-fm1-firmware/reference/FM-1-transporter \
/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python -m pytest \
  -o addopts= tests/test_fm1_transporter_bot_completion.py -q -ra \
  -p no:cacheprovider --basetemp=scratch/rom-bot-completion/pytest-green
```

The baseline variant sets `FM1_BOT_CAUSAL_BASELINE=1` and omits only `0002`.
It must fail the short/partial/residue/15-byte-response cases. The corrected
variant must pass all cases. On this branch the baseline had **8 expected
failures, 11 passes**; the corrected patch had **19 passes**. Full small logs
are in the private audit area `audit-20261101/rom-bot-completion/` as
`baseline-red.log` and `green.log`. The fake endpoint injects successful short 30/31
CBW, 511/512 and 513/512 data, 12/13 CSW, residue, bad tag/signature/status,
timeout and disconnect. It records the actual CDB opcode: upload failures
emit FB06 but no FB08. The separate direct fake of `fm1_host_bot` returns a
15-byte successful response to causally exercise `cmd_exec`'s new guard even
though patched `bot_cmd` would reject it first. Four caller-output cases check
the preserved `got` behavior. These host checks do not prove Pico execution,
USB silicon timing, flashed UF2 identity, ROM memory contents or a nonreturning
FB08 jump. The later fixed-ROM mode/driver must be designed against the newly
reviewed return-only artifact; it is outside this patch.

The local ignored test stage under this branch's `scratch/rom-bot-completion`
is deleted by the fixture in normal/failed runs. Test logs and this small note
are retained in private project audit scratch. The temporary upstream source
worktree used to generate `0002` is removed after the patch and review record
are frozen; the ignored pytest basetemp directories are removed at handoff.
