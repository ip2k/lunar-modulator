"""The opt-in links a real but disarmed SAVE scheduler; it grants no storage admission."""
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/native"))
import build_application_probe as builder  # noqa: E402


class ProjectSaveServiceOptionTests(unittest.TestCase):
    def test_save_service_is_off_by_default_and_has_no_compile_define(self):
        receipt = builder.project_save_service_configuration(False)
        self.assertEqual(receipt, {
            "linked": False,
            "compile_definition": None,
            "storage_admitted": False,
            "flash_io_bound": False,
            "save_service_armed": False,
            "runtime_verified": False,
            "hardware_tested": False,
        })
        self.assertEqual(builder.project_save_service_flags(False), [])

    def test_explicit_opt_in_has_define_but_stays_disarmed(self):
        receipt = builder.project_save_service_configuration(True)
        self.assertTrue(receipt["linked"])
        self.assertEqual(receipt["compile_definition"], "LUNAR_PROJECT_SAVE_SERVICE=1")
        self.assertFalse(receipt["storage_admitted"])
        self.assertFalse(receipt["flash_io_bound"])
        self.assertFalse(receipt["save_service_armed"])
        self.assertFalse(receipt["runtime_verified"])
        self.assertFalse(receipt["hardware_tested"])
        self.assertEqual(builder.project_save_service_flags(True),
                         ["-DLUNAR_PROJECT_SAVE_SERVICE=1"])

    def test_configuration_rejects_non_boolean_values(self):
        for value in (None, 0, 1, "false", []):
            with self.subTest(value=value):
                with self.assertRaisesRegex(TypeError, "must be a bool"):
                    builder.project_save_service_configuration(value)
                with self.assertRaisesRegex(TypeError, "must be a bool"):
                    builder.project_save_service_flags(value)

    def test_cli_rejects_value_attached_to_flag_before_creating_build(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            tmp_path = Path(temporary)
            build = tmp_path / "out"
            script = ROOT / "tools/native/build_application_probe.py"
            result = subprocess.run(
                [sys.executable, str(script), "--toolchain", str(tmp_path / "tc"),
                 "--catalogue", str(tmp_path / "catalogue"), "--build", str(build),
                 "--link-project-save-service=true"],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("link-project-save-service", result.stderr)
            self.assertFalse(build.exists())

    def test_production_app_binding_is_closed_and_does_not_use_test_wrapper(self):
        app = (ROOT / "firmware/native/app_probe.c").read_text()
        service = (ROOT / "firmware/native/project_save_service.h").read_text()
        builder_source = Path(builder.__file__).read_text()
        test_wrapper = ROOT / "tests/native/project_save_app_target.c"
        initializer = app.split(
            "static lunar_project_save_service save_service = {", 1
        )[1].split("};", 1)[0]
        self.assertIn("pause_ctx", initializer)
        self.assertIn("pause =", initializer)
        self.assertIn("resume =", initializer)
        self.assertNotIn(".io", initializer)
        self.assertNotIn("storage_admitted", initializer)
        self.assertIn("s->storage_admitted == 1", service)
        self.assertIn("s->io.read && s->io.erase && s->io.program && s->io.validate",
                      service)
        self.assertTrue(test_wrapper.is_file())
        self.assertNotIn("tests/native/project_save_app_target.c", builder_source)


if __name__ == "__main__":
    unittest.main()
