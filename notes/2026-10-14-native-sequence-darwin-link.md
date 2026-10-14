# Native sequence host linker portability

The native sequence probe in tests/test_native_project_sequences.py already obtains platform linker flags from tests/native_test_flags.py, but then appended GNU's -Wl,--gc-sections unconditionally. On macOS, Clang/ld rejects that option. The test now relies solely on the shared helper: Linux retains --gc-sections; Darwin uses -dead_strip. Production firmware flags and code are unchanged.

Validation on Hera, source base 845bfd5df92a43ca3f765419a49622c9293612f4, used the pinned lunar-recovery-pytest image, no network, and bounded docker-batch.slice resources. Command: python3 -m pytest -q -ra -p no:cacheprovider --basetemp=/tmp/lunar-native-seq tests/test_native_project_sequences.py. Result: 32 passed, 2 skipped. The skips are target-only compiler checks because FM1_NATIVE_TOOLCHAIN is absent in this test container. The Linux pass exercises the same platform-helper path after removing the duplicate literal; Mac coordinator verification is still pending.

Receipt directory: /home/claude/.local/share/codex-coordination/receipts/lunar-native-sequence-darwin-link-20261014/. Test log SHA-256: 7b0e989c9649795795bdb62fe2eeb568bbfbe06b7d6772925d24a5e86b808258. Updated test source SHA-256: ce86e566d66c0b0f806d3d24ac11af3d9e675e76ee588705be0627b006cc7ac7; helper unchanged SHA-256: c4ffd3ae3f1f9e4958c753ed70175232fa333d29868937d5d84e04940fb5f1f5.

The task worktree is not the active Mac semantic-tool root, so Rarefaction could not orient the remote test file and Serena could not resolve it in the current checkout. No shared semantic root was switched. No hardware or device operations were performed.
