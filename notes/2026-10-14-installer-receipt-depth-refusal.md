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

Checkpoint validation: the bounded payload reproduced `RecursionError` locally.
The Mac project interpreter lacks FastAPI, so route-test collection could not
run there; focused verification is pending in the existing Python 3.12 Hera
container with its read-only dependency mount. This change does not admit any
firmware or enable artifact retrieval.
