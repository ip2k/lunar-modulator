#!/usr/bin/env python3
"""tools/jieli/analyze.py -- read what tools/jieli/in-container.sh compiled and
write OUT/report.json and OUT/report.md.

Everything is read from the object files themselves (a small ELF reader, so it
needs no binutils that know pi32v2): section sizes, symbols, relocations and
the `fm1sz_*` constants of sizes.cc/sizes.c. The toolchain's LLVM objdump is
used only for relocation type names (the -fPIC profile).

    python3 tools/jieli/analyze.py OUT

Standard library only. MIT licence, like the rest of this repository.
"""
import json
import re
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

OBJDUMP = "/opt/jieli/pi32v2/bin/objdump"
PROFILES = ["ladder", "fast", "sdk", "pic"]

SHT_SYMTAB, SHT_NOBITS, SHT_RELA, SHT_REL = 2, 8, 4, 9
SHF_WRITE, SHF_ALLOC, SHF_EXEC = 0x1, 0x2, 0x4


class Elf:
    """Just enough ELF (32/64-bit, little-endian) for sizes, symbols and relocs."""

    def __init__(self, path):
        self.path = Path(path)
        d = self.data = self.path.read_bytes()
        if d[:4] != b"\x7fELF" or d[5] != 1:
            raise ValueError(f"{path}: not a little-endian ELF")
        self.is64 = d[4] == 2
        if self.is64:
            shoff, = struct.unpack_from("<Q", d, 0x28)
            shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x3A)
        else:
            shoff, = struct.unpack_from("<I", d, 0x20)
            shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2E)
        self.sections = []
        for i in range(shnum):
            o = shoff + i * shentsize
            if self.is64:
                name, typ, flags, addr, off, size, link, info, align, entsize = \
                    struct.unpack_from("<IIQQQQIIQQ", d, o)
            else:
                name, typ, flags, addr, off, size, link, info, align, entsize = \
                    struct.unpack_from("<IIIIIIIIII", d, o)
            self.sections.append(dict(name_off=name, type=typ, flags=flags, offset=off,
                                      size=size, link=link, info=info, entsize=entsize))
        strtab = self.sections[shstrndx]
        for s in self.sections:
            s["name"] = self._str(strtab, s["name_off"])
        self.symbols = self._symbols()

    def _str(self, sec, off):
        start = sec["offset"] + off
        end = self.data.index(b"\0", start)
        return self.data[start:end].decode("utf-8", "replace")

    def _symbols(self):
        out = []
        for s in self.sections:
            if s["type"] != SHT_SYMTAB:
                continue
            strtab = self.sections[s["link"]]
            n = s["size"] // s["entsize"]
            for i in range(n):
                o = s["offset"] + i * s["entsize"]
                if self.is64:
                    name, info, other, shndx, value, size = struct.unpack_from("<IBBHQQ", self.data, o)
                else:
                    name, value, size, info, other, shndx = struct.unpack_from("<IIIBBH", self.data, o)
                out.append(dict(name=self._str(strtab, name), value=value, size=size,
                                bind=info >> 4, type=info & 0xF, shndx=shndx))
        return out

    def section_bytes(self, sec):
        return self.data[sec["offset"]:sec["offset"] + sec["size"]]

    def sizes(self):
        """Berkeley-style: code, read-only data, data and bss of the allocated sections."""
        code = rodata = data = bss = 0
        for s in self.sections:
            if not s["flags"] & SHF_ALLOC:
                continue
            if s["type"] == SHT_NOBITS:
                bss += s["size"]
            elif s["flags"] & SHF_WRITE:
                data += s["size"]
            elif s["flags"] & SHF_EXEC:
                code += s["size"]
            else:
                rodata += s["size"]
        return dict(code=code, rodata=rodata, text=code + rodata, data=data, bss=bss)

    def undefined(self):
        return sorted({s["name"] for s in self.symbols
                       if s["shndx"] == 0 and s["name"] and s["bind"] in (1, 2)})

    def defined_globals(self):
        return {s["name"] for s in self.symbols
                if s["shndx"] != 0 and s["name"] and s["bind"] in (1, 2)}

    def call_map(self):
        """{function section name -> sorted referenced symbol names} from the
        relocation sections (with -ffunction-sections, one per function)."""
        symtab = [s for s in self.sections if s["type"] == SHT_SYMTAB]
        if not symtab:
            return {}
        out = defaultdict(set)
        for s in self.sections:
            if s["type"] not in (SHT_RELA, SHT_REL):
                continue
            target = self.sections[s["info"]]["name"]
            ent = s["entsize"] or (12 if s["type"] == SHT_RELA else 8)
            for i in range(s["size"] // ent):
                o = s["offset"] + i * ent
                _, rinfo = struct.unpack_from("<II", self.data, o)
                sym = self.symbols[rinfo >> 8] if (rinfo >> 8) < len(self.symbols) else None
                if sym and sym["name"]:
                    out[target].add(sym["name"])
        return {k: sorted(v) for k, v in out.items()}

    def constants(self, prefix="fm1sz_"):
        out = {}
        for s in self.symbols:
            if s["name"].startswith(prefix) and s["shndx"] not in (0, 0xFFF1, 0xFFF2):
                sec = self.sections[s["shndx"]]
                out[s["name"][len(prefix):]] = struct.unpack_from(
                    "<I", self.data, sec["offset"] + s["value"])[0]
        return out


def demangle(names):
    names = list(names)
    if not names:
        return {}
    try:
        r = subprocess.run(["c++filt"], input="\n".join(names), capture_output=True, text=True)
        return dict(zip(names, r.stdout.splitlines()))
    except OSError:
        return {n: n for n in names}


def group_of(rel):
    if rel.startswith("our/src/"):
        return "Engines, effects and shim (ours)"
    if rel.startswith("tp/plaits/"):
        return "Plaits (vendored, MIT)"
    if rel.startswith("tp/braids/"):
        return "Braids (vendored, MIT)"
    if rel.startswith("tp/stmlib/"):
        return "stmlib (vendored, MIT)"
    if rel.startswith("tp/msfa/"):
        return "msfa (vendored, Apache-2.0)"
    if rel.startswith("sw/"):
        return "Schwung modules (vendored, MIT)"
    if rel.startswith("gpl/"):                  # GPL_OBJ: built only with FM1_GPL_MODS=1
        return "GPL modules (vendored, GPL switch)"
    if rel.startswith("c/seq/"):
        return "Sequencer core"
    if rel.startswith("sim/"):
        return "App layer (sim/web/src)"
    return "other"


SOFT_DOUBLE = re.compile(r"^__(add|sub|mul|div|neg|eq|ne|lt|le|gt|ge|un|cmp)df[23]$|"
                         r"^__(extendsfdf2|truncdfsf2|fix(uns)?df[sd]i|float(un)?[sd]idf)$")
SOFT_FLOAT = re.compile(r"^__(add|sub|mul|div|neg|eq|ne|lt|le|gt|ge|un|cmp)sf[23]$|"
                        r"^__(fix(uns)?sf[sd]i|float(un)?[sd]isf)$")
INT64 = re.compile(r"^__(u?(div|mod)di3|ashldi3|lshrdi3|ashrdi3|muldi3|u?cmpdi2)$")


def read_logs(prof_dir, rel):
    log = prof_dir / "logs" / (rel + ".log")
    rc = prof_dir / "logs" / (rel + ".log.rc")
    text = log.read_text(errors="replace") if log.exists() else ""
    code = int(rc.read_text().strip()) if rc.exists() else None
    return code, text


def warnings_of(text):
    ws = []
    for line in text.splitlines():
        m = re.search(r"(warning|error): (.*)$", line)
        if m:
            flag = re.search(r"\[(-W[^\]]+)\]", line)
            ws.append(dict(kind=m.group(1), flag=flag.group(1) if flag else "",
                           where=line.split(": ")[0], text=m.group(2)))
    return ws


PUSH = re.compile(r"\[--sp\] = \{?([^}]*)\}?")
SP_ADJ = re.compile(r"\bsp \+= -(\d+)\b|\bsp -= (\d+)\b")
SP_ODD = re.compile(r"\bsp (\+|-)= r\d+|\bsp = ")


def functions(text):
    """(name, first instruction lines) for each function in objdump -d output."""
    out, name, body = [], None, []
    for line in text.splitlines():
        if line and not line[0].isspace() and line.endswith(":") and not line.startswith("Disassembly"):
            if name:
                out.append((name, body))
            name, body = line[:-1], []
        elif name and line.strip():
            body.append(line)
    if name:
        out.append((name, body))
    return out


def frame_of(body):
    """Bytes the prologue reserves: 4 per pushed register plus the sp adjustment."""
    regs = adj = 0
    how = ""
    for line in body[:8]:
        m = PUSH.search(line)
        if m and regs == 0:
            for part in m.group(1).split(","):
                part = part.strip()
                r = re.match(r"r(\d+)-r(\d+)$", part)
                regs += abs(int(r.group(1)) - int(r.group(2))) + 1 if r else (1 if part else 0)
        m = SP_ADJ.search(line)
        if m and adj == 0:
            adj = int(m.group(1) or m.group(2))
        if SP_ODD.search(line):
            how = "sp set from a register: " + line.split("\t")[-1].strip()
    return regs * 4 + adj, how


def reloc_types(obj):
    try:
        r = subprocess.run([OBJDUMP, "-r", str(obj)], capture_output=True, text=True)
    except OSError:
        return Counter()
    c = Counter()
    for line in r.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].startswith("R_"):
            c[parts[1]] += 1
    return c


def main(out):
    out = Path(out)
    report = dict(profiles={}, objects={}, groups={}, symbols={}, sizes={}, contraction={},
                  pic={}, stack={}, warnings={})

    # 1. Objects per profile: status, sizes, warnings.
    elves = {}
    for p in PROFILES:
        pdir = out / p
        if not (pdir / "objects.txt").exists():
            continue
        objs = [Path(x) for x in (pdir / "objects.txt").read_text().split()]
        base = pdir / "obj"
        prof = dict(opt=(pdir / "opt.txt").read_text().strip(), objects=len(objs), failed=[],
                    warnings=Counter())
        for o in objs:
            rel = str(o.relative_to(base))
            code, text = read_logs(pdir, rel)
            ws = warnings_of(text)
            for w in ws:
                prof["warnings"][f"{w['kind']} {w['flag']}".strip()] += 1
            entry = report["objects"].setdefault(rel, dict(group=group_of(rel)))
            entry[p] = dict(rc=code, warnings=len([w for w in ws if w["kind"] == "warning"]))
            if code != 0 or not o.exists():
                prof["failed"].append(rel)
                entry[p]["errors"] = [w for w in ws if w["kind"] == "error"][:5]
                continue
            e = Elf(o)
            elves[(p, rel)] = e
            entry[p].update(e.sizes())
            if p == "ladder":
                entry["warnings_list"] = [w for w in ws if w["kind"] == "warning"]
        prof["warnings"] = dict(prof["warnings"])
        report["profiles"][p] = prof

    # 2. Group totals (ladder and sdk).
    for p in ("ladder", "sdk"):
        g = defaultdict(lambda: Counter())
        for rel, entry in report["objects"].items():
            if p in entry and "code" in entry[p]:
                for k in ("code", "rodata", "text", "data", "bss"):
                    g[entry["group"]][k] += entry[p][k]
                g[entry["group"]]["objects"] += 1
        total = Counter()
        for v in g.values():
            total.update(v)
        g["TOTAL"] = total
        report["groups"][p] = {k: dict(v) for k, v in g.items()}

    # 3. Symbols: what the objects need from outside, and who provides it.
    ladder = {rel: e for (p, rel), e in elves.items() if p == "ladder"}
    ours = set()
    for e in ladder.values():
        ours |= e.defined_globals()
    libs = {}
    for f in sorted((out / "libsyms").glob("*.txt")):
        for name in f.read_text().split():
            libs.setdefault(name, f.stem)
    needed = defaultdict(set)
    for rel, e in ladder.items():
        for name in e.undefined():
            if name not in ours:
                needed[name].add(rel)
    callers = defaultdict(set)
    for rel, e in ladder.items():
        for fn_sec, syms in e.call_map().items():
            fn = fn_sec[len(".text."):] if fn_sec.startswith(".text.") else fn_sec
            for s in syms:
                if s in needed:
                    callers[s].add(f"{rel}:{fn}")
    dm = demangle({c.split(":", 1)[1] for v in callers.values() for c in v} | set(needed))

    def category(name):
        lib = libs.get(name, "UNRESOLVED")
        if SOFT_DOUBLE.match(name):
            return "soft double (compiler-rt)" if lib != "UNRESOLVED" else "soft double (unresolved)"
        if SOFT_FLOAT.match(name):
            return "soft float (compiler-rt)"
        if INT64.match(name):
            return "64-bit integer (compiler-rt)"
        return lib

    syms = {}
    for name in sorted(needed):
        syms[name] = dict(
            demangled=dm.get(name, name), provider=libs.get(name, "UNRESOLVED"),
            category=category(name), objects=sorted(needed[name]),
            callers=sorted(f"{c.split(':', 1)[0]}: {dm.get(c.split(':', 1)[1], c.split(':', 1)[1])}"
                           for c in callers.get(name, ())))
    report["symbols"] = syms

    # 4. Fused multiply-add: does -ffp-contract=fast change any code bytes?
    differ = []
    compared = 0
    for (p, rel), e in elves.items():
        if p != "ladder" or ("fast", rel) not in elves:
            continue
        f = elves[("fast", rel)]
        a = {s["name"]: e.section_bytes(s) for s in e.sections if s["flags"] & SHF_EXEC}
        b = {s["name"]: f.section_bytes(s) for s in f.sections if s["flags"] & SHF_EXEC}
        compared += len(a)
        for name in sorted(set(a) | set(b)):
            if a.get(name) != b.get(name):
                differ.append(f"{rel}:{name}")
    report["contraction"] = dict(functions_compared=compared, differing=differ)

    # 5. -fPIC: relocation types against the ladder build.
    for p in ("ladder", "pic"):
        c = Counter()
        for (q, rel), e in elves.items():
            if q == p:
                c.update(reloc_types(e.path))
        report["pic"][p] = dict(c)

    # 6. Stack frames from the disassembly (ladder): the prologue's register
    # push, `[--sp] = {rets, r8-r4}`, plus its `sp += -N`.
    frames, odd = [], []
    for f in sorted((out / "ladder" / "disasm").rglob("*.txt")):
        rel = str(f.relative_to(out / "ladder" / "disasm"))[:-4]
        for fn, body in functions(f.read_text(errors="replace")):
            fr, how = frame_of(body)
            frames.append((fr, rel, fn))
            if how:
                odd.append(f"{rel}: {fn}: {how}")
    frames.sort(reverse=True)
    dmf = demangle({fn for _, _, fn in frames[:25]})
    report["stack"] = dict(functions=len(frames), unusual=odd,
                           top=[dict(bytes=b, object=r, function=dmf.get(fn, fn)) for b, r, fn in frames[:25]])

    # 6b. The largest static RAM symbols (data and bss), ladder.
    ram = []
    for (p, rel), e in elves.items():
        if p != "ladder":
            continue
        for sym in e.symbols:
            if sym["shndx"] in (0, 0xFFF1, 0xFFF2) or sym["shndx"] >= len(e.sections) or not sym["size"]:
                continue
            sec = e.sections[sym["shndx"]]
            if sec["flags"] & SHF_ALLOC and (sec["flags"] & SHF_WRITE or sec["type"] == SHT_NOBITS):
                ram.append((sym["size"], rel, sym["name"]))
    ram.sort(reverse=True)
    report["ram_symbols"] = [dict(bytes=b, object=r, symbol=n) for b, r, n in ram[:15]]

    # 7. Instance and struct sizes on each target.
    sizes = {}
    for t in ("pi32v2", "i386", "x86_64"):
        d = out / "sizes" / t
        consts = {}
        for o in sorted(d.glob("*.o")):
            try:
                consts.update(Elf(o).constants())
            except (ValueError, OSError):
                pass
        sizes[t] = consts
    report["sizes"]["constants"] = sizes

    def r16(n):
        return (n + 15) & ~15

    inst = {}
    for t, c in sizes.items():
        v = {}
        for e in ("macro", "shapes", "macro_heavy", "sixop", "dx7", "test_sine", "test_gain"):
            if e in c:
                v[e] = c[e]
        for e in ("plate", "ensemble", "diffuse", "acid_bass", "comet_kit", "crater"):
            if e in c:
                v[e] = r16(c[e])
        if "schwung_instance" in c and "schwung_align" in c:
            al = c["schwung_align"]

            def up(n):
                return (n + al - 1) & ~(al - 1)

            v["sw_sophie"] = up(c["schwung_instance"]) + up(c["sophie_arena"])
            v["sw_psxverb"] = up(c["schwung_instance"]) + up(c["psxverb_arena"])
        inst[t] = v
    report["sizes"]["instance_size"] = inst
    for t in ("i386", "x86_64"):
        f = out / "sizes" / f"seq-sizes-{t}.json"
        if f.exists() and f.read_text().strip():
            report["sizes"][f"fm1_seq_size_{t}"] = json.loads(f.read_text())

    # 8. Every warning (ladder), by flag.
    wl = defaultdict(list)
    for rel, entry in report["objects"].items():
        for w in entry.get("warnings_list", []):
            wl[w["flag"] or "(no flag)"].append(f"{w['where']}: {w['text']}")
    report["warnings"] = {k: v for k, v in sorted(wl.items())}

    (out / "report.json").write_text(json.dumps(report, indent=1, sort_keys=True))
    (out / "report.md").write_text(markdown(report))
    print((out / "report.md").read_text())


def markdown(r):
    L = []
    L.append("# JieLi pi32v2 compile check\n")
    L.append("| Profile | Flags | Objects | Failed | Warnings |")
    L.append("| --- | --- | ---: | ---: | --- |")
    for p, v in r["profiles"].items():
        w = ", ".join(f"{k} ×{n}" for k, n in sorted(v["warnings"].items())) or "none"
        L.append(f"| {p} | `{v['opt']}` | {v['objects']} | {len(v['failed'])} | {w} |")
    for p, v in r["profiles"].items():
        for f in v["failed"]:
            errs = r["objects"][f][p].get("errors", [])
            L.append(f"- {p}: `{f}` failed: " + "; ".join(e["text"] for e in errs[:3]))
    for p in ("ladder", "sdk"):
        if p not in r["groups"]:
            continue
        L.append(f"\n## Size by group ({p})\n")
        L.append("| Group | Objects | Code | Read-only data | text | data | bss |")
        L.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for g, v in sorted(r["groups"][p].items(), key=lambda kv: (kv[0] == "TOTAL", kv[0])):
            L.append(f"| {g} | {v.get('objects', 0)} | {v.get('code', 0):,} | {v.get('rodata', 0):,} | "
                     f"{v.get('text', 0):,} | {v.get('data', 0):,} | {v.get('bss', 0):,} |")
    L.append("\n## Per object (ladder, then sdk text)\n")
    L.append("| Object | Code | Read-only data | text | data | bss | sdk text |")
    L.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for rel, e in sorted(r["objects"].items()):
        a, s = e.get("ladder", {}), e.get("sdk", {})
        if "code" not in a:
            L.append(f"| `{rel}` | failed | | | | | |")
            continue
        L.append(f"| `{rel}` | {a['code']:,} | {a['rodata']:,} | {a['text']:,} | {a['data']:,} | "
                 f"{a['bss']:,} | {s.get('text', 0):,} |")
    L.append("\n## External symbols the objects need (ladder)\n")
    L.append("| Symbol | Category | Provider | Objects |")
    L.append("| --- | --- | --- | ---: |")
    for name, v in r["symbols"].items():
        L.append(f"| `{v['demangled']}` | {v['category']} | {v['provider']} | {len(v['objects'])} |")
    L.append("\n## Callers of soft double, libm and unresolved symbols\n")
    for name, v in r["symbols"].items():
        if v["provider"] not in ("libc",) or v["category"].startswith("soft"):
            L.append(f"- `{v['demangled']}` ({v['category']}): " + "; ".join(v["callers"][:12])
                     + (" …" if len(v["callers"]) > 12 else ""))
    c = r["contraction"]
    L.append(f"\n## -ffp-contract=fast against off\n\n{c['functions_compared']} code sections compared; "
             f"{len(c['differing'])} differ.")
    for d in c["differing"][:40]:
        L.append(f"- `{d}`")
    L.append("\n## Relocation types\n")
    for p, v in r["pic"].items():
        L.append(f"- {p}: " + ", ".join(f"{k} ×{n}" for k, n in sorted(v.items())))
    L.append(f"\n## Largest stack frames (prologues, ladder; {r['stack']['functions']} functions)\n")
    for s in r["stack"]["top"]:
        L.append(f"- {s['bytes']:,} B `{s['function']}` ({s['object']})")
    for u in r["stack"]["unusual"]:
        L.append(f"- unusual prologue: {u}")
    L.append("\n## Largest static RAM symbols (ladder)\n")
    for s in r["ram_symbols"]:
        L.append(f"- {s['bytes']:,} B `{s['symbol']}` ({s['object']})")
    L.append("\n## Instance sizes (bytes)\n")
    inst = r["sizes"]["instance_size"]
    L.append("| Engine | pi32v2 | i386 | x86-64 |")
    L.append("| --- | ---: | ---: | ---: |")
    for e in sorted(set().union(*[set(v) for v in inst.values()])):
        L.append(f"| {e} | " + " | ".join(f"{inst.get(t, {}).get(e, '—'):,}" if isinstance(
            inst.get(t, {}).get(e), int) else "—" for t in ("pi32v2", "i386", "x86_64")) + " |")
    L.append("\n## Struct sizes and ABI (bytes)\n")
    cs = r["sizes"]["constants"]
    L.append("| Constant | pi32v2 | i386 | x86-64 |")
    L.append("| --- | ---: | ---: | ---: |")
    for k in sorted(set().union(*[set(v) for v in cs.values()])):
        vals = [cs.get(t, {}).get(k) for t in ("pi32v2", "i386", "x86_64")]
        L.append(f"| {k} | " + " | ".join("—" if v is None else f"{v:,}" for v in vals) + " |")
    for t in ("i386", "x86_64"):
        k = f"fm1_seq_size_{t}"
        if k in r["sizes"]:
            L.append(f"\n`fm1_seq_size()` on {t}, default limits: " +
                     ", ".join(f"{n} tracks {b:,}" for n, b in r["sizes"][k]["tracks"].items()
                               if n in ("4", "8", "16")))
    L.append("\n## Warnings (ladder)\n")
    for flag, ws in r["warnings"].items():
        L.append(f"- {flag}: {len(ws)}")
        for w in ws[:8]:
            L.append(f"  - {w}")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main(sys.argv[1])
