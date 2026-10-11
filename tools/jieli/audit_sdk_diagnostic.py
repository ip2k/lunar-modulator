#!/usr/bin/env python3
"""SDK flat-image/ELF contract; complements, never replaces, audit_link.py."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from audit_link import Elf, SHT_NOBITS, EM_PI32V2, ET_EXEC

LAYOUT = ((".text", "text_begin"), (".data", "data_lma"),
          (".dynamic_data", "dynamic_data_lma"), (".ram0_data", "_ram0_data_lma"),
          (".cache_ram_data", "cache_ram_data_lma"))

INITCALLS = {
    "early_initcall": ("app_version_check", "sys_event_init", "thread_fork_init", "sdfile_init"),
    "platform_initcall": ("syscfg_tools_init",),
    "initcall": ("app_update_init",),
    "module_initcall": ("wait_completion_init",),
    "late_initcall": ("sdk_meky_check",),
}

def registration_contract(elf):
    tables = {}
    for group, names in INITCALLS.items():
        lo, hi = (elf.symbol_value(group + suffix) for suffix in ("_begin", "_end"))
        values = tuple(elf.symbol_value(name) for name in names)
        if None in values or lo is None or hi != lo + 4 * len(names):
            raise ValueError("Startup registry bounds changed: " + group)
        if elf.read(lo, hi - lo) != struct.pack("<" + "I" * len(values), *values):
            raise ValueError("Startup registry members changed: " + group)
        tables[group] = list(names)
    lo, hi = (elf.symbol_value("syscfg_ops" + suffix) for suffix in ("_begin", "_end"))
    names = ("syscfg_file_init", "syscfg_bin_check_id", "syscfg_bin_read", None,
             None, "syscfg_bin_group_read", "syscfg_bin_ptr_read")
    values = tuple(0 if name is None else elf.symbol_value(name) for name in names)
    if None in values or lo is None or hi != lo + 28 or elf.read(lo, 28) != struct.pack("<7I", *values):
        raise ValueError("Read-only file cfg registration changed")
    return {"initcalls": tables, "syscfg_callbacks": list(names),
            "persistent_cfg_writer_registered": False,
            "automatic_NOR_mutation_review": "pending independent reachable-path review"}

def reconstruct(elf):
    image = bytearray()
    rows = []
    for name, symbol in LAYOUT:
        matches = [s for s in elf.sections if s["name"] == name]
        if len(matches) != 1:
            raise ValueError("Expected exactly one section " + name)
        section = matches[0]
        expected = 0x02000120 + len(image)
        lma = elf.symbol_value(symbol)
        if lma != expected:
            raise ValueError(f"{name} LMA {lma!r} != contiguous {expected:#x}")
        if section["type"] == SHT_NOBITS and section["size"]:
            raise ValueError(name + " contains uninitialized image bytes")
        data = elf.data[section["offset"]:section["offset"] + section["size"]]
        if len(data) != section["size"]:
            raise ValueError(name + " is truncated")
        rows.append({"section": name, "vma": section["addr"], "lma": lma,
                     "image_offset": len(image), "bytes": len(data)})
        image.extend(data)
    return bytes(image), rows

def instruction_contract(elf):
    """Reviewed 20250324.1 instructions, with relocated operands regenerated.

    References: pinned SDK startup.S/irq.c/p33.h; independent vendor objdump
    review in build/startup-resolution-goal.md. Keitark's Apache audit_boot.py
    identifies the same boot and integrity contracts; no hardware claim.
    """
    def value(name):
        result = elf.symbol_value(name)
        if result is None:
            raise ValueError("Missing instruction contract symbol " + name)
        return result
    def code(name, expected):
        if elf.read(value(name), len(expected)) != bytes(expected):
            raise ValueError("Reviewed instruction sequence changed: " + name)
    def long_call(site, target):
        return b"\x80\xff" + struct.pack("<i", target - site - 6)
    def short_call(site, target):
        near = target - site - 2
        if -512 <= near < 512 and near % 2 == 0:
            return bytes([(0x81 + (near // 64) * 16) & 255, 0x80 + ((near // 2) % 32)])
        delta = (target - site - 4) // 2
        if not -(1 << 21) <= delta < (1 << 21):
            raise ValueError("Short call out of range")
        return bytes([0x80 | ((delta >> 16) & 63), 0xea]) + struct.pack("<H", delta & 65535)
    def word(name):
        return struct.pack("<I", value(name))
    startup = value("chip_entry")
    expected = bytearray.fromhex(
        "ee ff 00 00 00 00 ed ff 00 00 00 00 80 ff 00 00 00 00 "
        "c3 ff 00 00 00 00 41 20 c2 ff 00 00 00 00 a2 a2 02 03 b1 05 f2 5d "
        "c4 ff 00 00 00 00 c1 ff 00 00 00 00 c2 ff 00 00 00 00 a2 a2 "
        "12 03 13 05 c3 05 f2 5c 80 ff 00 00 00 00 03 16 "
        "c0 ff 20 01 00 04 c1 ff 00 00 00 00 c2 ff 00 00 00 00 "
        "01 e8 04 00 80 ff 00 00 00 00 30 16 c3 ff 20 01 00 04 "
        "41 20 c2 ff 00 00 00 00 a2 a2 02 03 b1 05 f2 5d "
        "80 ff 00 00 00 00 80 ff 00 00 00 00 80 ff 00 00 00 00 "
        "c6 ff 00 00 00 00 d6 00")
    for offset, name in ((2, "_cpu0_ustack"), (8, "_cpu0_sstack"),
                         (20, "_ram0_bss_vma"), (28, "_ram0_bss_size"),
                         (42, "_ram0_data_vma"), (48, "_ram0_data_lma"),
                         (54, "_ram0_data_size"), (84, "_ram0_data_lma"), (148, "main")):
        expected[offset:offset+4] = word(name)
    for offset, name in ((12, "__wrap_boot_info_init"), (68, "boot_init_after_ram_ready"),
                         (98, "boot_memmove"), (128, "cache_way_config"),
                         (134, "memory_init"), (140, "update_result_get")):
        expected[offset:offset+6] = long_call(startup+offset, value(name))
    if startup != 0x0200018a or elf.read(0x02000120, 2) != bytes.fromhex("14 94"):
        raise ValueError("Stock entry branch changed")
    code("chip_entry", expected)
    bridge = value("__wrap_boot_info_init")
    code("__wrap_boot_info_init", bytes.fromhex(
        "10 04 e2 89 41 20 04 86 d8 ec 0a 21 8b 80 d8 ec 3b 21 c1 21 "
        "81 f8 f8 0d 40 26 41 20 04 84 8a 80 d8 ec 2b 10 c0 21 "
        "80 f8 fa 2f 88 80") + long_call(bridge+44, value("boot_info_init")) + bytes.fromhex("02 97 00 04"))
    bss = next(s for s in elf.sections if s["name"] == ".ram0_bss")
    if not (bss["addr"] <= value("_cpu0_ustack")-96 and
            value("_cpu0_ustack")+4096 == value("_cpu0_sstack") <= value("_cpu1_ustack")-96 and
            value("_cpu1_ustack")+4096 == value("_cpu1_sstack") <= bss["addr"]+bss["size"]):
        raise ValueError("SDK stack bounds changed")
    if value("_ram0_data_size") % 4 or value("_ram0_bss_size") % 4:
        raise ValueError("SDK copy/clear loops not word-aligned")
    code("cpu1_start", b"\xec\xff"+word("_cpu1_ustack")+b"\xee\xff"+word("_cpu1_sstack")+
         b"\xe0\xff"+word("cpu1_main")+bytes.fromhex("81 00"))
    exc = value("exception_irq_handler")
    code("exception_irq_handler", bytes.fromhex("70 e8 00 00 58 e9 2f 78 d8 e8 ff ff 64 e0 00 0e")+
         long_call(exc+16, value("exception_analyze"))+bytes.fromhex("f7 9f"))
    debug = value("debug_init")
    code("debug_init", bytes.fromhex("78 04 64 e0 00 76 c2 ff")+word("exception_irq_handler")+
         bytes.fromhex("40 21 41 27 7b 3f")+short_call(debug+18, value("request_irq")))
    integrity = value("sdk_meky_check")
    code("sdk_meky_check", bytes.fromhex("74 04 c4 ff")+word("isr_check_key")+
         bytes.fromhex("58 3b 41 26 43 20 42 16")+long_call(integrity+16,value("request_irq"))+
         bytes.fromhex("58 3b 41 26 43 21 42 16")+long_call(integrity+30,value("request_irq"))+
         bytes.fromhex("c0 ff 3c f1 ee 01 c0 ef 80 0d 00 e1 00 02 c0 ef 80 0d")+
         long_call(integrity+54,value("sys_timeout_add"))+bytes.fromhex("54 04"))
    timer = value("sys_timeout_add")
    code("sys_timeout_add", bytes.fromhex("10 04")+long_call(timer+2,value("os_current_task"))+
         b"\xc1\xff"+word("_mkey_check")+bytes.fromhex("42 e0 40 1f 43 21")+
         short_call(timer+20,value("__sys_timer_add"))+bytes.fromhex("00 04"))
    if elf.read(value("puk"), 4) != bytes.fromhex("98 36 6c f3"):
        raise ValueError("SDK unregistered-key sentinel changed")
    if elf.read(value("_mkey_check")+0xfe, 14) != bytes.fromhex(
            "d0 ec 90 00 c5 ff 98 36 6c f3 05 e8 54 00"):
        raise ValueError("SDK no-key-registered return branch changed")
    lock = value("p33_lock")
    unlock = value("p33_unlock")
    lock_code = elf.read(lock, 26)
    if lock_code is None or lock_code[:2] != bytes.fromhex("10 04"):
        raise ValueError("P33 lock prologue changed")
    # Link-local static symbol suffix varies when another source is added;
    # derive its address only from the verified literal-load position.
    lock_addr, = struct.unpack_from("<I", lock_code, 8)
    if not bss["addr"] > lock_addr >= 0x01c00000:
        raise ValueError("P33 lock is outside initialized SDK RAM data")
    code("p33_lock", bytes.fromhex("10 04")+short_call(lock+2,value("__local_irq_disable"))+
         bytes.fromhex("20 00 c0 ff")+struct.pack("<I",lock_addr)+
         bytes.fromhex("b0 00 40 e8 fd ff 20 00 00 04"))
    code("p33_unlock", bytes.fromhex("10 04 20 00 c0 ff")+struct.pack("<I",lock_addr)+
         bytes.fromhex("41 20 89 40")+short_call(unlock+14,value("__local_irq_enable"))+bytes.fromhex("00 04"))
    code("__local_irq_disable", bytes.fromhex("60 00 64 e0 00 06 00 a2 c1 ff")+
         word("irq_lock_cnt")+bytes.fromhex("10 18 c0 eb 01 00 20 00 80 00"))
    code("__local_irq_enable", bytes.fromhex("64 e0 00 06 c1 ff")+word("irq_lock_cnt")+
         bytes.fromhex("d8 ec 1a 20 fa 3f d8 ec 1b 20 82 42 20 00 61 00 80 00"))
    return {"startup_bridge_stacks_exception": "verified_instructions",
            "sdk_integrity_scheduling": "two_IRQ123_registrations_then_8000ms_callback",
            "p33_ownership": "SDK_atomic_lock_and_nested_per_core_IRQ_mask",
            "p33_lock_address": lock_addr, "p33_lock_acquisition_bounded": False,
            "runtime_result_verified": False}

def audit(elf_data, app):
    elf = Elf(elf_data)
    entry, = struct.unpack_from("<I", elf_data, 24)
    if elf.e_type != ET_EXEC or elf.e_machine != EM_PI32V2 or entry != 0x02000120:
        raise ValueError("Expected pi32v2 executable with stock app entry 0x02000120")
    rebuilt, rows = reconstruct(elf)
    if app != rebuilt:
        raise ValueError("Flat image differs from SDK section/LMA reconstruction")
    if len(app) > 691744:
        raise ValueError("Application exceeds FM-1_092 APP_BYTES=691744")
    for section in elf.sections:
        if section["flags"] & 2 and section["size"]:
            lo, hi = section["addr"], section["addr"] + section["size"]
            if lo < 0x01c7fd90 and hi > 0x01c7fd80:
                raise ValueError("Allocated section overlaps stock recovery marker")
            if section["name"] in (".syscfg.1.ops", ".syscfg.2.ops"):
                raise ValueError("Persistent cfg writer section survived")
    if elf.undefined_symbols():
        raise ValueError("Unresolved ELF symbols: " + ", ".join(sorted(elf.undefined_symbols())))
    required = ("chip_entry", "__wrap_boot_info_init", "boot_info_init", "cpu1_main",
                "app_main", "sdk_meky_check", "fm1_stock_power_param", "lunar_panel_probe")
    missing = [name for name in required if elf.symbol_value(name) is None]
    if missing:
        raise ValueError("Required startup/diagnostic symbol absent: " + ", ".join(missing))
    power = elf.read(elf.symbol_value("fm1_stock_power_param"), 20)
    if power is None or power != bytes.fromhex("000000000000000000000000040307010f000701"):
        raise ValueError("Stock-derived SDK power parameter bytes differ")
    return {"passed": True, "flashable": False, "entry": entry, "sections": rows,
            "application_sha256": hashlib.sha256(app).hexdigest(),
            "instruction_contract": instruction_contract(elf),
            "registration_contract": registration_contract(elf),
            "undefined_symbols": [], "app_capacity_bytes": 691744,
            "startup_symbols": {name: elf.symbol_value(name) for name in required},
            "pending": ["P33 lock requires healthy SDK runtime",
                        "stock-SPL cold boot and observed UBOOT", "actual panel output"]}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--json", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.elf.read_bytes(), args.app.read_bytes())
    args.json.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
