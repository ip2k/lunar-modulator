# Installer diagnostic provenance

[verified: source and host tests] Each diagnostic service job now retains
canonical catalogue/toolchain manifests and host bindings for the exact source
commit/tree/archive, worker entry point/image and request. Collection rechecks
those inputs before binding app, ELF and receipt hashes into provenance.json.
The API checks the envelope against its admitted request and verified outputs,
caps it at 65,536 bytes, and exposes bounded digest/profile metadata only.

This is diagnostic provenance, not firmware installation approval. The service
still emits expanded-d9000 with twelve Shapes voices; its sidecar explicitly
declares incompatibility with the trusted schema-2 expanded-d7000 packager.
Installability, hardware admission and hardware acceptance remain false.
Full input manifests remain local for later review. No delivery or deployment
path was enabled and no device operation was performed for this change.

[verified: host] Coordinator reran tests/test_installer_service.py using this
worktree's .venv: all cases passed except the existing optional retained-artifact
fixture skip. Delegate reported 88 passed, one skipped. Negative coverage includes
stale bindings, changed catalogue, empty/oversized envelope and overstated
installation/package status. The primary checkout's different Python environment
lacks FastAPI; its initial collection error was resolved by using the correct
worktree interpreter. Existing Starlette/httpx deprecation warning remains.

Next: capture a separately verified build tuple compatible with the trusted
packager, after physical runtime/audio and recovery gates pass. This envelope
does not close those gates. Active firmware goal remains incomplete.
