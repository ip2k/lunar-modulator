# Independent outer FWSC preservation check for the private D7000 diagnostic

This closes the source-availability limitation in the earlier materialized-package review. The retained FM-1_092 source FWSC is now present on Hera, and its raw bytes match the pinned SHA-256 `ed8415f32f5e2ff5558a24cee45eafd8d0a5b1982af14d4cb88ba019b876eb80` (810,548 bytes). The private package bytes are `event-horizon-showcase-d7000-diagnostic.fwsc`, SHA-256 `26402f8766ef523fc729bf16339291fa18c152c7da3e10717e2b8bd46af924d4` (978,484 bytes). Its receipt is mode 0600; package directory is mode 0700. The package's full receipt and structural review are in the existing materialization handoff.

I independently extracted the 20-slot FWSC prefix, decoded the logical header and eight entry rows, sliced each source and output allocation, and recomputed each payload CRC. For encrypted source suffix records I applied the documented legacy FM-1_092 SFC origin (`entry_offset - 0x1B000`); output entries decoded at their relocated logical offsets. This direct comparison does not call the package composer or its nested replacement verifier. The repository's independent `inspect_fwsc.py` reopened the output as identity `FM-1_990`, verified header/list CRCs and all eight payload CRCs, and reported `packaging_ready=false` with remaining gates.

| Outer entry | Check against source | Result |
| --- | --- | --- |
| `flash.bin` | Expected replacement: source 0xAE000 bytes to D7000; output extent/hash differs | expected change |
| `info.log` | zero-byte allocation | equal |
| `USR` | complete decoded allocation and CRC | equal; relocated SFC ciphertext |
| `isd_config.ini` | complete decoded allocation and CRC | equal; relocated SFC ciphertext |
| `ota.bin` | complete allocation, raw bytes and CRC | equal byte-for-byte |
| `script.ver` | complete decoded allocation and CRC | equal; relocated SFC ciphertext |
| `blimit.bin` | complete decoded allocation and CRC | equal; relocated SFC ciphertext |
| `tail.bin` | 64-byte raw allocation, terminal trailer | equal byte-for-byte; SHA-256 `79d4bbc325be8b2f49492a9e8bf712e3cfe4e7c55e874dced1445ed65616843b` |

The seven non-flash entries retain order/type, size, allocation, payload CRC and other entry metadata. Their logical offsets are unchanged only for `flash.bin`; the remaining entries move by exactly 167,936 bytes, from the expanded flash insertion. `tail.bin` is still the last entry and ends at logical EOF in both files. Its payload bytes are identical, as is `ota.bin`. Encrypted suffix ciphertext changes as expected when SFC blocks are relocated; equality here is of every decoded byte in each allocated payload, including padding, not ciphertext identity. Physical prefix identity markers, outer offsets, total length, header and list checksums necessarily change.

Limits: this checks outer payload correspondence and the output parser's integrity result. It is not a stock-updater acceptance test. The expanded `flash.bin` model, version identity `FM-1_990`, proprietary loader treatment of relocated extents, physical D7000 capacity, recovery and runtime remain unproven. The materialization receipt keeps `hardware_admitted`, `hardware_tested`, `installable`, `updater_acceptance_verified`, and `release_admitted` false. No package was transmitted or installed, and no hardware operation was performed.
