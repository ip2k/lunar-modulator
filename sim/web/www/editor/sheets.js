// editor/sheets.js -- the phone's sheets (notes/2026-10-06-web-editor.md §14, "v1 completed"):
// "Add a cable" as a three-step sheet (source, destination, amount) where the
// editor has no room for the table's row, and a block's menu, opened by a long
// press (a touch held for half a second without moving), by a right click or
// by the keyboard's menu key. Both are a dialog at the bottom of the editor on
// a phone and a card above the page elsewhere.
//
// Nothing here decides a rule: the lists are the chains' own (sources and
// destinations from the metadata and the mirror), the verdict shown before a
// cable is made is C's (the shadow Worker's `preview`, through the Map's
// `verdictFor`), and what a menu item does is what the same control in the
// inspector does. MIT licence, like the rest of this repository.

import { blockTag, parseBlockKey, parseModKey } from './model.js';

const HOLD_MS = 500;       // a long press
const SLOP = 8;            // px a held touch may drift

export function makeSheets(ctx, h) {
  const { st, el, root } = ctx;
  let current = null;                       // { box, anchor }

  function close(refocus = true) {
    if (!current) return;
    const { box, anchor } = current;
    current = null;
    box.remove();
    if (refocus && anchor && anchor.isConnected) anchor.focus({ preventScroll: true });
  }
  function shell(title, label, anchor) {
    close(false);
    const box = el('div', 'ed-sheet', { role: 'dialog', 'aria-modal': 'true', 'aria-label': label });
    const head = el('div', 'ed-sheet-head', {}, [el('b', 'ed-sheet-t', { text: title }),
      el('button', 'ed-btn ed-sheet-x', { type: 'button', text: 'Close', onclick: () => close() })]);
    box.append(head);
    box.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); close(); }
      // The dialog keeps the keys: Tab walks its own controls, round.
      if (e.key === 'Tab') {
        const f = [...box.querySelectorAll('button, select, input')].filter((x) => !x.disabled && x.getClientRects().length);
        if (!f.length) return;
        const i = f.indexOf(document.activeElement);
        const j = e.shiftKey ? (i <= 0 ? f.length - 1 : i - 1) : (i === f.length - 1 ? 0 : i + 1);
        e.preventDefault();
        f[j].focus();
      }
    });
    root.append(box);
    current = { box, anchor };
    return box;
  }
  const first = (box) => { const t = box.querySelector('select, input, .ed-sheet-go, button:not(.ed-sheet-x)') || box.querySelector('button'); if (t) t.focus({ preventScroll: true }); };

  // ---- Add a cable: source, destination, amount ---------------------------------------------
  function addCableSheet(anchor) {
    const names = ['From', 'To', 'Amount'];
    const pick = { src: null, dest: null, pct: 25 };
    const srcs = h.sourceOptions(false);
    const dests = h.destList();
    const mod = srcs.find((x) => x.value >= 64) || srcs[0];
    pick.src = mod ? mod.value : null;
    const sel = ctx.blockOf(st.selected) ? h.unitCode(st.selected) : -1;
    const d0 = dests.find((x) => Number(x.value.split(':')[0]) === sel) || dests[0];
    pick.dest = d0 ? d0.value : null;
    let at = 0;
    const box = shell('Add a cable', 'Add a cable', anchor);
    const body = el('div', 'ed-sheet-body');
    const foot = el('div', 'ed-sheet-foot');
    box.append(body, foot);
    let token = 0;
    function draw() {
      body.replaceChildren(el('p', 'ed-sheet-step', { 'aria-live': 'polite', text: `Step ${at + 1} of 3 · ${names[at]}` }));
      foot.replaceChildren();
      if (at === 0) {
        body.append(h.selectOf(srcs, pick.src, 'Cable from', 'sheet:src', (v) => { pick.src = Number(v); }));
      } else if (at === 1) {
        body.append(h.selectOf(dests, pick.dest, 'Cable to', 'sheet:to', (v) => { pick.dest = v; }));
      } else {
        const out = el('output', 'ed-sheet-amt', { for: 'ed-sheet-amount', text: `${pick.pct > 0 ? '+' : ''}${pick.pct} %` });
        const range = el('input', 'ed-sheet-range', { type: 'range', id: 'ed-sheet-amount', min: '-100', max: '100', step: '1', value: String(pick.pct), 'aria-label': 'Amount, percent', 'data-fk': 'sheet:amount' });
        range.addEventListener('input', () => { pick.pct = Number(range.value); out.textContent = `${pick.pct > 0 ? '+' : ''}${pick.pct} %`; });
        const verdict = el('p', 'ed-sheet-verdict', { role: 'status', text: 'Asking C…' });
        body.append(el('p', 'ed-sheet-sum', { text: `${h.srcName(pick.src)} → ${destWords(pick.dest)}` }), el('div', 'ed-sheet-row', {}, [range, out]), verdict);
        const mine = ++token;
        Promise.resolve(h.verdictFor(pick.src, pick.dest)).then((v) => {
          if (mine !== token || !verdict.isConnected) return;
          verdict.textContent = v.ok ? `${v.text}.` : `${v.text}.`;
          verdict.classList.toggle('is-no', !v.ok);
        });
      }
      if (at > 0) foot.append(el('button', 'ed-btn', { type: 'button', text: 'Back', onclick: () => { at -= 1; draw(); first(box); } }));
      foot.append(at < 2
        ? el('button', 'ed-btn ed-btn-go ed-sheet-go', { type: 'button', text: 'Next', onclick: () => { at += 1; draw(); first(box); } })
        : el('button', 'ed-btn ed-btn-go ed-sheet-go', { type: 'button', text: 'Make the cable', onclick: () => {
          const i = h.makeCable(pick.src, pick.dest, pick.pct);
          close(false);
          if (i >= 0) ctx.say(`Cable ${i + 1} made: ${h.srcName(pick.src)} to ${destWords(pick.dest)}, ${pick.pct} percent.`);
        } }));
    }
    const destWords = (v) => { const d = dests.find((x) => x.value === v); return d ? d.name : v; };
    draw();
    first(box);
    return box;
  }

  // ---- a block's menu ---------------------------------------------------------------------------
  function blockMenu(key, anchor) {
    const b = ctx.blockOf(key);
    const tag = blockTag(key);
    const name = b ? ctx.engineName(b.engine) : 'empty';
    const box = shell(`${tag} · ${name}`, `${tag} menu`, anchor);
    const list = el('div', 'ed-sheet-list', { role: 'group', 'aria-label': `${tag}` });
    const item = (text, fn, extra = {}) => el('button', 'ed-btn ed-sheet-i', { type: 'button', text, onclick: () => { close(false); fn(); }, ...extra });
    const view = () => (parseModKey(key) >= 0 ? 'mod' : st.view === 'mod' || st.view === 'sound' ? st.view : 'flow');
    list.append(item('Open its page', () => ctx.select(key, { view: view() }), { 'data-fk': 'menu:open' }));
    list.append(item(b ? 'Choose another…' : 'Choose…', () => {
      ctx.select(key, { view: view() });
      requestAnimationFrame(() => { const t = root.querySelector(`[data-fk="${CSS.escape(key)}:pick"]`); if (t) t.click(); });
    }, { 'data-fk': 'menu:pick' }));
    const mv = h.moveSelect(key);
    if (mv) { mv.classList.add('ed-sheet-move'); list.append(mv); }
    if (b) for (const t of ctx.projectTools(key)) { t.classList.add('ed-sheet-i'); list.append(t); }
    box.append(list);
    first(box);
    return box;
  }

  // ---- the long press ---------------------------------------------------------------------------
  // A touch held half a second without drifting, a right click, or the menu key. A tap that ends a
  // long press does not also select the block.
  function wireMenu(node, key) {
    if (!node || node.dataset.menu) return node;
    node.dataset.menu = key;
    let timer = 0, start = null, swallow = false;
    const clear = () => { clearTimeout(timer); timer = 0; start = null; };
    node.addEventListener('pointerdown', (e) => {
      if (e.pointerType === 'mouse' || e.button !== 0) return;
      start = { x: e.clientX, y: e.clientY, id: e.pointerId };
      clearTimeout(timer);
      timer = setTimeout(() => { timer = 0; swallow = true; blockMenu(key, node); }, HOLD_MS);
    });
    node.addEventListener('pointermove', (e) => { if (start && e.pointerId === start.id && Math.hypot(e.clientX - start.x, e.clientY - start.y) > SLOP) clear(); });
    node.addEventListener('pointerup', clear);
    node.addEventListener('pointercancel', clear);
    node.addEventListener('contextmenu', (e) => { e.preventDefault(); clear(); swallow = true; blockMenu(key, node); });
    node.addEventListener('click', (e) => { if (swallow) { swallow = false; e.stopImmediatePropagation(); e.preventDefault(); } }, true);
    return node;
  }

  return { addCableSheet, blockMenu, wireMenu, close, get open() { return !!current; } };
}
