# Dinghy FM1 base HAL selection

Selected source derives from https://github.com/zvenson/dinghy at
`d44df7db09b98ccad2f1233b8f83f5f09c04829e`, carried through Lunar's historical
`cccd21cc5dc82859ed8a5d84f0a7a40646d07353` tree. GPL-3.0-only; retain LICENSE,
upstream LICENSING.md and source notices. Credit zvenson, Leo Kuroshita
(@kurogedelic), Hügelton Instruments, Felucca and SLOOP/isod89.

[verified: source, 2026-11-01] Only the inventoried base HAL, LCD source and
vectors are imported. No platform app, flash, OTA, USB, settings, generated font,
logo, SDK component, loader or recovery source is present. LICENSING.md is the
unmodified upstream licensing overview; its descriptions of other components
are provenance, not a statement that those components are imported here.

`inventory.json` pins every imported source and its intentional local changes.
The diagnostic selection changes `fm1_irq.h`'s nested-fault automatic reset to
a halt. The new diagnostic startup/linker/platform glue lives separately under
`firmware/native/` and retains GPL notices for the derived portions.

The combined diagnostic is GPL-3.0-only even with switchable GPL engines omitted.
SDK-free GPL distribution is possible subject to the combined licences and
complete corresponding source requirements. This source import and offline link
are not device or release admission. No target performance or hardware claim is
established by the historical source's earlier tests.
