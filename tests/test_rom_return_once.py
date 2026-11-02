"""Actual fixed host with invented manifest/fake serial; never open a port."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time

import pytest

from tools.jieli import rom_return_once as host


def image_manifest():
    return dict(schema=1, candidate="return-r01", source_base=host.SOURCE_BASE,
                contract_sha256=host.CONTRACT_SHA256, return_payload_manifest_sha256=host.RETURN_MANIFEST_SHA256,
                payload_sha256=host.PAYLOAD_SHA256, board="pico2_w", build_id=host.BUILD_ID,
                upstream_commit="a7fb5e8ac692c528f8ed29e325911a3f4b8111d6", usb=host.USB,
                strict_source_commit="1" * 40, recipe_sha256="2" * 64, pico_build_manifest_sha256="5" * 64,
                patch_sha256={"0001": "b67768211e058c1f558720c7205295e6ec09dc3318f6491eb73566e2086a163f",
                              "0002": "9b4565fbc5a27d3034e13fb7ddcc7dbdcb7d1f60427424656da33abf9617d045",
                              "0003": "3" * 64}, uf2=dict(bytes=512, sha256="4" * 64))


class FakeSerial:
    def __init__(self, *, replies=None, fault=None, mount=17):
        self.writes = []
        self.buffer = b""
        self.closed = False
        self.replies = replies or {}
        self.fault = fault
        self.mount = mount

    @property
    def in_waiting(self):
        return len(self.buffer)

    def write(self, raw):
        self.writes.append(raw)
        name = raw.split(b"\n", 1)[0].decode().removeprefix("rr01-")
        self.phase = name
        if self.fault == (name, "crash"):
            os._exit(77)
        if self.fault == (name, "write"):
            return len(raw) - 1
        default = (f"OK rr01-ready v=1 build=rr01-pico-v1 mount={self.mount}\n".encode()
                   if name == "ready" else f"OK rr01-{name} mount={self.mount}\n".encode())
        self.buffer = self.replies.get(name, default)
        return len(raw)

    def flush(self):
        if self.fault == (self.phase, "flush"):
            raise OSError("fake flush failure")
        if self.fault == (self.phase, "block_flush"):
            time.sleep(60)

    def read(self, count):
        if self.fault == (self.phase, "read"):
            raise OSError("fake disconnect")
        if self.fault == (self.phase, "partial"):
            self.buffer = self.buffer.rstrip(b"\n")
        if not self.buffer:
            time.sleep(.002)
        result, self.buffer = self.buffer[:count], self.buffer[count:]
        return result

    def close(self):
        self.closed = True


@pytest.fixture
def private_tmp_path():
    # pytest's default /tmp ancestor is intentionally refused by the host on
    # Linux. Keep real filesystem tests inside the project's owned namespace;
    # TemporaryDirectory removes each test's inputs and spent records at exit.
    scratch = host.ROOT / "scratch"
    scratch.mkdir(mode=0o700, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rom-return-once-", dir=scratch) as directory:
        yield Path(directory)


@pytest.fixture
def inputs(private_tmp_path):
    parent = private_tmp_path / "private"
    parent.mkdir(mode=0o700)
    payload = parent / "payload"
    payload.write_bytes(b"\x80\x00" + bytes(510))
    manifest = parent / "reviewed-image.json"
    raw = json.dumps(image_manifest()).encode()
    manifest.write_bytes(raw)
    fake = FakeSerial()
    return dict(port="/dev/rr01-test-only", campaign=parent / "campaign", payload_path=payload,
                image_manifest=manifest, _reviewed_image_pin=hashlib.sha256(raw).hexdigest(),
                _serial_factory=lambda port: fake), fake


def test_unset_pin_and_unreviewed_cli_manifest_refuse_before_serial(inputs, monkeypatch):
    args, fake = inputs
    with monkeypatch.context() as patch:
        patch.setattr(host, "_read_file", lambda *a: pytest.fail("UNSET pin read an input"))
        with pytest.raises(ValueError, match="UNSET"):
            host._run_once(**dict(args, _reviewed_image_pin=None))
    # The CLI has the real pin; an invented fixture manifest must fail before
    # campaign allocation or the serial factory, with no private-seam bypass.
    monkeypatch.setattr(host, "_Campaign", lambda *a: pytest.fail("unreviewed CLI allocated a campaign"))
    with pytest.raises(SystemExit) as caught:
        host.main(["--port", args["port"], "--campaign", str(args["campaign"]), "--payload", str(args["payload_path"]),
                   "--reviewed-image-manifest", str(args["image_manifest"])])
    assert caught.value.code == 1 and not fake.writes and not args["campaign"].exists()


REVIEWED_IMAGE = host.ROOT / "firmware/rom-witness-return/reviewed-pico-image.json"


def test_reviewed_image_matches_recipe_and_patch_inventory():
    image = json.loads(REVIEWED_IMAGE.read_bytes())
    source = host.ROOT / "tools/fm1-transporter"
    build_manifest = source / "return-r01-build-manifest.json"
    assert host._sha(build_manifest.read_bytes()) == image["pico_build_manifest_sha256"]
    assert host._sha((source / "build-rom-return.sh").read_bytes()) == image["recipe_sha256"]
    for name in json.loads(build_manifest.read_bytes())["patches"]:
        assert host._sha((source / name).read_bytes()) == image["patch_sha256"][name[:4]]


def test_exact_reviewed_image_preflight_and_default_pin_flow(inputs):
    args, fake = inputs
    raw = REVIEWED_IMAGE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == host.REVIEWED_IMAGE_MANIFEST_SHA256
    args["image_manifest"] = REVIEWED_IMAGE
    args.pop("_reviewed_image_pin")
    payload, image = host._preflight(args["payload_path"], REVIEWED_IMAGE,
                                     _reviewed_image_pin=host.REVIEWED_IMAGE_MANIFEST_SHA256)
    assert payload == b"\x80\x00" + bytes(510)
    assert image["strict_source_commit"] == "ff1fed64c180a4e604f21bf6d34146f295f7f859"
    assert image["uf2"] == dict(bytes=144384, sha256="fecc4f116e212bed5906e7519a93ffe4907e1c93229307c43736b97f85dcbfaf")
    result = host._run_once(**args)  # Real default pin; only transport is fake.
    assert result["transport_return_evidence"] is True and len(fake.writes) == 3
    assert all(result[key] is False for key in ("hardware_admitted", "flashed_image_verified",
               "rom_abi_qualified", "fetch_coherence_qualified", "watchdog_lease_qualified", "installable"))
    receipt = json.loads((args["campaign"] / "campaign.json").read_text())
    assert receipt["reviewed_image_manifest_sha256"] == host.REVIEWED_IMAGE_MANIFEST_SHA256
    assert receipt["uf2"] == image["uf2"] and receipt["flashed_image_verified"] is False
    with pytest.raises(FileExistsError):
        host._run_once(**args)
    assert len(fake.writes) == 3


@pytest.mark.parametrize("field", ["strict_source_commit", "recipe_sha256", "pico_build_manifest_sha256",
    "patch_sha256", "uf2_sha256", "uf2_bytes", "contract_sha256", "source_base", "payload_sha256", "board",
    "approval", "whitespace"])
def test_reviewed_identity_mutation_refuses_with_real_pin_before_io(inputs, field):
    args, fake = inputs
    image = json.loads(REVIEWED_IMAGE.read_bytes())
    if field == "patch_sha256":
        image[field]["0003"] = "0" * 64
    elif field.startswith("uf2_"):
        image["uf2"][field.removeprefix("uf2_")] = "0" * 64 if field.endswith("sha256") else 144896
    elif field == "approval":
        image["approved"] = True
    elif field != "whitespace":
        image[field] = "pico" if field == "board" else "0" * len(image[field])
    raw = (json.dumps(image, indent=2) + "\n").encode()
    if field == "whitespace":
        raw += b"\n"
    args["image_manifest"].write_bytes(raw)
    args.pop("_reviewed_image_pin")
    with pytest.raises(ValueError, match="manifest digest mismatch"):
        host._run_once(**args)
    assert not fake.writes and not args["campaign"].exists()


def test_complete_fixed_flow_is_durable_and_spent(inputs, monkeypatch):
    args, fake = inputs
    events = []
    original_sync = os.fsync
    original_record = host._Campaign.record
    current = []
    def sync(fd):
        events.append((current[0] if current else "parent", "dir" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file"))
        return original_sync(fd)
    def record(self, name, value):
        current.append(name)
        try:
            return original_record(self, name, value)
        finally:
            current.pop()
    old_write = fake.write
    def write(raw):
        required = "jump_intent_consumed" if raw == b"rr01-call\n" else "upload_attempted" if raw.startswith(b"rr01-upload\n") else "campaign.json"
        assert (required, "file") in events and (required, "dir") in events
        return old_write(raw)
    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(host._Campaign, "record", record)
    monkeypatch.setattr(fake, "write", write)
    result = host._run_once(**args)
    assert result["status"] == "bounded_call_return_evidence" and result["transport_return_evidence"] is True
    assert result["hardware_admitted"] is False and result["flashed_image_verified"] is False
    assert fake.writes == [b"rr01-ready\n", b"rr01-upload\n" + b"\x80\x00" + bytes(510), b"rr01-call\n"]
    assert fake.closed and stat.S_IMODE(args["campaign"].stat().st_mode) == 0o700
    names = {"campaign.json", "upload_attempted", "jump_intent_consumed", "outcome.json"}
    assert {p.name for p in args["campaign"].iterdir()} == names
    before = {p.name: p.read_bytes() for p in args["campaign"].iterdir()}
    assert all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in args["campaign"].iterdir())
    with pytest.raises(FileExistsError):
        host._run_once(**args)
    assert before == {p.name: p.read_bytes() for p in args["campaign"].iterdir()}
    assert len(fake.writes) == 3


@pytest.mark.parametrize("field,value", [
    ("source_base", "0" * 40), ("contract_sha256", "0" * 64), ("board", "pico"),
    ("build_id", "ordinary-recovery"), ("schema", True), ("uf2", {"bytes": True, "sha256": "a" * 64}),
    ("uf2", {"bytes": 0, "sha256": "a" * 64}), ("uf2", {"bytes": 512, "sha256": "bad"}),
    ("usb", {}), ("strict_source_commit", "short"), ("patch_sha256", {}),
])
def test_even_repinned_wrong_manifest_refuses_before_io(inputs, field, value):
    args, fake = inputs
    image = image_manifest()
    image[field] = value
    raw = json.dumps(image).encode()
    args["image_manifest"].write_bytes(raw)
    args["_reviewed_image_pin"] = host._sha(raw)
    with pytest.raises(ValueError):
        host._run_once(**args)
    assert not fake.writes and not args["campaign"].exists()


@pytest.mark.parametrize("damage", ["payload", "digest", "extra", "duplicate", "oversize", "source"])
def test_local_preflight_refuses_without_io(inputs, monkeypatch, private_tmp_path, damage):
    args, fake = inputs
    if damage == "payload":
        args["payload_path"].write_bytes(bytes(512))
    elif damage == "digest":
        args["_reviewed_image_pin"] = "0" * 64
    elif damage == "source":
        new_root = private_tmp_path / "source"
        path = new_root / "firmware/rom-witness-return/manifest.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"changed")
        monkeypatch.setattr(host, "ROOT", new_root)
    else:
        raw = args["image_manifest"].read_bytes()
        if damage == "extra":
            raw = raw[:-1] + b',"approved":true}'
        elif damage == "duplicate":
            raw = raw[:-1] + b',"schema":1}'
        else:
            raw = b"x" * (host.MAX_MANIFEST + 1)
        args["image_manifest"].write_bytes(raw)
        args["_reviewed_image_pin"] = host._sha(raw)
    with pytest.raises(ValueError):
        host._run_once(**args)
    assert not fake.writes and not args["campaign"].exists()


@pytest.mark.parametrize("kind", ["symlink", "fifo", "empty", "large"])
def test_bounded_nofollow_input_files(inputs, kind):
    args, fake = inputs
    path = args["payload_path"]
    original = path.read_bytes()
    path.unlink()
    if kind == "symlink":
        dest = path.with_name("kept")
        dest.write_bytes(original)
        path.symlink_to(dest)
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        path.write_bytes(b"" if kind == "empty" else original + b"x")
    with pytest.raises((ValueError, OSError)):
        host._run_once(**args)
    assert not fake.writes


@pytest.mark.parametrize("kind", ["directory", "file", "symlink", "fifo", "shared_parent"])
def test_campaign_refuses_preexisting_or_shared_without_io(inputs, kind):
    args, fake = inputs
    path = args["campaign"]
    if kind == "directory":
        path.mkdir()
    elif kind == "file":
        path.write_bytes(b"keep")
    elif kind == "symlink":
        path.symlink_to(path.parent, target_is_directory=True)
    elif kind == "fifo":
        os.mkfifo(path)
    else:
        path.parent.chmod(0o750)
    with pytest.raises((ValueError, OSError)):
        host._run_once(**args)
    assert not fake.writes


@pytest.mark.parametrize("record", ["campaign.json", "upload_attempted", "jump_intent_consumed", "outcome.json"])
@pytest.mark.parametrize("fault", ["open", "write", "file_fsync", "dir_fsync"])
def test_actual_persistence_failures_never_grant_a_later_phase(inputs, monkeypatch, record, fault):
    args, fake = inputs
    original_record = host._Campaign.record
    current = []
    def tracked(self, name, value):
        current.append(name)
        try:
            return original_record(self, name, value)
        finally:
            current.pop()
    monkeypatch.setattr(host._Campaign, "record", tracked)
    def wrap(original, kind):
        def call(*a, **kw):
            actual = kind
            if kind == "fsync":
                actual = "dir_fsync" if stat.S_ISDIR(os.fstat(a[0]).st_mode) else "file_fsync"
            if current and current[-1] == record and actual == fault:
                raise OSError("injected persistence refusal")
            return original(*a, **kw)
        return call
    for name in ("open", "write", "fsync"):
        monkeypatch.setattr(os, name, wrap(getattr(os, name), name))
    if record in ("campaign.json", "outcome.json"):
        with pytest.raises(OSError):
            host._run_once(**args)
    else:
        assert host._run_once(**args)["status"] == "refused"
    expected = {"campaign.json": 0, "upload_attempted": 1, "jump_intent_consumed": 2, "outcome.json": 3}[record]
    assert len(fake.writes) == expected
    with pytest.raises(FileExistsError):
        host._run_once(**args)
    assert len(fake.writes) == expected


@pytest.mark.parametrize("record", ["upload_attempted", "jump_intent_consumed"])
@pytest.mark.parametrize("kind", ["symlink", "fifo", "file"])
def test_preexisting_receipt_cannot_be_overwritten(inputs, monkeypatch, record, kind):
    args, fake = inputs
    original = host._Campaign.record
    target = args["campaign"].parent / "keep"
    target.write_bytes(b"keep")
    def create(self, name, value):
        if name == record:
            p = args["campaign"] / name
            if kind == "symlink":
                p.symlink_to(target)
            elif kind == "fifo":
                os.mkfifo(p)
            else:
                p.write_bytes(b"keep")
        return original(self, name, value)
    monkeypatch.setattr(host._Campaign, "record", create)
    assert host._run_once(**args)["status"] == "refused"
    assert len(fake.writes) == (1 if record == "upload_attempted" else 2)
    assert target.read_bytes() == b"keep"


@pytest.mark.parametrize("phase", ["ready", "upload", "call"])
@pytest.mark.parametrize("fault", ["write", "flush", "read", "partial"])
def test_serial_faults_are_spent_without_retry(inputs, monkeypatch, phase, fault):
    args, fake = inputs
    fake.fault = (phase, fault)
    monkeypatch.setattr(host, "IO_SECONDS", .025)
    monkeypatch.setattr(host, "READY_SECONDS", .025)
    result = host._run_once(**args)
    assert result["status"] == ("inconclusive" if phase == "call" else "refused")
    assert result["transport_return_evidence"] is False and fake.closed
    assert len(fake.writes) == {"ready": 1, "upload": 2, "call": 3}[phase]
    with pytest.raises(FileExistsError):
        host._run_once(**args)


@pytest.mark.parametrize("ready", [b"0", b"01", b"4294967296", b"+1", b"1 ", b"1\r", b"1\nextra\n"])
def test_noncanonical_mount_or_extra_ready_refuses(inputs, ready):
    args, fake = inputs
    fake.replies["ready"] = b"OK rr01-ready v=1 build=rr01-pico-v1 mount=" + ready + b"\n"
    assert host._run_once(**args)["status"] == "refused"
    assert len(fake.writes) == 1


@pytest.mark.parametrize("mount", [1, 4294967295])
def test_canonical_mount_boundaries(inputs, mount):
    args, fake = inputs
    fake.mount = mount
    assert host._run_once(**args)["mount"] == mount
    assert len(fake.writes) == 3


@pytest.mark.parametrize("phase", ["upload", "call"])
@pytest.mark.parametrize("suffix", [b"18\n", b"17\r\n", b"17\nextra", b"17\nOK\n", b"17 extra\n"])
def test_nonexact_completion_cannot_be_success(inputs, phase, suffix):
    args, fake = inputs
    fake.replies[phase] = b"OK rr01-" + phase.encode() + b" mount=" + suffix
    result = host._run_once(**args)
    assert result["status"] == ("inconclusive" if phase == "call" else "refused")
    assert len(fake.writes) == (3 if phase == "call" else 2)


def test_alarm_conflicts_masks_and_nonmain_thread_refuse_before_io(inputs):
    args, fake = inputs
    old = signal.getsignal(signal.SIGALRM)
    with ThreadPoolExecutor(max_workers=1) as executor:
        with pytest.raises(ValueError, match="main-thread"):
            executor.submit(host._run_once, **args).result()
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        with pytest.raises(ValueError, match="alarm conflicts"):
            host._run_once(**args)
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 50
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    mask = signal.pthread_sigmask(signal.SIG_BLOCK, [signal.SIGALRM])
    try:
        with pytest.raises(ValueError, match="unblocked"):
            host._run_once(**args)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, mask)
    assert signal.getsignal(signal.SIGALRM) == old and not fake.writes


def child(args, code):
    setup = """
import json,sys,signal,time
from pathlib import Path
from tools.jieli import rom_return_once as host
from tests.test_rom_return_once import FakeSerial
args=json.loads(sys.argv[1])
for key in ('campaign','payload_path','image_manifest'): args[key]=Path(args[key])
"""
    encoded = json.dumps({k: str(v) for k, v in args.items() if k != "_serial_factory"})
    return [sys.executable, "-c", setup + code, encoded]


@pytest.mark.parametrize("phase", ["open", "upload", "call"])
def test_real_alarm_interrupts_actual_driver_blocking_phase_in_child(inputs, phase):
    args, fake = inputs
    script = """
host.IO_SECONDS=.05
phase=sys.argv[2]
transport=FakeSerial(fault=(phase,'block_flush'))
def previous(signum,frame): pass
signal.signal(signal.SIGALRM,previous)
old=signal.getsignal(signal.SIGALRM)
def factory(port):
    if phase=='open': time.sleep(60)
    return transport
start=time.monotonic()
result=host._run_once(**args,_serial_factory=factory)
assert result['status']==('inconclusive' if phase=='call' else 'refused') and result['reason']=='TimeoutError'
assert len(transport.writes)=={'open':0,'upload':2,'call':3}[phase]
assert transport.closed == (phase!='open')
assert time.monotonic()-start < 2
assert signal.getsignal(signal.SIGALRM)==old
assert signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0)
print('actual blocking phase interrupted; timer/handler restored')
"""
    run = subprocess.run(child(args, script) + [phase], cwd=host.ROOT, capture_output=True, text=True, timeout=5)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "actual blocking phase interrupted" in run.stdout


@pytest.mark.parametrize("reply", [b"ERR rr01-ready\n", b"OK rr01-ready v=2 build=rr01-pico-v1 mount=1\n",
    b"OK rr01-ready v=1 build=ordinary-recovery mount=1\n", b"x" * 96 + b"\n"])
def test_ready_errors_wrong_build_and_overflow_refuse(inputs, reply):
    args, fake = inputs
    fake.replies["ready"] = reply
    assert host._run_once(**args)["status"] == "refused"
    assert len(fake.writes) == 1


def test_unsolicited_bytes_and_parent_fsync_fail_before_commands(inputs, monkeypatch):
    args, fake = inputs
    original = os.fsync
    def fail(fd):
        raise OSError("parent fsync failure")
    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(OSError):
        host._run_once(**args)
    assert args["campaign"].is_dir() and not fake.writes
    with pytest.raises(FileExistsError):
        host._run_once(**args)
    monkeypatch.setattr(os, "fsync", original)
    args["campaign"] = args["campaign"].with_name("other-campaign")
    fake.buffer = b"unsolicited\n"
    assert host._run_once(**args)["status"] == "refused"
    assert not fake.writes


def test_partial_persistence_writes_finish_before_wire(inputs, monkeypatch):
    args, fake = inputs
    original = os.write
    calls = []
    def partial(fd, raw):
        calls.append(len(raw))
        return original(fd, raw[:7])
    monkeypatch.setattr(os, "write", partial)
    assert host._run_once(**args)["transport_return_evidence"] is True
    assert len(calls) > 20 and len(fake.writes) == 3


def test_missing_deadline_platform_primitive_refuses_before_io(inputs, monkeypatch):
    args, fake = inputs
    with monkeypatch.context() as patch:
        patch.delattr(signal, "setitimer")
        with pytest.raises(ValueError, match="POSIX"):
            host._run_once(**args)
    assert not fake.writes and not args["campaign"].exists()


@pytest.mark.parametrize("phase", ["upload", "call"])
def test_process_crash_keeps_attempt_and_refuses_restart(inputs, phase):
    args, fake = inputs
    run = subprocess.run(child(args, f"host._run_once(**args,_serial_factory=lambda _:FakeSerial(fault=('{phase}','crash')))"),
                         cwd=host.ROOT, capture_output=True, text=True, timeout=5)
    assert run.returncode == 77
    assert (args["campaign"] / "upload_attempted").is_file()
    assert (args["campaign"] / "jump_intent_consumed").exists() == (phase == "call")
    with pytest.raises(FileExistsError):
        host._run_once(**args)
    assert not fake.writes


def test_two_actual_processes_cannot_share_campaign(inputs):
    args, fake = inputs
    code = """
try:
    transport=FakeSerial()
    result=host._run_once(**args,_serial_factory=lambda _:transport)
except FileExistsError:
    print('lost-exclusive-claim')
else:
    assert len(transport.writes)==3
    print('one-fixed-flow')
"""
    processes = [subprocess.Popen(child(args, code), cwd=host.ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for _ in range(2)]
    try:
        output = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 0, stdout + stderr
            output.append(stdout.strip())
        assert sorted(output) == ['lost-exclusive-claim', 'one-fixed-flow']
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)


def alias_swap(monkeypatch, outer, other, *, old_open, relative_component):
    """Swap after old resolve, or just before corresponding openat component."""
    original_open = os.open
    parent_identity = (outer.parent.stat().st_dev, outer.parent.stat().st_ino)
    outer_identity = (outer.stat().st_dev, outer.stat().st_ino)
    moved = outer.with_name("outer-retained")
    fired = []
    def open_with_swap(path, *args, **kwargs):
        relative_parent = kwargs.get("dir_fd")
        identity = None
        if relative_parent is not None:
            info = os.fstat(relative_parent)
            identity = (info.st_dev, info.st_ino)
        expected = parent_identity if relative_component == "outer" else outer_identity
        old_match = Path(path) == old_open and relative_parent is None
        new_match = path == relative_component and identity == expected
        if not fired and (old_match or new_match):
            outer.rename(moved)
            outer.symlink_to(other, target_is_directory=True)
            fired.append(True)
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(os, "open", open_with_swap)
    return fired, moved


@pytest.mark.parametrize("component", ["outer", "private"])
def test_campaign_ancestor_swap_cannot_hide_claim_and_replay(inputs, monkeypatch, component):
    args, first = inputs
    owner = args["campaign"].parent / "alias-case"
    outer, other = owner / "outer", owner / "other"
    for path in (owner, outer, other, outer / "private", other / "private"):
        path.mkdir(mode=0o700)
    args["campaign"] = outer / "private" / "campaign"
    with monkeypatch.context() as patch:
        fired, moved = alias_swap(patch, outer, other, old_open=args["campaign"].parent,
                                  relative_component=component)
        try:
            try:
                host._run_once(**args)
            except (OSError, ValueError):
                pass
            assert fired, "race injection must reach actual directory acquisition"
        finally:
            if fired:
                outer.unlink()
                moved.rename(outer)
    second = FakeSerial()
    args["_serial_factory"] = lambda _: second
    try:
        host._run_once(**args)
    except FileExistsError:
        pass
    facts = dict(first_writes=len(first.writes), second_writes=len(second.writes),
                 original_claim=args["campaign"].exists(),
                 redirected_claim=(other / "private" / "campaign").exists())
    assert len(first.writes) + len(second.writes) <= 3, facts
    assert not facts["redirected_claim"], facts


@pytest.mark.parametrize("component", ["outer", "private"])
def test_input_ancestor_swap_never_reads_redirected_file(inputs, monkeypatch, component):
    args, _ = inputs
    owner = args["campaign"].parent / "input-alias"
    outer, other = owner / "outer", owner / "other"
    for path in (owner, outer, other, outer / "private", other / "private"):
        path.mkdir(mode=0o700)
    source = outer / "private" / "input"
    source.write_bytes(b"original")
    (other / "private" / "input").write_bytes(b"redirect")
    with monkeypatch.context() as patch:
        fired, moved = alias_swap(patch, outer, other, old_open=source, relative_component=component)
        try:
            try:
                result = host._read_file(source, 32)
            except (OSError, ValueError):
                result = None
            assert fired, "race injection must reach actual input acquisition"
            assert result in (None, b"original"), result
        finally:
            if fired:
                outer.unlink()
                moved.rename(outer)


@pytest.mark.parametrize("mode", [0o720, 0o702, 0o1777])
@pytest.mark.parametrize("operation", ["input", "campaign"])
def test_writable_ancestor_refuses_even_with_private_terminal_directory(inputs, mode, operation):
    args, fake = inputs
    ancestor = args["campaign"].parent / "writable"
    ancestor.mkdir(mode=0o700)
    terminal = ancestor / "private"
    terminal.mkdir(mode=0o700)
    path = terminal / "input"
    path.write_bytes(b"input")
    ancestor.chmod(mode)
    try:
        with pytest.raises(ValueError, match="ancestors"):
            if operation == "input":
                host._read_file(path, 32)
            else:
                args["campaign"] = terminal / "campaign"
                host._run_once(**args)
        assert not fake.writes
    finally:
        ancestor.chmod(0o700)


def test_foreign_owned_ancestor_refuses(inputs, monkeypatch):
    from types import SimpleNamespace
    args, _ = inputs
    original = os.fstat
    identity = args["payload_path"].parent.stat().st_ino
    def foreign(fd):
        info = original(fd)
        if info.st_ino == identity:
            return SimpleNamespace(st_mode=info.st_mode, st_uid=os.geteuid() + 1000)
        return info
    monkeypatch.setattr(os, "fstat", foreign)
    with pytest.raises(ValueError, match="ancestors"):
        host._read_file(args["payload_path"], 512)


def test_failed_component_walk_closes_owned_descriptors(inputs, monkeypatch):
    args, _ = inputs
    link = args["payload_path"].parent / "alias"
    link.symlink_to(args["payload_path"].parent, target_is_directory=True)
    opened = set()
    original_open, original_close = os.open, os.close
    def tracked_open(*a, **kw):
        fd = original_open(*a, **kw)
        opened.add(fd)
        return fd
    def tracked_close(fd):
        opened.discard(fd)
        return original_close(fd)
    monkeypatch.setattr(os, "open", tracked_open)
    monkeypatch.setattr(os, "close", tracked_close)
    with pytest.raises(OSError):
        host._read_file(link / args["payload_path"].name, 512)
    assert not opened
