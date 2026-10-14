/* SPDX-License-Identifier: MIT. Synthetic equal-size mutable fixture. */
#include <stdint.h>
__attribute__((section(".text.mutable"), noinline)) int lunar_mutable_entry(void) { return 0x41; }
__attribute__((section(".rodata.mutable"), used)) const uint8_t lunar_mutable_fixture[128] = {
#ifdef SPIKE_VARIANT_B
0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,0x42,
#else
0x13,0x37,0x00,0x7f,0xa5,0x5a,0x11,0x22,0x33,0x44,0x55,0x66,0x77,0x88,0x99,0xaa,
#endif
0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,
32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,
64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,79,80,81,82,83,84,85,86,87,88,89,90,91,92,93,94,95,
96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111};
