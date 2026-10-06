/* fm1_state_caps.h -- the caps a state reader enforces on hostile input
 * (notes/2026-10-06-state-files.md §16): the bytes a file of each kind may
 * hold after inflating, and the JSON reader's structure limits. One table,
 * so the reader (stage E3), the metadata export (fm1_meta.h, which carries
 * them to the web editor, so it refuses what a load would) and the tests
 * agree.
 *
 * Plain C99, our own code. MIT licence, like the rest of this repository.
 */
#ifndef FM1_STATE_CAPS_H_
#define FM1_STATE_CAPS_H_

/* Bytes after inflating, by kind. */
#define FM1_STATE_CAP_PROJECT 262144u   /* a full project is about 170 KB [inferred] */
#define FM1_STATE_CAP_SOUND 32768u
#define FM1_STATE_CAP_FX 32768u
#define FM1_STATE_CAP_MODS 65536u
#define FM1_STATE_CAP_CLIP 32768u
#define FM1_STATE_CAP_SETTINGS 4096u
#define FM1_STATE_CAP_MOVY1 65536u      /* a .movy1 set */
#define FM1_STATE_CAP_SYX 65536u        /* a .syx file (FM1_APP_DX7_FILE_MAX) */

/* JSON structure. */
#define FM1_STATE_CAP_DEPTH 8u          /* nesting; the deepest file is 6 */
#define FM1_STATE_CAP_STRING 16384u     /* bytes in a string (a movy1 line) */
#define FM1_STATE_CAP_KEY 64u           /* bytes in a member's name */
#define FM1_STATE_CAP_NUMBER 32u        /* characters in a number */
#define FM1_STATE_CAP_MEMBERS 64u       /* members in an object */
#define FM1_STATE_CAP_ITEMS 8192u       /* items in an array */

#endif /* FM1_STATE_CAPS_H_ */
