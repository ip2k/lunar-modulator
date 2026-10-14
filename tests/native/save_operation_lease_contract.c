/* SPDX-License-Identifier: GPL-3.0-only */
/* Host composition test for the real SAVE service. The tiny state writer and
 * NOR callbacks below are fakes; they prove callback ordering only. */
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "project_save_service.h"

struct fm1_state_writer {
    fm1_state_write_at_t write_at;
    void *ctx;
};
static struct fm1_state_writer *active_writer;
static unsigned save_messages, draw_calls, pause_calls, resume_calls;
static unsigned io_reads, io_erases, io_programs;
static int last_saved_ok;
static const char *last_saved_why;
static uint8_t flash[2 * 4096];
static int fail_erase, fail_program, unresolved_erase, pause_result = 1;
static int transport_ready = 1, xip_restored = 1;
static jmp_buf unresolved;

size_t fm1_state_bin_writer_size(void) { return sizeof(struct fm1_state_writer); }
fm1_state_writer_t *fm1_state_bin_stream_writer(void *mem, unsigned writer,
        const uint8_t version[3], fm1_state_write_at_t write_at, void *ctx,
        uint32_t capacity, fm1_state_report_t *rep) {
    (void)writer; (void)version; (void)capacity; (void)rep;
    active_writer = mem;
    active_writer->write_at = write_at;
    active_writer->ctx = ctx;
    return (fm1_state_writer_t *)active_writer;
}
int fm1_state_bin_write(void *opaque, const fm1_rec_t *record) {
    struct fm1_state_writer *w = opaque;
    uint8_t header[32] = {0}, payload = 0x5a;
    (void)record;
    /* project_save_write reads the payload length at header offset 20. */
    header[20] = 1;
    return w->write_at(w->ctx, sizeof header, &payload, 1) == 0 &&
           w->write_at(w->ctx, 0, header, sizeof header) == 0;
}
void fm1_state_report_init(fm1_state_report_t *rep) { memset(rep, 0, sizeof *rep); }
int fm1_app_state_collect_project(const fm1_app_t *app, int include_view,
        fm1_rec_sink_t sink, void *ctx, fm1_state_report_t *rep) {
    fm1_rec_t record = {0};
    (void)app; (void)include_view; (void)rep;
    record.type = FM1_REC_HEAD;
    return sink(ctx, &record);
}
int fm1_app_draw(fm1_app_t *app, uint32_t min_frames) {
    (void)app; (void)min_frames; draw_calls++; return 1;
}
void fm1_app_saved(fm1_app_t *app, int ok, const char *why) {
    (void)app; save_messages++; last_saved_ok = ok; last_saved_why = why;
}
static int pause_audio_and_display(void *ctx) {
    (void)ctx; pause_calls++; return pause_result;
}
static void resume_audio_and_display(void *ctx) { (void)ctx; resume_calls++; }
static int read_flash(void *ctx, uint32_t off, void *dst, uint32_t n) {
    (void)ctx; assert(off <= sizeof flash && n <= sizeof flash - off);
    io_reads++; memcpy(dst, flash + off, n); return 0;
}
static int erase_flash(void *ctx, uint32_t off) {
    (void)ctx; assert(!(off % 4096) && off <= sizeof flash - 4096); io_erases++;
    if (unresolved_erase) {
        /* Models a transport that cannot establish ready or XIP restoration.
         * longjmp only returns control to the host test, not the firmware API. */
        transport_ready = 0; xip_restored = 0; longjmp(unresolved, 1);
    }
    if (fail_erase) return -1;
    memset(flash + off, 0xff, 4096); transport_ready = 1; xip_restored = 1;
    return 0;
}
static int program_flash(void *ctx, uint32_t off, const void *src, uint32_t n) {
    const uint8_t *p = src; (void)ctx;
    assert(off <= sizeof flash && n <= sizeof flash - off && n <= 256);
    io_programs++;
    if (fail_program) return -1;
    for (uint32_t i = 0; i < n; ++i) {
        assert((flash[off + i] & p[i]) == p[i]); flash[off + i] &= p[i];
    }
    return 0;
}
static int validate_file(void *ctx, uint32_t off, uint32_t n) {
    (void)ctx; (void)off; (void)n; return 0;
}
static void reset_counts(void) {
    save_messages = draw_calls = pause_calls = resume_calls = 0;
    io_reads = io_erases = io_programs = 0;
    last_saved_ok = -1; last_saved_why = NULL;
}
static lunar_project_save_service service(void) {
    lunar_project_save_service s = {0};
    s.io.read = read_flash; s.io.erase = erase_flash;
    s.io.program = program_flash; s.io.validate = validate_file;
    s.slot_bytes = 4096; s.storage_admitted = 1;
    s.pause = pause_audio_and_display; s.resume = resume_audio_and_display;
    return s;
}
int main(void) {
    static fm1_app_t app;
    static lunar_project_save_service s;

    /* Without a verified capability binding, SAVE is refused before pause or
     * transport callbacks and the generation is consumed once. */
    reset_counts(); s = service(); s.storage_admitted = 0; app.save_gen = 1;
    assert(lunar_project_save_service_poll(&s, &app) == 2);
    assert(s.seen_gen == 1 && save_messages == 1 && !last_saved_ok);
    assert(!pause_calls && !resume_calls && !io_reads && !io_erases && !io_programs);
    assert(!lunar_project_save_service_poll(&s, &app));
    assert(save_messages == 1);

    /* A temporary quiesce deferral is not a handled save; it does not reach
     * storage, consume the generation, or resume a lease it never acquired. */
    reset_counts(); s = service(); app.save_gen = 2; pause_result = 0;
    assert(lunar_project_save_service_poll(&s, &app) == 1);
    assert(s.seen_gen == 0 && !save_messages && pause_calls == 1 && !resume_calls);
    assert(!io_reads && !io_erases && !io_programs);
    pause_result = 1;

    /* Once pause succeeds, a failed erase returns through the real service,
     * which reports failure, redraws, resumes exactly once, and never retries
     * that generation on a later poll. */
    reset_counts(); s = service(); app.save_gen = 3; fail_erase = 1;
    memset(flash, 0xff, sizeof flash);
    assert(lunar_project_save_service_poll(&s, &app) == 2);
    fail_erase = 0;
    assert(s.seen_gen == 3 && save_messages == 1 && !last_saved_ok);
    assert(pause_calls == 1 && resume_calls == 1 && draw_calls == 1);
    assert(io_erases == 1 && !io_programs);
    assert(!lunar_project_save_service_poll(&s, &app));
    assert(io_erases == 1 && resume_calls == 1);

    /* A returned program error has the same one-shot service behavior. */
    reset_counts(); s = service(); app.save_gen = 4; fail_program = 1;
    memset(flash, 0xff, sizeof flash);
    assert(lunar_project_save_service_poll(&s, &app) == 2);
    fail_program = 0;
    assert(s.seen_gen == 4 && save_messages == 1 && !last_saved_ok);
    assert(pause_calls == 1 && resume_calls == 1 && draw_calls == 1);
    assert(io_erases == 1 && io_programs == 1);
    assert(!lunar_project_save_service_poll(&s, &app));
    assert(io_programs == 1 && resume_calls == 1);

    /* A successful fake transaction reaches commit through the real store. */
    reset_counts(); s = service(); app.save_gen = 5;
    memset(flash, 0xff, sizeof flash);
    assert(lunar_project_save_service_poll(&s, &app) == 2);
    assert(s.seen_gen == 5 && save_messages == 1 && last_saved_ok);
    assert(pause_calls == 1 && resume_calls == 1 && draw_calls == 1);
    assert(io_erases == 1 && io_programs >= 3);
    assert(!lunar_project_save_service_poll(&s, &app));
    assert(io_erases == 1 && resume_calls == 1);

    /* If transport cannot prove ready and XIP restored, firmware control does
     * not return from the callback: service cannot resume/draw or retry. The
     * host longjmp observes this boundary without asserting hardware recovery. */
    reset_counts(); s = service(); app.save_gen = 6; unresolved_erase = 1;
    transport_ready = xip_restored = 1; memset(flash, 0xff, sizeof flash);
    if (!setjmp(unresolved)) (void)lunar_project_save_service_poll(&s, &app);
    unresolved_erase = 0;
    assert(!transport_ready && !xip_restored);
    assert(s.seen_gen == 6 && pause_calls == 1 && io_erases == 1);
    assert(!resume_calls && !draw_calls);
    /* A host-side return after the modeled non-return is not a firmware retry:
     * the service has already consumed the generation before entering I/O. */
    assert(!lunar_project_save_service_poll(&s, &app));
    assert(io_erases == 1 && !resume_calls);
    puts("actual SAVE service callback composition: PASS");
    return 0;
}
