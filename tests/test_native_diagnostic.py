"""Offline source-bound diagnostic builder guards; no toolchain or device needed."""
import importlib.util
import json
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_diagnostic', ROOT / 'tools/native/build_diagnostic.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_inventory_rejects_changed_source(tmp_path):
    source = tmp_path / 'unit.c'
    source.write_text('int value;\n')
    (tmp_path / 'inventory.json').write_text(json.dumps({'files': {'unit.c': builder.digest(source)}}))
    builder.check_inventory(tmp_path)
    source.write_text('int changed;\n')
    with pytest.raises(ValueError, match='source pin mismatch'):
        builder.check_inventory(tmp_path)


def test_current_input_manifest_and_vendor_pins():
    inputs = builder.manifest()
    for name in ['tools/native/build_diagnostic.py', 'tools/jieli/audit_link.py',
                 'firmware/native/diagnostic_api.h', 'sim/web/src/fm1_app.c',
                 'engines/mk/mod.mk']:
        assert inputs[name] == builder.digest(ROOT / name)
    assert not any('__pycache__' in p or p.endswith('.o') for p in inputs)
    for name in ['dinghy', 'compiler-rt', 'musl', 'printf']:
        builder.check_inventory(ROOT / 'firmware/third_party' / name)
