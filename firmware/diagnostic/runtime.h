/* MIT. Freestanding types: the target compiler must provide 32-bit unsigned. */
#ifndef LUNAR_DIAGNOSTIC_RUNTIME_H
#define LUNAR_DIAGNOSTIC_RUNTIME_H
typedef unsigned int diag_u32;
typedef char diag_u32_is_32_bits[(sizeof(diag_u32) == 4) ? 1 : -1];
void lunar_diag_memory_init(volatile unsigned char *data, const unsigned char *load,
                            unsigned data_bytes, volatile unsigned char *bss,
                            unsigned bss_bytes);
#endif
