/* fm1_mod_view.h -- the modulation pages on the virtual FM-1's screen
 * (docs/16 §5, stage MG3), between the app's title and bottom bars:
 *
 *   RACK    y 28-46 the rack: 8 cells, each filled to its module's first
 *           output, the shown one outlined (gold while grabbed), an empty
 *           position hollow; y 50 "3 ENV3 >2 <1 ~1" (position, module,
 *           cables out, in and a tick late); from y 72 four parameter rows
 *           as HOME's, with the marks below
 *   MATRIX  seven slot rows of 19 characters at 22 px (fm1_mod_ui_row), the
 *           selected one inverted, and the hint line
 *   CHAIN   eight lines, node and cable alternating (fm1_mod_ui_chain), the
 *           selected cable in the accent colour
 * and on every parameter page (HOME, FX, RACK) a routed parameter's row
 * (docs/16 §5.5): its label from abbr, a jack-shaped marker after it, a
 * gold bracket of +-the cables' depth round the base on the bar, and a
 * 1 px tick at the live value. Every text run keeps the 4 px gap; the
 * layout sweep (fm1-sim-render --screens) checks each state.
 *
 * C99, no heap. MIT licence, like the rest of this repository.
 */
#ifndef FM1_MOD_VIEW_H_
#define FM1_MOD_VIEW_H_

#include <stddef.h>
#include <stdint.h>

#include "fm1_mod_ui.h"
#include "fm1_tft.h"

#ifdef __cplusplus
extern "C" {
#endif

void fm1_mod_view_rack(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u);
void fm1_mod_view_matrix(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u,
                         uint64_t now);
void fm1_mod_view_chain(fm1_tft_t *t, const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u);

/* The title bar's text and the bottom bar's left text in a modulation mode
 * (FM1_MODE_RACK, _MATRIX, _CHAIN). */
void fm1_mod_view_title(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, int mode, char *buf,
                        size_t size);
void fm1_mod_view_bottom(const fm1_mod_ui_env_t *env, const fm1_mod_ui_t *u, int mode, char *buf,
                         size_t size);

/* A parameter row at y (label line, then its bar BAR_DY below), as HOME's
 * rows draw it, the value as `text` says (NULL: fm1_look_value's); with
 * routes > 0 it gets the marks: depth is the sum of the cables' amounts
 * (fm1_mod_ui_routes) and live the value the parameter has now. */
void fm1_mod_view_row(fm1_tft_t *t, int y, const fm1_param_t *p, float base, const char *text,
                      int routes, float depth, float live);

#ifdef __cplusplus
}
#endif

#endif /* FM1_MOD_VIEW_H_ */
