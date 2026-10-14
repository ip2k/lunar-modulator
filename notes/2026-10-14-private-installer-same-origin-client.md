# Private installer same-origin client

Status: implemented client opt-in only; no backend deployment or public endpoint.
The default static Pages artifact remains offline and request-export-only.

## Behavior

Before this change, the installer page supported an injected buildClient in
its mount function, but the shipped page entry point never created or supplied
one. A served page therefore always exported a JSON request even when a
same-origin service might be available.

The page now creates its existing bounded build client only when the trusted
HTML contains the marker name lunar-installer-build-service with content
enabled. The shipped HTML sets this marker to disabled. The page derives the
API origin from its own location.origin; users cannot change it through a URL
parameter or form. Requests use same-origin credentials. The POST happens only
after the chooser button is explicitly activated. The existing export fallback
remains the behavior for the default/static page.

The client path reports the checked application flash use (bytes used, budget,
and remaining bytes) from a validated diagnostic receipt. It explicitly says
no installable firmware file is available. The full-song default remains
pending: Event Horizon Showcase is a reversible preselection, not owner musical
acceptance, native playback acceptance, or release admission.

## Deployment and security boundary

The repository's Pages workflow builds and publishes static assets, including
the generated catalogue; it does not run the FastAPI application. The marker
must stay disabled in that artifact. Enabling it is a deployment-owned change
for a private origin that serves the existing /api/v1/builds and status routes
on the same origin behind access controls.

The API module is currently a factory around an injected adapter and pinned
worker template. It has no production app wiring, authentication, CSRF
protection, or deployment configuration. Same-origin fetch credentials do not
supply those controls by themselves. Do not enable the marker until the
deployment has authenticated private access, validates request origin/CSRF,
applies bounded rate limits and queue/resource caps, and launches only a fixed
server-owned worker template in an isolated job. No compiler path, command,
image, or remote service origin comes from the browser.

FastAPI remains the smallest fit because the existing API and Pydantic request
validation already use it. Its official docs describe static frontend serving
through StaticFiles (and recommend app.frontend() for frontends), while its
background-task guide directs heavy work to a larger external job system; this
repository's fixed job-adapter seam is consistent with that split. See:
- https://fastapi.tiangolo.com/tutorial/static-files/
- https://fastapi.tiangolo.com/tutorial/background-tasks/
- https://fastapi.tiangolo.com/tutorial/testing/

## Verification

The focused Node suite passed 18 tests in the pinned Playwright 1.63.0 image
(sha256:eff16c30e6f3f4af0a03fa4b706120d5e9b0891c344a27d64559aff5900a4a27),
with 2 CPUs, 2 GiB memory, equal swap cap, no network, and the docker-batch
user slice. Browser integration used a local loopback HTTP server inside the
container and Playwright route stubs for the API, not a worker or deployed
backend. It enabled the marker in test HTML, mounted the shipped page entry
point without dependency injection, verified no request before click,
same-origin POST/poll, request order/startup selection, deselected effect
omission, rejected request, and stopped waiting. Desktop (1440x1000) and mobile
(375x812) viewport checks reported no horizontal overflow and kept the full-song
status pending. The diagnostic result displayed 785312 / 868836 flash bytes,
83524 free, and no installable file.

Private screenshot outputs (not committed):
- /tmp/lunar-installer-client-browser-20261014/installer-desktop.png
- /tmp/lunar-installer-client-browser-20261014/installer-mobile.png

The browser API is a stubbed response, so these checks establish frontend
wiring and receipt display only. They do not establish an actual build job,
private access-control posture, deployability, image installability, or device
playback. Those require a protected same-origin service deployment and a fresh
build through its real worker.
