#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { uint32_t magic, body_bytes; uint16_t crc16, format; } spike_manifest_t;
int lunar_validate_region(const uint8_t *, const uint8_t *, const spike_manifest_t *, uint32_t);

int main(int argc, char **argv) {
    if (argc != 3) return 90;
    FILE *f = fopen(argv[1], "rb");
    if (!f) return 91;
    if (fseek(f, 0, SEEK_END)) return 92;
    long n = ftell(f);
    if (n < (long)sizeof(spike_manifest_t) || fseek(f, 0, SEEK_SET)) return 93;
    uint8_t *b = malloc((size_t)n);
    if (!b) return 94;
    if (fread(b, 1, (size_t)n, f) != (size_t)n) return 95;
    fclose(f);
    uint32_t max = (uint32_t)strtoul(argv[2], 0, 0);
    int rc = lunar_validate_region(b, b + n,
        (const spike_manifest_t *)(b + n - (long)sizeof(spike_manifest_t)), max);
    free(b);
    return rc == 0 ? 0 : rc == -1 ? 1 : 2;
}
