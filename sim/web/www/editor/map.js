// editor/map.js -- the Advanced editor's Map (stage ED5b,
// notes/2026-10-06-web-editor.md §3 mockup 05, §10, §13): the same cable
// slots as the matrix table, drawn as a patch bay. Sources on the left, the
// rack in the middle, destinations on the right; a cable runs from an output
// jack to an input jack, only in the gutters beside the columns and in the
// band above the rack, never across a block or a label. Selecting a module,
// a destination or a source (F, or a click) keeps its cables bright and dims
// the rest without their labels.
//
// The Map edits through the same records as the table (chains.js's
// `makeCable`, `ctx.setValue`): a cable dragged from an output to an input,
// or taken up with Enter and dropped with Enter, is one CABLE record; the
// verdict shown over an input while the cable is in hand is C's (the shadow
// Worker's `preview` with `mod`), never a rule here. It names no engine,
// effect, kind or source: every name, flag and jack comes from the metadata
// and the mirror. Live values reach it through the same `data-out` and
// `data-dest` hooks as the table's. MIT licence, like the rest of this
// repository.

import {
  ROLE, SOUNDS, INSERTS, MASTERS, SLOTS, NONE, GATE_DST, SLOT_ON, VOICE, moduleSource, isModuleSource, sourcePosition,
  blockKey, blockTag, modKey, parseBlockKey, parseModKey, hasFlag, cableEmpty, pctOfQ14, decodeMod,
} from './model.js';

const NS = 'http://www.w3.org/2000/svg';
const sv = (tag, attrs = {}) => {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, String(v));
  return n;
};
// A signal's kind in the metadata is cv_... for a continuous one; anything else is a gate or a trigger.
const isGate = (kind) => typeof kind === 'string' && !kind.startsWith('cv');
const visible = (e) => !!e && e.getClientRects().length > 0;
const inRect = (p, r, pad = 0) => p.x >= r.l - pad && p.x <= r.r + pad && p.y >= r.t - pad && p.y <= r.b + pad;
const hit = (a, b, pad = 0) => a.l < b.r + pad && a.r > b.l - pad && a.t < b.b + pad && a.b > b.t - pad;

// A polyline with its corners rounded.
function rounded(pts, r = 7) {
  let d = `M${pts[0].x} ${pts[0].y}`;
  for (let k = 1; k < pts.length - 1; ++k) {
    const a = pts[k - 1], b = pts[k], c = pts[k + 1];
    const l1 = Math.hypot(b.x - a.x, b.y - a.y), l2 = Math.hypot(c.x - b.x, c.y - b.y);
    const rr = Math.min(r, l1 / 2, l2 / 2);
    if (rr < 0.5) { d += ` L${b.x} ${b.y}`; continue; }
    const p1 = { x: b.x + ((a.x - b.x) / l1) * rr, y: b.y + ((a.y - b.y) / l1) * rr };
    const p2 = { x: b.x + ((c.x - b.x) / l2) * rr, y: b.y + ((c.y - b.y) / l2) * rr };
    d += ` L${p1.x} ${p1.y} Q${b.x} ${b.y} ${p2.x} ${p2.y}`;
  }
  const z = pts[pts.length - 1];
  return `${d} L${z.x} ${z.y}`;
}
const samples = (pts, step = 6) => {
  const out = [];
  for (let k = 1; k < pts.length; ++k) {
    const a = pts[k - 1], b = pts[k];
    const n = Math.max(1, Math.ceil(Math.hypot(b.x - a.x, b.y - a.y) / step));
    for (let j = 0; j < n; ++j) out.push({ x: a.x + ((b.x - a.x) * j) / n, y: a.y + ((b.y - a.y) * j) / n });
  }
  out.push(pts[pts.length - 1]);
  return out;
};
const bezier = (p0, p1, p2, p3, n = 40) => {
  const out = [];
  for (let k = 0; k <= n; ++k) {
    const t = k / n, u = 1 - t;
    out.push({ x: u * u * u * p0.x + 3 * u * u * t * p1.x + 3 * u * t * t * p2.x + t * t * t * p3.x,
      y: u * u * u * p0.y + 3 * u * u * t * p1.y + 3 * u * t * t * p2.y + t * t * t * p3.y });
  }
  return out;
};

export function makeMap(ctx, h) {
  const { st, meta, mm, el } = ctx;
  const { cableOf, verdictOf, destName, srcName, verdictWords, makeCable, toValue, pickerButton, preview, isLate, markChar, markWords } = h;
  const open = (name) => (st[name] || (st[name] = new Set()));

  let map = null, svg = null, pills = null, cols = {}, jacks = new Map(), geo = [], patch = null, obs = null, ghost = null;

  // ---- what is in focus ---------------------------------------------------------
  function focusTarget() {
    if (st.mapMode === 'refused') return { kind: 'refused' };
    if (st.mapMode === 'late') return { kind: 'late' };
    if (st.mapMode !== 'focus') return null;
    if (st.mapSrc != null && st.mapSrcSel === `${st.selected}|${st.selCable}`) return { kind: 'src', code: st.mapSrc };
    const sel = st.selected;
    const pos = parseModKey(sel);
    if (pos >= 0) return { kind: 'mod', pos };
    const b = parseBlockKey(sel);
    if (b && b.role !== ROLE.MODULE) return { kind: 'dst', key: sel, sound: b.role === ROLE.SOUND ? b.sound : undefined };
    const ci = /^c([0-9]+)$/.exec(sel || '');
    if (ci) return { kind: 'cable', i: Number(ci[1]) - 1 };
    return null;
  }
  const isOutOf = (code, pos) => isModuleSource(code) && sourcePosition(code) === pos;
  function inFocus(i, t) {
    if (!t) return true;
    const c = cableOf(i);
    if (t.kind === 'cable') return t.i === i;
    if (t.kind === 'refused') return verdictOf(i).code !== 0;
    if (t.kind === 'late') return isLate(i);
    if (t.kind === 'src') return c.src === t.code || c.via === t.code;
    if (t.kind === 'mod') return isOutOf(c.src, t.pos) || isOutOf(c.via, t.pos) || mm.unitKey(c.unit) === modKey(t.pos);
    const k = mm.unitKey(c.unit);
    if (k === t.key) return true;
    const b = k ? parseBlockKey(k) : null;
    return t.sound !== undefined && !!b && b.role === ROLE.INSERT && b.sound === t.sound;
  }
  function focusName(t) {
    if (!t) return '';
    if (t.kind === 'src') return srcName(t.code);
    if (t.kind === 'mod') { const b = ctx.blockOf(modKey(t.pos)); const k = b ? mm.kind(b.engine) : null; return `${t.pos + 1} ${k ? k.abbr : 'empty'}`; }
    if (t.kind === 'dst') return blockTag(t.key);
    if (t.kind === 'cable') return `cable ${t.i + 1}`;
    return t.kind === 'late' ? markWords('late') : 'refused';
  }

  // ---- the jacks ------------------------------------------------------------------
  const jackBtn = (cls, label, attrs = {}) => el('button', `ed-jack ${cls}`, { type: 'button', 'aria-label': label, ...attrs });
  function outJack(code, label, gate) {
    const j = jackBtn(`ed-jack-out${gate ? ' is-gate' : ''}`, `Start a cable from ${label}`, { 'data-src': String(code), 'data-fk': `mp:s${code}` });
    jacks.set(`s${code}`, j);
    return j;
  }
  function inJack(unit, dst, gate, label, poly) {
    const v = `${unit}:${dst}:${gate ? 1 : 0}`;
    const j = jackBtn(`ed-jack-in${gate ? ' is-gate' : ''}${poly ? ' is-poly' : ''}`, `${label}: a cable can end here`, { 'data-dst': v, 'data-fk': `mp:d${v}` });
    jacks.set(`d${v}`, j);
    return j;
  }
  const usedDst = () => {
    const s = new Set();
    for (const c of st.mirror.cables) if (!cableEmpty(c)) s.add(toValue(c));
    return s;
  };

  // ---- the sources --------------------------------------------------------------------
  function sourcesColumn() {
    const col = el('div', 'ed-map-col ed-map-srcs', { 'data-col': 'srcs', role: 'toolbar', 'aria-orientation': 'vertical', 'aria-label': 'Sources: outputs a cable can start from' });
    col.append(el('h3', 'ed-map-h ed-map-t', { text: 'Sources' }));
    const cables = st.mirror.cables.map((c, i) => [c, i]).filter(([c]) => !cableEmpty(c));
    const used = new Set(), viaOf = new Map();
    for (const [c, i] of cables) { used.add(c.src); if (c.via !== NONE) { used.add(c.via); viaOf.set(c.via, i); } }
    const row = (s) => {
      const r = el('div', `ed-map-row ed-map-src${used.has(s.id) ? ' is-used' : ' is-idle'}`, { 'data-srcrow': String(s.id) });
      const nm = el('span', 'ed-map-t ed-map-nm', { text: s.name });
      nm.addEventListener('click', () => focusSource(s.id));
      r.append(nm);
      if (viaOf.has(s.id)) r.append(el('span', 'ed-map-t ed-map-note', { text: `via, cable ${viaOf.get(s.id) + 1}` }));
      r.append(outJack(s.id, s.name, isGate(s.kind)));
      return r;
    };
    // The groups are the metadata's (1.2): the first is always open, the rest fold until asked for.
    const groups = mm.groupedSources();
    const [first, ...more] = groups;
    col.append(el('span', 'ed-map-g ed-map-t', { text: first ? first.title : 'Sources' }));
    for (const s of first ? first.list : []) col.append(row(s));
    for (const g of more) {
      const isOpen = open('mapSrcOpen').has(g.id);
      const shown = g.list.filter((s) => isOpen || used.has(s.id));
      const head = el('button', 'ed-map-more ed-map-btn', { type: 'button', 'aria-expanded': String(isOpen), 'data-fk': `mp:g${g.id}`,
        text: `${isOpen ? '▾' : '▸'} ${g.title} · ${g.list.length}`,
        onclick: () => { const o = open('mapSrcOpen'); if (o.has(g.id)) o.delete(g.id); else o.add(g.id); ctx.render(); } });
      col.append(head);
      for (const s of shown) col.append(row(s));
    }
    // A cable from a module that is gone has no jack to start from: it gets a stub, in words.
    const orphans = cables.filter(([c]) => !jacks.has(`s${c.src}`));
    if (orphans.length) col.append(el('span', 'ed-map-g ed-map-t', { text: 'No source' }));
    for (const [c, i] of orphans) {
      const r = el('div', 'ed-map-row ed-map-src is-used', { 'data-srcrow': `x${i}` }, [el('span', 'ed-map-t ed-map-nm', { text: `cable ${i + 1}: ${srcName(c.src)}` })]);
      const j = el('span', 'ed-jack ed-jack-out is-stub', { 'aria-hidden': 'true' });
      jacks.set(`xs${i}`, j);
      r.append(j);
      col.append(r);
    }
    return col;
  }
  function focusSource(code) {
    st.mapMode = 'focus';
    st.mapSrc = code;
    st.mapSrcSel = `${st.selected}|${st.selCable}`;
    ctx.render();
  }

  // ---- the rack -------------------------------------------------------------------------
  // "n more": the parameters of a block that have no cable yet, folded until asked for.
  function moreToggle(key, n, list) {
    const word = (on) => `${on ? '▾' : '▸'} ${n} more`;
    const isOpen = open('mapOpen').has(key);
    return el('button', 'ed-map-more ed-map-btn', { type: 'button', 'aria-expanded': String(isOpen), 'data-fk': `mp:o${key}`, text: word(isOpen),
      onclick: (e) => {
        const o = open('mapOpen');
        const now = !o.has(key);
        if (now) o.add(key); else o.delete(key);
        list.classList.toggle('is-open', now);
        e.currentTarget.setAttribute('aria-expanded', String(now));
        e.currentTarget.textContent = word(now);
        layout();
      } });
  }
  function moduleBlock(pos) {
    const key = modKey(pos);
    const blk = ctx.blockOf(key);
    const k = blk ? mm.kind(blk.engine) : null;
    if (!blk || !k) {
      return el('div', 'ed-map-mod is-empty', { 'data-block': key, 'data-pos': String(pos) }, [
        el('span', 'ed-map-t ed-map-nm', { text: `${pos + 1} · empty` }), pickerButton(key)]);
    }
    const unit = mm.unitCode(key);
    const e = meta.engine(blk.engine);
    const used = usedDst();
    const sel = st.selected === key;
    const box = el('div', `ed-map-mod${sel ? ' is-sel' : ''}`, { 'data-block': key, 'data-pos': String(pos) });
    const head = el('button', 'ed-map-mh ed-map-btn', { type: 'button', 'data-fk': `mp:m${pos}`, 'aria-current': sel ? 'true' : 'false', 'aria-label': `${pos + 1} ${k.abbr} ${k.name}. Select, and keep its cables bright`,
      onclick: () => { st.mapMode = 'focus'; st.mapSrc = null; ctx.select(key, { view: 'mod' }); } }, [
      el('span', 'ed-map-t ed-map-nm', { text: `${pos + 1} ${k.abbr}` }), ' ', el('span', 'ed-map-t ed-map-kind', { text: k.name })]);
    box.append(head);
    const body = el('div', 'ed-map-mb');
    const ins = el('div', 'ed-map-ins');
    const mid = el('div', 'ed-map-mid', {}, [el('canvas', 'ed-trace', { width: 120, height: 28, 'data-trace': String(pos), 'aria-hidden': 'true' })]);
    const outs = el('div', 'ed-map-outs');
    const rowIn = (dst, gate, name, poly) => ins.append(el('div', 'ed-map-row ed-map-in', {}, [inJack(unit, dst, gate, destName({ src: 1, via: NONE, unit, dst, flags: SLOT_ON | (gate ? GATE_DST : 0), amount: 1, offset: 0 }), poly),
      el('span', 'ed-map-t', { text: name })]));
    (k.gates || []).forEach((g, gi) => rowIn(gi, true, g.name, false));
    const shownP = e.params.filter((p) => hasFlag(p, 'input') || used.has(`${unit}:${p.uid}:0`));
    const moreP = e.params.filter((p) => hasFlag(p, 'mod') && !shownP.includes(p));
    for (const p of shownP) rowIn(p.uid, false, p.name, hasFlag(p, 'poly'));
    if (moreP.length) {
      const more = el('div', `ed-map-morelist${open('mapOpen').has(key) ? ' is-open' : ''}`, { 'data-more': key });
      ins.append(moreToggle(key, moreP.length, more));
      for (const p of moreP) more.append(el('div', 'ed-map-row ed-map-in', {}, [inJack(unit, p.uid, false, destName({ src: 1, via: NONE, unit, dst: p.uid, flags: SLOT_ON, amount: 1, offset: 0 }), hasFlag(p, 'poly')), el('span', 'ed-map-t', { text: p.name })]));
      ins.append(more);
    }
    (k.outs || []).forEach((o, port) => {
      const code = moduleSource(pos, port);
      outs.append(el('div', 'ed-map-row ed-map-out', {}, [el('span', 'ed-map-t', { text: o.name }), el('span', 'ed-live ed-map-val', { 'data-out': `${pos}:${port}`, text: '–' }),
        outJack(code, `${pos + 1} ${k.abbr} ${o.name}`, isGate(o.kind))]));
    });
    body.append(ins, mid, outs);
    box.append(body);
    return box;
  }
  function rackColumn() {
    const col = el('div', 'ed-map-col ed-map-rack', { 'data-col': 'rack', role: 'toolbar', 'aria-orientation': 'vertical', 'aria-label': 'Rack: modules, their inputs and outputs' });
    col.append(el('h3', 'ed-map-h ed-map-t', { text: 'Rack' }));
    for (let pos = 0; pos < mm.positions; ++pos) col.append(moduleBlock(pos));
    return col;
  }

  // ---- the destinations -----------------------------------------------------------------------
  function destGroup(key, title, sub, lvl) {
    const blk = ctx.blockOf(key);
    const e = blk ? meta.engine(blk.engine) : null;
    const unit = key === 'host' ? mm.unitCode('host') : mm.unitCode(key);
    if (!e && key !== 'host') return null;
    if (unit < 0) return null;
    const params = key === 'host' ? mm.host : e.params;
    const used = usedDst();
    const shown = params.filter((p) => used.has(`${unit}:${p.uid}:0`));
    const more = params.filter((p) => hasFlag(p, 'mod') && !shown.includes(p));
    const sel = st.selected === key;
    const box = el('div', `ed-map-grp${lvl ? ' is-nested' : ''}${sel ? ' is-sel' : ''}${key[0] === 's' && key.length === 2 ? ` ed-${key}` : ''}`, { 'data-block': key });
    const head = el('button', 'ed-map-gh ed-map-btn', { type: 'button', 'data-fk': `mp:g${key}`, 'aria-current': sel ? 'true' : 'false',
      'aria-label': `${title}${sub ? ` ${sub}` : ''}. Select, and keep its cables bright`,
      onclick: () => { st.mapMode = 'focus'; st.mapSrc = null; if (key === 'host') { st.selected = key; ctx.render(); } else ctx.select(key, { view: 'mod' }); } }, [
      el('span', 'ed-tag ed-map-tag', { text: title }), sub ? ' ' : null, el('span', 'ed-map-t ed-map-nm', { text: sub }),
    ]);
    box.append(head);
    const row = (p) => box.append(el('div', 'ed-map-row ed-map-in', {}, [
      inJack(unit, p.uid, false, destName({ src: 1, via: NONE, unit, dst: p.uid, flags: SLOT_ON, amount: 1, offset: 0 }), hasFlag(p, 'poly')),
      el('span', 'ed-map-t', { text: p.name }), hasFlag(p, 'poly') ? el('span', 'ed-poly', { role: 'img', 'aria-label': 'per voice', text: 'v' }) : null]));
    for (const p of shown) row(p);
    if (!shown.length) box.append(el('span', 'ed-map-t ed-map-note ed-map-none', { text: 'no cables' }));
    if (more.length) {
      const list = el('div', `ed-map-morelist${open('mapOpen').has(key) ? ' is-open' : ''}`, { 'data-more': key });
      box.append(moreToggle(key, more.length, list));
      for (const p of more) list.append(el('div', 'ed-map-row ed-map-in', {}, [
        inJack(unit, p.uid, false, destName({ src: 1, via: NONE, unit, dst: p.uid, flags: SLOT_ON, amount: 1, offset: 0 }), hasFlag(p, 'poly')),
        el('span', 'ed-map-t', { text: p.name }), hasFlag(p, 'poly') ? el('span', 'ed-poly', { role: 'img', 'aria-label': 'per voice', text: 'v' }) : null]));
      box.append(list);
    }
    return box;
  }
  function destinationsColumn() {
    const col = el('div', 'ed-map-col ed-map-dsts', { 'data-col': 'dsts', role: 'toolbar', 'aria-orientation': 'vertical', 'aria-label': 'Destinations: parameters a cable can end at' });
    col.append(el('h3', 'ed-map-h ed-map-t', { text: 'Destinations' }));
    const cables = st.mirror.cables.map((c, i) => [c, i]).filter(([c]) => !cableEmpty(c));
    const into = new Set(cables.map(([c]) => mm.unitKey(c.unit)));
    const all = open('mapOpen').has('*');
    const name = (key) => { const b = ctx.blockOf(key); return b ? (meta.engine(b.engine) || {}).name || b.engine : ''; };
    const quiet = [];
    for (let k = 0; k < SOUNDS; ++k) {
      const sk = blockKey(ROLE.SOUND, k);
      if (!ctx.blockOf(sk)) continue;
      const g = destGroup(sk, `S${k + 1}`, name(sk), 0);
      if (g) col.append(g);
      for (let j = 0; j < INSERTS; ++j) {
        const ik = blockKey(ROLE.INSERT, k, j);
        if (!ctx.blockOf(ik)) continue;
        if (into.has(ik) || all) { const x = destGroup(ik, `In${j + 1}`, name(ik), 1); if (x) col.append(x); } else quiet.push(ik);
      }
    }
    for (let j = 0; j < MASTERS; ++j) {
      const mk = blockKey(ROLE.MASTER, 0, j);
      if (!ctx.blockOf(mk)) continue;
      if (into.has(mk) || all) { const x = destGroup(mk, `M${j + 1}`, name(mk), 0); if (x) col.append(x); } else quiet.push(mk);
    }
    if (into.has('host') || all) { const x = destGroup('host', 'Host', 'the FM-1 itself', 0); if (x) col.append(x); } else quiet.push('host');
    if (quiet.length || all) {
      col.append(el('button', 'ed-map-more ed-map-btn', { type: 'button', 'aria-expanded': String(all), 'data-fk': 'mp:all',
        text: all ? '▾ Hide effects and the host with no cables' : `▸ ${quiet.length} effects and the host, no cables`,
        onclick: () => { const o = open('mapOpen'); if (o.has('*')) o.delete('*'); else o.add('*'); ctx.render(); } }));
    }
    // A cable whose destination is gone has no jack to end at: a stub, in words.
    const orphans = cables.filter(([c]) => !jacks.has(`d${toValue(c)}`));
    if (orphans.length) col.append(el('span', 'ed-map-g ed-map-t', { text: 'Not plugged in' }));
    for (const [c, i] of orphans) {
      const r = el('div', 'ed-map-row ed-map-in is-used', {}, [el('span', 'ed-jack ed-jack-in is-stub', { 'aria-hidden': 'true' }), el('span', 'ed-map-t', { text: `cable ${i + 1}: ${destName(c)}` })]);
      jacks.set(`xd${i}`, r.firstChild);
      col.append(r);
    }
    return col;
  }

  // ---- the view -------------------------------------------------------------------------------------
  function view() {
    jacks = new Map();
    geo = [];
    const wrap = el('section', 'ed-map-wrap', { 'aria-label': 'Cable map' });
    const cables = st.mirror.cables.map((c, i) => i).filter((i) => !cableEmpty(cableOf(i)));
    const refused = cables.filter((i) => verdictOf(i).code).length;
    const late = cables.filter((i) => isLate(i)).length;
    const t = focusTarget();
    const chip = (text, on, fn, extra = '') => el('button', `ed-fchip${on ? ' is-on' : ''}${extra}`, { type: 'button', 'aria-pressed': String(on), 'data-fk': `mp:f${text.slice(0, 8)}`, text, onclick: fn });
    const nIn = t ? cables.filter((i) => inFocus(i, t)).length : 0;
    const chips = el('div', 'ed-fchips', { role: 'group', 'aria-label': 'Which cables are bright' }, [
      chip(`All ${cables.length}`, !t, () => { st.mapMode = 'all'; ctx.render(); }),
      t && t.kind !== 'refused' && t.kind !== 'late' ? chip(`Focus: ${focusName(t)} · ${nIn}`, true, () => { st.mapMode = 'all'; ctx.render(); }) : null,
      !t && (st.selected && (parseModKey(st.selected) >= 0 || (parseBlockKey(st.selected) && st.selected !== 'host'))) ? chip(`Focus: ${blockTag(st.selected)}`, false, () => { st.mapMode = 'focus'; st.mapSrc = null; ctx.render(); }) : null,
      refused ? chip(`Refused · ${refused}`, !!t && t.kind === 'refused', () => { st.mapMode = t && t.kind === 'refused' ? 'all' : 'refused'; ctx.render(); }, ' is-refused') : null,
      late ? chip(`${markWords('late').replace(/^./, (c) => c.toUpperCase())} · ${late}`, !!t && t.kind === 'late', () => { st.mapMode = t && t.kind === 'late' ? 'all' : 'late'; ctx.render(); }, ' is-late') : null,
    ]);
    const legend = el('p', 'ed-legend ed-map-legend', {}, [el('span', 'ed-l-mod', { text: 'modulation' }), el('span', 'ed-l-gate', { text: 'gate or trigger' }), el('span', 'ed-l-voice', { text: `${markWords('voice')} (${markChar('voice', 'v')})` }), el('span', 'ed-l-late', { text: `${markWords('late')} (${markChar('late', '~')})` }), el('span', 'ed-l-refuse', { text: '✕ refused' })]);
    wrap.append(el('div', 'ed-map-head', {}, [chips, legend]));
    wrap.append(el('p', 'ed-map-hand', { 'aria-hidden': 'true' }));
    map = el('div', 'ed-map');
    svg = sv('svg', { class: 'ed-map-svg', 'aria-hidden': 'true', focusable: 'false' });
    pills = el('div', 'ed-map-pills', { 'aria-hidden': 'true' });
    cols = { srcs: null, rack: null, dsts: null };
    cols.rack = rackColumn();
    cols.dsts = destinationsColumn();
    cols.srcs = sourcesColumn();
    map.append(svg, pills, cols.srcs, cols.rack, cols.dsts);
    wrap.append(map, el('p', 'ed-note ed-map-how', {}, [
      'Start from either an output or an input: drag to the other end, or use Enter, arrows and Enter. Select a cable to drag either end. ',
      'F keeps the selected module, destination or source bright; Esc shows all. The table has every cable in words.']));
    for (const col of Object.values(cols)) rove(col);
    wire(map);
    if (obs) obs.disconnect();
    // Re-drawn a frame later: laying out changes the map's own padding, and a change made inside the
    // observer's callback is the loop WebKit reports as an error.
    let queued = false;
    obs = new ResizeObserver(() => { if (!queued) { queued = true; requestAnimationFrame(() => { queued = false; layout(); }); } });
    obs.observe(map);
    requestAnimationFrame(() => layout());
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => layout());
    return wrap;
  }
  // The hint line over the map says what is in hand.
  function say(text) { const p = map && map.parentNode && map.parentNode.querySelector('.ed-map-hand'); if (p) p.textContent = text; }

  // ---- keyboard: one tab stop per column, arrows inside ---------------------------------------
  function items(col) { return [...col.querySelectorAll('button')].filter((b) => visible(b) && !b.disabled); }
  function rove(col) {
    col.addEventListener('focusin', (e) => { const b = e.target.closest && e.target.closest('button'); if (b) { for (const x of col.querySelectorAll('button')) x.tabIndex = x === b ? 0 : -1; } });
    col.addEventListener('keydown', (e) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      const b = e.target.closest && e.target.closest('button');
      if (!b) return;
      const flat = patch ? patchTargets() : items(col);
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Home' || e.key === 'End') {
        const at = flat.indexOf(b);
        const to = e.key === 'Home' ? 0 : e.key === 'End' ? flat.length - 1 : at < 0 ? 0 : Math.max(0, Math.min(flat.length - 1, at + (e.key === 'ArrowDown' ? 1 : -1)));
        if (flat[to]) { e.preventDefault(); flat[to].focus(); }
      }
    });
  }
  // One tab stop per column: the button that has the keys, else the first one shown.
  function roveAll() {
    for (const col of Object.values(cols)) {
      const list = items(col);
      const cur = list.find((b) => b === document.activeElement) || list.find((b) => b.tabIndex === 0) || list[0];
      for (const b of col.querySelectorAll('button')) b.tabIndex = b === cur ? 0 : -1;
    }
  }
  const patchTargets = () => [...map.querySelectorAll(patch && patch.dst ? '.ed-jack-out' : '.ed-jack-in')].filter((b) => b.tagName === 'BUTTON' && visible(b));

  // ---- making a cable: by pointer or by keys ------------------------------------------------------
  function srcLabel(code) { return srcName(code); }
  function begin(code, jack, how, dst = null, slot = -1) {
    patch = { src: code, dst, slot, jack, how, over: null, verdicts: new Map() };
    map.classList.add('is-patching');
    jack.classList.add('is-hand');
    const label = dst ? jack.getAttribute('aria-label').replace(': a cable can end here', '') : srcLabel(code);
    const ends = dst ? 'outputs' : 'inputs';
    say(`${label} in hand. Drop it on an ${dst ? 'output' : 'input'}; Esc puts it back.`);
    ctx.say(`${label}: a cable is in hand. Arrow keys move between ${ends}, Enter drops it, Escape cancels.`);
    layout();
  }
  function end(drop, target) {
    const p = patch;
    patch = null;
    if (!map) return;
    map.classList.remove('is-patching');
    for (const x of map.querySelectorAll('.is-hand, .is-aim, .is-no, .is-ok')) x.classList.remove('is-hand', 'is-aim', 'is-no', 'is-ok');
    if (ghost) { ghost.remove(); ghost = null; }
    say('');
    if (p && drop && target) {
      const dst = p.dst || target.dataset.dst;
      const src = p.dst ? Number(target.dataset.src) : p.src;
      if (!dst || !Number.isFinite(src)) return;
      makeCable(src, dst, 25, p.slot);
    } else if (p && p.jack && p.jack.isConnected && p.how === 'key') p.jack.focus();
    layout();
  }
  // C's verdict for a cable from the one in hand to an input, asked when it is over it.
  async function aim(target) {
    if (!patch) return;
    const p = patch;
    for (const x of map.querySelectorAll('.is-aim, .is-no, .is-ok')) { x.classList.remove('is-aim', 'is-no', 'is-ok'); x.removeAttribute('title'); }
    p.over = target;
    if (!target) return;
    target.classList.add('is-aim');
    const dst = p.dst || target.dataset.dst;
    const src = p.dst ? Number(target.dataset.src) : p.src;
    const key = `${src}:${dst}`;
    let v = p.verdicts.get(key);
    if (!v) {
      v = await verdictFor(src, dst, p.slot);
      p.verdicts.set(key, v);
    }
    if (patch !== p || p.over !== target) return;
    target.classList.add(v.ok ? 'is-ok' : 'is-no');
    target.title = v.text;
    say(`${srcLabel(src)}: ${v.text}`);
    ctx.say(`${v.text}.`);
  }
  async function verdictFor(src, dst, slot = -1) {
    const free = slot >= 0 ? slot : st.mirror.cables.findIndex((c) => cableEmpty(c));
    if (free < 0) return { ok: false, text: verdictWords(6, { what: 'matrix', used: SLOTS, max: SLOTS }) };
    const rec = h.cableRecord(free, src, dst);
    const r = await preview([rec], false, true);
    if (!r) return { ok: true, text: 'Drop to patch' };
    const code = r.codes[0];
    if (code && code < 32) return { ok: false, code, text: verdictWords(code) };          // the edit itself is refused
    // From 32 up the cable is written but the planner leaves it out (C's code); else ask the rack as it would be.
    let v = code;
    if (!v && r.mod) v = decodeMod(r.mod).verdicts[free];
    if (!v) return { ok: true, text: 'Runs' };
    // The planner's own code, in the metadata's words, with the names it leaves to fill in.
    const [u, d, g] = dst.split(':').map(Number);
    const blk = ctx.blockOf(mm.unitKey(u));
    const p = blk && !g ? meta.param(blk.engine, d) : null;
    const to = h.destName({ src, via: NONE, unit: u, dst: d, flags: SLOT_ON | (g ? GATE_DST : 0), amount: 0, offset: 0 });
    return { ok: false, code: v, text: `${verdictWords(v, { from: srcName(src), to, param: p ? p.name : to })} (the cable is kept, and runs once this is put right)` };
  }
  function wire(root) {
    root.addEventListener('click', (e) => {
      const j = e.target.closest && e.target.closest('button.ed-jack');
      if (!j) return;
      if (patch) {
        if (patch.jack === j) { end(false); return; }
        if (patch.dst ? j.classList.contains('ed-jack-out') : j.classList.contains('ed-jack-in')) { end(true, j); return; }
        end(false);
      }
      const input = j.classList.contains('ed-jack-in');
      begin(input ? null : Number(j.dataset.src), j, e.detail === 0 ? 'key' : 'click', input ? j.dataset.dst : null);
      if (e.detail === 0) { const f = patchTargets()[0]; if (f) f.focus(); }
    });
    root.addEventListener('pointerdown', (e) => {
      const handle = e.target.closest && e.target.closest('.ed-cab-end');
      const j = e.target.closest && e.target.closest('button.ed-jack');
      if ((!j && !handle) || e.button !== 0) return;
      const start = { x: e.clientX, y: e.clientY };
      const slot = handle ? Number(handle.dataset.slot) : -1;
      const c = slot >= 0 ? cableOf(slot) : null;
      const input = handle ? handle.dataset.end === 'source' : j.classList.contains('ed-jack-in');
      const anchor = handle ? jacks.get(input ? `d${toValue(c)}` : `s${c.src}`) : j;
      if (!anchor || anchor.tagName !== 'BUTTON') return;
      let dragging = false;
      const targetAt = (ev) => {
        const t = document.elementFromPoint(ev.clientX, ev.clientY);
        return t && t.closest ? t.closest(input ? 'button.ed-jack-out' : 'button.ed-jack-in') : null;
      };
      const move = (ev) => {
        if (!dragging && Math.hypot(ev.clientX - start.x, ev.clientY - start.y) > 5) {
          dragging = true;
          if (patch) end(false);
          begin(input ? null : (c ? c.src : Number(j.dataset.src)), anchor, 'drag', input ? (c ? toValue(c) : j.dataset.dst) : null, slot);
        }
        if (!dragging || !patch) return;
        drawGhost(ev.clientX, ev.clientY, anchor);
        const to = targetAt(ev);
        if (to !== patch.over) aim(to);
      };
      const cancel = () => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        window.removeEventListener('pointercancel', cancel);
        if (dragging && patch) end(false);
      };
      const up = (ev) => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
        window.removeEventListener('pointercancel', cancel);
        if (dragging) {
          const to = targetAt(ev);
          end(!!to, to);
          const swallow = (c) => { c.stopPropagation(); c.preventDefault(); };
          window.addEventListener('click', swallow, { capture: true, once: true });
          setTimeout(() => window.removeEventListener('click', swallow, { capture: true }), 0);
        }
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
      window.addEventListener('pointercancel', cancel);
    });
    root.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && patch) { e.stopPropagation(); e.preventDefault(); end(false); return; }
      if (e.key === 'Escape' && st.mapMode !== 'all' && st.mapMode) { e.stopPropagation(); e.preventDefault(); st.mapMode = 'all'; ctx.render(); return; }
      if ((e.key === 'f' || e.key === 'F') && !e.altKey && !e.ctrlKey && !e.metaKey && !patch) {
        const j = e.target.closest && e.target.closest('button');
        if (!j) return;
        e.preventDefault();
        if (st.mapMode === 'focus') { st.mapMode = 'all'; ctx.render(); return; }
        if (j.dataset.src && !jackIsModule(j)) { focusSource(Number(j.dataset.src)); return; }
        st.mapMode = 'focus'; st.mapSrc = null;
        const blk = j.closest('[data-block]');
        if (blk && blk.dataset.block !== st.selected && blk.dataset.block !== 'host') ctx.select(blk.dataset.block, { view: 'mod' }); else ctx.render();
      }
    });
  }
  const jackIsModule = (j) => isModuleSource(Number(j.dataset.src));
  function drawGhost(x, y, from) {
    const B = frame();
    const r = from.getBoundingClientRect();
    const a = { x: r.left + r.width / 2 - B.left, y: r.top + r.height / 2 - B.top };
    const b = { x: x - B.left, y: y - B.top };
    if (!ghost || !ghost.isConnected) { ghost = sv('path', { class: 'ed-cab-ghost' }); svg.append(ghost); }
    const dx = Math.max(30, Math.abs(b.x - a.x) / 2);
    ghost.setAttribute('d', `M${a.x} ${a.y} C${a.x + dx} ${a.y} ${b.x - dx} ${b.y} ${b.x} ${b.y}`);
  }

  // ---- the geometry: jacks, lanes, cables and pills -----------------------------------------------------
  // The map's padding box: where the svg and the pills are drawn from.
  const frame = () => { const r = map.getBoundingClientRect(); return { left: r.left + map.clientLeft, top: r.top + map.clientTop, width: map.clientWidth, height: map.clientHeight }; };
  const colOf = (e) => { const c = e.closest('.ed-map-col'); return c ? c.dataset.col : ''; };
  function layout() {
    if (!map || !map.isConnected || !svg) return;
    const t = focusTarget();
    // Which cables have both ends, and which way each runs.
    const items = [];
    st.mirror.cables.forEach((c, i) => {
      if (cableEmpty(c)) return;
      const s = jacks.get(`s${c.src}`) || jacks.get(`xs${i}`);
      const d = jacks.get(`d${toValue(c)}`) || jacks.get(`xd${i}`);
      if (!s || !d || !visible(s) || !visible(d)) return;
      const sc = colOf(s), dc = colOf(d);
      items.push({ i, c, s, d, sc, dc, kind: sc === 'srcs' ? (dc === 'rack' ? 'A' : 'B') : dc === 'dsts' ? 'C' : 'D' });
    });
    const nB = items.filter((x) => x.kind === 'B').length;
    const top = 18 + nB * 9;
    map.style.paddingTop = `${top + 8}px`;
    const B = frame();
    const rel = (r) => ({ l: r.left - B.left, t: r.top - B.top, r: r.right - B.left, b: r.bottom - B.top });
    const colR = {};
    for (const k of Object.keys(cols)) colR[k] = rel(cols[k].getBoundingClientRect());
    const g1 = { l: colR.srcs.r, r: colR.rack.l }, g2 = { l: colR.rack.r, r: colR.dsts.l };
    const mods = [...cols.rack.querySelectorAll('.ed-map-mod')].map((m) => rel(m.getBoundingClientRect()));
    const ctr = (e) => { const r = e.getBoundingClientRect(); return { x: r.left + r.width / 2 - B.left, y: r.top + r.height / 2 - B.top }; };
    svg.setAttribute('width', B.width);
    svg.setAttribute('height', B.height);
    svg.setAttribute('viewBox', `0 0 ${B.width} ${B.height}`);
    svg.innerHTML = '';
    pills.innerHTML = '';
    geo = [];
    const lane = (g, k, n) => (n <= 1 ? (g.l + g.r) / 2 : g.l + 16 + (k * (g.r - g.l - 32)) / (n - 1));
    const laneUsers = items.filter((x) => x.kind === 'B' || x.kind === 'D');
    const gapUse = new Map();
    let kB = 0;
    for (const x of items) {
      x.p0 = ctr(x.s);
      x.p1 = ctr(x.d);
      if (x.kind === 'A' || x.kind === 'C') {
        const dx = Math.max(24, (x.p1.x - x.p0.x) * 0.5);
        const c1 = { x: x.p0.x + dx, y: x.p0.y }, c2 = { x: x.p1.x - dx, y: x.p1.y };
        x.poly = bezier(x.p0, c1, c2, x.p1);
        x.d_ = `M${x.p0.x} ${x.p0.y} C${c1.x} ${c1.y} ${c2.x} ${c2.y} ${x.p1.x} ${x.p1.y}`;
        continue;
      }
      const k = laneUsers.indexOf(x);
      const L1 = lane(g1, laneUsers.length - 1 - k, laneUsers.length), L2 = lane(g2, k, laneUsers.length);
      let pts;
      if (x.kind === 'B') {
        const chY = 10 + (kB++) * 9;
        pts = [x.p0, { x: L1, y: x.p0.y }, { x: L1, y: chY }, { x: L2, y: chY }, { x: L2, y: x.p1.y }, x.p1];
      } else {
        const q = Number(x.d.closest('.ed-map-mod').dataset.pos);
        const gi = q > 0 ? q - 1 : 0;           // the gap below block gi and above block gi + 1
        const lo = mods[gi], hi = mods[gi + 1];
        const gy = hi ? (lo.b + hi.t) / 2 : lo.b + 6;
        const n = gapUse.get(gi) || 0;
        gapUse.set(gi, n + 1);
        const y = gy + (n % 3 - 1) * 3;
        pts = [x.p0, { x: L2, y: x.p0.y }, { x: L2, y }, { x: L1, y }, { x: L1, y: x.p1.y }, x.p1];
      }
      x.pts = pts;
      x.poly = samples(pts);
      x.d_ = rounded(pts);
    }
    // Draw: dim cables first, then the lit, the selected last.
    const lit = (x) => inFocus(x.i, t);
    const sel = (x) => st.selCable === `c${x.i + 1}`;
    const order = [...items].sort((a, b) => (lit(a) - lit(b)) || (sel(a) - sel(b)));
    for (const x of order) {
      const c = x.c, ref = !!verdictOf(x.i).code;
      const cls = `ed-cab${!isModuleSource(c.src) && mm.sources.get(c.src) && isGate(mm.sources.get(c.src).kind) ? ' is-gate' : ''}${c.flags & GATE_DST ? ' is-gate' : ''}${ref ? ' is-refused' : ''}${sel(x) ? ' is-sel' : ''}${lit(x) ? '' : ' is-dim'}${!(c.flags & SLOT_ON) ? ' is-off' : ''}`;
      const g = sv('g', { class: cls, 'data-cable': x.i });
      if (c.flags & VOICE) g.append(sv('path', { d: x.d_, class: 'ed-cab-band' }));
      g.append(sv('path', { d: x.d_, class: 'ed-cab-line' }));
      const hitp = sv('path', { d: x.d_, class: 'ed-cab-hit' });
      hitp.addEventListener('click', () => { st.selCable = `c${x.i + 1}`; ctx.select(`c${x.i + 1}`, { view: 'mod' }); });
      g.append(hitp);
      if (ref) { const e = x.p1; g.append(sv('path', { d: `M${e.x - 18} ${e.y - 4} l8 8 M${e.x - 18} ${e.y + 4} l8 -8`, class: 'ed-cab-x' })); }
      if (sel(x)) {
        for (const [end, p, shift] of [['source', x.p0, 24], ['destination', x.p1, -24]]) {
          g.append(sv('circle', { class: 'ed-cab-end', cx: p.x + shift, cy: p.y, r: 7,
            'data-slot': x.i, 'data-end': end }));
        }
      }
      svg.append(g);
      geo.push(x);
    }
    // The jacks that carry a cable are lit.
    for (const j of map.querySelectorAll('.ed-jack.is-wired')) j.classList.remove('is-wired');
    for (const x of items) { x.s.classList.add('is-wired'); x.d.classList.add('is-wired'); }
    placePills(items, t, colR, B);
    roveAll();
  }

  // The amount pills: for the selected cable, the lit ones in focus, and the refused; each in a
  // clear place in a gutter or the band above the rack, never over a label, a block or another pill.
  function placePills(items, t, colR, B) {
    const want = items.filter((x) => st.selCable === `c${x.i + 1}` || (t && inFocus(x.i, t)) || verdictOf(x.i).code);
    want.sort((a, b) => (st.selCable === `c${b.i + 1}`) - (st.selCable === `c${a.i + 1}`));
    const blocks = Object.values(colR);
    const placed = [];
    const others = (x, lit) => items.filter((y) => y !== x && (lit === undefined || inFocus(y.i, t) === lit));
    const clearOf = (r, list) => list.every((y) => !y.poly.some((p) => inRect(p, r, 1)));
    for (const x of want) {
      const c = x.c, ref = !!verdictOf(x.i).code;
      const amt = pctOfQ14(c.amount);
      const p = el('div', `ed-map-pill${ref ? ' is-refused' : ''}${st.selCable === `c${x.i + 1}` ? ' is-sel' : ''}`, { 'data-cable': String(x.i) });
      p.append(...[(c.flags & VOICE) ? el('span', 'ed-pill-v', { text: markChar('voice', 'v') }) : null, isLate(x.i) ? el('span', 'ed-pill-l', { title: markWords('late'), text: markChar('late', '~') }) : null, ref ? el('span', 'ed-pill-r', { text: markChar('refused', '!') }) : null,
        el('span', 'ed-pill-a', { text: `${amt > 0 ? '+' : ''}${amt} %` }), el('span', 'ed-live ed-map-live', { 'data-dest': String(x.i), text: '' })].filter(Boolean));
      p.addEventListener('click', () => { st.selCable = `c${x.i + 1}`; ctx.select(`c${x.i + 1}`, { view: 'mod' }); });
      p.style.visibility = 'hidden';
      pills.append(p);
      const w = p.offsetWidth + 4, hh = p.offsetHeight + 4;
      const cand = [];
      for (const f of [0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82, 0.1, 0.9]) cand.push(x.poly[Math.min(x.poly.length - 1, Math.floor(f * (x.poly.length - 1)))]);
      for (let k = 0; k < x.poly.length; k += 3) cand.push(x.poly[k]);
      const rectAt = (q) => ({ l: q.x - w / 2, t: q.y - hh / 2, r: q.x + w / 2, b: q.y + hh / 2 });
      const ok = (r, level) => r.l >= 0 && r.t >= 0 && r.r <= B.width && r.b <= B.height && !blocks.some((b) => hit(r, b, 1)) && !placed.some((q) => hit(r, q, 2)) &&
        (level >= 2 || clearOf(r, others(x, level === 0 ? undefined : true)));
      let spot = null;
      const isSel = st.selCable === `c${x.i + 1}`;
      for (const level of isSel ? [0, 1, 2] : [0, 1]) { spot = cand.find((q) => ok(rectAt(q), level)); if (spot) break; }
      if (!spot) { p.remove(); continue; }
      const r = rectAt(spot);
      placed.push(r);
      p.style.left = `${spot.x}px`;
      p.style.top = `${spot.y}px`;
      p.style.visibility = '';
    }
  }

  // ---- the check: what the tests and a doubting eye ask ---------------------------------------------------------
  // Faults: a cable over a label or a block (away from its own jacks), two labels over each
  // other, a pill over a label, a block or a lit cable that is not its own, text cut off.
  function faults() {
    if (!map || !map.isConnected) return ['the map is not shown'];
    const out = [];
    const B = frame();
    const rel = (r) => ({ l: r.left - B.left, t: r.top - B.top, r: r.right - B.left, b: r.bottom - B.top });
    const texts = [...map.querySelectorAll('.ed-map-t')].filter(visible).map((e) => ({ e, r: rel(e.getBoundingClientRect()) }));
    const blocks = [...map.querySelectorAll('.ed-map-mod, .ed-map-grp')].filter(visible).map((e) => ({ e, r: rel(e.getBoundingClientRect()) }));
    const pillR = [...pills.children].map((e) => ({ e, r: rel(e.getBoundingClientRect()), i: Number(e.dataset.cable) }));
    for (const x of geo) {
      const own = [x.p0, x.p1];
      for (const p of x.poly) {
        if (own.some((q) => Math.hypot(q.x - p.x, q.y - p.y) < 20)) continue;
        const tx = texts.find((q) => inRect(p, q.r, 1));
        if (tx) { out.push(`cable ${x.i + 1} runs over the label "${tx.e.textContent.trim().slice(0, 24)}"`); break; }
        const bx = blocks.find((q) => inRect(p, q.r, 0));
        if (bx) { out.push(`cable ${x.i + 1} runs across a block (${bx.e.dataset.block})`); break; }
      }
    }
    for (let a = 0; a < texts.length; ++a) for (let b = a + 1; b < texts.length; ++b) {
      if (texts[a].e.contains(texts[b].e) || texts[b].e.contains(texts[a].e)) continue;
      if (hit(texts[a].r, texts[b].r, -1)) out.push(`labels overlap: "${texts[a].e.textContent.trim().slice(0, 20)}" and "${texts[b].e.textContent.trim().slice(0, 20)}"`);
    }
    for (const q of pillR) {
      const tx = texts.find((t) => hit(q.r, t.r, 0));
      if (tx) out.push(`pill of cable ${q.i + 1} is over the label "${tx.e.textContent.trim().slice(0, 20)}"`);
      if (blocks.some((b) => hit(q.r, b.r, 0))) out.push(`pill of cable ${q.i + 1} is over a block`);
      const mine = geo.find((g) => g.i === q.i);
      // The selected cable's pill may cover another cable when the map is crowded (declared; mockup 05's rule).
      for (const g of st.selCable === `c${q.i + 1}` ? [] : geo) {
        if (g === mine || !g.c || !map.querySelector(`.ed-cab[data-cable="${g.i}"]:not(.is-dim)`)) continue;
        if (g.poly.some((p) => inRect(p, q.r, 0))) { out.push(`pill of cable ${q.i + 1} is over cable ${g.i + 1}`); break; }
      }
      for (const o of pillR) if (o !== q && o.i > q.i && hit(q.r, o.r, 0)) out.push(`pills of cables ${q.i + 1} and ${o.i + 1} overlap`);
    }
    for (const t of texts) if (t.e.scrollWidth > t.e.clientWidth + 1 && getComputedStyle(t.e).overflow !== 'visible') out.push(`text cut off: "${t.e.textContent.trim().slice(0, 24)}"`);
    if (map.scrollWidth > map.clientWidth + 1) out.push('the map scrolls sideways');
    return out;
  }
  const stats = () => ({ cables: geo.length, pills: pills ? pills.children.length : 0, lit: geo.filter((x) => !svg.querySelector(`[data-cable="${x.i}"].is-dim`)).length, patching: !!patch });

  return { view, layout, faults, stats, verdictFor, cancel: () => { if (patch) end(false); } };
}
