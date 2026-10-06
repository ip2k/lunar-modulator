"""Tests for tools/jieli/package_guard.py, the packaging gate that keeps the
FM-1's own SPL, isd_config.ini, ota.bin and cfg in any package (CLAUDE.md
trap 11).

No vendor binary is in the repository, so the tests stage synthetic files and
pass the guard the synthetic SPL's hash. One test checks the real pin against
a local stock unpack when FM1_STOCK_UNPACK points at one (skipped otherwise),
and one checks that the pin agrees with the hash the docs record.
"""
import hashlib
import importlib.util
import os
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location(
        "package_guard", ROOT / "tools" / "jieli" / "package_guard.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PG = load()

FAKE_SPL = b"UBOOT2.00 stand-in " * 16
FAKE_SPL_SHA = hashlib.sha256(FAKE_SPL).hexdigest()
FILES = {
    "top/uboot.boot": FAKE_SPL,
    "top/isd_config.ini": b"[SYS_CFG_PARAM] stand-in",
    "ota.bin": b"usb_hid_ota stand-in",
    "files/cfg": b"JLFS cfg stand-in",
    "files/app.bin": b"our app",
}


def stage(root, overrides=None, drop=()):
    files = dict(FILES)
    files.update(overrides or {})
    for rel, data in files.items():
        if rel in drop:
            continue
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    return root


def check(tmp_path, pkg_over=None, pkg_drop=(), stock_over=None):
    stock = stage(tmp_path / "stock", stock_over)
    pkg = stage(tmp_path / "pkg", pkg_over, pkg_drop)
    return PG.check_package(pkg, stock, spl_sha256=FAKE_SPL_SHA, spl_size=len(FAKE_SPL))


def status(report, key):
    return next(c["status"] for c in report["checks"] if c["check"] == key)


def test_stock_head_passes(tmp_path):
    report = check(tmp_path)
    assert report["passed"] is True, report


def test_foreign_spl_fails(tmp_path):
    report = check(tmp_path, pkg_over={"top/uboot.boot": b"an SDK V1.2.13 uboot.boot"})
    assert report["passed"] is False
    assert status(report, "spl_is_stock") == "fail"


@pytest.mark.parametrize("rel", ["top/isd_config.ini", "ota.bin", "files/cfg"])
def test_changed_head_file_fails(tmp_path, rel):
    report = check(tmp_path, pkg_over={rel: FILES[rel] + b"!"})
    assert report["passed"] is False
    assert status(report, f"identical:{rel}") == "fail"


@pytest.mark.parametrize("rel", ["top/uboot.boot", "top/isd_config.ini", "ota.bin", "files/cfg"])
def test_missing_head_file_fails(tmp_path, rel):
    report = check(tmp_path, pkg_drop=(rel,))
    assert report["passed"] is False


@pytest.mark.parametrize("extra", ["top/uboot_no_ota.boot", "wl82loader.bin", "tools/WL82LOADER.BIN",
                                   "files/usb_loader.bin", "boot/other.boot"])
def test_extra_spl_or_loader_fails(tmp_path, extra):
    report = check(tmp_path, pkg_over={extra: b"x"})
    assert report["passed"] is False
    assert status(report, "no_foreign_spl_or_loader") == "fail"


def test_wrong_stock_reference_fails(tmp_path):
    # A "stock" directory whose SPL is not the FM-1's is refused, even when the
    # package matches it byte for byte.
    other = {"top/uboot.boot": b"not the FM-1 SPL"}
    report = check(tmp_path, pkg_over=other, stock_over=other)
    assert report["passed"] is False
    assert status(report, "stock_reference") == "fail"


def test_cli_exit_codes(tmp_path):
    stock = stage(tmp_path / "stock")
    pkg = stage(tmp_path / "pkg")
    # The real pin, synthetic files: the SPL cannot match, so the CLI fails.
    assert PG.main(["--package", str(pkg), "--stock", str(stock)]) == 1
    assert PG.main(["--package", str(tmp_path / "nope"), "--stock", str(stock)]) == 2


def test_pin_matches_the_documented_hash():
    # docs/09 and the research log record the full SPL hash; the pin must agree.
    for doc in ("docs/09-first-session-checklist.md", "notes/2026-09-06-research-log.md"):
        text = (ROOT / doc).read_text()
        assert PG.STOCK_SPL_SHA256 in text, doc
    assert re.fullmatch(r"[0-9a-f]{64}", PG.STOCK_SPL_SHA256)
    assert PG.STOCK_SPL_SHA256.startswith("730e54f0") and PG.STOCK_SPL_SHA256.endswith("d3ef")


@pytest.mark.skipif(not os.environ.get("FM1_STOCK_UNPACK"),
                    reason="set FM1_STOCK_UNPACK to an unpacked stock .fwsc to check the real SPL")
def test_real_stock_spl_matches_the_pin():
    spl = pathlib.Path(os.environ["FM1_STOCK_UNPACK"]) / "top" / "uboot.boot"
    data = spl.read_bytes()
    assert len(data) == PG.STOCK_SPL_SIZE
    assert hashlib.sha256(data).hexdigest() == PG.STOCK_SPL_SHA256
