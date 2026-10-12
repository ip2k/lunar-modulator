// MIDI learn, with browser defaults and versioned project metadata.
// MIT licence, like the rest of Lunar Modulator.
export const STORAGE_KEY = 'lunar.midi-map.v1';
export const MAX_BINDINGS = 64;
const bytes = (s) => new TextEncoder().encode(s).length;
export function midiMessage(source, data) {
  const [status, number, value = 0] = data;
  const type = status & 0xf0;
  if (!Number.isInteger(status) || status < 0x80 || status >= 0xf0 ||
      !Number.isInteger(number) || number < 0 || number > 127 || !Number.isInteger(value) || value < 0 || value > 127) return null;
  if (![0x80, 0x90, 0xb0].includes(type)) return null;
  return { source: String(source), channel: status & 15, kind: type === 0xb0 ? 'cc' : 'note', number,
    value, down: type === 0xb0 ? value >= 64 : type === 0x90 && value > 0 };
}
const address = (m) => JSON.stringify([m.source, m.channel, m.kind, m.number]);
const valid = (b) => b && typeof b.target === 'string' && b.target.length > 0 && bytes(b.target) <= 192 && !b.target.includes('\0') &&
  /^[\x20-\x7e]+$/.test(b.target) &&
  typeof b.source === 'string' && b.source.length > 0 && bytes(b.source) <= 128 && !b.source.includes('\0') && Number.isInteger(b.channel) && b.channel >= 0 && b.channel < 16 &&
  ['note', 'cc'].includes(b.kind) && Number.isInteger(b.number) && b.number >= 0 && b.number < 128;
export function validMidiMap(saved) {
  if (saved?.version !== 1 || !Array.isArray(saved.bindings) || saved.bindings.length > MAX_BINDINGS || !saved.bindings.every(valid)) return false;
  const targets = new Set(), sources = new Set(), strings = new Set();
  for (const b of saved.bindings) {
    if (targets.has(b.target) || sources.has(address(b))) return false;
    targets.add(b.target); sources.add(address(b)); strings.add(b.target); strings.add(b.source);
  }
  return [...strings].reduce((n, s) => n + bytes(s) + 1, 0) <= 4096;
}

// This core has no DOM or Web MIDI dependency; tests use the same dispatch path.
export class MidiMap {
  constructor({ storage = null, changed = () => {}, edited = () => {}, blocked = () => false, modeChanged = () => {} } = {}) {
    this.storage = storage; this.changed = changed; this.blocked = blocked;
    this.edited = edited; this.modeChanged = modeChanged;
    this.targets = new Map(); this.bindings = new Map(); this.held = new Map(); this.edges = new Map();
    this.learning = false; this.selected = null; this.error = '';
    try {
      const saved = JSON.parse(storage?.getItem(STORAGE_KEY) || 'null');
      if (validMidiMap(saved)) for (const b of saved.bindings) {
        for (const [key, old] of this.bindings) if (old.target === b.target) this.bindings.delete(key);
        this.bindings.set(address(b), { ...b });
      }
    } catch { this.error = 'Saved MIDI assignments could not be read.'; }
  }
  register(id, target) { this.targets.set(id, target); }
  release(source = null) {
    for (const [key, h] of this.held) if (source === null || h.source === source) { this.held.delete(key); h.release(); }
    for (const [key, edge] of this.edges) if (source === null || edge.source === source) this.edges.delete(key);
  }
  learn(on) { this.release(); this.modeChanged(); this.learning = !!on; this.selected = null; this.changed(); }
  select(id) { if (this.targets.has(id)) { this.selected = id; this.changed(); } }
  clear(id, edited = true) {
    this.release();
    for (const [key, b] of this.bindings) if (b.target === id) this.bindings.delete(key);
    this.save(); if (edited) this.edited();
  }
  export() { return { version: 1, bindings: [...this.bindings.values()].map((b) => ({ ...b })) }; }
  import(saved) {
    if (saved && !validMidiMap(saved)) { this.error = 'Project MIDI assignments are invalid or exceed the controller mapping limits.'; this.changed(); return false; }
    this.release(); this.bindings.clear(); this.selected = null;
    if (saved) for (const b of saved.bindings) {
      for (const [key, old] of this.bindings) if (old.target === b.target) this.bindings.delete(key);
      this.bindings.set(address(b), { source: b.source, channel: b.channel, kind: b.kind, number: b.number, target: b.target });
    }
    this.save();
    return true;
  }
  save() {
    try { this.storage?.setItem(STORAGE_KEY, JSON.stringify({ version: 1, bindings: [...this.bindings.values()] })); this.error = ''; }
    catch { this.error = 'MIDI assignments work for this visit, but browser storage could not save them.'; }
    this.changed();
  }
  handle(source, data) {
    const m = midiMessage(source, data);
    if (this.learning) {
      if (m && (m.kind === 'cc' || m.down) && this.selected) {
        const binding = { source: m.source, channel: m.channel, kind: m.kind, number: m.number, target: this.selected };
        const bindings = [...this.bindings.values()].filter((b) => b.target !== this.selected && address(b) !== address(m)).concat(binding);
        if (!validMidiMap({ version: 1, bindings })) {
          this.error = `Assignments allow ${MAX_BINDINGS} controls and 4 KiB of unique IDs (target 192 bytes, input 128 bytes).`; this.changed(); return true;
        }
        this.clear(this.selected, false);
        this.bindings.set(address(m), binding);
        this.edges.set(address(m), { source: m.source, value: m.value, down: m.down });
        this.selected = null;
        this.save(); this.edited();
      }
      return true; // Every message is consumed in learn mode, even pitch bend.
    }
    if (!m) return false;
    const key = address(m), b = this.bindings.get(key);
    if (!b) return false;
    const held = this.held.get(key);
    if (!m.down && held) { this.held.delete(key); held.release(); }
    const t = this.targets.get(b.target);
    const previous = this.edges.get(key);
    this.edges.set(key, { source: m.source, value: m.value, down: m.down });
    if (!t || this.blocked() || t.available?.() === false) { if (held && m.down) { this.held.delete(key); held.release(); } return true; }
    if (t.kind === 'relative') {
      if (m.kind === 'cc') { if (previous && m.value !== previous.value) t.turn(m.value - previous.value); }
      else if (m.down && !previous?.down) t.turn(1);
    } else if (t.kind === 'value') {
      if (m.kind === 'cc' || m.down) t.value(m.value / 127);
    } else if (m.down && !previous?.down) {
      const release = t.press(m.value);
      // A layout/mode button can release other held actions synchronously.
      // Keep its own edge so a stream of high CC packets still clicks once.
      this.edges.set(key, { source: m.source, value: m.value, down: m.down });
      if (typeof release === 'function') this.held.set(key, { source: m.source, release });
    }
    return true;
  }
}

const SELECTOR = 'button, select, input[type=range], input[type=number], input[type=checkbox], input[type=radio], summary, [role=slider], [role=button], [data-midi-id], [data-key], [data-button], [data-encoder], [data-master], .power';
const CONTEXT = ['data-block', 'data-uid', 'data-midi-context', 'data-mixer-track', 'data-track', 'data-scene',
  'data-song-entry', 'data-note', 'data-step', 'data-automation-lane', 'data-automation-step', 'data-live-track', 'data-live-scene',
  'data-preview-track', 'data-preview-scene', 'data-progress-track', 'data-progress-scene', 'data-sound-fader', 'data-inspector', 'data-layout', 'data-view', 'data-testid'];
const visible = (e) => e.isConnected && !e.disabled && !e.readOnly && e.getAttribute('aria-disabled') !== 'true' &&
  !e.closest('[hidden], [inert]') && e.getClientRects().length > 0;
const label = (e) => e.getAttribute('aria-label') || e.title ||
  (e.getAttribute('aria-labelledby') || '').split(' ').map((id) => document.getElementById(id)?.textContent || '').join(' ').trim() ||
  e.labels?.[0]?.textContent || e.textContent.trim().slice(0, 80) || e.id || 'Control';

// Semantic attributes identify controls across redraws; generated ed-* IDs are
// intentionally ignored. Within a semantic row, class + ordinal distinguishes
// the individual segment/tool buttons, independent of their changing caption.
function boundedId(raw) {
  const id = raw.replace(/[^\x20-\x7e]/gu, (char) => encodeURIComponent(char));
  if (bytes(id) <= 192) return id;
  let hash = 2166136261;
  for (const char of id) hash = Math.imul(hash ^ char.charCodeAt(0), 16777619) >>> 0;
  return `${id.slice(0, 70)}:h${hash.toString(16)}`;
}
export function targetId(e) {
  if (e.dataset.midiId) return boundedId(e.dataset.midiId);
  if (e.dataset.fk) return boundedId(`editor:control:${e.dataset.fk}`);
  if (e.id && !/^ed-.*-\d+$/.test(e.id)) return boundedId(`ui:${e.id}`);
  const parts = [], scope = e.closest('.ed, #panel, main, header') || document.body;
  for (let p = e; p && p !== scope.parentElement; p = p.parentElement) {
    const attrs = CONTEXT.filter((a) => p.hasAttribute(a)).map((a) => `${a.slice(5)}=${p.getAttribute(a)}`);
    if (attrs.length) parts.unshift(attrs.join('&'));
    if (p === scope) break;
  }
  const anchor = e.closest(CONTEXT.map((a) => `[${a}]`).join(',')) || scope;
  const cls = [...e.classList].filter((c) => !/^(is-|has-|down$|active$)/.test(c)).join('.');
  const peers = [...anchor.querySelectorAll(SELECTOR)].filter((p) => p.tagName === e.tagName &&
    [...p.classList].filter((c) => !/^(is-|has-|down$|active$)/.test(c)).join('.') === cls);
  const semantic = parts.length ? `${e.tagName}.${cls}:${Math.max(0, peers.indexOf(e))}` :
    `${e.tagName}:${e.getAttribute('aria-label') || e.textContent.trim().slice(0, 100)}:${Math.max(0, peers.indexOf(e))}`;
  return boundedId(`${scope.id || scope.classList[0] || 'page'}/${parts.join('/')}/${semantic}`);
}

export function nativeTarget(e) {
  const available = () => visible(e);
  if (e.tagName === 'SELECT') return { kind: 'value', available, value: (u) => {
    const options = [...e.options].filter((o) => !o.disabled && !o.hidden);
    if (!options.length) return;
    e.value = options[Math.min(options.length - 1, Math.floor(u * options.length))].value;
    e.dispatchEvent(new Event('change', { bubbles: true }));
  } };
  if (e.tagName === 'INPUT' && ['range', 'number'].includes(e.type)) return { kind: 'value', available, value: (u) => {
    const min = Number(e.min || 0), max = Number(e.max || (e.type === 'range' ? 100 : 127));
    const step = e.step === 'any' ? 0 : Number(e.step || 1);
    let v = min + u * (max - min);
    if (step > 0) v = min + Math.round((v - min) / step) * step;
    e.value = String(Math.max(min, Math.min(max, v)));
    e.dispatchEvent(new Event('input', { bubbles: true }));
    e.dispatchEvent(new Event('change', { bubbles: true }));
  } };
  // Custom sliders require an explicit adapter, rather than a cosmetic ARIA edit.
  if (e.getAttribute('role') === 'slider') return null;
  return { kind: 'button', available, press: () => {
    if (e.tagName === 'SUMMARY') e.parentElement.open = !e.parentElement.open;
    else e.click();
  } };
}

export function createMidiLearn({ header, storage = { getItem: (key) => window.localStorage.getItem(key), setItem: (key, value) => window.localStorage.setItem(key, value) }, connect = () => {}, modeChanged = () => {}, edited = () => {} }) {
  const button = document.createElement('button');
  button.type = 'button'; button.id = 'midi-learn'; button.className = 'midi-learn-toggle';
  button.setAttribute('aria-label', 'MIDI learn'); button.setAttribute('aria-pressed', 'false'); button.title = 'MIDI learn: assign a controller to a control';
  // Original piano glyph, constructed here; no manufacturer art.
  button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2" y="5" width="20" height="14" rx="2" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M7 6v12m5-12v12m5-12v12" fill="none" stroke="currentColor"/><path d="M5 5h3v8H5zm5 0h3v8h-3zm7 0h3v8h-3z" fill="currentColor"/></svg>';
  header.append(button);
  const overlay = document.createElement('div'); overlay.className = 'midi-learn-overlay'; overlay.hidden = true;
  const help = document.createElement('aside'); help.className = 'midi-learn-help';
  const message = document.createElement('p'); message.setAttribute('role', 'status');
  const connectButton = document.createElement('button'); connectButton.type = 'button'; connectButton.textContent = 'Connect MIDI'; connectButton.onclick = connect;
  const done = document.createElement('button'); done.type = 'button'; done.textContent = 'Done'; done.onclick = () => map.learn(false);
  const assignments = document.createElement('details'); const summary = document.createElement('summary'); summary.textContent = 'Saved assignments'; assignments.append(summary);
  const list = document.createElement('div'); assignments.append(list);
  help.append(message, connectButton, done, assignments); overlay.append(help); document.body.append(overlay);
  const explicit = new WeakMap(), elements = new Map();
  let frame = 0;
  const schedule = () => { if (!frame) frame = requestAnimationFrame(() => { frame = 0; refresh(); }); };
  const map = new MidiMap({ storage, changed: schedule, edited, modeChanged, blocked: () => !!document.querySelector('dialog[open]') ||
    !!document.activeElement?.matches('textarea, input:not([type=range]):not([type=checkbox]):not([type=radio]), [contenteditable]:not([contenteditable=false])') });
  function register(e, id, adapter) { e.dataset.midiId = id; explicit.set(e, adapter); schedule(); }
  function refresh() {
    map.targets.clear(); elements.clear();
    for (const e of document.querySelectorAll(SELECTOR)) {
      if (overlay.contains(e) || e === button) continue;
      const adapter = explicit.get(e) || nativeTarget(e);
      if (!adapter) continue;
      const id = targetId(e);
      // The same parameter may appear in Flow and Sound. The visible instance
      // wins so redraw/layout changes preserve the logical parameter binding.
      if (!elements.has(id) || visible(e)) { elements.set(id, e); map.register(id, adapter); }
    }
    button.setAttribute('aria-pressed', String(map.learning)); overlay.hidden = !map.learning;
    document.body.classList.toggle('midi-learning', map.learning);
    for (const e of overlay.querySelectorAll('.midi-learn-target, .midi-learn-badge')) e.remove();
    if (!map.learning) return;
    const layout = document.getElementById('layout-switch');
    help.style.top = `${Math.max(12, header.getBoundingClientRect().bottom + 12, (layout?.getBoundingClientRect().bottom || 0) + 12)}px`;
    const selected = elements.get(map.selected);
    message.textContent = map.error || (!navigator.requestMIDIAccess ? 'Web MIDI is unavailable in this browser. You can inspect or clear saved assignments.' :
      selected ? `${label(selected)}: press a controller note or move a CC.` : 'Choose a highlighted control, then press a note or move a CC. MIDI is silent while learning.');
    connectButton.disabled = !navigator.requestMIDIAccess;
    list.replaceChildren();
    const occupied = [help.getBoundingClientRect(), ...[...elements.values()].filter(visible).map((e) => e.getBoundingClientRect())];
    const bindingFor = new Map([...map.bindings.values()].map((b) => [b.target, b]));
    for (const [id, e] of elements) {
      if (!visible(e)) continue;
      const r = e.getBoundingClientRect();
      const mark = document.createElement('div'); mark.className = `midi-learn-target${id === map.selected ? ' is-selected' : ''}`;
      Object.assign(mark.style, { left: `${r.left}px`, top: `${r.top}px`, width: `${r.width}px`, height: `${r.height}px` });
      overlay.append(mark);
      const b = bindingFor.get(id);
      if (!b) continue;
      const badge = document.createElement('span'); badge.className = 'midi-learn-badge';
      const name = `${b.kind === 'cc' ? 'CC' : 'N'}${b.number} · ch${b.channel + 1}`;
      badge.append(document.createTextNode(name));
      const clear = document.createElement('button'); clear.type = 'button'; clear.textContent = '×'; clear.setAttribute('aria-label', `Clear MIDI assignment for ${label(e)}`);
      clear.onclick = () => map.clear(id); badge.append(clear); overlay.append(badge);
      // Collision-free badges are placed beside the control, with breathing room.
      const size = badge.getBoundingClientRect(); const x = Math.max(6, Math.min(innerWidth - size.width - 6, r.right + 6));
      let y = Math.max(6, Math.min(innerHeight - size.height - 6, r.top));
      for (let n = 0; n < 100 && occupied.some((o) => x < o.right + 4 && x + size.width + 4 > o.left && y < o.bottom + 4 && y + size.height + 4 > o.top); n++) y += size.height + 6;
      if (y + size.height > innerHeight - 6) { badge.remove(); continue; } // Still available in Saved assignments.
      Object.assign(badge.style, { left: `${x}px`, top: `${y}px` }); occupied.push({ left: x, right: x + size.width, top: y, bottom: y + size.height });
    }
    for (const b of map.bindings.values()) {
      const row = document.createElement('div'); row.className = 'midi-learn-assignment';
      const e = elements.get(b.target);
      row.append(document.createTextNode(`${e ? label(e) : b.target}: ${b.kind.toUpperCase()} ${b.number}, channel ${b.channel + 1}, input ${b.source}`));
      const clear = document.createElement('button'); clear.type = 'button'; clear.textContent = '×'; clear.setAttribute('aria-label', `Clear ${b.target}`); clear.onclick = () => map.clear(b.target); row.append(clear); list.append(row);
    }
  }
  button.onclick = () => { map.learn(!map.learning); };
  const capture = (event) => {
    if (!map.learning || event.target.closest('.midi-learn-overlay, #midi-learn')) return;
    const e = event.target.closest(SELECTOR);
    if (!e || !visible(e) || !map.targets.has(targetId(e))) return;
    event.preventDefault(); event.stopImmediatePropagation();
    if (event.type === 'pointerdown' || event.type === 'click') map.select(targetId(e));
  };
  for (const type of ['pointerdown', 'click', 'wheel']) document.addEventListener(type, capture, { capture: true, passive: false });
  document.addEventListener('keydown', (e) => {
    if (!map.learning || e.target.closest('.midi-learn-overlay, #midi-learn') || e.metaKey || e.ctrlKey || e.altKey || e.key === 'Tab') return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); map.learn(false); return; }
    if (e.target.matches('input, textarea, [contenteditable]')) return;
    e.preventDefault(); e.stopImmediatePropagation();
    const target = e.target.closest(SELECTOR);
    if (target && ['Enter', ' '].includes(e.key) && visible(target)) map.select(targetId(target));
  }, true);
  window.addEventListener('blur', () => map.release());
  document.addEventListener('visibilitychange', () => { if (document.hidden) map.release(); });
  window.addEventListener('fm1-power', () => map.release());
  window.addEventListener('fm1-midi-release', () => map.release());
  for (const type of ['resize', 'scroll']) window.addEventListener(type, schedule, true);
  new MutationObserver((records) => { if (records.some((r) => !overlay.contains(r.target))) schedule(); }).observe(document.body,
    { subtree: true, childList: true, attributes: true, attributeFilter: ['hidden', 'disabled', 'aria-disabled', 'data-layout'] });
  refresh();
  return { map, register, refresh, handle: (source, data) => map.handle(source, data), release: (source) => map.release(source) };
}
