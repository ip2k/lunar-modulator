"""Exercise packet imports in isolation, including the physically missing files."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'native_packet_preparer', ROOT / 'tools/fm1_prepare_native_read_packet.py')
PREPARER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARER)

# Import-time and complete-install replay dependencies. Each omission runs in
# its own interpreter; cached repository modules cannot conceal an absent file.
DEPENDENCIES = (
    'fm1_fixed_target_reset.py', 'fm1_fixed_loader_reset.py',
    'fm1_sdk_rehearsal.py', 'fm1_bound_sdk_trace.py',
    'fm1_bound_sdk_diagnostic.py', 'fm1_bound_diagnostic.py',
    'fm1_flash_transaction.py', 'fm1_fixed_loader_backup.py',
    'fm1_uboot_read.py', 'jieli/raw_flash_profile.py',
    'jieli/raw_sdk_diagnostic.py', 'jieli/audit_sdk_diagnostic.py',
    'jieli/audit_link.py', 'jieli/diagnostic_report.py',
    'jieli/inspect_stock_flash.py',
)


def copy_packet(destination):
    destination.mkdir(mode=0o700)
    for relative, expected in PREPARER.TOOL_PINS.items():
        source = ROOT / 'tools' / relative
        target = destination / relative
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        PREPARER.pinned_copy(source, target, expected)
    for relative, expected in PREPARER.REPOSITORY_PINS.items():
        target = destination.parent / relative
        if target.exists():
            assert PREPARER.digest(target.read_bytes()) == expected
            continue
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        PREPARER.pinned_copy(ROOT / relative, target, expected)


def isolated_import(packet):
    program = '''
import hashlib, pathlib, sys
root = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'jieli'))
import fm1_sdk_trace_boot as boot
import fm1_sdk_trace_sg
import fm1_sdk_trace_read
import fm1_sdk_trace_return_admission
import fm1_bound_sdk_trace as policy
runtime, modules = policy.core_modules()
for name, pin in runtime.SOURCES.items():
    assert hashlib.sha256((root / name).read_bytes()).hexdigest() == pin
assert boot.legacy.reset.RESET_CDB.hex() == 'fc0c00000001ffffffffffffffffffff'
'''
    return subprocess.run([sys.executable, '-I', '-S', '-B', '-c', program, str(packet)],
                          capture_output=True, text=True, timeout=30)


def test_complete_packet_imports_without_repository_path(tmp_path):
    packet = tmp_path / 'tools'
    copy_packet(packet)
    result = isolated_import(packet)
    assert result.returncode == 0, result.stderr
    assert len(PREPARER.REPOSITORY_PINS) == 14
    for relative, expected in PREPARER.REPOSITORY_PINS.items():
        assert PREPARER.digest((packet.parent / relative).read_bytes()) == expected
    assert {'fm1_fixed_target_reset.py', 'fm1_fixed_loader_reset.py'} <= PREPARER.TOOL_PINS.keys()


@pytest.mark.parametrize('missing', DEPENDENCIES)
def test_missing_dependency_is_rejected_before_hardware(tmp_path, missing):
    packet = tmp_path / 'tools'
    copy_packet(packet)
    (packet / missing).unlink()
    result = isolated_import(packet)
    assert result.returncode != 0
    assert result.stderr
