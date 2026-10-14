# Installed all13 footprint experiment

[verified] Read-only Hera measurement of installed-candidate application SHA
`eff6f5b2821a229f7a0255a873031c52d5f8242e4312f07e3f54fb4c951f5960`;
linked ELF SHA `35655a21de5c08d09fa19ef2fd4f253efbc107346c6e107a1988dca4e69dac29`
was separately checked on Hera. No hardware command or firmware change occurred.
`receipt.json` pins application, symbol-table and section-report hashes.
`measure.py` rejects a different application and checks every measured symbol
lies within its bytes. Every whole-symbol zlib experiment decompresses exactly.

[verified] Application is 845,916 bytes, from physical 0x4120 to exclusive
0xD297C. Section report: .text 0xCE3B0, .ram_text 0x468, .data 0x44;
allocation .pool ends at 0x01C736C0, leaving 2,368 bytes before guard0.
This is linked allocation headroom, not measured stack usage or free heap.

[verified] Largest constant symbols include Plaits integrated waves (50,688
bytes), ride (46,999), crash (43,300), packed Braids (24,159), and hat (20,250).
Drum generator/source inspection confirms the sample data already uses 8-bit
mu-law and a decode table. Plaits source uses direct waveform pointers.

[verified] Top thirty constant symbols together save 40,329 bytes with separate
whole-symbol zlib streams. Separate 256-byte zlib blocks plus a four-byte offset
table entry per block and terminal entry save only 2,884 bytes in aggregate.
The three cymbal samples compress poorly in small blocks; packed Braids expands.
Decoder executable cost, decompression latency and runtime working memory are
not included. No decoder was implemented or selected. Whole-stream results are
an offline comparison, not a deployable random-access storage design.

[inferred] General lossless compression is not presently a justified shortcut
to two maximum-capacity project slots: full-table expansion conflicts with tight
linked RAM allocation, while tested small-block savings are inadequate.
Next investigate project allocation/transaction alternatives and other flash
contributors before changing DSP data, capacities or protected banks.

[verified] Geometry-only upper bound, not write authorization: aligned unused
application tail 0xD3000..0xD9000 is 24 KiB. Existing VM is 64 KiB, USR 72 KiB,
and gap 12 KiB. Even if VM/USR were eventually migrated and repurposed, keeping
BTIF/device keys and an 8 KiB settings journal yields 164 KiB total, versus
200 KiB for two 100 KiB project slots. Those areas are not contiguous and the
current two-slot core has no scatter mapping. VM/USR remain protected, and the
application tail has not been admitted as an owned storage window. No allocation,
migration or device write is approved by this arithmetic.

Semantic MCP status was refreshed: both select the primary checkout rather than
this worktree; neither was used as linked-artifact evidence or switched globally.
Binary layout evidence comes from retained target linker/objdump outputs.
