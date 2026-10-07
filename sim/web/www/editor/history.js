// editor/history.js -- one page history for the editor's and the panel's
// edits (stage ED2, notes/2026-10-06-web-editor.md §8): parameter values,
// a sound's level and a MIDI effect's on. No DOM; node runs it as is
// (test/editor-unit.mjs).
//
// - Each entry has its origin (editor or panel) and how it was made.
// - A pointer drag is one entry (begin/end); key repeats and knob turns on
//   one parameter from one origin within 600 ms are one.
// - Undo and redo hand back the entry; the caller sends its `before` or
//   `after` as an edit, and the change that comes back is not recorded again
//   (the caller passes it to `confirm`).
// - A new edit clears what could be redone; 200 entries at most.
// Structural entries (stage ED3: an engine or effect chosen, a swap, a
// module moved or chosen) carry the records that undo and redo them in
// `info` and never vanish when they end where they began; undo's snapshot
// fallback comes with ED4. MIT licence, like the rest of this repository.

export const MERGE_MS = 600;
export const LIMIT = 200;

export class History {
  constructor({ limit = LIMIT, mergeMs = MERGE_MS, now = () => Date.now() } = {}) {
    this.limit = limit;
    this.mergeMs = mergeMs;
    this.now = now;
    this.entries = [];
    this.at = 0;               // entries[0..at) are done; entries[at..] can be redone
    this.drag = null;          // the target key a pointer drag holds
    this.nextId = 1;
  }

  get canUndo() { return this.at > 0; }
  get canRedo() { return this.at < this.entries.length; }
  get done() { return this.entries.slice(0, this.at); }

  beginDrag(target) { this.drag = target; this.dragEntry = null; }
  endDrag() { this.drag = null; this.dragEntry = null; }

  // One change: {target, label, before, after, origin, how}. `target` is a
  // stable key for the value (block, uid). Returns the entry it made or grew,
  // or null when nothing changed.
  record(c) {
    if (c.before === c.after) return null;
    const t = this.now();
    const last = this.at > 0 ? this.entries[this.at - 1] : null;
    const inDrag = this.drag !== null && this.drag === c.target && c.origin === 'editor';
    const merge = last && last.target === c.target && last.origin === c.origin && this.at === this.entries.length &&
      ((inDrag && this.dragEntry === last) ||
       (!inDrag && c.how !== 'typed' && last.how === c.how && t - last.at <= this.mergeMs));
    if (merge) {
      last.after = c.after;
      last.at = t;
      if (c.info && c.info.redo) last.info.redo = c.info.redo;
      if (last.after === last.before && !(last.info && last.info.struct)) {          // back where it began: no step
        this.entries.splice(this.at - 1, 1);
        this.at -= 1;
        if (inDrag) this.dragEntry = null;
        return null;
      }
      return last;
    }
    this.entries.length = this.at;               // a new edit: no more redo
    const e = { id: this.nextId++, target: c.target, label: c.label || c.target, before: c.before, after: c.after,
      origin: c.origin, how: c.how || 'set', at: t, info: c.info || null };
    this.entries.push(e);
    if (this.entries.length > this.limit) this.entries.shift();
    this.at = this.entries.length;
    if (inDrag) this.dragEntry = e;
    return e;
  }

  // An entry's value as C set it (the echo of the editor's own op).
  confirm(id, after) {
    const e = this.entries.find((x) => x.id === id);
    if (e) e.after = after;
  }

  // An edit C refused: its entry goes, if nothing has been stacked on it.
  drop(id) {
    const i = this.entries.findIndex((x) => x.id === id);
    if (i >= 0 && i === this.at - 1 && this.at === this.entries.length) {
      this.entries.splice(i, 1);
      this.at -= 1;
    }
  }

  undo() {
    if (!this.canUndo) return null;
    this.drag = null;
    this.at -= 1;
    return this.entries[this.at];
  }

  redo() {
    if (!this.canRedo) return null;
    this.drag = null;
    return this.entries[this.at++];
  }

  clear() { this.entries = []; this.at = 0; this.drag = null; }
}
