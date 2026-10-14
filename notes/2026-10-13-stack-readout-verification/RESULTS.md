# Native stack measurement readout

[verified] Opt-in watermark probes now overlay two footer lines after shared
application drawing. They show minimum observed user/system patterned margins
in bytes and completed sample count. Out-of-range or unavailable margins show
dashes. Fixed-width conversion avoids adding a formatter dependency. The footer
owns rows208..239 with four-pixel left padding and a three-row text gap.

[verified] Thirty ASAN/UBSAN tests passed in thirty Hera containers, with zero
exit codes and no OOM. They cover all user-margin values, system values,
unavailable margins, uint32 sample limit, adjacent buffer sentinels, indexed
TFT output validity, text widths and untouched pixels outside the footer.
The actual TFT renderer generated preview.png; visually inspected with no
clipping or overlap. It shows synthetic maximum margins, not device readings.

[verified] The full thirteen-engine, twelve-voice Shapes FIRST ORBIT target
linked with216064 instance-pool bytes. Strict entry/artifact, exact watermark
painter/call byte, SDK-free/eFuse and embedded production-content checks pass.
Target ELF SHA256: 35655a21de5c08d09fa19ef2fd4f253efbc107346c6e107a1988dca4e69dac29.
Source hashes and terminal container receipts are saved alongside this note.
No device command was issued. These values remain unmeasured on hardware;
readout changes require refreshed startup/stack/IRQ/timing assessment before
physical admission. Settings migration/physical rollback, browser builder/
installer, licensing and review/CI/integration remain open.
