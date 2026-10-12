# Demo-song Round 5 source corrections

This final allowed critic iteration starts from the frozen Round 4 source commit `75e029dcb4416c3b0381d0f6665fac0a6c0c3160`. It closes the two concrete correctness findings and incorporates bounded phrase refinements from the critic's R4-C review without changing the four-song scope:

- Afterglow Relay now selects Warble on its lead insert, so the documented Wow .26 / Flutter .12 / Mix .16 values are active in the emitted `.lunar` project. The checker validates the serialized insert and exact parameter values. R4 had stored the tuple but still selected Echo; that false impression is corrected in the R4 note.
- Peak chord-answer attacks sharing pitch and onset are coalesced into one event with the longer gate and stronger accent. The checker asserts there are no duplicate pitch/onset pairs across each peak answer clip.
- Afterglow Relay's Bridge holds G-B-D for one full bar across the Cmaj9-to-G6 common-tone change and stages a G4 pickup into the C-based second verse; its outro adds E4 before the final held A3.
- Event Horizon's Drop2 second sentence alternates full simultaneous chord stacks between 1.5- and 2-beat gates, preserving the unarpeggiated chord sound while varying its swell length.
- Neon Transit's first chorus now plays E4-G4-B4-C5-B4-G4-E4 over Em7, making the C5 suspension resolve through B4 before returning to E4. Afterglow, Event Horizon, and Packet Bloom each use a middle-register pickup in the penultimate outro bar before the final low tonic.

Source checks pass: `python3 -m py_compile tools/demo_songs.py`, generator `--write`/`--check` (9 outputs current), four `engines/build/fm1-state check` runs (all `OK`, zero repaired/skipped/defaulted; estimated RAM Afterglow 195,360, Event Horizon 244,576, Packet Bloom 195,360, Neon Transit 244,640 of 387,924), and `git diff --check`. Parent full-song render, browser save/open, and critic review remain separate gates. These project-state estimates do not establish physical FM-1 memory fit; no by-ear or hardware-playback claim is made. This note is part of the frozen R5 source snapshot; runtime receipts and the critic disposition remain separate evidence.
