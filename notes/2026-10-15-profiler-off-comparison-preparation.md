# Profiler-off comparison preparation — 2026-10-15

The profiler-off build is staged as a separate comparison candidate. This is preparation and an in-progress physical campaign record, not evidence of boot or audio acceptance.

The frozen deployment bundle SHA-256 is `6a48026f531842a4eb7e8d7d9febd27081e092babe1b1f33468646b1de1b1c98`, with 14 staged files. File-only preflight passed. The first attempt encountered only constructor-created `__pycache__` extras; those were quarantined without changing source inputs, then preflight passed on the exact staged files. Campaign pin SHA-256 is `08802ea99a838db6e5db2c87df2084c54fc64a668f97bb0663627e29b88a22c5`.

The campaign was launched once as PID `219753` after fresh paired-read admission. At this note's checkpoint, the physical run has started but has not completed. A prior profiler-on baseline measured 464.450 produced blocks/s against 689.344 blocks/s required, with 224.879 underruns/s. The preceding cold-boot acceptance attempt failed; do not treat the current running capture as a successful cold boot or as musical acceptance until its evidence is reviewed.

The bound campaign handoff at `scratch/c0-profiler-off-deployment-v2/bound-rom103-v2/HANDOFF.md` now names the correct campaign digest. No device action was performed in this note update. Next: root reviews the single running campaign's completion evidence and compares it with the profiler-on baseline; preserve the no-retry rule and report boot, audio, and underrun results separately.
