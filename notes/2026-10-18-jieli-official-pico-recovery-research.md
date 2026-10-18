# Official JieLi forced entry and Pico recovery priority

Owner steering,2026-10-18: recover this FM1 and return it to stock; prioritize
an easier Pico2W recovery-key trial over making oscilloscope qualification a
universal prerequisite. Official adapter ordered, expected in1–2weeks. Owner supplied a seller
description naming V4.1 Downloader, advertising AC701X/700X/698X/697X/696X/
695X/692X and a broad full-range claim. No explicit AC791N listing. Seller
operation-video profile: https://space.bilibili.com/15172053 . This is research and preparation; no device was programmed
or driven in this follow-up. Previous scope plan remains a fallback.

## Primary-source findings checked today

1. [Official AC79 USB-download instructions](https://doc.zh-jieli.com/AC79/zh-cn/release_v1.1.0/getting_started/preparation/update.html)
   explicitly recommend the forced-upgrade adapter for internal-flash parts and
   identify successful download mode as WL82 UBOOT1.00. Dev-kit UPDATE/RESET
   instructions are not evidence of accessible FM1 controls or a reset witness.
2. [V4 operating instructions](https://doc.zh-jieli.com/Tools/zh-cn/dev_tools/forced_upgrade/upgrade_and_download.html)
   describe restarting the target while a key is present: default/bit2 button
   operation interrupts output power for at least250ms; bit1 periodically cuts
   power and sends USB_KEY; bit3 continuously sends USB_KEY without cutting
   power. Thus continuous triggering is a documented vendor strategy. The
   document gives no exact waveform/cadence proving equivalence to either our
   repeat gateware or a MicroPython implementation. [inferred] A battery-powered
   FM1 may remain running across the adapter's VBUS interruption, so target
   reset cannot be assumed. No battery disconnect/internal work is proposed.
3. [V4 switch table](https://doc.zh-jieli.com/Tools/zh-cn/dev_tools/forced_upgrade/toggle_switch.html)
   confirms low switch3 is continuous USB_KEY, switch2 is ISP_KEY rather than
   a faster USB_KEY variant; only one low switch may be selected. Switch7
   enables the tool's own USB auxiliary interface. That interface is distinct
   from the target entering UBOOT. Default DP/DM mode is high impedance unless
   configured for other functions. Apply no setting until the purchased model
   is known; V2/V3/V4 and mass-production programmers are distinct products.
4. [Official AC791N mass-programming restrictions](https://doc.zh-jieli.com/Tools/zh-cn/mass_prod_tools/burner_1tuo8/commom_funcs.html)
   distinguish initial KEY provisioning from rewriting flash; AC791N blank-chip
   KEY provisioning needs the1-to-2 programmer, while1-to-8 flash rewrites have
   different conditions. This is not a reason to provision keys on this owned
   FM1. Retain the repository's eFuse/key-command exclusions and stock backup.
5. [Battery-programming manual](https://doc.zh-jieli.com/Tools/zh-cn/mass_prod_tools/burner_1tuo8/pcba_battery.html)
   has a USB battery mode requiring a normally running SDK with PC support.
   Do not assume that application-assisted mode recovers a nonresponsive FM1.

These are verified documentation statements, not physical acceptance of the
ordered adapter. No download.bat, isd_download, programmer firmware update,
key/eFuse command or factory profile was executed. A stock restore is separate
from forced entry; prefer the already reviewed/private unit-specific baseline
and allowlisted RAM-loader workflow rather than an arbitrary SDK factory image.

## The successful Pico reference versus our existing firmware

[verified: GitHub API today]
[czietz's gist](https://gist.github.com/czietz/9a94cf3c3e68f2ceb45fab682e1cbbd5)
latest code revision7c846aca65db47adbaad9e4e81dc1b9de1eb1f9d sends3000
nominal50kHz SPI key words on GP10(SCK/D+)/GP11(MOSI/D−), followed by2s
of1kHz PWM on D+, repeating indefinitely. It does not detect ACK or enumeration.
SPI setup/deinit timing remains unmeasured. Original Pico success does not
establish identical timing or electrical behavior on RP2350/MicroPython.

[reported: owners; comments reread today]
[czietz](https://github.com/ip2k/lunar-modulator/issues/2#issuecomment-5857481133)
and [masanaohayashi](https://github.com/ip2k/lunar-modulator/issues/2#issuecomment-5890460122)
report FM1 success; the latter reports backup/write too. No success is claimed
on this FM1. The reference is resistorless push-pull and unlicensed; do not
silently copy it into distributed firmware or substitute it for the open-drain
circuit required by docs/10 E1. A specific change to that electrical policy
would need an explicit owner decision, not inference from generic trial approval.

[verified: source and retained artifact]
The existing SDK-built Pico2W dongle avoids adding MicroPython/custom code.
`git diff dfc4894c -- dongle/firmware` is empty. Private retained UF2
`scratch/pico2w-recovery/status-replay.uf2` SHA256:
`8a89633eecd149b7b6422fdf815a9fc3efa0351b8aa7ca1e569dfcf788f2f717`.
Read [prior programming](2026-10-14-pico2-w-programming.md) and
[FAULT review](2026-10-14-pico-fault-offline-review.md): the prior Pico trial
stopped at SELFTEST/FAULT before sending a key. Missing external pull-ups were
an unverified wiring explanation, not FM1 rejection. Do not reflash simply to
repeat the same disconnected-line failure.

[verified: offline regression]17 tests pass in0.52s, Python3.12.14/pytest9.1.1:
`uv run --no-project --with pytest==9.1.1 --with rp2040-pio-emulator==0.88.0 --with adafruit-circuitpython-pioasm python -m pytest -o addopts= -p no:cacheprovider tests/test_usb_key_pio.py tests/test_dongle_model.py`.
The first attempt using the installer venv failed collection because
adafruit_pioasm was absent; the isolated uv environment resolved dependencies.
These tests establish model/waveform behavior, not analog loading or recovery.

## Concrete next test: minimal Pico circuit, manual host handoff

No scope is a prerequisite if the existing minimal circuit is assembled and
passes its own checks. No relay, Cynthion or transparent dual-socket fixture is
needed. Use the existing [minimal circuit](../docs/10-usb-key-dongle.md#3-hardware):

| Pico GPIO | Connection |
|---|---|
| GP14 | through100Ω to target D+ |
| GP15 | through100Ω to target D− |
| GP16 | through2.2kΩ to the same target D+ node |
| GP19 | through2.2kΩ to the same target D− node |
| GND | verified cable GND |
| VBUS pin40 | verified target5V conductor under reviewed USB-powered arrangement |

GP17 has no relay connected. These GPIO numbers differ from the gist and must
match the installed UF2; do not wire GP10/11 to firmware expecting GP14/15.
Reference [official Pico2W pinout](https://datasheets.raspberrypi.com/picow/pico-2-w-pinout.pdf).
Cable colours do not establish pin assignment. Use unpowered continuity to
verify each end, no data/power shorts, and the cable's USB-C source/sink
arrangement before attaching the FM1. The photographed socket's5.1kΩ CC
resistors cannot replace data-line pull-ups. Confirm supply routing prevents
an unintended second source/backfeed; no breadboard schematic is accepted
solely from colour or the socket photo. Scope/50Ω terminators remain unused.

1. Owner connects Pico's own USB to bench01 with every GPIO detached and FM1
   disconnected; identify actual runtime/BOOTSEL before opening/resetting it.
   Existing firmware may be reused; no need to reprogram a matching image.
2. Once parts/wiring are confirmed, test the isolated dongle circuit with no
   FM1 attached: require SELFTEST ok and no fault. Firmware starts keying after
   self-test; do not treat serial attach as an arming interlock. This is why the
   FM1 remains physically detached during setup. Stop on a fault.
3. With its tested key already running, attach LEFT/OFF FM1 via the verified
   target cable, then switch RIGHT/ON once. Fixed D+ clock, unchanged firmware.
   Do not connect a PC to that target's data lines while Pico remains attached.
   USB CDC on the Pico's own socket is a different bus.
4. On completed sequence, disconnect target cable from Pico fixture, leave FM1
   RIGHT/ON, and attach FM1 directly to bench01 with a normal data cable. Check
   real4c4a:8057 identity and UBOOT inquiry before any writer. DONE alone is
   not success. If stuck/FAULT, disconnect target from active fixture and
   preserve status; do not proceed to flashing or blindly restart the sequence.
5. After genuine ROM entry: inspect supported chip/loader identity, take and
   compare two fresh full reads before erase/program, bind the fresh state to
   a concrete unit-specific stock restore plan, verify stock SPL/OTA/cfg and
   keys are preserved, then bounded writes and complete readback. Historical
   target-specific restore scripts must not be invoked with stale campaign
   bindings. Stock boot/display/audio acceptance follows physical restoration.

[verified: fresh passive host inventory] bench01 answered SSH; lsusb listed
root hubs and KA6 only, no Pico or FM1. No/dev/serial/by-id directory. No serial,
SG, USB control/JTAG or flash command was sent. Exact UTC was not recorded for
that observation; it occurred during this follow-up. Owner asked to connect
Pico alone, confirm resistor availability and identify ordered adapter. Owner subsequently deferred connecting Pico until tomorrow. Resistor
availability is still pending. Those are the present physical dependencies;
no bench operation is scheduled or running. Existing unrelateduv.lock preserved.

## Ordered V4.1 compatibility conclusion

[verified: online research] Official AC79 documentation links the V4 forced-entry
manual directly. This supports trying that class of adapter with AC79, but no
primary V4.1-specific AC791N compatibility matrix was found in this search.
[reported: seller description] The ordered V4.1 product advertises JL's full
range without naming AC791N. Treat its exact hardware/firmware and switches as
unconfirmed until arrival; do not blindly transfer V4 switch numbering onto an
unseen board. No seller video was used as primary compatibility evidence.
The V4 continuous USB_KEY mode is relevant evidence supporting repeated entry
trials; it does not establish successful power-on recovery on this FM1.

Tomorrow's first action remains Pico-alone identification, then a verified
minimal circuit and self-test. If no suitable resistors are available, record
that parts dependency; do not introduce resistorless push-pull drive silently.
The desired endpoint is stock firmware restored and booting normally. UBOOT
entry is the immediate enabling milestone, not the final recovery verdict.

## Seller Bilibili link checked in Chrome — 2026-10-18

[verified: rendered Chrome profile] Opened the exact supplied URL
https://space.bilibili.com/15172053 after the web reader could not retrieve it.
The profile title identifies 爱米饭的小韩 and its visible uploads count is six.
All six listed uploads concern games; no JieLi downloader operation video was
listed. This is a current profile observation, not proof that no relevant video
ever existed. The seller link appears incorrect or outdated [inferred]. No
video was watched or used to infer switch settings or AC791N compatibility.
Use the linked official JieLi instructions as the operation reference pending
a correct seller video or inspection of the actual ordered adapter.
