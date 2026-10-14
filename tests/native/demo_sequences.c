/* SPDX-License-Identifier: MIT */
/* Exercise full collected projects through the native sequence staging path. */
#include "project_seq.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static unsigned char *read_file(const char *path, size_t *length) {
    FILE *file = fopen(path, "rb");
    long size;
    unsigned char *bytes;
    if (!file) return NULL;
    if (fseek(file, 0, SEEK_END) || (size = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET)) {
        fclose(file);
        return NULL;
    }
    bytes = (unsigned char *)malloc((size_t)size + 1u);
    if (!bytes) {
        fclose(file);
        return NULL;
    }
    if (fread(bytes, 1, (size_t)size, file) != (size_t)size) {
        fclose(file);
        free(bytes);
        return NULL;
    }
    if (fclose(file)) {
        free(bytes);
        return NULL;
    }
    bytes[size] = 0;
    *length = (size_t)size;
    return bytes;
}

int main(int argc, char **argv) {
    unsigned char *binary, *source_set, *scratch_mem, *reference_mem;
    size_t binary_size, source_set_size, scratch_size;
    fm1_state_names_t names;
    fm1_state_report_t report;
    fm1_host_t host = { .api_version = FM1_ENGINE_API_VERSION,
                        .sample_rate = 44118, .max_frames = 64 };
    fm1_seq_limits_t limits;
    fm1_seq_t *seq, *reference;
    fm1_seq_info_t info;
    fm1_seq_stats_t stats;
    char *exported, *reference_export;
    unsigned has_set = 0, track, slot, scene;
    uint32_t notes = 0, locks = 0, trigs = 0;
    size_t export_size;
    uint32_t expected_bars;
    if (argc != 4) return 2;
    expected_bars = (uint32_t)strtoul(argv[3], NULL, 10);
    binary = read_file(argv[1], &binary_size);
    source_set = read_file(argv[2], &source_set_size);
    if (!binary || !source_set || binary_size > FM1_STATE_BIN_MAX) return 3;

    fm1_state_names_default(&names);
    /* Match fm1_app_init's FM1_APP_SEQ_TRACKS production capacity. */
    fm1_seq_limits_default(&limits, 8);
    scratch_size = fm1_seq_size(&limits);
    scratch_mem = (unsigned char *)calloc(1, scratch_size);
    reference_mem = (unsigned char *)calloc(1, scratch_size);
    if (!scratch_mem || !(seq = fm1_seq_create(scratch_mem, &limits, 44118))) return 4;
    if (!reference_mem || !(reference = fm1_seq_create(reference_mem, &limits, 44118)) ||
        !fm1_seq_import_movy1(reference, (const char *)source_set, source_set_size)) return 4;
    fm1_state_report_init(&report);
    if (!lunar_project_seq_stage(binary, (uint32_t)binary_size, &names, &host,
                                 seq, &has_set, &report) || !has_set ||
        report.code != FM1_STATE_OK) {
        fprintf(stderr, "stage failed: code=%u what=%s\n", report.code, report.what);
        return 5;
    }

    /* Compare the packed/streaming stage with direct import of the source SET
     * text; export is canonical and need not preserve source formatting. */
    export_size = fm1_seq_export_movy1(reference, NULL, 0);
    exported = (char *)malloc(export_size + 1u);
    reference_export = (char *)malloc(export_size + 1u);
    if (!exported || !reference_export) return 6;
    if (fm1_seq_export_movy1(seq, exported, export_size + 1u) != export_size ||
        fm1_seq_export_movy1(reference, reference_export, export_size + 1u) != export_size ||
        memcmp(exported, reference_export, export_size)) {
        fprintf(stderr, "staged export differs from direct source import: bytes=%lu\n",
                (unsigned long)export_size);
        return 7;
    }

    fm1_seq_get_info(seq, &info);
    fm1_seq_get_stats(seq, &stats);
    for (track = 0; track < info.tracks; ++track) {
        for (slot = 0; slot < FM1_SEQ_SCENES; ++slot) {
            fm1_seq_clip_info_t clip;
            if (!fm1_seq_get_clip(seq, (uint8_t)track, (uint8_t)slot, &clip)) return 8;
            notes += clip.notes;
            locks += clip.locks;
            trigs += clip.trigs;
        }
    }
    for (scene = 0; scene < FM1_SEQ_SCENES; ++scene) {
        if (!fm1_seq_scene_name(seq, (uint8_t)scene)[0]) {
            fprintf(stderr, "scene %u has no retained name\n", scene);
            return 9;
        }
    }
    if (fm1_seq_song_bars(seq) != expected_bars || info.song_len == 0 ||
        info.song_entries == 0 || info.tracks == 0 || !notes || !locks ||
        stats.refused || stats.dropped_events || stats.gates_evicted || stats.movy_faults) {
        fprintf(stderr, "semantic metrics mismatch: bars=%lu/%lu song_len=%u entries=%u tracks=%u notes=%lu locks=%lu trigs=%lu refused=%lu dropped=%lu evicted=%lu faults=%lu\n",
                (unsigned long)fm1_seq_song_bars(seq), (unsigned long)expected_bars,
                info.song_len, info.song_entries, info.tracks,
                (unsigned long)notes, (unsigned long)locks, (unsigned long)trigs,
                (unsigned long)stats.refused, (unsigned long)stats.dropped_events,
                (unsigned long)stats.gates_evicted, (unsigned long)stats.movy_faults);
        return 10;
    }
    printf("bars=%lu song_entries=%u scenes=%u tracks=%u notes=%lu locks=%lu trigs=%lu set_bytes=%lu\n",
           (unsigned long)fm1_seq_song_bars(seq), info.song_entries, FM1_SEQ_SCENES,
           info.tracks, (unsigned long)notes, (unsigned long)locks, (unsigned long)trigs,
           (unsigned long)export_size);
    free(exported);
    free(reference_export);
    free(scratch_mem);
    free(reference_mem);
    free(source_set);
    free(binary);
    return 0;
}
