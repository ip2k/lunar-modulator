# SPDX-License-Identifier: MIT
"""Compose a non-installable, same-identity V15 candidate in private memory.

All trust inputs belong to the operator, never to a request or checked receipt.
No CLI, service dispatch, binary file output, identity override or transport.
The unchanged V15 model preserves proprietary donor bytes; this function grants
no right to distribute them. Real protected-input use requires its own recorded
approval. Only synthetic inputs are exercised by the default tests.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from typing import Mapping

from . import selected_trio_profile as trio

# The existing offline tools use sibling imports. Reuse that exact local module
# directory, as trusted_fwsc_package does; no caller-provided import location.
_JIELI = Path(__file__).resolve().parents[1] / "jieli"
sys.path.insert(0, str(_JIELI))
import model_app_replacement as model  # noqa: E402
import inspect_stock_flash as nested  # noqa: E402
import inspect_version_contract as version_contract  # noqa: E402
import package_guard  # noqa: E402

DONOR_IDENTITY = "FM-1_015"
DONOR_BYTES = 699956
DONOR_SHA256 = "db1642b2b6fa5c2cccb11ffd13878068bb28601678d3644049f99dc40e7edb8a"
REFERENCE_PATHS = frozenset({"top/uboot.boot", "top/isd_config.ini", "ota.bin",
                           "files/app.bin", "files/cfg", "files/cfg_tool.bin",
                           "files/eq_cfg_hw.bin"})
MAX_REFERENCE_FILE_BYTES = 1024 * 1024
MAX_REFERENCE_BYTES = 2 * 1024 * 1024
_COMPONENT_PINS = {
    "top/uboot.boot": (14384, "730e54f0a439f58d147be4364ad21e19566945ada9d3a7bbc8371dce5068d3ef"),
    "files/app.bin": (581564, "306e47065f35d7a7a05ada7f5dd092f6e770952054f33f0a86b75fd10ffe3203"),
    "ota.bin": (19969, "ef1f2db89b011fa53e71df363f0122de0ea896618c53fb53e8da676322004541"),
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True)
class ReferencePin:
    bytes: int
    sha256: str


@dataclass(frozen=True)
class TrustedV15DonorPins:
    """Independent acquisition record; never load this from candidate evidence.

    Record names document provenance/authorization, not an approval mechanism.
    The caller must establish the actual scope before handling protected input.
    """
    identity: str
    bytes: int
    sha256: str
    references: Mapping[str, ReferencePin]
    acquisition_record: str
    authorization_record: str


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _donor_inputs(raw, reference, pins):
    if (type(raw) is not bytes or len(raw) != DONOR_BYTES or _sha(raw) != DONOR_SHA256
            or not isinstance(pins, TrustedV15DonorPins)
            or pins.identity != DONOR_IDENTITY or type(pins.bytes) is not int
            or pins.bytes != DONOR_BYTES or pins.sha256 != DONOR_SHA256):
        raise ValueError("fixed stock V15 donor pin required")
    for record in (pins.acquisition_record, pins.authorization_record):
        if type(record) is not str or not record.strip() or len(record) > 1024:
            raise ValueError("operator donor acquisition and authorization records required")
    if (not isinstance(reference, Mapping) or len(reference) != len(REFERENCE_PATHS)
            or not isinstance(pins.references, Mapping)
            or len(pins.references) != len(REFERENCE_PATHS)):
        raise ValueError("exact seven operator-pinned stock reference files required")
    # Snapshot mappings; bytes values and frozen per-file pins remain immutable
    # throughout the repeated reads performed by the established inspectors.
    values, expected = dict(reference), dict(pins.references)
    if set(values) != REFERENCE_PATHS or set(expected) != REFERENCE_PATHS:
        raise ValueError("exact seven operator-pinned stock reference files required")
    total = 0
    for name in sorted(REFERENCE_PATHS):
        value, pin = values[name], expected[name]
        if (type(value) is not bytes or len(value) > MAX_REFERENCE_FILE_BYTES
                or not isinstance(pin, ReferencePin) or type(pin.bytes) is not int
                or pin.bytes != len(value) or type(pin.sha256) is not str
                or not _SHA.fullmatch(pin.sha256)):
            raise ValueError("invalid bounded stock reference: " + name)
        total += len(value)
        if total > MAX_REFERENCE_BYTES:
            raise ValueError("stock reference aggregate exceeds bound")
    manifest = {}
    for name, value in sorted(values.items()):
        actual = (len(value), _sha(value))
        if actual != (expected[name].bytes, expected[name].sha256):
            raise ValueError("operator stock reference pin mismatch: " + name)
        if name in _COMPONENT_PINS and actual != _COMPONENT_PINS[name]:
            raise ValueError("fixed stock component pin mismatch: " + name)
        manifest[name] = dict(bytes=actual[0], sha256=actual[1])
    if len(values["top/isd_config.ini"]) != 699:
        raise ValueError("fixed stock config size differs")
    return values, manifest


def _scratch_root(path):
    root = Path(path).absolute()
    if root.resolve(strict=True) != root:
        raise ValueError("operator scratch root must not contain symlinks")
    info = root.stat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError("operator scratch root must be an owner-only directory")
    return root


def compose_selected_v15_candidate(*, request_raw: bytes, receipt_raw: bytes,
                                   app: bytes, elf: bytes, trusted: trio.TrustedInputs,
                                   donor_fwsc: bytes, donor_reference: Mapping[str, bytes],
                                   donor_pins: TrustedV15DonorPins,
                                   scratch_root: Path) -> tuple[bytes, dict]:
    """Return bytes only after original v2 and V15 verification both succeed.

    scratch_root is an existing operator-owned 0700 directory, outside source.
    Only a fresh child containing the seven bounded reference files is written.
    Cleanup is attempted on success and failure; a candidate is returned only
    after cleanup succeeds. If deletion is refused, the exception propagates
    without a candidate and private references may remain in that known root.
    The operator must inspect the root and remove only the owned child once
    its filesystem access is restored. No candidate file is written.
    The caller owns the returned bytes and their private lifecycle. The result
    deliberately retains FM-1_015 and must never be offered as an installable
    upgrade, even if another running identity would accept the version number.
    """
    if (type(request_raw) is not bytes or len(request_raw) > trio.MAX_REQUEST_BYTES
            or type(receipt_raw) is not bytes or len(receipt_raw) > trio.MAX_RECEIPT
            or type(app) is not bytes or not 0 < len(app) <= trio.APP_BUDGET
            or type(elf) is not bytes or len(elf) > trio.MAX_ELF
            or not isinstance(trusted, trio.TrustedInputs)):
        raise ValueError("bounded actual v2 artifact and operator trust required")
    root = _scratch_root(scratch_root)
    summary = trio.validate_receipt(request_raw, receipt_raw, app=app, elf=elf, trusted=trusted)
    if any(summary.get(key) is not False for key in trio.DENIED):
        raise ValueError("selected validation cannot grant admission")
    references, manifest = _donor_inputs(donor_fwsc, donor_reference, donor_pins)
    # Explicit dir= is essential: no default /tmp workspace or mutable caller
    # reference tree is consulted. The operator controls the root's lifetime.
    with tempfile.TemporaryDirectory(prefix="selected-v15-", dir=root) as temporary:
        stock = Path(temporary)
        for name, raw in references.items():
            dest = stock / name
            dest.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
            with os.fdopen(fd, "wb") as handle:
                handle.write(raw)
        if not package_guard.check_package(stock, stock)["passed"]:
            raise ValueError("original stock package guard refused reference")
        baseline = nested.inspect_nested(donor_fwsc, stock)
        xip = baseline["stock_xip"]
        if (baseline["identity"] != DONOR_IDENTITY or xip["app_bytes"] != trio.APP_BUDGET
                or xip["entry"] != 0x02000120 or xip["app_image_offset"] != 0x4120):
            raise ValueError("fixed V15 application placement differs")
        donor_version = version_contract.inspect_contract(donor_fwsc, stock)
        candidate = model._build(donor_fwsc, stock, app)
        verified = model.verify_replacement(donor_fwsc, candidate, stock, app)
    # All final output construction follows successful cleanup as well as full
    # verification; cleanup failure must not return an apparently finished job.
    return candidate, dict(
        schema=1, status="selected-trio-v2-private-v15-memory-candidate-verified",
        candidate_returned_in_memory=True, file_written=False, transport_used=False,
        request_sha256=summary["request_sha256"], receipt_sha256=_sha(receipt_raw),
        artifact_sha256=_sha(app), elf_sha256=_sha(elf), source_commit=trusted.source_commit,
        source_tree_oid=trusted.source_tree_oid, donor_sha256=_sha(donor_fwsc),
        donor_reference_manifest=manifest, donor_reference_manifest_sha256=_sha(_canonical(manifest)),
        donor_acquisition_record=donor_pins.acquisition_record,
        donor_authorization_record=donor_pins.authorization_record,
        candidate_sha256=_sha(candidate), candidate_bytes=len(candidate),
        identity=DONOR_IDENTITY, identity_changed=False,
        packaging_ready=False, release_candidate=False, updater_acceptance_verified=False,
        same_identity_diagnostic_only=True, runtime_identity_service_verified=False,
        validation=summary, donor_version_check=donor_version, replacement_check=verified,
        **trio.DENIED)
