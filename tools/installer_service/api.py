# SPDX-License-Identifier: MIT
"""Private/local build-service API prototype; no Kubernetes or build execution."""
from __future__ import annotations
import hashlib, json, re, secrets, threading
from dataclasses import dataclass
from typing import Literal, Protocol
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, ValidationError, field_validator, model_validator

MAX_BODY_BYTES = 65536
MAX_ARTIFACT_BYTES = 1048576
OPAQUE_ID = re.compile(r"[A-Za-z0-9_-]{32}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
GROUPS = ("engines", "effects", "midi", "modulation")


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
    return (json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode()


class BuildRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    version: StrictInt = Field(ge=1, le=1)
    engines: list[StrictStr] = Field(min_length=1, max_length=128)
    effects: list[StrictStr] = Field(max_length=128)
    midi: list[StrictStr] = Field(max_length=128)
    modulation: list[StrictStr] = Field(max_length=128)
    project_ids: list[StrictStr] = Field(min_length=1, max_length=8)
    startup_index: StrictInt = Field(ge=0)

    @field_validator("engines", "effects", "midi", "modulation", "project_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(values) != len(set(values)):
            raise ValueError("IDs must be unique within each list")
        return values

    @model_validator(mode="after")
    def startup_in_range(self):
        if self.startup_index >= len(self.project_ids):
            raise ValueError("startup_index is outside project_ids")
        return self


@dataclass(frozen=True)
class WorkerTemplate:
    """Fixed server-owned worker settings; never populated from request fields."""
    image_digest: str
    namespace: str
    command: tuple[str, ...] = (
        "python3", "/workspace/tools/native/build_demo_image.py",
        "--request", "/input/request.json",
        "--state-tool", "/workspace/build/fm1-state",
        "--toolchain", "/opt/pi32v2",
        "--catalogue", "/workspace/engines",
        "--out", "/output/build",
    )

    def __post_init__(self):
        if not self.image_digest.startswith("sha256:") or len(self.image_digest) != 71:
            raise ValueError("worker image must be pinned by sha256 digest")
        if not self.namespace or "/" in self.namespace:
            raise ValueError("invalid fixed namespace")


@dataclass(frozen=True)
class WorkerResult:
    artifact: bytes
    receipt: bytes


@dataclass(frozen=True)
class WorkerSnapshot:
    status: Literal["queued", "running", "succeeded", "failed"]
    result: WorkerResult | None = None


class JobAdapter(Protocol):
    def submit(self, build_id: str, request_bytes: bytes, request_sha256: str,
               template: WorkerTemplate) -> None: ...
    def get(self, build_id: str) -> WorkerSnapshot | None: ...


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

    def set_running(self, build_id):
        self.jobs[build_id] = WorkerSnapshot("running")

    def succeed(self, build_id, artifact, receipt):
        self.jobs[build_id] = WorkerSnapshot("succeeded", WorkerResult(artifact, receipt))

    def fail(self, build_id):
        self.jobs[build_id] = WorkerSnapshot("failed")


@dataclass(frozen=True)
class Admission:
    request_sha256: str
    request: dict


def _verify_result(admission: Admission, result: WorkerResult) -> dict:
    if len(result.artifact) > MAX_ARTIFACT_BYTES or len(result.receipt) > 65536:
        raise ValueError("worker result exceeds configured cap")
    try:
        receipt = json.loads(result.receipt, object_pairs_hook=_unique_object,
                             parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, DuplicateKey, ValueError) as exc:
        raise ValueError("worker receipt is invalid JSON") from exc
    if not isinstance(receipt, dict):
        raise ValueError("worker receipt is not an object")
    artifact_sha = hashlib.sha256(result.artifact).hexdigest()
    false_fields = ("installable", "hardware_admitted", "hardware_tested",
                    "native_ram_verified", "native_playback_verified",
                    "full_song_default_accepted")
    if (type(receipt.get("version")) is not int or receipt["version"] != 1
            or receipt.get("status") != "linked-private-diagnostic"
            or receipt.get("request_sha256") != admission.request_sha256
            or receipt.get("project_ids") != admission.request["project_ids"]
            or type(receipt.get("startup_index")) is not int
            or receipt["startup_index"] != admission.request["startup_index"]
            or receipt.get("app_sha256") != artifact_sha
            or type(receipt.get("app_bytes")) is not int
            or receipt["app_bytes"] != len(result.artifact)
            or any(receipt.get(key) is not False for key in false_fields)):
        raise ValueError("worker receipt does not bind the admitted diagnostic build")
    if any(not isinstance(receipt.get(key), str) or not SHA256.fullmatch(receipt[key])
           for key in ("app_sha256", "request_sha256")):
        raise ValueError("worker receipt has malformed digest")
    return {"status": receipt["status"], "artifact_sha256": artifact_sha,
            "artifact_bytes": len(result.artifact), "installable": False,
            "hardware_tested": False}


def create_app(*, adapter: JobAdapter, template: WorkerTemplate,
               module_kinds: dict[str, str], project_ids: set[str],
               queue_cap: int = 1) -> FastAPI:
    """Construct a local API around an injected fixed adapter and trusted catalogue."""
    if not 1 <= queue_cap <= 4:
        raise ValueError("queue_cap must be between 1 and 4")
    if not module_kinds or not project_ids:
        raise ValueError("trusted module and project catalogues are required")
    app = FastAPI(title="Private Lunar diagnostic build prototype", docs_url=None,
                  redoc_url=None, openapi_url=None)
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
        doc = model.model_dump(mode="json")
        for group, kind in zip(GROUPS, ("sound", "audio_fx", "midi_fx", "mod")):
            if any(module not in module_kinds or module_kinds[module] != kind
                   for module in doc[group]):
                return None, JSONResponse({"detail": "invalid build request"}, 422)
        if any(project not in project_ids for project in doc["project_ids"]):
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
            admissions[build_id] = Admission(digest, doc)
        return JSONResponse({"id": build_id, "status": "queued",
                             "status_url": f"/api/v1/builds/{build_id}"}, 202)

    @app.get("/api/v1/builds/{build_id}")
    async def get_build(build_id: str):
        if not OPAQUE_ID.fullmatch(build_id):
            return JSONResponse({"detail": "build not found"}, 404)
        admission = admissions.get(build_id)
        snapshot = adapter.get(build_id) if admission is not None else None
        if admission is None or snapshot is None:
            return JSONResponse({"detail": "build not found"}, 404)
        result = {"id": build_id, "status": snapshot.status,
                  "kind": "private-diagnostic-build"}
        if snapshot.status == "succeeded":
            if snapshot.result is None:
                return JSONResponse({"detail": "build result unavailable"}, 502)
            try:
                result["result"] = _verify_result(admission, snapshot.result)
            except ValueError:
                return JSONResponse({"detail": "build result failed verification"}, 502)
        return result

    return app
