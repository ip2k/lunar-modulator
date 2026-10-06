/* fm1_mod_view.h -- the modulation pages on the virtual FM-1's screen
 * (docs/16 §5, stage MG3), between the app's title and bottom bars:
 *
 *   RACK    y 28-46 the rack: 8 cells, each a meter of its module's first
 *           output in the modulation colour (an empty position hollow),
 *           the shown one with the selection's bar under it (gold while
 *           grabbed); y 50 the line "LFO6  2 out  7 in  1 late  4 voices"
 *           in MID (SMALL when that does not fit); from y 72 four parameter
 *           rows as HOME's
 *   MATRIX  nine slot rows of 28 characters in MID at 18 px (fm1_mod_ui_row):
 *           the source in the modulation colour, the mark subtle, the
 *           destination and amount as text, a sound's "S<n>" in its colour
 *           (one multi-colour run a row, audit L2); the selected row on the
 *           selection's bar, an off one subtle, a refused one in the
 *           refusal colour; the hint line under them
 *   CHAIN   ten lines in MID, node and cable alternating (fm1_mod_ui_chain),
 *           coloured as MATRIX's, the selected cable on the selection's bar
 * and on every parameter page (HOME, FX, RACK) a routed parameter's row
 * (docs/16 §5.5; audit Q3): its label at full length in the modulation
 * colour, a bracket in that colour of +-the cables' depth round the base
 * on the bar, and a 1 px tick at the live value in the text colour. Every
 * text run keeps the 4 px gap; the layout sweep (fm1-sim-render --screens)
 * checks each state.
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
