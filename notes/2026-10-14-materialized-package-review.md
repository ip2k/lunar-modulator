# Materialized D7000 diagnostic FWSC review

Status: reviewed offline; structural checks pass. This is not updater or device acceptance.

## Artifact and tuple binding

Reviewed the private package at /home/claude/.local/share/codex-private/lunar-trusted-d7000-20261014/event-horizon-showcase-d7000-diagnostic.fwsc. It is 978,484 bytes, mode 0600, in a mode-0700 parent directory. SHA-256: 26402f8766ef523fc729bf16339291fa18c152c7da3e10717e2b8bd46af924d4. Its receipt is mode 0600, 1,716 bytes, SHA-256 3f489b267e97fd78c13fab9c05b52b420c70a2fe61d92f237e0967dc73038c4d; receipt path, size and digest match the file.

The private build tuple at /home/claude/mvave-fm1/combined-nor-target-20261014/out/companion-set/build_tuple.json hashes to the receipt's externally pinned digest 2005957ad3dfbb5e34030717c6f0045cb3c96265a24641b8c370f1c39d835a23. It names fm1-092-d7000 / expanded-d7000, song-diagnostic, app identity FM-1_990, recovery identity FM-1_000, and keeps hardware_admitted, hardware_tested, and installable false. Its app (845,732 bytes, SHA-256 ba46bf0a4d1bda4d604223c658b141b4a9068e37f65afddd998af04d5296cfc8), ELF (978,068 bytes, SHA-256 bb69fad7cf662dce19dbf8b265657717d3606404134a1bb68f7635cc8ef48b61), artifact receipt, build receipt, and provenance hashes each match retained build outputs and tuple fields.

## Reopen and decoded comparisons

tools/jieli/inspect_fwsc.py reopened the emitted package as FM-1_990. Header CRC, entry-list CRC, and all eight outer payload CRCs passed. Entry order/types were flash.bin, info.log, USR, isd_config.ini, ota.bin, script.ver, blimit.bin, and tail.bin; the flash allocation is 880,640 bytes (0xD7000). The stock OTA payload bytes match the retained stock ota.bin reference (19,969 bytes; SHA-256 ef1f2db89b011fa53e71df363f0122de0ea896618c53fb53e8da676322004541).

I also decoded the package flash through the strict model_092_app_replacement profile after normalizing only the outer package identity for that FM-1_092 decoder. Its nested record/app-area checks passed. The decoded app is exactly 845,732 bytes and has the tuple/receipt SHA-256 above. The decoded uboot.boot, isd_config.ini, cfg_tool.bin, cfg, and key-MAC descriptor digests match the receipt; the first four are also compared by the model against the retained pinned 092 unpack reference. The app fits the preserved D7000 tail bound with 13,948 bytes of calculated headroom.

## Limits and handoff

The original source FWSC bytes pinned by the model (ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80) were not present in the retained Hera files inspected. Consequently I could not independently reopen that source package or compare every preserved outer payload and the opaque tail byte-for-byte to it. The output remains tied to the strict source SHA in the package/model implementation and receipt, but this particular byte comparison was not reproduced in this review.

The package and receipt explicitly leave hardware_admitted, hardware_tested, installable, updater_acceptance_verified, and release_admitted false. No device or transport operations were performed. Structural parser success does not establish stock updater acceptance, expanded-layout boot, settings migration, rollback, or musical behavior. The next step is the coordinator-owned stock-path acceptance campaign using this exact private artifact and receipt, preserving no-retry and recovery gates; no repackaging or flag change is justified by this review.

