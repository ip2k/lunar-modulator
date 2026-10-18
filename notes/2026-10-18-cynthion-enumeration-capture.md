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

## Mouse control fails through analyzer [verified]

Owner connected a mouse to TARGET A, C→bench01 and CONTROL→Mac unchanged.
Packetry detected low-speed attachment, resets and traffic. Fresh bench log
08:34:48 UTC shows low-speed devices64–68, descriptor/setup-address errors -71,
and unable to enumerate. No recognized mouse in lsusb. Stopped/saved through
CUA as control02-mouse-auto.pcapng, 109868 bytes, SHA256
0be23643253bfe1dca8c52883c330f328d9b6170aea106c41beb7a265d7b12ed.
Independent block review: 2107 custom events, 1161 USB packet blocks. Forty-eight
SETUP-PID and forty-eight DATA0-PID records have valid PID complements; this
alone does not establish complete valid transactions or a device response.
Control path has not passed. The mouse's failure prevents attributing the
FM1 failure specifically to its firmware/hardware. Asked same mouse directly
on bench01, bypassing Cynthion; FM1 remains detached. Direct result pending.
Private receipts: host-mouse-control.txt, control02-tshark.txt,
control02-review.json. Packetry stopped, official analyzer, Auto speed.

## Direct mouse passes; replacement-cable comparison pending [verified]

Fresh bench 08:35:41UTC: same mouse enumerated directly at usb3-1 as 17ef:6019,
Lenovo USB Optical Mouse, HID driver bound. Prior Cynthion path used usb3-2;
port difference is a confounder, not a proven cable or Cynthion hardware fault.
Asked replace C→bench cable with known data cable and use the successful direct
mouse port, then reconnect mouse→A, keeping FM1 detached/CONTROL→Mac.
Fresh Auto capture started and active verified through CUA before confirmation.
Next inspect fresh USB/kernel and Packetry, save unique control03 capture.

## Replacement-cable mouse test also fails [verified]

Owner confirmed replacement C→bench cable and mouse→A. Fresh host log shows
usb1-1 devices114–117, low-speed descriptor/setup errors -71, no mouse identity.
Direct success was usb3-1, so the requested identical-host-port comparison is
not established by kernel paths. Packetry shows incomplete setting-address
requests. Stopped/saved control03-mouse-replacement.pcapng, 70308 bytes, SHA256
dcb74ad2b1248e723799ef074f8a565b87540ea5f70221d6f0fb45578af3920b.
Requested complete Cynthion power removal: both TARGET cables and CONTROL off,
wait5sec, reconnect CONTROL only, keep FM1/mouse detached. Await confirmation.
This tests retained PHY state as a hypothesis; no confirmed cause or damage.
Official analyzer source uses UTMITranslator and non-driving op_mode01; no code
changed or custom gateware loaded in this step. Private host receipt:
host-mouse-replacement.txt. Next check analyzer identity after cold start,
then arrange fresh known-device control before returning to FM1 recovery.

## Cold reset completed, next control pending [verified]

Owner confirmed CONTROL only after complete cable removal. Fresh cynthion info
reports USB Analyzer 1d50:615b bcd0104. Fresh Auto capture started via CUA,
active/empty verified. Asked reconnect replacement C cable→bench01 then mouse→A,
FM1 detached/noUSERnoRESET. Await connection; no cold-reset control result yet.

## Cold-reset mouse still fails; fixed-low comparison active [verified]

Fresh bench08:40:38UTC shows usb1-1 devices118–121 descriptor/setup -71,
no mouse identity. Auto capture displayed only start/VBUSvalid21.748578316s/
LSidle31.730483450s. On stop/save Packetry reported "sending on a closed
channel"; dismissed via CUA. Saved control04-cold-auto.pcapng (size/hash below).
Treat recording as incomplete, not proof of absent host traffic. Cold reset
did not restore mouse enumeration; retained PHY-state cause not established.
Selected fixed Low1.5Mbps via keyboard, verified label, started fresh capture.
Asked owner flip only TARGET C USB-C plug180degrees/reconnect same socket,
confirm TARGET C label (not AUX), keep mouseA/CONTROLMac/FM1detached unchanged.
Await reply; next inspect capture+bench and save control05 unique file.
control04: 67804 bytes, SHA256 e24627cd6f09663f8ce8ba11e3b11588590967383906a77b32031917ac28c1a6.

## Fixed low + TARGET C orientation still fails; FPGA-offline control pending

Owner flipped TARGET C plug. Fresh bench host-mouse-flipped.txt shows usb1-1
122–125 descriptor/setup errors -71, no identity. Stopped/saved through CUA:
control05-low-flipped.pcapng 68696B SHA256
8a8b6ab914ff9a8f77be34b5adbd784d4c760e70437cc72f4e0a0b8091b9c975.
Independent blocks:2003custom/110USB. control04 saved file has1992custom/96USB,
despite GUI showing only3events; the earlier display description was not a
complete file analysis. Retain closed-channel caveat, not zero-packet claim.

Reviewed installed Apollo source: info --force-offline requests debugger
handoff then calls force_fpga_offline. Executed supported command after capture
stopped/saved; confirmed Cynthion r1.4 Apollo Debugger 1d50:615c (not analyzer).
No persistent flash write. This removes running analyzer gateware from next
comparison. Asked mouse unplug/replug at A, keep C/CONTROL, FM1 detached.
Await reply; then fresh bench enumeration. Private offline-control.txt receipt.
Official button/port reference: https://cynthion.readthedocs.io/en/latest/hardware/device_overview.html

## Mouse enumeration passes after analyzer restore and software power cycle [verified]

Owner replugged mouse with FPGA offline. Fresh host receipt at08:44:33UTC
showed no new attach, so this is inconclusive: installed r1.4 platform source
maps TARGET VBUS switches to FPGA pins, and offline state does not establish
powered passthrough. Private host-mouse-fpga-offline.txt preserves the receipt.

Restored official analyzer with supported cynthion run analyzer (exit0; no
persistent flash). Initial restore still produced -71 retries. Through CUA,
verified TARGET-A power source TARGET-C, toggled TARGET power off, selected
fixed Low1.5Mbps, started capture, then toggled TARGET power on. At08:45:46UTC
bench01 enumerated Lenovo mouse17ef:6019 atusb1-1 and bound HID. Packetry
independently decoded device/config descriptors, SET_ADDRESS and mouse name.
This validates this low-speed path; exact cause is not isolated because analyzer
restore, fixed speed and software power cycling were combined. It does not
establish full-speed operation or any FM1 recovery state.

Saved control06-low-software-power-pass.pcapng through CUA; verified806876B,
SHA256 cc46944b45675ab9a104a7e9c788a26fb9a6583f7b82a1962f742e6aa67c1013.
Independent tshark decoded vendor17ef/product6019/EP0max8 atframes91,209.
Private host-mouse-software-power.txt contains successful host enumeration.

Fresh fixed Full12Mbps capture is now running, TARGET power on. Asked owner
remove mouse only, connect FM1 atA LEFT/OFF then switch RIGHT/ON; keep
CONTROL Mac and C bench01, noUSER/RESET. Await confirmation, then inspect
Packetry and fresh bench logs, stop/save unique FM1 capture. No firmware writes.

