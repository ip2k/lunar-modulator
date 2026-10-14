# Real build tuple validation

This offline check used integrated base a0d46a9c9611a2240610df5df5d47117b93c1c34 and retained controller result /home/claude/mvave-fm1/fullsong-current-build-20261014/result. The requested /home/claude/mvave-fm1/d7000-target-link-20261014 is link-only: it has no selection/ or top-level image.json, so it cannot drive the retained-controller fixture.

tools.installer_service.docker_worker.verified_build_outputs(result) accepted the real app, ELF and image receipt tuple and independently matched receipt hashes to bytes:

- App: 862,296 bytes, SHA-256 b4eb29241bc32833a49d171c1b1ff0caa25246fdb94c66e604b78539afbdf956.
- ELF: 994,540 bytes, SHA-256 f370fdb840b723e78388b81f56a076d30a130ad560485281fbe6c2ad406d294a.
- The link verifier and checked_link_receipt agree on the one Event Horizon project, startup index 0, song-diagnostic mode with 120 seconds, and required SAVE service. The resulting receipt remains installable=false, hardware_admitted=false, hardware_tested=false, native_ram_verified=false, and native_playback_verified=false.

The retained TestClient fixture originally called checked_link_receipt with its default diagnostic mode, mismatching this build's song-diagnostic verification. The fixture now asserts exact song-diagnostic mode and 120 seconds and passes that mode explicitly. It also directly proves the checker refuses the wrong diagnostic mode.

Validation used LUNAR_RETAINED_BUILD=/home/claude/mvave-fm1/fullsong-current-build-20261014/result with the pinned task pytest binary on tests/test_installer_service.py and tests/test_native_demo_image_controller.py. Result: focused service/controller suite passed. The TestClient path used its fake job adapter but actual retained request, selection, prepared profile, verification, app and ELF; this was not a real Docker worker/API end-to-end run.

A test mutation experiment showed the service accepts a changed runtime_configuration.return_to_rom_seconds field in an otherwise valid receipt. The builder checker rejects wrong runtime metadata; service-side runtime enforcement remains a separate follow-up if required. No hardware, device, deployment, or installability claims are made. No binaries were copied into the repository.
