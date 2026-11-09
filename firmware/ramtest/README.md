# M4 RAM test image (dev kit)

A RAM-only, SDK-free pi32v2 image for the AC79 dev kit, loaded and started
by `tools/ram_runner.py` through the mask ROM (milestone M4 of docs/18). It:

1. sets up UART1 TX on PB3 at 1,000,000 baud (the dev kit's debug header,
   read by the Tigard);
2. prints `LUNAR_RAMTEST ready=1 build=<id> entry=0x01c02000 bytes=<n> ...`;
3. prints ten `LUNAR_RAMTEST beat=<n>` lines, then `LUNAR_RAMTEST reset=app`;
4. clears the 16-byte `usb_update_mode` boot marker at `0x01C7FD80` and
   resets the chip through P33 as the SDK's `__cpu_reset` does, so the
   installed application boots again.

If the reset does not happen it prints `LUNAR_RAMTEST reset_failed=<why>`
and then `LUNAR_RAMTEST stuck beat=<n>` lines; power or the Update/Reset
buttons recover the board. A UART that never signals "sent" costs one
bounded timeout, after which output is skipped and the reset still runs.

The logic is in `ramtest.c`, which takes register access through a small
I/O table, so `tests/test_ramtest_image.py` compiles it natively and checks
every register it touches. `main.c` and `startup.S` bind it to the chip;
`app.ld` links it at `0x01C02000` inside 16 KiB.

Build (JieLi clang in a container on a Docker host):

    LUNAR_BUILD_ID=<id> LUNAR_SESSION=<label> \
        bash tools/jieli/link-diagnostic.sh <docker-host> <toolchain-dir> <scratch-dir> ramtest

That writes `build/jieli-ramtest/`. Run it as in
`notes/2026-11-08-ram-runner-devkit.md` §3. It is for the dev kit only: the
FM-1's UART pins differ, and running anything on the FM-1 needs its own
owner approval.
