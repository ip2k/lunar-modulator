/* SPDX-License-Identifier: MIT
 * M6 RAM image core: one reduced voice into ALNK0, per-block timing and the
 * RAM status block. Portable C99 with no register access of its own: ALNK0
 * goes through `struct lunar_alnk0_ops` (board/alnk0_audio.h), the
 * stopwatch through `struct lunar_timer_io` (timing/timer4.h) and the
 * report sink through a callback, so tests/test_m6_image.py runs all of it
 * on a desktop against a simulated ALNK0 and timer. 32-bit integer
 * arithmetic only: the SDK-free link has no runtime library.
 */
#ifndef LUNAR_M6_CORE_H
#define LUNAR_M6_CORE_H

#include <stdint.h>

#include "../board/alnk0_audio.h"
#include "../timing/timer4.h"

#define LUNAR_M6_FRAMES        64u    /* stereo frames per ALNK0 half (F20) */
#define LUNAR_M6_HALF_WORDS    128u   /* LEN: 32-bit words per half */
#define LUNAR_M6_FS_NOMINAL    44118u /* F18 [reported] */
#define LUNAR_M6_WINDOW        1024u  /* blocks per published timing window */
#define LUNAR_M6_HASH_BLOCKS   1024u  /* blocks covered by pcm_hash */
#define LUNAR_M6_KICK_BLOCKS 256u   /* about 0.37 s; must be a power of two */
#define LUNAR_M6_NOTE_BLOCKS   512u   /* blocks per arpeggio note, ~0.74 s */
#define LUNAR_M6_LEVEL         4096   /* peak envelope, Q15: output -18 dBFS */
#define LUNAR_M6_ATTACK        128    /* samples of linear attack */

/* Stopwatch: TIMER4 free-running, OSC source, prescaler index 2 (/16), PRD
 * 0x7fff [verified: SDK timer test2.c CON layout and divider table]. The
 * modulus is PRD + 1 [inferred]; a block (~1.45 ms) is under a quarter of a
 * wrap for any oscillator up to 40 MHz, and every caller reads the counter at
 * least once per block, so deltas below the modulus are unambiguous. */
#define LUNAR_M6_TIMER_PRD     0x7fffu
#define LUNAR_M6_TIMER_MOD     (LUNAR_M6_TIMER_PRD + 1u)
#define LUNAR_M6_TIMER_RUN     ((2u << 4) | (1u << 3) | 1u)
/* Tick rates at the two oscillators stock V15 chooses between [verified: V15
 * bytes, timing/README.md]. Waits use the upper rate so they are never short. */
#define LUNAR_M6_TICK_HZ_24M   1500000u
#define LUNAR_M6_TICK_HZ_40M   2500000u
#define LUNAR_M6_TICKS_PER_MS_UPPER (LUNAR_M6_TICK_HZ_40M / 1000u)
#define LUNAR_M6_FIRST_TIMEOUT_MS 100u /* first ALNK0 block, at least */
#define LUNAR_M6_STALL_TIMEOUT_MS 50u  /* any later block, at least */
#define LUNAR_M6_CALIBRATE_TICKS 1500u /* cpu_polls span: 1 ms at 24 MHz */

#define LUNAR_M6_MAGIC  0x55413a4du /* "M:AU" little-endian */
#define LUNAR_M6_LAYOUT 1u
#define LUNAR_M6_STATUS_BYTES 144u
#define LUNAR_SYS_DIV  0x00010008u
#define LUNAR_CLK_CON0 0x0001000cu
#define LUNAR_CLK_CON1 0x00010010u

enum lunar_m6_step {
    LUNAR_M6_ENTERED = 1, LUNAR_M6_CORE_OK, LUNAR_M6_TIMER_OK, LUNAR_M6_REPORT_OK,
    LUNAR_M6_STOPWATCH_OK, LUNAR_M6_ALNK0_OK, LUNAR_M6_FIRST_BLOCK, LUNAR_M6_HASHED,
    LUNAR_M6_FINISHED
};

enum lunar_m6_flag {
    LUNAR_M6_FLAG_TIMER_FALLBACK = 1u << 0, /* setup delays fell back to a spin */
    LUNAR_M6_FLAG_NO_CLOCK = 1u << 1,       /* no first ALNK0 block in time */
    LUNAR_M6_FLAG_STALL = 1u << 2,          /* ALNK0 blocks stopped coming */
    LUNAR_M6_FLAG_PINS_MASKED = 1u << 3,    /* dev kit: PORTC writes dropped */
    LUNAR_M6_FLAG_REPORT_FAILED = 1u << 4,  /* panel or UART gave up */
    LUNAR_M6_FLAG_ALNK0_FAILED = 1u << 5,   /* lunar_alnk0_start refused */
    LUNAR_M6_FLAG_WDT_ARMED = 1u << 6,      /* P3_WDT_CON bit 4 was set at entry */
    LUNAR_M6_FLAG_WDT_FAILED = 1u << 7      /* a watchdog kick hit a busy P33 bus */
};

enum lunar_m6_end {
    LUNAR_M6_END_DONE = 0, LUNAR_M6_END_ALNK0, LUNAR_M6_END_NO_CLOCK, LUNAR_M6_END_STALL,
    LUNAR_M6_END_ARGS
};

/* The RAM status block. Stable layout (LUNAR_M6_LAYOUT 1): every field is a
 * 32-bit word at the offset in the comment, then the build id. Tick fields
 * are TIMER4 ticks of the stopwatch above. tests/test_m6_image.py pins it. */
struct lunar_m6_status {
    uint32_t magic;            /*   0 */
    uint32_t layout;           /*   4 */
    uint32_t step;             /*   8 enum lunar_m6_step, last reached */
    int32_t alnk0_result;      /*  12 lunar_alnk0_start's return */
    uint32_t report_result;    /*  16 FM-1: panel result; kit: 0, or 1 if the UART failed */
    uint32_t flags;            /*  20 enum lunar_m6_flag */
    uint32_t end;              /*  24 enum lunar_m6_end once the loop has stopped */
    uint32_t tick_mod;         /*  28 stopwatch modulus */
    uint32_t blocks;           /*  32 blocks rendered */
    uint32_t late;             /*  36 blocks whose work ran past the next boundary */
    uint32_t missed;           /*  40 boundaries passed unseen: free half repeated,
                                  or an interval over 3/2 of the shortest */
    uint32_t render_last;      /*  44 voice render, per block */
    uint32_t render_min;       /*  48 */
    uint32_t render_max;       /*  52 */
    uint32_t interval_last;    /*  56 between ALNK0 boundaries seen */
    uint32_t interval_min;     /*  60 */
    uint32_t interval_max;     /*  64 */
    uint32_t busy_max;         /*  68 render plus report work, per block */
    uint32_t windows;          /*  72 complete windows of LUNAR_M6_WINDOW blocks */
    uint32_t win_render;       /*  76 render ticks summed over the last window */
    uint32_t win_interval;     /*  80 interval ticks summed over the last window */
    uint32_t pcm_hash;         /*  84 FNV-1a over the words of the first blocks */
    uint32_t pcm_hash_blocks;  /*  88 blocks in pcm_hash so far */
    uint32_t cpu_polls;        /*  92 stopwatch reads in LUNAR_M6_CALIBRATE_TICKS */
    uint32_t first_wait;       /*  96 ticks from ALNK0 start to its first block */
    uint32_t sys_div;          /* 100 SYS_DIV 0x10008, read once at entry */
    uint32_t clk_con0;         /* 104 CLK_CON0 0x1000C, read once at entry */
    uint32_t clk_con1;         /* 108 CLK_CON1 0x10010 */
    uint32_t clk_con2;         /* 112 CLK_CON2 0x10014 [all four: verified, WL82.h] */
    uint32_t timer_con_before; /* 116 TIMER4 CON as found at entry */
    uint32_t pins_masked;      /* 120 dev kit: PORTC writes dropped */
    char build_id[20];         /* 124 NUL-terminated, 1..19 characters */
};

/* The reduced voice: two sine operators (modulator at twice the carrier
 * frequency into the carrier's phase), one envelope that also scales the
 * modulation depth, a four-note arpeggio (A3 C#4 E4 A4, 512 blocks each),
 * both channels equal. Each note attacks linearly over 128 samples from
 * wherever the last one decayed to, then decays exponentially with a time
 * constant of 8,192 samples (~0.19 s; about -35 dB by the next note). Phases
 * run on across notes, so nothing jumps. Reads the trunc12 sine (m6_sine.h).
 * Not msfa's operator or envelope. */
struct lunar_m6_voice {
    uint32_t carrier, modulator; /* phases, 32-bit cycle */
    int32_t env;                 /* envelope, Q15 << 16: 0..LUNAR_M6_LEVEL << 16 */
    uint32_t note, block_in_note, attack;
};

struct lunar_m6_platform {
    void *context;
    const struct lunar_alnk0_ops *alnk0;
    const struct lunar_timer_io *timer;   /* stopwatch registers */
    /* One bounded unit of report work (a panel pixel, a UART byte). Called
     * only while the block's slack budget lasts. Returns 0 when idle. */
    int (*report)(void *context);
    /* Optional: clear the watchdog. Called once every LUNAR_M6_KICK_BLOCKS
     * blocks, after the render is timed and before the report work. */
    void (*kick)(void *context);
};

struct lunar_m6 {
    volatile struct lunar_m6_status *status;
    struct lunar_m6_voice voice;
    const struct lunar_m6_platform *platform;
    int32_t *buffer;        /* 2 * LUNAR_M6_HALF_WORDS words, 32-byte aligned */
    uint32_t dma_address;
    uint32_t have_last, last_tick, last_half; /* have_last: boundaries seen, to 2 */
    uint32_t acc_blocks, acc_render, acc_interval;
};

int32_t lunar_m6_sine(uint32_t phase);
void lunar_m6_voice_init(struct lunar_m6_voice *voice);
/* Render one half: LUNAR_M6_FRAMES stereo frames, L then R, Q23 words. */
void lunar_m6_voice_render(struct lunar_m6_voice *voice, int32_t *words);
uint32_t lunar_m6_hash_words(uint32_t hash, const int32_t *words, unsigned count);
#define LUNAR_M6_HASH_SEED 2166136261u

void lunar_m6_status_init(volatile struct lunar_m6_status *status, const char *build_id);

/* Stopwatch on TIMER4 (registers through `io`): stop and clear, CNT 0,
 * PRD, then run. tick() reads CNT reduced below the modulus. */
void lunar_m6_stopwatch_start(const struct lunar_timer_io *io);
uint32_t lunar_m6_tick(const struct lunar_timer_io *io);
uint32_t lunar_m6_ticks_between(uint32_t then, uint32_t now);
/* 1 when CNT changes within `polls` reads: the stopwatch is counting. Every
 * timed wait below assumes it is, so callers check this first. */
int lunar_m6_stopwatch_alive(const struct lunar_timer_io *io, uint32_t polls);
/* Wait at least `ticks` (counted across wraps); returns the polls taken. */
uint32_t lunar_m6_wait_ticks(const struct lunar_timer_io *io, uint32_t ticks);

/* Per-block accounting, from stopwatch readings: a boundary seen at `now`
 * with `half` free, the render finished at `rendered`, the report work
 * finished at `done` with `pending_again` read then. */
void lunar_m6_on_boundary(struct lunar_m6 *m, uint32_t now, uint32_t half);
void lunar_m6_on_rendered(struct lunar_m6 *m, uint32_t start, uint32_t rendered);
void lunar_m6_on_done(struct lunar_m6 *m, uint32_t start, uint32_t done, int pending_again);
/* Report work may continue while the block is younger than half its shortest
 * interval, once 8 intervals are known; never before. */
int lunar_m6_slack_left(const struct lunar_m6 *m, uint32_t start, uint32_t now);

/* Start ALNK0 and run blocks until `max_blocks` (0 = forever) or a stop.
 * Interrupts stay masked: the boundary is polled (`attach_irq` must not
 * enable anything). Returns enum lunar_m6_end; stops ALNK0 before returning. */
int lunar_m6_run(struct lunar_m6 *m, const struct lunar_m6_platform *platform,
                 int32_t *buffer, uint32_t dma_address, uint32_t max_blocks);

/* Dev kit: is this an ALNK0 pin register the kit build must not write? */
int lunar_m6_kit_masks(uint32_t address);

/* Formatting helpers shared by the panel and the UART report. */
unsigned lunar_m6_put_u(char *out, unsigned room, uint32_t value);
unsigned lunar_m6_put_hex(char *out, unsigned room, uint32_t value);
/* fs estimate in Hz from a window's interval ticks and the tick rate. */
uint32_t lunar_m6_fs_estimate(uint32_t win_interval, uint32_t tick_hz);
/* Render load of a window in tenths of a percent. */
uint32_t lunar_m6_load_permille(uint32_t win_render, uint32_t win_interval);
/* One report line for the last published window, ending CR LF, NUL-terminated
 * when room allows; returns the characters written. `room` >= 128 fits all. */
unsigned lunar_m6_format_window(const volatile struct lunar_m6_status *status,
                                char *out, unsigned room);

#endif
