/* SPDX-License-Identifier: GPL-3.0-only */
#include "fm1_state.h"
#include "project_store.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define MAX_SLOT (LP_MAX + LP_SECTOR)
static uint8_t flash[2u * MAX_SLOT], baseline[2u * MAX_SLOT];
static uint8_t data[LP_MAX], old_data[LP_MAX], new_data[LP_MAX];
static uint32_t data_n, old_data_n, new_data_n, slot_bytes;
static unsigned mutation_count, fail_mutation, validate_count;
static int failure_mode; /* 1: partial mutation, 2: full operation then error */

typedef struct { uint32_t off, n; int failed; } flash_source;

static uint32_t memory_read(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
    flash_source *src = (flash_source *)ctx;
    if (off > src->n || n > src->n - off) return 0;
    memcpy(out, flash + src->off + off, n);
    return n;
}

static uint32_t file_read(void *ctx, uint32_t off, uint8_t *out, uint32_t n) {
    (void)ctx;
    if (off > data_n || n > data_n - off) return 0;
    memcpy(out, data + off, n);
    return n;
}

static int discard_record(void *ctx, const fm1_rec_t *record) {
    (void)ctx; (void)record; return 1;
}

static int read_valid_file(uint32_t off, uint32_t n) {
    flash_source src = {off, n, 0};
    fm1_state_report_t report;
    fm1_state_report_init(&report);
    ++validate_count;
    return fm1_state_bin_read(memory_read, &src, n, discard_record, NULL,
                              &report, 0) ? 0 : 1;
}

static int read_flash(void *ctx, uint32_t off, void *out, uint32_t n) {
    (void)ctx;
    assert(off <= sizeof flash && n <= sizeof flash - off);
    memcpy(out, flash + off, n);
    return 0;
}

static int erase_flash(void *ctx, uint32_t off) {
    (void)ctx;
    assert(!(off % LP_SECTOR) && off <= sizeof flash - LP_SECTOR);
    if (++mutation_count == fail_mutation) {
        /* A failed transport may still have erased a physical prefix. */
        memset(flash + off, 0xff, failure_mode == 2 ? LP_SECTOR : LP_SECTOR / 2u);
        return -1;
    }
    memset(flash + off, 0xff, LP_SECTOR);
    return 0;
}

static int program_flash(void *ctx, uint32_t off, const void *bytes, uint32_t n) {
    const uint8_t *src = (const uint8_t *)bytes;
    uint32_t i, written = n;
    int fail;
    (void)ctx;
    assert(off <= sizeof flash && n <= sizeof flash - off && n <= 256u);
    assert((off & 255u) + n <= 256u);
    fail = ++mutation_count == fail_mutation;
    if (fail) written = failure_mode == 2 ? n : n / 2u;
    for (i = 0; i < written; ++i) {
        assert((flash[off + i] & src[i]) == src[i]);
        flash[off + i] = src[i];
    }
    return fail ? -1 : 0;
}

static int validate(void *ctx, uint32_t off, uint32_t n) {
    (void)ctx;
    assert(off <= sizeof flash && n <= sizeof flash - off);
    return read_valid_file(off, n);
}

static const lunar_project_io io = {NULL, read_flash, erase_flash,
                                    program_flash, validate};

static void store_file(void) {
    lunar_project_store store;
    assert(!lunar_project_begin(&store, &io, slot_bytes));
    assert(!lunar_project_write(&store, 0, data, data_n));
    assert(!lunar_project_commit(&store, data_n));
}

static int update_file(void) {
    lunar_project_store store;
    int rc = lunar_project_begin(&store, &io, slot_bytes);
    if (!rc) rc = lunar_project_write(&store, 0, data, data_n);
    if (!rc) rc = lunar_project_commit(&store, data_n);
    return rc;
}

static void assert_recovery(int expected_slot, uint32_t expected_generation,
                            const uint8_t *expected_data, uint32_t expected_n) {
    lunar_project_store store;
    int slot;
    uint32_t generation, length;
    unsigned decodes = validate_count;
    memset(&store, 0, sizeof store);
    store.io = io;
    store.slot_bytes = slot_bytes;
    assert(!lunar_project_scan(&store, &slot, &generation, &length));
    if (slot != expected_slot || generation != expected_generation || length != expected_n) {
        fprintf(stderr, "recovery mismatch: slot=%d generation=%u length=%u expected_slot=%d expected_generation=%u expected_length=%u\n",
                slot, generation, length, expected_slot, expected_generation, expected_n);
        abort();
    }
    assert(validate_count > decodes); /* scan invokes the real state decoder */
    assert(!memcmp(flash + (uint32_t)slot * slot_bytes + LP_HEADER,
                   expected_data, expected_n));
}

static void exercise_faults(unsigned shard,
                            int old_slot, uint32_t old_generation,
                            const uint8_t *old_payload, uint32_t old_n,
                            int new_slot, uint32_t new_generation,
                            const uint8_t *new_payload, uint32_t new_n) {
    unsigned total_mutations, ordinal;
    mutation_count = 0;
    fail_mutation = 0;
    assert(!update_file());
    total_mutations = mutation_count;
    assert(total_mutations);
    memcpy(flash, baseline, sizeof flash);
    for (ordinal = shard + 1u; ordinal <= total_mutations; ordinal += 30u) {
        unsigned mode;
        for (mode = 1; mode <= 2; ++mode) {
            int expect_new = mode == 2 &&
                ordinal == slot_bytes / LP_SECTOR +
                    (data_n + (LP_HEADER & 255u) + 255u) / 256u + 2u;
            memcpy(flash, baseline, sizeof flash);
            mutation_count = 0;
            fail_mutation = ordinal;
            failure_mode = (int)mode;
            assert(update_file());
            assert(mutation_count == ordinal);
            assert(!memcmp(flash + (uint32_t)old_slot * slot_bytes,
                           baseline + (uint32_t)old_slot * slot_bytes,
                           slot_bytes));
            fail_mutation = 0;
            assert_recovery(expect_new ? new_slot : old_slot,
                            expect_new ? new_generation : old_generation,
                            expect_new ? new_payload : old_payload,
                            expect_new ? new_n : old_n);
        }
    }
    memcpy(flash, baseline, sizeof flash);
}

static void load_fixture(const char *path) {
    FILE *file = fopen(path, "rb");
    assert(file);
    data_n = (uint32_t)fread(data, 1, sizeof data, file);
    assert(!ferror(file) && !fclose(file));
    assert(data_n && data_n <= slot_bytes - LP_HEADER);
    {
        fm1_state_report_t report;
        fm1_state_report_init(&report);
        assert(fm1_state_bin_read(file_read, NULL, data_n, discard_record,
                                  NULL, &report, 0));
    }
}

int main(int argc, char **argv) {
    lunar_project_store store;
    unsigned shard;
    int slot;
    uint32_t generation, length;
    assert(argc == 5);
    slot_bytes = (uint32_t)strtoul(argv[3], NULL, 10);
    shard = (unsigned)strtoul(argv[4], NULL, 10);
    assert(slot_bytes == 102400u || slot_bytes == 49152u);
    assert(shard < 30u);
    load_fixture(argv[1]);
    old_data_n = data_n;
    memcpy(old_data, data, data_n);

    memset(flash, 0xff, sizeof flash);
    mutation_count = 0;
    store_file(); /* Generation 0, slot 0, with the original payload. */
    memset(&store, 0, sizeof store);
    store.io = io;
    store.slot_bytes = slot_bytes;
    assert(!lunar_project_scan(&store, &slot, &generation, &length));
    assert(slot == 0 && generation == 0 && length == old_data_n);
    memcpy(baseline, flash, sizeof flash);

    load_fixture(argv[2]);
    new_data_n = data_n;
    memcpy(new_data, data, data_n);
    if (strcmp(argv[1], argv[2])) assert(memcmp(old_data, new_data, old_data_n));
    exercise_faults(shard, 0, 0u, old_data, old_data_n,
                    1, 1u, new_data, new_data_n);

    /* Establish the distinct generation-1 image before testing 1 -> 2. */
    mutation_count = 0;
    fail_mutation = 0;
    assert(!update_file());
    memset(&store, 0, sizeof store);
    store.io = io;
    store.slot_bytes = slot_bytes;
    assert(!lunar_project_scan(&store, &slot, &generation, &length));
    assert(slot == 1 && generation == 1 && length == new_data_n);
    assert(!memcmp(flash + slot_bytes + LP_HEADER, new_data, new_data_n));
    memcpy(baseline, flash, sizeof flash);

    memcpy(data, old_data, old_data_n);
    data_n = old_data_n;
    exercise_faults(shard, 1, 1u, new_data, new_data_n,
                    0, 2u, old_data, old_data_n);

    if (shard == 0u) {
        /* Store API has no body-length preflight: begin erases inactive first. */
        memcpy(flash, baseline, sizeof flash);
        mutation_count = 0;
        fail_mutation = 0;
        assert(!lunar_project_begin(&store, &io, slot_bytes));
        assert(mutation_count == slot_bytes / LP_SECTOR);
        {
            unsigned before = mutation_count;
            assert(lunar_project_write(&store, 0, data,
                                      slot_bytes - LP_HEADER + 1u));
            assert(mutation_count == before);
        }
        assert_recovery(1, 1u, new_data, new_data_n);

        memset(&store, 0, sizeof store);
        store.io = io;
        store.slot_bytes = slot_bytes;
        mutation_count = 0;
        assert(lunar_project_begin(&store, &io, slot_bytes + 1u));
        assert(!mutation_count); /* malformed geometry is refused before erase */
    }
    return 0;
}
