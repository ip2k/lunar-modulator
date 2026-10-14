# Installer diagnostic build tuple retention

The private build worker used to copy only `app.bin` and `image.json` from its bounded build scratch directory. The linker ELF at `link/lunar-app-probe.elf` was discarded, even though `image.json` carried an `elf_sha256`. A later package-preparation step therefore had no retained ELF bytes to compare with the build receipt.

The worker now exports a third bounded regular file, `elf.bin`, capped at 16 MiB. The actual retained full-song and Shapes 8 linker ELFs measured 994,536 and 977,956 bytes on Hera, respectively. The worker rejects duplicate-key or malformed receipt JSON and verifies both app and ELF digests before writing the tuple. The Docker adapter requires all three files to be nonempty regular files, enforces caps, and checks stable lengths while reading. `WorkerResult` now holds app bytes, receipt bytes, and ELF bytes; the API independently checks `elf_sha256` against the retained ELF before reporting success. Status reports only ELF digest and length; no content-download endpoint was added.

The original image receipt is retained byte-for-byte in the internal result. Its existing request/profile/build verification digests and project/module metadata remain the provenance source; this change invents no missing source, toolchain, or catalogue fields. Admission/installability/hardware flags remain false. This does not make the diagnostic result a package or authorize delivery or flashing.

Focused checks on Hera:

- `pytest -o addopts= -q -ra tests/test_installer_service.py`: 64 passed, 1 skipped. The skip is the optional retained-real-build TestClient case (`LUNAR_RETAINED_BUILD` not set). One existing Starlette/httpx deprecation warning.
- `python3 -m py_compile tools/installer_service/api.py tools/installer_service/docker_adapter.py tools/installer_service/docker_worker.py`: passed.
- `git diff --check`: passed.

Tests cover worker digest correspondence and duplicate JSON keys, missing/empty/oversized/symlinked ELF outputs at the adapter boundary, API receipt/ELF tampering and size refusal, and successful retention through `WorkerResult`. No device, network service, package, download endpoint, or installability gate was exercised.

Next dependency: a separately reviewed package builder/download flow must consume this internal tuple while preserving the existing diagnostic-only boundary, validating complete source/request/profile provenance, and keeping release admission explicit and false until its independent gates are met.
