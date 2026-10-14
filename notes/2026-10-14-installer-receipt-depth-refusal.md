# Installer worker receipt nesting refusal

The diagnostic API checks worker receipts as untrusted JSON. [verified] A
20,012-byte receipt containing 10,000 nested arrays fits below its 65,536-byte
cap but raises `RecursionError` in the standard JSON decoder. The API and
Docker worker previously caught malformed syntax and encoding but omitted this
decoder exception. The API request-body parser already handled it.

Both receipt decoders now convert this failure to their existing `ValueError`
refusal. The API status route returns its existing generic HTTP 502 verification
error, without exposing receipt contents. Tests cover excessive nesting at the
status route and worker file reader, plus duplicate keys and invalid UTF-8.

Validation: the bounded payload reproduced `RecursionError` locally. The Mac
project interpreter lacks FastAPI, so route-test collection could not run there.
The complete `tests/test_installer_service.py` suite passed in the existing
Python 3.12 Hera container with read-only source/dependency mounts, at exact
source `2cdcc8eef600eb793e47cac30bd685be38e67f42`; one optional retained-artifact
test skipped. Log: `/home/claude/mvave-fm1/receipt-depth-check-20261014/pytest.log`.
Container image: `sha256:a2be656a55327f06b955781df241217e1da23a2fcef52040479dab8a8793e8fa`;
network disabled, one CPU, 2 GiB memory/swap, 256 PIDs, `docker-batch.slice`.
This change does not admit any firmware or enable artifact retrieval.
