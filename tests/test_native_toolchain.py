"""Only an absent target SDK skips optional compile checks."""
import pytest
from tests.native_test_toolchain import configured_target_toolchain

def test_absent_toolchain_is_optional(monkeypatch):
    monkeypatch.delenv("FM1_NATIVE_TOOLCHAIN", raising=False)
    with pytest.raises(pytest.skip.Exception):
        configured_target_toolchain()

def test_configured_path_is_not_silently_skipped(monkeypatch, tmp_path):
    missing = tmp_path / "configured-but-missing"
    monkeypatch.setenv("FM1_NATIVE_TOOLCHAIN", str(missing))
    assert configured_target_toolchain() == missing
