# Sequence candidate publication timestamps — 2026-11-01

[verified] Root review found actual candidate_profile.c passed two clock reads as
arguments to publish. C leaves argument evaluation order unspecified, so a
compiler may pass a later p_start and earlier p_end; the core correctly refuses
that reversed interval. The candidate-owned host stream fixture had the same
expression. Both now read p_start, then p_end in separate full expressions and
pass the stored values. No core, timing threshold, hardware or admission changes.

The already-reviewed a1eda9c7 native lifecycle portability correction is a separate
explicit test dependency, cherry-picked here as5a8e16c4. Coordinator root6ec7ca48
already has it and must retain its existing fixture rather than replace it with
this candidate ancestry. The minimal 19-path candidate port excludes that file.

[verified] Bounded search/read covered every tick/ms/clock/publish occurrence in
all cpu1_candidate source/header/assembly/profile files and the two owned candidate
fixtures. The two changed calls were the only paired timestamp argument calls;
remaining elapsed calculations use a stored baseline and one live sample or
separate full expressions. No new broad timing abstraction is introduced.

Focused actual candidate suite passes12 tests in17.78s with final explicit
fixture expressions:542 modes each normal and ASan/UBSan plus negative selection/
default compilation. Three-suite precheck passes27 in33.15s; production source
was stable, fixture declaration formatting was then split into two lines and
candidate suite rerun. Existing root GCC regression already demonstrates the
language portability failure; historical actual pi32 listing happened to choose
the intended order. This correction removes reliance on that compiler choice.

Actual profile initializes target MMIO/stacks and never returns. An artificial
host startup architecture was deliberately avoided. The authorized follow-up is
an actual five-TU target recompile/link and explicit listing trace of first clock
return to publish p_start and second return to p_end, source-bound by a fresh
receipt and independent review. That compile-path check is not device execution
or silicon/timing proof. Historical f703 approval/1c5 receipt remains historical
until the corrected source and fresh receipt are independently approved.
