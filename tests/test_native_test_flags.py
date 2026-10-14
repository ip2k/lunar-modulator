"""Platform options for native probes preserve sanitizers without GNU ld flags on macOS."""
import pytest

from tests.native_test_flags import (
    native_host_flags,
    native_host_link_flags,
    native_no_pie_flags,
)


def test_linux_native_flags_keep_asan_ubsan_non_pie_and_section_gc():
    flags = native_host_flags("linux")
    assert "-fsanitize=address,undefined" in flags
    assert "-fno-omit-frame-pointer" in flags
    assert "-fno-pie" in flags and "-no-pie" in flags
    assert "-Wl,--gc-sections" in flags


def test_darwin_native_flags_keep_sanitizers_and_use_ld64_dead_strip():
    flags = native_host_flags("darwin")
    assert "-fsanitize=address,undefined" in flags
    assert "-fno-omit-frame-pointer" in flags
    assert "-Wl,-dead_strip" in flags
    assert "-fno-pie" not in flags and "-no-pie" not in flags
    assert "-Wl,--gc-sections" not in flags


@pytest.mark.parametrize("platform", ["win32", "freebsd14"])
def test_unsupported_native_host_platform_is_explicit(platform):
    with pytest.raises(RuntimeError, match="unsupported native test host"):
        native_host_link_flags(platform)
    with pytest.raises(RuntimeError, match="unsupported native test host"):
        native_no_pie_flags(platform)
