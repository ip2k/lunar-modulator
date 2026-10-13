/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "wave_tables.c"
#include "expected.inc"

int main(int argc, char **argv)
{
    assert(argc == 2);
    unsigned shard = (unsigned)strtoul(argv[1], NULL, 10);
    assert(shard < 16);
    for (unsigned repeat = 0; repeat < 3; ++repeat) {
        memset(lunar_waves_plaits, 0xa5, sizeof lunar_waves_plaits);
        memset(lunar_waves_braids, 0xa5, sizeof lunar_waves_braids);
        assert(lunar_wave_tables_init() == 0);
        assert(memcmp(lunar_waves_plaits, expected_2, sizeof expected_2) == 0);
        assert(memcmp(lunar_waves_braids, expected_1, sizeof expected_1) == 0);
    }
    for (unsigned i = 0; i < 2; ++i) {
        lunar_wave_table_t table = lunar_wave_tables[i];
        unsigned length = table.output_bytes;
        unsigned char *guarded = malloc(length + 32);
        assert(guarded);
        table.output = guarded + 16;
        for (unsigned n = shard; n < table.packed_bytes; n += 16) {
            memset(guarded, 0xa5, length + 32);
            table.packed_bytes = n;
            assert(lunar_wave_table_decode(&table) == -1);
            for (unsigned g = 0; g < 16; ++g)
                assert(guarded[g] == 0xa5 && guarded[length + 16 + g] == 0xa5);
            table.packed_bytes = lunar_wave_tables[i].packed_bytes;
        }
        table.fnv32 ^= 1u;
        assert(lunar_wave_table_decode(&table) == -1);
        table.fnv32 ^= 1u;
        table.output_bytes = length - table.width;
        assert(lunar_wave_table_decode(&table) == -1);
        table.output_bytes = length;
        table.width = 3;
        assert(lunar_wave_table_decode(&table) == -1);
        free(guarded);
    }
    return 0;
}
