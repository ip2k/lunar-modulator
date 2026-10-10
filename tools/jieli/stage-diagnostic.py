#!/usr/bin/env python3
"""MIT. Stage inert application bytes with guarded stock components, no package.

This does not pack, upload or flash firmware. The diagnostic's handover and
observation prerequisites are unfinished; a staged tree is not installable.
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

from audit_link import Elf, audit
from diagnostic_report import report
from package_guard import check_package, SPL_PATH, IDENTICAL_TO_STOCK


def stage(stock, elf_path, app_path, destination):
    stock, destination = Path(stock), Path(destination)
    if destination.exists():
        raise ValueError("destination already exists; choose a new staging directory")
    elf_bytes, app_bytes = Path(elf_path).read_bytes(), Path(app_path).read_bytes()
    link = audit([(str(elf_path), Elf(elf_bytes))], [(str(app_path), app_bytes)],
                 True, runtime="sdk-free")
    layout = report(elf_bytes, app_bytes, link)
    stock_check = check_package(stock, stock)
    if not stock_check["passed"]:
        raise ValueError("stock reference failed package_guard; no staging performed")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".diagnostic-stage-", dir=destination.parent) as temporary:
        staged = Path(temporary)
        for relative in (SPL_PATH,) + IDENTICAL_TO_STOCK:
            target = staged / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stock / relative, target)
        (staged / "files/app.bin").write_bytes(app_bytes)
        guard = check_package(staged, stock)
        if not guard["passed"]:
            raise ValueError("staged tree failed package_guard")
        hashes = {relative: hashlib.sha256((staged / relative).read_bytes()).hexdigest()
                  for relative in (SPL_PATH,) + IDENTICAL_TO_STOCK + ("files/app.bin",)}
        manifest = dict(status="staged-only-not-installable", device_execution="unverified",
                        package_created=False, layout=layout, sha256=hashes,
                        elf_sha256=hashlib.sha256(elf_bytes).hexdigest(),
                        link_audit=link, package_guard=guard,
                        next_gate="establish stock SPL handover and observable diagnostic before a device experiment")
        (staged / "staging-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        # Rename is atomic in this parent directory; no partially validated tree.
        staged.rename(destination)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock", required=True, help="unpacked stock tree plus byte-exact ota.bin")
    parser.add_argument("--elf", required=True)
    parser.add_argument("--app", required=True)
    parser.add_argument("--out", required=True, help="new local staging directory")
    args = parser.parse_args()
    try:
        result = stage(args.stock, args.elf, args.app, args.out)
    except (OSError, ValueError) as exc:
        print(f"stage-diagnostic: {exc}", file=sys.stderr)
        return 1
    print(f"stage-diagnostic: guarded tree at {args.out}; no installable package or device verification")
    print(f"application sha256: {result['sha256']['files/app.bin']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
