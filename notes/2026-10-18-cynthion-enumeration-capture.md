# Passive USB enumeration capture, 2026-10-18

Owner requested protocol capture before oscilloscope work. Current goal remains
recovery followed by functioning, web-installable Lunar; neither is accepted.

## Setup [verified]

Both TARGET ports owner-confirmed empty before volatile restore of official
analyzer238282B, SHA256
`5afd1741247da483876bbc7b0d87606ef34503558f31f638162409cb2f0ea5da`.
Run exited0. This replaces custom repeating-key gateware; no key is currently
loaded. No persistent Cynthion flash or FM1 firmware/loader commands issued.
Packetry process6555 claimed analyzer exclusively; cynthcap list could not open
it. CUA inspected actual window and started/stopped/saved captures successfully.
Old displayed file cynthion-v8-repeat-display-pass.pcapng was historical, not
current evidence. SuperQ did not quit Packetry; no successful quit claimed.

## Capture1: automatic speed [verified]

Owner connected TARGETC→bench01, still-powered FM1→TARGETA, RIGHT/ON unchanged.
404-byte attempt01-auto.pcapng, five analyzer custom events and zero USB packets.
VBUSvalid46.145221850s; LSidle56.827273400s; SE0bothlow56.827273550s;
stop84.016080500s. No device attach/reset/setup/descriptor exchange. Bench
kernel logged no newattach. This did not reproduce earlier descriptor-71.

## Capture2: fixed full speed [verified]

An extra7.9sec auto idle capture was started/stopped during menu verification;
not saved or counted as physical test. Menu coordinate selection did not apply;
keyboard Home/Down/Down/Return selected Full12Mbps, verified screenshot and
start event. Owner then unplugged only TARGETC hostend2sec and reconnected,
FM1A/RIGHTON unchanged per instructions.

Saved attempt02-full.pcapng4920bytes SHA256
`422a508f3879faa8cf4e4dd139ec5553be29f7a60458c5b5ca2cad905ef9db8d`.
File is big-endian pcapng. Independent block read and tshark agree126packet
records, each1–2bytes; firstbytes FF88,FA17,F920,F3one. All violate USB PID
complement rule. No valid SETUP/DATA/ACK/NAK/STALL or descriptor response.
Packets span27.367840466–31.677108150s, around cable removal/reconnection.
Events startFull0s, VBUSinvalid27.426888066s, VBUSvalid31.511019750s,
stop46.084753983s. No overflow event reported. Fresh bench08:27:08UTC lsusb
roots+KA6 only, no new kernelattach and no FM1identity.

Malformed records cannot be attributed to FM1 replies; no valid host transaction
was captured. Capture does not prove ROM state, exact analog voltage, signal
integrity, clock frequency, flash corruption or hardware damage. Official
troubleshooting warns invalid groups may result from capture-speed mismatch.
https://cynthion.readthedocs.io/en/latest/tutorials/usb_analysis.html#troubleshooting
Official docs confirm A/C shared analyzerpath and CONTROLmanagement:
https://cynthion.readthedocs.io/en/latest/tutorials/usb_analysis.html#connect

## Next dependency

Both captures stopped and saved. Analyzer remains loaded; Packetry Full12Mbps,
TARGETpowerON displayed. Owner asked about known-working keyboard/mouse,
or temporary KA6, for samepath control capture before scope conclusion.
No further reconfiguration or probing requested. Raw private evidence lives
under scratch/cynthion-enumeration-capture-20261018/, including load log,
bothpcapng,tsharkdecodes,JSONreviews and freshhostlogs. Not committed binaries.

## Control capture interrupted by RESET; fresh capture pending [verified]

Owner reported pressing Cynthion RESET while unplugging FM1. Packetry's USB
write request failed (0xe00002ed); dismissed via computer use. Fresh Cynthion
info reported official USB Analyzer. Saved 276-byte interrupted capture as
control01-reset-interrupted.pcapng; it contains only the capture-start event.
Started fresh Auto capture, verified active in Packetry. Asked owner to connect
a working keyboard/mouse to TARGET A, keeping TARGET C→bench01 and CONTROL→Mac,
without RESET/USER. Connection remains pending; no control-device acceptance.
