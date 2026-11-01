#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fixed return-r01 host for one reviewed offline strict Pico image.

No discovery, generic transporter, retry, recovery or post-call commands.
An exact reply is transport evidence only, never flashed-image/ROM attestation.
The image pin does not authorize device traffic or qualify target execution.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import signal
import stat
import threading
import time

ROOT = Path(__file__).resolve().parents[2]
SOURCE_BASE = "a7a1c310a346dcad03892557c4405470576ed00c"
CONTRACT_SHA256 = "6f5b203a0b07ecba8c16f392c4e3aa0f2122431d2ee9a8f11a912829e40ded09"
RETURN_MANIFEST_SHA256 = "e03ef5e05b1b8161bde6efc1fe4507a6bc2a743d5647f65f2fcd6ad79716800c"
PAYLOAD_SHA256 = "898b7737d69e351e54b406aebda27652c04413344d19dfb698a8642e33b698f9"
BUILD_ID = "rr01-pico-v1"
USB = dict(vid=0x2E8A, pid=0x000A, product="Lunar fixed ROM return-r01",
           data_interface=2, data_interface_string="Return-r01 fixed data")
# Exact firmware/rom-witness-return/reviewed-pico-image.json bytes, derived from
# the independently reviewed ff1fed64 offline build. Not flashed attestation.
# No CLI/environment option can populate or bypass this trust anchor.
REVIEWED_IMAGE_MANIFEST_SHA256 = "84f294a2140e4425f764e5597c9618d9c571f4952b3d2baed3c78938d30dc5a7"
IO_SECONDS = 5.0
READY_SECONDS = 10.0
MAX_LINE = 96
MAX_MANIFEST = 8192
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_READY = re.compile(rb"OK rr01-ready v=1 build=rr01-pico-v1 mount=([1-9][0-9]{0,9})\n\Z")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def invalid_constant(value):
        raise ValueError("nonfinite JSON")
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def _open_directory(path):
    """Walk from / using retained directory fds; never resolve then reopen.

    The namespace must be stable and controlled by root/the operator. This
    prevents alias traversal, not deliberate same-UID replacement of records.
    """
    path = Path(path).absolute()
    if path.anchor != "/" or ".." in path.parts:
        raise ValueError("unambiguous absolute directory path required")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for component in (None, *path.parts[1:]):
            if component is not None:
                child = os.open(component, flags, dir_fd=fd)
                previous, fd = fd, child
                os.close(previous)
            info = os.fstat(fd)
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.geteuid())
                    or stat.S_IMODE(info.st_mode) & 0o022):
                raise ValueError("root/operator-owned non-writable ancestors required")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_file(path, limit):
    path = Path(path).absolute()
    parent_fd = _open_directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            raise ValueError("bounded regular input file required")
        data = bytearray()
        while len(data) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(data)))
            if not part:
                break
            data.extend(part)
        if len(data) > limit or len(data) != info.st_size:
            raise ValueError("input size changed or exceeds bound")
        return bytes(data)
    finally:
        os.close(fd)


def _deadline_support():
    if (os.name != "posix" or not hasattr(signal, "setitimer")
            or threading.current_thread() is not threading.main_thread()):
        raise ValueError("POSIX main-thread deadline required")
    if signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("existing real-time alarm conflicts with deadline")
    if not hasattr(signal, "pthread_sigmask") or signal.SIGALRM in signal.pthread_sigmask(signal.SIG_BLOCK, []):
        raise ValueError("SIGALRM must already be unblocked")


@contextmanager
def _deadline(seconds):
    """Cover open/write/tcdrain/read; do not take over an existing alarm."""
    _deadline_support()
    handler = signal.getsignal(signal.SIGALRM)
    timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(signum, frame):
        raise TimeoutError("fixed transport phase expired")
    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, handler)
        signal.setitimer(signal.ITIMER_REAL, *timer)


def _preflight(payload_path, image_manifest, *, _reviewed_image_pin):
    # Refuse before opening even an input file when no reviewed image exists.
    if (type(_reviewed_image_pin) is not str or not _HEX.fullmatch(_reviewed_image_pin)):
        raise ValueError("reviewed strict UF2 manifest pin is UNSET")
    _deadline_support()
    raw = _read_file(image_manifest, MAX_MANIFEST)
    if _sha(raw) != _reviewed_image_pin:
        raise ValueError("reviewed image manifest digest mismatch")
    image = _json(raw)
    fixed = dict(schema=1, candidate="return-r01", source_base=SOURCE_BASE,
                 contract_sha256=CONTRACT_SHA256,
                 return_payload_manifest_sha256=RETURN_MANIFEST_SHA256,
                 payload_sha256=PAYLOAD_SHA256, board="pico2_w", build_id=BUILD_ID,
                 upstream_commit="a7fb5e8ac692c528f8ed29e325911a3f4b8111d6", usb=USB)
    variable = {"strict_source_commit", "pico_build_manifest_sha256", "recipe_sha256", "patch_sha256", "uf2"}
    if not isinstance(image, dict) or set(image) != set(fixed) | variable:
        raise ValueError("unsupported reviewed image manifest schema")
    for key, value in fixed.items():
        # JSON spelling/types must agree (True is not an integer identity).
        if json.dumps(image[key], sort_keys=True) != json.dumps(value, sort_keys=True):
            raise ValueError("reviewed image field mismatch: " + key)
    if (type(image["strict_source_commit"]) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", image["strict_source_commit"])
            or any(type(image[k]) is not str or not _HEX.fullmatch(image[k])
                   for k in ("recipe_sha256", "pico_build_manifest_sha256"))):
        raise ValueError("full strict source and recipe hashes required")
    patches = image["patch_sha256"]
    if (not isinstance(patches, dict) or set(patches) != {"0001", "0002", "0003"}
            or any(type(v) is not str or not _HEX.fullmatch(v) for v in patches.values())
            or patches["0001"] != "b67768211e058c1f558720c7205295e6ec09dc3318f6491eb73566e2086a163f"
            or patches["0002"] != "9b4565fbc5a27d3034e13fb7ddcc7dbdcb7d1f60427424656da33abf9617d045"):
        raise ValueError("fixed strict patch inventory required")
    uf2 = image["uf2"]
    if (not isinstance(uf2, dict) or set(uf2) != {"sha256", "bytes"}
            or type(uf2["sha256"]) is not str or not _HEX.fullmatch(uf2["sha256"])
            or type(uf2["bytes"]) is not int or not 0 < uf2["bytes"] <= 16 * 1024 * 1024):
        raise ValueError("bounded final UF2 identity required")
    manifest = _read_file(ROOT / "firmware/rom-witness-return/manifest.json", MAX_MANIFEST)
    if _sha(manifest) != RETURN_MANIFEST_SHA256:
        raise ValueError("return source manifest mismatch")
    for name, expected in _json(manifest)["sources"].items():
        if _sha(_read_file(ROOT / name, 4 * 1024 * 1024)) != expected:
            raise ValueError("return source mismatch")
    payload = _read_file(payload_path, 512)
    if payload != b"\x80\x00" + bytes(510) or _sha(payload) != PAYLOAD_SHA256:
        raise ValueError("fixed return payload required")
    return payload, image


class _Campaign:
    """Never resume/overwrite/remove records in a stable owned namespace."""
    def __init__(self, path):
        self.fd = None
        path = Path(path).absolute()
        parent = path.parent
        parent_fd = _open_directory(parent)
        try:
            info = os.fstat(parent_fd)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise ValueError("owner-only campaign parent required")
            os.mkdir(path.name, mode=0o700, dir_fd=parent_fd)
            os.fsync(parent_fd)
            self.fd = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            info = os.fstat(self.fd)
            if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise ValueError("private owned campaign required")
        except BaseException:
            self.close()
            raise
        finally:
            os.close(parent_fd)

    def record(self, name, value):
        raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
        if len(raw) > MAX_MANIFEST or name not in {"campaign.json", "upload_attempted", "jump_intent_consumed", "outcome.json"}:
            raise ValueError("bounded fixed receipt required")
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=self.fd)
        try:
            position = 0
            while position < len(raw):
                count = os.write(fd, raw[position:])
                if not count:
                    raise OSError("short persistence write")
                position += count
            os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(self.fd)

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def _open_serial(port):
    # Existing dependency, imported only after all preflight and persistence.
    import serial
    return serial.Serial(port=port, baudrate=115200, timeout=0.05, write_timeout=IO_SECONDS,
                         xonxoff=False, rtscts=False, dsrdtr=False, exclusive=True)


def _exchange(port, command, seconds):
    with _deadline(seconds):
        if port.in_waiting:
            raise ValueError("unsolicited serial bytes")
        if port.write(command) != len(command):
            raise OSError("short serial write")
        port.flush()
        reply = bytearray()
        while b"\n" not in reply:
            part = port.read(MAX_LINE + 1 - len(reply))
            if type(part) is not bytes:
                raise ValueError("invalid serial read")
            reply.extend(part)
            if len(reply) > MAX_LINE:
                raise ValueError("overlong reply")
        if reply.count(b"\n") != 1 or reply[-1] != 10 or port.in_waiting:
            raise ValueError("extra serial reply bytes")
        return bytes(reply)


def _run_once(*, port, campaign, payload_path, image_manifest,
              _reviewed_image_pin=REVIEWED_IMAGE_MANIFEST_SHA256, _serial_factory=_open_serial):
    """Private test seam permits fixture pins/fake serial, never a CLI bypass."""
    payload, image = _preflight(payload_path, image_manifest, _reviewed_image_pin=_reviewed_image_pin)
    if type(port) is not str or not port.startswith("/dev/") or len(port) > 4096 or any(c.isspace() or ord(c) < 32 for c in port):
        raise ValueError("one explicit POSIX data port required")
    storage = _Campaign(campaign)
    serial_port = None
    call_intent = False
    phase = "campaign"
    result = dict(schema=1, status="refused", reason="not_started", hardware_admitted=False,
                  flashed_image_verified=False, rom_abi_qualified=False, fetch_coherence_qualified=False,
                  watchdog_lease_qualified=False, installable=False, transport_return_evidence=False)
    try:
        storage.record("campaign.json", dict(schema=1, id=secrets.token_hex(16),
                       created_ns=time.time_ns(), source_base=SOURCE_BASE, contract_sha256=CONTRACT_SHA256,
                       payload_sha256=PAYLOAD_SHA256, reviewed_image_manifest_sha256=_reviewed_image_pin,
                       uf2=image["uf2"], build_id=BUILD_ID, flashed_image_verified=False))
        try:
            phase = "open"
            with _deadline(IO_SECONDS):
                serial_port = _serial_factory(port)
            phase = "ready"
            reply = _exchange(serial_port, b"rr01-ready\n", READY_SECONDS)
            match = _READY.fullmatch(reply)
            if match is None or int(match[1]) > 0xFFFFFFFF:
                raise ValueError("fixed ready identity required")
            mount = int(match[1])
            result["mount"] = mount
            phase = "upload_persistence"
            storage.record("upload_attempted", dict(schema=1, mount=mount, time_ns=time.time_ns()))
            phase = "upload"
            reply = _exchange(serial_port, b"rr01-upload\n" + payload, IO_SECONDS)
            if reply != f"OK rr01-upload mount={mount}\n".encode():
                raise ValueError("fixed upload completion required")
            phase = "call_persistence"
            storage.record("jump_intent_consumed", dict(schema=1, mount=mount, time_ns=time.time_ns()))
            call_intent = True
            phase = "call"
            reply = _exchange(serial_port, b"rr01-call\n", IO_SECONDS)
            if reply != f"OK rr01-call mount={mount}\n".encode():
                raise ValueError("fixed call completion required")
            result.update(status="bounded_call_return_evidence", reason="matching_transport_reply",
                          transport_return_evidence=True)
        except Exception as exc:
            result.update(status="inconclusive" if call_intent else "refused", reason=type(exc).__name__)
        finally:
            if serial_port is not None:
                try:
                    with _deadline(IO_SECONDS):
                        serial_port.close()
                except Exception as exc:
                    result.update(status="inconclusive" if call_intent else "refused",
                                  reason="close_" + type(exc).__name__, transport_return_evidence=False)
        result["phase"] = phase
        storage.record("outcome.json", result)
        return result
    finally:
        storage.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True, help="explicit strict CDC interface-02 data port")
    parser.add_argument("--campaign", required=True, type=Path, help="new directory in private owned parent; retained, never resumed")
    parser.add_argument("--payload", required=True, type=Path, help="exact private 512-byte return-r01 payload")
    parser.add_argument("--reviewed-image-manifest", required=True, type=Path, help="independently reviewed strict UF2 manifest")
    args = parser.parse_args(argv)
    try:
        result = _run_once(port=args.port, campaign=args.campaign, payload_path=args.payload,
                           image_manifest=args.reviewed_image_manifest)
    except (OSError, ValueError, TimeoutError) as exc:
        parser.exit(1, f"rom_return_once: {type(exc).__name__}: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["transport_return_evidence"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
