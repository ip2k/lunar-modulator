// editor.js -- draws the mockups' controls from meta.js the way the editor would draw
// them from the metadata export (a slider row per FLOAT, segments or a list field per
// ENUM, LOG on the LOG law), plus scopes, curve icons and patch-bay cables; then checks
// the layout: text over text, text over a mark, a mark within 3 px of text on its line,
// a cable over text, clipped text, sideways scroll. Findings go to the console as
// "LAYOUT ..." lines, which render.mjs prints. MIT like the repository.

const NS = 'http://www.w3.org/2000/svg';
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
function svg(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}
function el(tag, cls, text, parent) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}

// ---- values, as C's fm1_look_value would give them (the editor asks the shadow module) ----
const MINUS = '−';
function num(v, dec) { const s = Math.abs(v).toFixed(dec); return (v < 0 && +s !== 0 ? MINUS : '') + s; }
function fmt(p, v) {
  const span = p.max - p.min;
  switch (p.unit) {
    case 'hz': return v >= 1000 ? [num(v / 1000, v >= 10000 ? 1 : 2), 'kHz'] : [num(v, 0), 'Hz'];
    case 'ms': return v >= 1000 ? [num(v / 1000, 2), 's'] : [num(v, v < 10 ? 1 : 0), 'ms'];
    case 'db': return [(v > 0 ? '+' : '') + num(v, 1), 'dB'];
    case 'semi': return [(v > 0 ? '+' : '') + num(v, 0), 'st'];
    case 'pct': return [(p.min < 0 && v > 0 ? '+' : '') + num(v, 0), '%'];
    default:
      if (span >= 10) return [num(v, 0), ''];
      return [(p.min < 0 && v > 0 ? '+' : '') + num(v, 2), ''];
  }
}
function lookup(kind, id, name) {
  const M = window.META;
  const src = kind === 'k' ? M.kinds[id] : M.engines[id];
  if (!src) throw new Error('no ' + kind + ' ' + id);
  const p = src.params.find((q) => q.n === name);
  if (!p) throw new Error('no param ' + name + ' in ' + id);
  return p;
}
const isLog = (p) => p.f.includes('log');
function pos(p, v) {
  if (isLog(p)) return Math.log(v / p.min) / Math.log(p.max / p.min);
  return (v - p.min) / (p.max - p.min);
}
const pc = (x) => (Math.min(1, Math.max(0, x)) * 100).toFixed(2) + '%';

// ---- a parameter row ------------------------------------------------------------------------
function row(r) {
  const d = r.dataset;
  const p = lookup(d.k ? 'k' : 'e', d.k || d.e, d.p);
  r.classList.add('row');
  r.innerHTML = '';
  const lab = el('div', 'lab', null, r);
  if (d.knob) el('span', 'kc', d.knob, lab);
  el('span', 'nm', d.label || p.n, lab);
  if (d.pill) el('span', 'pill', d.pill, lab);
  if (d.refused) el('span', 'pill r', '!' + d.refused, lab);
  if ('lane' in d) el('span', 'lane', null, lab);
  if (d.pill || d.mod) r.classList.add('modded');
  r.setAttribute('aria-label', p.n);
  if (p.t === 'enum') {
    const entries = p.e || [];
    const v = entries.includes(d.v) ? entries.indexOf(d.v) : +d.v;
    r.classList.add('wide');
    const n = p.max - p.min + 1;
    if (n > 4 && n <= 8 && d.list === undefined && !d.cols) r.classList.add('tall');
    if (n > 8 || d.list !== undefined) {
      const f = el('div', 'listf', null, r);
      el('span', 'v', entries[v] ?? String(v), f);
      el('span', 'place', `${v + 1}/${n}`, f);
      el('span', 'caret', '▾', f);
      r.setAttribute('role', 'combobox');
    } else {
      const cols = +(d.cols || (n <= 4 ? n : 4));
      const g = el('div', 'segs', null, r);
      g.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
      entries.slice(0, n).forEach((t, i) => el('span', i === v ? 'on' : '', t, g));
      r.setAttribute('role', 'radiogroup');
    }
    return;
  }
  const v = +d.v;
  const t = el('div', 'track', null, r);
  el('span', 'rail', null, t);
  const bip = p.min < 0 && p.max > 0;
  const a = bip ? pos(p, 0) : 0, b = pos(p, v);
  const f = el('span', 'fill', null, t);
  f.style.left = pc(Math.min(a, b)); f.style.width = pc(Math.abs(b - a));
  if (bip) el('span', 'zero', null, t).style.left = pc(pos(p, 0));
  if (isLog(p)) {
    for (const m of [1, 2, 5]) for (let dec = 1e-3; dec < 1e6; dec *= 10) {
      const x = m * dec; if (x <= p.min || x >= p.max) continue;
      el('span', 'tk', null, t).style.left = pc(pos(p, x));
    }
  }
  if (!bip && Math.abs(p.d - v) > 1e-9) el('span', 'def', null, t).style.left = pc(pos(p, p.d));
  if (d.mod) {
    const [lo, hi] = d.mod.split(',').map(Number);
    const br = el('span', 'bracket', null, t);
    br.style.left = pc(pos(p, lo)); br.style.width = pc(pos(p, hi) - pos(p, lo));
  }
  for (const x of (d.voices ? d.voices.split(',') : d.live ? [d.live] : []))
    el('span', 'live', null, t).style.left = pc(pos(p, +x));
  el('span', 'thumb', null, t).style.left = pc(b);
  const [txt, unit] = fmt(p, v);
  const val = el('div', 'val', null, r);
  el('span', null, txt, val);
  if (unit) el('span', 'u', unit, val);
  r.setAttribute('role', 'slider');
  r.setAttribute('aria-valuetext', txt + (unit ? ' ' + unit : ''));
}

// ---- scopes and small pictures --------------------------------------------------------------
function wave(kind, x, ph) {
  const t = ((x + ph) % 1 + 1) % 1;
  switch (kind) {
    case 'tri': return 1 - 4 * Math.abs(t - 0.5);
    case 'sine': return Math.sin(2 * Math.PI * t);
    case 'func': { const r = 0.4; return t < r ? -1 + 2 * Math.pow(t / r, 0.7) : 1 - 2 * Math.pow((t - r) / (1 - r), 1.6); }
    case 'rand': { const n = Math.floor(x * 9 + ph * 9); const a = Math.sin(n * 12.9898) * 43758.5453; const b = Math.sin((n + 1) * 12.9898) * 43758.5453; const f = (x * 9 + ph * 9) % 1; const s = f * f * (3 - 2 * f); return ((a - Math.floor(a)) * (1 - s) + (b - Math.floor(b)) * s) * 2 - 1; }
    default: return 0;
  }
}
function envAt(x, start, len) {
  const t = x - start; if (t < 0) return -1;
  if (t < 0.05) return -1 + 2 * (t / 0.05);
  const sus = -1 + 2 * 0.4;
  if (t < 0.25) return 1 - (1 - sus) * ((t - 0.05) / 0.2);
  if (t < len) return sus;
  const q = (t - len) / 0.3; return q >= 1 ? -1 : sus - (sus + 1) * q;
}
function scope(s) {
  const d = s.dataset, W = 200, H = 40;
  s.setAttribute('viewBox', `0 0 ${W} ${H}`); s.setAttribute('preserveAspectRatio', 'none');
  s.setAttribute('role', 'img'); s.setAttribute('aria-label', d.label || 'live output');
  const y = (v) => (H / 2 - v * (H / 2 - 5)).toFixed(2);
  svg('line', { x1: 0, y1: H / 2, x2: W, y2: H / 2, stroke: css('--border'), 'stroke-width': 1, 'vector-effect': 'non-scaling-stroke' }, s);
  const traces = [];
  if (d.wave === 'voices') (d.starts || '0.05,0.3,0.55').split(',').map(Number).forEach((st, i) => traces.push((x) => envAt(x, st, st + 0.35 + 0.05 * i)));
  else if (d.wave === 'gate') { const n = +(d.n || 8); traces.push((x) => ((x * n) % 1) < 0.18 ? 0.8 : -0.8); }
  else if (d.wave === 'idle') traces.push(() => -0.9);
  else traces.push((x) => wave(d.wave, x * (+d.cycles || 2), +(d.ph || 0)) * (+d.amp || 1));
  traces.forEach((f, i) => {
    let p = '';
    for (let k = 0; k <= 200; k++) { const x = k / 200; p += (k ? 'L' : 'M') + (x * W).toFixed(1) + ' ' + y(f(x)); }
    svg('path', { d: p, fill: 'none', stroke: css('--live'), 'stroke-width': d.wave === 'voices' ? 1.4 : 1.7, 'stroke-opacity': d.wave === 'voices' ? 0.55 + 0.15 * i : (d.dim ? 0.5 : 1), 'vector-effect': 'non-scaling-stroke' }, s);
  });
}
const CURVES = {
  lin: (x) => x, expo: (x) => x * x * x, log: (x) => 1 - Math.pow(1 - x, 3), s: (x) => x * x * (3 - 2 * x),
  sq: (x) => x * x, sqrt: (x) => Math.sqrt(x), step: (x) => Math.floor(x * 4) / 4, inv: (x) => 1 - x,
};
function curve(c) {
  const f = CURVES[c.dataset.curve]; const W = 26, H = 14;
  c.setAttribute('viewBox', `0 0 ${W} ${H}`); c.setAttribute('role', 'img'); c.setAttribute('aria-label', c.dataset.curve + ' curve');
  let p = '';
  for (let k = 0; k <= 26; k++) { const x = k / 26; p += (k ? 'L' : 'M') + (1 + x * (W - 2)).toFixed(1) + ' ' + (H - 1 - f(x) * (H - 2)).toFixed(1); }
  svg('path', { d: p, fill: 'none', stroke: c.dataset.c ? css(c.dataset.c) : css('--text'), 'stroke-width': 1.6, 'stroke-linecap': 'round' }, c);
}

// ---- cables ------------------------------------------------------------------------------------
const STYLE = {
  mod: { dash: '6 3.5', w: 1.8, c: '--mod' },
  voice: { dash: '6 3.5', w: 1.8, c: '--mod', band: true },
  gate: { dash: '0.1 4', w: 2.4, c: '--mod', cap: 'round' },
  refused: { dash: '6 3.5', w: 1.8, c: '--refuse', x: true },
  audio: { dash: '', w: 2.2, c: '--label' },
};
function rel(host, e) { const h = host.getBoundingClientRect(), r = e.getBoundingClientRect(); return { x: r.left - h.left, y: r.top - h.top, w: r.width, h: r.height }; }
function anchor(host, sel, side) {
  const e = document.querySelector(sel);
  if (!e) throw new Error('no element ' + sel);
  const r = rel(host, e);
  if (e.classList.contains('jack')) return [r.x + r.w / 2, r.y + r.h / 2];
  if (side === 't') return [r.x + r.w / 2, r.y];
  if (side === 'b') return [r.x + r.w / 2, r.y + r.h];
  return side === 'l' ? [r.x, r.y + r.h / 2] : [r.x + r.w, r.y + r.h / 2];
}
function boxesHit(a, b) { return a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h; }
function textBoxes(host) {
  const out = [];
  const walker = document.createTreeWalker(host, NodeFilter.SHOW_TEXT);
  const h = host.getBoundingClientRect();
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    if (!n.textContent.trim()) continue;
    const p = n.parentElement; if (!p || p.closest('.wire-layer') || p.closest('svg') || p.closest('.intent')) continue;
    const cs = getComputedStyle(p); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
    const r = document.createRange(); r.selectNodeContents(n);
    for (const b of r.getClientRects()) if (b.width > 0.5 && b.height > 0.5) out.push({ x: b.left - h.left, y: b.top - h.top, w: b.width, h: b.height, el: p });
  }
  return out;
}
function drawCables(hostSel, specs) {
  const host = document.querySelector(hostSel);
  host.classList.add('wire-host');
  const layer = svg('svg', { class: 'wire-layer', 'aria-hidden': 'true', width: host.scrollWidth, height: host.scrollHeight });
  host.prepend(layer);
  const defs = svg('defs', {}, layer);
  const markers = {};
  const marker = (colour) => {
    const id = 'arr' + Object.keys(markers).length + Math.random().toString(36).slice(2, 6);
    const m = svg('marker', { id, viewBox: '0 0 10 10', refX: 9, refY: 5, markerWidth: 9, markerHeight: 9, orient: 'auto-start-reverse', markerUnits: 'userSpaceOnUse' }, defs);
    svg('path', { d: 'M0 0 L10 5 L0 10 z', fill: colour }, m);
    return id;
  };
  const avoid = textBoxes(host);
  const drawn = [];
  for (const sp of specs) {
    const st = STYLE[sp.kind || 'mod'];
    const colour = css(sp.color || st.c);
    let [x0, y0] = anchor(host, sp.from, sp.fs || 'r');
    let [x3, y3] = anchor(host, sp.to, sp.ts || 'l');
    if (sp.ty === 'same') y3 = y0;
    const toJack = document.querySelector(sp.to).classList.contains('jack');
    if (toJack) x3 -= 9;
    const fd = sp.fd || 1, td = sp.td || -1;   // leaving rightwards, arriving from the left
    const k = sp.bend ?? Math.max(40, Math.abs(x3 - x0) * 0.45);
    const dpath = sp.route ? sp.route(x0, y0, x3, y3) : `M${x0} ${y0} C${x0 + fd * k} ${y0} ${x3 + td * k} ${y3} ${x3} ${y3}`;
    const g = svg('g', { 'data-cable': sp.id || '', opacity: sp.dim ? 0.4 : 1 }, layer);
    if (sp.sel) svg('path', { d: dpath, fill: 'none', stroke: css('--select'), 'stroke-opacity': 0.35, 'stroke-width': 9, 'stroke-linecap': 'round' }, g);
    if (st.band) svg('path', { d: dpath, fill: 'none', stroke: colour, 'stroke-opacity': 0.22, 'stroke-width': 8, 'stroke-linecap': 'round' }, g);
    const p = svg('path', { d: dpath, fill: 'none', stroke: colour, 'stroke-width': st.w, 'stroke-dasharray': st.dash, 'stroke-linecap': st.cap || 'butt' }, g);
    if (!st.x) p.setAttribute('marker-end', `url(#${markers[colour] || (markers[colour] = marker(colour))})`);
    else {
      const L = p.getTotalLength(), q = p.getPointAtLength(L - 1), s2 = 5;
      svg('path', { d: `M${q.x - s2} ${q.y - s2} L${q.x + s2} ${q.y + s2} M${q.x - s2} ${q.y + s2} L${q.x + s2} ${q.y - s2}`, stroke: colour, 'stroke-width': 2.2, 'stroke-linecap': 'round' }, g);
    }
    g.__path = p; g.__spec = sp; drawn.push(g);
  }
  // Pills go on after every path, so a pill avoids the cables as well as text and pills.
  const pillBoxes = [];
  const samples = drawn.map((g) => { const p = g.__path, L = p.getTotalLength(), pts = []; for (let s = 0; s <= L; s += 4) { const q = p.getPointAtLength(s); pts.push([q.x, q.y]); } return pts; });
  drawn.forEach((g, gi) => {
    const sp = g.__spec, p = g.__path;
    if (!sp.pill) return;
    const pill = el('div', 'cpill' + (sp.kind === 'refused' ? ' r' : '') + (sp.sel ? ' sel' : '') + (sp.dim ? ' dim' : ''));
    pill.innerHTML = sp.pill;
    host.appendChild(pill);
    const L = p.getTotalLength();
    const base = sp.t ?? 0.5;
    const tries = [0]; for (let k = 1; k <= 16; k++) tries.push(-0.035 * k, 0.035 * k);
    let ok = false;
    // First a place clear of every cable; failing that, one clear of the bright ones
    // (a dimmed cable may pass under a pill's opaque ground).
    for (const strict of [true, false]) {
      for (const dt of tries) {
        const t = base + dt; if (t < 0.1 || t > 0.9) continue;
        const q = p.getPointAtLength(L * t);
        pill.style.left = q.x + 'px'; pill.style.top = q.y + 'px';
        const b = rel(host, pill); const bb = { x: b.x - 3, y: b.y - 3, w: b.w + 6, h: b.h + 6 };
        if (pillBoxes.some((o) => boxesHit(o, bb)) || avoid.some((o) => boxesHit(o, bb))) continue;
        if (samples.some((pts, j) => j !== gi && (strict || !drawn[j].__spec.dim) && pts.some(([x, y]) => x > bb.x && x < bb.x + bb.w && y > bb.y && y < bb.y + bb.h))) continue;
        pillBoxes.push(bb); ok = true; g.__under = !strict; break;
      }
      if (ok) break;
    }
    if (!ok) console.log('LAYOUT pill-unplaced ' + (sp.id || sp.pill));
    g.__pill = pill;
  });
}

// ---- the layout check ------------------------------------------------------------------------------
const MARKS = '.thumb,.bracket,.live,.lane,.pill,.kc,.mk,.tag,.jack,.cpill,.led,.mm,.fd,.zero,.def,.tk,.dot,.sw,.amt .b,.rbar,.ram .bar,.lvb,.poly,.scope,.curve,.trace';
function describe(e) { return (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ').join('.') : e.tagName.toLowerCase()) + ' "' + e.textContent.trim().slice(0, 26) + '"'; }
function checkLayout() {
  const issues = [];
  const texts = textBoxes(document.body);
  for (let i = 0; i < texts.length; i++) for (let j = i + 1; j < texts.length; j++) {
    const a = texts[i], b = texts[j];
    if (a.el === b.el) continue;
    const ix = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x), iy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    if (ix > 1 && iy > 2) issues.push(`text over text: ${describe(a.el)} / ${describe(b.el)}`);
  }
  // text must stay inside its box (a panel, a block, a bar), with a pixel to spare
  for (const t of texts) {
    const box = t.el.closest('.panel, .blk, .appbar, .statusbar, .side, .cablein, .opt, .node, .chip, .btn, .val, .listf, .segs span, .mc, .mod-b, .dgrp, .from, .detail');
    if (!box) continue;
    const r = box.getBoundingClientRect(), bb = document.body.getBoundingClientRect();
    const x = r.left - bb.left, y = r.top - bb.top;
    if (t.x < x - 1 || t.y < y - 1 || t.x + t.w > x + r.width + 1 || t.y + t.h > y + r.height + 1)
      issues.push(`text out of its box: ${describe(t.el)} / ${box.className}`);
  }
  const hb = document.body.getBoundingClientRect();
  const marks = [...document.querySelectorAll(MARKS)].filter((m) => !m.closest('.intent')).map((m) => { const r = m.getBoundingClientRect(); return { el: m, x: r.left - hb.left, y: r.top - hb.top, w: r.width, h: r.height }; }).filter((m) => m.w > 0 && m.h > 0);
  for (const t of texts) for (const m of marks) {
    if (m.el.contains(t.el) || t.el.contains(m.el)) continue;
    const a = { x: t.x + 1, y: t.y + 2, w: t.w - 2, h: t.h - 4 };
    if (boxesHit(a, m)) { issues.push(`text over mark: ${describe(t.el)} / ${m.el.className.baseVal ?? m.el.className}`); continue; }
    const vert = a.y < m.y + m.h && m.y < a.y + a.h;
    const gap = Math.max(m.x - (t.x + t.w), t.x - (m.x + m.w));
    if (vert && gap >= 0 && gap < 3) issues.push(`mark hugs text (${gap.toFixed(1)} px): ${describe(t.el)} / ${m.el.className.baseVal ?? m.el.className}`);
  }
  for (const layer of document.querySelectorAll('svg.wire-layer')) {
    const host = layer.parentElement; const boxes = textBoxes(host);
    for (const g of layer.querySelectorAll('g')) {
      if (!g.__path) continue;
      const p = g.__path, L = p.getTotalLength(), pill = g.__pill, hit = new Set();
      for (let s = 2; s < L - 2; s += 3) {
        const q = p.getPointAtLength(s);
        for (const b of boxes) {
          if (pill && (b.el === pill || pill.contains(b.el))) continue;
          const under = b.el.closest('.cpill'); if (under && g.__spec.dim && [...layer.querySelectorAll('g')].some((o) => o.__pill === under && o.__under)) continue;
          if (q.x > b.x + 0.5 && q.x < b.x + b.w - 0.5 && q.y > b.y + 1 && q.y < b.y + b.h - 1) hit.add(b.el);
        }
      }
      for (const e of hit) issues.push(`cable over text: ${g.__spec.id || g.__spec.pill} / ${describe(e)}`);
    }
  }
  for (const e of document.querySelectorAll('body *')) {
    if (e.closest('svg') || !e.textContent.trim() || e.children.length > 3) continue;
    const cs = getComputedStyle(e);
    if (cs.overflow === 'visible' && cs.overflowX === 'visible' && cs.textOverflow !== 'ellipsis') continue;
    if (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 2) issues.push(`clipped: ${describe(e)} (${e.scrollWidth}x${e.scrollHeight} in ${e.clientWidth}x${e.clientHeight})`);
  }
  if (document.documentElement.scrollWidth > innerWidth + 1) issues.push(`page scrolls sideways: ${document.documentElement.scrollWidth} > ${innerWidth}`);
  for (const i of [...new Set(issues)]) console.log('LAYOUT ' + i);
  console.log(`LAYOUT-SUMMARY ${new Set(issues).size} issue(s) at ${innerWidth}px, ${texts.length} text boxes, ${marks.length} marks`);
}

function cables() {
  document.querySelectorAll('svg.wire-layer, .cpill').forEach((e) => e.remove());
  if (window.CABLES) for (const [host, specs] of Object.entries(window.CABLES())) drawCables(host, specs);
}
function build() {
  document.querySelectorAll('[data-p]').forEach(row);
  document.querySelectorAll('svg.scope[data-wave]').forEach(scope);
  document.querySelectorAll('svg[data-curve]').forEach(curve);
}
window.MOCK = { relayout() { if (window.AFTER) window.AFTER(); cables(); checkLayout(); return 1; } };
document.addEventListener('DOMContentLoaded', async () => {
  await document.fonts.ready;
  build();
  if (window.AFTER) window.AFTER();
  cables();
  checkLayout();
  document.documentElement.dataset.ready = '1';
});
