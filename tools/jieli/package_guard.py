#!/usr/bin/env python3
"""tools/jieli/package_guard.py -- refuse an FM-1 package whose head is not
the device's own (CLAUDE.md trap 11; notes/2026-10-05-softkey-efuse.md §4.4).

Lunar links JieLi's SDK V1.2.13 *libraries*, but never its SPL or loaders:
only SDK V1.1.9's `uboot.boot` is the FM-1's, and a V1.2.12+ SPL would take
an untested key path on this chip. Any packaging step must call this guard
(or `check_package()`) on its staged tree before it builds a package, and stop
on failure. It asserts:

  1. `top/uboot.boot` is the stock SPL: SHA-256 730e54f0...d3ef, 14,384 bytes
     (the head of every stock package from V13 to FM-1_092, and SDK V1.1.9's
     cpu/wl82/tools/uboot.boot) [verified: docs/02, notes/2026-09-06-*];
  2. `top/isd_config.ini`, `ota.bin` and `files/cfg` are byte-identical to the
     stock package's (the chip key 0x980F, the flash layout and the OTA loader
     stay the device's);
  3. no other SPL or loader is anywhere in the tree: no `*.boot` but
     `top/uboot.boot` (so no `uboot_no_ota.boot`), no `wl82loader*`, nothing
     with "loader" in its name.

The stock reference is a directory with the same four paths: the output of
kagaimiq's `fwunpack_newfw.py` for a stock `.fwsc` (top/, files/) plus the
`ota.bin` entry carved from it (docs/02 §2). Its SPL must match the pin too,
so a wrong "stock" directory is caught rather than trusted.

Reads files only. It talks to no device and sends nothing anywhere. Vendor
binaries are inputs, never committed. MIT licence.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

# The FM-1's SPL (SDK V1.1.9 uboot.boot), as shipped in every stock package.
STOCK_SPL_SHA256 = "730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef"
STOCK_SPL_SIZE = 14384

SPL_PATH = "top/uboot.boot"
IDENTICAL_TO_STOCK = ("top/isd_config.ini", "ota.bin", "files/cfg")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _forbidden(rel):
    """Why a staged file must not be packaged, or None."""
    name = rel.name.lower()
    if rel.as_posix() != SPL_PATH and name.endswith(".boot"):
        return "an SPL other than top/uboot.boot (e.g. an SDK uboot_no_ota.boot)"
    if name.startswith("wl82loader") or "loader" in name:
        return "a loader binary (wl82loader.bin can burn eFuses; never package one)"
    return None


def check_package(package_dir, stock_dir, spl_sha256=STOCK_SPL_SHA256, spl_size=STOCK_SPL_SIZE):
    """Return a report dict: {"passed": bool, "checks": [{check, status, detail}]}.
    status is "pass" or "fail"; any fail means the package must not be built."""
    pkg, stock = Path(package_dir), Path(stock_dir)
    checks = []

    def record(key, ok, detail):
        checks.append(dict(check=key, status="pass" if ok else "fail", detail=detail))

    # 0. The stock reference must itself be the FM-1's.
    ref_spl = stock / SPL_PATH
    if not ref_spl.is_file():
        record("stock_reference", False, f"{ref_spl} missing: not an unpacked stock package")
    else:
        h = _sha256(ref_spl)
        record("stock_reference", h == spl_sha256,
               f"stock {SPL_PATH} sha256 {h[:12]}… "
               + ("matches the FM-1 SPL pin" if h == spl_sha256
                  else f"is not the FM-1 SPL ({spl_sha256[:12]}…): wrong reference directory"))
    missing_ref = [r for r in IDENTICAL_TO_STOCK if not (stock / r).is_file()]
    record("stock_reference_files", not missing_ref,
           f"stock reference lacks {', '.join(missing_ref)}" if missing_ref
           else f"stock reference has {', '.join(IDENTICAL_TO_STOCK)}")

    # 1. The package's SPL is the stock one.
    spl = pkg / SPL_PATH
    if not spl.is_file():
        record("spl_is_stock", False, f"{SPL_PATH} missing from the package")
    else:
        h, n = _sha256(spl), spl.stat().st_size
        ok = h == spl_sha256 and n == spl_size
        record("spl_is_stock", ok,
               f"{SPL_PATH}: {n} B, sha256 {h[:12]}…"
               + ("" if ok else f"; expected {spl_size} B, {spl_sha256[:12]}… "
                  "(never ship an SDK V1.2.x SPL)"))

    # 2. isd_config.ini, ota.bin and cfg byte-identical to stock.
    for rel in IDENTICAL_TO_STOCK:
        mine, ref = pkg / rel, stock / rel
        if not mine.is_file():
            record(f"identical:{rel}", False, f"{rel} missing from the package")
        elif not ref.is_file():
            record(f"identical:{rel}", False, f"{rel} missing from the stock reference")
        else:
            same = mine.read_bytes() == ref.read_bytes()
            record(f"identical:{rel}", same,
                   f"{rel} byte-identical to stock" if same
                   else f"{rel} differs from stock (sha256 {_sha256(mine)[:12]}… vs {_sha256(ref)[:12]}…)")

    # 3. No other SPL or loader anywhere in the staged tree.
    bad = []
    if pkg.is_dir():
        for f in sorted(p for p in pkg.rglob("*") if p.is_file()):
            why = _forbidden(f.relative_to(pkg))
            if why:
                bad.append(f"{f.relative_to(pkg).as_posix()}: {why}")
    record("no_foreign_spl_or_loader", not bad, bad or "no other .boot or loader file")

    return dict(passed=all(c["status"] == "pass" for c in checks), checks=checks)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--package", required=True, help="the staged package tree")
    ap.add_argument("--stock", required=True, help="an unpacked stock FM-1 package (+ ota.bin)")
    ap.add_argument("--json", help="write the report here")
    args = ap.parse_args(argv)
    if not Path(args.package).is_dir() or not Path(args.stock).is_dir():
        print("package_guard: --package and --stock must be directories", file=sys.stderr)
        return 2
    report = check_package(args.package, args.stock)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2))
    for c in report["checks"]:
        d = c["detail"]
        if isinstance(d, list):
            d = d[0] + (f" (+{len(d) - 1} more)" if len(d) > 1 else "")
        print(f"  [{'ok  ' if c['status'] == 'pass' else 'FAIL'}] {c['check']}  {d}")
    print(f"package_guard: {'PASS' if report['passed'] else 'FAIL'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
