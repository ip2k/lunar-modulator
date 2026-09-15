# 11 — Local FM-1 Workbench

A lightweight browser bench interface for device identity, local firmware
inspection, and a timestamped packet log. It uses the existing Python/RtMidi
transport on Windows, macOS and Linux; there is no browser extension, Node build,
cloud service, or vendor updater dependency.

## Start

Create a virtual environment with Python 3.10 or later: `python -m venv .venv`.
Then, from the repository root:

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-workbench.txt
.\.venv\Scripts\python.exe tools/fm1_workbench.py --open
```

macOS / Linux:

```sh
.venv/bin/python -m pip install -r requirements-workbench.txt
.venv/bin/python tools/fm1_workbench.py --open
```

The address is `http://127.0.0.1:8765`. Choose `--port 8766` if that port is in
use, or `--port 0` to allocate one. Stop the process with Ctrl+C. Without the
optional MIDI packages, local package and application inspection still work.

## Device and debug log

1. Connect and power on the FM-1. Close other software holding its MIDI ports.
2. Refresh the ports and check the selected input and output. A unique normal
   FM-1 port is selected in each direction; multiple candidates require a choice.
   Windows may number input and output differently (`FM-1 Midi 0` / `FM-1 Midi 1`).
3. Select **Read identity**. This sends exactly one fixed identity query and
   closes both ports after a reply or timeout. It never starts automatically.
4. Inspect the decoded identity, checksum result, and TX/RX bytes. **Export
   report** opens a review of the session JSON. Copy it or request a JSON
   download. The selectable preview also works when a browser cannot save the
   download. Review the report before sharing.

[verified: source and automated tests] The transport sends only
`F0 00 32 45 00 00 00 40 7F F7`. It rejects changed, ambiguous, OTA and BLE
endpoints; malformed, corrupt or unexpected replies end the request. The log
preserves the received bytes on those failures. A successful identity query
establishes an identity response, not flash readback, audio function, or recovery.

The debug window is scoped to these requests and local analysis actions. It is
not a system-wide MIDI monitor. No arbitrary SysEx console is provided.

## Inspect firmware locally

Choose an original `.fwsc` package, or select application mode for an already
unpacked `app.bin`. The filename is only a label: firmware identity is read from
the bytes. The report includes size, SHA-256, integrity checks, package entries,
and application/MSFA findings where the format is supported. See
[12 — Package inspection](12-package-inspection.md) for exact coverage.

Files are limited to 8 MiB and processed in memory by the loopback Python
process. The server does not save or redistribute firmware. Session exports
contain metadata and identity packets, not package payloads. Exported metadata
can include filenames and MIDI port names; inspect it before publication.

## Scope and extension points

This is the first bench component of a possible open updater. Firmware loading
remains future work, subject to [the recovery rules](07-recovery-and-risk.md).
There is no upgrade command, flash endpoint, hidden write switch, or executable
upload path in this service. A package passing checks is not authorization to
flash it and does not establish its compatibility with a device.

| Component | Responsibility |
| --- | --- |
| `tools/fm1_identify.py` | Shared strict identity decoder and existing CLI |
| `tools/fm1_package.py` | Offline binary inspection and report generation |
| `tools/fm1_workbench.py` | Exact port selection, fixed query, loopback HTTP API |
| `web/` | Static HTML, CSS and JavaScript; no device command construction |

Before adding a writer, demonstrate unit-specific dump/restore, implement a
separate reviewed state machine and one-time confirmation for the exact target
and package, reproduce the partial-block framing fixture, exercise disconnect
and power-loss behavior on a recoverable unit, and require post-reboot identity
and USB checks. A loader terminal acknowledgement alone is insufficient.

The local HTTP service binds only to `127.0.0.1`, restricts Host and Origin,
requires same-origin POST requests, limits upload size, and serves an explicit
static-file allowlist. It is a local bench tool; do not expose it through a
network proxy. These checks prevent another website from issuing bench requests
through a browser. They do not isolate it from other programs running locally.

## Credits and validation

This contribution uses Echomatter's package-analysis and MIDI framing lessons,
the existing ip2k identity tool and hardware fixture, and the prior work credited
in [04 — Prior art](04-prior-art.md). It introduces no historical modified-package
exceptions. Vendor binaries and machine-specific recovery tooling are not included.

Run `python -m pytest` after installing `requirements-dev.txt`. The tests cover
corrupt identity replies, endpoint selection, exact outbound bytes, timeouts,
port cleanup, HTTP boundaries, and synthetic package corruption. Live bench and
browser checks are recorded separately in `notes/`.
