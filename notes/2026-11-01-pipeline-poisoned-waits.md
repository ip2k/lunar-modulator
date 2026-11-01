# Pipeline lifecycle poison escape — 2026-11-01

Personal/non-commercial work, authorized separately from the offline CPU1
candidate. The actual shared core could poll forever in core_start/core_finish
when its millisecond source stopped and a delay hook permanently poisoned it.
Timeout arithmetic alone cannot expire against a stopped clock.

The correction checks existing permanent poison in both polling predicates and
refuses finish if poison accompanies exit. It preserves the first per-core error,
normal timeout rules, permanent storage and one-attempt ownership. It adds no
retry, free, replay, hardware path or callback cancellation.

[verified] Before correction, the existing actual protocol fixture plus injected
stopped ms/failing delay reproduced BOTH start and finish hangs, each killed by
a one-second external subprocess watchdog. The fixture retains an unentered
worker for start and blocks the existing stack-report hook before exit for finish.
After correction, each returns refusal after one failing delay call; error701
survives later timeout refusal, counts/storage remain retained and no extra
callback executes. Only the host harness cancels its pthread after assertions.

[verified] Command: PYTHONDONTWRITEBYTECODE=1 primary-project .venv/bin/python
-m pytest -q -o addopts= -p no:cacheprovider tests/test_devkit_renderer_pipeline.py
--basetemp=scratch/cpu1-candidate-20261101/poison-green. Result: 12 passed in7.40s;
24 actual protocol modes through SDK wrapper AND atomic host adapter, normal and
ASan/UBSan =96 executions, plus build/header checks. Local Apple ASan, no silicon,
native timing, stalled bus or hung C-call proof. Hooks still must return; poison
does not forcibly interrupt a callback or make memory reusable.

Small private logs: scratch/cpu1-candidate-20261101/logs/core-poison-{red,green}.log.
Temporary compile/test trees are owned by this lane and removed at handoff.
Parent owns independent review, CI and integration of this separate correction.
