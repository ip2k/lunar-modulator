# TLSF instance allocation

Source: https://github.com/mattconte/tlsf
Pinned revision: `deff9ab509341f264addbd3c8ada533678591905`.
BSD-3-Clause notice is retained in the unmodified header and copied to LICENSE.
`tlsf.c` and `tlsf.h` are byte-identical upstream files, pinned by inventory.json.

Lunar needs a bounded shared RAM pool with 16-byte instance alignment and
stable addresses while other instances are selected. TLSF provides aligned
allocation/free without moving live allocations and avoids power-of-two size
rounding for large instances. O1Heap (https://github.com/pavel-kirienko/o1heap)
was also inspected: its deterministic half-fit algorithm rounds fragments to
powers of two, too expensive for Lunar instances around 65 KiB and 71 KiB.
This narrow BSD component is compatible with the GPL native HAL application.

The adapter is main-loop owned; it is not called from the audio interrupt.
The allocator is not thread safe. Code/metadata cost, fragmentation, capacity
refusal and real target linkage still require verification. Import alone does
not mean that the application uses the pool or all engines fit in RAM.

Verification [verified, host/target compile; not hardware]: 16 independent
Hera containers passed 131,072 allocation/replacement attempts with ASan and
UBSan, byte-preservation, alignment, non-overlap, allocator consistency,
capacity refusal and coalescing checks. Isolated pi32v2 retained code is
1,424 bytes; TLSF control metadata is 3,188 bytes inside the supplied pool.
The only unresolved symbol is memcpy, supplied by the native C runtime.
Full application integration, actual fragmentation and device timing remain
unverified. Receipts are private build/native-external-arenas-16-20261012/
instance-pool-{target,verification}.json.
