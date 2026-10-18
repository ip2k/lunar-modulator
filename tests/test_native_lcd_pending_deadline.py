# SPDX-License-Identifier: GPL-3.0-only
"""Host C harness for the exact production display integration, no devices."""
from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LcdPendingDeadlineTest(unittest.TestCase):
    def test_production_display_and_all_profile_combinations(self):
        compiler = shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("host C compiler unavailable; target compilation is separate")
        source = (ROOT / "firmware/native/app_probe.c").read_text()
        start = source.index("static lunar_lcd_pending_deadline_t lcd_pending_deadline;")
        function = source.index("static void display_strip(uint32_t *row)", start)
        end = source.index("{", function) + 1
        depth = 1
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        with tempfile.TemporaryDirectory(prefix="lunar-lcd-deadline-") as temp:
            out = Path(temp)
            (out / "display_strip_exact.h").write_text(source[start:end] + "\n")
            for render, gaps in ((False, False), (True, False), (False, True), (True, True)):
                with self.subTest(render_profile=render, producer_gaps=gaps):
                    binary = out / f"lcd-{int(render)}-{int(gaps)}"
                    flags = []
                    if render:
                        flags.append("-DLUNAR_RENDER_STAGE_PROFILE=1")
                    if gaps:
                        flags.append("-DLUNAR_DIAGNOSTIC_PRODUCER_GAPS=1")
                    if os.environ.get("LUNAR_HOST_SANITIZERS") == "1":
                        flags += ["-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                                  "-fno-pie", "-no-pie"]
                    subprocess.run([compiler, "-std=c99", "-O1", "-g", "-Wall",
                        "-Wextra", "-Werror", *flags,
                        "-I", str(ROOT / "firmware/native"),
                        "-I", str(ROOT / "sim/web/src"), "-I", str(out),
                        str(ROOT / "tests/native/lcd_pending_deadline_test.c"),
                        "-o", str(binary)], check=True, capture_output=True, text=True)
                    result = subprocess.run([str(binary)], check=True, timeout=10,
                                            capture_output=True, text=True)
                    self.assertIn("production integration PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
