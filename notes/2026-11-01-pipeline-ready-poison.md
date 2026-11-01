# Native READY grant hook-order correction — 2026-11-01

Separate authorized correctness dependency. In the native adapter's pre-RUN loop,
the native_ms hook can synchronously set abort/common poison AFTER the timeout
expression's initial aborted read. READY/ENTERED could then grant RUN for that
iteration. Later start refusal overwrote command with REFUSED, hiding the grant
from a final status snapshot.

The correction rechecks existing abort/common poison in the READY branch before
storing RUN. It preserves the first error and permanent storage/one-attempt rules.
This closes synchronous hook ordering only; it is NOT an atomic grant against
arbitrary concurrent physical faults, memory corruption or a general memory-model
claim. No hardware path is enabled or executed.

The existing actual adapter fixture waits for real READY before its mocked launch
returns. The next CPU0 native_ms injects poison, with and without abort, and records
any observed RUN before final failure can hide it. Before correction, the
hook_poison_ready case failed its no-RUN assertion. Logs are retained privately
under scratch/cpu1-candidate-20261101/logs/ready-{red,green}.log. The normal and
ASan/UBSan suite covers both variants, preserved error 0x9123, zero callbacks and
one launch; normal lifecycle behavior and default refusal remain covered.

Parent owns independent review, CI and integration. Temporary host executables
are removed at lane handoff. No target compiler, device, transport or daemon was
required for this correction.
