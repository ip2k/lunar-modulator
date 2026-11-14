#!/usr/bin/env python3
"""fm1t_m5p2 - the m5-plan-2 host tool for the FM-1 Transporter data port, nothing more.

A copy of fm1t_m5.py (itself adapted from kurogedelic's FM-1-transporter
`tools/fm1t.py` at a7fb5e8; MIT, Copyright (c) 2026 kurogedelic; licence in
LICENSE.upstream next to this file) for the two RAM runs the owner approved on
2026-11-14 (HANDOFF "Owner decisions, 2026-11-14";
notes/2026-11-14-m5-plan-2.md sections 6, 7 and 9). fm1t_m5.py is left
untouched; tests/test_fm1t_m5p2.py pins the lines on which the two differ.

    fm1t_m5p2.py preflight [--image IMG --sha256 HEX] [--loader wl82loader.bin]
    fm1t_m5p2.py --port P --log L status
    fm1t_m5p2.py --port P --log L rekey --fm1-is-off
    fm1t_m5p2.py --port P --log L info --loader wl82loader.bin
    fm1t_m5p2.py --port P --log L dump OUT.bin --loader wl82loader.bin [--compare REF.bin]
    fm1t_m5p2.py --port P --log L ramrun m5p2.bin --run 1 --sha256 HEX
    fm1t_m5p2.py --port P --log L ramrun m5p2-mailbox.bin --run 2 --sha256 HEX
    fm1t_m5p2.py --port P --log L crumbs
    fm1t_m5p2.py compare A.bin B.bin

What differs from fm1t_m5.py, and why:

1. Two pinned images, one per run, each with its own one-attempt lock:
   - run 1, `m5p2.bin` (build id m5-plan-2, SHA-256 aba6ed7c...), lock
     fm1t_m5p2-ramrun.lock;
   - run 2, `m5p2-mailbox.bin` (build id m5-plan-2m, SHA-256 b63a643e...),
     lock fm1t_m5p2-mailbox-ramrun.lock. It is admitted only from a run
     directory that already holds run 1's lock, and run 1 is refused where
     run 2's lock exists. Either run is refused where M5's or M6's lock is.
   Both images are 7,920 B, so memw carries exactly two chunks
   (4,096 + 3,824 B) inside [0x01C02000, 0x01C03EF0), and the jump is
   refused until all of them were written. `--run` must name the run whose
   pinned hash the image has; there is no flag that admits another image.
2. `crumbs` (run 2 only) reads the image's twelve breadcrumb words back after
   the watchdog reset has returned the chip to the mask ROM. It sends `ping`,
   `status` (which must answer uboot=1 v15=0 loader=0 loader_running=0, because
   the flash loader would overwrite the breadcrumbs: it is loaded at
   0x01C02000 and is 24,064 B long) and exactly one `memr 0x1c05fc0 48`, the
   transporter's existing ROM memory read. It is admitted only in a run
   directory holding run 2's lock. Its own lock, fm1t_m5p2-crumbs.lock, is
   created when the transporter answers `DATA 48`, so a read that never
   happened (no reply, or `ERR memr at ...` on a stale mount) can be tried
   again, and a read that happened cannot. The 48 bytes are logged as hex
   before they are checked or decoded.
3. `status` must also answer v15=0 wherever the ROM is needed, so nothing
   but `ping`, `status` and `rekey` (which refuses a mounted device) is ever
   sent while a running V15 is attached.

Unchanged from fm1t_m5.py: the soft key cannot be sent (no `uboot` request,
no console port: --port must end in -if02); ramrun refuses --loader,
FM1T_LOADER, --addr, --arg, --clear, --poke and --read, and starts only on a
fresh ROM entry (loader=0 loader_running=0); the jump is sent once and
nothing follows it; `info` and `dump` take only JieLi's wl82loader.bin and
only read flash (there is no write, erase, wsec, runapp or selftest path);
`compare` requires two whole, byte-identical 1 MiB dumps; lengths are plain
decimal; and every line sent and received goes to a new JSONL receipt.

All command strings the tool can put on the data port are in ALLOWED; Link
is the only code that writes to the port and checks every line against the
subcommand's allow-list before writing it (tests/test_fm1t_m5p2.py).
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

# -- What the owner approved (2026-11-14, HANDOFF "Owner decisions, 2026-11-14").
#    Changing any of these needs a new approval; there is deliberately no
#    command-line override. Run 2 only after run 1, in the same run directory.
RUNS = {
    1: {"sha256": "aba6ed7ceaa0cac990dedcaf664b10707632a139be83b3bea5e0f62739bf968c",
        "build_id": "m5-plan-2", "lock": "fm1t_m5p2-ramrun.lock", "needs": None},
    2: {"sha256": "b63a643e14983ac07a883867d073368733f6f714b7f35116aa85a4e91d80421c",
        "build_id": "m5-plan-2m", "lock": "fm1t_m5p2-mailbox-ramrun.lock",
        "needs": "fm1t_m5p2-ramrun.lock"},
}
APPROVED_IMAGE_BYTES = 7920      # both images
RAM_BASE = 0x01C02000            # load and jump address, fixed
RAM_END = 0x01C06000             # the image must end at or before this (M5 link budget)
JUMP_ARG = 0x1                   # as the ROM honoured on the dev kit; upstream LOADER_ARG
MEMW_CHUNK = 4096                # transporter limit per memw / memr (JL_SECTOR_SIZE, JL_READ_MAX)

# One RAM-run attempt per run and run directory: created just before the first
# memw, next to the receipt. A second attempt (a retry) needs a new owner approval.
RAMRUN_LOCKS = tuple(r["lock"] for r in RUNS.values())
# M5's and M6's locks in the same directory also refuse: m5p2 needs its own.
OTHER_RAMRUN_LOCKS = ("fm1t_m5-ramrun.lock", "fm1t_m6-ramrun.lock")

# The breadcrumbs (firmware/m5p2/m5p2.h): twelve little-endian words, word 0 the
# magic "M5P2", word 11 its complement. Read once, after run 2, from the ROM.
CRUMBS_ADDR = 0x01C05FC0
CRUMBS_BYTES = 48
CRUMBS_MAGIC = 0x3250354D
CRUMBS_LOCK = "fm1t_m5p2-crumbs.lock"
CRUMB_NAMES = ("magic", "stage", "wdt_con", "ticks_per_block", "max_gap", "kicks",
               "kick_failures", "panel", "elapsed_ms", "cycles", "ticks", "check")
STAGES = ("", "entry", "pa2_on", "timer_ok", "timer_dead", "measured", "cadence_a",
          "cadence_b", "spi_ok", "setup_ok", "display_on", "frame_done", "blinking",
          "finishing")
TIMER_DEAD_FLAG = 0x100          # in the stage word: TIMER4 failed at some point
PANEL_RESULTS = {0: "ok", 1: "invalid", 2: "transfer_failed", 3: "delay_failed",
                 0xFF: "not_run"}
if not (RAM_BASE + APPROVED_IMAGE_BYTES <= CRUMBS_ADDR
        and CRUMBS_ADDR + CRUMBS_BYTES <= RAM_END):
    raise SystemExit("fm1t_m5p2: the image and the breadcrumbs overlap or leave the window")

# JieLi's WL82 USB loader from kagaimiq's jl-uboot-tool (docs/17 section 1).
LOADER_SHA256 = "d41da6126760c9d66660bcc0cac8d27d221806c5e369a8036921efe68dca5376"
LOADER_BYTES = 24064
LOADER_CHUNK = 4096

FLASH_SIZE = 0x100000
SECTOR = 0x1000
EXPECTED_INFO = "OK key=980F type=3 id=856014"

# `ERR jump ms=N`: the Pico gives up on the ROM's reply after 2,000 ms
# (XFER_TIMEOUT_MS in src/pio_host.c). A shorter failure means the command
# itself failed, not that the image is running.
JUMP_RUNNING_MIN_MS = 1500
JUMP_RUNNING_MAX_MS = 10000

BAUD = 115200                    # never 1200: that puts the Pico into BOOTSEL
PORT_SUFFIX = "-if02"            # the data port; interface 0 is the console
PORT_NAME = "FM-1_Transporter"

TIMEOUT_STATUS = 5
TIMEOUT_LDR = 5
TIMEOUT_INFO = 30
TIMEOUT_READ_HEADER = 30
TIMEOUT_READ_BYTES = 10
TIMEOUT_MEM = 20
TIMEOUT_JUMP = 20

USB_KEY_STEPS = ("ROM entry is by USB_KEY only (docs/19 and docs/17 section 4): switch the "
                 "FM-1 OFF, run `fm1t_m5p2.py ... rekey --fm1-is-off`, reopen the console, wait "
                 "for the key to run, switch the FM-1 ON, wait for `UBOOT READY`, then rerun.")

# -- The allow-list: every line this tool can send, per subcommand. Each
#    pattern must match the whole line. Payload bytes are allowed only
#    directly after a memw/ldr header, with that header's length and CRC.
_HEX8 = r"[0-9A-F]{8}"
_LDR_OFFSETS = "|".join(str(o) for o in range(0, LOADER_BYTES, LOADER_CHUNK))
# Only the chunk addresses of the approved images: 0x1c02000, 0x1c03000.
_RAM_ADDRS = "|".join(f"{a:#x}" for a in range(RAM_BASE, RAM_BASE + APPROVED_IMAGE_BYTES,
                                               MEMW_CHUNK))
# A length the transporter reads as the same number (strtoul base 0: no leading 0).
_LEN = r"[1-9][0-9]{0,3}"
PATTERNS = {
    "ping": r"ping",
    "status": r"status",
    "rekey": r"rekey",
    "ldr": rf"ldr ({_LDR_OFFSETS}) ({_LEN}) ({_HEX8})",
    "info": r"info",
    "read": rf"read 0x0 {FLASH_SIZE}",
    "memw": rf"memw ({_RAM_ADDRS}) ({_LEN}) ({_HEX8})",
    "memr": rf"memr ({_RAM_ADDRS}) ({_LEN})",
    "jump": rf"jump {RAM_BASE:#x} {JUMP_ARG:#x}",
    "crumbs_memr": rf"memr {CRUMBS_ADDR:#x} {CRUMBS_BYTES}",
}
ALLOWED = {
    "status": ("ping", "status"),
    "rekey": ("ping", "status", "rekey"),
    "info": ("ping", "status", "ldr", "info"),
    "dump": ("ping", "status", "ldr", "info", "read"),
    "ramrun": ("ping", "status", "memw", "memr", "jump"),
    "crumbs": ("ping", "status", "crumbs_memr"),
}
# Named so the refusal says why. The allow-list already excludes them.
FORBIDDEN_WORDS = {
    "uboot": "sends the soft key F0 22 24 35 7D F7 to a mounted V15 (CLAUDE.md trap 9, D2)",
    "k": "console soft key (D2)",
    "wsec": "flash erase and program",
    "runapp": "leaves UBOOT through the loader (docs/17 section 8)",
}
_COMPILED = {name: re.compile(p) for name, p in PATTERNS.items()}


class Refused(Exception):
    """Raised before anything is sent: admission, arguments, the gate."""


class Stop(Exception):
    """Raised after the session started: an unexpected reply or state. Stop and
    power off; do not retry (docs/19)."""


# -- Admission (offline) -----------------------------------------------------

def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def admit_image(path, sha256, run):
    """The image must fit the M5 window and be exactly the image pinned for `run`."""
    if run not in RUNS:
        raise Refused(f"--run must be one of {sorted(RUNS)}")
    if not sha256:
        raise Refused("--sha256 is required")
    data = Path(path).read_bytes()
    if not data:
        raise Refused(f"{path} is empty")
    if RAM_BASE + len(data) > RAM_END:
        raise Refused(f"{path}: {len(data)} B at {RAM_BASE:#010x} ends at "
                      f"{RAM_BASE + len(data):#010x}, past {RAM_END:#010x}")
    digest = hashlib.sha256(data).hexdigest()
    if sha256.lower() != digest:
        raise Refused(f"{path}: SHA-256 is {digest}, not the --sha256 given ({sha256})")
    if digest != RUNS[run]["sha256"] or len(data) != APPROVED_IMAGE_BYTES:
        raise Refused(f"{path}: {digest} ({len(data)} B) is not the approved run {run} image "
                      f"{RUNS[run]['sha256']} ({APPROVED_IMAGE_BYTES} B, build id "
                      f"{RUNS[run]['build_id']}); another image needs a code change and a new "
                      "owner approval")
    return data


def admit_loader(path):
    if not path:
        raise Refused("--loader wl82loader.bin is required for info and dump")
    data = Path(path).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != LOADER_BYTES or digest != LOADER_SHA256:
        raise Refused(f"{path}: {len(data)} B, SHA-256 {digest}; expected JieLi's "
                      f"wl82loader.bin, {LOADER_BYTES} B, {LOADER_SHA256}")
    return data


def check_port_path(port):
    if not port:
        raise Refused("--port is required (the transporter's /dev/serial/by-id/...-if02); "
                      "this tool does not probe for ports")
    name = os.path.basename(port)
    if "-if00" in name or not name.endswith(PORT_SUFFIX) or PORT_NAME not in name:
        raise Refused(f"{port}: not the FM-1 Transporter data port; pass "
                      f"/dev/serial/by-id/usb-kurogedelic_{PORT_NAME}_<serial>{PORT_SUFFIX} "
                      "(never the console, -if00)")


def crc32(data):
    return zlib.crc32(data) & 0xFFFFFFFF


# -- The gate ----------------------------------------------------------------

def approved_write_end():
    """The end of the SRAM range the owner approved for writing: the image."""
    return RAM_BASE + APPROVED_IMAGE_BYTES


def check_line(mode, line):
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
        if name in ("memw", "memr"):
            addr, length = int(m.group(1), 16), int(m.group(2))
            end = approved_write_end()
            if not 1 <= length <= MEMW_CHUNK or addr + length > end:
                raise Refused(f"refused: {line!r} leaves the approved write range "
                              f"[{RAM_BASE:#x}, {end:#x})")
        if name == "ldr":
            off, length = int(m.group(1)), int(m.group(2))
            if not 1 <= length <= LOADER_CHUNK or off + length > LOADER_BYTES:
                raise Refused(f"refused: {line!r} outside the loader's {LOADER_BYTES} B")
        return name
    raise Refused(f"refused in {mode}: {line!r} is not on the allow-list")


class Link:
    """The only code that writes to the port. Every line is checked against the
    subcommand's allow-list, logged, then written; replies are logged."""

    def __init__(self, port, mode, log, image=None, run=None):
        self._port = port
        self.mode = mode
        self._log = log
        self._payload = None        # (name, addr, len, crc32) a memw/ldr header announced
        self._memw_sent = set()
        self._written = 0           # image bytes handed to memw, in order
        self.sealed = None          # reason nothing more may be sent
        self._image = None
        if mode == "ramrun":
            # The gate itself knows the one approved image: a memw payload must be
            # exactly its bytes at that address, and the jump needs all of them.
            if run not in RUNS or image is None \
                    or hashlib.sha256(image).hexdigest() != RUNS[run]["sha256"] \
                    or len(image) != APPROVED_IMAGE_BYTES:
                raise Refused("refused: a RAM-run link needs the approved image of its run")
            self._image = bytes(image)

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
        name = check_line(self.mode, line)
        if name == "memw":
            addr = int(line.split()[1], 16)
            if addr in self._memw_sent:
                raise Refused(f"refused: memw {addr:#x} again; a memw is never resent")
            if addr != RAM_BASE + self._written:
                raise Refused(f"refused: memw {addr:#x} out of order; the image goes up "
                              f"in order from {RAM_BASE:#x}")
        if name == "jump" and self._written != APPROVED_IMAGE_BYTES:
            raise Refused(f"refused: jump before the whole approved image was written "
                          f"({self._written} of {APPROVED_IMAGE_BYTES} B)")
        self._check_quiet()
        if name == "memw":
            self._memw_sent.add(addr)
        if name in ("memw", "ldr"):
            parts = line.split()
            self._payload = (name, int(parts[1], 0), int(parts[2]), int(parts[3], 16))
        self._log("tx", line=line)
        self._write(line.encode("ascii") + b"\n")
        if name == "jump":
            self.sealed = "the jump"
        elif name == "crumbs_memr":
            self.sealed = "the crumbs read"
        elif name == "rekey":
            self.sealed = "rekey (the transporter reboots)"
        return name

    def send_payload(self, data):
        if not self._payload:
            raise Refused("refused: payload bytes without a memw/ldr header")
        name, addr, length, crc = self._payload
        if len(data) != length or crc32(data) != crc:
            raise Refused(f"refused: payload {len(data)} B crc {crc32(data):08X} does not "
                          f"match its header ({length} B, {crc:08X})")
        if name == "memw":
            off = addr - RAM_BASE
            if self._image is None or data != self._image[off:off + length]:
                raise Refused(f"refused: memw {addr:#x} payload is not the approved image's "
                              "bytes at that address")
            self._written += length
        self._payload = None
        self._log("tx-bytes", len=len(data), crc32=f"{crc32(data):08X}",
                  sha256=hashlib.sha256(data).hexdigest())
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
                  sha256=hashlib.sha256(out).hexdigest())
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
    """Find the data port: `ping` is answered PONG by the transporter's core 0,
    even while core 1 is still keying. Bytes already waiting predate this run:
    they are logged and dropped, never taken as a reply."""
    link.drain_at_open()
    reply = link.request("ping", TIMEOUT_STATUS)
    if reply != "PONG":
        raise Stop(f"no PONG from the data port (got {reply!r}); is this the transporter's -if02?")


_STATUS = re.compile(r"OK uboot=([01]) v15=([01]) loader=([01]) loader_running=([01])")


def read_status(link):
    reply = link.request("status", TIMEOUT_STATUS)
    if not reply:
        # Only `ping` and `rekey` are served by core 0. `status` waits for core 1,
        # which is busy until the USB_KEY handoff (src/transporter_proto.c, main.c).
        raise Stop("no reply to `status`: the transporter's core 1 is busy, most likely "
                   "waiting for the console or running the USB_KEY (the console shows "
                   "`KEY: ... packets`). This is not a fault. With the FM-1 off and the key "
                   "running, switch the FM-1 on and wait for `UBOOT READY`; do not rekey")
    m = _STATUS.fullmatch(reply)
    if not m:
        raise Stop(f"unexpected status reply {reply!r}")
    return dict(zip(("uboot", "v15", "loader", "loader_running"), (int(x) for x in m.groups())))


def require_uboot(st):
    if st["uboot"] != 1 or st["v15"] != 0:
        raise Stop(f"no UBOOT on the transporter (status {st}). {USB_KEY_STEPS}")


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
        raise Stop(f"a device is still mounted on the transporter ({st}); the FM-1 is not off. "
                   "Switch it off and rerun rekey")
    reply = link.request("rekey", TIMEOUT_STATUS)
    if not reply:
        raise Stop("no reply to rekey. The transporter reboots 50 ms after answering, so the "
                   "reply can be lost: if the console shows it rebooting and `KEY: sending`, "
                   "the rekey took effect; otherwise replug the Pico with the FM-1 off")
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


def prepare_loader(link, loader, result):
    st = read_status(link)
    result["status_before"] = st
    require_uboot(st)
    if st["loader"] != 1:
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


def read_flash(link):
    reply = link.request(f"read 0x0 {FLASH_SIZE}", TIMEOUT_READ_HEADER)
    if reply != f"DATA {FLASH_SIZE}":
        raise Stop(f"read: unexpected reply {reply!r}")
    data = link.recv_bytes(FLASH_SIZE, TIMEOUT_READ_BYTES)
    if len(data) != FLASH_SIZE:
        raise Stop(f"read stalled at {len(data):#x} of {FLASH_SIZE:#x}")
    end = link.recv_line(TIMEOUT_READ_BYTES)
    if end != f"END {crc32(data):08X}":
        raise Stop(f"read: transfer check failed ({end!r}, local {crc32(data):08X})")
    return data


def cmd_dump(link, args, result):
    prepare_loader(link, args.loader_bytes, result)
    t0 = time.time()
    data = read_flash(link)
    with open(args.out, "xb") as f:
        f.write(data)
    digest = hashlib.sha256(data).hexdigest()
    result.update(out=str(args.out), sha256=digest, crc32=f"{crc32(data):08X}",
                  seconds=round(time.time() - t0, 1))
    print(f"saved {args.out}: {len(data)} B, sha256 {digest}")
    if args.compare:
        report = compare_images(Path(args.compare).read_bytes(), data)
        result["compare"] = {"ref": str(args.compare), **report}
        print_compare(args.compare, args.out, report)
        if not report["identical"]:
            raise Stop(f"{args.out} differs from {args.compare}")
    result["verdict"] = "dump saved" + (" and identical to the reference" if args.compare else "")


def mem_write(link, addr, data):
    for off in range(0, len(data), MEMW_CHUNK):
        chunk = data[off:off + MEMW_CHUNK]
        link.send_line(f"memw {addr + off:#x} {len(chunk)} {crc32(chunk):08X}")
        link.send_payload(chunk)
        reply = link.recv_line(TIMEOUT_MEM)
        if reply != "OK":
            raise Stop(f"memw {addr + off:#x}: {reply!r}; not retried")


def mem_read(link, addr, length):
    out = bytearray()
    for off in range(0, length, MEMW_CHUNK):
        n = min(MEMW_CHUNK, length - off)
        reply = link.request(f"memr {addr + off:#x} {n}", TIMEOUT_MEM)
        if reply != f"DATA {n}":
            raise Stop(f"memr {addr + off:#x}: {reply!r}")
        data = link.recv_bytes(n, TIMEOUT_MEM)
        end = link.recv_line(TIMEOUT_MEM)
        if len(data) != n or end != f"END {crc32(data):08X}":
            raise Stop(f"memr {addr + off:#x}: transfer check failed ({end!r})")
        out += data
    return bytes(out)


_JUMP = re.compile(r"(OK|ERR jump) ms=(\d+)")


def jump_verdict(reply):
    """Return (exit code, verdict) for the jump's reply. Exit 0 only for the
    expected outcome of a non-returning image."""
    m = _JUMP.fullmatch(reply)
    if not reply:
        return 3, "no reply to jump: stop; watch the unit, photograph, power off; do not retry"
    if not m:
        return 3, f"unexpected jump reply {reply!r}: stop; power off; do not retry"
    ms = int(m.group(2))
    if m.group(1) == "OK":
        return 3, (f"jump answered OK after {ms} ms: the image returned, which m5p2 never does; "
                   "stop; watch the unit, power off; do not retry")
    if JUMP_RUNNING_MIN_MS <= ms <= JUMP_RUNNING_MAX_MS:
        return 0, (f"ERR jump after {ms} ms: the ROM never answered, as expected for an image "
                   "that does not return. Image presumed running; the backlight, the TFT and "
                   "the LEDs are the proof. Nothing more is sent")
    return 3, (f"ERR jump after {ms} ms, outside [{JUMP_RUNNING_MIN_MS}, "
               f"{JUMP_RUNNING_MAX_MS}]: either the ROM refused the jump or the FM-1 left "
               "the bus early (the console says which: `EP .. timeout` or `device gone`). "
               "The image may be running: watch the unit and photograph it, then power off; "
               "stop; do not retry")


def cmd_ramrun(link, args, result):
    image = args.image_bytes
    run = RUNS[args.run]
    st = read_status(link)
    result["status"] = st
    require_uboot(st)
    if st["loader"] or st["loader_running"]:
        raise Stop(f"the transporter holds or runs the flash loader ({st}); a RAM run needs a "
                   f"fresh ROM entry. FM-1 off, rekey, FM-1 on")
    if run["needs"] and not (args.log.parent / run["needs"]).exists():
        raise Stop(f"{run['needs']} is gone from {args.log.parent}: run {args.run} only after "
                   "run 1, from the same run directory")
    lock = args.log.parent / run["lock"]
    with open(lock, "x") as f:       # raises FileExistsError: never a second attempt
        f.write(json.dumps({"time": round(time.time(), 3), "receipt": args.log.name,
                            "run": args.run, "image_sha256": run["sha256"]}) + "\n")
    result["lock"] = str(lock)
    mem_write(link, RAM_BASE, image)
    back = mem_read(link, RAM_BASE, len(image))
    result["readback"] = "equal" if back == image else "MISMATCH"
    print(f"loaded {len(image)} B at {RAM_BASE:#x}; read-back {result['readback']}")
    if back != image:
        raise Stop("image read-back mismatch; not jumping")
    reply = link.request(f"jump {RAM_BASE:#x} {JUMP_ARG:#x}", TIMEOUT_JUMP)
    code, verdict = jump_verdict(reply)
    result.update(jump_reply=reply, verdict=verdict)
    print(verdict)
    return code


def decode_crumbs(data):
    """The twelve words by name, with the stage and the panel result spelled out."""
    words = [int.from_bytes(data[i:i + 4], "little") for i in range(0, CRUMBS_BYTES, 4)]
    out = dict(zip(CRUMB_NAMES, words))
    out["valid"] = words[0] == CRUMBS_MAGIC and words[11] == CRUMBS_MAGIC ^ 0xFFFFFFFF
    stage = words[1] & 0xFF
    out["stage_name"] = STAGES[stage] if 0 < stage < len(STAGES) else f"unknown {stage}"
    out["timer_dead"] = bool(words[1] & TIMER_DEAD_FLAG)
    out["panel_name"] = PANEL_RESULTS.get(words[7], f"unknown {words[7]}")
    return out


def cmd_crumbs(link, args, result):
    st = read_status(link)
    result["status"] = st
    require_uboot(st)
    if st["loader"] or st["loader_running"]:
        raise Stop(f"the transporter holds or runs the flash loader ({st}). The loader is "
                   f"loaded at {RAM_BASE:#x} over the breadcrumbs, so they cannot be read in "
                   "this ROM session: power off")
    line = f"memr {CRUMBS_ADDR:#x} {CRUMBS_BYTES}"
    reply = link.request(line, TIMEOUT_MEM)
    if reply != f"DATA {CRUMBS_BYTES}":
        raise Stop(f"{line}: {reply!r}. Nothing was read and no crumbs lock was taken. If the "
                   "console showed no new `UBOOT READY` after the jump, the transporter's "
                   "mount may be stale: docs/19 section 7.6, then run crumbs again")
    lock = args.log.parent / CRUMBS_LOCK
    with open(lock, "x") as f:       # raises FileExistsError: the read happened before
        f.write(json.dumps({"time": round(time.time(), 3), "receipt": args.log.name,
                            "read": line}) + "\n")
    result["lock"] = str(lock)
    data = link.recv_bytes(CRUMBS_BYTES, TIMEOUT_MEM)
    result["crumbs_hex"] = data.hex()            # raw, before any check or decoding
    link._log("crumbs-raw", hex=data.hex())
    end = link.recv_line(TIMEOUT_MEM)
    if len(data) != CRUMBS_BYTES or end != f"END {crc32(data):08X}":
        raise Stop(f"{line}: transfer check failed ({end!r}); the raw bytes are in the receipt")
    crumbs = decode_crumbs(data)
    result["crumbs"] = crumbs
    for name in CRUMB_NAMES:
        print(f"{name:16} {crumbs[name]:#010x} {crumbs[name]}")
    print(f"stage {crumbs['stage_name']}, timer_dead {crumbs['timer_dead']}, "
          f"panel {crumbs['panel_name']}, valid {crumbs['valid']}")
    if not crumbs["valid"]:
        result["verdict"] = ("breadcrumbs read, but the magic or its complement does not match: "
                             "they did not survive, or were never written. Power off")
        print(result["verdict"])
        return 3
    result["verdict"] = f"breadcrumbs read and valid; last stage {crumbs['stage_name']}"
    print(result["verdict"])
    return 0


# -- Offline subcommands ------------------------------------------------------

def compare_images(ref, data):
    sectors = [a for a in range(0, max(len(ref), len(data)), SECTOR)
               if ref[a:a + SECTOR] != data[a:a + SECTOR]]
    return {
        "identical": ref == data and len(data) == FLASH_SIZE,
        "sizes": [len(ref), len(data)],
        "sha256": [hashlib.sha256(ref).hexdigest(), hashlib.sha256(data).hexdigest()],
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
    if args.image:
        digest = sha256_file(args.image)
        run = next((n for n, r in RUNS.items() if r["sha256"] == digest), 1)
        admit_image(args.image, args.sha256, run)
        print(f"image {args.image}: approved run {run} image ({RUNS[run]['build_id']}), "
              f"{APPROVED_IMAGE_BYTES} B, {digest}, ends at "
              f"{RAM_BASE + APPROVED_IMAGE_BYTES:#010x}")
    if args.loader:
        admit_loader(args.loader)
        print(f"loader {args.loader}: wl82loader.bin, {LOADER_BYTES} B, {LOADER_SHA256}")
    print(f"tool {Path(__file__).name}: sha256 {sha256_file(__file__)}")
    return 0


# -- Main --------------------------------------------------------------------

# Upstream ramrun options that M5 and m5p2 refuse by name (M5 note section 4.2).
RAMRUN_REFUSED_FLAGS = {
    "--loader": "the loader is never uploaded in a RAM-run session",
    "--clear": "writes RAM outside the image",
    "--poke": "writes RAM outside the image",
    "--read": "would send memr after the jump",
    "--addr": f"the address is fixed at {RAM_BASE:#010x}",
    "--arg": f"the jump argument is fixed at {JUMP_ARG}",
}

PORT_COMMANDS = {"status": cmd_status, "rekey": cmd_rekey, "info": cmd_info,
                 "dump": cmd_dump, "ramrun": cmd_ramrun, "crumbs": cmd_crumbs}


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="the transporter's data port, "
                    "/dev/serial/by-id/usb-kurogedelic_FM-1_Transporter_<serial>-if02")
    ap.add_argument("--log", type=Path, help="new JSONL receipt file (required with --port)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="read the transporter's status (read-only)")
    r = sub.add_parser("rekey", help="reboot the transporter into USB_KEY; FM-1 must be off")
    r.add_argument("--fm1-is-off", action="store_true",
                   help="confirm the FM-1 is switched off (checked against status too)")
    i = sub.add_parser("info", help="chip key and flash id through the loader")
    i.add_argument("--loader", required=True, help="wl82loader.bin (docs/17 section 1)")
    d = sub.add_parser("dump", help="read the whole 1 MiB flash through the loader")
    d.add_argument("out", type=Path, help="new file for the dump")
    d.add_argument("--loader", required=True, help="wl82loader.bin (docs/17 section 1)")
    d.add_argument("--compare", type=Path, help="earlier dump that must be byte-identical")
    m = sub.add_parser("ramrun", help="load run 1's or run 2's approved image at 0x01C02000 "
                       "and jump once")
    m.add_argument("image", type=Path)
    m.add_argument("--run", type=int, required=True, choices=sorted(RUNS),
                   help="1: m5p2.bin; 2: m5p2-mailbox.bin, only after run 1")
    m.add_argument("--sha256", required=True, help="must be that run's pinned SHA-256")
    sub.add_parser("crumbs", help="after run 2: read the 48 B of breadcrumbs from the ROM, once")
    p = sub.add_parser("preflight", help="check image, loader and this tool offline")
    p.add_argument("--image", type=Path)
    p.add_argument("--sha256")
    p.add_argument("--loader", type=Path)
    c = sub.add_parser("compare", help="two dumps must be byte-identical (offline)")
    c.add_argument("a", type=Path)
    c.add_argument("b", type=Path)
    return ap


def admit(args, environ):
    """Every check that needs no port. Raises Refused."""
    if args.cmd == "ramrun":
        if environ.get("FM1T_LOADER"):
            raise Refused("FM1T_LOADER is set in the environment; unset it: the loader is "
                          "never uploaded in a RAM-run session")
        args.image_bytes = admit_image(args.image, args.sha256, args.run)
        here = args.log.parent if args.log else None
        if here and (here / RUNS[args.run]["lock"]).exists():
            raise Refused(f"{here / RUNS[args.run]['lock']} exists: run {args.run} was already "
                          "attempted from this run directory. There is no second attempt; "
                          "another run needs a new owner approval")
        for other in OTHER_RAMRUN_LOCKS:
            if here and (here / other).exists():
                raise Refused(f"{here / other} exists: this is M5's or M6's run directory; "
                              "run m5p2 from a new one (docs/19 section 7)")
        needs = RUNS[args.run]["needs"]
        if here and needs and not (here / needs).exists():
            raise Refused(f"no {needs} in {here}: run {args.run} is allowed only after run 1, "
                          "from the same run directory")
        if here and args.run == 1 and (here / RUNS[2]["lock"]).exists():
            raise Refused(f"{here / RUNS[2]['lock']} exists: run 1 never follows run 2")
    if args.cmd == "crumbs":
        if environ.get("FM1T_LOADER"):
            raise Refused("FM1T_LOADER is set in the environment; unset it: the loader would "
                          "overwrite the breadcrumbs")
        here = args.log.parent if args.log else None
        if here and not (here / RUNS[2]["lock"]).exists():
            raise Refused(f"no {RUNS[2]['lock']} in {here}: crumbs reads run 2's breadcrumbs "
                          "and runs only in run 2's directory")
        if here and (here / CRUMBS_LOCK).exists():
            raise Refused(f"{here / CRUMBS_LOCK} exists: the breadcrumbs were already read "
                          "from this run directory")
    if args.cmd in ("info", "dump"):
        args.loader_bytes = admit_loader(args.loader)
    if args.cmd == "dump":
        if args.out.exists():
            raise Refused(f"{args.out} exists; dumps are never overwritten")
        if args.compare and not args.compare.is_file():
            raise Refused(f"{args.compare}: no such reference dump")
    if args.cmd == "rekey" and not args.fm1_is_off:
        raise Refused("rekey needs --fm1-is-off: switch the FM-1 off and check the switch first")
    check_port_path(args.port)
    if not args.log:
        raise Refused("--log is required: every line sent and received is recorded")
    if args.log.exists():
        raise Refused(f"{args.log} exists; each step gets a new receipt")


def main(argv=None, environ=None, opener=None):
    environ = os.environ if environ is None else environ
    opener = opener or open_port
    ap = build_parser()
    argv = list(sys.argv[1:] if argv is None else argv)
    if "ramrun" in argv:
        for arg in argv:
            flag = arg.split("=", 1)[0]
            if flag in RAMRUN_REFUSED_FLAGS:
                print(f"fm1t_m5p2: refused: ramrun {flag}: {RAMRUN_REFUSED_FLAGS[flag]}",
                      file=sys.stderr)
                return 1
    args = ap.parse_args(argv)
    try:
        if args.cmd == "compare":
            return cmd_compare(args)
        if args.cmd == "preflight":
            return cmd_preflight(args)
        admit(args, environ)
    except Refused as exc:
        print(f"fm1t_m5p2: {exc}", file=sys.stderr)
        return 1

    result = {}
    code = 0
    with open(args.log, "x") as fp:
        def log(event, **fields):
            fp.write(json.dumps({"time": round(time.time(), 3), "event": event, **fields}) + "\n")
            fp.flush()

        log("start", tool=Path(__file__).name, tool_sha256=sha256_file(__file__),
            argv=list(argv), cmd=args.cmd, port=args.port,
            image_sha256=getattr(args, "image_bytes", None)
            and hashlib.sha256(args.image_bytes).hexdigest(),
            build_id=RUNS[args.run]["build_id"] if args.cmd == "ramrun" else None,
            run=getattr(args, "run", None))
        port = None
        try:
            port = opener(args.port)
            link = Link(port, args.cmd, log, image=getattr(args, "image_bytes", None),
                        run=getattr(args, "run", None))
            handshake(link)
            code = PORT_COMMANDS[args.cmd](link, args, result) or 0
        except Refused as exc:
            # The port is open, so something may have been sent: a stop, not exit 1.
            code, result["verdict"] = 3, f"STOP: refused mid-session: {exc}"
        except FileExistsError as exc:
            why = ("this run or read was already attempted from this run directory; no second "
                   "attempt" if str(exc.filename).endswith(RAMRUN_LOCKS + (CRUMBS_LOCK,))
                   else "never overwritten")
            code, result["verdict"] = 3, f"STOP: {exc.filename} exists: {why}"
        except Stop as exc:
            code, result["verdict"] = 3, f"STOP: {exc}"
        except Exception as exc:  # noqa: BLE001  (record it, then stop)
            code, result["verdict"] = 3, f"STOP: {type(exc).__name__}: {exc}"
        finally:
            if port is not None:
                try:
                    port.close()
                except Exception:  # noqa: BLE001
                    pass
            log("end", exit=code, **result)
    if code:
        print(f"fm1t_m5p2: {result.get('verdict')}", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
