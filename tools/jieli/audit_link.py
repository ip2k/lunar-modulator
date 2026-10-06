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
  pending  the check needs a linked image or the vendor objdump, or a hit in
           a linked image lies inside the SDK's dormant check and a human
           must confirm it; reported, never a failure on its own (a real
           link is not accepted until every pending item is signed off)

On objects, the symbol-reference, eFuse-access and byte-pattern checks all
run (they are the compile-time half of the safeguards); any hit in our own
objects is a failure. On a linked image the same scans run, and a hit is
attributed to the function whose symbol covers it: the SDK's own dormant
machinery may legitimately touch its mailbox (V1.2.8+ `boot_info_init` ->
`mkey_dummy_func` stores the chip key at 0x01C8010C [verified: notes §3]),
so that one store passes, other hits inside the dormant functions are
pending (a human confirms them with the vendor objdump), and a hit anywhere
else fails. The `late_initcall` group check reads the linked image's
`late_initcall_begin`/`_end` table and requires exactly [sdk_meky_check];
`sdk_meky_check`'s exact scheduling needs the vendor objdump and stays
pending until the real link (DEVELOPERS.md I1).

  --sources DIR                       our C/C++ sources: no request_irq(123)
                                      and no IRQ-123 vector address

What this does NOT cover, by design: the packaging safeguards
(notes/2026-10-05-softkey-efuse.md §4.4) -- asserting the stock SPL hash
730e54f0... and byte-identical isd_config.ini/ota.bin/cfg -- live in
tools/jieli/package_guard.py. And nothing in this tool talks to a device.

MIT licence, like the rest of this repository.
"""
import argparse
import json
import re
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
# The SDK functions that make up the dormant check in a linked image: hits of
# the mailbox / IRQ-123 immediates inside them are the SDK's, not ours.
DORMANT_FUNCTIONS = ALLOWED_KEYCHECK_SYMBOLS + ("mkey_dummy_func",)

# The post-cpu0_start stub `key_check_demo` hashes 92 bytes from (V1.2.8+).
STUB_ADDR = 0x0200012E
# The mailbox words `mkey_dummy_func`/`key_check_demo` read and write.
MAILBOX_LO, MAILBOX_HI = 0x01C80108, 0x01C80110  # inclusive, word-aligned
# The one mailbox access a V1.2.8+ link always carries: boot_info_init passes
# the chip key to mkey_dummy_func, which stores it here [verified: os_api.c IR,
# notes/2026-10-05-softkey-efuse.md §3]. Allowed in that function, or in
# boot_info_init if LTO inlines the call there; nowhere else.
EXPECTED_MAILBOX_STORES = {("mkey_dummy_func", 0x01C8010C), ("boot_info_init", 0x01C8010C)}
# IRQ 123's vector-table slot (base 0x01C80000, slot 123).
IRQ123_VECTOR = 0x01C80000 + 123 * 4  # 0x01C801EC

# Byte signatures that must not appear anywhere in the image.
# The SDK's embedded JL_KEY_2020 blob begins FE 23 A8 B1 28 D4 B4 29.
SDK_KEY_BLOB_PREFIX = bytes.fromhex("FE23A8B128D4B429")
# key_check_demo's 92-byte hash begins 99 56 B6 46 (a prefix; a 4-byte hit is
# a strong signal, not a proof).
KEY_CHECK_DEMO_HASH_PREFIX = bytes.fromhex("9956B646")

# WL82 eFuse controller SFRs (JL_EFUSE 0x13700-0x1371F). No application code
# touches these; only the (never-linked) download loader. The P33 route to the
# eFuse strobes (P3_EFUSE_CON0/CON1/RDAT, P33 bytes 0xB0-0xB2) is not
# byte-scannable (small immediates are everywhere); it is covered by the SDK
# scan in the notes (no app library does it) and by never linking a loader.
EFUSE_SFR_LO, EFUSE_SFR_HI = 0x13700, 0x1371F

# Our sources must not claim IRQ 123: request_irq(123, ...) with a literal
# first argument, or the vector-slot address written out.
IRQ123_SOURCE_PATTERNS = (
    re.compile(r"\brequest_irq\s*\(\s*(?:\(\s*\w+\s*\)\s*)?(?:123|0[xX]0*7[bB])\b"),
    re.compile(r"\b0[xX]0*1[cC]801[eE][cC]\b"),
)
SOURCE_SUFFIXES = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".s", ".S", ".inc")

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

    def function_at(self, addr):
        """Name of the sized symbol (function or object) covering addr, or None."""
        best = None
        for s in self.symbols:
            if s["name"] and s["shndx"] != 0 and s["size"] and s["value"] <= addr < s["value"] + s["size"]:
                if best is None or s["type"] == 2:  # prefer STT_FUNC
                    best = s
        return best["name"] if best else None

    def symbol_value(self, name):
        for s in self.symbols:
            if s["name"] == name and s["shndx"] != 0:
                return s["value"]
        return None

    def read(self, addr, n):
        """n bytes at load address addr from an allocated section, or None."""
        for s in self.sections:
            if (s["flags"] & SHF_ALLOC) and s["type"] != SHT_NOBITS and s["addr"] <= addr \
                    and addr + n <= s["addr"] + s["size"]:
                o = s["offset"] + addr - s["addr"]
                return self.data[o:o + n]
        return None

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


def audit(elves, flat_images, linked, sources=None):
    """sources: None, or [(path, line number, line)] of our C/C++ sources."""
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
    #      A source is (label, elf or None, load address of the blob, blob).
    scan_sources = []
    for name, e in elves:
        for sec, addr, blob in e.allocated_bytes():
            scan_sources.append((f"{name}:{sec}", e, addr, blob))
    for name, blob in flat_images:
        scan_sources.append((name, None, None, blob))

    def imm_hits(values, attributable=False):
        """[(label, offset, value, owning function or None)] for each LE32 hit.
        attributable: with a linked ELF, skip flat images (their bytes are the
        ELF's, which can be attributed to functions; a flat image cannot)."""
        out = []
        for value in values:
            for src, e, addr, blob in scan_sources:
                if attributable and linked and e is None:
                    continue
                for off in _find_le32(blob, value):
                    fn = e.function_at(addr + off) if (linked and e is not None and addr) else None
                    out.append((src, off, value, fn))
        return out

    def fmt(hit):
        src, off, value, fn = hit
        return f"{src} +0x{off:x} (0x{value:08X}{', in ' + fn if fn else ''})"

    def scan_bytes(key, needle, label):
        hits = []
        for src, _e, _a, blob in scan_sources:
            start = 0
            while True:
                i = blob.find(needle, start)
                if i < 0:
                    break
                hits.append(f"{src} +0x{i:x}")
                start = i + 1
        record(key, "fail" if hits else "pass", hits or f"no {label}")

    def classify(key, hits, allowed, clean_detail):
        """Objects: any hit fails (they are ours). Linked image: a hit in
        `allowed` (function, value) pairs passes, a hit inside the SDK's dormant
        functions is pending for a human, anything else fails."""
        if not hits:
            record(key, "pass", clean_detail)
            return
        if not linked:
            record(key, "fail", [fmt(h) for h in hits])
            return
        bad = [h for h in hits if (h[3], h[2]) not in allowed and h[3] not in DORMANT_FUNCTIONS]
        review = [h for h in hits if (h[3], h[2]) not in allowed and h[3] in DORMANT_FUNCTIONS]
        ok = [h for h in hits if (h[3], h[2]) in allowed]
        if bad:
            record(key, "fail", [fmt(h) for h in bad])
        elif review:
            record(key, "pending", ["inside the SDK's dormant check; confirm with the vendor objdump"]
                   + [fmt(h) for h in review])
        else:
            record(key, "pass", ["only the SDK's expected access"] + [fmt(h) for h in ok])

    # 3. The key_check_demo stub: nothing may load or call it, SDK or ours.
    stub = imm_hits([STUB_ADDR])
    record("stub_0200012E_unused", "fail" if stub else "pass",
           [fmt(h) for h in stub] or f"no immediate 0x{STUB_ADDR:08X} (key_check_demo stub call/load)")

    # 4. The key-check mailbox: ours never; the SDK's mkey_dummy_func store is expected.
    classify("keycheck_mailbox_unwritten",
             imm_hits(range(MAILBOX_LO, MAILBOX_HI + 4, 4), attributable=True), EXPECTED_MAILBOX_STORES,
             f"no reference to 0x{MAILBOX_LO:08X}-0x{MAILBOX_HI:08X}")

    # 5-6. The SDK's key blob and key_check_demo's hash never appear.
    scan_bytes("no_sdk_key_blob", SDK_KEY_BLOB_PREFIX, "SDK JL_KEY_2020 blob bytes (FE 23 A8 B1 ...)")
    scan_bytes("no_key_check_demo_hash", KEY_CHECK_DEMO_HASH_PREFIX,
               "key_check_demo hash bytes (99 56 B6 46 ...)")

    # 7. IRQ 123 reserved for the SDK: our code must not install its vector.
    #    In a linked image, a reference inside the dormant check is the SDK's
    #    own (pending, for a human to confirm); anywhere else it fails.
    classify("irq123_reserved", imm_hits([IRQ123_VECTOR], attributable=True), set(),
             f"no reference to IRQ-123 vector 0x{IRQ123_VECTOR:08X}")
    if sources is not None:
        src_hits = []
        for path, line_no, line in sources:
            if any(rx.search(line) for rx in IRQ123_SOURCE_PATTERNS):
                src_hits.append(f"{path}:{line_no}: {line.strip()[:100]}")
        record("irq123_unused_in_sources", "fail" if src_hits else "pass",
               src_hits or "no request_irq(123, ...) or IRQ-123 vector address in our sources")

    # 8. eFuse controller never touched (the application never reads or writes
    #    JL_EFUSE; only the never-linked download loader does). No exceptions.
    efuse = imm_hits(range(EFUSE_SFR_LO, EFUSE_SFR_HI + 1, 4))
    record("no_efuse_controller_access", "fail" if efuse else "pass",
           [fmt(h) for h in efuse] or f"no reference to eFuse SFRs 0x{EFUSE_SFR_LO:05X}-0x{EFUSE_SFR_HI:05X}")

    # 9. The late_initcall group is exactly [sdk_meky_check] (fm1-nes
    #    audit_boot.py:251-264): the dormant check is linked, not stubbed or
    #    dropped, and nothing else was added to the group.
    image = next((e for _n, e in elves if e.e_type == ET_EXEC), None) if linked else None
    if image is None:
        record("late_initcall_group", "pending", "needs the linked image (SDK __initcall section)")
    else:
        begin = image.symbol_value("late_initcall_begin")
        end = image.symbol_value("late_initcall_end")
        meky = image.symbol_value("sdk_meky_check")
        if begin is None or end is None:
            record("late_initcall_group", "fail", "late_initcall_begin/_end not in the symbol table")
        elif meky is None:
            record("late_initcall_group", "fail",
                   "sdk_meky_check is not linked: the dormant check must stay, not be stubbed or dropped")
        else:
            raw = image.read(begin, end - begin) if end >= begin else None
            if raw is None or len(raw) % 4:
                record("late_initcall_group", "fail",
                       f"cannot read the table at 0x{begin:08X}-0x{end:08X}")
            else:
                ptrs = struct.unpack(f"<{len(raw) // 4}I", raw)
                ok = ptrs == (meky,)
                record("late_initcall_group", "pass" if ok else "fail",
                       f"late_initcall = [{', '.join(f'0x{x:08X}' for x in ptrs)}]; "
                       f"expected [sdk_meky_check 0x{meky:08X}]")

    # 10. sdk_meky_check's exact scheduling: <= 2 request_irq(123, isr_check_key)
    #     and sys_timeout_add(_mkey_check, 8000). Needs the vendor objdump's
    #     decode of pi32v2 long calls (trap 4); pending until the real link.
    if linked:
        record("sdk_meky_check_scheduling", "pending",
               "linked image: verify sdk_meky_check does only <=2 request_irq(123, isr_check_key) "
               "and sys_timeout_add(_mkey_check, 8000) with the vendor objdump "
               "(fm1-nes audit_boot.py:267-278 pins its own link's bytes)")
    else:
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


def collect_sources(dirs):
    """[(path, line number, line)] for every C/C++/asm source under dirs."""
    out = []
    for d in dirs:
        root = Path(d)
        files = [root] if root.is_file() else sorted(p for p in root.rglob("*") if p.is_file())
        for f in files:
            if f.suffix not in SOURCE_SUFFIXES:
                continue
            for i, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
                out.append((str(f), i, line))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--elf", help="a linked pi32v2 firmware ELF")
    ap.add_argument("--app", help="the flat application image (byte scans), ELF or raw")
    ap.add_argument("--objects", action="append", metavar="DIR|ARCHIVE",
                    help="a directory of .o files or an .a archive (repeatable)")
    ap.add_argument("--sources", action="append", metavar="DIR",
                    help="our C/C++ sources, scanned for request_irq(123) (repeatable)")
    ap.add_argument("--json", help="write the full report here")
    args = ap.parse_args(argv)
    if not (args.elf or args.app or args.objects):
        ap.error("give at least one of --elf, --app or --objects")
    for d in args.sources or []:
        if not Path(d).exists():
            ap.error(f"--sources {d}: no such file or directory")

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

    sources = collect_sources(args.sources) if args.sources else None
    report = audit(elves, flat, linked, sources)
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
