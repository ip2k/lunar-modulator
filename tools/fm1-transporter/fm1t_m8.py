#!/usr/bin/env python3
"""fm1t_m8 - the M8 flash-install host tool for the FM-1 Transporter data port.

Adapted from fm1t_m6.py (itself from kurogedelic's FM-1-transporter
`tools/fm1t.py` at a7fb5e8; MIT, Copyright (c) 2026 kurogedelic; licence in
LICENSE.upstream next to this file). It keeps M6's read paths and gates and
replaces the RAM run with two flash writes, both inside [0x4000, 0x93000):

    fm1t_m8.py preflight [--package P.fwsc --sha256 HEX] [--v15 FM-1.fwsc] [--loader L]
    fm1t_m8.py --port P --log L status
    fm1t_m8.py --port P --log L rekey --fm1-is-off
    fm1t_m8.py --port P --log L info --loader wl82loader.bin
    fm1t_m8.py --port P --log L dump OUT.bin --loader wl82loader.bin [--compare REF.bin]
    fm1t_m8.py --port P --log L install P.fwsc --sha256 HEX --identity FM-1_015 \\
               --loader wl82loader.bin [--write --tool-sha256 HEX]
    fm1t_m8.py --port P --log L restore --v15 FM-1.fwsc \\
               --loader wl82loader.bin [--write --tool-sha256 HEX]
    fm1t_m8.py compare A.bin B.bin

docs/22 is the runbook. No Lunar image is approved yet (docs/18 row M8):
APPROVED_PACKAGE_SHA256 is None, and `install` refuses until a code change
pins the hash the owner approves. There is no command-line override.

What `install` and `restore` do, in one session each:

1. `status` must say uboot=1 and v15=0 (D2: nothing is sent to a running
   V15). The ROM is entered by USB_KEY only (docs/17 section 4).
2. The loader (JieLi's wl82loader.bin, pinned) goes up. `install --write`
   always uploads it itself and refuses a transporter that already holds one
   (so it runs first in a fresh ROM entry); the dry run and `restore` use a
   held loader and record that, so `restore` can follow a failed install
   without a power cycle. Then `info` must be exactly `OK key=980F type=3
   id=856014` (the owner's chip key and Puya P25Q80H flash).
3. Two full 1 MiB reads, saved next to the receipt, must be byte-identical.
4. Preconditions on that before-image:
   - its head [0, 0x4000) must be V15's (SHA-256 d9f43191...); the head is
     never written, and the target's head must equal it too;
   - `install`: [0, 0x93000) must be a known region (KNOWN_REGIONS: stock
     V15 today), and --identity, read with tools/fm1_identify.py before the
     unit was keyed, must be that region's identity. The known region fixes
     the layout and so the write range: V15's app ends where its VM begins,
     0x93000 (notes/2026-11-08-0x94600-forensics.md);
   - `restore`: the app region may hold anything (an interrupted install
     leaves a mix); the target is stock V15's own region, pinned by hash.
5. Only sectors whose bytes differ from the target are written, each once,
   inside [0x4000, write end) where write end is at most 0x93000. Each `wsec`
   is erased, programmed and verified by the transporter; the tool then reads
   that sector back and compares all 4,096 bytes.
6. A final full read, saved, must equal the target over [0, 0x93000) and the
   before-image over [0x93000, 1 MiB): nothing outside the write changed.

Without --write both stop after step 5's plan: nothing is erased or written.
--write also needs --tool-sha256 equal to this file's own SHA-256, the hash
the owner approved. `install --write` takes a one-attempt lock per approved
package hash, in LOCK_DIR (not under --log), just before the first `wsec`;
a second install of the same image, from any directory, is refused.
`restore` takes no lock: it is the recovery path and may be rerun, each time
from two fresh in-session reads.

Stricter than upstream fm1t.py: no `uboot`, `k`, `memw`, `jump`, `runapp`,
`selftest-write` or `ramrun`; the port must be the pinned transporter's data
port (serial 560A5ACCF298BDCB, interface 02); every line sent is checked
against an allow-list by Link, the only code that writes to the port; a
`wsec` payload must be the target's own bytes for a sector in the planned
list; and every line and payload goes to a JSONL receipt (--log, a new file).
Each `wsec` goes out through Link.send_wsec, which checks the payload before
the header, so a refusal never leaves the transporter waiting for 4,096
bytes. `install` refuses root and sudo, because its lock is under $HOME. Once
any `wsec` went out, every stop, including Ctrl-C, says to run `restore`.
Single file, standard library only (pyserial is imported only to open the
port), so this file's hash covers all of its logic.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
import zlib

# -- What the owner approves (docs/18 row M8, docs/22 section 1). None until
#    an image is approved; changing any of these needs a new approval.
APPROVED_PACKAGE_SHA256 = None
APPROVED_PACKAGE_BYTES = None
APPROVED_BUILD_ID = None

# The transporter on the bench (docs/17), by its USB serial number.
TRANSPORTER_SERIAL = "560A5ACCF298BDCB"
PORT_NAME = "FM-1_Transporter"
PORT_SUFFIX = "-if02"            # the data port; interface 0 is the console
BAUD = 115200

# JieLi's WL82 USB loader from kagaimiq's jl-uboot-tool (docs/17 section 1).
LOADER_SHA256 = "d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376"
LOADER_BYTES = 24064
LOADER_CHUNK = 4096

# The owner's chip key and flash JEDEC id (0x856014, Puya P25Q80H).
EXPECTED_INFO = "OK key=980F type=3 id=856014"

FLASH_SIZE = 0x100000
SECTOR = 0x1000
HEAD_END = 0x4000                # SPL, isd_config, top directory: never written
WRITE_MIN = 0x4000               # the transporter's JL_WRITE_MIN
WRITE_END = 0x93000              # the transporter's JL_WRITE_END; V15's VM starts here
REGION_BYTES = 0x93000           # [0, 0x93000): a package's flash.bin entry

# Stock V15 (FM-1_015), docs/02 and tools/jieli/build_fwsc.py V15_PROFILE.
V15_PACKAGE_SHA256 = "db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a"
V15_PACKAGE_BYTES = 699956
V15_REGION_SHA256 = "c1068a403c04a6378a626afb66cc217f72d13f10aa200e983b7a9817cc1dac03"
HEAD_SHA256 = "d9f43191777656de01c7bed4f9e9ba2e34e94832c5d2ed02c3fc7ab7a6d9bd67"

# The flash.bin entry sits at logical offset 0x400 of a V15-geometry package;
# the physical file keeps one extra byte per 48 for the first 20 records, so
# it starts at file offset 0x414 (docs/17 research shim; equal for V15
# [verified 2026-11-14 against the CDN package]). build_fwsc.py keeps this
# geometry for Lunar packages.
REGION_FILE_OFFSET = 0x414

# Regions [0, 0x93000) the tool accepts as a known starting point for an
# install: hash -> (name, the identity the unit reports, the app's end).
KNOWN_REGIONS = {
    V15_REGION_SHA256: ("stock V15", "FM-1_015", 0x93000),
}

# One install attempt per approved package hash, wherever --log points.
LOCK_DIR = Path.home() / ".local" / "state" / "fm1t_m8"

TIMEOUT_STATUS = 5
TIMEOUT_LDR = 5
TIMEOUT_INFO = 30
TIMEOUT_READ_HEADER = 30
TIMEOUT_READ_BYTES = 10
TIMEOUT_WSEC = 20

USB_KEY_STEPS = ("ROM entry is by USB_KEY only (docs/22 and docs/17 section 4): switch the "
                 "FM-1 OFF, run `fm1t_m8.py ... rekey --fm1-is-off`, reopen the console, wait "
                 "for the key to run, switch the FM-1 ON, wait for `UBOOT READY`, then rerun.")

# -- The allow-list. Each pattern must match the whole line. Addresses are
#    0x-hex only and lengths plain decimal: the transporter parses both with
#    strtoul(..., 0), which reads a leading 0 as octal.
_HEX8 = r"[0-9A-F]{8}"
_LEN = r"[1-9][0-9]{0,3}"
_ADDR = r"0x[1-9a-f][0-9a-f]{3,4}"
_LDR_OFFSETS = "|".join(str(o) for o in range(0, LOADER_BYTES, LOADER_CHUNK))
PATTERNS = {
    "ping": r"ping",
    "status": r"status",
    "rekey": r"rekey",
    "ldr": rf"ldr ({_LDR_OFFSETS}) ({_LEN}) ({_HEX8})",
    "info": r"info",
    "read": rf"read 0x0 {FLASH_SIZE}",
    "readsec": rf"read ({_ADDR}) {SECTOR}",
    "wsec": rf"wsec ({_ADDR}) ({_HEX8})",
}
_WRITE_MODE = ("ping", "status", "ldr", "info", "read", "readsec", "wsec")
ALLOWED = {
    "status": ("ping", "status"),
    "rekey": ("ping", "status", "rekey"),
    "info": ("ping", "status", "ldr", "info"),
    "dump": ("ping", "status", "ldr", "info", "read"),
    "install": _WRITE_MODE,
    "restore": _WRITE_MODE,
}
FORBIDDEN_WORDS = {
    "uboot": "sends the soft key F0 22 24 35 7D F7 to a mounted V15 (CLAUDE.md trap 9, D2)",
    "k": "console soft key (D2)",
    "runapp": "leaves UBOOT through the loader (docs/17 section 8)",
    "memw": "writes SRAM; M8 writes flash only",
    "jump": "runs code; M8 writes flash only",
}
_COMPILED = {name: re.compile(p) for name, p in PATTERNS.items()}


class Refused(Exception):
    """Raised before anything is sent: admission, arguments, the gate."""


class Stop(Exception):
    """Raised after the session started: an unexpected reply or state. Stop;
    do not power-cycle mid-write; follow docs/22's recovery steps."""


# -- Admission (offline) -----------------------------------------------------

def sha256(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256(Path(path).read_bytes())


def region_of_package(raw):
    """The package's flash.bin entry: [0, 0x93000) as it lies in flash."""
    region = raw[REGION_FILE_OFFSET:REGION_FILE_OFFSET + REGION_BYTES]
    if len(region) != REGION_BYTES:
        raise Refused(f"package too short for a {REGION_BYTES:#x}-byte flash entry at "
                      f"{REGION_FILE_OFFSET:#x}")
    return region


def check_target(region, what):
    """Every target: exactly [0, 0x93000), whole sectors, V15's head."""
    if len(region) != REGION_BYTES or len(region) % SECTOR:
        raise Refused(f"{what}: {len(region):#x} B, not exactly {REGION_BYTES:#x}")
    if sha256(region[:HEAD_END]) != HEAD_SHA256:
        raise Refused(f"{what}: head [0, {HEAD_END:#x}) is not V15's ({HEAD_SHA256[:12]}...); "
                      "the head is never written")


def admit_install(path, digest):
    """The Lunar package: exactly the approved one. Returns its region."""
    if APPROVED_PACKAGE_SHA256 is None:
        raise Refused("no install image is approved yet (APPROVED_PACKAGE_SHA256 is None); "
                      "the owner approves a package hash first (docs/22 section 1), then "
                      "the hash is pinned in this file")
    if not digest:
        raise Refused("--sha256 is required")
    raw = Path(path).read_bytes()
    got = sha256(raw)
    if digest.lower() != got:
        raise Refused(f"{path}: SHA-256 is {got}, not the --sha256 given ({digest})")
    if got != APPROVED_PACKAGE_SHA256 or len(raw) != APPROVED_PACKAGE_BYTES:
        raise Refused(f"{path}: {got} ({len(raw)} B) is not the approved package "
                      f"{APPROVED_PACKAGE_SHA256} ({APPROVED_PACKAGE_BYTES} B, build id "
                      f"{APPROVED_BUILD_ID}); another image needs a code change and a new "
                      "owner approval")
    region = region_of_package(raw)
    check_target(region, path)
    if sha256(region) in KNOWN_REGIONS:
        raise Refused(f"{path}: its flash region is {KNOWN_REGIONS[sha256(region)][0]}; "
                      "use `restore` for that")
    return region


def admit_v15(path):
    """Stock V15's package, pinned; returns its region, pinned too."""
    if not path:
        raise Refused("--v15 FM-1.fwsc (stock V15, docs/02) is required")
    raw = Path(path).read_bytes()
    got = sha256(raw)
    if got != V15_PACKAGE_SHA256 or len(raw) != V15_PACKAGE_BYTES:
        raise Refused(f"{path}: {got} ({len(raw)} B) is not stock V15 "
                      f"{V15_PACKAGE_SHA256} ({V15_PACKAGE_BYTES} B)")
    region = region_of_package(raw)
    if sha256(region) != V15_REGION_SHA256:
        raise Refused(f"{path}: flash region {sha256(region)} is not V15's {V15_REGION_SHA256}")
    check_target(region, path)
    return region


def admit_loader(path):
    if not path:
        raise Refused("--loader wl82loader.bin is required")
    data = Path(path).read_bytes()
    got = sha256(data)
    if len(data) != LOADER_BYTES or got != LOADER_SHA256:
        raise Refused(f"{path}: {len(data)} B, SHA-256 {got}; expected JieLi's "
                      f"wl82loader.bin, {LOADER_BYTES} B, {LOADER_SHA256}")
    return data


def expected_port_name():
    return f"usb-kurogedelic_{PORT_NAME}_{TRANSPORTER_SERIAL}{PORT_SUFFIX}"


def check_port_path(port):
    if not port:
        raise Refused("--port is required (the transporter's /dev/serial/by-id/...-if02); "
                      "this tool does not probe for ports")
    if port != f"/dev/serial/by-id/{expected_port_name()}":
        raise Refused(f"{port}: not the pinned transporter's data port; pass "
                      f"/dev/serial/by-id/{expected_port_name()} (never the console, -if00)")


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def sector_diff(a, b, lo, hi):
    return [s for s in range(lo, hi, SECTOR) if a[s:s + SECTOR] != b[s:s + SECTOR]]


def plan_write(before, target, write_end):
    """The sectors to write, all inside [WRITE_MIN, write_end) and never past
    WRITE_END; refuse when the target differs from the flash anywhere else."""
    if write_end > WRITE_END or write_end % SECTOR:
        raise Refused(f"write end {write_end:#x} is past {WRITE_END:#x} or not a sector boundary")
    outside = (sector_diff(before, target, 0, WRITE_MIN)
               + sector_diff(before, target, write_end, len(target)))
    if outside:
        raise Refused("the target differs from the flash outside [" f"{WRITE_MIN:#x}, "
                      f"{write_end:#x}): sectors " + " ".join(f"{s:#07x}" for s in outside))
    return sector_diff(before, target, WRITE_MIN, write_end)


# -- The gate ----------------------------------------------------------------

def check_line(mode, line, write_end=WRITE_END):
    """Return the pattern name `line` matches in `mode`'s allow-list, or raise."""
    if mode not in ALLOWED:
        raise Refused(f"unknown mode {mode!r}")
    if not isinstance(line, str) or not re.fullmatch(r"[ -~]{1,62}", line):
        raise Refused(f"refused: {line!r} is not one printable line under 63 characters")
    word = line.split(" ", 1)[0]
    if word in FORBIDDEN_WORDS:
        raise Refused(f"refused: {word!r} {FORBIDDEN_WORDS[word]}")
    for name in ALLOWED[mode]:
        m = _COMPILED[name].fullmatch(line)
        if not m:
            continue
        if name in ("wsec", "readsec"):
            addr = int(m.group(1), 16)
            end = min(write_end, WRITE_END)
            if addr % SECTOR or not WRITE_MIN <= addr < end:
                raise Refused(f"refused: {line!r} leaves the write range "
                              f"[{WRITE_MIN:#x}, {end:#x}) or is not sector-aligned")
        if name == "ldr":
            off, length = int(m.group(1)), int(m.group(2))
            if not 1 <= length <= LOADER_CHUNK or off + length > LOADER_BYTES:
                raise Refused(f"refused: {line!r} outside the loader's {LOADER_BYTES} B")
        return name
    raise Refused(f"refused in {mode}: {line!r} is not on the allow-list")


class Link:
    """The only code that writes to the port. Every line is checked against the
    subcommand's allow-list, logged, then written; replies are logged. In the
    write modes `wsec` is refused until arm() hands over the target and the
    planned sectors; each planned sector may be sent once, with the target's
    own 4,096 bytes as its payload."""

    def __init__(self, port, mode, log):
        self._port = port
        self.mode = mode
        self._log = log
        self._payload = None        # (name, addr, len, crc32) a header announced
        self.sealed = None
        self._target = None
        self._planned = frozenset()
        self._write_end = WRITE_MIN
        self._wsec_ready = None     # set only inside send_wsec
        self.written = []           # sectors whose wsec went out, in order

    def arm(self, target, write_end, planned):
        if self.mode not in ("install", "restore"):
            raise Refused(f"refused: {self.mode} never writes flash")
        if self._target is not None:
            raise Refused("refused: the link is armed once per session")
        check_target(target, "target")
        if write_end > WRITE_END:
            raise Refused(f"refused: write end {write_end:#x} past {WRITE_END:#x}")
        for s in planned:
            if s % SECTOR or not WRITE_MIN <= s < write_end:
                raise Refused(f"refused: planned sector {s:#x} outside "
                              f"[{WRITE_MIN:#x}, {write_end:#x})")
        self._target = bytes(target)
        self._write_end = write_end
        self._planned = frozenset(planned)

    def _write(self, data):
        self._port.write(data)
        flush = getattr(self._port, "flush", None)
        if flush:
            flush()

    def drain_at_open(self):
        waiting = getattr(self._port, "in_waiting", 0)
        if waiting:
            stale = self._port.read(waiting)
            self._log("rx-discarded-at-open", data=stale.decode("latin-1"))

    def _check_quiet(self):
        waiting = getattr(self._port, "in_waiting", 0)
        if waiting:
            stale = self._port.read(waiting)
            self._log("rx-unexpected", data=stale.decode("latin-1"))
            raise Stop(f"unexpected bytes from the transporter before a request: {stale!r}")

    def send_line(self, line):
        if self.sealed:
            raise Refused(f"refused: nothing is sent after {self.sealed} ({line!r})")
        if self._payload:
            raise Refused(f"refused: {line!r} while a payload is due")
        write_end = self._write_end if self.mode in ("install", "restore") else WRITE_END
        name = check_line(self.mode, line, write_end)
        if name == "wsec":
            addr = int(line.split()[1], 16)
            if self._target is None:
                raise Refused("refused: wsec before the write was planned and armed")
            if addr not in self._planned:
                raise Refused(f"refused: wsec {addr:#x} is not a planned sector")
            if addr in self.written:
                raise Refused(f"refused: wsec {addr:#x} again; a sector is never resent")
            if self._wsec_ready != addr:
                raise Refused("refused: wsec goes out only through send_wsec, which checks "
                              "the payload before the header")
        self._check_quiet()
        if name in ("wsec", "ldr"):
            parts = line.split()
            if name == "wsec":
                self._payload = (name, int(parts[1], 16), SECTOR, int(parts[2], 16))
                self.written.append(int(parts[1], 16))
            else:
                self._payload = (name, int(parts[1]), int(parts[2]), int(parts[3], 16))
        self._log("tx", line=line)
        self._write(line.encode("ascii") + b"\n")
        if name == "rekey":
            self.sealed = "rekey (the transporter reboots)"
        return name

    def send_wsec(self, addr, data):
        """One sector: the payload is checked against the target before the header
        goes out, so a refusal never leaves core 0 waiting for 4,096 bytes."""
        if self._target is None:
            raise Refused("refused: wsec before the write was planned and armed")
        if data != self._target[addr:addr + SECTOR]:
            raise Refused(f"refused: wsec {addr:#x} payload is not the target's bytes there")
        self._wsec_ready = addr
        try:
            self.send_line(f"wsec {addr:#x} {crc32(data):08X}")
        finally:
            self._wsec_ready = None
        self.send_payload(data)

    def send_payload(self, data):
        if not self._payload:
            raise Refused("refused: payload bytes without a wsec/ldr header")
        name, addr, length, crc = self._payload
        if len(data) != length or crc32(data) != crc:
            # The header is already on the wire and core 0 counts payload bytes,
            # so nothing more may be sent this session.
            self.sealed = "a payload that did not match its header"
            raise Refused(f"refused: payload {len(data)} B crc {crc32(data):08X} does not "
                          f"match its header ({length} B, {crc:08X})")
        if name == "wsec" and data != self._target[addr:addr + SECTOR]:
            self.sealed = "a wsec payload that was not the target's"
            raise Refused(f"refused: wsec {addr:#x} payload is not the target's bytes there")
        self._payload = None
        self._log("tx-bytes", len=len(data), crc32=f"{crc32(data):08X}", sha256=sha256(data))
        self._write(data)

    def recv_line(self, timeout):
        self._port.timeout = timeout
        raw = self._port.readline()
        line = raw.decode("latin-1").rstrip("\r\n")
        self._log("rx", line=line, timeout=raw[-1:] != b"\n")
        return line

    def recv_bytes(self, n, timeout):
        self._port.timeout = timeout
        out = bytearray()
        while len(out) < n:
            chunk = self._port.read(min(65536, n - len(out)))
            if not chunk:
                break
            out += chunk
        self._log("rx-bytes", len=len(out), expected=n, crc32=f"{crc32(out):08X}",
                  sha256=sha256(out))
        return bytes(out)

    def request(self, line, timeout):
        self.send_line(line)
        return self.recv_line(timeout)


# -- Port --------------------------------------------------------------------

def open_port(port):
    """Open the data port at 115200 (pyserial imported only here)."""
    import serial  # noqa: PLC0415  (pyserial; never needed offline)
    return serial.Serial(port, BAUD, timeout=1, exclusive=True)


def handshake(link):
    link.drain_at_open()
    reply = link.request("ping", TIMEOUT_STATUS)
    if reply != "PONG":
        raise Stop(f"no PONG from the data port (got {reply!r}). Either this is not the "
                   "transporter's -if02, or an earlier session stopped in the middle of a "
                   "4,096-byte payload and the transporter is still counting bytes (it has no "
                   "timeout). Then replug the Pico only, not the FM-1 [inferred: the FM-1 runs on "
                   "its battery and has no VBUS from the Pico, so it stays on], and check "
                   "`status` before anything else (docs/22 section 5)")


_STATUS = re.compile(r"OK uboot=([01]) v15=([01]) loader=([01]) loader_running=([01])")


def read_status(link):
    reply = link.request("status", TIMEOUT_STATUS)
    if not reply:
        raise Stop("no reply to `status`: the transporter's core 1 is busy, most likely "
                   "running the USB_KEY. With the FM-1 off and the key running, switch the "
                   "FM-1 on and wait for `UBOOT READY`; do not rekey. If instead a `wsec` "
                   "timed out in the previous session, core 1 may still be busy: leave the "
                   "FM-1 on, wait 30 s and run `status` again (docs/22 section 5)")
    m = _STATUS.fullmatch(reply)
    if not m:
        raise Stop(f"unexpected status reply {reply!r}")
    return dict(zip(("uboot", "v15", "loader", "loader_running"), (int(x) for x in m.groups())))


def require_uboot(st):
    if st["v15"]:
        raise Stop(f"a running V15 is attached to the transporter ({st}); nothing is sent to "
                   "it (D2). Switch the FM-1 off, then enter UBOOT by USB_KEY. " + USB_KEY_STEPS)
    if st["uboot"] != 1:
        raise Stop(f"no UBOOT on the transporter (status {st}). If this follows a failed "
                   "install, the ROM is no longer mounted, so re-entering it means switching the "
                   "FM-1 off; the boot area [0x0, 0x4000) is never written, so docs/17 still "
                   f"recovers it (D1). {USB_KEY_STEPS}")


# -- Subcommands that use the port ------------------------------------------

def cmd_status(link, _args, result):
    result["status"] = read_status(link)
    print("status:", result["status"])


def cmd_rekey(link, args, result):
    if not args.fm1_is_off:
        raise Refused("rekey needs --fm1-is-off: switch the FM-1 off and check the switch first")
    st = read_status(link)
    result["status"] = st
    if st["uboot"] or st["v15"]:
        raise Stop(f"a device is still mounted on the transporter ({st}); the FM-1 is not off")
    reply = link.request("rekey", TIMEOUT_STATUS)
    if not reply:
        raise Stop("no reply to rekey. The transporter reboots 50 ms after answering, so the "
                   "reply can be lost: if the console shows `KEY: sending`, the rekey took "
                   "effect; otherwise replug the Pico with the FM-1 off")
    if reply != "OK rekey":
        raise Stop(f"unexpected rekey reply {reply!r}")
    result["verdict"] = "transporter rebooting into USB_KEY; reopen the console, then FM-1 on"
    print(result["verdict"])


def upload_loader(link, loader):
    for off in range(0, len(loader), LOADER_CHUNK):
        chunk = loader[off:off + LOADER_CHUNK]
        link.send_line(f"ldr {off} {len(chunk)} {crc32(chunk):08X}")
        link.send_payload(chunk)
        reply = link.recv_line(TIMEOUT_LDR)
        if reply != "OK":
            raise Stop(f"loader upload to the transporter failed at {off}: {reply!r}")


def prepare_loader(link, loader, result, fresh=False):
    """fresh: the pinned loader must be uploaded in this session (install --write).
    Otherwise a loader the transporter already holds is used and recorded as such;
    restore accepts one so that it can follow a failed install without a power cycle."""
    st = read_status(link)
    result["status_before"] = st
    require_uboot(st)
    if fresh and (st["loader"] or st["loader_running"]):
        raise Stop(f"the transporter already holds a loader ({st}); `install --write` uploads "
                   "the pinned loader itself, in a fresh ROM entry. Nothing was written: switch "
                   "the FM-1 off, rekey, and run the write as the first step after "
                   "`UBOOT READY` (docs/22 section 4)")
    if st["loader"] == 1:
        result["loader"] = "held from an earlier session; not re-uploaded"
        print("loader: the transporter already holds one (not re-uploaded this session)")
    else:
        upload_loader(link, loader)
        st = read_status(link)
        result["status_after_upload"] = st
        if st["loader"] != 1 or st["uboot"] != 1:
            raise Stop(f"loader not held by the transporter after upload ({st})")
    reply = link.request("info", TIMEOUT_INFO)
    result["info"] = reply
    print(reply)
    if reply != EXPECTED_INFO:
        raise Stop(f"info is {reply!r}, not {EXPECTED_INFO!r}: not this FM-1's chip and flash")


def cmd_info(link, args, result):
    prepare_loader(link, args.loader_bytes, result)
    result["verdict"] = "info matches: key 980F, flash 856014"


def read_span(link, line, n):
    reply = link.request(line, TIMEOUT_READ_HEADER)
    if reply != f"DATA {n}":
        raise Stop(f"{line}: unexpected reply {reply!r}")
    data = link.recv_bytes(n, TIMEOUT_READ_BYTES)
    if len(data) != n:
        raise Stop(f"{line}: stalled at {len(data):#x} of {n:#x}")
    end = link.recv_line(TIMEOUT_READ_BYTES)
    if end != f"END {crc32(data):08X}":
        raise Stop(f"{line}: transfer check failed ({end!r}, local {crc32(data):08X})")
    return data


def read_flash(link):
    return read_span(link, f"read 0x0 {FLASH_SIZE}", FLASH_SIZE)


def save_new(path, data):
    with open(path, "xb") as f:
        f.write(data)


def cmd_dump(link, args, result):
    prepare_loader(link, args.loader_bytes, result)
    data = read_flash(link)
    save_new(args.out, data)
    result.update(out=str(args.out), sha256=sha256(data), crc32=f"{crc32(data):08X}")
    print(f"saved {args.out}: {len(data)} B, sha256 {sha256(data)}")
    if args.compare:
        report = compare_images(Path(args.compare).read_bytes(), data)
        result["compare"] = {"ref": str(args.compare), **report}
        print_compare(args.compare, args.out, report)
        if not report["identical"]:
            raise Stop(f"{args.out} differs from {args.compare}")
    result["verdict"] = "dump saved" + (" and identical to the reference" if args.compare else "")


def dump_paths(log):
    stem = log.with_suffix("")
    return {k: Path(f"{stem}-{k}.bin") for k in ("before-a", "before-b", "after")}


def precondition(mode, before, args, result):
    """Return (target, write end) once the before-image allows the write."""
    head = sha256(before[:HEAD_END])
    region = sha256(before[:REGION_BYTES])
    result["before_head_sha256"], result["before_region_sha256"] = head, region
    if head != HEAD_SHA256:
        raise Stop(f"flash head [0, {HEAD_END:#x}) is {head}, not V15's {HEAD_SHA256}: not "
                   "the layout this tool knows. Stop; read docs/07 and docs/17")
    if mode == "install":
        known = KNOWN_REGIONS.get(region)
        if not known:
            raise Stop(f"flash [0, {REGION_BYTES:#x}) is {region}, not a known region "
                       f"({', '.join(v[0] for v in KNOWN_REGIONS.values())}); an install starts "
                       "only from a known image. Restore V15 first (docs/22 section 5)")
        name, identity, app_end = known
        if args.identity != identity:
            raise Stop(f"--identity {args.identity!r} does not match the flash, which holds "
                       f"{name} ({identity}); read the identity again (docs/22 section 3)")
        result["layout"] = {"region": name, "identity": identity, "app_end": f"{app_end:#x}"}
        return args.target, min(app_end, WRITE_END)
    known = KNOWN_REGIONS.get(region)
    result["layout"] = {"region": known[0] if known else "unknown (a partial or other image)",
                        "app_end": f"{WRITE_END:#x}", "target": "stock V15"}
    return args.target, WRITE_END


def write_sectors(link, target, sectors, result):
    done = []
    result["sectors_written"] = done
    for s in sectors:
        chunk = target[s:s + SECTOR]
        link.send_wsec(s, chunk)
        reply = link.recv_line(TIMEOUT_WSEC)
        if reply != "OK":
            raise Stop(f"wsec {s:#x}: {reply!r}. The sector may be erased or partly written. "
                       "Do not power-cycle and do not retry it: keep the FM-1 on and run "
                       "`restore` (docs/22 section 5)")
        back = read_span(link, f"read {s:#x} {SECTOR}", SECTOR)
        if back != chunk:
            raise Stop(f"read-back of {s:#x} differs from what was written. Do not power-cycle: "
                       "run `restore` (docs/22 section 5)")
        done.append(f"{s:#07x}")
        print(f"sector {s:#07x}: written, read back equal")


def cmd_write(link, args, result):
    mode = args.cmd
    prepare_loader(link, args.loader_bytes, result,
                   fresh=(mode == "install" and args.write))
    paths = dump_paths(args.log)
    a = read_flash(link)
    save_new(paths["before-a"], a)
    b = read_flash(link)
    save_new(paths["before-b"], b)
    result["before"] = {"a": str(paths["before-a"]), "b": str(paths["before-b"]),
                        "sha256": [sha256(a), sha256(b)]}
    if a != b:
        raise Stop("the two before-reads differ in sectors "
                   + " ".join(f"{s:#07x}" for s in sector_diff(a, b, 0, FLASH_SIZE))
                   + ": the flash or the link is unstable; not writing")
    target, write_end = precondition(mode, a, args, result)
    try:
        sectors = plan_write(a, target, write_end)
    except Refused as exc:
        raise Stop(str(exc)) from None
    result["plan"] = {"write_end": f"{write_end:#x}", "sectors": [f"{s:#07x}" for s in sectors],
                      "target_sha256": sha256(target)}
    print(f"{mode}: {len(sectors)} sectors differ inside [{WRITE_MIN:#x}, {write_end:#x})"
          + (": " + " ".join(f"{s:#07x}" for s in sectors) if sectors else ""))
    if not args.write:
        result["verdict"] = f"dry run: nothing written ({len(sectors)} sectors planned)"
        print(result["verdict"])
        return 0
    if not sectors:
        result["verdict"] = "nothing to write: the flash already holds the target"
        print(result["verdict"])
        return 0
    if mode == "install":
        lock = install_lock(args.package_sha256)
        lock.parent.mkdir(parents=True, exist_ok=True)
        with open(lock, "x") as f:   # FileExistsError: never a second attempt
            f.write(json.dumps({"time": round(time.time(), 3), "receipt": str(args.log),
                                "package_sha256": args.package_sha256}) + "\n")
        result["lock"] = str(lock)
    link.arm(target, write_end, sectors)
    write_sectors(link, target, sectors, result)
    after = read_flash(link)
    expected = target + a[REGION_BYTES:]
    result["after"] = {"path": str(paths["after"]), "sha256": sha256(after),
                       "equal": after == expected}
    try:
        save_new(paths["after"], after)
    except OSError as exc:      # the verdict below still stands
        result["after"]["save_error"] = f"{type(exc).__name__}: {exc}"
    if after != expected:
        raise Stop("the final read differs from the expected flash in sectors "
                   + " ".join(f"{s:#07x}" for s in sector_diff(after, expected, 0, FLASH_SIZE))
                   + ". Do not power-cycle: run `restore` (docs/22 section 5)")
    result["verdict"] = (f"{mode} done: {len(sectors)} sectors written and read back; the final "
                         "read equals the target over [0, 0x93000) and the before-read above")
    if "save_error" in result["after"]:
        result["verdict"] += f"; the after-dump was not saved ({result['after']['save_error']})"
    print(result["verdict"])
    return 0


def install_lock(package_sha256):
    return LOCK_DIR / f"install-{package_sha256}.lock"


# -- Offline subcommands ------------------------------------------------------

def compare_images(ref, data):
    sectors = [a for a in range(0, max(len(ref), len(data)), SECTOR)
               if ref[a:a + SECTOR] != data[a:a + SECTOR]]
    return {
        "identical": ref == data and len(data) == FLASH_SIZE,
        "sizes": [len(ref), len(data)],
        "sha256": [sha256(ref), sha256(data)],
        "differing_sectors": [f"{a:#07x}" for a in sectors],
    }


def print_compare(a, b, report):
    print(f"{a}: {report['sizes'][0]} B sha256 {report['sha256'][0]}")
    print(f"{b}: {report['sizes'][1]} B sha256 {report['sha256'][1]}")
    if report["identical"]:
        print("IDENTICAL over the whole 1 MiB")
    else:
        print("DIFFERENT" + (": sectors " + " ".join(report["differing_sectors"])
                             if report["differing_sectors"] else ": sizes"))


def cmd_compare(args):
    report = compare_images(Path(args.a).read_bytes(), Path(args.b).read_bytes())
    print_compare(args.a, args.b, report)
    return 0 if report["identical"] else 1


def cmd_preflight(args):
    """Offline: print every pinned value and, given both packages, the plan an
    install from stock V15 would write, for the owner's approval."""
    print(f"tool {Path(__file__).name}: sha256 {sha256_file(__file__)}")
    print(f"transporter port: /dev/serial/by-id/{expected_port_name()}")
    print(f"expected info: {EXPECTED_INFO}")
    print(f"approved package: {APPROVED_PACKAGE_SHA256 or 'none yet'}")
    v15 = lunar = None
    if args.loader:
        admit_loader(args.loader)
        print(f"loader {args.loader}: wl82loader.bin, {LOADER_BYTES} B, {LOADER_SHA256}")
    if args.v15:
        v15 = admit_v15(args.v15)
        print(f"v15 {args.v15}: stock V15, region sha256 {V15_REGION_SHA256}")
    if args.package:
        if not args.sha256:
            raise Refused("--sha256 is required with --package")
        raw = Path(args.package).read_bytes()
        if sha256(raw) != args.sha256.lower():
            raise Refused(f"{args.package}: SHA-256 is {sha256(raw)}, not {args.sha256}")
        lunar = region_of_package(raw)
        check_target(lunar, args.package)
        state = "APPROVED" if sha256(raw) == APPROVED_PACKAGE_SHA256 else "not approved"
        print(f"package {args.package}: {len(raw)} B, sha256 {sha256(raw)} ({state}); "
              f"region sha256 {sha256(lunar)}")
    if v15 is not None and lunar is not None:
        sectors = plan_write(v15, lunar, WRITE_END)
        print(f"install over stock V15 writes {len(sectors)} sectors inside "
              f"[{WRITE_MIN:#x}, {WRITE_END:#x}): " + " ".join(f"{s:#07x}" for s in sectors))
        back = plan_write(lunar, v15, WRITE_END)
        print(f"restore to V15 afterwards writes {len(back)} sectors")
    return 0


# -- Main --------------------------------------------------------------------

PORT_COMMANDS = {"status": cmd_status, "rekey": cmd_rekey, "info": cmd_info,
                 "dump": cmd_dump, "install": cmd_write, "restore": cmd_write}


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help=f"the transporter's data port, /dev/serial/by-id/"
                    f"{expected_port_name()}")
    ap.add_argument("--log", type=Path, help="new JSONL receipt file (required with --port)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="read the transporter's status (read-only)")
    r = sub.add_parser("rekey", help="reboot the transporter into USB_KEY; FM-1 must be off")
    r.add_argument("--fm1-is-off", action="store_true")
    i = sub.add_parser("info", help="chip key and flash id through the loader")
    i.add_argument("--loader", required=True)
    d = sub.add_parser("dump", help="read the whole 1 MiB flash through the loader")
    d.add_argument("out", type=Path)
    d.add_argument("--loader", required=True)
    d.add_argument("--compare", type=Path)
    n = sub.add_parser("install", help="write the approved Lunar package's region (dry run "
                       "unless --write)")
    n.add_argument("package", type=Path)
    n.add_argument("--sha256", required=True)
    n.add_argument("--identity", required=True,
                   help="the identity tools/fm1_identify.py read before keying, e.g. FM-1_015")
    n.add_argument("--loader", required=True)
    n.add_argument("--write", action="store_true")
    n.add_argument("--tool-sha256", help="this file's SHA-256, as approved; needed with --write")
    s = sub.add_parser("restore", help="write stock V15's region back (dry run unless --write)")
    s.add_argument("--v15", required=True, type=Path)
    s.add_argument("--loader", required=True)
    s.add_argument("--write", action="store_true")
    s.add_argument("--tool-sha256", help="this file's SHA-256; needed with --write")
    p = sub.add_parser("preflight", help="check packages, loader and this tool offline")
    p.add_argument("--package", type=Path)
    p.add_argument("--sha256")
    p.add_argument("--v15", type=Path)
    p.add_argument("--loader", type=Path)
    c = sub.add_parser("compare", help="two dumps must be byte-identical (offline)")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    return ap


def admit(args):
    """Every check that needs no port. Raises Refused."""
    if args.cmd in ("info", "dump", "install", "restore"):
        args.loader_bytes = admit_loader(args.loader)
    if args.cmd == "install":
        args.target = admit_install(args.package, args.sha256)
        args.package_sha256 = APPROVED_PACKAGE_SHA256
        if install_lock(args.package_sha256).exists():
            raise Refused(f"{install_lock(args.package_sha256)} exists: this package was already "
                          "installed or attempted. There is no second attempt; another needs a "
                          "new owner approval")
    if args.cmd == "restore":
        args.target = admit_v15(args.v15)
    if args.cmd in ("install", "restore") and args.write:
        own = sha256_file(__file__)
        if not args.tool_sha256:
            raise Refused(f"--write needs --tool-sha256: the hash the owner approved (this "
                          f"file is {own})")
        if args.tool_sha256.lower() != own:
            raise Refused(f"--tool-sha256 {args.tool_sha256} is not this file's {own}: "
                          "not the approved tool")
    if args.cmd == "dump":
        if args.out.exists():
            raise Refused(f"{args.out} exists; dumps are never overwritten")
        if args.compare and not args.compare.is_file():
            raise Refused(f"{args.compare}: no such reference dump")
    if args.cmd == "rekey" and not args.fm1_is_off:
        raise Refused("rekey needs --fm1-is-off: switch the FM-1 off and check the switch first")
    if args.cmd == "install" and (getattr(os, "geteuid", lambda: 1)() == 0
                                  or os.environ.get("SUDO_USER")):
        raise Refused("install does not run as root or under sudo: its one-attempt lock is in "
                      "the user's home (~/.local/state/fm1t_m8), so another account would not "
                      "see it. Give your user the serial port (group dialout) instead")
    check_port_path(args.port)
    if not args.log:
        raise Refused("--log is required: every line sent and received is recorded")
    if args.log.exists():
        raise Refused(f"{args.log} exists; each step gets a new receipt")
    if args.cmd in ("install", "restore"):
        for path in dump_paths(args.log).values():
            if path.exists():
                raise Refused(f"{path} exists; dumps are never overwritten")


def main(argv=None, opener=None):
    opener = opener or open_port
    argv = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "compare":
            return cmd_compare(args)
        if args.cmd == "preflight":
            return cmd_preflight(args)
        admit(args)
    except Refused as exc:
        print(f"fm1t_m8: {exc}", file=sys.stderr)
        return 1

    result = {}
    code = 0
    with open(args.log, "x") as fp:
        def log(event, **fields):
            fp.write(json.dumps({"time": round(time.time(), 3), "event": event, **fields}) + "\n")
            fp.flush()

        log("start", tool=Path(__file__).name, tool_sha256=sha256_file(__file__),
            argv=argv, cmd=args.cmd, port=args.port,
            package_sha256=getattr(args, "package_sha256", None),
            build_id=APPROVED_BUILD_ID if args.cmd == "install" else None,
            write=bool(getattr(args, "write", False)))
        port = None
        link = None
        try:
            port = opener(args.port)
            link = Link(port, args.cmd, log)
            handshake(link)
            code = PORT_COMMANDS[args.cmd](link, args, result) or 0
        except Refused as exc:
            code, result["verdict"] = 3, f"STOP: refused mid-session: {exc}"
        except FileExistsError as exc:
            why = ("this package was already installed or attempted; no second attempt"
                   if str(exc.filename).endswith(".lock") else "never overwritten")
            code, result["verdict"] = 3, f"STOP: {exc.filename} exists: {why}"
        except Stop as exc:
            code, result["verdict"] = 3, f"STOP: {exc}"
        except Exception as exc:  # noqa: BLE001  (record it, then stop)
            code, result["verdict"] = 3, f"STOP: {type(exc).__name__}: {exc}"
        except KeyboardInterrupt:
            code, result["verdict"] = 3, "STOP: interrupted"
        finally:
            if link is not None and link.written:
                result["wsec_sent"] = [f"{s:#07x}" for s in link.written]
                if code and "run `restore`" not in result.get("verdict", ""):
                    result["verdict"] = (result.get("verdict", "STOP") + ". Writes began this "
                                         "session: do not power-cycle the FM-1; run `restore` "
                                         "(docs/22 section 5)")
            if port is not None:
                try:
                    port.close()
                except Exception:  # noqa: BLE001
                    pass
            log("end", exit=code, **result)
    if code:
        print(f"fm1t_m8: {result.get('verdict')}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
