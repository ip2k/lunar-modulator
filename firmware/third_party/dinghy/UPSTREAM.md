# Dinghy FM1 platform

Unmodified application platform sources from https://github.com/zvenson/dinghy
at `d44df7db09b98ccad2f1233b8f83f5f09c04829e`. GPL-3.0-only;
retain LICENSE, LICENSING.md and source notices. Credit zvenson, Leo Kuroshita
(@kurogedelic), Hügelton Instruments, Felucca and SLOOP/isod89.
The generated Terminus font is SIL OFL 1.1; its notice is included.
No logos, SDK binary components, loader sources or packaging tools are imported.
`inventory.json` pins the current local source bytes. Its `local_modifications` map distinguishes intentional local changes from upstream-original bytes; `hal/fm1_flash.h` records both its upstream SHA-256 and current local SHA-256. That file contains the FM-1 ICFG-preservation and status-deadline changes, not an upstream-original copy. No other listed source is locally modified.

This platform's updater and settings layout must be reviewed against the stock
partition safeguards before device admission. Import and compilation are not
installation authorization or proof of stock-layout compatibility.
