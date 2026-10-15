# Dinghy FM1 platform

Application platform sources derive from https://github.com/zvenson/dinghy
at `d44df7db09b98ccad2f1233b8f83f5f09c04829e`. GPL-3.0-only; retain
LICENSE, LICENSING.md and source notices. Credit zvenson, Leo Kuroshita
(@kurogedelic), Hügelton Instruments, Felucca and SLOOP/isod89. The generated
Terminus font is SIL OFL 1.1; its notice is included. No logos, SDK binary
components, loader sources or packaging tools are imported.

`inventory.json` pins current local source bytes. Its `local_modifications`
map distinguishes intentional local changes from upstream-original bytes.
`hal/fm1_flash.h` records its FM-1 ICFG-preservation, status-deadline,
caller-span validation, aligned page-staging changes, test seam, guarded
watchdog lease, and naming update. `hal/fm1_sys.h` records checked P33 and
watchdog transfer additions. `src/platform.c` records the guarded UART1 MIDI
hook, compile-gated IRQ occupancy instrumentation with preserved ICFG and
unchanged service cadence, and the LUNAR-prefixed configuration/identity macros. `src/usb.c`
records the Lunar Modulator USB strings and LUNAR-prefixed interface macros.
`src/bootguard.h`, `src/gfx.c`, `src/ota.c` and `gen/lunar_font.h` record
their local naming adaptations. The OTA parser retains the exact legacy
`FELUCCA-LOADER-1` signature bytes to recognize existing loader data; that
protocol marker is compatibility data, not product or platform branding.
Each entry includes the upstream and current local SHA-256.

This platform's updater and settings layout must be reviewed against the stock
partition safeguards before device admission. Import and compilation are not
installation authorization or proof of stock-layout compatibility.
