/* GPL-3.0-only. Typed host injection; no MMIO or device execution. */
#ifndef LUNAR_SELECTED_RETURN_TARGET_INJECTED
#error "host injection only"
#endif
typedef struct { uint32_t unused; } fm1_crash_t;
static void fm1_fault(const fm1_crash_t *);
#define FM1_AUDIO_HALF 0x80u
#define FM1_IRQ_ALNK0 11u
#define FM1_IRQ_TIMER5 63u
#define FM1_TICKS_PER_US 24u
static void fm1_irq_init(void),fm1_irq_mask(unsigned),fm1_irq_enable_all(void);
static void fm1_timer5_ack(void),fm1_input_tick(void),fm1_input_init(void);
static void fm1_timer5_start(void (*)(void),uint32_t);
static void fm1_audio_prepare(int32_t *,uint32_t,void (*)(void),uint32_t);
static void fm1_audio_start_prepared(void),fm1_audio_finish_start(void),fm1_audio_stop(void);
static uint8_t fm1_audio_pending(void);
static uint32_t fm1_audio_free_half(void),fm1_ticks(void);
static void fm1_audio_ack_aux(uint8_t),fm1_audio_ack_half(void);
static void lunar_audio_owner_test_iteration(void);
