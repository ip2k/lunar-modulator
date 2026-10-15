"""The UI may cache only the all-track mute scan, not focused track state."""
import subprocess

from tests.engine_helpers import ROOT


def test_mute_mask_cache_matches_full_scan_across_mutations(tmp_path):
    harness = tmp_path / "mute_mask_cache.c"
    harness.write_text(r'''#include "fm1_seq.h"
#include "fm1_seq_ui.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

unsigned fm1_seq_ui_test_mute_mask_scans;

static fm1_seq_t *make_seq(unsigned tracks, void **memory) {
    fm1_seq_limits_t limits;
    fm1_seq_limits_default(&limits, (uint8_t)tracks);
    *memory = calloc(1, fm1_seq_size(&limits));
    if (!*memory) return NULL;
    return fm1_seq_create(*memory, &limits, 44118);
}

static int refuse(void *ctx, const fm1_seq_cmd_t *cmd) {
    (void)ctx; (void)cmd;
    return 0;
}

static void sync_and_print(fm1_seq_ui_t *ui, fm1_seq_t *seq, uint32_t gen) {
    (void)fm1_seq_ui_sync(ui, seq, gen, 64u * gen);
    printf("%u:%04x\n", ui->tracks, ui->muted);
}

int main(void) {
    static const char imported[] =
        "movy1\nbpm 12000\nswing 50\nlink 0\n"
        "tk 0 0 1\ntk 1 0 0\ntk 2 0 1\ntk 3 0 0\n"
        "tk 4 0 0\ntk 5 0 0\ntk 6 0 0\ntk 7 0 0\n";
    fm1_seq_ui_t ui;
    fm1_seq_ui_emit_t emit = { NULL, refuse };
    fm1_seq_cmd_t cmd;
    fm1_seq_t *seq, *replacement;
    void *seq_mem = NULL, *replacement_mem = NULL;
    uint32_t gen = 0;

    seq = make_seq(8, &seq_mem);
    if (!seq) return 2;
    fm1_seq_ui_init(&ui, 44118.0f);
    fm1_seq_ui_enter(&ui);
    sync_and_print(&ui, seq, gen);       /* first observation */
    sync_and_print(&ui, seq, gen);       /* stable mask is cached */

    if (!fm1_seq_parse("mute 2 1", 8, &cmd)) return 3;
    (void)fm1_seq_apply(seq, &cmd, NULL, 0);
    ++gen;                               /* normal app command generation */
    sync_and_print(&ui, seq, gen);
    sync_and_print(&ui, seq, gen);

    if (!fm1_seq_import_movy1(seq, imported, sizeof imported - 1u)) return 4;
    ++gen;                               /* app import uses seq_drop */
    sync_and_print(&ui, seq, gen);

    fm1_seq_ev_t events[512];
    (void)fm1_seq_midi_transport_in(seq, 0xFAu, events, 512);
    ++gen;                               /* conservative transport invalidation */
    sync_and_print(&ui, seq, gen);

    replacement = make_seq(3, &replacement_mem);
    if (!replacement) return 6;
    if (!fm1_seq_import_movy1(replacement,
            "movy1\nbpm 12000\nswing 50\nlink 0\ntk 0 0 0\ntk 1 0 1\ntk 2 0 0\n",
            strlen("movy1\nbpm 12000\nswing 50\nlink 0\ntk 0 0 0\ntk 1 0 1\ntk 2 0 0\n"))) return 7;
    /* A replaced instance must invalidate even if the caller reuses gen. */
    sync_and_print(&ui, replacement, gen);

    /* The UI updates optimistically even when its emitter refuses.  A same-gen
       sync must recover the mask from the core rather than cache the guess. */
    fm1_seq_ui_key(&ui, replacement, FM1_SEQ_UI_KEY_MUTE, 1, 100, 0,
                   FM1_MODE_SEQ, 0, &emit);
    fm1_seq_ui_key(&ui, replacement, FM1_SEQ_UI_KEY_MUTE, 0, 0, 1,
                   FM1_MODE_SEQ, 0, &emit);
    sync_and_print(&ui, replacement, gen);
    fprintf(stderr, "scans=%u\n", fm1_seq_ui_test_mute_mask_scans);
    free(replacement_mem);
    free(seq_mem);
    return 0;
}
''')
    seq_sources = sorted((ROOT / "engines" / "seq").glob("*.c"))
    common = [
        "cc", "-std=c99", "-O2", "-Wall", "-Wextra",
        "-DFM1_SEQ_UI_TEST_MUTE_MASK_SCAN_COUNT",
        f"-I{ROOT / 'engines' / 'include'}",
        f"-I{ROOT / 'engines' / 'seq'}",
        f"-I{ROOT / 'engines' / 'host'}",
        f"-I{ROOT / 'sim' / 'web' / 'src'}",
        str(ROOT / "sim" / "web" / "src" / "fm1_seq_ui.c"),
        *(str(path) for path in seq_sources), str(harness), "-lm",
    ]
    outputs = []
    scans = []
    for uncached in (False, True):
        command = common.copy()
        if uncached:
            command.insert(1, "-DFM1_SEQ_UI_DISABLE_MUTE_MASK_CACHE")
        exe = tmp_path / ("full-scan" if uncached else "cached")
        command += ["-o", str(exe)]
        subprocess.run(command, check=True, capture_output=True, text=True)
        result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
        outputs.append(result.stdout)
        scans.append(int(result.stderr.strip().split("=", 1)[1]))

    assert outputs[0] == outputs[1]
    assert scans == [6, 8]
    assert outputs[0].splitlines() == [
        "8:0000", "8:0000", "8:0004", "8:0004", "8:0005", "8:0005",
        "3:0002", "3:0002",
    ]
