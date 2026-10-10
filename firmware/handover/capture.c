/* MIT. Capture only the six stock SPL words; do not read its trailing header. */
#include "runtime.h"
void lunar_handover_capture(volatile diag_u32 *destination,
                            const volatile diag_u32 *source)
{
    unsigned i;
    for (i = 0; i < 23; ++i) destination[i] = 0;
    for (i = 0; i < 6; ++i) destination[i] = source[i];
}
