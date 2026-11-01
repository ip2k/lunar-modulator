"""Exercise the remote build wrapper's real shell flow without a LAN build."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "sim/web/build-on-aeon.sh"


def executable(path, source):
    path.write_text("#!/usr/bin/env python3\n" + source)
    path.chmod(0o755)


@pytest.fixture
def fake_remote():
    # The test and wrapper's logs/fetches stay inside this project's own tree.
    base = ROOT / "scratch/sim-web-stage-lifecycle-tests" / uuid.uuid4().hex
    bin_dir = base / "bin"
    bin_dir.mkdir(parents=True)
    remote = base / "remote"
    (remote / "playwright/node_modules/playwright").mkdir(parents=True)
    (remote / "playwright/node_modules/axe-core").mkdir()
    (remote / "playwright/owner-cache-marker").write_text("keep")
    calls = base / "docker.jsonl"
    barrier = base / "barrier"
    barrier.mkdir()
    containers = base / "containers"
    containers.mkdir()
    log_dir = ROOT / "sim/web/build/remote-runs"
    logs_before = set(log_dir.iterdir()) if log_dir.exists() else set()
    default_sine = next(line.split("=", 1)[1].strip()
                        for line in (ROOT / "engines/Makefile").read_text().splitlines()
                        if line.startswith("FM1_DX7_SINE ?="))
    trial_sine = "msfa" if default_sine == "trunc12" else "trunc12"
    trial = ROOT / f"sim/web/build/dx7-{trial_sine}"
    assert not trial.exists(), "isolated worktree should have no prior trial artifacts"

    executable(bin_dir / "ssh", """
import os, shlex, subprocess, sys
args = sys.argv[2:]  # host, then the exact script-supplied remote command
command = args[0] if len(args) == 1 else shlex.join(args)
if os.environ.get("FAKE_STAGE_FAIL") and command.startswith("bash -s --"):
    raise SystemExit(44)
raise SystemExit(subprocess.run(["bash", "-c", command], stdin=sys.stdin.buffer).returncode)
""")
    executable(bin_dir / "tar", """
import sys, tarfile
if "-cf" in sys.argv:
    with tarfile.open(fileobj=sys.stdout.buffer, mode="w|"):
        pass
elif "-x" in sys.argv:
    sys.stdin.buffer.read()  # drain git archive as well as the empty fake tar
else:
    raise SystemExit("unexpected tar operation")
""")
    executable(bin_dir / "docker", """
import json, os, pathlib, sys, time
args = sys.argv[1:]
with open(os.environ["FAKE_DOCKER_CALLS"], "a") as stream:
    stream.write(json.dumps(args) + "\\n")
if args[:2] == ["image", "inspect"]:
    if "--format" in args:
        print("fake@sha256:" + "0" * 64)
elif args[:1] == ["info"] or args[:1] == ["pull"]:
    pass
elif args[:2] == ["container", "inspect"]:
    raise SystemExit(0 if pathlib.Path(os.environ["FAKE_CONTAINERS"], args[2]).exists() else 1)
elif args[:2] == ["rm", "-f"]:
    pathlib.Path(os.environ["FAKE_CONTAINERS"], args[2]).unlink()
elif args[:1] == ["run"]:
    name = args[args.index("--name") + 1]
    stage = next(a[:-5] for a in args if a.endswith(":/src"))
    if os.environ.get("FAKE_WAIT_FOR_TWO"):
        pathlib.Path(os.environ["FAKE_BARRIER"], name).touch()
        deadline = time.monotonic() + 10
        while len(list(pathlib.Path(os.environ["FAKE_BARRIER"]).iterdir())) < 2:
            if time.monotonic() > deadline:
                raise SystemExit("concurrent run did not reach barrier")
            time.sleep(.01)
    if "alpine:3.22" in args and os.environ.get("FAKE_PAUSE_MUSL"):
        pause = pathlib.Path(os.environ["FAKE_PAUSE_MUSL"])
        pause.with_suffix(".started").touch()
        deadline = time.monotonic() + 10
        while not pause.with_suffix(".release").exists():
            if time.monotonic() > deadline:
                raise SystemExit("first build was not released")
            time.sleep(.01)
    if os.environ.get("FAKE_DOCKER_FAIL") == "alpine" and "alpine:3.22" in args:
        if os.environ.get("FAKE_DOCKER_LEFTOVER"):
            pathlib.Path(os.environ["FAKE_CONTAINERS"], name).touch()
        raise SystemExit(41)
    if "emscripten/emsdk:6.0.10" in args:
        www = pathlib.Path(stage, "sim/web/www")
        build = pathlib.Path(stage, "sim/web/build")
        www.mkdir(parents=True, exist_ok=True)
        build.mkdir(parents=True, exist_ok=True)
        marker = os.environ.get("FAKE_ARTIFACT_MARKER")
        (www / "fm1.wasm").write_bytes((marker + ":wasm").encode() if marker else b"fake wasm")
        gpl = int(next(a.split("=", 1)[1] for a in args if a.startswith("FM1_GPL_MODS=")))
        record = dict(wasm_bytes=9, parity=True, gpl_mods=gpl, dx7_sine="msfa", licences=[])
        if marker:
            record["marker"] = marker
        (www / "fm1.wasm.json").write_text(json.dumps(record))
        (www / "meta.json").write_text(json.dumps(dict(marker=marker)) if marker else "{}")
        (build / "parity.json").write_text(json.dumps(dict(marker=marker)) if marker else "{}")
    if "mcr.microsoft.com/playwright:v1.63.0-noble" in args:
        assert pathlib.Path(stage, "playwright/node_modules/playwright").is_dir()
        assert pathlib.Path(stage, "playwright/node_modules/axe-core").is_dir()
        build = pathlib.Path(stage, "sim/web/build")
        (build / "screenshots").mkdir(parents=True)
        (build / "screenshots/fake.png").write_bytes(b"png")
        (build / "readme-screenshots").mkdir()
        (build / "readme-screenshots/fake.png").write_bytes(b"png")
else:
    raise SystemExit("unexpected docker operation: " + repr(args))
""")
    executable(bin_dir / "scp", """
import os, pathlib, shutil, sys
args = [a for a in sys.argv[1:] if a not in ("-q", "-r")]
if os.environ.get("FAKE_SCP_FAIL") == "parity" and any("parity.json" in a for a in args[:-1]):
    raise SystemExit(43)
dest = pathlib.Path(args[-1])
for source in args[:-1]:
    src = pathlib.Path(source.split(":", 1)[1])
    target = dest / src.name if dest.is_dir() else dest
    if src.is_dir():
        shutil.copytree(src, target)
    else:
        shutil.copy2(src, target)
""")
    env = os.environ.copy()
    env.update(PATH=f"{bin_dir}:{env['PATH']}", FM1_SIM_HOST="fake@host",
               FM1_REMOTE_DIR=str(remote), FM1_DX7_SINE=trial_sine,
               FAKE_DOCKER_CALLS=str(calls), FAKE_BARRIER=str(barrier),
               FAKE_CONTAINERS=str(containers),
               PYTHONDONTWRITEBYTECODE="1")
    yield base, env, calls, log_dir, trial

    if trial.exists():
        shutil.rmtree(trial)
    if log_dir.exists():
        for entry in set(log_dir.iterdir()) - logs_before:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
        if not any(log_dir.iterdir()):
            log_dir.rmdir()
    shutil.rmtree(base)
    if not any(base.parent.iterdir()):
        base.parent.rmdir()
    lock_dir = ROOT / "sim/web/build/publish-locks"
    if lock_dir.exists() and not any(lock_dir.iterdir()):
        lock_dir.rmdir()


def run_wrapper(env, *args):
    return subprocess.run(["bash", str(SCRIPT), *args], cwd=ROOT, env=env,
                          text=True, capture_output=True, timeout=30)


def run_logs(log_dir):
    return sorted(log_dir.glob("build-*.log"), key=lambda p: p.stat().st_mtime_ns)


def test_success_and_failed_fetch_preserves_previous_results(fake_remote):
    base, env, calls, log_dir, trial = fake_remote
    success = run_wrapper(env, "--readme-screenshots")
    assert success.returncode == 0, success.stdout + success.stderr
    assert (trial / "fm1.wasm").read_bytes() == b"fake wasm"
    assert (trial / "parity.json").read_text() == "{}"
    assert (trial / "screenshots/fake.png").exists()
    assert (trial / "readme-screenshots/fake.png").exists()
    prior = {p.name: p.read_bytes() for p in trial.iterdir() if p.is_file()}

    failed_env = dict(env, FAKE_SCP_FAIL="parity")
    failure = run_wrapper(failed_env, "--no-screenshot")
    assert failure.returncode == 43, failure.stdout + failure.stderr
    assert {p.name: p.read_bytes() for p in trial.iterdir() if p.is_file()} == prior
    logs = run_logs(log_dir)
    assert len(logs) == 2
    for log in logs:
        contents = log.read_text()
        assert "cleanup=ok" in contents and "stage=" in contents
        stage = next(line[6:] for line in contents.splitlines() if line.startswith("stage="))
        assert not Path(stage).exists()
        assert not (log_dir / (log.stem + ".fetch")).exists()
    assert not list((base / "remote/runs").iterdir())
    assert (base / "remote/playwright/owner-cache-marker").read_text() == "keep"
    docker_calls = [json.loads(line) for line in calls.read_text().splitlines()]
    page = next(call for call in docker_calls if call[:1] == ["run"]
                and "mcr.microsoft.com/playwright:v1.63.0-noble" in call)
    assert any(arg.endswith("/playwright:/pw") for arg in page)
    assert "--memory=8g" in page and "--memory-swap=8g" in page
    assert "--cgroup-parent=docker-batch.slice" in page


def test_concurrent_failed_runs_get_distinct_stages_and_cleanup(fake_remote):
    base, env, calls, log_dir, _ = fake_remote
    env.update(FAKE_WAIT_FOR_TWO="1", FAKE_DOCKER_FAIL="alpine",
               FAKE_DOCKER_LEFTOVER="1")
    # Different destinations may build together; the same destination may not.
    commands = [["bash", str(SCRIPT), "--no-screenshot"],
                ["bash", str(SCRIPT), "--no-screenshot", "--engines-ref", "HEAD"]]
    processes = [subprocess.Popen(command, cwd=ROOT, env=env, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                 for command in commands]
    try:
        results = [process.communicate(timeout=30) for process in processes]
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=5)
    assert [process.returncode for process in processes] == [41, 41], results
    logs = run_logs(log_dir)
    assert len(logs) == 2
    stages = [next(line[6:] for line in log.read_text().splitlines()
                   if line.startswith("stage=")) for log in logs]
    assert len(set(stages)) == 2
    assert all(not Path(stage).exists() for stage in stages)
    assert not list((base / "remote/runs").iterdir())
    docker_calls = [json.loads(line) for line in calls.read_text().splitlines()]
    runs = [call for call in docker_calls if call[:1] == ["run"]]
    assert len(runs) == 2
    assert all("--name" in call and "--rm" in call for call in runs)
    assert len({call[call.index("--name") + 1] for call in runs}) == 2
    assert not list((base / "containers").iterdir())
    removed = [call[2] for call in docker_calls if call[:2] == ["rm", "-f"]]
    assert set(removed) == {call[call.index("--name") + 1] for call in runs}


def test_failed_stage_allocation_never_touches_shared_sources(fake_remote):
    base, env, calls, _, _ = fake_remote
    shared = base / "remote/src"
    shared.mkdir()
    (shared / "owner-data").write_text("keep")
    failure = run_wrapper(dict(env, FAKE_STAGE_FAIL="1"), "--no-screenshot")
    assert failure.returncode == 44, failure.stdout + failure.stderr
    assert (shared / "owner-data").read_text() == "keep"
    assert not (base / "remote/runs").exists()
    assert not calls.exists()  # no image pull or container launch
    assert not list((ROOT / "sim/web/build/publish-locks").glob("*.lock"))


def test_same_destination_concurrent_build_refuses_overlap_then_publishes_whole_set(fake_remote):
    base, env, calls, log_dir, trial = fake_remote
    pause = base / "pause-a"
    first_env = dict(env, FAKE_ARTIFACT_MARKER="A", FAKE_PAUSE_MUSL=str(pause),
                     FM1_GPL_MODS="0")
    first = subprocess.Popen(["bash", str(SCRIPT), "--no-screenshot"], cwd=ROOT,
                             env=first_env, text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
    try:
        import time
        deadline = time.monotonic() + 10
        while not pause.with_suffix(".started").exists():
            assert first.poll() is None
            assert time.monotonic() < deadline
            time.sleep(.01)
        second_env = dict(env, FAKE_ARTIFACT_MARKER="B", FM1_GPL_MODS="1")
        overlap = run_wrapper(second_env, "--no-screenshot")
        assert overlap.returncode == 75, overlap.stdout + overlap.stderr
        pause.with_suffix(".release").touch()
        first_output = first.communicate(timeout=30)
        assert first.returncode == 0, first_output
    finally:
        pause.with_suffix(".release").touch()
        if first.poll() is None:
            first.kill()
            first.communicate(timeout=5)

    def assert_set(marker, gpl):
        assert (trial / "fm1.wasm").read_bytes() == f"{marker}:wasm".encode()
        record = json.loads((trial / "fm1.wasm.json").read_text())
        assert (record["marker"], record["gpl_mods"]) == (marker, gpl)
        assert json.loads((trial / "meta.json").read_text())["marker"] == marker
        assert json.loads((trial / "parity.json").read_text())["marker"] == marker

    assert_set("A", 0)
    retry = run_wrapper(second_env, "--no-screenshot")
    assert retry.returncode == 0, retry.stdout + retry.stderr
    assert_set("B", 1)
    assert any("publication_busy" in log.read_text() for log in run_logs(log_dir))
    assert not list((ROOT / "sim/web/build/publish-locks").glob("*.lock"))
    assert not list((base / "remote/runs").iterdir())


def test_ref_spellings_that_sanitize_to_one_destination_share_claim(fake_remote):
    base, env, _, log_dir, _ = fake_remote
    pause = base / "pause-alias"
    first_env = dict(env, FAKE_PAUSE_MUSL=str(pause), FAKE_DOCKER_FAIL="alpine")
    first = subprocess.Popen(["bash", str(SCRIPT), "--no-screenshot",
                              "--engines-ref", "HEAD~0"], cwd=ROOT, env=first_env,
                             text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        import time
        deadline = time.monotonic() + 10
        while not pause.with_suffix(".started").exists():
            assert first.poll() is None
            assert time.monotonic() < deadline
            time.sleep(.01)
        overlap = run_wrapper(env, "--no-screenshot", "--engines-ref", "HEAD^0")
        assert overlap.returncode == 75, overlap.stdout + overlap.stderr
        pause.with_suffix(".release").touch()
        first.communicate(timeout=30)
        assert first.returncode == 41
    finally:
        pause.with_suffix(".release").touch()
        if first.poll() is None:
            first.kill()
            first.communicate(timeout=5)
    assert any("publication_busy" in log.read_text() and "ref-HEAD_0" in log.read_text()
               for log in run_logs(log_dir))
    assert not list((ROOT / "sim/web/build/publish-locks").glob("*.lock"))
    assert not list((base / "remote/runs").iterdir())
