#!/usr/bin/env python3
"""Offline private SDK diagnostic build. Never packages, downloads or flashes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import secrets
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
PIN = "e30b1ee375d1f2993fc23bf92c8b99006a6e5f9d"
STAGE_SHA256 = "3c58c0bb8ab885f0bf620b2a9e871ee97f771b5563c3dfabb3ecf0436410beb2"
SECTIONS = (".text", ".data", ".dynamic_data", ".ram0_data", ".cache_ram_data")

def make_list(text, name):
    match = re.search(r"^" + re.escape(name) + r"\s*:=\s*\\\n((?:.*\\\n)*)", text, re.M)
    if not match:
        raise ValueError("Missing pinned Makefile list: " + name)
    return match[1].replace("\\\n", " ").split()

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def verify_stage(sdk):
    marker = sdk / ".lunar-sdk-stage.json"
    if not marker.is_file():
        raise ValueError("Missing pinned SDK stage manifest")
    if sha(marker) != STAGE_SHA256:
        raise ValueError("Pinned SDK stage manifest hash mismatch")
    stage = json.loads(marker.read_text())
    if stage.get("schema") != 1 or stage.get("private_build_input") is not True:
        raise ValueError("Unsupported or non-private SDK stage manifest")
    if stage.get("revision") != PIN:
        raise ValueError("SDK stage revision mismatch")
    files = stage["files"]
    actual = {str(p.relative_to(sdk)): sha(p) for p in sdk.rglob("*") if p.is_file() and p != marker}
    if actual != files:
        bad = sorted(set(actual) ^ set(files) | {p for p in actual.keys() & files.keys() if actual[p] != files[p]})
        raise ValueError("SDK staged byte inventory differs: " + ", ".join(bad[:20]))
    return stage

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--toolchain", type=Path, required=True, help="20250324.1 pi32v2/bin")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-commit", help="Recorded source SHA when using an isolated rsync source stage")
    parser.add_argument("--recovery-trace", action="store_true", help="Enable diagnostic-only owned RAM recovery phases")
    parser.add_argument("--recovery-trace-nonce", help="Explicit 128-bit hex nonce for reproducible comparison; otherwise freshly generated")
    args = parser.parse_args()
    if args.recovery_trace_nonce is not None and not args.recovery_trace:
        parser.error("--recovery-trace-nonce requires --recovery-trace")
    if args.recovery_trace_nonce is not None and not re.fullmatch(r"[0-9a-fA-F]{32}", args.recovery_trace_nonce):
        parser.error("Recovery trace nonce must be exactly 32 hexadecimal digits")
    nonce = (args.recovery_trace_nonce or secrets.token_hex(16)).lower() if args.recovery_trace else None
    sdk, tc, out = (p.resolve() for p in (args.sdk, args.toolchain, args.out))
    if sdk == out or sdk in out.parents or ROOT == out or out == tc or tc in out.parents:
        parser.error("Output must be separate from SDK, source root and toolchain")
    if "20250324.1" not in str(tc):
        parser.error("Only owner-selected vendor 20250324.1 is permitted")
    out.mkdir(parents=True, exist_ok=True)
    manifest = out / "build-manifest.json"
    manifest.write_text(json.dumps({"status": "BUILDING_OR_FAILED", "flashable": False}) + "\n")
    with (out / "build.log").open("w") as log:
        def run(cmd):
            result = subprocess.run(list(map(str, cmd)), cwd=out, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True)
            log.write(" ".join(map(str, cmd)) + "\n" + result.stdout)
            log.flush()
            if result.returncode:
                raise RuntimeError(result.stdout[-9000:])
            return result.stdout
        stage = verify_stage(sdk)
        make = sdk / "apps/demo/demo_hello/board/wl82/Makefile"
        text = make.read_text()
        flags = make_list(text, "CFLAGS")
        defines = make_list(text, "DEFINES") + ["-D__SHELL__", "-DLUNAR_PI32V2"]
        if args.recovery_trace:
            defines.append("-DLUNAR_SDK_RECOVERY_TRACE")
            nonce_header = out / "recovery_trace_nonce.h"
            raw_nonce = bytes.fromhex(nonce)
            nonce_header.write_text("/* Generated private image nonce, little-endian words. */\n" +
                "".join(f"#define LUNAR_SDK_RECOVERY_NONCE_{i} 0x{int.from_bytes(raw_nonce[i*4:i*4+4], 'little'):08x}u\n" for i in range(4)))
        owned = ROOT / "firmware/sdk-diagnostic"
        includes = ["-I" + str(p) for p in (owned, owned / "third_party/fm1-nes", ROOT / "firmware/display", ROOT / "firmware/recovery")]
        if args.recovery_trace:
            includes.append("-I" + str(out))
        includes += ["-I" + str((make.parent / p[2:]).resolve()) for p in make_list(text, "INCLUDES")]
        sources = [(make.parent / p).resolve() for n in ("c_SRC_FILES", "S_SRC_FILES") for p in make_list(text, n)]
        sources = [p for p in sources if p.name not in ("app_main.c", "board.c", "cpp_run_init.c")]
        sources += [owned / "board.c", owned / "app_main.c", owned / "third_party/fm1-nes/board_power.c",
                    ROOT / "firmware/third_party/fm1-nes/boot_compat.c",
                    ROOT / "firmware/display/panel_probe.c", ROOT / "firmware/display/spi1_transport.c",
                    ROOT / "firmware/recovery/request.c"]
        if args.recovery_trace:
            sources.append(owned / "recovery_trace.c")
        libs = [sdk / "include_lib/newlib/pi32v2-lib" / n for n in ("libm.a", "libc.a", "libcompiler_rt.a")]
        libs += [sdk / "cpu/wl82/liba" / n for n in ("cpu.a", "event.a", "system.a", "cfg_tool.a", "fs.a", "common_lib.a", "update.a")]
        for p in sources + libs:
            if not p.is_file():
                raise ValueError("Missing staged dependency: " + str(p))
        for source, name in ((sdk / "cpu/wl82/sdk_ld.c", "sdk.ld"), (sdk / "cpu/wl82/sdk_used_list.c", "sdk.used")):
            run([tc / "clang", *flags, *defines, *includes, "-D__LD__", "-E", "-P", source, "-o", out / name])
        used = out / "sdk.used"
        used.write_text(used.read_text() + "\napp_main\nlunar_panel_probe\ndiagnostic_worker\np33_lock\np33_unlock\nsys_local_irq_disable\nsys_local_irq_enable\n")
        if args.recovery_trace:
            used.write_text(used.read_text() + "\nlunar_sdk_recovery_trace_record\nlunar_sdk_recovery_trace_init\n"
                "lunar_sdk_recovery_trace_before_lock\nlunar_sdk_recovery_trace_phase\n"
                "lunar_sdk_recovery_trace_mailbox_verified\nlunar_sdk_recovery_trace_final_start_intent\n")
        ld = (out / "sdk.ld").read_text()
        for old, new in (("*(.data)", "*(.data .data.*)"), ("*(.bss)", "*(.bss .bss.*)"),
                         ("*(.syscfg.1.ops)", "/* excluded persistent cfg repair */"),
                         ("*(.syscfg.2.ops)", "/* excluded persistent cfg repair */")):
            if ld.count(old) != 1:
                raise ValueError("Pinned link-script expectation changed: " + old)
            ld = ld.replace(old, new)
        ld += "\nSECTIONS { /DISCARD/ : { *(.syscfg.1.ops) *(.syscfg.2.ops) } }\n"
        (out / "sdk.ld").write_text(ld)
        objects = []
        for i, source in enumerate(sources):
            obj = out / (str(i) + "-" + source.name + ".o")
            run([tc / "clang", *flags, *defines, *includes, "-c", source, "-o", obj])
            objects.append(obj)
        elf = out / "lunar-sdk-diagnostic.elf"
        run([tc / "lto-wrapper", "-o", elf, *objects, "--start-group", *libs, "--end-group",
             "-T" + str(out / "sdk.ld"), "-M=" + str(out / "lunar-sdk-diagnostic.map"),
             "--wrap=boot_info_init", "--plugin-opt=mcpu=r3", "--plugin-opt=-mattr=+fprev1",
             "--plugin-opt=-pi32v2-large-program=true", "--plugin-opt=-used-symbol-file=" + str(out / "sdk.used")])
        parts = []
        for section in SECTIONS:
            part = out / (section[1:] + ".bin")
            run([tc / "objcopy", "-O", "binary", "-j", section, elf, part])
            parts.append(part.read_bytes())
        app = out / "lunar-sdk-diagnostic.app.bin"
        app.write_bytes(b"".join(parts))
        (out / "symbols.txt").write_text(run([tc / "nm", "-n", "-S", elf]))
        (out / "disassembly.asm").write_text(run([tc / "objdump", "-d", "-mcpu=r3", elf]))
        run([sys.executable, ROOT / "tools/jieli/audit_link.py", "--elf", elf, "--app", app,
             "--sources", owned, "--runtime", "sdk", "--json", out / "key-link-audit.json"])
        run([sys.executable, ROOT / "tools/jieli/audit_sdk_diagnostic.py", "--elf", elf,
             "--app", app, "--json", out / "sdk-image-audit.json"])
        result = {"status": "LINKED_PRIVATE_DIAGNOSTIC_UNTESTED", "flashable": False,
                  "sdk_commit": PIN, "sdk_stage_manifest_sha256": sha(sdk / ".lunar-sdk-stage.json"),
                  "source_commit": args.source_commit or run(["git", "-C", ROOT, "rev-parse", "HEAD"]).strip(),
                  "toolchain": str(tc),
                  "toolchain_sha256": {name: sha(tc / name) for name in ("clang", "lto-wrapper", "objcopy", "objdump", "nm")},
                  "application_bytes": app.stat().st_size,
                  "application_sha256": sha(app), "elf_sha256": sha(elf),
                  "device_operations_performed": False, "recovery_integrated": True,
                  "recovery_trace": {"enabled": args.recovery_trace, "schema": 1 if args.recovery_trace else None,
                                     "nonce_hex": nonce, "record_bytes": 64 if args.recovery_trace else None,
                                     "startup_reason": "unavailable_sentinel" if args.recovery_trace else None},
                  "source_sha256": {str(p): sha(p) for p in sources + list(owned.rglob("*.h"))},
                  "build_audit_sha256": {str(p.relative_to(ROOT)): sha(p) for p in
                      (Path(__file__).resolve(), ROOT / "tools/jieli/audit_sdk_diagnostic.py",
                       ROOT / "tools/jieli/audit_link.py")},
                  "archive_sha256": {str(p): sha(p) for p in libs},
                  "cflags": flags, "defines": defines, "flat_section_order": SECTIONS,
                  "pending": ["SDK P33 lock requires a healthy other core",
                              "stock-SPL cold boot, hardware panel and observed UBOOT"]}
        manifest.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({k: v for k, v in result.items() if k not in ("source_sha256", "archive_sha256", "cflags", "defines")}, indent=2))

if __name__ == "__main__":
    main()
