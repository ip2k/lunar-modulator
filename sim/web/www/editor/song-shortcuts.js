// Song workspace keyboard policy. Keep native form, dialog and browser keys.
// MIT licence, like the rest of Lunar.
export function songCommand(e, { canvas = false, note = false, section = false } = {}) {
  if (e.defaultPrevented || e.isComposing || e.repeat) return null;
  const key = e.key.toLowerCase(), mod = e.ctrlKey || e.metaKey;
  const selection = canvas || note || section;
  if (mod) return !e.altKey && !e.shiftKey && key === 'd' && selection ? 'duplicate' : null;
  if (e.altKey) return !e.shiftKey && key === 'a' ? 'mute' : null;
  if (key === ' ' || e.code === 'Space') return canvas ? (e.shiftKey ? 'restart' : 'transport') : null;
  if (e.shiftKey) return null;
  if (key === 'tab') return canvas ? 'arrangeMix' : null;
  if (key === 'e') return 'clip';
  if (key === 'a') return 'automation';
  if (key === 'd') return 'device';
  if (key === 'i') return 'sidebar';
  if (key === '0') return 'mute';
  if (key === 'f2' && selection || key === 'enter' && canvas) return 'rename';
  if (['delete', 'backspace'].includes(key)) return selection ? 'delete' : null;
  if (['arrowleft', 'arrowright', 'arrowup', 'arrowdown'].includes(key)) return canvas || note ? key : null;
  return null;
}

export function noteNudge(c, n, dx, dy) {
  const step = Math.max(c.loopStart, Math.min(c.loopStart + c.length - 1, n.step + dx));
  return { step, tick: Math.max(0, step * 24 + n.tick - n.step * 24), pitch: Math.max(0, Math.min(127, n.pitch + dy)) };
}

export function duplicateNote(c, original) {
  const source = c?.notes.find(n => JSON.stringify(n) === JSON.stringify(original));
  if (!source) throw new Error('This note changed elsewhere. Select it again.');
  if (source.step + 1 >= c.loopStart + c.length) throw new Error('No next step inside this clip.');
  const next = { ...source, step: source.step + 1, tick: source.tick + 24 };
  if (c.notes.some(n => n.step === next.step && n.pitch === next.pitch)) throw new Error('The next step already has this pitch.');
  const trig = c.trigs.find(t => t.step === source.step && t.lane === source.pitch);
  if (trig && c.trigs.some(t => t.step === next.step && t.lane === next.pitch)) throw new Error('The next step already has a trigger for this pitch.');
  c.notes.push(next);
  if (trig) c.trigs.push({ ...trig, step: next.step });
  return c.notes.length - 1;
}

export function makeSongShortcuts(root, ctx) {
  return function onKey(e) {
    const target = e.target;
    if (!root.isConnected || !ctx.ready() || !target?.closest ||
        target.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="textbox"], [role="slider"]') ||
        document.querySelector('dialog[open], [role="dialog"][aria-modal="true"]:not([hidden])') ||
        (root.querySelector('.sq-import') || document.querySelector('details[open].sq-file-tools'))) return false;
    const inside = root.contains(target);
    // The host may route keys from body after a selected control was redrawn.
    if (!inside && target !== document.body) return false;
    const canvas = target === root || target === document.body ||
      !!target.closest('.sq-roll, .sq-scroll, .sq-view-panel') && !target.closest('button, a, summary, [role="button"], [role="tab"]');
    const note = !!target.closest('[data-note]');
    const section = !!target.closest('.sq-entry');
    const command = songCommand(e, { canvas, note, section });
    if (!command || !ctx.run(command)) return false;
    e.preventDefault(); e.stopPropagation(); ctx.claimKeys?.();
    return true;
  };
}
