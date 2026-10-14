/* SPDX-License-Identifier: MIT
 * Offline fixed-entry verifier spike; not production firmware.
 * Uses the existing Dinghy ota_crc16 polynomial/init convention (poly 0x1021,
 * MSB-first, init 0, no final XOR). This isolated copy is not linked in prod.
 */
#include <stdint.h>
typedef struct { uint32_t magic, body_bytes; uint16_t crc16, format; } spike_manifest_t;
#define SPIKE_MAGIC 0x31525646u
#define BODY_LIMIT 0x020D3000u
#define BODY_ORIGIN 0x02001000u
static uint16_t spike_crc16(const uint8_t *p, uint32_t n) __attribute__((section(".text.immutable"), noinline));
static uint16_t spike_crc16(const uint8_t *p, uint32_t n) {
    uint32_t crc = 0, bit;
    while (n--) {
        crc ^= (uint32_t)*p++ << 8;
        for (bit = 0; bit < 8u; ++bit) crc = (crc & 0x8000u) ? ((crc << 1) ^ 0x1021u) : (crc << 1);
        crc &= 0xffffu;
    }
    return (uint16_t)crc;
}
int lunar_validate_region(const uint8_t *begin, const uint8_t *end, const spike_manifest_t *manifest, uint32_t max_body)
    __attribute__((section(".text.immutable"), noinline));
int lunar_validate_region(const uint8_t *begin, const uint8_t *end, const spike_manifest_t *manifest, uint32_t max_body) {
    const uint32_t extent = (uint32_t)((uintptr_t)end - (uintptr_t)begin);
    const uint32_t manifest_bytes = (uint32_t)sizeof(spike_manifest_t);
    if ((uintptr_t)end < (uintptr_t)begin || extent < manifest_bytes || extent > max_body ||
        manifest->magic != SPIKE_MAGIC || manifest->format != 1u || manifest->body_bytes != extent - manifest_bytes) return -1;
    return spike_crc16(begin, manifest->body_bytes) == manifest->crc16 ? 0 : -2;
}
#ifndef SPIKE_HOST_TEST
extern const uint8_t __mutable_start[], __mutable_end[];
extern const spike_manifest_t __mutable_manifest[];
int lunar_validate_mutable(void) __attribute__((section(".text.immutable"), noinline));
int lunar_validate_mutable(void) {
    if ((uintptr_t)__mutable_start != BODY_ORIGIN || (uintptr_t)__mutable_end > BODY_LIMIT) return -1;
    return lunar_validate_region(__mutable_start, __mutable_end, __mutable_manifest, BODY_LIMIT - BODY_ORIGIN);
}
#endif
