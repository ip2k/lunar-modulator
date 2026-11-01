"""Small offline publication probes. No target execution or hardware binding."""
import json
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "firmware/native"
FIXTURE = ROOT / "tests/fixtures/native_publication/check.c"
PROOF = ["-DLUNAR_DIAGNOSTIC_OFFLINE_PROOF=1"]
TARGET = ["-DLUNAR_DIAGNOSTIC_PI32V2_PUBLICATION=1",
          "-DLUNAR_DIAGNOSTIC_CPU0_ONLY=1"]
INJECTED = [*TARGET, "-DLUNAR_DIAGNOSTIC_PUBLICATION_INJECTED=1"]


@pytest.mark.parametrize("sanitized", [False, True])
def test_publication_queue_and_boundaries(tmp_path, sanitized):
    # Include the system declarations first: Darwin's fortified string header
    # otherwise replaces command-line memcpy/memset names with builtins. Only
    # this test wrapper redirects payload work; production source stays intact.
    wrapper = tmp_path / "transport.c"
    wrapper.write_text('''#include <string.h>
#undef memcpy
#undef memset
void *publication_copy(void *, const void *, size_t);
void *publication_zero(void *, int, size_t);
#define memcpy publication_copy
#define memset publication_zero
#include "diagnostic_transport.c"
''')
    outputs = []
    for backend, defines in [("host", []), ("injected", INJECTED)]:
        binary = tmp_path / backend
        flags = ["-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                 "-fno-builtin", *PROOF, *defines, "-I", str(NATIVE)]
        if sanitized:
            flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer"]
        obj = tmp_path / (backend + ".o")
        subprocess.run([os.environ.get("CC", "cc"), *flags,
                        "-c", str(wrapper), "-o", str(obj)], check=True)
        subprocess.run([os.environ.get("CC", "cc"), *flags, str(FIXTURE),
                        str(obj), "-o", str(binary)], check=True)
        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                check=True, timeout=20)
        print(backend, result.stdout, end="")
        outputs.append(json.loads(result.stdout.splitlines()[-1]))
    assert outputs[0] == outputs[1]  # bytes, field offsets, queue results


@pytest.mark.parametrize("defines,diagnostic", [
    ([], "offline proof required"),
    (PROOF, "explicit publication selection required"),
    ([*PROOF, *TARGET], "pi32v2 compiler or injected test required"),
    ([*PROOF, "-DLUNAR_DIAGNOSTIC_PI32V2_PUBLICATION=1",
      "-DLUNAR_DIAGNOSTIC_PUBLICATION_INJECTED=1"], "CPU0-only proof required"),
    ([*PROOF, *INJECTED, "-D__PI32V2__=1"], "injected backend is host test only"),
])
def test_publication_refuses_implicit_binding(tmp_path, defines, diagnostic):
    src = tmp_path / "guard.c"
    src.write_text('#include "diagnostic_publication_pi32v2.h"\n')
    result = subprocess.run([os.environ.get("CC", "cc"), "-std=c11", *defines,
                             "-I", str(NATIVE), "-fsyntax-only", str(src)],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert diagnostic in result.stderr
