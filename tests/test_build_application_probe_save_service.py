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
                         ["-DLUNAR_PROJECT_SAVE_SERVICE=1",
                          "-DFM1_STATE_BIN_COMPACT_WRITER=1"])

    def test_compact_codec_uses_catalogue_target_flags_and_writer_mode(self):
        flags = builder.compact_state_bin_flags(
            Path("/toolchain"), Path("/catalogue"), True, 12)
        for expected in (
            ["-target", "pi32v2"], ["-mcpu=r3"], ["-mfprev1"], ["-Oz"],
            ["-flto"], ["-DFM1_TFT_INDEXED=1"], ["-DFM1_SHAPES_VOICES=12"],
            ["-DFM1_STATE_BIN_COMPACT_WRITER=1"],
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected[0], flags)
                if len(expected) == 2:
                    self.assertEqual(flags[flags.index(expected[0]) + 1], expected[1])

    def test_compact_codec_replaces_exactly_one_cached_object(self):
        import tempfile
        from unittest import mock
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cached = root / "shard-12/obj/state/state/state_bin.o"
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"cached")
            objects = [root / "other.o", cached, root / "last.o"]

            def fake_compile(command, **kwargs):
                output = Path(command[command.index("-o") + 1])
                output.write_bytes(b"fresh-compact-codec")
                return mock.Mock(returncode=0)

            with mock.patch.object(builder.subprocess, "run", side_effect=fake_compile) as run:
                receipt = builder.replace_with_compact_state_bin(
                    objects, root / "catalogue", root / "toolchain", root / "build",
                    indexed_tft=True, shapes_voices=12)

            self.assertEqual(objects[0], root / "other.o")
            self.assertEqual(objects[2], root / "last.o")
            self.assertEqual(objects[1], root / "build/state-bin-compact/state_bin.o")
            self.assertEqual(receipt["mode"], "compact-writer")
            self.assertEqual(receipt["cached_object_sha256"], builder.digest(cached))
            self.assertEqual(receipt["fresh_object_sha256"], builder.digest(objects[1]))
            self.assertTrue(receipt["replaced_exactly_one"])
            command = run.call_args.args[0]
            self.assertEqual(command.count("-DFM1_STATE_BIN_COMPACT_WRITER=1"), 1)
            self.assertNotIn(str(cached), command)

    def test_codec_selector_refuses_missing_or_duplicate_cached_objects(self):
        with self.assertRaisesRegex(SystemExit, "found 0"):
            builder.state_bin_object_index([Path("other.o")])
        with self.assertRaisesRegex(SystemExit, "found 2"):
            builder.state_bin_object_index([
                Path("a/state/state/state_bin.o"),
                Path("b/state/state/state_bin.o"),
            ])

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
