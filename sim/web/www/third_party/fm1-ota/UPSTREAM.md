# Upstream attribution and local changes

This directory contains the GPL-3.0-only Web MIDI OTA implementation derived
from Felucca by Leo Kuroshita (@kurogedelic) and Hügelton Instruments.

- Repository: <https://github.com/hugelton/Felucca>
- Upstream path: `web/fm1ota.js`
- Pinned upstream commit: `1727537624390cc3f9c7dff2456b43b3a8edb005`
- Retrieved source SHA-256: `4d9fb9962ee0c2ac33e94ffd551eed577776e3705597e422b0eed8be21008c66`
- License: `LICENSE` (GPL-3.0-only)

`fm1ota.js` retains upstream authorship and adds strict frame/body/checksum
validation, bounded MIDI input handling, hard and idle transfer deadlines,
zero-length/range rejection, and send-result checks. Changes are marked in the
file. The browser adapter importing this module is also GPL-3.0-only. This
module is not wired to the installer, does not request Web MIDI access, and
does not itself establish package admission or device-install acceptance.
