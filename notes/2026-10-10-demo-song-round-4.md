# Demo-song Round 4 source revision

This note records the frozen-intent work after critic Round 3 (`cdf8d8fcc0bd89518f3fe28ec1a6661a827c19bc`). It is a source/structure checkpoint, not listening acceptance; the independent critic and parent full-song render/browser checks remain pending for this round.

Round 4 addresses the critic's remaining arrangement-specific requests in the generator and four authoritative `.lunar` files:

- Afterglow Relay emits distinct authored second four-bar peak sentences, common-tone chord voicings across changing chord sizes, and a bridge brightness/timbre drift. The R4 generator also stored a Warble tuple, but its sound configuration still selected Echo, so those values were inactive in the R4 emitted project. Round 5 corrects the selected insert and verifies the serialized result.
- Event Horizon and Neon Transit each launch one continuous eight-bar intro instead of repeating a four-bar scene. Their chain lengths stay at 116 and 104 bars respectively.
- Packet Bloom's Glitch includes a one-bar ensemble interruption with the exposed C#4-to-D4 lead resolution; the remaining Glitch bars retain their broken rhythm. Its Warble is Wow .64, Flutter .42, Mix .29.
- Each outro now places a full-bar tonic sustain in bass and chord; the melody also sustains the tonic for the closing bar, with Neon Transit resolving an octave above. Neon Transit withdraws new drum attacks in the last four bars.
- Peak second sentences and replies are distinct, chord/scale-aware events rather than late parameter changes alone. The source checker asserts these emitted-event properties and the intended scene transitions.

Verification on this source snapshot: `python3 -m py_compile tools/demo_songs.py`, generator `--write`/`--check` (9 generated files current), `engines/build/fm1-state check` on all four canonical projects (all `OK`, zero repaired/skipped/defaulted; estimated RAM 244,640 / 244,576 / 195,360 / 244,640 of 387,924), and `git diff --check`. These are format, generator, and host-estimate checks; they do not prove musical acceptance, actual device RAM fit, hardware playback, or listening quality.
