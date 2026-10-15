# SPDX-License-Identifier: MIT
"""Single injected reset after a same-process, completed diagnostic install.

No device opener or CLI is provided. The caller supplies a fresh passive
snapshot and an already-bound reset transport; this module sends no upload.
"""
from dataclasses import dataclass
import json
import binascii
import os
from pathlib import Path
import stat
import time
from weakref import WeakSet

from fm1_flash_transaction import digest
from native import event120_reset as reset_module
from native import event120_generic_boot as generic_boot
from native import generic_diagnostic_flash as flash

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_KIND = "fm1-passive-loader-after-completed-diagnostic"
BOOT_KIND = "lunar-generic-diagnostic-completed-boot"
FLASH_BYTES, MAX_AGE = 1048576, 120
SOURCE_PINS = {
    "native/generic_diagnostic_flash.py": "524ac70a4514f6bd3ec96d19a8924808624334620d0317a779aedfe33ef7247a",
    "native/expanded_candidate.py": "46b03dfd636792473e720314268ad41cc9af9ca54f12d2118216cb8f3bdb8d7d",
    "native/generic_diagnostic_sg_adapter.py": "f637e74db1c27c235ed425eb4bba2ff568adca19377e3b9cf188fb439d2af16c",
    "native/expanded_sg.py": "f18e73b658c9d0b06b03b528c6fd4dd4da511a95102ea44252836d885e1a3700",
    "native/event120_generic_boot.py": "a060459933f8e34b34df8a0978e76e65e3d92f6bb728cbeb3306f4ffb132d820",
    "native/event120_reset.py": "f7b75e3448fe30babaed23b70340bab76db1e2c8815d13d22c6bdb00116a770c",
    "fm1_fixed_target_reset.py": "b846b574fe1e5b7597001f6f833044a07143540f2c0b3676e93bac807869833a",
    "fm1_fixed_loader_reset.py": "dbbe363104aa339b63430ff0a99f817aba27afa233a266d449f45e048cd09116",
    "fm1_bound_diagnostic.py": "25e57ffda466c898df88370069cf4d7fce02134e141ba95516347c30953d1a36",
    "fm1_flash_transaction.py": "d0527efbe74314b30a2cd76897c022a1c7857db888ef6e8f8610dbb329956908",
}
_PREPARED, _CLAIMED = WeakSet(), WeakSet()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _read(path, limit):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        with os.fdopen(fd, "rb") as fp:
            if not stat.S_ISREG(os.fstat(fp.fileno()).st_mode):
                raise ValueError("Expected regular evidence file")
            data = fp.read(limit + 1)
    except BaseException:
        try: os.close(fd)
        except OSError: pass
        raise
    if len(data) > limit: raise ValueError("Evidence bound exceeded")
    return data


def _source_evidence():
    evidence = []
    for relative, expected in SOURCE_PINS.items():
        path = ROOT / relative
        raw = _read(path, 2 * 1024 * 1024)
        if digest(raw) != expected:
            raise ValueError("Reviewed install/reset source changed: " + relative)
        evidence.append((path, raw))
    own = Path(__file__).resolve()
    evidence.append((own, _read(own, 256 * 1024)))
    return tuple(evidence)


def _successful_sg_log(path, policy):
    target = policy.target
    allowed_sectors = set(policy.sectors)
    raw = _read(path, 64 * 1024 * 1024)
    lines = raw.splitlines()
    if not lines or len(lines) % 2 or len(lines) > 65536:
        raise ValueError("Complete bounded SG intent/completion transcript required")
    requests, reads = [], []
    for index in range(0, len(lines), 2):
        intent, done = json.loads(lines[index]), json.loads(lines[index + 1])
        n = index // 2
        if (intent.get("event") != "sg_submit_intent" or done.get("event") != "sg_completion"
                or intent.get("index") != n or done.get("index") != n
                or intent.get("direction") != "install" or done.get("direction") != "install"
                or intent.get("retry") is not False or done.get("retry") is not False
                or any(type(done.get(k)) is not int or done[k] != 0 for k in
                       ("status", "masked", "msg", "host", "driver", "resid", "info", "sense_len"))
                or done.get("sense_hex") != ""):
            raise ValueError("SG transcript contains incomplete, failed or retried command")
        try:
            cdb = bytes.fromhex(intent["cdb"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Malformed SG command") from exc
        if len(cdb) != 16:
            raise ValueError("Malformed SG CDB")
        op, address = int.from_bytes(cdb[:2], "big"), int.from_bytes(cdb[2:6], "big")
        if op == 0xFC0A:
            expected = bytes.fromhex("fc0a" + "ff" * 14)
            if cdb != expected or intent.get("in_len") != 16 or intent.get("out_len") != 0:
                raise ValueError("Malformed liveness query")
        elif op == 0xFD05:
            expected = (b"\xfd\x05" + address.to_bytes(4, "big") + b"\x01\x00").ljust(16, b"\xff")
            if (cdb != expected or address % 256 or address > FLASH_BYTES - 256
                    or intent.get("in_len") != 256 or intent.get("out_len") != 0
                    or intent.get("payload_sha256") is not None):
                raise ValueError("Malformed flash read")
            reads.append((address, done.get("response_sha256")))
        elif op == 0xFB01:
            expected = (b"\xfb\x01" + address.to_bytes(4, "big")).ljust(16, b"\xff")
            if (cdb != expected or intent.get("in_len") != 16 or intent.get("out_len") != 0
                    or address not in allowed_sectors):
                raise ValueError("Malformed or unauthorized erase")
        elif op == 0xFB04:
            expected_page = target[address:address + 256]
            expected_cdb = (b"\xfb\x04" + address.to_bytes(4, "big") + b"\x01\x00\x00" +
                            binascii.crc_hqx(expected_page, 0).to_bytes(2, "little")).ljust(16, b"\xff")
            if (address % 256 or address > FLASH_BYTES - 256 or address // 4096 * 4096 not in allowed_sectors
                    or cdb != expected_cdb or intent.get("in_len") != 0 or intent.get("out_len") != 256
                    or intent.get("payload_sha256") != digest(expected_page)):
                raise ValueError("Malformed or unauthorized page program")
        else:
            raise ValueError("Unexpected command in diagnostic install transcript")
        requests.append((op, address))
    expected_reads = [(address, digest(target[address:address + 256]))
                      for address in range(0, FLASH_BYTES, 256)]
    if reads[-len(expected_reads):] != expected_reads:
        raise ValueError("Transcript lacks final complete target readback")
    if not requests or requests[-1] != (0xFD05, FLASH_BYTES - 256):
        raise ValueError("Final full-image readback is not the last device command")
    return raw, len(requests)


def _load_snapshot(provider, original_binding, completed_at, now=None):
    if not callable(provider): raise ValueError("Fresh passive snapshot provider required")
    path, expected_sha256 = provider()
    raw = _read(path, 65536)
    # Sample after the callback has produced the snapshot. A provider may need
    # time to capture sysfs state; comparing against a pre-callback clock can
    # reject a valid observation as being in the future.
    now = time.time() if now is None else now
    if digest(raw) != expected_sha256: raise ValueError("Passive snapshot digest differs")
    value = json.loads(raw)
    if (not isinstance(value, dict) or set(value) !=
            {"schema", "kind", "observed_at", "usb_binding", "sg_binding"}
            or type(value.get("schema")) is not int or value["schema"] != 1
            or value.get("kind") != SNAPSHOT_KIND
            or type(value.get("observed_at")) not in (int, float)
            or not completed_at <= value["observed_at"] <= now
            or not 0 <= now - value["observed_at"] <= MAX_AGE
            or value.get("usb_binding") != original_binding.get("usb_binding")
            or value.get("sg_binding") != original_binding.get("sg_binding")):
        raise ValueError("Fresh same-loader USB/SG snapshot required")
    return Path(path).absolute(), raw, value


def _verify_completion(policy, result):
    if not isinstance(result, dict) or result.get("direction") != "install":
        raise ValueError("Successful in-process install result required")
    target_sha = digest(policy.target)
    if result.get("verified_sha256") != target_sha:
        raise ValueError("Run result does not verify exact transaction target")
    journal = policy.check_files()
    if (journal.get("state") != "complete" or journal.get("direction") != "install"
            or journal.get("intent") is not None or journal.get("verified_sha256") != target_sha):
        raise ValueError("Durable complete full-image readback is absent")
    return journal, target_sha


@dataclass(frozen=True, eq=False)
class Prepared:
    evidence_root: Path
    campaign: bytes
    campaign_sha256: str
    expected_binding: bytes
    evidence: tuple
    log_sha256: str
    marker: Path
    authorization: object
    policy: object
    bridge: object
    expected_mapping: bytes
    header_type: type

    def check(self):
        if self not in _PREPARED or self.authorization is not _PREPARED:
            raise ValueError("Factory-created completed diagnostic boot required")
        self.policy.check_files()
        campaign = json.loads(self.campaign)
        if digest(self.policy.target) != campaign["target_sha256"]:
            raise ValueError("Transaction target no longer matches boot campaign")
        if _canonical(self.bridge.discover_sg(campaign["usb_binding"])) != self.expected_mapping:
            raise ValueError("Same-loader SG mapping changed")
        for path, expected in self.evidence:
            if _read(path, 64 * 1024 * 1024) != expected:
                raise ValueError("Pinned boot evidence changed: " + str(path))
        campaign = json.loads(self.campaign)
        if not 0 <= time.time() - campaign["observed_at"] <= MAX_AGE:
            raise ValueError("Passive loader snapshot expired")
        if digest(_read(campaign["install_log_path"], 64 * 1024 * 1024)) != self.log_sha256:
            raise ValueError("Install SG transcript changed")
        try: marker = _read(self.marker, 256)
        except FileNotFoundError as exc: raise ValueError("Durable one-use marker missing") from exc
        if marker != self.campaign_sha256.encode("ascii"):
            raise ValueError("One-use marker differs")


def run_completed(policy, session, *, evidence_root, install_log_path,
                  snapshot_provider, after_install=None, now=None):
    """Run one complete install, then make one no-upload FC0C reset request.

    The reset session uses the pinned `event120_generic_boot.session_class`
    over the still-connected bridge and the exact fresh post-install mapping.
    No ROM uploader is constructed. ``after_install`` may start audio capture
    before the new passive snapshot is acquired.
    """
    if (not isinstance(policy, flash.Policy) or policy not in flash._POLICIES
            or not isinstance(session, flash.DiagnosticSession)
            or session._policy._policy is not policy or session._policy.direction != "install"
            or session._latched or session._running):
        raise ValueError("Exact factory policy and unused install session required")
    policy.check_files(require_fresh=True)
    original = session._capture_binding()
    if (not isinstance(original, dict) or original.get("phase") != "loader"
            or not original.get("loader_sha256")
            or original.get("identity") != json.loads(policy.plan_bytes)["identity"]):
        raise ValueError("Install session is not bound to sealed transaction")
    if after_install is not None and not callable(after_install):
        raise ValueError("after_install must be callable")
    # Own the one and only success result; no detached result can be supplied.
    result = session.run()
    completed_at = time.time() if now is None else now
    journal, target_sha = _verify_completion(policy, result)
    logged = session._transport
    log_obj = getattr(logged, "log", None)
    if (not getattr(logged, "closed", False) or log_obj is None
            or getattr(log_obj, "fd", object()) is not None):
        raise ValueError("Install session lacks closed durable SG transcript")
    install_log_path = Path(install_log_path).absolute()
    if Path(log_obj.path).absolute() != install_log_path:
        raise ValueError("Install transcript is not the bound session log")
    install_log, command_count = _successful_sg_log(install_log_path, policy)
    if after_install is not None: after_install(dict(result))
    snapshot_path, snapshot_raw, snapshot = _load_snapshot(
        snapshot_provider, original, completed_at, now)
    root = Path(evidence_root).absolute()
    root_stat = root.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(root_stat.st_mode) or root_stat.st_uid != os.getuid()
            or stat.S_IMODE(root_stat.st_mode) != 0o700):
        raise ValueError("Owner-only boot evidence root required")
    marker, receipt_dir = root / ".generic-diagnostic-boot.consumed", root / "generic-diagnostic-boot"
    if os.path.lexists(marker) or os.path.lexists(receipt_dir):
        raise ValueError("One-use boot evidence already exists")
    evidence = list(_source_evidence())
    evidence.extend(((install_log_path, install_log), (snapshot_path, snapshot_raw)))
    for path, expected, _limit in policy.evidence: evidence.append((Path(path), expected))
    expected_binding = {k: original[k] for k in
                        ("phase", "loader_sha256", "usb_binding", "sg_binding", "identity")}
    record = {
        "schema": 1, "kind": BOOT_KIND, "completed_at": completed_at,
        "observed_at": snapshot["observed_at"], "usb_binding": snapshot["usb_binding"],
        "sg_binding": snapshot["sg_binding"], "loader_sha256": original["loader_sha256"],
        "identity": original["identity"], "target_sha256": target_sha,
        "plan_sha256": digest(policy.plan_bytes), "journal_sha256": digest(_canonical(journal)),
        "result_sha256": digest(_canonical(result)), "install_log_path": str(install_log_path),
        "install_log_sha256": digest(install_log), "install_command_count": command_count,
        "snapshot_path": str(snapshot_path), "snapshot_sha256": digest(snapshot_raw),
        "upload_operations": 0, "flash_operations_after_install": 0,
        "retry": False, "boot_observed": False,
    }
    raw = _canonical(record)
    transport_prepared = getattr(getattr(logged, "inner", None), "prepared", None)
    bridge = getattr(transport_prepared, "bridge", None)
    mapping_bytes = getattr(transport_prepared, "mapping", None)
    header_type = getattr(transport_prepared, "header_type", None)
    if (bridge is None or not isinstance(mapping_bytes, bytes)
            or mapping_bytes != _canonical(snapshot["sg_binding"]) or header_type is None):
        raise ValueError("Install session lacks exact reviewed USB/SG bridge binding")
    prepared = Prepared(root, raw, digest(raw), _canonical(expected_binding), tuple(evidence),
                        digest(install_log), marker, _PREPARED, policy, bridge, mapping_bytes, header_type)
    _PREPARED.add(prepared)
    receipt_dir.mkdir(mode=0o700)
    fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try: os.write(fd, prepared.campaign_sha256.encode("ascii")); os.fsync(fd)
    finally: os.close(fd)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try: os.fsync(fd)
    finally: os.close(fd)
    campaign_path = receipt_dir / "campaign.json"
    with open(campaign_path, "xb") as fp:
        fp.write(raw); fp.flush(); os.fsync(fp.fileno())
    fd = os.open(receipt_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try: os.fsync(fd)
    finally: os.close(fd)
    out_log = receipt_dir / "commands.jsonl"
    if os.path.lexists(out_log): raise ValueError("Boot log already exists")
    def log(event, **fields):
        row = _canonical({"time": time.time(), "event": event, **fields}) + b"\n"
        fd = os.open(out_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try: os.write(fd, row); os.fsync(fd)
        finally: os.close(fd)
    log("completed_diagnostic_boot_prepared", campaign_sha256=prepared.campaign_sha256,
        target_sha256=target_sha, commands=1, upload_operations=0,
        flash_operations_after_install=0, retry=False, boot_observed=False)
    ResetSession = generic_boot.session_class(reset_module)
    boot = ResetSession(prepared, log)
    try:
        result = boot.request_reset()
        log("completed_diagnostic_boot_request_completed", **result, retry=False)
        return result
    except BaseException as exc:
        log("completed_diagnostic_boot_stopped", error=type(exc).__name__,
            detail=str(exc), retry=False, boot_observed=False)
        raise
    finally:
        boot.close()
