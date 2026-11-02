# CPU1 candidate platform provenance

Source: [felucca-bsp](https://github.com/hugelton/felucca-bsp), pinned
`d6b8f771795be04d77e15d72a79f474a723796d7`.
The guarded launch/hold algorithms and secondary assembly entry are adapted from
`chip/fm1_cpu1.h`, `chip/fm1_cpu1_stop.h`, `chip/fm1_cpu1.S`, with guard/register
facts from `chip/fm1_guard.h` and core-aware fault handling from `chip/fm1_irq.h`.
These files carry MPL-2.0, including contributions by Kerem Kilic (Ellic Studio),
Charles Vestal, Leo Kuroshita (@kurogedelic), Hügelton Instruments. Their
[public permission record](https://github.com/hugelton/felucca-bsp/issues/5)
and upstream NOTICE describe the additional MPL grant for earlier GPL code.
Keep this attribution and the included MPL license with derivatives. No
proprietary SDK implementation is copied.

Lunar adaptations live in `firmware/native/cpu1_candidate*`: bounded injectable
MMIO operations, saved-state cleanup, explicit linker storage, shared-origin
clock extension, permanent fault records and integration with the real native
adapter/common core. The MPL platform layer stays separate from the MIT common
core. This is an offline, unadmitted stock-SPL candidate, not a supported BSP.

Independent cross-check: [pi32v2-isa CPU1 guide](https://github.com/jvitkauskas/pi32v2-isa/blob/e57532149664a53a4184891f0cd5b65bb703cf07/docs/CPU1.md)
and MIT-0 `tools/hwtest/app/{dual-platform,peer}.S` at that exact commit.
Those experiments ran on another FM-1/bootloader and do not prove our inherited
RTI/cache/rails state or shared-memory reliability. No power/cache policy is
imported here, and no native execution or redistribution admission is implied.
