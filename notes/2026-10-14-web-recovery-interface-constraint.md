# Browser recovery transport constraint — 2026-10-14

[verified] Passive sysfs inspection on `claude@bench01.local` reports the
current FM1 recovery interface at `/sys/bus/usb/devices/1-1:1.0` as class `08`,
subclass `06`, protocol `50`. This reads kernel metadata only; no USB handle,
loader command, flash or boot operation was issued. The connection was earlier
observed as `4c4a:8057`, bus 1, device 36. These observations do not grant a fresh
physical campaign or establish loader liveness.

[verified] The [WebUSB specification](https://wicg.github.io/webusb/#has-a-protected-interface-class)
lists mass-storage class `0x08` as protected. The current
[Chromium implementation](https://chromium.googlesource.com/chromium/src/+/HEAD/content/browser/usb/web_usb_service_impl.cc)
(`GetProtectedInterfaceClasses`, viewed blob
`3c34492e7274ddc3d628639b3f46acae0c6600d1`) includes mass storage. Its special
unrestricted permission requires an isolated context; it is not the ordinary
public website route required for Lunar. An ordinary WebUSB site therefore
cannot claim this observed recovery interface.

[inferred] Porting the Linux SCSI Generic writer to browser bulk transfers alone
cannot satisfy the web installer requirement. Do not advertise direct browser
mask-ROM recovery or use disabled browser protections as the release flow.
The offline expanded manifest and native recovery transaction remain useful,
but they do not establish a web-capable transport.

Next candidate to evaluate: a small, SDK-free, GPL native updater fitting the
stock app slot, installed with the existing stock WebMIDI/OTA route, then an
exact receipt-bound expanded-image transaction over MIDI. It must preserve
stock SPL/OTA/config, keep recovery independent of the app, bind fresh matching
backups, protect reserved ranges, write the directory last, support interrupted
write recovery and complete readback. This is a design candidate, not an
implemented or admitted updater. A native companion is another possible route,
but would add installation requirements and does not by itself establish the
requested web-installable release.

Full-song device-test preparation also requires pressing PLAY after project
startup: `lunar_project_start` restores the sequence, units and view, while the
existing PLAY input starts the sequencer. The host full-song evidence explicitly
issued that action. The two-minute diagnostic does not auto-play merely because
the project is embedded. Record this in the watched-test instructions and allow
the complete 108.8-second arrangement to finish before the recovery deadline.
