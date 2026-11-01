# Private selected-Trio API, 2026-11-01

Base7abc5b4595b0483650836cf460dcb6fd7dec6d3f; branch
feature/2026-11-01@selected-trio-private-api. This lane owns api.py, server.py,
selected API tests, narrow server tests and this note. No browser/worker/native
changes, service/container activation or target build is in scope.

The existing v1 API retains its factory signature, canonical bytes, routes,
response shape and historical native prerequisite refusal. A private common
helper shares bounded body, queue, retention and lifecycle mechanics. A separate
explicitly enabled factory accepts only the v2 fixed Trio offline request and
exposes /api/v2/offline-builds and its status path, with loopback TrustedHost,
no docs/CORS/downloads. No CLI or public capability is activated.

The server supplies adapter.verify_selected_trio_result(build_id,request_bytes,
result), backed by that adapter's private recorded job inputs. Its summary is
checked again against the admitted canonical request, pinned source identity and
actual output hashes/sizes. Unknown claims and every true admission flag refuse.
No trusted anchors are reconstructed from result/envelope claims. WorkerResult
stays unchanged. Worker implementation is a separate owner/dependency; missing
callback capability refuses before worker construction in this checkout.

Selected verification has one dedicated executor slot and no pending work queue;
a concurrent verification receives503. A cancelled HTTP waiter cannot release
the slot before the underlying work completes. In-flight verification prevents
expiry/deletion, and shutdown drains verification before adapter shutdown and
job deletion. The trusted callback must use already acquired bounded private
bytes without subprocesses or external input acquisition.

Tests use existing FastAPI/TestClient and service venv, bytecode/cache disabled,
exact scratch/selected-trio-api/pytest basetemp removed at completion, and small
logs retained. Initial queue extraction plus selected HTTP checks:185 passed,
1 pre-existing retained-native-input skip. Further lifecycle/factory checks are
in progress. Synthetic callbacks test HTTP binding and are not native acceptance.

Rarefaction status confirms the shared primary Python profile; orient/scope
reject this sibling worktree path. Serena absolute create_app lookup matches
source lines621-765 before edits. No semantic root or server was switched.
Direct bounded source/Git inspection is the fallback. Existing maintained
FastAPI/Pydantic/Starlette/threading/concurrent.futures machinery is sufficient;
no package or licence change. Personal/noncommercial project. SDK inputs remain
private and untouched. Independent composed review precedes any allocated real
container or loopback execution. Source worktree stays until integration; keep
small evidence and remove owned test products in this flow.
