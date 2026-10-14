# Matched -Os target application size experiment - 2026-10-14

## Result

[verified] Recompiling all 167 catalogue objects with the pinned pi32v2 Clang using -Os plus LTO and linking the same full-song Event Horizon candidate, all 13 engines, all 55 selected modules, project loader, linked SAVE service, song-diagnostic runtime, and stack watermark produces a 962,588-byte app. That is 100,292 bytes larger than the matched -Oz baseline of 862,296 bytes. It fails the actual expanded-D9000 XIP link by 93,752 bytes and is 101,944 bytes over the prospective D7000 app budget of 860,644 bytes. -Os is not a viable size reduction here.

The -Os compiled LTO object files sum to 2,958,100 bytes across all 167 objects, versus 3,165,512 bytes for -Oz. The smaller bitcode/object total does not predict smaller linked output: after the target LTO link, .text grows from 0xD2380 to 0xEAB44 bytes (+100,292). Do not use cached object-file totals as an app-size proxy.

## Matched inputs and method

Source base: dbf008c7c88b87c54434e595a9e7617605bf4138. Pinned image: lunar-jieli-check:bookworm, image ID sha256:0fcc80c729c795f96758e301a86df8c42b466cc0b40cb9dfbaf8db693589eefc. Container limits: docker-batch.slice, 4 CPUs, 8 GiB memory and equal swap, 512 processes, network disabled, read-only root.

The full 16-shard catalogue was freshly compiled at -Os, with LTO, shared resampler, indexed TFT, Shapes at 12 voices, and all modules. Every shard report confirms -Os/LTO and the same 536-input source manifest; all 167 objects succeeded. Report manifest SHA-256: 1dde1115c10d385a0664053fd43f601a6c85e5912d183a3aea53e8c53eaf201d. The unmodified -Oz catalogue used for the comparison has the same target/profile settings and complete object coverage.

The experiment copied the exact source tree to a private staging directory and adapted only temporary native-probe scripts to compile/link with -Os. The temporary libc build was also changed from -Oz to -Os; the arithmetic runtime already uses -Os. No repository production code or builder gate was changed. The prepared profile SHA-256 is b4086fe3bc9e53e7bc6fc7c40a041fbbfdd46beb708ce318f218c3f63f3b1a46; it selects 55 modules and embeds Event Horizon Showcase (4,345 packed bytes) at startup index 0.

A regular attempt using the real expanded-D9000 app budget failed at the target XIP region: overflow 93,752 bytes. To inspect symbols after that failure, a second private diagnostic link temporarily enlarged only the copied experiment linker's XIP length; this is not a hardware layout or target profile. The resulting ELF/app hashes and sizes below describe that diagnostic artifact only. The direct probe's final verification marks installable=false and hardware admission/testing false. The SAVE service remained linked=true, storage_admitted=false, flash_io_bound=false, save_service_armed=false, runtime_verified=false, hardware_tested=false.

## Diagnostic link evidence

The widened-link app is 962,588 bytes (SHA-256 d360bdb441e18ba5557ed9be370cbdb9fc7010f8378835c0653ab47bec8d5643). ELF SHA-256: 6ff8a6e271641e40f6daa01c5599f1fbe843e273bfdc840036f7eedfce70fd36. Link map SHA-256: 0ca443f722eac30f3114643e9f92a07b36c530b2de689766b1240344876d8b98. Section report SHA-256: 203de537b499225910edb9ca1febfcc69ada1c9115c2bddb3412095fbadfda9e. Verification receipt SHA-256: 979996390127f19ff09080beb225332030948af832ccc5dddb8ffbc356ca902c. Artifact receipt SHA-256: e7ce2d4c13ffc00e760092bafcbc4d5f900c16776a51ea5e09b3ae85e6c5f984.

Sections: .text 0xEAB44; .ram_text 0x468; .data 0x70; .bss 0x4BE0; .pool 0x66AA0; .noinit 0x18. Stack watermark instrumentation verified by the probe. SDK-free link/key audit passed with 0 failed and 0 pending checks; RAM flash code call check passed. The widened diagnostic extent's layout_passed flag must not be read as a target-layout pass: the correctly budgeted D9000 link failed before an ELF existed.

Largest retained symbols in the diagnostic link:
- 50,688 B Plaits integrated wave data, _ZN6plaits20wav_integrated_wavesE (same size as -Oz)
- 46,999 B x0x_smp_ride (same as -Oz)
- 43,300 B x0x_smp_crash (same as -Oz)
- 24,159 B packed_braids (same as -Oz)
- 20,250 B x0x_smp_hh (same as -Oz)
- 15,996 B apply_op (versus 14,230 B at -Oz)
- 13,034 B fm1_app_encoder (versus 11,030 B at -Oz)
- 12,110 B fm1_app_render (versus 11,032 B at -Oz)
- 11,928 B draw (versus 10,508 B at -Oz)
- 10,644 B Crater render code
- 9,728 B x0x_pot_exp (same as -Oz)
- 8,192 B each MSFA kSinTab and kExp2Tab (same as -Oz)

Largest table/sample contributions are live data; this measurement does not prove they are safely removable. -Os also increases several selected live code symbols, so there is no obvious small code adjustment inferred from this one optimizer switch.

## Limits and next step

This is a private native target link-size experiment, not an audio performance benchmark. No runtime audio, complete song playback, hardware behavior, physical installation, SAVE storage admission, or owner musical acceptance was tested. Continuous mode was not used. No package was built or sent to hardware.

Keep -Oz as the smaller measured setting. There is no bounded compiler-flag-only change evidenced to close the 1,652-byte D7000 gap while retaining watermark. The next feature-preserving investigation should focus on storage representation of retained tables/sample assets, starting with a reversible offline A/B of the largest static Plaits wave data and selected samples. Any compression proposal must include decoder/access code, RAM scratch, startup/real-time costs, exact app size and target-side render/oracle evidence; don't subtract the gross compressed bytes. A gain in the 1.7 KiB range is only a minimum for the proposed D7000 arithmetic, not admission or a release decision.
