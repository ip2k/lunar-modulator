#include "../../firmware/third_party/tlsf/tlsf.c"
#define S(name, expr) __attribute__((used)) const unsigned fm1sz_##name=(unsigned)(expr)
S(size, sizeof(control_t));
S(block, sizeof(block_header_t));
S(overhead, block_header_overhead);
S(min, block_size_min);
S(align, ALIGN_SIZE);
S(pool_overhead, 2*block_header_overhead);
