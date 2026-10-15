# SPDX-License-Identifier: MIT
"""Private/local build-service API prototype; no Kubernetes or build execution."""
from __future__ import annotations
import asyncio, hashlib, json, re, secrets, threading, time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Literal, Protocol
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, field_validator, model_validator

from tools.native.module_selection import wavetable_namespaces
from tools.native.flash_layout import app_budget
from tools.native.runtime_mode import runtime_configuration
from .provenance import make_diagnostic_provenance, sha256 as provenance_sha256

MAX_BODY_BYTES = 65536
MAX_ARTIFACT_BYTES = 1048576
MAX_ELF_BYTES = 16 * 1024 * 1024
OPAQUE_ID = re.compile(r"[A-Za-z0-9_-]{32}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GROUPS = ("engines", "effects", "midi", "modulation")
WAVETABLE_PROFILE = "compressed-required-banks-flash-plaits-v1"
WAVETABLES = {
    "braids": {"namespace": "braids", "symbol": "wt_waves", "width": 1, "raw_bytes": 33024,
               "raw_sha256": "c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634"},
}
TARGET_STORAGE = {"rgb565_bytes": 220832, "indexed_bytes": 163744,
                  "pool_credit_bytes": 57088}
BASE_INSTANCE_POOL_BYTES = 192000
SHAPES_VOICES = 12
SCHEMA2_PROFILE_ID = "fm1-092-d7000"
SCHEMA2_TUPLE_SCHEMA = 2
SHAPES8_WAVETABLE_PROFILE = "compressed-required-banks-ram-plaits-braids-shapes8-v1"
SHAPES8_TABLES = (
    {"namespace": "plaits", "symbol": "wav_integrated_waves", "width": 2,
     "raw_bytes": 50688,
     "raw_sha256": "bd1d04177e240247de3224ef8e6f52afd907d8ae1a9971e0ce4ba68258e7ecea",
     "packed_bytes": 32513,
     "packed_sha256": "2cbdd706ef8cd7b97e705b139eab7a328ff4cb03257326faf34c396ac5b21255",
     "fnv32": 2231692768,
     "generated_source_sha256": "b5dacba5b7df4af0c5966f5bd8906bd2c30486ccf8ef156db02248e6d469787c"},
    {"namespace": "braids", "symbol": "wt_waves", "width": 1,
     "raw_bytes": 33024,
     "raw_sha256": "c672fccb061496d0229bfc5c2d55ec61f367e1539dda5870fd667a059c90f634",
     "packed_bytes": 24159,
     "packed_sha256": "d05f3f0b852719327983c82418a1b6b9e4c2414430078267653a77feb2ed1952",
     "fnv32": 3119621762,
     "generated_source_sha256": "c3c20d193d012125c53b2d2cba811c33c559462c070fed2702dc896727f2b82e"},
)


class DuplicateKey(ValueError): pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKey("duplicate JSON key")
        result[key] = value
    return result


def _reject_constant(_value):
    raise ValueError("non-finite JSON number")


def canonical_request(request: dict) -> bytes:
    normalized = dict(request)
    if normalized.get("set_ids") == []:
        normalized.pop("set_ids")
    return (json.dumps(normalized, sort_keys=True, separators=(",", ":")) + "\n").encode()


class BuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: StrictInt = Field(ge=1, le=1)
    engines: list[StrictStr] = Field(min_length=1, max_length=128)
    effects: list[StrictStr] = Field(max_length=128)
    midi: list[StrictStr] = Field(max_length=128)
    modulation: list[StrictStr] = Field(max_length=128)
    project_ids: list[StrictStr] = Field(min_length=1, max_length=8)
    startup_index: StrictInt = Field(ge=0)
    set_ids: list[StrictStr] = Field(default_factory=list, max_length=8)
    # Omitted D9000 requests retain their historical canonical bytes. D7000
    # must be an explicit, schema-2-shaped diagnostic profile selection.
    flash_layout: Literal["expanded-d9000", "expanded-d7000"] = "expanded-d9000"
    runtime_mode: Literal["diagnostic", "song-diagnostic"] = "diagnostic"

    @field_validator("engines", "effects", "midi", "modulation", "project_ids", "set_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("IDs must be unique within each list")
        return values

    @model_validator(mode="after")
    def startup_in_range(self):
        if self.startup_index >= len(self.project_ids):
            raise ValueError("startup_index is outside project_ids")
        if self.flash_layout == "expanded-d7000":
            if self.runtime_mode != "song-diagnostic":
                raise ValueError("expanded-d7000 requires the schema-2 song-diagnostic runtime")
            selected = set(self.engines + self.effects + self.midi + self.modulation)
            if not {"macro", "shapes"}.issubset(selected):
                raise ValueError("expanded-d7000 requires the fixed Macro+Shapes8 profile")
        elif self.runtime_mode != "diagnostic":
            raise ValueError("legacy expanded-d9000 requests use the bounded diagnostic runtime")
        return self


@dataclass(frozen=True)
class WorkerTemplate:
    """Fixed server-owned worker settings; never populated from request fields."""
    image_digest: str
    namespace: str
    command: tuple[str, ...] = (
        "python3", "/workspace/tools/installer_service/docker_worker.py",
    )

    def __post_init__(self):
        if (not isinstance(self.image_digest, str)
                or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_digest)):
            raise ValueError("worker image must be pinned by lowercase sha256 digest")
        if not self.namespace or "/" in self.namespace:
            raise ValueError("invalid fixed namespace")


@dataclass(frozen=True)
class WorkerResult:
    artifact: bytes
    receipt: bytes
    elf: bytes
    provenance: bytes


@dataclass(frozen=True)
class WorkerSnapshot:
    status: Literal["queued", "running", "succeeded", "failed"]
    result: WorkerResult | None = None


class JobAdapter(Protocol):
    def submit(self, build_id: str, request_bytes: bytes, request_sha256: str,
               template: WorkerTemplate) -> None: ...
    def get(self, build_id: str) -> WorkerSnapshot | None: ...
    def delete(self, build_id: str) -> None: ...


class QueueFull(Exception): pass


class FakeJobAdapter:
    """In-memory test adapter; it never launches processes or contacts a cluster."""
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.jobs: dict[str, WorkerSnapshot] = {}
        self.submissions: dict[str, tuple[bytes, str, WorkerTemplate]] = {}

    def submit(self, build_id, request_bytes, request_sha256, template):
        if sum(s.status in ("queued", "running") for s in self.jobs.values()) >= self.capacity:
            raise QueueFull
        self.submissions[build_id] = (request_bytes, request_sha256, template)
        self.jobs[build_id] = WorkerSnapshot("queued")

    def get(self, build_id):
        return self.jobs.get(build_id)

    def delete(self, build_id):
        self.jobs.pop(build_id, None)
        self.submissions.pop(build_id, None)

    def set_running(self, build_id):
        self.jobs[build_id] = WorkerSnapshot("running")

    def succeed(self, build_id, artifact, receipt, elf=b"diagnostic-elf", provenance=None):
        if provenance is None:
            # Negative-path tests deliberately inject malformed receipts and
            # artifacts. Keep the fake adapter from raising before the status
            # endpoint can exercise its controlled refusal path.
            try:
                parsed = json.loads(receipt)
                bindings = {
                    "source_commit": "1" * 40,
                    "source_tree_oid": "2" * 40,
                    "source_archive_sha256": "3" * 64,
                    "worker_sha256": "4" * 64,
                    "worker_image_digest": self.submissions[build_id][2].image_digest,
                    "catalogue_manifest_sha256": "6" * 64,
                    "toolchain_manifest_sha256": "7" * 64,
                }
                provenance = make_diagnostic_provenance(
                    bindings=bindings, request_sha256=parsed["request_sha256"],
                    artifact=artifact, elf=elf, receipt_raw=receipt, receipt=parsed)
            except (ValueError, KeyError, TypeError, UnicodeDecodeError, RecursionError):
                provenance = b"{}"
        self.jobs[build_id] = WorkerSnapshot(
            "succeeded", WorkerResult(artifact, receipt, elf, provenance))

    def fail(self, build_id):
        self.jobs[build_id] = WorkerSnapshot("failed")


@dataclass(frozen=True)
class Admission:
    request_sha256: str
    request: dict
    created_at: float
    worker_image_digest: str


def _verify_wavetable_receipt(receipt: dict, selected: list[str], flash_layout: str) -> None:
    """Bind the fixed compiled wavetable profile to admitted module choices."""
    if flash_layout == "expanded-d7000":
        expected_rows = [dict(row) for row in SHAPES8_TABLES]
        rows = receipt.get("compressed_wave_tables")
        if (receipt.get("wavetable_profile") != SHAPES8_WAVETABLE_PROFILE
                or receipt.get("indexed_tft") is not True
                or receipt.get("flash_plaits_wavetables") is not False
                or type(receipt.get("shapes_voices")) is not int
                or receipt["shapes_voices"] != 8
                or rows != expected_rows
                or not {"macro", "shapes"}.issubset(set(selected))):
            raise ValueError("worker Shapes8 D7000 profile differs from fixed policy")
        integer_fields = ("width", "raw_bytes", "packed_bytes", "fnv32")
        digest_fields = ("raw_sha256", "packed_sha256", "generated_source_sha256")
        for actual, expected in zip(rows, expected_rows):
            if (not isinstance(actual, dict) or set(actual) != set(expected)
                    or any(type(actual.get(key)) is not int or actual[key] != expected[key]
                           for key in integer_fields)
                    or any(type(actual.get(key)) is not str or actual[key] != expected[key]
                           for key in digest_fields)
                    or type(actual.get("namespace")) is not str
                    or actual["namespace"] != expected["namespace"]
                    or type(actual.get("symbol")) is not str
                    or actual["symbol"] != expected["symbol"]):
                raise ValueError("worker D7000 wavetable identity is malformed or stale")
        storage = receipt.get("target_app_storage")
        if (not isinstance(storage, dict) or storage != TARGET_STORAGE
                or any(type(storage.get(key)) is not int for key in TARGET_STORAGE)):
            raise ValueError("worker target storage profile differs from fixed layout")
        raw_bytes = sum(row["raw_bytes"] for row in expected_rows)
        expected_pool = BASE_INSTANCE_POOL_BYTES + TARGET_STORAGE["pool_credit_bytes"] - raw_bytes
        if type(receipt.get("instance_pool_bytes")) is not int or receipt["instance_pool_bytes"] != expected_pool:
            raise ValueError("worker instance pool does not match the D7000 Shapes8 profile")
        return
    if flash_layout != "expanded-d9000":
        raise ValueError("worker selected an unsupported flash layout")
    expected_namespaces = wavetable_namespaces(selected, flash_plaits=True)
    rows = receipt.get("compressed_wave_tables")
    if (receipt.get("wavetable_profile") != WAVETABLE_PROFILE
            or receipt.get("indexed_tft") is not True
            or receipt.get("flash_plaits_wavetables") is not True
            or type(receipt.get("shapes_voices")) is not int
            or receipt["shapes_voices"] != SHAPES_VOICES
            or not isinstance(rows, list)
            or [row.get("namespace") if isinstance(row, dict) else None for row in rows]
               != expected_namespaces):
        raise ValueError("worker wavetable profile differs from fixed policy/module selection")
    expected_raw_bytes = 0
    for row, namespace in zip(rows, expected_namespaces):
        if set(row) != {"namespace", "symbol", "width", "raw_bytes", "packed_bytes",
                        "raw_sha256", "packed_sha256", "fnv32", "generated_source_sha256"}:
            raise ValueError("worker compressed wavetable metadata has unknown fields")
        spec = WAVETABLES.get(namespace)
        if spec is None:
            raise ValueError("worker selected an unsupported compressed wavetable namespace")
        if (row.get("symbol") != spec["symbol"]
                or type(row.get("width")) is not int or row["width"] != spec["width"]
                or type(row.get("raw_bytes")) is not int or row["raw_bytes"] != spec["raw_bytes"]
                or row.get("raw_sha256") != spec["raw_sha256"]
                or type(row.get("packed_bytes")) is not int
                or not 0 < row["packed_bytes"] <= spec["raw_bytes"]
                or any(not isinstance(row.get(key), str) or not SHA256.fullmatch(row[key])
                       for key in ("packed_sha256", "generated_source_sha256"))
                or type(row.get("fnv32")) is not int or not 0 <= row["fnv32"] <= 0xffffffff):
            raise ValueError("worker compressed wavetable metadata is malformed or stale")
        expected_raw_bytes += spec["raw_bytes"]
    storage = receipt.get("target_app_storage")
    if (not isinstance(storage, dict) or storage != TARGET_STORAGE
            or any(type(storage.get(key)) is not int for key in TARGET_STORAGE)):
        raise ValueError("worker target storage profile differs from fixed layout")
    expected_pool = (BASE_INSTANCE_POOL_BYTES + TARGET_STORAGE["pool_credit_bytes"]
                     - expected_raw_bytes)
    if (type(receipt.get("instance_pool_bytes")) is not int
            or receipt["instance_pool_bytes"] != expected_pool):
        raise ValueError("worker instance pool does not match the selected wavetable profile")


def _verify_runtime_configuration(receipt: dict) -> None:
    """Require an exact supported diagnostic runtime description from the worker."""
    config = receipt.get("runtime_configuration")
    fields = {"runtime_mode", "return_to_rom_seconds", "define", "release_accepted"}
    if not isinstance(config, dict) or set(config) != fields:
        raise ValueError("worker runtime configuration is missing or malformed")
    mode = config.get("runtime_mode")
    # The builder currently admits only bounded diagnostics. The canonical
    # helper also describes continuous mode, but it is not an installer mode.
    if type(mode) is not str or mode not in ("diagnostic", "song-diagnostic"):
        raise ValueError("worker runtime mode is unsupported")
    expected = runtime_configuration(mode)
    if any(type(config[key]) is not type(value) or config[key] != value
           for key, value in expected.items()):
        raise ValueError("worker runtime configuration differs from canonical mode")


def _verify_result(admission: Admission, result: WorkerResult, trusted_set_parents=None) -> dict:
    if (not isinstance(result.artifact, bytes) or not isinstance(result.elf, bytes)
            or not isinstance(result.receipt, bytes) or not isinstance(result.provenance, bytes)
            or not result.artifact or not result.elf or not result.provenance
            or len(result.artifact) > MAX_ARTIFACT_BYTES or len(result.elf) > MAX_ELF_BYTES
            or len(result.receipt) > 65536 or len(result.provenance) > 65536):
        raise ValueError("worker result exceeds configured cap or is malformed")
    try:
        receipt = json.loads(result.receipt, object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKey, ValueError,
            RecursionError) as exc:
        raise ValueError("worker receipt is invalid JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("worker receipt is not an object")
    try:
        provenance = json.loads(result.provenance.decode("ascii"), object_pairs_hook=_unique_object,
                                parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKey, ValueError,
            RecursionError) as exc:
        raise ValueError("worker provenance is invalid JSON") from exc
    if not isinstance(provenance, dict):
        raise ValueError("worker provenance is not an object")
    artifact_sha = hashlib.sha256(result.artifact).hexdigest()
    elf_sha = hashlib.sha256(result.elf).hexdigest()
    request = admission.request
    projects = request["project_ids"]
    set_ids = request.get("set_ids", [])
    trusted_set_parents = {} if trusted_set_parents is None else trusted_set_parents
    selected_content = receipt.get("selected_content")
    startup_index = request["startup_index"]
    expected_selected = [module for group in GROUPS for module in request[group]]
    content = receipt.get("content")
    embedded = receipt.get("embedded_content")
    service = receipt.get("project_save_service")
    codec = receipt.get("state_bin_codec")
    false_fields = ("installable", "hardware_admitted", "hardware_tested",
                    "native_ram_verified", "native_playback_verified",
                    "full_song_default_accepted")
    flash_layout = request.get("flash_layout", "expanded-d9000")
    runtime_mode = request.get("runtime_mode", "diagnostic")
    selected_budget = app_budget(flash_layout) if flash_layout == "expanded-d7000" else MAX_ARTIFACT_BYTES
    _verify_runtime_configuration(receipt)
    if (type(receipt.get("version")) is not int or receipt["version"] != 1
            or receipt.get("status") != "linked-private-diagnostic"
            or receipt.get("flash_layout") != flash_layout
            or receipt.get("request_sha256") != admission.request_sha256
            or receipt.get("project_ids") != projects
            or receipt.get("set_ids", []) != set_ids
            or type(receipt.get("startup_index")) is not int
            or receipt["startup_index"] != startup_index
            or receipt.get("startup_project_id") != projects[startup_index]
            or receipt.get("runtime_hook_linked") is not (len(projects) > 1)
            or receipt.get("app_sha256") != artifact_sha
            or receipt.get("elf_sha256") != elf_sha
            or type(receipt.get("app_bytes")) is not int
            or receipt["app_bytes"] != len(result.artifact)
            or type(receipt.get("app_budget_bytes")) is not int
            or (flash_layout == "expanded-d7000"
                and receipt["app_budget_bytes"] != app_budget("expanded-d7000"))
            or not 0 < receipt["app_bytes"] <= receipt["app_budget_bytes"]
            or receipt["app_budget_bytes"] > selected_budget
            or (flash_layout == "expanded-d7000"
                and receipt["runtime_configuration"].get("runtime_mode") != runtime_mode)
            or any(receipt.get(key) is not False for key in false_fields)):
        raise ValueError("worker receipt does not bind the admitted diagnostic build")
    if any(not isinstance(receipt.get(key), str) or not SHA256.fullmatch(receipt[key])
           for key in ("app_sha256", "request_sha256", "prepared_profile_sha256", "elf_sha256",
                       "verification_sha256", "artifact_receipt_sha256")):
        raise ValueError("worker receipt has malformed digest")
    if (not isinstance(receipt.get("module_selection"), dict)
            or receipt["module_selection"].get("selected") != expected_selected):
        raise ValueError("worker module selection differs from admission")
    _verify_wavetable_receipt(receipt, expected_selected, flash_layout)
    _verify_diagnostic_provenance(provenance, admission, result, receipt,
                                  artifact_sha, elf_sha)
    expected_parents = {set_id: trusted_set_parents[set_id] for set_id in set_ids}
    expected_identity = ([{"kind": "project", "id": project} for project in projects]
                         + [{"kind": "set", "id": set_id,
                             "parent_project_id": expected_parents[set_id]}
                            for set_id in set_ids])
    if receipt.get("set_parents", {}) != expected_parents:
        raise ValueError("worker companion SET parent identity differs from trusted catalogue")
    if (not isinstance(selected_content, list) or len(selected_content) != len(expected_identity)
            or any(not isinstance(row, dict) for row in selected_content)
            or selected_content != expected_identity
            or not isinstance(content, list) or not 1 <= len(content) <= 16
            or len(content) != len(expected_identity)):
        raise ValueError("worker ordered content identity is malformed")
    # Validate every untrusted row before reading fields to derive aggregate
    # sizes or hashes. Malformed JSON shapes must be a controlled refusal, not
    # an AttributeError/TypeError escaping the status route.
    for expected_row, row in zip(expected_identity, content):
        if (not isinstance(row, dict) or row.get("kind") != expected_row["kind"]
                or row.get("id") != expected_row["id"]
                or (expected_row["kind"] == "set"
                    and row.get("parent_project_id") != expected_row["parent_project_id"])
                or type(row.get("bytes")) is not int or row["bytes"] <= 0
                or not isinstance(row.get("packed_sha256"), str)
                or not SHA256.fullmatch(row["packed_sha256"])):
            raise ValueError("worker content row is malformed")
    packed_content_bytes = sum(row["bytes"] for row in content)
    packed_hashes = [row["packed_sha256"] for row in content]
    if (not isinstance(embedded, dict)
            or embedded.get("assets") != content
            or type(embedded.get("asset_count")) is not int
            or embedded["asset_count"] != len(content)
            or type(embedded.get("packed_content_bytes")) is not int
            or embedded["packed_content_bytes"] != packed_content_bytes
            or embedded.get("packed_sha256") != packed_hashes
            or embedded.get("prepared_sha256") != receipt.get("prepared_profile_sha256")
            or embedded.get("native_playback_verified") is not False
            or embedded.get("sequence_semantics_verified") is not False):
        raise ValueError("worker embedded content differs from prepared profile")
    if (not isinstance(service, dict) or service.get("linked") is not True
            or service.get("compile_definition") != "LUNAR_PROJECT_SAVE_SERVICE=1"
            or any(service.get(key) is not False for key in
                   ("storage_admitted", "flash_io_bound", "save_service_armed",
                    "runtime_verified", "hardware_tested"))):
        raise ValueError("worker SAVE service metadata is missing or armed")
    if (not isinstance(codec, dict) or codec.get("mode") != "compact-writer"
            or codec.get("compile_definition") != "FM1_STATE_BIN_COMPACT_WRITER=1"
            or codec.get("replaced_exactly_one") is not True
            or not isinstance(codec.get("fresh_object"), str) or not codec["fresh_object"]
            or not isinstance(codec.get("cached_object"), str) or not codec["cached_object"]
            or any(not isinstance(codec.get(key), str) or not SHA256.fullmatch(codec[key])
                   for key in ("source_sha256", "fresh_object_sha256", "cached_object_sha256"))):
        raise ValueError("worker codec metadata is missing or invalid")
    return {"status": receipt["status"], "artifact_sha256": artifact_sha,
            "artifact_bytes": len(result.artifact), "elf_sha256": elf_sha,
            "elf_bytes": len(result.elf), "installable": False,
            "provenance": _provenance_summary(provenance, result.provenance),
            "app_budget_bytes": receipt["app_budget_bytes"],
            "remaining_bytes": receipt["app_budget_bytes"] - len(result.artifact),
            "hardware_tested": False}


def _verify_diagnostic_provenance(provenance, admission, result, receipt, app_sha, elf_sha):
    """Cross-check the host envelope without promoting it to a package tuple."""
    expected_top = {"schema", "kind", "bindings", "outputs", "profile",
                    "trusted_fwsc_packager_compatible", "compatibility_reason",
                    "installable", "hardware_admitted", "hardware_tested"}
    if set(provenance) != expected_top or type(provenance.get("schema")) is not int or \
            provenance["schema"] != 1 or provenance.get("kind") != "private-diagnostic-build-provenance":
        raise ValueError("worker provenance schema is malformed")
    bindings = provenance.get("bindings")
    binding_keys = {"source_commit", "source_tree_oid", "source_archive_sha256",
                    "worker_sha256", "worker_image_digest", "catalogue_manifest_sha256",
                    "toolchain_manifest_sha256", "request_sha256"}
    if not isinstance(bindings, dict) or set(bindings) != binding_keys:
        raise ValueError("worker provenance input bindings are malformed")
    if (not isinstance(bindings.get("source_commit"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", bindings["source_commit"])
            or not isinstance(bindings.get("source_tree_oid"), str)
            or not re.fullmatch(r"[0-9a-f]{40}", bindings["source_tree_oid"])
            or not isinstance(bindings.get("worker_image_digest"), str)
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", bindings["worker_image_digest"])
            or any(not isinstance(bindings.get(key), str) or not SHA256.fullmatch(bindings[key])
                   for key in binding_keys - {"source_commit", "source_tree_oid", "worker_image_digest"})
            or bindings.get("request_sha256") != admission.request_sha256
            or bindings.get("worker_image_digest") != admission.worker_image_digest):
        raise ValueError("worker provenance is stale or has malformed host bindings")
    outputs = provenance.get("outputs")
    expected_outputs = {"artifact_sha256": app_sha, "artifact_bytes": len(result.artifact),
                        "elf_sha256": elf_sha, "elf_bytes": len(result.elf),
                        "image_receipt_sha256": provenance_sha256(result.receipt),
                        "verification_sha256": receipt.get("verification_sha256"),
                        "artifact_receipt_sha256": receipt.get("artifact_receipt_sha256")}
    if not isinstance(outputs, dict) or outputs != expected_outputs:
        raise ValueError("worker provenance does not bind the exact build outputs")
    flash_layout = admission.request.get("flash_layout", "expanded-d9000")
    # D9000 historically accepted any canonical bounded runtime mode carried
    # by the worker receipt; keep that behavior while D7000 binds the request.
    runtime_mode = (admission.request.get("runtime_mode", "diagnostic")
                    if flash_layout == "expanded-d7000"
                    else receipt["runtime_configuration"]["runtime_mode"])
    profile = provenance.get("profile")
    if flash_layout == "expanded-d7000":
        expected_profile = {"flash_layout": "expanded-d7000",
                            "runtime_mode": runtime_mode,
                            "shapes_voices": 8,
                            "tuple_schema": SCHEMA2_TUPLE_SCHEMA,
                            "profile_id": SCHEMA2_PROFILE_ID}
    else:
        expected_profile = {"flash_layout": "expanded-d9000",
                            "runtime_mode": runtime_mode,
                            "shapes_voices": SHAPES_VOICES}
    if profile != expected_profile:
        raise ValueError("worker provenance profile differs from verified diagnostic build")
    reason = ("D7000 diagnostic profile matches schema-2 layout/profile; a trusted tuple still requires separately captured operator and build provenance plus an external tuple digest"
              if flash_layout == "expanded-d7000" else
              "diagnostic service emits expanded-d9000/12-voice; trusted schema-2 packager requires an explicitly captured expanded-d7000 tuple")
    if (provenance.get("trusted_fwsc_packager_compatible") is not False
            or provenance.get("compatibility_reason") != reason
            or any(provenance.get(key) is not False
                   for key in ("installable", "hardware_admitted", "hardware_tested"))):
        raise ValueError("worker provenance overstates package or hardware status")


def _provenance_summary(provenance, raw):
    bindings = provenance["bindings"]
    return {
        "sha256": provenance_sha256(raw),
        "kind": provenance["kind"],
        "source_commit": bindings["source_commit"],
        "source_tree_oid": bindings["source_tree_oid"],
        "source_archive_sha256": bindings["source_archive_sha256"],
        "worker_sha256": bindings["worker_sha256"],
        "worker_image_digest": bindings["worker_image_digest"],
        "catalogue_manifest_sha256": bindings["catalogue_manifest_sha256"],
        "toolchain_manifest_sha256": bindings["toolchain_manifest_sha256"],
        "request_sha256": bindings["request_sha256"],
        "output_bindings": provenance["outputs"],
        "profile": provenance["profile"],
        "trusted_fwsc_packager_compatible": False,
    }


def create_app(*, adapter: JobAdapter, template: WorkerTemplate,
               module_kinds: dict[str, str], project_ids: set[str],
               set_parents: dict[str, str] | None = None,
               queue_cap: int = 1, record_cap: int = 64,
               retention_seconds: int = 3600, clock=time.monotonic) -> FastAPI:
    """Construct a local API around an injected fixed adapter and trusted catalogue."""
    if type(queue_cap) is not int or not 1 <= queue_cap <= 4:
        raise ValueError("queue_cap must be between 1 and 4")
    if type(record_cap) is not int or not 1 <= record_cap <= 128:
        raise ValueError("record_cap must be between 1 and 128")
    if type(retention_seconds) is not int or not 60 <= retention_seconds <= 86400:
        raise ValueError("retention_seconds must be between 60 and 86400")
    if not module_kinds or not project_ids:
        raise ValueError("trusted module and project catalogues are required")
    set_parents = {} if set_parents is None else set_parents
    if (not isinstance(set_parents, dict)
            or any(not isinstance(key, str) or not isinstance(value, str)
                   or value not in project_ids for key, value in set_parents.items())):
        raise ValueError("trusted companion SET catalogue is malformed")
    @asynccontextmanager
    async def lifespan(_app):
        try:
            yield
        finally:
            shutdown = getattr(adapter, "shutdown", None)
            if callable(shutdown):
                await asyncio.to_thread(shutdown)

    app = FastAPI(title="Private Lunar diagnostic build prototype", docs_url=None,
                  redoc_url=None, openapi_url=None, lifespan=lifespan)
    admissions: dict[str, Admission] = {}
    lock = threading.Lock()

    async def read_bounded_json(request: Request):
        media = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if media != "application/json":
            return None, JSONResponse({"detail": "content type must be application/json"}, 415)
        if request.headers.get("content-encoding", "identity").lower() != "identity":
            return None, JSONResponse({"detail": "content encoding is unsupported"}, 415)
        length = request.headers.get("content-length")
        if length:
            try:
                if int(length) < 0 or int(length) > MAX_BODY_BYTES:
                    return None, JSONResponse({"detail": "request body is too large"}, 413)
            except ValueError:
                return None, JSONResponse({"detail": "invalid content length"}, 400)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > MAX_BODY_BYTES:
                return None, JSONResponse({"detail": "request body is too large"}, 413)
        try:
            decoded = json.loads(bytes(body).decode("utf-8"), object_pairs_hook=_unique_object,
                                 parse_constant=_reject_constant)
            if not isinstance(decoded, dict):
                raise ValueError("request must be an object")
            model = BuildRequest.model_validate(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKey, ValueError,
                ValidationError, RecursionError):
            return None, JSONResponse({"detail": "invalid build request"}, 422)
        doc = model.model_dump(mode="json", exclude_defaults=True)
        for group, kind in zip(GROUPS, ("sound", "audio_fx", "midi_fx", "mod")):
            if any(module not in module_kinds or module_kinds[module] != kind
                   for module in doc[group]):
                return None, JSONResponse({"detail": "invalid build request"}, 422)
        if (any(project not in project_ids for project in doc["project_ids"])
                or any(set_id not in set_parents for set_id in doc.get("set_ids", []))
                or any(set_parents[set_id] not in doc["project_ids"]
                       or set_parents[set_id] != doc["project_ids"][doc["startup_index"]]
                       for set_id in doc.get("set_ids", []))):
            return None, JSONResponse({"detail": "invalid build request"}, 422)
        return doc, None

    @app.post("/api/v1/builds", status_code=202)
    async def submit_build(request: Request):
        doc, error = await read_bounded_json(request)
        if error is not None:
            return error
        data = canonical_request(doc)
        digest = hashlib.sha256(data).hexdigest()
        build_id = secrets.token_urlsafe(24)
        with lock:
            now = clock()
            expired = []
            for existing_id, existing in admissions.items():
                snapshot = adapter.get(existing_id)
                terminal = snapshot is None or snapshot.status in ("succeeded", "failed")
                if terminal and now - existing.created_at >= retention_seconds:
                    expired.append(existing_id)
            for existing_id in expired:
                adapter.delete(existing_id)
                admissions.pop(existing_id, None)
            if len(admissions) >= record_cap:
                return JSONResponse({"detail": "build record capacity is full"}, 429,
                                    headers={"Retry-After": str(retention_seconds)})
            active = sum(
                (snapshot := adapter.get(existing_id)) is not None
                and snapshot.status in ("queued", "running")
                for existing_id in admissions
            )
            if active >= queue_cap:
                return JSONResponse({"detail": "build queue is full"}, 429,
                                    headers={"Retry-After": "30"})
            try:
                adapter.submit(build_id, data, digest, template)
            except QueueFull:
                return JSONResponse({"detail": "build queue is full"}, 429,
                                    headers={"Retry-After": "30"})
            except Exception:
                return JSONResponse({"detail": "build service unavailable"}, 503)
            admissions[build_id] = Admission(digest, doc, now, template.image_digest)
        return JSONResponse({"id": build_id, "status": "queued",
                             "status_url": f"/api/v1/builds/{build_id}"}, 202)

    @app.get("/api/v1/builds/{build_id}")
    async def get_build(build_id: str):
        if not OPAQUE_ID.fullmatch(build_id):
            return JSONResponse({"detail": "build not found"}, 404)
        with lock:
            admission = admissions.get(build_id)
            if admission is not None and clock() - admission.created_at >= retention_seconds:
                expiring = adapter.get(build_id)
                if expiring is None or expiring.status in ("succeeded", "failed"):
                    adapter.delete(build_id)
                    admissions.pop(build_id, None)
                    admission = None
            snapshot = adapter.get(build_id) if admission is not None else None
        if admission is None or snapshot is None:
            return JSONResponse({"detail": "build not found"}, 404)
        result = {"id": build_id, "status": snapshot.status,
                  "kind": "private-diagnostic-build"}
        if snapshot.status == "succeeded":
            if snapshot.result is None:
                return JSONResponse({"detail": "build result unavailable"}, 502)
            try:
                result["result"] = _verify_result(admission, snapshot.result, set_parents)
            except (ValueError, TypeError, AttributeError, KeyError, OverflowError):
                return JSONResponse({"detail": "build result failed verification"}, 502)
        return result

    return app
