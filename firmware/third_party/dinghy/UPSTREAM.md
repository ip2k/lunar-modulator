# Dinghy FM1 platform

Unmodified application platform sources from https://github.com/zvenson/dinghy
at `d44df7db09b98ccad2f1233b8f83f5f09c04829e`. GPL-3.0-only;
retain LICENSE, LICENSING.md and source notices. Credit zvenson, Leo Kuroshita
(@kurogedelic), Hügelton Instruments, Felucca and SLOOP/isod89.
The generated Terminus font is SIL OFL 1.1; its notice is included.
No logos, SDK binary components, loader sources or packaging tools are imported.
`inventory.json` pins current local source bytes. Its `local_modifications` map distinguishes intentional local changes from upstream-original bytes. `hal/fm1_flash.h` records its upstream and local SHA-256 values and the FM-1 ICFG-preservation, status-deadline, caller-span validation, aligned page-staging changes, test seam, and guarded watchdog lease. `hal/fm1_sys.h` records its upstream and local SHA-256 values and checked P33/watchdog transfer additions; the original bytes match the initial import. These are GPL-derived platform files. No other listed source is locally modified.

This platform's updater and settings layout must be reviewed against the stock
partition safeguards before device admission. Import and compilation are not
installation authorization or proof of stock-layout compatibility.
