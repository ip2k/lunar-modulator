# M5 test-pattern image (built, not run)

A RAM-only, SDK-free pi32v2 image for the FM-1's first visible sign of life
(milestone M5 of docs/18, which is on the
`feature/2026-10-29@fm1-release-plan` branch). It runs on core 0 with interrupts masked and does
the following:

1. Pulls PA2 low.
2. Stops TIMER4 and binds it at 40 MHz.
3. Configures SPI1 and draws the test pattern with the build id on the TFT.
4. Starts the key matrix.
5. Blinks every LED line `step` times, then pauses, forever. Six blinks mean
   every step succeeded.

A `lunar_m5_status` block in `.bss` records the step reached, the TIMER4
control word it found, the panel result, whether the timer fell back to a
spin, the matrix rows and the decoded keys. Its address is in the map file.

The image is linked at `0x01C02000` within 16 KiB by `app.ld`, and its
`.image` section is the whole binary. Build it with:

    LUNAR_SESSION=<label> bash tools/jieli/link-diagnostic.sh <docker-host> \
        <toolchain-dir> <scratch-dir> m5-test-pattern

That writes `build/jieli-m5/`: the ELF, the binary, the map, a disassembly,
`audit_link.json`, `report.json` (`diagnostic_report.py` profile `ram`) and
`sha256.txt`.

**Nothing loads or runs this image.** Running it needs a separate, authorised
hardware session with a reviewed RAM loader. The open questions are in
`notes/2026-11-08-fm1-board-layer.md`.
