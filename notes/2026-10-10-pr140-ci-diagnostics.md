# Combined candidate CI diagnostics

This note preserves observed failures and limitations outside the candidate
branch. It does not authorize a merge, retry, changed acceptance threshold,
or device operation.

## Initial exact-head Pages result

[verified] PR [#140](https://github.com/ip2k/lunar-modulator/pull/140), head
`5d9fa46f2ae27f12d26c472813b1f4b0d3716b0c`, ran Pages
[38033498860, job 114159082740](https://github.com/ip2k/lunar-modulator/actions/runs/38033498860/job/114159082740).
The job concluded SUCCESS, with deployment skipped for the pull request.
The actual strict manual step reported:

```text
2026-10-10T07:13:56.7898116Z warning: warble (Warble) has no section in the manual; 06-effects.md lists it with its generated table only
2026-10-10T07:13:56.7906799Z warning: repeat (Repeat) has no section in the manual; 06-effects.md lists it with its generated table only
2026-10-10T07:13:56.7908386Z manual: 17 chapters, 42 engines and effects, sequencer in the build, 0 outline boxes; 0 errors, 2 warnings
```

[verified] This combined result is different from the earlier documentation
bundle's 40-entry, zero-warning manual receipt. The two missing usage
sections are a real documentation omission. The owner assigned their
correction to the documentation stream; the candidate remains unmerged.
A documentation correction requires a fresh exact-head CI result even
when engine and simulator source hashes remain unchanged.

## Observation and remaining gates

[verified] A read-only monitor records changes to PR140 checks and stops
if the exact head changes. It never reruns, cancels, or mutates a check.
Initial CI run: [38033498813](https://github.com/ip2k/lunar-modulator/actions/runs/38033498813).
At 07:14:25 UTC, Pages had succeeded, deployment was skipped, three checks
were running and ten were queued; no functional failure had been observed.
That snapshot is not a final CI acceptance.

The prior owner report that Sound 2 A crackled during a swap remains an
unresolved listening failure. Browser, native and offline parity receipts
do not establish a human listening pass or device readiness.
