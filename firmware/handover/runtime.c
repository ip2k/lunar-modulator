/* MIT. RAM-only handover preparation, no SDK/ROM/MMIO or board output. */
#include "runtime.h"
extern unsigned char __data_begin[], __data_end[], __data_load[];
extern unsigned char __bss_begin[], __bss_end[];
extern volatile unsigned char __stack_guard[], __ssp_guard[];
void lunar_handover_capture(volatile diag_u32 *, const volatile diag_u32 *);
static volatile diag_u32 data_cookie = 0x4c554e41u;
static volatile diag_u32 bss_cookie;
struct handover_state {
    diag_u32 magic, version, status, incoming_r0, iterations;
    diag_u32 boot_words[23];
};
volatile struct handover_state lunar_handover;

void lunar_handover_start(diag_u32 incoming_r0)
{
    unsigned i;
    /* This link's bounded low RAM initialization excludes 0x01c7fe08.
     * Compiler preservation of incoming_r0 is checked in target disassembly. */
    lunar_diag_memory_init(__data_begin, __data_load,
                           (unsigned)(__data_end - __data_begin), __bss_begin,
                           (unsigned)(__bss_end - __bss_begin));
    lunar_handover.magic = 0x4c484e44u; /* LHND */
    lunar_handover.version = 1;
    lunar_handover.incoming_r0 = incoming_r0;
    lunar_handover.status = (data_cookie == 0x4c554e41u && bss_cookie == 0) ? 1u : 2u;
    if (incoming_r0 == 0x01c7fe08u)
        lunar_handover_capture(lunar_handover.boot_words,
                              (const volatile diag_u32 *)incoming_r0);
    else
        lunar_handover.status = 4; /* Unexpected entry argument: never dereference. */
    for (i = 0; i < 16; ++i) {
        __stack_guard[i] = 0xa5;
        __ssp_guard[i] = 0x5a;
    }
    for (;;) {
        for (i = 0; i < 16; ++i)
            if (__stack_guard[i] != 0xa5 || __ssp_guard[i] != 0x5a)
                lunar_handover.status = 3;
        ++lunar_handover.iterations;
    }
}
