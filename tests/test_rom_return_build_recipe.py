"""Offline, actual-wrapper checks for the fixed ROM-return build recipe."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/fm1-transporter/build-rom-return.sh"
UPSTREAM = "a7fb5e8ac692c528f8ed29e325911a3f4b8111d6"
SDK = "a1438dff1d38bd9c65dbd693f0e5db4b9ae91779"
TINYUSB = "86ad6e56c1700e85f1c5678607a762cfe3aa2f47"
PIO_USB = "fe9133fc513b82cc3dc62c67cb51f2339cf29ef7"
IMAGE_ID = "sha256:" + "6" * 64
IMAGE_REF = "lunar-pico-builder@sha256:" + "a" * 64


@pytest.fixture
def fake_inputs(tmp_path):
    upstream = tmp_path / "upstream"
    sdk = tmp_path / "sdk"
    tinyusb = sdk / "lib/tinyusb"
    (upstream / "lib/Pico-PIO-USB/src").mkdir(parents=True)
    tinyusb.mkdir(parents=True)
    (upstream / "lib/Pico-PIO-USB/src/dummy.c").write_text("/* fixture */\n")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    git = bin_dir / "git"
    git.write_text("""#!/usr/bin/env python3
import io, os, sys, tarfile
from pathlib import Path
a = sys.argv[1:]
assert a.pop(0) == '-C'
path = Path(a.pop(0))
cmd = a.pop(0)
if cmd == 'rev-parse':
    if path == Path(os.environ['FAKE_UPSTREAM']): print(os.environ['FAKE_UPSTREAM_SHA'])
    elif path == Path(os.environ['FAKE_SDK']): print(os.environ['FAKE_SDK_SHA'])
    elif path == Path(os.environ['FAKE_TINYUSB']): print(os.environ['FAKE_TINYUSB_SHA'])
    else: print(os.environ['FAKE_PIO_SHA'])
elif cmd == 'ls-tree':
    print('160000 commit ' + (os.environ['FAKE_PIO_SHA'] if path == Path(os.environ['FAKE_UPSTREAM']) else os.environ['FAKE_TINYUSB_SHA']) + '\\t' + a[-1])
elif cmd == 'status': pass
elif cmd == 'show': print('1700000000')
elif cmd == 'archive':
    with tarfile.open(fileobj=sys.stdout.buffer, mode='w|') as t:
        data = b'# fixture\\n'
        info = tarfile.TarInfo('CMakeLists.txt')
        info.size = len(data)
        t.addfile(info, io.BytesIO(data))
elif cmd in ('init', 'apply'): pass
else: raise SystemExit('unexpected git command: ' + cmd)
""")
    docker = bin_dir / "docker"
    docker.write_text("""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
a = sys.argv[1:]
with open(os.environ['FAKE_DOCKER_LOG'], 'a') as f: f.write(json.dumps(a) + '\\n')
if a[:2] == ['image', 'inspect']:
    print(os.environ['FAKE_RESOLVED_ID'])
elif a[0] == 'run':
    mount = next(a[i+1] for i,x in enumerate(a) if x == '-v' and a[i+1].endswith(':/build:rw'))
    build = Path(mount.removesuffix(':/build:rw'))
    for name in ('fm1_transporter_return_r01.uf2', 'fm1_transporter_return_r01.elf',
                 'fm1_transporter_return_r01.elf.map', 'return-r01.nm',
                 'return-r01.disasm', 'return-r01.sections', 'return-r01.size',
                 'compile_commands.json', 'CMakeCache.txt'):
        (build / name).write_text(name + '\\n')
    print('fake offline build')
else: raise SystemExit('unexpected docker command')
""")
    git.chmod(0o755)
    docker.chmod(0o755)
    log = tmp_path / "docker.jsonl"
    env = os.environ.copy()
    env.update(PATH=f"{bin_dir}:{env['PATH']}", FM1T_RETURN_UPSTREAM=str(upstream),
               FM1T_RETURN_SDK=str(sdk), FM1T_RETURN_TINYUSB=str(tinyusb),
               FM1T_RETURN_SDK_SHA=SDK, FM1T_RETURN_TINYUSB_SHA=TINYUSB,
               FM1T_RETURN_CPUSET="8-11", FAKE_UPSTREAM=str(upstream),
               FAKE_UPSTREAM_SHA=UPSTREAM, FAKE_SDK=str(sdk), FAKE_SDK_SHA=SDK,
               FAKE_TINYUSB=str(tinyusb), FAKE_TINYUSB_SHA=TINYUSB,
               FAKE_PIO_SHA=PIO_USB, FAKE_RESOLVED_ID=IMAGE_ID,
               FAKE_DOCKER_LOG=str(log))
    return tmp_path, env, log


def _run(inputs, image):
    tmp_path, env, log = inputs
    env["FM1T_RETURN_IMAGE"] = image
    out = tmp_path / "out"
    result = subprocess.run(["bash", str(SCRIPT), str(out)], env=env,
                            text=True, capture_output=True, check=False)
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, out, calls


@pytest.mark.parametrize("image", [IMAGE_ID, IMAGE_REF])
def test_resolves_then_runs_immutable_id_and_copies_sdk_map(fake_inputs, image):
    result, out, calls = _run(fake_inputs, image)
    assert result.returncode == 0, result.stderr
    assert calls[0] == ["image", "inspect", image, "--format", "{{.Id}}"]
    run = calls[1]
    assert run[0] == "run"
    assert IMAGE_ID in run
    assert run[run.index("sh") - 1] == IMAGE_ID
    assert image not in run or image == IMAGE_ID
    assert "--pull=never" in run and "--network=none" in run
    assert "--cpus=4" in run and "--cpuset-cpus=8-11" in run
    assert "--memory=6g" in run and "--memory-swap=6g" in run
    assert "-DCMAKE_EXE_LINKER_FLAGS=" not in run[-1]
    assert (out / "image-ref.txt").read_text() == image + "\n"
    assert (out / "image-id.txt").read_text() == IMAGE_ID + "\n"
    assert (out / "return-r01.map").read_text() == "fm1_transporter_return_r01.elf.map\n"
    assert (out / "artifact-sha256.txt").is_file()
    assert not (out / "stage").exists()


@pytest.mark.parametrize("image", ["lunar-pico-builder:latest", "sha256:abc", "lunar@sha256:abc"])
def test_rejects_floating_or_malformed_image_before_io(fake_inputs, image):
    result, out, calls = _run(fake_inputs, image)
    assert result.returncode == 64
    assert not out.exists()
    assert calls == []


def test_rejects_nonimmutable_or_mismatched_resolved_id(fake_inputs):
    tmp_path, env, log = fake_inputs
    env["FAKE_RESOLVED_ID"] = "lunar-pico-builder:latest"
    result, out, calls = _run(fake_inputs, IMAGE_REF)
    assert result.returncode != 0
    assert len(calls) == 1
    assert not (out / "return-r01-pico2_w.uf2").exists()
    shutil.rmtree(out)
    env["FAKE_RESOLVED_ID"] = "sha256:" + "f" * 64
    log.unlink()
    result, out, calls = _run(fake_inputs, IMAGE_ID)
    assert result.returncode != 0
    assert len(calls) == 1
