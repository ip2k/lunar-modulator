/* MIT. Inert RAM-only diagnostic. No MMIO, ROM calls, interrupts or services. */
#include "runtime.h"
extern unsigned char __data_begin[], __data_end[], __data_load[];
extern unsigned char __bss_begin[], __bss_end[], __stack_guard[];
static volatile diag_u32 data_cookie = 0x4c554e41u;
static volatile diag_u32 bss_cookie;
struct diagnostic_state {
    diag_u32 magic, version, status, incoming_r0, iterations;
};
volatile struct diagnostic_state lunar_diagnostic;

void lunar_diag_start(diag_u32 incoming_r0)
{
    unsigned i;
    lunar_diag_memory_init(__data_begin, __data_load,
                           (unsigned)(__data_end - __data_begin), __bss_begin,
                           (unsigned)(__bss_end - __bss_begin));
    lunar_diagnostic.magic = 0x4c444941u; /* LDIA */
    lunar_diagnostic.version = 1;
    lunar_diagnostic.incoming_r0 = incoming_r0; /* Preserve only, never dereference. */
    lunar_diagnostic.status = (data_cookie == 0x4c554e41u && bss_cookie == 0) ? 1u : 2u;
    for (i = 0; i < 16; ++i) __stack_guard[i] = 0xa5;
    for (;;) {
        for (i = 0; i < 16; ++i)
            if (__stack_guard[i] != 0xa5) lunar_diagnostic.status = 3;
        ++lunar_diagnostic.iterations;
    }
}
