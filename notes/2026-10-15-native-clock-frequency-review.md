# Clock configuration is not an effective CPU-frequency measurement

[verified: owner] The latest physical cold boot still produced a very laggy
waveform and badly distorted notes. The failure persists across a power cycle;
the real-time requirement has not passed.

[verified] A read-only review of the retained pinned SDK V1.2.13
`clk_early_init()` IR found a case-6 cached-clock calculation. The existing
snapshot has `CLK_CON0=0x1c1`, `CLK_CON2=6`, `SYS_DIV=0x10200`, and PLL words
`0x45400203`, `0x0940022b`, `0x0750310c`. Applying that IR's unsigned operations
selects 24 MHz oscillator input, divisor 12 and multiplier 270, then applies
the case-6 factor 2/3: a **cached** system value of 360 MHz, HSB 180 MHz and
LSB 60 MHz. This conflicts with the nominal 240 MHz project note. It is not a
measurement of PLL lock or of the clock reaching the CPU.

[verified] Native audio initialization clears `CLK_CON2` bits 11:8 while
preserving low nibble 6. The inspected native startup does not configure the
main PLL or `CLK_CON0`. The retained stock SPL branch map contains known
frequency-selector values 0, 2 and 3; it does not resolve selector 6's origin.
An opaque external RAM-loader initializer remains an evidence gap. Equal
cold-boot and loader-started snapshots establish equality of sampled words,
not their provenance or the effective CPU frequency.

[inferred] A clock-tree problem remains a possible contributor to throughput
failure, but these facts do not justify clock reprogramming or an overclock.
No clock writes were made. A documented cycle counter or clock output,
independently measured against a known timebase, would provide stronger
evidence. No usable route was located in this bounded local-source review.
A busy-loop benchmark alone cannot assign MHz without instruction and
memory-timing evidence. TIMER4 is documented by the HAL as a 24 MHz oscillator
timebase; this does not establish CPU MHz either.

## Evidence and next dependency

[verified] The detailed private review is
`scratch/native-clock-frequency-review.md`, SHA256
`a747869145ddeb5603f279ba307084f90e43049f299f17736b7b75621e268de6`.
It records pinned IR SHA256
`a9c6369caab3fed7bcc1150a6fa689beca88cefb6d7f20d8749a7fce70814288`
and the source/branch-map paths. Its scope was retained local source and
recorded snapshots; no fresh device register measurement was performed.

[verified] The next performance target remains exact `c0f138a0`, whose
16-shard target build and link passed. Root reran the five complete export
checks successfully. Its performance and hardware acceptance remain unproven.
The FM1 was passively observed as ROM device101 after automatic recovery;
the consumed ROM99 campaign must never be launched again. A separate bounded
limiter RAM-helper trial is being developed without changing its arithmetic.
