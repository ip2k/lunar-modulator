# Offline expanded-profile loader core probe

This directory contains a narrowly modified loader core for host-only fake-NOR testing, adapted from Felucca prior art. It is GPL-3.0-only and is not linked into Lunar firmware or an installable package.

Upstream: [Felucca](https://github.com/hugelton/Felucca), pinned commit `1727537624390cc3f9c7dff2456b43b3a8edb005`, file `firmware/loader/ldr_core.c`.

Changes in this probe: app high bound changed from `0x93000` to the recorded FM-1_092 expanded profile's `0xD9000`; sector traversal keeps the directory sector at `0x4000` last; the success/record-invalidation and record-sector cleanup operations are omitted because ownership/recovery semantics for expanded VM/BTIF/USR and staging are unresolved; compile is rejected unless `LUNAR_EXPANDED_OFFLINE_TEST` is defined. Host test hooks inject NOR and OTA reads. This is not a target loader adaptation and must not be connected to a device.
