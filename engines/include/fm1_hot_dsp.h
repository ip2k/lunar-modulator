/* fm1_hot_dsp.h -- private opt-in placement attribute for native DSP bodies.
 *
 * This deliberately has no dependency on the engine API so a vendored class
 * declaration can use the placement switch without importing FM1 interfaces.
 */
#ifndef FM1_HOT_DSP_H_
#define FM1_HOT_DSP_H_

#if defined(FM1_HOT_DSP_RAM) && FM1_HOT_DSP_RAM
#define FM1_HOT_DSP_RENDER __attribute__((noinline, used, section(".ram_dsp")))
#else
#define FM1_HOT_DSP_RENDER
#endif

#endif /* FM1_HOT_DSP_H_ */
