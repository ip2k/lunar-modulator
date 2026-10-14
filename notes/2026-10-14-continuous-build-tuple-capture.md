# Continuous native build tuple capture

This capture attaches immutable provenance to the retained fresh continuous
D7000 build output. It did not compile or rebuild firmware.

The source is pinned to commit
298ff12a506b40f60efb1ae236894d661634ed90. The application is 845,716 bytes,
SHA-256 0a7a2fecbd730586b8792e7da6c9a6cf35fa26ae4fb77798b93b5f30e9922f02.
The ELF SHA-256 is
7c79e47b0261f0a8ac7bdbf80ff61a3250dedac04503df0efa9b9ca75c887e9d.
The tuple identifies the expanded-D7000 profile, continuous runtime,
FM-1_500 application identity, and FM-1_000 recovery identity.

Private capture products live at
/home/claude/.local/share/codex-private/continuous-tuple-20261014/run-298ff12/build-output/build/
and are mode 0600:
- build_tuple.json SHA-256 9c246fb70bfb04cb6a6adbaf845fe71a882ba0228317b286f648b502b2e66ec4
- build-provenance.json SHA-256 2d8c80fd69df3dd5015fa1d64866d29f7035b0ba0fe8204ea5bac25ba66b5094
- tuple-capture.json SHA-256 b82b9cf2dd606f19778fc6dd8b37a1efed6d80152da036cd83664f9f7d6a7943
- catalogue-manifest.json SHA-256 af1462fc04d6a6614c4b2d5b417e43c2670361095ea1484a8b7b03e2e5fd0429
- source-tree-manifest.json SHA-256 ed9c5ae33deaee9c91826e4fc0ea883fdab7397b33e9a7bf4ba9b1990dd7710e

The original container invocation, source snapshot, catalogue snapshot, toolchain
manifest, request, and build receipts were rechecked by the capture routine.
The tuple/provenance bind the invocation, request and prepared-profile raw
digests, complete catalogue/toolchain/source manifests, compiler identity,
worker source and provenance, wrapper, linked objects, app, ELF, and receipts.
Independent checks confirmed the image/artifact app bytes and lengths, ELF
digest, raw verification/artifact receipt digests, and tuple/provenance hashes.

All installable, hardware-admitted and hardware-tested fields are false.
SAVE remains linked but disarmed; storage and flash-I/O admission remain false.
This is not an FWSC package, installation, recovery proof, or hardware acceptance.

Validation on Hera for commit c7045fe791fa5737a0877c4e04d65e60ff993ce5:
the focused capture, wrapper, and image-controller suite passed 93/93 tests;
py_compile and git diff --check passed. The new orchestration test uses the
retained private inputs and stops at container inspection before sidecar writes;
it skips if those private inputs are unavailable. The separate authorized
capture-only invocation then wrote the sidecars above without rebuilding.

The authorized capture-only retry completed against the original retained build
output. The invocation record remained byte-identical (SHA-256
7f993540ed6c4f3a74b140a379c3ef5153c3c46a95adbdb059f4aedb8011a3b4); there was
no compile, rebuild, Docker run, or receipt regeneration. The capture routine
revalidated the recorded source, catalogue snapshot, toolchain, request,
prepared profile, wrapper, worker source/provenance, linked-object inventory,
app, ELF, and controller receipts before writing the private sidecars.

The complete artifact hashes and capture boundaries above are the result. The
capture-only operation proves provenance for this retained diagnostic output;
it does not validate an FWSC package. A separately reviewed, offline package
validation is the next proposed step and has not been run.
