# Private selected-Trio API, 2026-11-01

Base `7abc5b4595b0483650836cf460dcb6fd7dec6d3f`; branch
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

Selected retention is capped at four jobs and 16 MiB private evidence per job.
A no-op adapter deletion cannot release API record capacity; confirmed absence
is required. Valid requests are unavailable outside an active ASGI lifespan.
Shutdown closes admission before draining the executor and adapter.

Tests use existing FastAPI/TestClient and service venv, bytecode/cache disabled,
exact scratch/selected-trio-api/pytest basetemp removed at completion, and small
logs retained. Seven focused suites pass 392 tests and six subtests, with one
pre-existing retained-native-input skip and the existing Starlette deprecation
warning. Cancellation, blocked-verifier responsiveness, shutdown ordering,
confirmed-delete capacity and repeated lifespan tests are in-process only.
Synthetic callbacks test HTTP binding and are not native acceptance.

Rarefaction status confirms the shared primary Python profile; orient/scope
reject this sibling worktree path. Serena absolute create_app lookup matches
source lines621-765 before edits. No semantic root or server was switched.
Direct bounded source/Git inspection is the fallback. Existing maintained
FastAPI/Pydantic/Starlette/threading/concurrent.futures machinery is sufficient;
no package or licence change. Personal/noncommercial project. SDK inputs remain
private and untouched. Independent composed review precedes any allocated real
container or loopback execution. Source worktree stays until integration; keep
small evidence and remove owned test products in this flow.

Focused command: existing service .venv/bin/python -m pytest with
PYTHONDONTWRITEBYTECODE=1, -o addopts='' -q -p no:cacheprovider and
--basetemp=scratch/selected-trio-api/pytest; files selected_trio_api, service,
server, request_contract, selected_trio_profile, native_profile and trusted_policy.
Final log: scratch/selected-trio-api/final-tests.log. The separate worker lane
provides profile_id/toolchain_archive/cxx_headers config fields and the trusted
callback; composed source review/tests are required after that dependency lands.
No actual HTTP listener/container/native execution acceptance is claimed here.

Preparatory independent review identified request canonicalization dropping an
unknown empty set_ids field from result summaries. Summary validation now requires
the exact expected key set before comparing values; a causal regression refuses it.

Independent composition review then found the inherited Docker adapter removed
its ownership maps before an ignored filesystem removal, making get(None) false
cleanup evidence. The actual delete method now retains maps/capacity until lstat
confirms the exact owned directory entry is absent, under the lifecycle lock.
Removal errors, no-op removal, symlinks and inaccessible entries retain recovery
state. Tracked live workers/processes cannot lose their paths. Selected records
also require terminal status and confirmed container cleanup. There is no Docker
operation in delete and no name-only cleanup. The worker integration must retain
its selected_inputs/selected_verified maps until this same confirmation succeeds;
that separate branch is not incorporated here.

Three causal regressions failed against 25d962b before the correction: API
capacity-one expiration after no-op/raised removal, and shutdown after no-op
removal. Production delete tests now cover recovery success, lock ownership,
live/uncertain guards and the cancelled HTTP waiter followed by shutdown.
Submission, results and container state are synthetic; deletion is the actual
production method on owned fixture directories. Focused five-suite result:
238 passed, one expected retained-input skip. RED/GREEN logs and final combined
results are retained under scratch/selected-trio-api/cleanup-*.log; disposable
basetemps are removed after the run. No listener, container, native build,
device traffic, private donor data or production capability was used or enabled.
