/* SPDX-License-Identifier: GPL-3.0-only
 * Fake-NOR transaction tests for the isolated Felucca derivative.
 * No USB, target HAL, SPL record, or physical flash is used. */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#define LUNAR_EXPANDED_OFFLINE_TEST 1
#define APP_LO 0x4000u
#ifndef APP_HI
#define APP_HI 0xD9000u
#endif
#define FLASH_BYTES 0x100000u
#define OTA_DATA_OFF 0x400u
static uint8_t nor[FLASH_BYTES], logical[FLASH_BYTES + OTA_DATA_OFF], hdr[0x400];
static uint32_t erase_order[512], erases, bad_range, fail_erase, fail_prog, programs;
static int flip_readback; static uint32_t flip_readback_off, flip_readback_count;
static int corrupt_package, enable_mutation, mutate_after_check, mutated_chunk;

static uint16_t ota_crc16(const uint8_t *p, uint32_t n, uint32_t c)
{
    uint32_t i;
    while (n--) { c ^= (uint32_t)*p++ << 8; for (i = 0; i < 8; i++) c = (c & 0x8000u) ? ((c << 1) ^ 0x1021u) : (c << 1); c &= 0xFFFFu; }
    return (uint16_t)c;
}
static uint16_t ota_rd16(const uint8_t *p) { return (uint16_t)(p[0] | ((uint16_t)p[1] << 8)); }
static void ota_wr16(uint8_t *p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
static int ota_memeq(const void *a, const void *b, uint32_t n) { return memcmp(a, b, n) == 0; }
static int ota_read(uint32_t off, void *p, uint32_t n)
{
    if (off == 0xF0000000u) { memset(p, 0, n); return 0; }
    if (off > FLASH_BYTES + OTA_DATA_OFF || n > FLASH_BYTES + OTA_DATA_OFF - off) return -1;
    memcpy(p, logical + off, n);
    if (mutate_after_check && off == OTA_DATA_OFF + 0x5000u && n == 512u) {
        ((uint8_t *)p)[17] ^= 0x01u; mutated_chunk = 1;
    }
    if (enable_mutation && off == OTA_DATA_OFF + FLASH_BYTES - 512u && n == 512u) mutate_after_check = 1;
    if (corrupt_package && off == OTA_DATA_OFF + 0x5000u && n == 512u) ((uint8_t *)p)[0] ^= 0x80u;
    return 0;
}
static int ota_ufw(uint8_t *out, uint32_t *off, uint32_t *size, uint32_t *ota_off, uint32_t *ota_len)
{
    memcpy(out, hdr, sizeof hdr); *off = OTA_DATA_OFF; *size = FLASH_BYTES; *ota_off = 0; *ota_len = 0; return 0;
}
static int ldr_fread(uint32_t off, void *p, uint32_t n)
{
    if (off > FLASH_BYTES || n > FLASH_BYTES - off) return -1;
    memcpy(p, nor + off, n);
    if (flip_readback && off == flip_readback_off && n == 0x1000u && ++flip_readback_count == 2u) { ((uint8_t *)p)[0] ^= 1; flip_readback = 0; }
    return 0;
}
static int ldr_erase(uint32_t off)
{
    if (off < APP_LO || off + 0x1000u > APP_HI || (off & 0xFFFu)) { bad_range++; return -1; }
    if (erases < sizeof erase_order / sizeof erase_order[0]) erase_order[erases] = off;
    erases++;
    memset(nor + off, 0xFF, 0x1000u);
    if (fail_erase == off) { fail_erase = 0; return -1; }
    return 0;
}
static int ldr_prog(uint32_t off, const void *p, uint32_t n)
{
    const uint8_t *src = p; uint32_t i;
    if (off < APP_LO || off + n > APP_HI || ((off & 0xFFu) + n > 256u)) { bad_range++; return -1; }
    for (i = 0; i < n; i++) nor[off + i] &= src[i];
    programs++;
    if (fail_prog && programs == fail_prog) { fail_prog = 0; return -1; }
    return 0;
}
static void ldr_progress(uint32_t done, uint32_t total) { (void)done; (void)total; }
#include "ldr_core.c"

static void setup(void)
{
    uint32_t i;
    memset(nor, 0x5A, sizeof nor); memcpy(logical + OTA_DATA_OFF, nor, sizeof nor);
    memset(logical + OTA_DATA_OFF + APP_LO, 0xA6, APP_HI - APP_LO);
    /* Valid app-head checksum for the fixture's zero test key. */
    ota_wr16(logical + OTA_DATA_OFF + APP_LO, ota_crc16(logical + OTA_DATA_OFF + APP_LO + 2, 30, 0));
    /* Start with the same valid old directory in NOR; failed body writes must
       not silently invalidate it in this portable-core model. */
    memcpy(nor + APP_LO, logical + OTA_DATA_OFF + APP_LO, 32);
    memcpy(hdr, (uint8_t[0x400]){0}, sizeof hdr);
    hdr[8] = 1; /* one UFW entry */
    ota_wr16(hdr + 0x40, 0); /* flash.bin type */
    ota_wr16(hdr + 0x44, ota_crc16(logical + OTA_DATA_OFF, FLASH_BYTES, 0));
    erases = programs = bad_range = 0; fail_erase = fail_prog = 0; flip_readback = 0; flip_readback_off = 0x5000; flip_readback_count = 0; corrupt_package = enable_mutation = mutate_after_check = mutated_chunk = 0;
    for (i = 0; i < sizeof erase_order / sizeof erase_order[0]; i++) erase_order[i] = 0xFFFFFFFFu;
}
static int require(const char *name, int ok) { printf("%-44s %s\n", name, ok ? "ok" : "FAIL"); return ok ? 0 : 1; }
int main(void)
{
    int bad = 0, rc; uint8_t protected_prefix[APP_LO], protected_suffix[FLASH_BYTES - APP_HI];
    setup(); memcpy(protected_prefix, nor, APP_LO); memcpy(protected_suffix, nor + APP_HI, sizeof protected_suffix);
    rc = ldr_session();
    bad += require("expanded transaction completes after verified sector writes", rc == 0 && !memcmp(nor + APP_LO, logical + OTA_DATA_OFF + APP_LO, APP_HI - APP_LO));
    bad += require("directory sector 0x4000 is erased last", erases && erase_order[erases - 1] == APP_LO);
    bad += require("protected prefix and suffix unchanged", !memcmp(nor, protected_prefix, APP_LO) && !memcmp(nor + APP_HI, protected_suffix, sizeof protected_suffix));
    bad += require("no fake write escaped exact profile", bad_range == 0);
    setup();
    { uint8_t byte; bad += require("last in-range byte is readable", ldr_fread(FLASH_BYTES - 1u, &byte, 1u) == 0); bad += require("read starting at flash end is rejected", ldr_fread(FLASH_BYTES, &byte, 1u) != 0); bad += require("read crossing flash end is rejected", ldr_fread(FLASH_BYTES - 1u, &byte, 2u) != 0); }
    setup(); corrupt_package = 1; rc = ldr_session();
    bad += require("corrupt package is rejected before any erase", rc == -12 && erases == 0);
    setup(); enable_mutation = 1; rc = ldr_session();
    bad += require("changed host chunk is refused before erase", rc == -13 && mutated_chunk && erases == 0);
    setup(); fail_erase = 0x5000; rc = ldr_session();
    bad += require("erase cut leaves old directory valid while body is partial", rc == -9 && ota_rd16(nor + APP_LO) == ota_crc16(nor + APP_LO + 2, 30, 0) && nor[0x5000] == 0xFF);
    rc = ldr_session();
    bad += require("host retry after erase cut completes", rc == 0 && !memcmp(nor + APP_LO, logical + OTA_DATA_OFF + APP_LO, APP_HI - APP_LO));
    setup(); fail_prog = 1; rc = ldr_session();
    bad += require("partial page-program cut leaves old directory valid", rc == -10 && ota_rd16(nor + APP_LO) == ota_crc16(nor + APP_LO + 2, 30, 0) && nor[0x5100] == 0xFF && nor[0x5100] != logical[OTA_DATA_OFF + 0x5100]);
    rc = ldr_session();
    bad += require("host retry after program cut completes", rc == 0 && !memcmp(nor + APP_LO, logical + OTA_DATA_OFF + APP_LO, APP_HI - APP_LO));
    setup(); flip_readback = 1; rc = ldr_session();
    bad += require("readback mismatch causes sector rewrite and retry", rc == 0 && !memcmp(nor + APP_LO, logical + OTA_DATA_OFF + APP_LO, APP_HI - APP_LO));
    bad += require("readback retry touches only the mismatched sector", erases == (APP_HI - APP_LO) / 0x1000u + 1u);
    setup(); flip_readback = 1; flip_readback_off = APP_LO; rc = ldr_session();
    bad += require("directory last readback mismatch is retried", rc == 0 && !memcmp(nor + APP_LO, logical + OTA_DATA_OFF + APP_LO, APP_HI - APP_LO));
    bad += require("directory retry remains the final sector write", erases && erase_order[erases - 1] == APP_LO);
#if APP_HI == 0xD7000u
    setup();
    bad += require("D6FFF app boundary sector is writable", ldr_erase(0xD6000u) == 0);
    bad += require("D7000 stage boundary is outside app writes", ldr_erase(0xD7000u) != 0 && ldr_prog(0xD7000u, nor, 1) != 0);
    bad += require("two-sector stage ends at VM start", 0xD7000u + 0x2000u == 0xD9000u);
    bad += require("6954-byte loader fits before D8F00 record arithmetically", 0xD7000u + 6954u <= 0xD8F00u && 0xD8F00u + 80u <= 0xD9000u);
    setup();
    { uint8_t suffix[FLASH_BYTES - APP_HI]; memcpy(suffix, nor + APP_HI, sizeof suffix); rc = ldr_session();
      bad += require("D7000 profile transaction preserves stage and later banks", rc == 0 && !memcmp(nor + APP_HI, suffix, sizeof suffix)); }
#endif
    printf("%s\n", bad ? "OFFLINE CORE TEST FAILED" : "offline core test passed"); return bad != 0;
}
