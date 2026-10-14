# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools/native/demo_preload_catalogue.py"
SPEC = importlib.util.spec_from_file_location("demo_preload_catalogue", TOOL)
catalogue = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(catalogue)


class DemoPreloadCatalogueTests(unittest.TestCase):
    def test_original_manifest_pin_is_source_introduction_not_receipt(self):
        group = catalogue.ORIGINALS
        commit = group["manifest_commit"]
        changed = subprocess.check_output(
            ["git", "-C", str(ROOT), "diff-tree", "--root", "--no-commit-id",
             "--name-only", "-r", commit], text=True
        ).splitlines()
        self.assertIn(group["manifest_path"], changed)
        manifest = subprocess.check_output(
            ["git", "-C", str(ROOT), "show", f"{commit}:{group['manifest_path']}"]
        )
        self.assertEqual(hashlib.sha256(manifest).hexdigest(),
                         "1c1e003dbb4f25f61209a93600eeaa4659af689900d3c55103c933a475619730")
        inherited = subprocess.check_output([
            "git", "-C", str(ROOT), "show",
            f"{group['receipt_commit']}:{group['manifest_path']}"])
        self.assertEqual(inherited, manifest)

    def test_dependencies_include_master_effects_and_are_raw_engine_ids(self):
        project = {
            "sounds": [
                {"engine": "macro", "inserts": [{"engine": "hall"}],
                 "midi_fx": [{"engine": "arp"}, {"engine": "arp"}]},
                {"engine": "drums", "inserts": [{"engine": "hall"}]},
            ],
            "master": [{"engine": "limit"}, {"engine": "hall"}, {"engine": "hall"}],
            "mod": {"rack": [{"kind": "lfo"}, {"kind": "env"}, {"kind": "lfo"}]},
        }
        self.assertEqual(catalogue._module_dependencies(project), {
            "sound_engines": ["drums", "macro"],
            "audio_effects": ["hall"],
            "master_effects": ["hall", "limit"],
            "midi_effects": ["arp"],
            "modulation_modules": ["env", "lfo"],
        })
        result = catalogue.build_catalogue(str(ROOT))
        for candidate in result["candidates"]:
            self.assertFalse(candidate["dependency_scan_complete"])
            self.assertEqual(candidate["dependency_identifier_kind"], "raw-project-engine-identifiers")
            self.assertIn("verify exact embedded module data and linked image profile with the packed-image decoder",
                          candidate["dependency_admission_requires"])

    def test_runtime_duration_is_usable_only_for_exact_asset_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = pathlib.Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            receipt = {
                "rate": 44118,
                "songs": [{"title": "Song", "projectSha256": "asset-sha", "duration": 42.5}],
            }
            path = repo / "receipt.json"
            path.write_text(json.dumps(receipt))
            subprocess.run(["git", "-C", str(repo), "add", "receipt.json"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "receipt"], check=True)
            revision = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            group = {"receipt_commit": revision, "receipt_path": "receipt.json"}

            exact = catalogue._receipt_for(str(repo), group, "Song", "asset-sha")
            stale = catalogue._receipt_for(str(repo), group, "Song", hashlib.sha256(b"different").hexdigest())

        self.assertEqual(exact["status"], "exact-asset-match")
        self.assertEqual(exact["duration_seconds"], 42.5)
        self.assertEqual(stale["status"], "stale-asset-hash")
        self.assertIsNone(stale["duration_seconds"])

    def test_candidate_slug_is_stable_and_ascii(self):
        self.assertEqual(catalogue._slug("Packet Bloom"), "packet-bloom")
        self.assertEqual(catalogue._slug("Satellite Hearts"), "satellite-hearts")


if __name__ == "__main__":
    unittest.main()
