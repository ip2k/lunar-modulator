# Aeon schema-9 matched profiling-package build

This task builds a schema-7 diagnostic control and a schema-9 stage-profile
variant from the same exact firmware source commit, using the frozen thirteen-
engine Event Horizon profile, selection, target toolchain, and pinned Aeon image.
The runner is derived from the reviewed stage-7 Aeon runner at SHA-256
`41d1b44b5f7dd303f5d44b4c19fa693b076d26d88abd5d93eaa4d778e661c808`; the byte-
identical source copy is retained as `frozen-run_aeon-stage7.py` for audit.

The pair is a *profiling-package* comparison, not a resampler-only overhead
measurement. The stage-7 control compiles without `--resampler-stage-profile`
and links without `--diagnostic-irq-profile` or
`--diagnostic-resampler-stage-profile`. The schema-9 variant adds all three
opt-ins. The app validator requires IRQ profiling alongside schema 9 and
forbids it alongside schema 7; schema 9 records the tracked IRQ union itself
and replaces the separate schema-6 packet cadence. Workload, engine/render
profiles, compiler/link flags, prepared EH+SET profile, selection, and source
SHA remain equal. Instrumentation overhead remains physically unmeasured.

On Aeon run `python3 run_pair.py --output <fresh-absolute-output-path>` from
this directory after acquiring the task claim. The wrapper checks frozen
stage-7 receipt/output hashes, prepared profile and selection pins, compiler
snapshot manifest, exact source commit, and the runner-derived flag deltas
before starting bounded sequential builds. Each build uses 16 catalogue
chunks, four concurrent containers at 2 CPU/2 GiB each, then a 4 CPU/4 GiB
link; containers use `docker-batch.slice`, no network, and explicit equal
memory/swap limits. The output records commands, image/toolchain receipts,
container exit/policy evidence, link artifacts, and readiness flags. No package
construction or device access occurs.

The exact source commit is `36988d0c2ef1b793e5f9d343fac1b9f6c4b7891f`.
