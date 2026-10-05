"""Tests for tools/jieli/audit_link.py, the SDK key/eFuse link gate.

The audit reads pi32v2 ELF objects, which this Mac's toolchain cannot produce,
so the tests build minimal ELF32 objects by hand (one symtab, one allocated
PROGBITS section). That is enough to exercise every statically-checkable rule:
forbidden key-check symbols, the stub/mailbox/eFuse immediates, the SDK key
blob bytes and the IRQ-123 vector. The structural checks (SDK init-call group,
sdk_meky_check scheduling) only report pending without a linked image, so the
tests assert they never turn a clean object set red.
"""
import importlib.util
import pathlib
import struct

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location(
        "audit_link", ROOT / "tools" / "jieli" / "audit_link.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


AL = load()

EM_PI32V2 = 0xF1


def build_object(symbols=(), undef=(), section_bytes=b"", section_flags=0x6, e_type=1):
    """A minimal ELF32 LE relocatable with .shstrtab, .strtab, a PROGBITS
    section (`.text`, bytes given) and a .symtab.

    symbols: iterable of names defined in .text (shndx -> the text section).
    undef:   iterable of undefined global names (shndx 0).
    section_flags: SHF for the data section (0x6 = ALLOC|EXEC by default).
    """
    # Section name string table.
    shstr = b"\0"
    def shname(n):
        nonlocal shstr
        off = len(shstr)
        shstr += n.encode() + b"\0"
        return off
    n_null = 0
    n_text = shname(".text")
    n_shstr = shname(".shstrtab")
    n_strtab = shname(".strtab")
    n_symtab = shname(".symtab")

    # Symbol string table.
    strtab = b"\0"
    sym_entries = [struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0)]  # null symbol
    text_index = 1  # .text is section 1 (after null section 0)
    for name in symbols:
        off = len(strtab)
        strtab += name.encode() + b"\0"
        info = (1 << 4) | 0  # GLOBAL, NOTYPE
        sym_entries.append(struct.pack("<IIIBBH", off, 0, 0, info, 0, text_index))
    for name in undef:
        off = len(strtab)
        strtab += name.encode() + b"\0"
        info = (1 << 4) | 0
        sym_entries.append(struct.pack("<IIIBBH", off, 0, 0, info, 0, 0))
    symtab = b"".join(sym_entries)

    # Lay out section bodies after a 52-byte ELF header.
    ehsize = 52
    bodies = []
    off = ehsize
    def place(data):
        nonlocal off
        start = off
        bodies.append(data)
        off += len(data)
        return start
    text_off = place(section_bytes)
    shstr_off = place(shstr)
    strtab_off = place(strtab)
    symtab_off = place(symtab)

    shoff = off
    # Section headers: null, .text, .shstrtab, .strtab, .symtab
    def sh(name, typ, flags, addr, offset, size, link, info, align, entsize):
        return struct.pack("<IIIIIIIIII", name, typ, flags, addr, offset, size,
                           link, info, align, entsize)
    sh_null = sh(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    sh_text = sh(n_text, 1, section_flags, 0, text_off, len(section_bytes), 0, 0, 4, 0)
    sh_shstr = sh(n_shstr, 3, 0, 0, shstr_off, len(shstr), 0, 0, 1, 0)
    strtab_index = 3
    sh_strtab = sh(n_strtab, 3, 0, 0, strtab_off, len(strtab), 0, 0, 1, 0)
    sh_symtab = sh(n_symtab, AL.SHT_SYMTAB, 0, 0, symtab_off, len(symtab),
                   strtab_index, 0, 4, 16)
    sheaders = sh_null + sh_text + sh_shstr + sh_strtab + sh_symtab
    shnum = 5
    shstrndx = 2

    ehdr = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
    ehdr += struct.pack("<HHIIIIIHHHHHH",
                        e_type, EM_PI32V2, 1, 0, 0, shoff, 0,
                        ehsize, 0, 0, 40, shnum, shstrndx)
    return ehdr + b"".join(bodies) + sheaders


def run(obj_bytes, tmp_path, name="obj.o"):
    p = tmp_path / name
    p.write_bytes(obj_bytes)
    args = AL.argparse.Namespace(elf=None, app=None, objects=[str(p)], json=None)
    elves, flat, linked = AL.collect_elves(args)
    return AL.audit(elves, flat, linked)


def status(report, key):
    return next(c["status"] for c in report["checks"] if c["check"] == key)


def test_reader_roundtrips_a_hand_built_object(tmp_path):
    obj = build_object(symbols=("our_engine_render",), undef=("memset",),
                       section_bytes=b"\x00\x11\x22\x33")
    e = AL.Elf(obj)
    assert e.e_machine == EM_PI32V2
    assert "our_engine_render" in e.defined_symbols()
    assert "memset" in e.undefined_symbols()


def test_clean_object_passes(tmp_path):
    obj = build_object(symbols=("fm1_seq_create", "plaits_render"),
                       undef=("memset", "sqrtf"),
                       section_bytes=bytes(range(32)))
    report = run(obj, tmp_path)
    assert report["passed"] is True
    assert report["n_fail"] == 0
    # Dormant check is simply absent in an object set; that is allowed.
    assert status(report, "forbidden_keycheck_symbols") == "pass"
    assert status(report, "no_efuse_controller_access") == "pass"
    # Structural checks are pending without a link, never a failure.
    assert status(report, "late_initcall_group") == "pending"
    assert status(report, "sdk_meky_check_scheduling") == "pending"


def test_defining_a_forbidden_symbol_fails(tmp_path):
    obj = build_object(symbols=("sdk_chip_key_verify_v2",))
    report = run(obj, tmp_path)
    assert report["passed"] is False
    assert status(report, "forbidden_keycheck_symbols") == "fail"


def test_referencing_a_forbidden_symbol_fails(tmp_path):
    obj = build_object(symbols=("our_code",), undef=("mkey_check",))
    report = run(obj, tmp_path)
    assert report["passed"] is False
    assert status(report, "forbidden_keycheck_symbols") == "fail"


def test_dormant_symbols_are_allowed(tmp_path):
    obj = build_object(symbols=("sdk_meky_check", "_mkey_check", "isr_check_key"))
    report = run(obj, tmp_path)
    assert report["passed"] is True
    assert status(report, "forbidden_keycheck_symbols") == "pass"
    assert status(report, "dormant_keycheck_present") == "pass"


def test_stub_immediate_fails(tmp_path):
    obj = build_object(section_bytes=struct.pack("<I", AL.STUB_ADDR))
    report = run(obj, tmp_path)
    assert status(report, "stub_0200012E_unused") == "fail"
    assert report["passed"] is False


def test_mailbox_word_fails(tmp_path):
    obj = build_object(section_bytes=b"\xaa" + struct.pack("<I", 0x01C8010C))
    report = run(obj, tmp_path)
    assert status(report, "keycheck_mailbox_unwritten") == "fail"


def test_efuse_sfr_fails(tmp_path):
    obj = build_object(section_bytes=struct.pack("<I", 0x13700))
    report = run(obj, tmp_path)
    assert status(report, "no_efuse_controller_access") == "fail"


def test_sdk_key_blob_bytes_fail(tmp_path):
    obj = build_object(section_bytes=b"\x00\x00" + AL.SDK_KEY_BLOB_PREFIX + b"\x00",
                       section_flags=0x2)  # ALLOC, not exec (rodata)
    report = run(obj, tmp_path)
    assert status(report, "no_sdk_key_blob") == "fail"


def test_key_check_demo_hash_bytes_fail(tmp_path):
    obj = build_object(section_bytes=AL.KEY_CHECK_DEMO_HASH_PREFIX, section_flags=0x2)
    report = run(obj, tmp_path)
    assert status(report, "no_key_check_demo_hash") == "fail"


def test_irq123_vector_in_object_fails(tmp_path):
    obj = build_object(section_bytes=struct.pack("<I", AL.IRQ123_VECTOR))
    report = run(obj, tmp_path)
    assert status(report, "irq123_reserved") == "fail"


def test_bytes_in_nonallocated_section_are_ignored(tmp_path):
    # SHF flags 0 -> not ALLOC: the blob bytes live only in a debug-like section
    # and must not trip the scan.
    obj = build_object(section_bytes=AL.SDK_KEY_BLOB_PREFIX, section_flags=0x0)
    report = run(obj, tmp_path)
    assert status(report, "no_sdk_key_blob") == "pass"


def test_archive_of_objects_is_scanned(tmp_path):
    clean = build_object(symbols=("a",))
    dirty = build_object(symbols=("sdk_mkey_lock",))
    # Build a tiny ar archive by hand.
    def member(name, body):
        header = (name + "/").ljust(16) + "0".ljust(12) + "0".ljust(6) + "0".ljust(6) \
                 + "100644".ljust(8) + str(len(body)).ljust(10) + "`\n"
        pad = b"\n" if len(body) % 2 else b""
        return header.encode("latin-1") + body + pad
    archive = b"!<arch>\n" + member("clean.o", clean) + member("dirty.o", dirty)
    p = tmp_path / "engine.a"
    p.write_bytes(archive)
    args = AL.argparse.Namespace(elf=None, app=None, objects=[str(p)], json=None)
    elves, flat, linked = AL.collect_elves(args)
    report = AL.audit(elves, flat, linked)
    assert report["passed"] is False
    assert status(report, "forbidden_keycheck_symbols") == "fail"
