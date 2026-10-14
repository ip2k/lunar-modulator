"""Host-only compiler/linker flags shared by sanitized native probes."""
import sys


def native_host_flags(platform=None):
    """Return platform-correct options for a sanitized host test binary."""
    return ["-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            *native_no_pie_flags(platform), *native_host_link_flags(platform)]


def native_host_link_flags(platform=None):
    """Return section collection appropriate for the host linker."""
    platform = sys.platform if platform is None else platform
    if platform.startswith("linux"):
        return ["-Wl,--gc-sections"]
    if platform == "darwin":
        return ["-Wl,-dead_strip"]
    raise RuntimeError(f"unsupported native test host platform: {platform}")


def native_no_pie_flags(platform=None):
    """Return Linux-only no-PIE switches used to stabilize sanitizer runs."""
    platform = sys.platform if platform is None else platform
    if platform.startswith("linux"):
        return ["-fno-pie", "-no-pie"]
    if platform == "darwin":
        return []
    raise RuntimeError(f"unsupported native test host platform: {platform}")
