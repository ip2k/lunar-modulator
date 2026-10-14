#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile and run the profile admission tests on Hera in the pinned image."""
import datetime
import hashlib
import pathlib
import subprocess
import sys
import uuid

ROOT = pathlib.Path(__file__).resolve().parents[2]
HOST = "claude@192.168.1.48"
IMAGE = "sha256:7e32dd6d9d9d02ed13b5d5b1480486e60a0010a8247d7e76c52cb9552c61ce5d"
STAMP = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN = f"project-storage-profile-{STAMP}-{uuid.uuid4().hex[:8]}"
REMOTE = f"/home/claude/mvave-fm1/{RUN}"
SOURCE = [ROOT / "firmware/native/project_storage_profile.h",
          ROOT / "tests/native/project_storage_profile_test.c"]


def run(args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


run(["ssh", "-o", "BatchMode=yes", HOST, f"mkdir -p {REMOTE}/src {REMOTE}/out"])
for path in SOURCE:
    run(["scp", "-o", "BatchMode=yes", str(path), f"{HOST}:{REMOTE}/src/{path.name}"])

remote_script = f"""set +e
docker run --name {RUN} --user 1001:1001 --network none \\
  --cgroup-parent docker-batch.slice --label lan.project=lunar-modulator \\
  --label lan.session={RUN} --cpus 1 --memory 512m --memory-swap 512m \\
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=128m \\
  -v {REMOTE}/src:/src:ro,z -v {REMOTE}/out:/out:rw,z \\
  {IMAGE} sh -ec 'gcc -std=c11 -O1 -g -Wall -Wextra -Werror \\
    -fsanitize=address,undefined -fno-omit-frame-pointer -fno-pie -no-pie \\
    -I/src /src/project_storage_profile_test.c -o /out/profile-test \\
    && /out/profile-test'
rc=$?
docker inspect {RUN} --format 'container_exit={{{{.State.ExitCode}}}} oom={{{{.State.OOMKilled}}}}'
inspect_rc=$?
docker rm {RUN} >/dev/null
test $inspect_rc -eq 0 && exit $rc
exit 99
"""
result = subprocess.run(["ssh", "-o", "BatchMode=yes", HOST, remote_script], text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
print(result.stdout, end="")
for path in SOURCE:
    print(f"sha256 {path.relative_to(ROOT)} {hashlib.sha256(path.read_bytes()).hexdigest()}")
print(f"remote_artifacts={REMOTE}/out")
sys.exit(result.returncode)
