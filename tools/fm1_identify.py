#!/usr/bin/env python3
"""Read-only identity query for an M-VAVE FM-1 over USB-MIDI (macOS, Windows, Linux).

Sends the ten-byte SysEx identity request the official updater issues at
start-up, waits for the reply, prints and decodes it. **This is the only
message the tool ever sends.** No upgrade command, no vendor "syscmd" frames,
nothing that writes to the device. See docs/03 §2 and docs/09 §3.

    host -> device   F0 00 32 45 00 00 00 40 7F F7
    device -> host   F0 00 32 45 58 01 00 00 23 4D 5A 44 79 ... F7   (41 bytes)

Everything between F0 and F7 is a 7-bit packed bitstream (the `00 32 45 58`
header included); unpacked it is a 34-byte JieLi "ID block" (`00 59 11`, length 27, checksum) holding the model name and a
version field. The decoder mirrors the official updater's parser as
reverse-engineered by AL-255 (FM-1-RE, `tools/fm1_ota.py`,
`parse_handshake_identity`), credited here.

Usage:
    python tools/fm1_identify.py                       # first port whose name contains "FM-1"
    python tools/fm1_identify.py --list                # show MIDI ports and exit
    python tools/fm1_identify.py --save notes/id.syx   # also keep the raw reply
    python tools/fm1_identify.py --decode-file id.syx  # decode a saved reply, no device access

Requires mido and python-rtmidi (docs/09 §0) unless --decode-file is used.
"""

import argparse
import re
import sys
import time

QUERY = [0x00, 0x32, 0x45, 0x00, 0x00, 0x00, 0x40, 0x7F]   # mido adds F0 ... F7


def hexs(data):
    return " ".join(f"{b:02X}" for b in data)


def ascii_view(data):
    return "".join(chr(b) if 0x20 <= b < 0x7F else "." for b in data)


def unpack7(wire, *, complete=False):
    """7-bit wire bytes -> 8-bit data; LSB-first continuous bitstream (docs/03 §3)."""
    out, acc, nbits = bytearray(), 0, 0
    for b in wire:
        if not 0 <= b < 0x80:
            raise ValueError("packed MIDI data is not 7-bit clean")
        acc |= b << nbits
        nbits += 7
        while nbits >= 8:
            out.append(acc & 0xFF)
            acc >>= 8
            nbits -= 8
    if complete and acc:
        raise ValueError("nonzero padding in packed MIDI data")
    return bytes(out)


def decode(reply):
    """Decode a raw F0..F7 identity reply into model/version (after AL-255)."""
    info = {}
    if len(reply) < 4 or reply[0] != 0xF0 or reply[-1] != 0xF7:
        info["error"] = "not a complete SysEx message"
        return info
    info["sysex_header"] = hexs(reply[:5]) + ("  (packed form of the 00 59 11 ID block)" if reply[1:5] == b"\x00\x32\x45\x58" else "")
    try:
        d = unpack7(reply[1:-1], complete=True)  # header is part of the packed stream
    except ValueError as exc:
        info["error"] = str(exc)
        return info
    info["id_block"] = f"{len(d)} bytes: {hexs(d)}"
    if len(d) != 34 or d[:3] != b"\x00\x59\x11":
        info["error"] = "unexpected ID block header (want 00 59 11, 34 bytes)"
        return info
    body_len = int.from_bytes(d[3:6], "little")
    info["body_len"] = body_len
    info["checksum_ok"] = d[-1] == ((~sum(d[6:-1])) & 0xFF)
    if body_len != 27 or len(reply) != 41:
        info["error"] = "unexpected ID block length (want 27 body bytes, 41 wire bytes)"
        return info
    if not info["checksum_ok"]:
        info["error"] = "ID block checksum mismatch"
        return info
    if not re.fullmatch(rb"[A-Za-z0-9-]+_[0-9]{3}\x00*", d[6:-1]):
        info["error"] = "unexpected identity field (want MODEL_NNN with zero padding)"
        return info
    plain = d[6:-1]
    info["plain_field"] = ascii_view(plain)
    sep = plain.find(b"_")
    if sep < 0:
        info["error"] = "no '_' separator in identity field"
        return info
    info["model"] = plain[:sep].decode("ascii", "replace")
    # On hardware (FM-1_015, 2026-09-06) the plain field carries the whole
    # "MODEL_NNN" identity, so that is the primary decode.
    m = re.match(rb"[0-9]+", plain[sep + 1:])
    if m:
        info["version"] = int(m.group(0), 10)
        info["identity"] = f"{info['model']}_{info['version']:03d}"
    else:
        info["error"] = "no decimal version after the separator"
    # AL-255's mirror of the updater's parser derives the version from a second
    # field (bytes 14..33 plus ASCII '0'); on the real reply that gives 0, so it
    # is reported only for comparison.
    encoded = bytes((b + ord("0")) & 0xFF for b in d[14:34])
    m2 = re.match(rb"[0-9]+", encoded[sep + 1:])
    info["al255_second_field"] = f"{ascii_view(encoded)} -> version {int(m2.group(0), 10) if m2 else None}"
    return info


def report(replies):
    for i, r in enumerate(replies):
        print(f"reply {i}: {len(r)} bytes")
        print("  hex  :", hexs(r))
        print("  ascii:", ascii_view(r))
        for k, v in decode(r).items():
            print(f"  {k}: {v}")


def query_device(port, timeout):
    import mido
    ins, outs = mido.get_input_names(), mido.get_output_names()
    in_hits = [n for n in ins if port.lower() in n.lower()]
    out_hits = [n for n in outs if port.lower() in n.lower()]
    if not in_hits or not out_hits:
        print(f"no MIDI port matching {port!r}; inputs={ins} outputs={outs}")
        return None
    replies = []
    with mido.open_input(in_hits[0]) as inp, mido.open_output(out_hits[0]) as out:
        for _ in inp.iter_pending():          # drop anything stale
            pass
        out.send(mido.Message("sysex", data=QUERY))
        print(f"port : in={in_hits[0]!r} out={out_hits[0]!r}")
        print(f"sent : F0 {hexs(QUERY)} F7")
        t0, first = time.monotonic(), None
        while time.monotonic() - t0 < timeout:
            for msg in inp.iter_pending():
                if msg.type == "sysex":
                    replies.append(bytes([0xF0, *msg.data, 0xF7]))
                    first = first or time.monotonic()
                else:
                    print("other:", msg)
            if first and time.monotonic() - first > 0.3:   # grace period for multi-part replies
                break
            time.sleep(0.02)
    return replies


def main():
    ap = argparse.ArgumentParser(description="Read-only FM-1 identity query")
    ap.add_argument("--port", default="FM-1", help="substring of the MIDI port name (default: FM-1)")
    ap.add_argument("--timeout", type=float, default=3.0, help="seconds to wait for a reply")
    ap.add_argument("--save", help="write the raw reply bytes (F0..F7) to this file")
    ap.add_argument("--list", action="store_true", help="list MIDI ports and exit")
    ap.add_argument("--decode-file", help="decode a saved reply instead of querying the device")
    args = ap.parse_args()

    if args.decode_file:
        raw = open(args.decode_file, "rb").read()
        replies, offset = [], 0
        while offset < len(raw):
            end = raw.find(b"\xF7", offset)
            if raw[offset] != 0xF0 or end < 0:
                print("error: capture contains incomplete SysEx or bytes outside a message")
                return 1
            replies.append(raw[offset:end + 1])
            offset = end + 1
        report(replies)
        return 0 if replies and all("error" not in decode(r) for r in replies) else 1
    if args.list:
        import mido
        print("inputs :", mido.get_input_names())
        print("outputs:", mido.get_output_names())
        return 0

    replies = query_device(args.port, args.timeout)
    if replies is None:
        return 1
    if not replies:
        print(f"no SysEx reply within {args.timeout}s")
        return 2
    report(replies)
    if args.save:
        with open(args.save, "wb") as fh:
            for r in replies:
                fh.write(r)
        print(f"saved {sum(len(r) for r in replies)} bytes to {args.save}")
    return 0 if all("error" not in decode(r) for r in replies) else 1


if __name__ == "__main__":
    sys.exit(main())
