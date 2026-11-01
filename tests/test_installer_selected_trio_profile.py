# SPDX-License-Identifier: MIT
"""Pure source/contract checks; no service, worker, compiler or device is run."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest
from pydantic import ValidationError
from tools.installer_service import build_capabilities as capabilities
from tools.installer_service import selected_trio_profile as profile
from tools.installer_service.request_contract import canonical_request, validate_request as v1_request
from tools.installer_service.server import check_native_prerequisites

ROOT = Path(__file__).resolve().parents[1]
BASE = "7ab2810420999629d170531a6f2f78fd44a8484f"


def request(**changes):
    value = dict(version=2, profile_id=capabilities.SELECTED_TRIO_PROFILE,
                 runtime_mode="offline", flash_layout="stock-sized-diagnostic",
                 engines=["trio"], effects=[], midi=[], modulation=[],
                 project_ids=["init-starter-trio"], startup_index=0)
    value.update(changes)
    return json.dumps(value).encode()


def test_fixed_request_canonical_and_no_internal_arp_selection():
    validated = profile.validate_request(request())
    assert validated["midi"] == []
    assert "arp" not in canonical_request(validated).decode()
    assert canonical_request(validated) == canonical_request(profile.validate_request(request(set_ids=[])))
    assert validated["version"] == 2 and validated["runtime_mode"] == "offline"


@pytest.mark.parametrize("changes", [
    {"version": True}, {"version": 1}, {"version": 2.0}, {"version": "2"},
    {"profile_id": "sdk-free-single-fm6-diagnostic-v1"},
    {"profile_id": "fm1-500-d7000-hall-o2-stage7-v1"},
    {"runtime_mode": "diagnostic"}, {"runtime_mode": "song-diagnostic"},
    {"runtime_mode": "continuous"}, {"runtime_mode": "rom20"},
    {"flash_layout": "expanded-d9000"}, {"flash_layout": "expanded-d7000"},
    {"flash_layout": "stock-protected"}, {"engines": ["dx7"]},
    {"engines": ["trio", "trio"]}, {"engines": []}, {"engines": [True]},
    {"effects": ["hall"]}, {"midi": ["arp"]}, {"modulation": ["lfo"]},
    {"project_ids": ["init-starter-trio", "init-starter-trio"]},
    {"project_ids": ["packet-bloom"]}, {"startup_index": 1},
    {"startup_index": False}, {"set_ids": ["companion"]},
    {"command": "builder"}, {"installable": True}, {"source_commit": BASE},
])
def test_fixed_request_refuses_other_selections_and_claims(changes):
    with pytest.raises((ValueError, ValidationError)):
        profile.validate_request(request(**changes))


@pytest.mark.parametrize("raw", [b'{"version":2,"version":2}', b'[]', b'{"version":NaN}',
    b'{"value":1e999}', b'\xff', b' ' * 65537])
def test_fixed_request_uses_shared_bounded_strict_json(raw):
    with pytest.raises((ValueError, UnicodeError)):
        profile.validate_request(raw)


def test_v1_canonical_bytes_and_rejection_stay_unchanged():
    catalogue = (ROOT / "tests/fixtures/installer-request-catalogue.json").read_bytes()
    old = dict(version=1, engines=["trio"], effects=[], midi=[], modulation=[],
               project_ids=["init-starter-trio"], startup_index=0)
    expected = b'{"effects":[],"engines":["trio"],"midi":[],"modulation":[],"project_ids":["init-starter-trio"],"startup_index":0,"version":1}\n'
    assert canonical_request(v1_request(json.dumps(old).encode(), catalogue)) == expected
    with pytest.raises(ValueError):
        v1_request(request(), catalogue)
    with pytest.raises(ValueError, match="native build prerequisites are unavailable"):
        check_native_prerequisites(ROOT, BASE)


def test_source_declaration_never_enables_any_capability():
    result = capabilities.selected_trio_capability()
    assert result["internal_dependencies"] == ["arp"]
    for field in ("service_enabled", "native_build_verified", *profile.DENIED):
        assert result[field] is False
    assert result["flash_layout"] == "stock-sized-diagnostic"
    result["internal_dependencies"].append("other")
    assert capabilities.selected_trio_capability()["internal_dependencies"] == ["arp"]


def test_current_fixed_source_prerequisites_pass_separately_from_legacy_gate():
    capabilities.check_profile_prerequisites(ROOT, BASE, capabilities.SELECTED_TRIO_PROFILE)


@pytest.fixture
def committed_source(tmp_path):
    for relative in capabilities.SELECTED_TRIO_PREREQUISITES:
        path = tmp_path / relative; path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("synthetic source only\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
    sha = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"]).decode().strip()
    return tmp_path, sha


@pytest.mark.parametrize("failure", ["missing", "changed", "symlink"])
def test_source_preflight_refuses_missing_changed_or_aliased_source(committed_source, failure):
    root, sha = committed_source
    path = root / capabilities.SELECTED_TRIO_PREREQUISITES[0]
    if failure == "missing": path.unlink()
    elif failure == "changed": path.write_text("changed\n")
    else:
        path.unlink(); path.symlink_to(root / capabilities.SELECTED_TRIO_PREREQUISITES[1])
    with pytest.raises(ValueError):
        capabilities.check_profile_prerequisites(root, sha, capabilities.SELECTED_TRIO_PROFILE)


@pytest.mark.parametrize("raw", [b"", b"ELF", bytes(52), bytes(100)])
def test_malformed_elf_refuses_without_tools_or_unbounded_reader(raw):
    with pytest.raises(ValueError):
        profile._elf(raw)
