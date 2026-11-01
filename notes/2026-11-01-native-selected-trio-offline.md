# Fixed Trio offline diagnostic, source milestone

This branch composes the reviewed selected PROJECT applier with the
root-integrated bounded reader and adds a separately named SDK-free Trio
diagnostic source path. It does not make a package, installer profile, ROM
return path, or device candidate. The existing FM6 diagnostic CLI and its
source/closure checks remain the default.

`selected_diagnostic_app.c` allocates a permanent external 16,384-byte sound
arena and 16,384-byte aligned bounded-reader workspace. Its startup calls
`fm1_app_init_arenas`, then passes the **linked** generated 597-byte Trio
blob to `lunar_selected_project_load` before the existing diagnostic platform
enables audio, Timer5 or interrupts. Startup is one-shot. A refusal is a
sticky silent fault; there is no reset, USB command, flash write, SAVE or
runtime project chooser. The current platform still spins on a fault or in
the main loop. `FM1_APP_STATE_EXTERNAL_WORKSPACE=1` applies only to this
profile, so the default large state workspace is not silently admitted.

`build_selected_trio_diagnostic.py` is a fixed wrapper around the existing
`build_diagnostic.py` toolchain pin, fresh output, inventory, source-manifest,
libc++ header, object graph, linker layout, symbol refusal and `audit_link`
gates. Its internal selected plan chooses `FM1_MODULES=trio` with
`FM1_GPL_MODS=1`, the selected app, applier and generated blob. There is no
public module or arbitrary project argument. The host preparer rebuilds the
fixed source through exact current Trio renderer metadata and strict
`fm1-state pack`; the target receipt binds both host tool hashes, metadata,
packed bytes, generated C/header/receipt, source manifest, object hashes,
ELF/flat bytes and the linked blob's address and byte equality. The receipt
names `sdk-free-selected-trio-offline-diagnostic-v1`, keeps hardware/release/
distribution admission false, and identifies Dinghy plus Felucca Trio as
GPL-3.0-only sources. It does not inherit FM6 voice or DX7-sine claims.

Host regression builds the actual generated blob and selected app, compares
its 14 parameters/info/level and 64-frame PCM with the current app's general
loader, and proves one-shot initialization and sticky silent fault behavior.
The default FM6 build plan is asserted separately. The integrated selected
applier's normal and ASan/UBSan actual-app oracle passed independently at
`a68a9e31c8c2ec3a4327b9a6029a7eede3767d31`. These host checks are not
target ABI, link, memory, deadline, audio-output or physical proof.

The source milestone requires independent review before any reserved target
compile. The later target job must use the pinned toolchain, 4 CPUs in the
assigned 8–11 lane and at most 6 GiB, keep small receipt/map/audit/ELF logs,
and remove reproducible objects. It must prove exact ELF blob bytes, zero
`audit_link` failures and actual XIP/RAM/stack/guard fit before anyone can
discuss a timed ROM return. The separate reset/mailbox/watchdog design is
still under review; this source deliberately contains none of it. The
installer service's arbitrary PROJECT/SET/SAVE contract remains refused.
