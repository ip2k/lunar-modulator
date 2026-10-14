# Local installer build-service prototype - 2026-10-14

## Outcome

Implemented a FastAPI/Pydantic API prototype for the coordinator design at `notes/2026-10-14-installer-build-service-design.md`. It provides bounded strict admission, an injected worker adapter, an in-memory fake lifecycle, and verification of a diagnostic result receipt against the admitted canonical request and exact app bytes.

This code does not create Jobs, start subprocesses, run compiler tools, persist state, serve artifacts, deploy, or contact a device. It is a local integration prototype, not a deployable service.

FastAPI/Pydantic fit the narrow JSON contract. The body is streamed and parsed before Pydantic validation so duplicate JSON object keys can be rejected. See [FastAPI request-body models](https://fastapi.tiangolo.com/tutorial/body/) and [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/). Pin metadata was checked at [FastAPI on PyPI](https://pypi.org/project/fastapi/), [Pydantic on PyPI](https://pypi.org/project/pydantic/), [Uvicorn on PyPI](https://pypi.org/project/uvicorn/), [HTTPX on PyPI](https://pypi.org/project/httpx/), and [pytest on PyPI](https://pypi.org/project/pytest/). Application and test pins are separate; audit transitive licenses before distribution/deployment.

## Contract and safety boundary

- POST accepts the version-1 selection schema: strict integer/string types, body up to 65,536 bytes, JSON plus identity encoding, duplicate/unknown key rejection, bounded unique ID lists, startup index validation, trusted Make-catalogue module-kind membership, and the eight source-defined project IDs.
- Queue admission is capped at 1-4, with opaque 192-bit random IDs and 429 retry guidance under pressure. Image digest, namespace, and command are immutable server-side template values. Requests cannot provide paths, compiler options, shell text, toolchain, image, or catalogue.
- GET discloses only admitted job state and a result summary. Success requires a receipt with unique JSON keys bound to private diagnostic status, canonical request SHA-256, ordered project IDs/startup index, exact app SHA-256/byte count, and diagnostic/non-installable flags. Artifact and receipt sizes are bounded. There is no artifact download or worker path exposure.
- The fake adapter exercises queued/running/succeeded/failed in tests and never starts a process or contacts Kubernetes. A real adapter, durable queue/admission store, request persistence/recovery, per-IP/global throttles, expiry, result storage, authentication/abuse controls, isolation, deployment, and public ingress remain unimplemented and unapproved.

## Verification

Executed on Hera using the task-specific Python 3.12 venv with FastAPI 0.143.0, Pydantic 2.14.1, Uvicorn 0.54.0, HTTPX 0.28.1, and pytest 8.4.2:

```text
25 passed, 1 warning
```

The warning is Starlette's deprecation notice that its TestClient integration with HTTPX is deprecated and suggests httpx2. It does not fail tests. Coverage includes accepted canonical admission and fixed-template forwarding; duplicate keys; strict scalar types; unknown fields/IDs/wrong groups; project/startup limits; content type/encoding/body cap; queue pressure; opaque lookups/state transitions; and receipt tampering, overclaims, and caps. The catalogue-loader test checks trusted lightweight Make metadata/project constants, not a firmware build.

Dependencies are pinned in `tools/installer_service/requirements-app.txt` and `requirements-test.txt`. No default app instance or network listener is created: construction requires an injected template and adapter.

## Limits and next dependency

This is not a deployment, security review, durable job system, or end-to-end build result. Fake-adapter receipts are unit-test evidence only. The next integration step requires owner-approved private job/image/result storage and resource/isolation design, followed by a separately reviewed real adapter. Before public exposure, settle same-origin hosting/proxy, abuse controls, retention, authentication, and quota. The service returns only `private-diagnostic-build`; it must never be wired to install/flash.
