#ifndef FM1_BOARD_POWER_H
#define FM1_BOARD_POWER_H
#include <stdint.h>
/* 0: not entered; 1: SDK power init running; 2: returned. Live RAM only,
 * not a voltage measurement or a hardware-qualification flag. */
extern volatile uint32_t fm1_power_stage;
void fm1_board_power_init(void);
#endif
