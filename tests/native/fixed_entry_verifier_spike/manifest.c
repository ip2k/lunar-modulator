/* SPDX-License-Identifier: MIT. Offline placeholder patched after link. */
#include <stdint.h>
typedef struct { uint32_t magic, body_bytes; uint16_t crc16, format; } spike_manifest_t;
__attribute__((section(".mutable.manifest"), used)) const spike_manifest_t spike_manifest = {0x31525646u,0,0,1};
