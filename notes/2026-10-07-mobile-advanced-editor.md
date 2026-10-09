# Mobile Advanced editor and a real FM-1

Owner request, 2026-10-07: use the Advanced editor on an iPhone to edit the
actual running FM-1, ideally over BLE wireless MIDI. **Deferred until we
have installable firmware** (owner, same date). This is a saved design and
resume plan, not an implemented feature or a claim of device compatibility.

## Where we are

[verified: repository source] The Advanced editor currently edits the virtual
FM-1 through the shared C edit layer and browser worklet. See
`sim/web/src/fm1_edit.c`, `sim/web/www/app.js`, `sim/web/www/worklet.js`, and
`notes/2026-10-06-web-editor.md`. Browser MIDI input exists in `app.js`, but
that does not expose the full editor protocol on a real device. Responsive
CSS and pointer handlers already exist; a narrow viewport test does not
prove real iPhone touch usability.

[verified: MDN compatibility data checked 2026-10-07] Safari/iOS and iOS
WebView are listed without Web MIDI and Web Bluetooth support. Installing
a PWA alone does not provide these missing native APIs. Recheck this at
resumption; support can change. Sources:
[Web MIDI](https://developer.mozilla.org/en-US/docs/Web/API/Web_MIDI_API),
[Web Bluetooth](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API),
and [MDN Navigator compatibility data](https://github.com/mdn/browser-compat-data/blob/main/api/Navigator.json).

[reported: Apple documentation] Core MIDI supports Bluetooth LE MIDI;
CoreAudioKit’s `CABTMIDICentralViewController` supplies a peripheral discovery
and connection UI. This does not establish that our FM-1 firmware exposes
a compatible BLE MIDI peripheral. Sources:
[Apple QA1831](https://developer.apple.com/library/archive/qa/qa1831/_index.html),
[connection controller](https://developer.apple.com/documentation/coreaudiokit/cabtmidicentralviewcontroller).

## Shortest paths to evaluate

[inferred: proposed architecture] For a standalone iPhone editor, reuse the
existing HTML/JavaScript UI inside a small WKWebView app. Add a narrow native
Core MIDI bridge for USB MIDI and BLE MIDI, rather than rebuilding the
editor in Swift. The bridge should carry the same transport messages as
the desktop connection; keep editor logic independent of transport. Test
on an actual iPhone before committing to this route.

[inferred: earlier demonstration] Safari on the phone could connect over a
LAN WebSocket to a Mac/Pi relay attached to the FM-1’s USB MIDI port. This
avoids an initial iOS app and device BLE implementation, but requires the
relay and network. It is a prototype option, not a selected product design.

[inferred: hardware/licensing option] If a SDK-free firmware cannot provide
BLE cheaply, first make USB MIDI editing work. Evaluate an external
USB-host-to-BLE-MIDI bridge; confirm bidirectional SysEx support, power and
packet limits before choosing hardware. A conventional DIN/TRS adapter may
not work: the FM-1 MIDI jack is input-only [reported: docs/01-hardware.md].
Built-in BLE remains a separate decision because the JieLi Bluetooth stack
may reintroduce closed-library dependencies; see
`2026-10-07-sdk-runtime-evaluation.md` in the separate SDK evaluation branch.

## Firmware prerequisite and resume checklist

[inferred: proposed contract] Stock/VA MIDI controls are a subset; do not
assume they can represent Lunar’s engines, chains, modulation and project
state. Reuse the shared edit layer behind a versioned, bidirectional device
protocol. It needs device identity/capabilities and metadata compatibility,
initial state snapshot, acknowledged edits with refusal reasons, change
notifications for physical controls, reconnect/resynchronization and bounded
chunking for large transfers. MIDI CC can provide an early parameter demo;
full editing needs the richer contract, likely framed/chunked SysEx. Validate
BLE SysEx fragmentation and throughput rather than assuming USB behavior.

After installable firmware works:

1. Prove one parameter edit and its readback over USB MIDI on the real FM-1;
   confirm the panel and editor agree while audio runs.
2. Define the versioned transport around existing edit records; add rate
   limiting/coalescing, acknowledgments and reconnect state recovery.
3. Audit real iPhone portrait/landscape use: touch targets, sliders, cable
   creation/reconnection, scrolling versus dragging, sheets, keyboard, safe
   areas, and alternatives to hover and keyboard-only actions.
4. Choose native iOS bridge or LAN relay for the first mobile demonstration,
   then evaluate direct BLE independently.
5. Test hardware knob edits arriving at the phone, lost connections,
   interrupted project transfer, rapid edits during playback and app resume.

Keep this work deferred while firmware installation/recovery is the priority.
No iOS app, relay, BLE stack or hardware editor protocol was implemented by
this note.
