/* MIT. Volatile writes prevent lowering these loops to a libc memop. */
#include "runtime.h"
void lunar_diag_memory_init(volatile unsigned char *data, const unsigned char *load,
                            unsigned data_bytes, volatile unsigned char *bss,
                            unsigned bss_bytes)
{
    unsigned i;
    for (i = 0; i < data_bytes; ++i) data[i] = load[i];
    for (i = 0; i < bss_bytes; ++i) bss[i] = 0;
}
