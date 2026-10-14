# Recovery readiness for unattended Event Horizon testing

Date: 2026-10-14. Offline source and handoff review only. I performed no FM-1, Pico, USB, MIDI, flash, power, or reset operation.

## Current state and observed recovery

[reported: coordinator hardware handoff] The latest repeat began from ROM device46, issued one FC0C request, observed native USB device47, and later observed ROM device48 without a physical power cycle or intervening device command. The SG completion was ambiguous and not retried. See `notes/2026-10-14-event120-repeat46-hardware.md`. The installed/read-back image for that repeat was the Event Horizon 120-second song-diagnostic target, full-flash SHA-256 `145c0280d652b73515e01e2f1f0d88fe33344645463e89d57a2d0048c6aa4657`. This is timed-image recovery evidence; owner listening/control acceptance remains pending. The earlier device44 repeat and ROM46 observation are historical, not the latest enumeration.

[verified: source] `firmware/native/runtime_mode.h` defaults diagnostic builds to 20 seconds and supports 120 seconds; continuous mode is 0 seconds. In `firmware/native/app_probe.c`, the live main loop handles expiration by stopping audio, detaching USB, delaying, clearing the boot guard and entering ROM. This is a tested path for a responsive application, not a watchdog recovery guarantee.

[verified: source] The fixed SysEx soft key `F0 22 24 35 7D F7` sets `usb.uboot_req` in `firmware/third_party/dinghy/src/usb.c`. `platform_poll()` consumes it by stopping audio, detaching USB, delaying, clearing the boot guard and entering ROM. The main event loop must still be alive and processing USB/MIDI; this cannot recover a hung or non-booting image.

[inferred: source behavior, not hardware-tested] For an unattended continuous-app test, an operator could schedule the fixed soft-key request as a responsive-app stop path, with the host ready to observe ROM. It would establish only that the running image can voluntarily return to ROM. It does not establish recovery from a hang, watchdog reset, or failed boot.

## Continuous candidate and recovery limits

[verified: current target note/build receipt; not installed] The current continuous D7000 Event Horizon candidate is a separate offline artifact: app SHA-256 `d7216f6c62c42266c1886e4b57f6ed33de8afcffec7be226e724fbadfe137d3b`, 845,768 bytes, under the 860,644-byte D7000 app budget. It has a zero-second timed return and is not covered by the device46-to-48 timed-image observation. See the current continuous target note at commit `6f4b1e804b7c70136b4deefa69de3591ed3e20b6`. The earlier continuous artifact SHA `5c923197629121ce90a33919b516ced23ef8edbaa1943ea1e9568b596b6557ee` is historical and must not be treated as the current build.

[verified: source; target behavior not established] The app startup boot guard and watchdog code in `firmware/native/recovery.c` and `bootguard.h` are app-level mechanisms. Startup arms an approximately eight-second watchdog, while the normal loop feeds it. No exact continuous-target test demonstrates that a hung app reliably returns to ROM. A watchdog reset during NOR busy/program activity is specifically unresolved; SAVE remains disarmed. Do not treat watchdog behavior as the recovery route for unattended destructive tests.

[reported: coordinator-reported captures; wiring confirmation pending] The Pico2W dongle remains in `FAULT` because its GP14/GP15 line-state self-test fails before `key_phase`; no USB_KEY exchange is attempted. GP14 is D+, GP15 D−, and separate pins control the external pullups. Repeated captures report the same fault. A passing electrical self-test would still need an actual key exchange and observed ROM enumeration before the dongle counts as app-independent recovery.

## Smallest next steps

1. [inferred: safe test sequencing] The 120-second diagnostic target has already shown a timed return to ROM without a physical power cycle. For a repeat, start host capture before its single authorized boot and wait for ROM; that still does not test continuous playback.
2. [inferred: conditional on separate image admission] To test the current continuous candidate without a planned power cycle, first obtain separate fresh paired-read/boot admission for that exact image. Then use a reviewed one-shot host soft-key request while the app is responsive and verify ROM enumeration. This tests voluntary app return only; it is not recovery from a hang.
3. [verified: current outstanding hardware evidence] Resolve the Pico wiring/self-test cause, then require a real USB_KEY exchange and ROM observation before counting the Pico as recovery for a hung app.
4. [verified: current gate] Keep SAVE disarmed and do not use watchdog reset as recovery during NOR activity until the RAM/XIP-off and WDT behavior is proven.

The next continuous-image acceptance result is a watched, exact-image soft-key-to-ROM observation after separate fresh image admission. App-independent hung-app recovery additionally requires a working Pico USB_KEY-to-ROM observation. Neither result is established here. No unattended hang recovery is currently proven.

## Evidence limits

[verified] This note is an offline review of repository source, current target notes and coordinator-provided hardware handoff. It did not re-run the hardware sequence or inspect live device state. Device47-to-ROM48 belongs to the installed 120-second diagnostic image. The current continuous candidate is a build artifact only; it has no installation or boot evidence. App soft-key recovery requires a live event loop; the Pico path is currently blocked before key exchange; watchdog/NOR recovery remains unproven.

