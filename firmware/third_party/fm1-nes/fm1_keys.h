/* SPDX-License-Identifier: Apache-2.0
 * Adapted from fm1-nes by Keitark (870f3054869c77f03fc1c8a3a425dafa3dfa7b22):
 * firmware/nes/src/fm1_stock_keys.c and firmware/usb-diag/peripheral_logic.c.
 * Changes are listed in UPSTREAM.md. Lunar Modulator, 2026-11-08.
 */
#ifndef LUNAR_FM1_KEYS_H
#define LUNAR_FM1_KEYS_H

#define LUNAR_MATRIX_COLUMNS 11u
#define LUNAR_KEY_COUNT 41u     /* ids 0-13 buttons, 14-40 keys F3..G5 */
#define LUNAR_ENCODER_COUNT 7u

/* One packed sample per PHYSICAL column (the 595 output selected while the
 * rows were read): bit0 PA0, bits1-4 PA5-PA8, bit5 PB7, active low. */
unsigned lunar_keys_pack(unsigned porta_in, unsigned portb_in);

/* Pressed key ids as a 41-bit set in two words: bit (id & 31) of word id/32.
 * A NULL rows pointer yields no keys. No 64-bit arithmetic (pi32v2 helper-free). */
void lunar_keys_decode(const unsigned char rows[LUNAR_MATRIX_COLUMNS], unsigned pressed[2]);

/* Physical (column << 4 | row bit) of key id, or 0xff for a bad id. */
unsigned lunar_key_cell(unsigned id);

struct lunar_encoders {
    unsigned char previous[LUNAR_ENCODER_COUNT], candidate[LUNAR_ENCODER_COUNT];
    int count[LUNAR_ENCODER_COUNT];
    unsigned invalid[LUNAR_ENCODER_COUNT];
    unsigned valid;
};
extern const char *const lunar_encoder_names[LUNAR_ENCODER_COUNT];

void lunar_encoders_reset(struct lunar_encoders *s);
/* Counts are contact edges, not detents; the clockwise sign is unestablished. */
void lunar_encoders_sample(struct lunar_encoders *s, const unsigned char rows[LUNAR_MATRIX_COLUMNS]);
#endif
