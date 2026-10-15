"""Keep local source naming reproducible without changing upstream behavior."""
import hashlib
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "engines/third_party/upstream-engines"


def test_feature_macro_adaptation_is_exact_and_reproducible():
    spec = importlib.util.spec_from_file_location("engine_vendor", SOURCE / "vendor.py")
    vendor = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vendor)
    adapted = (SOURCE / "src/core.h").read_bytes()
    original = adapted.replace(b"LUNAR_SLICE", b"FELUCCA_SLICE").replace(
        b"LUNAR_FM4", b"FELUCCA_FM4")
    assert hashlib.sha256(original).hexdigest() == (
        "1822b8b41853127cd6f21dde363c3627f4dbd234f603618c0feb2dcdd4c02a3c")
    assert vendor.local_source("firmware/src/core.h", original) == adapted
    assert vendor.local_source("firmware/src/core.h", adapted) == adapted
    assert vendor.local_source("firmware/src/dsp.c", original) == original
    assert b"FELUCCA_" not in adapted
