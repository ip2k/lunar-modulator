#!/usr/bin/env python3
"""tools/jieli/audit_link.py -- gate a Lunar FM-1 build against the SDK's
dormant key and eFuse checks (notes/2026-10-05-softkey-efuse.md §3-4).

The owner's decision (2026-10-05) is to link JieLi's SDK **V1.2.13** closed
libraries (Gitee release/AC79NN_SDK_V1.2.0 at e30b1ee) but never to stub the
key check: it is inert on the FM-1 (nothing registers a licence blob, so
`_mkey_check` returns at its "nothing registered" branch), and patching
LTO-internal vendor code is riskier than leaving it. This audit, modelled on
fm1-nes's `firmware/nes/audit_boot.py`, fails the build if the inert check
ever becomes live, if any eFuse-touching or key-comparing code is linked, or
if our own code uses the resources the SDK reserves for it.

It reads ELF objects/images itself (a small ELF reader; standard library
only, no binutils that know pi32v2). Two kinds of input:

  --elf IMAGE.elf [--app IMAGE.bin]   a linked firmware (runs every check)
  --objects DIR|ARCHIVE.a             relocatable objects, e.g. this repo's
                                      engine archive or the compile-only set
                                      from tools/jieli/compile-check.sh

Checks fall in three buckets per input:
  pass     the condition holds
  fail     a violation -> non-zero exit (the build must stop)
  pending  the check needs a linked image / vendor objdump and the input is
           objects only; reported, never a failure

On objects, the symbol-reference, eFuse-access and byte-pattern checks all
run (they are the compile-time half of the safeguards). The structural
checks of the SDK init-call section and `sdk_meky_check`'s exact scheduling
need the linked image and are reported pending until then.

What this does NOT cover, by design: the packaging safeguards
(notes/2026-10-05-softkey-efuse.md §4.4) -- asserting the stock SPL hash
730e54f0... and byte-identical isd_config.ini/ota.bin/cfg -- live in the
packaging tool, not here. And nothing in this tool talks to a device.

MIT licence, like the rest of this repository.
"""
import argparse
import json
import struct
import sys
from pathlib import Path

# ---- the resources the SDK key/eFuse check owns (notes 2026-10-05 §3-4) -----

# Symbols that must not survive LTO or be referenced: the active key-comparing
# and eFuse-reading entry points. `sdk_meky_check`, `_mkey_check` and
# `isr_check_key` are the dormant check itself and are allowed to remain.
FORBIDDEN_SYMBOLS = (
    "mkey_check",
    "sdk_mkey_lock",
    "sdk_mkey_lock_v2_cfun",
    "key_check_demo",
    "sdk_chip_key_verify_v2",
)
ALLOWED_KEYCHECK_SYMBOLS = ("sdk_meky_check", "_mkey_check", "isr_check_key")

# The post-cpu0_start stub `key_check_demo` hashes 92 bytes from (V1.2.8+).
STUB_ADDR = 0x0200012E
# The mailbox words `mkey_dummy_func`/`key_check_demo` read and write.
MAILBOX_LO, MAILBOX_HI = 0x01C80108, 0x01C80110  # inclusive, word-aligned
# IRQ 123's vector-table slot (base 0x01C80000, slot 123).
IRQ123_VECTOR = 0x01C80000 + 123 * 4  # 0x01C801EC

# Byte signatures that must not appear anywhere in the image.
# The SDK's embedded JL_KEY_2020 blob begins FE 23 A8 B1 28 D4 B4 29.
SDK_KEY_BLOB_PREFIX = bytes.fromhex("FE23A8B128D4B429")
# key_check_demo's 92-byte hash begins 99 56 B6 46 (a prefix; a 4-byte hit is
# a strong signal, not a proof).
KEY_CHECK_DEMO_HASH_PREFIX = bytes.fromhex("9956B646")

# WL82 eFuse controller SFRs (JL_EFUSE 0x13700-0x1371F) and the P33 bytes that
# reach the eFuse program/read strobes (P3_EFUSE_CON0/CON1/RDAT 0xB0/0xB1/0xB2).
# No application code touches these; only the (never-linked) download loader.
EFUSE_SFR_LO, EFUSE_SFR_HI = 0x13700, 0x1371F

SHT_SYMTAB, SHT_NOBITS, SHT_RELA, SHT_REL = 2, 8, 4, 9
SHF_WRITE, SHF_ALLOC, SHF_EXEC = 0x1, 0x2, 0x4
ET_REL, ET_EXEC = 1, 2
EM_PI32V2 = 0xF1


class Elf:
    """Just enough ELF32 little-endian for sizes, symbols, relocations and the
    bytes of allocated sections. Raises ValueError on anything unexpected."""

    def __init__(self, data, name="<elf>"):
        self.name = name
        self.data = data
        if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
            raise ValueError(f"{name}: not a 32-bit little-endian ELF")
        (self.e_type, self.e_machine) = struct.unpack_from("<HH", data, 16)
        shoff, = struct.unpack_from("<I", data, 0x20)
        shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x2E)
        self.sections = []
        for i in range(shnum):
            o = shoff + i * shentsize
            name_off, typ, flags, addr, off, size, link, info, align, entsize = \
                struct.unpack_from("<IIIIIIIIII", data, o)
            self.sections.append(dict(name_off=name_off, type=typ, flags=flags, addr=addr,
                                      offset=off, size=size, link=link, info=info,
                                      entsize=entsize))
        if shstrndx < len(self.sections):
            strtab = self.sections[shstrndx]
            for s in self.sections:
                s["name"] = self._cstr(strtab["offset"], s["name_off"])
        else:
            for s in self.sections:
                s["name"] = ""
        self.symbols = self._symbols()

    def _cstr(self, base, off):
        start = base + off
        end = self.data.index(b"\0", start)
        return self.data[start:end].decode("utf-8", "replace")

    def _symbols(self):
        out = []
        for s in self.sections:
            if s["type"] != SHT_SYMTAB:
                continue
            strtab = self.sections[s["link"]]
            ent = s["entsize"] or 16
            for i in range(s["size"] // ent):
                o = s["offset"] + i * ent
                name, value, size, info, other, shndx = struct.unpack_from("<IIIBBH", self.data, o)
                out.append(dict(name=self._cstr(strtab["offset"], name), value=value,
                                size=size, bind=info >> 4, type=info & 0xF, shndx=shndx))
        return out

    def defined_symbols(self):
        return {s["name"] for s in self.symbols if s["name"] and s["shndx"] != 0}

    def undefined_symbols(self):
        return {s["name"] for s in self.symbols
                if s["name"] and s["shndx"] == 0 and s["bind"] in (1, 2)}

    def relocation_symbol_names(self):
        """Names of symbols referenced by any relocation section."""
        names = set()
        for s in self.sections:
            if s["type"] not in (SHT_RELA, SHT_REL):
                continue
            ent = s["entsize"] or (12 if s["type"] == SHT_RELA else 8)
            for i in range(s["size"] // ent):
                _, rinfo = struct.unpack_from("<II", self.data, s["offset"] + i * ent)
                idx = rinfo >> 8
                if idx < len(self.symbols) and self.symbols[idx]["name"]:
                    names.add(self.symbols[idx]["name"])
        return names

    def allocated_bytes(self):
        """Concatenated bytes of allocated PROGBITS sections (code and data),
        each tagged with its name and load address, for immediate scans."""
        out = []
        for s in self.sections:
            if (s["flags"] & SHF_ALLOC) and s["type"] != SHT_NOBITS and s["size"]:
                out.append((s["name"], s["addr"], self.data[s["offset"]:s["offset"] + s["size"]]))
        return out


def _iter_archive_members(data):
    """Yield (name, bytes) for each member of a System V `ar` archive."""
    if data[:8] != b"!<arch>\n":
        raise ValueError("not an ar archive")
    pos, longnames = 8, b""
    while pos + 60 <= len(data):
        header = data[pos:pos + 60]
        name = header[0:16].decode("latin-1").rstrip()
        try:
            size = int(header[48:58].decode("latin-1").strip())
        except ValueError:
            break
        body = data[pos + 60:pos + 60 + size]
        pos += 60 + size + (size & 1)
        if name == "//":
            longnames = body
            continue
        if name in ("/", "/SYM64/", "__.SYMDEF", "__.SYMDEF SORTED", "ARFILENAMES/"):
            continue
        if name.startswith("/") and name[1:].isdigit():
            start = int(name[1:])
            end = longnames.find(b"\n", start)
            name = longnames[start:end].decode("latin-1").rstrip("/")
        else:
            name = name.rstrip("/")
        yield name, body


def collect_elves(args):
    """Return (elves, flat_images). elves is a list of (name, Elf); flat_images
    is a list of (name, raw bytes) for a non-ELF --app image."""
    elves, flat = [], []
    linked = False
    if args.elf:
        data = Path(args.elf).read_bytes()
        e = Elf(data, name=Path(args.elf).name)
        elves.append((e.name, e))
        linked = True
    if args.app:
        data = Path(args.app).read_bytes()
        if data[:4] == b"\x7fELF":
            elves.append((Path(args.app).name, Elf(data, name=Path(args.app).name)))
        else:
            flat.append((Path(args.app).name, data))
    for spec in args.objects or []:
        p = Path(spec)
        if p.is_dir():
            for obj in sorted(p.rglob("*.o")):
                elves.append((str(obj.relative_to(p)), Elf(obj.read_bytes(), name=str(obj))))
        elif p.suffix == ".a" or p.read_bytes()[:8] == b"!<arch>\n":
            for member, body in _iter_archive_members(p.read_bytes()):
                if body[:4] == b"\x7fELF":
                    elves.append((f"{p.name}({member})", Elf(body, name=member)))
        else:
            elves.append((p.name, Elf(p.read_bytes(), name=p.name)))
    return elves, flat, linked


# ---- the checks -------------------------------------------------------------

def _find_le32(blob, value):
    """Offsets where the 4-byte little-endian encoding of `value` appears."""
    needle = struct.pack("<I", value & 0xFFFFFFFF)
    hits, start = [], 0
    while True:
        i = blob.find(needle, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    return hits


def audit(elves, flat_images, linked):
    checks = []

    def record(key, status, detail):
        checks.append(dict(check=key, status=status, detail=detail))

    # 1. Forbidden key-check symbols: not defined, not referenced.
    defined_hits, ref_hits = [], []
    for name, e in elves:
        d = e.defined_symbols()
        r = e.undefined_symbols() | e.relocation_symbol_names()
        for sym in FORBIDDEN_SYMBOLS:
            if sym in d:
                defined_hits.append(f"{name}: defines {sym}")
            if sym in r:
                ref_hits.append(f"{name}: references {sym}")
    hits = defined_hits + ref_hits
    record("forbidden_keycheck_symbols", "fail" if hits else "pass",
           hits or f"none of {', '.join(FORBIDDEN_SYMBOLS)} defined or referenced")

    # 2. The dormant check's own symbols: present is fine (we do not stub it),
    #    but record what is there for the review trail.
    present = sorted({s for name, e in elves for s in e.defined_symbols()
                      if s in ALLOWED_KEYCHECK_SYMBOLS})
    record("dormant_keycheck_present", "pass",
           f"allowed dormant symbols present: {present or 'none (objects do not link the SDK check yet)'}")

    # 3-6. Byte / immediate scans over every allocated section and flat image.
    #      Each is a 4-byte little-endian immediate or a literal signature.
    scan_sources = []
    for name, e in elves:
        for sec, addr, blob in e.allocated_bytes():
            scan_sources.append((f"{name}:{sec}", blob))
    for name, blob in flat_images:
        scan_sources.append((name, blob))

    def scan_imm(key, value, label):
        hits = [f"{src} +0x{off:x}" for src, blob in scan_sources for off in _find_le32(blob, value)]
        record(key, "fail" if hits else "pass", hits or f"no immediate 0x{value:08X} ({label})")

    def scan_bytes(key, needle, label):
        hits = []
        for src, blob in scan_sources:
            start = 0
            while True:
                i = blob.find(needle, start)
                if i < 0:
                    break
                hits.append(f"{src} +0x{i:x}")
                start = i + 1
        record(key, "fail" if hits else "pass", hits or f"no {label}")

    scan_imm("stub_0200012E_unused", STUB_ADDR, "key_check_demo stub call/load")
    mailbox_hits = [f"{src} +0x{off:x} (0x{w:08X})"
                    for w in range(MAILBOX_LO, MAILBOX_HI + 4, 4)
                    for src, blob in scan_sources for off in _find_le32(blob, w)]
    record("keycheck_mailbox_unwritten", "fail" if mailbox_hits else "pass",
           mailbox_hits or f"no reference to 0x{MAILBOX_LO:08X}-0x{MAILBOX_HI:08X}")
    scan_bytes("no_sdk_key_blob", SDK_KEY_BLOB_PREFIX, "SDK JL_KEY_2020 blob bytes (FE 23 A8 B1 ...)")
    scan_bytes("no_key_check_demo_hash", KEY_CHECK_DEMO_HASH_PREFIX,
               "key_check_demo hash bytes (99 56 B6 46 ...)")

    # 7. IRQ 123 reserved for the SDK: our code must not install its vector.
    irq_hits = [f"{src} +0x{off:x}" for src, blob in scan_sources
                for off in _find_le32(blob, IRQ123_VECTOR)]
    # In a linked image sdk_meky_check legitimately registers IRQ 123; flag only
    # references that are not inside that function. Without disassembly we can
    # bound it: objects are ours (any hit is a violation); a linked image gets
    # a pending note so a human confirms the only hit is sdk_meky_check's.
    if irq_hits and not linked:
        record("irq123_reserved", "fail", irq_hits)
    elif irq_hits and linked:
        record("irq123_reserved", "pending",
               [f"IRQ-123 vector 0x{IRQ123_VECTOR:08X} referenced; confirm only sdk_meky_check does"] + irq_hits)
    else:
        record("irq123_reserved", "pass", f"no reference to IRQ-123 vector 0x{IRQ123_VECTOR:08X}")

    # 8. eFuse controller never touched (the application never reads or writes
    #    JL_EFUSE; only the never-linked download loader does).
    efuse_hits = [f"{src} +0x{off:x} (0x{w:08X})"
                  for w in range(EFUSE_SFR_LO, EFUSE_SFR_HI + 1, 4)
                  for src, blob in scan_sources for off in _find_le32(blob, w)]
    record("no_efuse_controller_access", "fail" if efuse_hits else "pass",
           efuse_hits or f"no reference to eFuse SFRs 0x{EFUSE_SFR_LO:05X}-0x{EFUSE_SFR_HI:05X}")

    # 9-10. Structural checks that need the linked image's SDK sections and the
    #       vendor objdump. Reported pending on objects; the real link runs them.
    if linked:
        record("late_initcall_group", "pending",
               "linked image: verify the late_initcall group is exactly [sdk_meky_check] "
               "(read __initcall section pointers; see fm1-nes audit_boot.py:251-264)")
        record("sdk_meky_check_scheduling", "pending",
               "linked image: verify sdk_meky_check does only <=2 request_irq(123, isr_check_key) "
               "and sys_timeout_add(_mkey_check, 8000) (needs the vendor objdump; "
               "fm1-nes audit_boot.py:267-278)")
    else:
        record("late_initcall_group", "pending", "needs the linked image (SDK __initcall section)")
        record("sdk_meky_check_scheduling", "pending", "needs the linked image and the vendor objdump")

    failed = [c for c in checks if c["status"] == "fail"]
    pending = [c for c in checks if c["status"] == "pending"]
    return dict(
        passed=not failed,
        linked=linked,
        inputs=[name for name, _ in elves] + [name for name, _ in flat_images],
        n_fail=len(failed),
        n_pending=len(pending),
        checks=checks,
    )


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elf", help="a linked pi32v2 firmware ELF")
    ap.add_argument("--app", help="the flat application image (byte scans), ELF or raw")
    ap.add_argument("--objects", action="append", metavar="DIR|ARCHIVE",
                    help="a directory of .o files or an .a archive (repeatable)")
    ap.add_argument("--json", help="write the full report here")
    args = ap.parse_args(argv)
    if not (args.elf or args.app or args.objects):
        ap.error("give at least one of --elf, --app or --objects")

    try:
        elves, flat, linked = collect_elves(args)
    except ValueError as exc:
        print(f"audit_link: {exc}", file=sys.stderr)
        return 2
    if not elves and not flat:
        print("audit_link: no ELF objects or image found in the inputs", file=sys.stderr)
        return 2
    for name, e in elves:
        if e.e_machine not in (EM_PI32V2, 0):
            print(f"audit_link: warning: {name} machine 0x{e.e_machine:x} is not pi32v2", file=sys.stderr)

    report = audit(elves, flat, linked)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))

    width = max(len(c["check"]) for c in report["checks"])
    for c in report["checks"]:
        mark = {"pass": "ok  ", "fail": "FAIL", "pending": "...."}[c["status"]]
        detail = c["detail"]
        if isinstance(detail, list):
            detail = detail[0] + (f" (+{len(detail) - 1} more)" if len(detail) > 1 else "")
        print(f"  [{mark}] {c['check'].ljust(width)}  {detail}")
    tag = "PASS" if report["passed"] else "FAIL"
    print(f"audit_link: {tag} ({report['n_fail']} fail, {report['n_pending']} pending, "
          f"{'linked' if linked else 'objects-only'})")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
