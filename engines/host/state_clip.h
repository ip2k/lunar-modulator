/* state_clip.h -- a clip file's lines and a set (state_clip.c): the
 * desktop tools' clip load and save (fm1-render, fm1-seq), until the app's
 * state stage (A1) merges a clip into the core directly. Host code. MIT
 * licence. */
#ifndef STATE_CLIP_H_
#define STATE_CLIP_H_

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* The set (movy1 text, as the core exports it) with a clip file's lines (at
 * track 0, slot 0) put at `track` and `slot` (0-based): the slot's old
 * lines go, the clip's lanes take the track's lane with the same label or
 * else a free one (none free: NULL, NO_ROOM in err), and its locks follow
 * them. A malloc'd text, for fm1_seq_import_movy1; NULL with err. */
char *fm1_state_clip_into(const char *set, size_t n, const char *const *clip, size_t nclip, unsigned track,
                          unsigned slot, char *err, size_t errcap);

/* A clip out of a set: the au lines of the lanes its locks use, then its
 * cl, cp, lk and tg lines, at track 0 and slot 0. NULL when that slot has
 * no clip. Free with fm1_state_clip_free. */
char **fm1_state_clip_from(const char *set, size_t n, unsigned track, unsigned slot, size_t *count);
void fm1_state_clip_free(char **lines, size_t count);

#ifdef __cplusplus
}
#endif

#endif /* STATE_CLIP_H_ */
