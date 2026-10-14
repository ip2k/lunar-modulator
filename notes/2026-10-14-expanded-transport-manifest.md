# Offline expanded transport manifest

The raw expanded candidate now has an offline manifest builder at
`tools/native/expanded_transport_manifest.py`. It consumes immutable full-flash
baseline/target bytes, the pinned recorded-layout reference, exact app and ELF
bytes, and the candidate, link, and prepared-selection receipts. It reparses
the target geometry and independently binds the candidate's target/baseline/
app/ELF digests and byte counts, the private link receipt, request/profile
hashes, ordered project IDs and startup choice. It then checks the receipt's
erase-sector map against actual changed bytes, excludes protected regions, and
places the directory sector after application-data sectors.

The output is explicitly `offline-expanded-transport-manifest` and
`installable: false`; hardware admission, physical writer readiness, recovery,
settings migration, and device I/O all remain false. This is a review artifact,
not FWSC packaging or a transport command stream. The current production
120-second diagnostic app is 862,272 bytes with SHA-256
`264a35311828d7269aca10f8f8c65e5429ead5df23162a9d781d1f36e5e4980d`;
the older 862,320-byte / 20-second app is a separate build and is not a size
conflict. The API accepts either only when all supplied receipts and bytes
correspond exactly; synthetic tests do not validate either production image.

Focused tests use generated ELF/app and raw-layout fixtures. They cover receipt
correspondence, multi-sector directory-last order, stale digests and sizes,
foreign/reordered sectors, writable-range mismatch, protected-area mutation,
profile mismatch, and admission attempts. Command:

```sh
/Users/likwid/Developer/mvave-fm1-firmware/.venv/bin/python -m pytest -q \
  tests/test_expanded_transport_manifest.py tests/test_expanded_native_candidate.py
```

Result: 40 passed. The current worktree's `.venv` lacks pytest, so the already
configured primary checkout's venv ran pytest while the current worktree stayed
the import/test root. Serena selected this worktree and its Python symbols were
available. Rarefaction remained selected on the primary checkout despite an
orient request for this worktree; no shared semantic-server redirection was
attempted.

The next integration step is to call this builder from a higher-level offline
candidate controller and retain its receipt beside the exact input hashes.
Before any transport is considered, separately decide how to deliver the
expanded transaction. The FM-1 mask-ROM interface is USB mass storage
(class 08/subclass 06/protocol 50); WebUSB protects class 08 interfaces, so a
normal browser page cannot claim it in Chromium. Investigate either a narrowly
reviewed native MIDI bootstrap installed through the stock updater followed by
an expanded transaction over WebMIDI, or an authenticated local companion.
Neither path is implemented here. Preserve the stock SPL/OTA/cfg and existing
protected-sector policy; physical install, settings migration, rollback, and
recovery validation remain owner-controlled gates.
