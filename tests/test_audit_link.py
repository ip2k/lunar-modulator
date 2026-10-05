"""Tests for tools/jieli/audit_link.py, the SDK key/eFuse link gate.

The audit reads pi32v2 ELF objects, which this Mac's toolchain cannot produce,
so the tests build minimal ELF32 objects by hand (one symtab, one allocated
PROGBITS section). That is enough to exercise every statically-checkable rule:
forbidden key-check symbols, the stub/mailbox/eFuse immediates, the SDK key
blob bytes and the IRQ-123 vector. The structural checks (SDK init-call group,
sdk_meky_check scheduling) only report pending without a linked image, so the
tests assert they never turn a clean object set red.

A second builder makes minimal linked executables (functions with addresses
and sizes, a late_initcall table) to test attribution: the SDK's own
mkey_dummy_func mailbox store passes, other hits inside the dormant check are
pending, hits anywhere else fail, and the late_initcall group must be exactly
[sdk_meky_check]. The source scan (request_irq(123)) is tested on text.
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


# ---- linked images: attribution to functions, the late_initcall table -------

TEXT_BASE = 0x02000120
INIT_BASE = 0x02090000


def build_linked(funcs, init_ptrs=None, extra_syms=()):
    """A minimal ELF32 LE executable (ET_EXEC).

    funcs: [(name, body bytes)] laid out back to back in .text from TEXT_BASE;
           each gets an STT_FUNC symbol with its address and size.
    init_ptrs: None (no late_initcall table), or a list of names/ints whose
           addresses fill a .initcall section bounded by late_initcall_begin/_end.
    extra_syms: [(name, value)] additional sized-0 symbols.
    Returns (bytes, {name: address})."""
    text, addrs, fsyms = b"", {}, []
    for name, body in funcs:
        addrs[name] = TEXT_BASE + len(text)
        fsyms.append((name, addrs[name], len(body), 2, 1))
        text += body
        text += b"\0" * (-len(text) % 4)
    sections = [(".text", TEXT_BASE, text, 0x6)]
    syms = list(fsyms)
    if init_ptrs is not None:
        words = b"".join(struct.pack("<I", addrs[p] if isinstance(p, str) else p) for p in init_ptrs)
        sections.append((".initcall", INIT_BASE, words or b"\0\0\0\0"[:0], 0x2))
        syms.append(("late_initcall_begin", INIT_BASE, 0, 0, 2))
        syms.append(("late_initcall_end", INIT_BASE + len(words), 0, 0, 2))
    for name, value in extra_syms:
        syms.append((name, value, 0, 0, 1))

    shstr = b"\0"
    def shname(n):
        nonlocal shstr
        off = len(shstr)
        shstr += n.encode() + b"\0"
        return off
    strtab = b"\0"
    entries = [struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0)]
    for name, value, size, typ, shndx in syms:
        off = len(strtab)
        strtab += name.encode() + b"\0"
        entries.append(struct.pack("<IIIBBH", off, value, size, (1 << 4) | typ, 0, shndx))
    symtab = b"".join(entries)

    body, offs, pos = b"", [], 52
    for _n, _a, data, _f in sections:
        offs.append(pos + len(body))
        body += data
    shstr_names = [shname(n) for n, _a, _d, _f in sections]
    n_shstr, n_str, n_sym = shname(".shstrtab"), shname(".strtab"), shname(".symtab")
    shstr_off = pos + len(body); body += shstr
    str_off = pos + len(body); body += strtab
    sym_off = pos + len(body); body += symtab
    shoff = pos + len(body)

    def sh(name, typ, flags, addr, offset, size, link, entsize):
        return struct.pack("<IIIIIIIIII", name, typ, flags, addr, offset, size, link, 0, 4, entsize)
    heads = sh(0, 0, 0, 0, 0, 0, 0, 0)
    for (n, a, d, f), o, nm in zip(sections, offs, shstr_names):
        heads += sh(nm, 1, f, a, o, len(d), 0, 0)
    i_shstr = len(sections) + 1
    heads += sh(n_shstr, 3, 0, 0, shstr_off, len(shstr), 0, 0)
    heads += sh(n_str, 3, 0, 0, str_off, len(strtab), 0, 0)
    heads += sh(n_sym, AL.SHT_SYMTAB, 0, 0, sym_off, len(symtab), i_shstr + 1, 16)
    shnum = len(sections) + 4
    ehdr = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\0" * 8
    ehdr += struct.pack("<HHIIIIIHHHHHH", 2, EM_PI32V2, 1, TEXT_BASE, 0, shoff, 0,
                        52, 0, 0, 40, shnum, i_shstr)
    return ehdr + body + heads, addrs


def run_linked(elf_bytes, tmp_path, app=None, sources=None):
    p = tmp_path / "fw.elf"
    p.write_bytes(elf_bytes)
    a = None
    if app is not None:
        a = tmp_path / "app.bin"
        a.write_bytes(app)
    args = AL.argparse.Namespace(elf=str(p), app=str(a) if a else None, objects=None, json=None)
    elves, flat, linked = AL.collect_elves(args)
    assert linked is True
    return AL.audit(elves, flat, linked, sources)


NOP = b"\x00" * 8
DORMANT = [("sdk_meky_check", NOP), ("_mkey_check", NOP), ("isr_check_key", NOP)]


def le(v):
    return struct.pack("<I", v)


def test_linked_clean_image_passes_with_initcall_group(tmp_path):
    elf, _ = build_linked(DORMANT + [("main", NOP)], init_ptrs=["sdk_meky_check"])
    report = run_linked(elf, tmp_path)
    assert report["passed"] is True, report
    assert status(report, "late_initcall_group") == "pass"
    assert status(report, "sdk_meky_check_scheduling") == "pending"


def test_linked_sdk_mailbox_store_in_mkey_dummy_func_passes(tmp_path):
    # V1.2.8+ boot_info_init -> mkey_dummy_func stores the chip key at 0x01C8010C.
    elf, _ = build_linked(DORMANT + [("mkey_dummy_func", NOP + le(0x01C8010C))],
                          init_ptrs=["sdk_meky_check"])
    report = run_linked(elf, tmp_path)
    assert status(report, "keycheck_mailbox_unwritten") == "pass"
    assert report["passed"] is True


def test_linked_mailbox_in_our_code_fails(tmp_path):
    elf, _ = build_linked(DORMANT + [("fm1_app_main", NOP + le(0x01C8010C))],
                          init_ptrs=["sdk_meky_check"])
    report = run_linked(elf, tmp_path)
    assert status(report, "keycheck_mailbox_unwritten") == "fail"
    assert report["passed"] is False


def test_linked_other_mailbox_word_in_dormant_check_is_pending(tmp_path):
    # Not the one verified store: a human confirms it with the vendor objdump.
    elf, _ = build_linked([("sdk_meky_check", NOP), ("_mkey_check", NOP + le(0x01C80108)),
                           ("isr_check_key", NOP)], init_ptrs=["sdk_meky_check"])
    report = run_linked(elf, tmp_path)
    assert status(report, "keycheck_mailbox_unwritten") == "pending"
    assert report["passed"] is True


def test_linked_mailbox_value_outside_any_named_function_fails(tmp_path):
    # An unnamed region (a stray literal pool) cannot be attributed: it fails.
    elf, _ = build_linked(DORMANT + [("", le(0x01C8010C))], init_ptrs=["sdk_meky_check"])
    assert status(run_linked(elf, tmp_path), "keycheck_mailbox_unwritten") == "fail"
    # The expected value, but in a function that is not mkey_dummy_func: fails.
    elf, _ = build_linked(DORMANT + [("fm1_x", le(0x01C80110))], init_ptrs=["sdk_meky_check"])
    assert status(run_linked(elf, tmp_path), "keycheck_mailbox_unwritten") == "fail"


def test_linked_irq123_vector_in_our_code_fails_in_sdk_is_pending(tmp_path):
    ours, _ = build_linked(DORMANT + [("fm1_isr_setup", le(AL.IRQ123_VECTOR))],
                           init_ptrs=["sdk_meky_check"])
    assert status(run_linked(ours, tmp_path), "irq123_reserved") == "fail"
    sdk, _ = build_linked([("sdk_meky_check", le(AL.IRQ123_VECTOR)), ("_mkey_check", NOP),
                           ("isr_check_key", NOP)], init_ptrs=["sdk_meky_check"])
    assert status(run_linked(sdk, tmp_path), "irq123_reserved") == "pending"


def test_linked_stub_reference_fails_even_in_sdk_code(tmp_path):
    elf, _ = build_linked([("sdk_meky_check", NOP), ("_mkey_check", NOP),
                           ("isr_check_key", le(AL.STUB_ADDR))], init_ptrs=["sdk_meky_check"])
    report = run_linked(elf, tmp_path)
    assert status(report, "stub_0200012E_unused") == "fail"


def test_linked_efuse_access_fails_even_in_sdk_code(tmp_path):
    elf, _ = build_linked([("sdk_meky_check", NOP), ("_mkey_check", le(0x13704)),
                           ("isr_check_key", NOP)], init_ptrs=["sdk_meky_check"])
    assert status(run_linked(elf, tmp_path), "no_efuse_controller_access") == "fail"


def test_late_initcall_group_with_an_extra_entry_fails(tmp_path):
    elf, _ = build_linked(DORMANT + [("fm1_late", NOP)], init_ptrs=["sdk_meky_check", "fm1_late"])
    assert status(run_linked(elf, tmp_path), "late_initcall_group") == "fail"


def test_late_initcall_group_pointing_elsewhere_fails(tmp_path):
    # A stubbed check: the slot points at a different function.
    elf, _ = build_linked(DORMANT + [("stub_ret", NOP)], init_ptrs=["stub_ret"])
    assert status(run_linked(elf, tmp_path), "late_initcall_group") == "fail"


def test_late_initcall_group_without_the_dormant_check_fails(tmp_path):
    elf, _ = build_linked([("main", NOP)], init_ptrs=["main"])
    report = run_linked(elf, tmp_path)
    assert status(report, "late_initcall_group") == "fail"


def test_late_initcall_table_missing_fails(tmp_path):
    elf, _ = build_linked(DORMANT, init_ptrs=None)
    assert status(run_linked(elf, tmp_path), "late_initcall_group") == "fail"


def test_flat_image_alongside_elf_does_not_double_count_sdk_store(tmp_path):
    body = NOP + le(0x01C8010C)
    elf, _ = build_linked(DORMANT + [("mkey_dummy_func", body)], init_ptrs=["sdk_meky_check"])
    report = run_linked(elf, tmp_path, app=b"\x11" * 16 + body)
    assert status(report, "keycheck_mailbox_unwritten") == "pass"


def test_flat_image_alone_cannot_excuse_a_mailbox_hit(tmp_path):
    p = tmp_path / "app.bin"
    p.write_bytes(b"\x11" * 8 + le(0x01C8010C))
    args = AL.argparse.Namespace(elf=None, app=str(p), objects=None, json=None)
    elves, flat, linked = AL.collect_elves(args)
    report = AL.audit(elves, flat, linked)
    assert status(report, "keycheck_mailbox_unwritten") == "fail"


# ---- sources: IRQ 123 is the SDK's ------------------------------------------

def scan_sources(tmp_path, text):
    d = tmp_path / "src"
    d.mkdir(exist_ok=True)
    (d / "isr.c").write_text(text)
    obj = build_object(symbols=("fm1_isr",))
    p = tmp_path / "obj.o"
    p.write_bytes(obj)
    args = AL.argparse.Namespace(elf=None, app=None, objects=[str(p)], json=None)
    elves, flat, linked = AL.collect_elves(args)
    return AL.audit(elves, flat, linked, AL.collect_sources([d]))


def test_sources_request_irq_123_fails(tmp_path):
    for text in ("request_irq(123, 6, my_isr, 0);", "request_irq( 0x7B , 3, f, 1);",
                 "request_irq((u8)123, 1, f, 0);", "*(volatile u32 *)0x01C801EC = (u32)f;"):
        report = scan_sources(tmp_path, text)
        assert status(report, "irq123_unused_in_sources") == "fail", text


def test_sources_other_irqs_pass(tmp_path):
    report = scan_sources(tmp_path, "request_irq(11, 3, alnk_isr, 0);\nrequest_irq(1234, 0, f, 0);\n")
    assert status(report, "irq123_unused_in_sources") == "pass"


def test_cli_runs_with_sources_and_objects(tmp_path):
    obj = tmp_path / "a.o"
    obj.write_bytes(build_object(symbols=("fm1_ok",)))
    src = tmp_path / "s"
    src.mkdir()
    (src / "ok.c").write_text("int fm1_ok(void) { return 0; }\n")
    out = tmp_path / "r.json"
    assert AL.main(["--objects", str(obj), "--sources", str(src), "--json", str(out)]) == 0
    (src / "bad.c").write_text("void f(void) { request_irq(123, 6, g, 0); }\n")
    assert AL.main(["--objects", str(obj), "--sources", str(src)]) == 1
