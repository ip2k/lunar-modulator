# Materialized D7000 diagnostic FWSC review

Status: reviewed offline; structural checks pass. This is not updater or device acceptance.

## Artifact and tuple binding

Reviewed  (978,484 bytes, mode 0600, parent directory mode 0700), SHA-256 . Its receipt is mode 0600, 1,716 bytes, SHA-256 ; the package path, size and digest in the receipt match the file.

The private build tuple at  hashes to the receipt's externally pinned digest . It names  / , , app identity , recovery identity , and keeps , , and  false. Its app ( bytes, SHA-256 ), ELF ( bytes, SHA-256 ), artifact receipt, build receipt, and provenance hashes each match the retained build outputs and tuple fields.

## Reopen and decoded comparisons

 reopened the emitted package as . Header CRC, entry-list CRC, and all eight outer payload CRCs passed. Entry order/types were flash.bin, info.log, USR, isd_config.ini, ota.bin, script.ver, blimit.bin, and tail.bin; the flash allocation is 880,640 bytes (). The stock OTA payload bytes match the retained stock  reference (19,969 bytes; SHA-256 ).

I also decoded the package flash through the strict  profile after normalizing only the outer package identity for that FM-1_092 decoder. Its nested record/app-area checks passed. The decoded app is exactly 845,732 bytes and has the tuple/receipt SHA-256 above. The decoded , , , , and key-MAC descriptor digests match the receipt; the first four are also compared by the model against the retained pinned 092 unpack reference. The app fits the preserved D7000 tail bound with 13,948 bytes of calculated headroom.

## Limits and handoff

The original source FWSC bytes pinned by the model () were not present in the retained Hera files I inspected. Consequently I could not independently re-open that source package or compare every preserved outer payload and the opaque tail byte-for-byte to it. The output remains tied to the strict source SHA in the package/model implementation and the receipt, but this particular byte comparison was not reproduced in this review.

The package and receipt explicitly leave , , , , and  false. No device or transport operations were performed. Structural parser success does not establish stock updater acceptance, expanded-layout boot, settings migration, rollback, or musical behavior. The next step is the coordinator-owned stock-path acceptance campaign using this exact private artifact and its receipt, preserving the no-retry and recovery gates; no repackaging or flag change is justified by this review.
