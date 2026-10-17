# Private continuous build: Aeon image contract v2

[reported: owner] Hera is unavailable for builds during RAID/M.2/NIC maintenance;
use Aeon instead. The existing trusted continuous wrapper required image
`0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc`,
which is absent on Aeon. Historical records identify it as a Hera-built image.
The floating Debian/apt recipe cannot reproduce that historical image ID.

[verified: read-only Aeon inspection] The separately identified cached image is
`sha256:bcffae0f43893343df2c5ec1a0e53458682cc421f1e33ec7802a98482afd3495`,
Linux/amd64. Its complete environment is exactly
`PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`.
Entrypoint is null; its inherited labels are exactly `project=lunar-modulator`
and `session=gplfu`. Those are image metadata, not new task names.

[verified: bounded offline execution] Python 3.11.2, GNU Make 4.3, GCC/G++
12.2.0 and binutils 2.40 executed successfully inside this exact image. The
full installed-package vector and image inspection are retained on Aeon at
`/home/claude/.local/share/codex-coordination/tasks/lunar-aeon-image-prerequisites-20261017/`.
The container used no network, read-only rootfs, uid 1001, no capabilities,
no-new-privileges, docker-batch.slice, one CPU, 256 MiB RAM/equal swap and 64
PIDs. It exited zero and was removed. Handoff SHA-256:
`84759a9c2e538f3f1d46ddf537beeb740b0383c8bd84a86241fae45a36e493cd`.

[verified: source] The continuous wrapper and independent capture validator now
pin this exact image as a new private build contract. Both require the full
merged label map: the two immutable base labels plus the two explicit
`lan.project=lunar-modulator` / `lan.session=continuous-tuple-capture` task
labels. Equality remains exact: unknown, missing or changed labels fail. The
image environment, command, mounts, toolchain/compiler hashes, resources and
security checks are unchanged. There is no caller-selected image parameter.
The separate frozen Trio runner and all historical tuples/receipts retain
their original identities; this update does not revalidate them as v2 builds.

[verified: focused host tests] Wrapper and tuple-capture suites passed 41
cases; one optional private-artifact case skipped. Checks include matching
producer/capture pins and refusal of missing, changed or extra image labels.
This is not a real producer execution or successful tuple capture. A fresh
clean checkout, current catalogue, exact request and new output directory
are still required to exercise that path on Aeon.

No hardware, installation, corresponding-source completeness, distribution,
realtime playback or release acceptance is granted. Existing admission flags
remain false. Shared semantic servers still select the primary checkout;
exact-path inspection and focused tests supplied this change's evidence.
