# SPDX-License-Identifier: MIT
"""Focused tests for the offline request contract and its refusal boundaries."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools.installer_service.request_contract import (
    MAX_REQUEST_BYTES,
    canonical_request,
    main,
    result_for,
    validate_request,
)


CATALOGUE = {
    "version": 1,
    "groups": {
        "engines": ["macro", "shapes", "sixop", "drums", "trio"],
        "effects": ["hall", "reverb"],
        "midi": ["arp"],
        "modulation": ["lfo"],
    },
    "projects": [
        {"id": "song-a"}, {"id": "song-b"},
    ],
    "sets": [
        {"id": "song-a-set", "parent_project_id": "song-a"},
        {"id": "song-b-set", "parent_project_id": "song-b"},
    ],
    "installable": False,
}


def catalogue_bytes():
    return json.dumps(CATALOGUE).encode()


def request(**changes):
    value = {
        "version": 1,
        "engines": ["trio"],
        "effects": [],
        "midi": [],
        "modulation": [],
        "project_ids": ["song-a"],
        "startup_index": 0,
    }
    value.update(changes)
    return json.dumps(value, separators=(",", ":")).encode()


class InstallerRequestContractTests(unittest.TestCase):
    def test_accepts_actual_generated_default_catalogue_and_request(self):
        fixture = Path(__file__).parent / "fixtures" / "installer-request-catalogue.json"
        catalogue_data = fixture.read_bytes()
        catalogue = json.loads(catalogue_data)
        request_data = json.dumps(catalogue["default_build_request"]).encode()
        normalized = validate_request(request_data, catalogue_data)
        self.assertEqual(sum(len(ids) for ids in catalogue["groups"].values()), 55)
        self.assertEqual(len(catalogue["projects"]), 11)
        self.assertEqual(len(catalogue["sets"]), 1)
        self.assertEqual(len(normalized["engines"] + normalized["effects"] + normalized["midi"] + normalized["modulation"]), 55)
        self.assertFalse(result_for(normalized)["installable"])

    def test_valid_minimal_request_matches_reference_canonical_bytes(self):
        normalized = validate_request(request(), catalogue_bytes())
        expected = b'{"effects":[],"engines":["trio"],"midi":[],"modulation":[],"project_ids":["song-a"],"startup_index":0,"version":1}\n'
        self.assertEqual(canonical_request(normalized), expected)

    def test_explicit_empty_set_list_is_elided_like_api_default(self):
        normalized = validate_request(request(set_ids=[]), catalogue_bytes())
        self.assertNotIn("set_ids", normalized)
        self.assertEqual(canonical_request(normalized), canonical_request(
            validate_request(request(), catalogue_bytes())))

    def test_valid_companion_set_is_bound_to_startup_project(self):
        normalized = validate_request(
            request(set_ids=["song-a-set"]), catalogue_bytes())
        self.assertEqual(normalized["set_ids"], ["song-a-set"])

    def test_valid_expanded_continuous_request_is_preserved(self):
        normalized = validate_request(request(
            engines=["macro", "shapes", "sixop", "drums"], effects=["hall"],
            project_ids=["song-a"], set_ids=["song-a-set"],
            flash_layout="expanded-d7000", runtime_mode="continuous"),
            catalogue_bytes())
        self.assertEqual(normalized["runtime_mode"], "continuous")
        self.assertFalse(result_for(normalized)["installable"])

    def test_refuses_unknown_fields(self):
        self.refuses(request(extra="unexpected"))

    def test_refuses_wrong_group_and_unknown_module_ids(self):
        self.refuses(request(engines=["hall"]))
        self.refuses(request(engines=["not-in-catalogue"]))

    def test_refuses_test_module(self):
        catalogue = json.loads(catalogue_bytes())
        catalogue["groups"]["engines"].append("test-debug")
        self.refuses(request(engines=["test-debug"]), json.dumps(catalogue).encode())

    def test_refuses_unknown_project_or_set(self):
        self.refuses(request(project_ids=["missing"]))
        self.refuses(request(set_ids=["missing-set"]))

    def test_refuses_set_from_a_non_startup_project(self):
        self.refuses(request(project_ids=["song-a", "song-b"], startup_index=0,
                             set_ids=["song-b-set"]))

    def test_refuses_duplicate_keys_at_any_object_depth(self):
        duplicate_request = b'{"version":1,"version":1}'
        self.refuses(duplicate_request)
        nested_catalogue = b'{"groups":{},"groups":{}}'
        self.refuses(request(), nested_catalogue)

    def test_refuses_non_object_malformed_nonfinite_and_oversized_json(self):
        for raw in (b"[]", b"{bad", b'{"version":NaN}',
                    b" " * (MAX_REQUEST_BYTES + 1)):
            with self.subTest(raw=raw[:16]):
                self.refuses(raw)

    def test_accepts_finite_nested_catalogue_metadata(self):
        catalogue = json.loads(catalogue_bytes())
        catalogue["projects"][0]["metadata"] = {"ratio": 1.25e2, "underflow": 1e-9999}
        normalized = validate_request(request(), json.dumps(catalogue).encode())
        self.assertEqual(normalized["project_ids"], ["song-a"])

    def test_refuses_positive_and_negative_overflow_in_nested_catalogue_metadata(self):
        base = catalogue_bytes()
        for number in (b"1e9999", b"-1e9999"):
            with self.subTest(number=number):
                raw = base.replace(b'"id": "song-a"',
                                   b'"id": "song-a", "metadata": {"value": ' + number + b'}',
                                   1)
                self.refuses(request(), raw)

    def test_refuses_boolean_or_coerced_integer_fields(self):
        self.refuses(request(version=True))
        self.refuses(request(startup_index="0"))

    def test_refuses_duplicate_ids_and_invalid_runtime_combinations(self):
        self.refuses(request(engines=["trio", "trio"]))
        self.refuses(request(flash_layout="expanded-d9000", runtime_mode="continuous"))
        self.refuses(request(flash_layout="expanded-d7000", runtime_mode="diagnostic"))
        self.refuses(request(engines=["macro"], effects=["hall"],
                             flash_layout="expanded-d7000", runtime_mode="song-diagnostic"))

    def test_cli_emits_non_installable_validated_result(self):
        with tempfile.TemporaryDirectory(prefix="lunar-request-contract-") as scratch:
            request_path = Path(scratch) / "request.json"
            catalogue_path = Path(scratch) / "catalogue.json"
            request_path.write_bytes(request())
            catalogue_path.write_bytes(catalogue_bytes())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = main([str(request_path), "--catalogue", str(catalogue_path)])
        self.assertEqual(result, 0)
        self.assertFalse(json.loads(output.getvalue())["installable"])

    def test_catalogue_rejects_duplicate_or_cross_group_module_ids(self):
        catalogue = json.loads(catalogue_bytes())
        catalogue["groups"]["effects"].append("trio")
        self.refuses(request(), json.dumps(catalogue).encode())

    def refuses(self, raw_request, raw_catalogue=None):
        with self.assertRaises((ValueError, TypeError)):
            validate_request(raw_request, catalogue_bytes() if raw_catalogue is None else raw_catalogue)


if __name__ == "__main__":
    unittest.main()
