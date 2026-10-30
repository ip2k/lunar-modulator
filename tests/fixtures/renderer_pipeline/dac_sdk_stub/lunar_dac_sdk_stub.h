/* Declarations only, for a host syntax check of renderer_pipeline_dac.c.
 * Not the SDK: no register, IRQ or timing behaviour is modelled. */
#ifndef LUNAR_DAC_SDK_STUB_H
#define LUNAR_DAC_SDK_STUB_H
#include <stdint.h>
#include <stdio.h>
typedef uint8_t u8;
#define ___interrupt
#define local_irq_save(f) ((f)=0)
#define local_irq_restore(f) ((void)(f))
#define FADE_DISABLE 0
struct dac_platform_data { unsigned pa_mute_port, hw_channel, ch_num, sr_points, vcm_init_delay_ms; };
typedef struct { uint32_t DAC_ADR, DAC_LEN, DAC_PNS, DAC_HRP, DAC_SWP, DAC_CON, DAC_SWN; } stub_audio_t;
extern volatile stub_audio_t *JL_AUDIO;
void dac_irq_handler(void);
void dac_early_init(int a, unsigned channel, unsigned delay);
int dac_open(const struct dac_platform_data *config);
int dac_set_sample_rate(unsigned rate);
void dac_set_data_handler(void *priv, void (*handler)(void *, u8 *, int));
void request_irq(unsigned irq, unsigned priority, void (*handler)(void), unsigned cpu);
void dac_set_volume(unsigned volume);
void dac_set_gain(unsigned gain, unsigned fade);
int dac_on(void);
int dac_off(void);
int dac_close(void);
uint32_t timer_get_ms(void);
void os_time_dly(unsigned ticks);
unsigned uxTaskGetStackHighWaterMark(void *task);
#endif
