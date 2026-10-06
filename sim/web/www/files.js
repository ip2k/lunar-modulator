// files.js -- the virtual FM-1's files (stage W1, notes/2026-10-06-state-files.md
// §12): Open… and drop, Save… downloads, SAVE on the panel, browser storage
// (IndexedDB: saved projects, a whole-project autosave and Recent), launch
// links (?load= and #lunar=, with the into/view/hl/play/entry hints and an
// arrival card), Copy link, and the ?embed=1 postMessage API for the guide.
//
// The audio thread sees only the binary container (worklet.js). Everything
// that reads or writes JSON, and pass 1 of every load, runs in the shadow
// Worker (shadow.worker.js), a second instance of the module that mirrors
// the live project first, so its answer is the firmware's own: the C reader
// and loader judge every file, and every refusal's words are the module's
// (memory only ever as a percent of the FM-1's budget). JSON.parse here
// reads only what C wrote, or a file's title for its card.
//
// Nothing is sent to any device, and no file or message can turn MIDI out
// on, fetch a URL outside the allowlist, or change a setting.
// MIT licence, like the rest of this repository.

const KIND = { project: 1, sound: 2, fx: 3, mods: 4, clip: 5, settings: 6, set: 7 };
const KIND_NAME = Object.fromEntries(Object.entries(KIND).map(([k, v]) => [v, k]));
const KIND_WORD = { project: 'project', sound: 'sound', fx: 'effects', mods: 'mod rack', clip: 'clip',
  settings: 'settings', set: 'set' };
const FLAG_WITHOUT = 1, FLAG_REPLACE = 2, FLAG_QUIET = 4;
const TEXT_CAP = 262144;          // the module's text buffer (fm1w_text_cap)
const SYX_CAP = 65536;            // FM1_APP_DX7_FILE_MAX
const LINK_CAP = 32768;           // #lunar=: characters of base64url (ST13)
const RECENT = 5;
const AUTOSAVE_QUIET_MS = 5000;   // 5 s after the last change...
const AUTOSAVE_MAX_MS = 15000;    // ...or 15 s after the first unsaved one
const CHANGED_MS = 250;           // embed: `changed` at most 4 a second
const LOAD_PREFIXES = ['guide/', 'manual/', 'examples/'];
const LOAD_PATH = /^[a-z0-9][a-z0-9/_.-]*\.(lunar|movy1|syx)$/;
const PREF = 'lunar.sim.';

export const EXAMPLES = [
  { path: 'examples/first-orbit.lunar', title: 'First orbit', kind: 'project' },
  { path: 'examples/deep-bass.sound.lunar', title: 'Deep space bass', kind: 'sound' },
  { path: 'examples/space-verbs.fx.lunar', title: 'Space verbs', kind: 'fx' },
  { path: 'examples/wobble.mods.lunar', title: 'Wobble', kind: 'mods' },
  { path: 'examples/bass-a.clip.lunar', title: 'Bass riff A', kind: 'clip' },
];

// ---- small helpers ---------------------------------------------------------------
const $ = (id) => document.getElementById(id);
const plural = (n, one, many) => `${n.toLocaleString('en')} ${n === 1 ? one : many}`;
const decoder = new TextDecoder();
const encoder = new TextEncoder();
const when = (t) => new Date(t).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
export const slug = (s) => String(s || '').toLowerCase().normalize('NFKD').replace(/[^a-z0-9]+/g, '-')
  .replace(/^-+|-+$/g, '').slice(0, 48) || 'lunar';

export function pref(key, value) {
  try {
    if (value === undefined) return localStorage.getItem(PREF + key);
    localStorage.setItem(PREF + key, String(value));
  } catch (err) { /* storage blocked: preferences last this visit only */ }
  return null;
}

// 1 binary, 2 JSON, 3 a .movy1 set, 4 DX7 SysEx or a raw bank, 0 none (§11).
export function sniff(b) {
  if (b.length >= 6 && b[0] === 0x89 && decoder.decode(b.subarray(1, 6)) === 'Lunar') return 1;
  let i = 0;
  while (i < b.length && (b[i] === 0x20 || b[i] === 0x09 || b[i] === 0x0a || b[i] === 0x0d)) ++i;
  if (b[i] === 0x7b) return 2;
  if (decoder.decode(b.subarray(i, i + 5)) === 'movy1') return 3;
  if (b[0] === 0xf0 || b.length === 4096) return 4;
  return 0;
}

// What a card shows of a file: its kind, title and about. Only for display;
// the module reads the file.
function describe(bytes, fileName) {
  const enc = sniff(bytes);
  const d = { enc, kind: null, title: fileName ? fileName.replace(/\.(lunar|movy1|syx|json)$/i, '') : 'Untitled', about: '' };
  if (enc === 2) {
    try {
      const j = JSON.parse(decoder.decode(bytes));
      if (j && typeof j === 'object') {
        if (typeof j.kind === 'string' && KIND[j.kind]) d.kind = j.kind;
        const t = typeof j.title === 'string' ? j.title : typeof j.name === 'string' ? j.name : '';
        if (t) d.title = t.slice(0, 80);
        if (typeof j.about === 'string') d.about = j.about.slice(0, 280);
      }
    } catch (err) { /* the module says what is wrong with it */ }
  } else if (enc === 3) {
    d.kind = 'set';
  }
  return d;
}

// Base64url, both ways.
function b64url(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
function unb64url(s) {
  if (!/^[A-Za-z0-9_-]*$/.test(s)) throw new Error('the link is not base64url');
  const bin = atob(s.replace(/-/g, '+').replace(/_/g, '/') + '==='.slice((s.length + 3) % 4));
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; ++i) out[i] = bin.charCodeAt(i);
  return out;
}

// A stream read into one buffer, stopping as soon as it passes `cap` bytes
// (a decompression bomb or an oversized file ends there).
async function readCapped(stream, cap) {
  const reader = stream.getReader();
  const chunks = [];
  let total = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    total += value.length;
    if (total > cap) {
      reader.cancel().catch(() => {});
      throw new Error(`it is larger than the ${Math.round(cap / 1024)} KiB the simulator reads`);
    }
    chunks.push(value);
  }
  const out = new Uint8Array(total);
  let at = 0;
  for (const c of chunks) { out.set(c, at); at += c.length; }
  return out;
}

export async function deflateLink(text) {
  const s = new Blob([encoder.encode(text)]).stream().pipeThrough(new CompressionStream('deflate-raw'));
  return b64url(await readCapped(s, TEXT_CAP));
}
export async function inflateLink(data) {
  if (data.length > LINK_CAP) throw new Error(`the link holds more than ${LINK_CAP / 1024} KiB`);
  const s = new Blob([unb64url(data)]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
  return readCapped(s, TEXT_CAP);
}

// ?load=PATH: an allowlisted path on this page's own origin, or null.
export function loadUrl(path, base = document.baseURI) {
  if (typeof path !== 'string' || path.length > 200) return null;
  if (!LOAD_PATH.test(path) || path.includes('..') || path.includes('//') || path.includes('\\')) return null;
  if (!LOAD_PREFIXES.some((p) => path.startsWith(p))) return null;
  let u;
  try { u = new URL(path, base); } catch (err) { return null; }
  const dir = new URL('.', base);
  if (u.origin !== location.origin || dir.origin !== location.origin) return null;
  if (u.search || u.hash || u.pathname !== dir.pathname + path) return null;
  return u;
}

// view=seq.track=2 (the link's form of a view line) as the view object.
const VIEW_MODES = ['home', 'fx', 'glo', 'seq', 'session', 'song', 'rack', 'matrix', 'chain'];
const VIEW_INTS = { sound: [1, 4], page: [1, 16], track: [1, 16], bar: [1, 64], pos: [1, 8], slot: [1, 32], entry: [1, 64] };
const VIEW_PANELS = ['track', 'set', 'clip', 'step'];
export function parseView(text) {
  if (typeof text !== 'string' || text.length > 120) return null;
  const [mode, ...rest] = text.split('.');
  if (!VIEW_MODES.includes(mode)) return null;
  const v = { mode };
  for (const kv of rest) {
    const [k, val, extra] = kv.split('=');
    if (extra !== undefined || val === undefined) return null;
    if (VIEW_INTS[k]) {
      const n = Number(val);
      if (!Number.isInteger(n) || n < VIEW_INTS[k][0] || n > VIEW_INTS[k][1]) return null;
      v[k] = n;
    } else if (k === 'panel' && VIEW_PANELS.includes(val)) {
      v.panel = val;
    } else if (k === 'unit' && /^[a-z0-9]{2,8}$/.test(val)) {
      v.unit = val;
    } else {
      return null;
    }
  }
  return v;
}

// into=s2 | master | t3.2 (track 3, slot 2), for a kind.
function parseInto(text, kind) {
  if (typeof text !== 'string') return null;
  let m;
  if (kind === 'sound' && (m = /^s([1-4])$/.exec(text))) return { into: Number(m[1]) - 1, slot: 0 };
  if (kind === 'fx' && text === 'master') return { into: -1, slot: 0 };
  if (kind === 'fx' && (m = /^s([1-4])$/.exec(text))) return { into: Number(m[1]) - 1, slot: 0 };
  if (kind === 'clip' && (m = /^t([1-8])\.([1-8])$/.exec(text))) return { into: Number(m[1]) - 1, slot: Number(m[2]) - 1 };
  return null;
}

function readHints(params) {
  const h = {};
  if (params.has('into')) h.into = params.get('into');
  if (params.has('view')) h.view = params.get('view');
  if (params.has('hl')) h.hl = params.get('hl').split(',').map((s) => s.trim().toUpperCase()).filter(Boolean).slice(0, 16);
  if (params.get('play') === '1') h.play = true;
  if (params.has('entry')) {
    const n = Number(params.get('entry'));
    if (Number.isInteger(n) && n >= 1 && n <= 64) h.entry = n;
  }
  return h;
}

// ---- browser storage: IndexedDB, or memory when it is blocked ------------------------
const memory = { files: new Map(), autosave: new Map(), recent: new Map() };
let memoryId = 1;
let dbPromise = null;
function openDb() {
  if (!dbPromise) {
    dbPromise = new Promise((resolve) => {
      try {
        const req = indexedDB.open('lunar-modulator', 1);
        req.onupgradeneeded = () => {
          const d = req.result;
          if (!d.objectStoreNames.contains('files')) d.createObjectStore('files', { keyPath: 'id', autoIncrement: true });
          if (!d.objectStoreNames.contains('autosave')) d.createObjectStore('autosave');
          if (!d.objectStoreNames.contains('recent')) d.createObjectStore('recent', { keyPath: 'id', autoIncrement: true });
        };
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => resolve(null);
        req.onblocked = () => resolve(null);
      } catch (err) {
        resolve(null);
      }
    });
  }
  return dbPromise;
}
async function idb(store, mode, fn) {
  const d = await openDb();
  if (d) {
    try {
      return await new Promise((resolve, reject) => {
        const t = d.transaction(store, mode);
        const req = fn(t.objectStore(store));
        t.oncomplete = () => resolve(req ? req.result : undefined);
        t.onerror = () => reject(t.error);
        t.onabort = () => reject(t.error);
      });
    } catch (err) { /* fall through to memory */ }
  }
  return null;
}
export const store = {
  async available() { return (await openDb()) !== null; },
  async get(name, key) {
    const r = await idb(name, 'readonly', (s) => s.get(key));
    return r !== null ? r : memory[name].get(key) || null;
  },
  async put(name, value, key) {
    if (await openDb()) {
      const r = await idb(name, 'readwrite', (s) => (key === undefined ? s.put(value) : s.put(value, key)));
      if (r !== null) return r;
    }
    const k = key !== undefined ? key : value.id || memoryId++;
    memory[name].set(k, key === undefined ? { ...value, id: k } : value);
    return k;
  },
  async all(name) {
    const r = await idb(name, 'readonly', (s) => s.getAll());
    return r !== null ? r : [...memory[name].values()];
  },
  async del(name, key) {
    await idb(name, 'readwrite', (s) => s.delete(key));
    memory[name].delete(key);
  },
};

// ---- the page's files ------------------------------------------------------------
export function initFiles(env) {
  const { sim, powerOn, loadDx7Files, controlEl } = env;
  const params = new URLSearchParams(location.search);
  const embed = params.get('embed') === '1' && window.parent !== window;
  const f = {
    title: pref('title') || 'Untitled', gen: 0, dirty: false, pending: [], undo: null,
    shadowCalls: 0, workletLoads: [], autosaves: 0, lastNotice: null,
  };
  sim.files = f;
  let worker = null, workerRate = 0, nextId = 1;
  const waiting = new Map();

  // ---- the shadow Worker and the worklet, by promise ----
  function shadow(op, msg = {}, transfer = []) {
    if (!worker) {
      worker = new Worker(new URL('shadow.worker.js', import.meta.url), { type: 'module' });
      worker.onmessage = (e) => {
        const w = waiting.get(e.data.re);
        if (w) { waiting.delete(e.data.re); w(e.data); }
      };
      worker.onerror = (e) => {
        for (const w of waiting.values()) w({ ok: false, error: e.message || 'the shadow Worker failed' });
        waiting.clear();
      };
    }
    const rate = sim.ctx ? sim.ctx.sampleRate : 44100;
    if (rate !== workerRate && op !== 'init') {
      workerRate = rate;
      shadow('init', { wasm: sim.wasm.slice(0), rate });
    }
    const id = nextId++;
    ++f.shadowCalls;
    return new Promise((resolve) => {
      waiting.set(id, resolve);
      worker.postMessage({ id, op, ...msg }, transfer);
    });
  }
  function worklet(msg, transfer = []) {
    if (!sim.node) return Promise.resolve({ ok: false, off: true });
    const id = nextId++;
    return new Promise((resolve) => {
      waiting.set(id, resolve);
      sim.node.port.postMessage({ ...msg, id }, transfer);
    });
  }
  async function liveBin() {
    const r = await worklet({ type: 'state-save', kind: 1, arg: 0 });
    if (!r.ok) throw new Error(r.off ? 'Power is off.' : 'The project could not be saved.');
    return r.bytes;
  }
  const report = (r, fallback) => (r && r.report && typeof r.report === 'object' ? r.report
    : { code: 'BAD', message: (r && r.error) || fallback || 'Something went wrong.' });

  // ---- the notice over the status line ----
  const noticeEl = $('file-notice');
  function notice(tone, text, sub = '', actions = []) {
    f.lastNotice = { tone, text, sub };
    noticeEl.hidden = false;
    noticeEl.className = `file-notice ${tone}`;
    noticeEl.textContent = '';
    const p = document.createElement('p');
    p.className = 'notice-text';
    p.textContent = text;
    noticeEl.append(p);
    if (sub) {
      const s = document.createElement('p');
      s.className = 'notice-sub';
      s.textContent = sub;
      noticeEl.append(s);
    }
    const row = document.createElement('div');
    row.className = 'notice-actions';
    for (const a of [...actions, { label: 'Dismiss', fn: () => { noticeEl.hidden = true; } }]) {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = a.label;
      b.addEventListener('click', () => { b.blur(); a.fn(); });
      row.append(b);
    }
    noticeEl.append(row);
  }

  // The module's report, in words. A refusal is the module's own sentence.
  function loadedText(rep, d, target) {
    const parts = [];
    // A project counts what it holds; a sound or effects loaded into the
    // panel count what came with them (the sounds are the panel's own).
    if (rep.sounds && d.kind === 'project') parts.push(plural(rep.sounds, 'sound', 'sounds'));
    if (rep.effects) parts.push(plural(rep.effects, 'effect', 'effects'));
    if (rep.modules) parts.push(plural(rep.modules, 'module', 'modules'));
    if (rep.cables) parts.push(plural(rep.cables, 'cable', 'cables'));
    if (rep.tracks) parts.push(plural(rep.tracks, 'track', 'tracks') + (rep.clips ? ` with ${plural(rep.clips, 'clip', 'clips')}` : ''));
    else if (rep.clips) parts.push(plural(rep.clips, 'clip', 'clips'));
    if (rep.song) parts.push(`a ${rep.song}-entry song`);
    if (rep.voices) parts.push(plural(rep.voices, 'FM6 voice', 'FM6 voices'));
    const kind = d.kind && d.kind !== 'project' ? `${KIND_WORD[d.kind]} ` : '';
    return `Loaded ${kind}“${d.title}”${target}${parts.length ? `: ${parts.join(', ')}` : ''}. ` +
      `It takes ${rep.percent}% of the FM-1's RAM.`;
  }
  function subText(rep) {
    const s = [];
    if (rep.left_out) s.push(`${plural(rep.left_out, 'part was', 'parts were')} left out.`);
    if (rep.skipped) s.push(`${plural(rep.skipped, 'member was', 'members were')} skipped${rep.first_skip ? `, the first ${rep.first_skip}` : ''}.`);
    if (rep.repaired) s.push(`${plural(rep.repaired, 'value was', 'values were')} out of range and set to the nearest.`);
    return s.join(' ');
  }
  function targetText(kind, t) {
    if (!t) return '';
    if (kind === 'sound') return ` into Sound ${t.into + 1}`;
    if (kind === 'fx') return t.into < 0 ? ' into the master effects' : ` into Sound ${t.into + 1}'s effects`;
    if (kind === 'clip') return ` into track ${t.into + 1}, slot ${t.slot + 1}`;
    return '';
  }

  // ---- the target of a partial kind ----
  const targetEl = $('target-card');
  function askTarget(kind, title) {
    if (!['sound', 'fx', 'clip'].includes(kind)) return Promise.resolve({ into: 0, slot: 0 });
    return new Promise((resolve) => {
      const current = sim.state ? sim.state.sound : 0;
      const sel = $('target-into'), slotSel = $('target-slot');
      const opts = kind === 'sound' ? [0, 1, 2, 3].map((i) => [i, `Sound ${i + 1}`])
        : kind === 'fx' ? [[-1, 'Master effects'], ...[0, 1, 2, 3].map((i) => [i, `Sound ${i + 1}'s effects`])]
          : [0, 1, 2, 3, 4, 5, 6, 7].map((i) => [i, `Track ${i + 1}`]);
      sel.innerHTML = opts.map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
      sel.value = String(kind === 'sound' ? current : kind === 'fx' ? -1 : 0);
      $('target-slot-field').hidden = kind !== 'clip';
      slotSel.value = '0';
      $('target-title').textContent = `Load ${KIND_WORD[kind]} “${title}” into`;
      targetEl.hidden = false;
      $('target-into').focus();
      const done = (v) => {
        targetEl.hidden = true;
        $('target-ok').onclick = null;
        $('target-cancel').onclick = null;
        resolve(v);
      };
      $('target-ok').onclick = () => done({ into: Number(sel.value), slot: Number(slotSel.value) });
      $('target-cancel').onclick = () => done(null);
    });
  }

  // ---- a load: pass 1 in the shadow, the packed file to the worklet ----
  // Resolves to { ok, report }; with `ui`, says it on the page and offers
  // "Load without …", "Replace the clip" and Undo load.
  async function load(bytes, o = {}) {
    const d = o.d || describe(bytes, o.name);
    if (d.enc === 0 && o.name && /\.syx$/i.test(o.name)) d.enc = 4;
    let kind = d.kind;
    let target = o.target || null;
    let live;
    try {
      live = await liveBin();
    } catch (err) {
      return { ok: false, report: { code: 'OFF', message: err.message } };
    }
    // A binary file's kind is the module's word (pass 1 with no target).
    if (!kind) {
      const probe = await shadow('check', { bytes, kind: 0, into: 0, slot: 0, flags: 0, live: live.slice(0) });
      kind = probe.report && KIND[probe.report.kind] ? probe.report.kind : null;
      d.kind = kind;
    }
    if (!target && ['sound', 'fx', 'clip'].includes(kind)) {
      target = o.ask === false ? { into: kind === 'fx' ? -1 : kind === 'sound' && sim.state ? sim.state.sound : 0, slot: 0 }
        : await askTarget(kind, d.title);
      if (!target) return { ok: false, cancelled: true, report: { code: 'CANCELLED', message: 'Not loaded.' } };
    }
    target = target || { into: 0, slot: 0 };
    const flags = o.flags | 0;
    const c = await shadow('check', { bytes, kind: 0, into: target.into, slot: target.slot, flags, live: live.slice(0) });
    if (!c.ok) {
      const rep = report(c);
      if (o.ui) refused(rep, bytes, { ...o, d, target });
      return { ok: false, report: rep };
    }
    let before = live;
    if (f.skipBefore) { before = f.skipBefore; f.skipBefore = null; } else if (o.before !== false) await addRecent(`Before ${d.title}`, live);
    const l = await worklet({ type: 'state-load', bytes: c.bin, kind: 0, into: target.into, slot: target.slot,
      flags: flags | (o.quiet ? FLAG_QUIET : 0) }, [c.bin.buffer]);
    f.workletLoads.push({ binary: l.binary === true, ok: l.ok === true });
    const rep = l.report ? JSON.parse(l.report) : { code: 'BAD', message: 'The audio thread takes the binary container only.' };
    if (!l.ok) {
      if (o.ui) refused(rep, bytes, { ...o, d, target });
      return { ok: false, report: rep };
    }
    if (kind === 'project') setTitle(d.title);
    if (o.before !== false) f.undo = { bin: before, title: d.title };
    touched();
    if (o.ui) {
      notice('loaded', loadedText(rep, d, targetText(kind, target)), subText(rep),
        o.before !== false ? [{ label: 'Undo load', fn: undoLoad }] : []);
    }
    return { ok: true, report: rep, kind };
  }

  function refused(rep, bytes, o) {
    const actions = [];
    if (rep.code === 'NO_ROOM' && o.d.kind === 'clip' && !(o.flags & FLAG_REPLACE)) {
      actions.push({ label: 'Replace the clip', fn: () => load(bytes, { ...o, flags: (o.flags | 0) | FLAG_REPLACE }) });
    } else if ((rep.code === 'UNKNOWN' || rep.code === 'NO_ROOM') && !(o.flags & FLAG_WITHOUT)) {
      const what = rep.name || rep.what;
      actions.push({ label: what ? `Load without ${what}` : 'Load without what does not fit',
        fn: () => load(bytes, { ...o, flags: (o.flags | 0) | FLAG_WITHOUT }) });
    }
    const where = rep.line ? ` (line ${rep.line}, column ${rep.col}${rep.path ? `, ${rep.path}` : ''})` : '';
    notice('refused', `“${o.d.title}” was not loaded. ${rep.message || rep.code}${where}`, '', actions);
  }

  async function undoLoad() {
    const u = f.undo;
    if (!u) return;
    f.undo = null;
    const r = await load(u.bin, { d: { enc: 1, kind: 'project', title: u.title }, before: false, quiet: true });
    if (r.ok) notice('info', `The load of “${u.title}” was undone: the project is as it was before it.`);
    else notice('refused', `The load could not be undone: ${r.report.message}`);
  }

  function setTitle(t) {
    f.title = t || 'Untitled';
    pref('title', f.title);
  }

  // ---- Recent, saved projects, the autosave ----
  async function addRecent(name, bin) {
    await store.put('recent', { name, bin, size: bin.length, modified: Date.now() });
    const all = (await store.all('recent')).sort((a, b) => a.modified - b.modified || a.id - b.id);
    for (const old of all.slice(0, Math.max(0, all.length - RECENT))) await store.del('recent', old.id);
    renderLibrary();
  }

  let autosaveTimer = null, firstDirty = 0, lastAutosave = 0, lastBytes = null;
  function touched() {
    f.dirty = true;
    ++f.gen;
    const now = Date.now();
    if (!firstDirty) firstDirty = now;
    clearTimeout(autosaveTimer);
    const due = Math.max(Math.min(now + AUTOSAVE_QUIET_MS, firstDirty + AUTOSAVE_MAX_MS), lastAutosave + AUTOSAVE_QUIET_MS);
    autosaveTimer = setTimeout(autosave, Math.max(0, due - now));
    if (embed) changedSoon();
  }
  async function autosave() {
    clearTimeout(autosaveTimer);
    autosaveTimer = null;
    if (!f.dirty || !sim.node) return false;
    f.dirty = false;
    firstDirty = 0;
    lastAutosave = Date.now();
    let bin;
    try { bin = await liveBin(); } catch (err) { return false; }
    if (lastBytes && lastBytes.length === bin.length && lastBytes.every((b, i) => b === bin[i])) return true;
    lastBytes = bin;
    await store.put('autosave', { name: f.title, bin, size: bin.length, modified: Date.now() }, 'project');
    ++f.autosaves;
    return true;
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') autosave(); });
  window.addEventListener('pagehide', () => { autosave(); });

  async function savePressed() {
    let ok = false, reason = 'NOT SAVED';
    try {
      const bin = await liveBin();
      await store.put('files', { kind: 'project', name: f.title, bin, size: bin.length, origin: 'user', mission: null,
        modified: Date.now() });
      ok = true;
    } catch (err) {
      reason = 'STORAGE BLOCKED';
    }
    if (sim.node) sim.node.port.postMessage({ type: 'saved', ok, reason: encoder.encode(reason) });
    if (ok) {
      notice('info', f.memoryOnly ? `Saved “${f.title}” for this visit only: this browser blocks storage.`
        : `Saved “${f.title}” in this browser: Files, Saved in this browser, lists it.`);
    }
    renderLibrary();
  }

  // ---- downloads ----
  function download(text, name, type) {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([text], { type }));
    a.download = name;
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 4000);
  }
  // kind: a KIND name; arg as fm1w_state_save's. Resolves to the text.
  async function saveText(kind, arg = 0, live = null) {
    const r = await shadow('save', { kind: KIND[kind], arg, live: live || await liveBin() });
    if (!r.ok || typeof r.text !== 'string') throw new Error(report(r, 'Nothing to save.').message || 'Nothing to save.');
    return r.text;
  }
  function fileName(kind, arg) {
    const base = slug(f.title);
    if (kind === 'project') return `${base}.lunar`;
    if (kind === 'set') return `${base}.movy1`;
    const who = kind === 'sound' ? `-s${arg + 1}` : kind === 'fx' ? (arg < 0 ? '-master' : `-s${arg + 1}`) : '';
    return `${base}${who}.${kind}.lunar`;
  }
  async function saveAs(choice) {
    const [kind, a] = choice.split(':');
    const arg = a === 'current' ? (sim.state ? sim.state.sound : 0) : Number(a || 0);
    try {
      const text = await saveText(kind, arg);
      const name = fileName(kind, arg);
      download(text, name, kind === 'set' ? 'text/plain' : 'application/json');
      pref('last-file', name);
      notice('info', `Saved ${name} (${Math.ceil(text.length / 1024)} KB) to your downloads.`);
    } catch (err) {
      notice('refused', `Not saved: ${err.message}`);
    }
  }

  // ---- Copy link ----
  async function copyLink() {
    try {
      const text = await saveText('project');
      const data = await deflateLink(JSON.stringify(JSON.parse(text)));
      if (data.length > LINK_CAP) {
        notice('refused', `This project needs a ${Math.ceil(data.length / 1024)} KiB link, more than the ` +
          `${LINK_CAP / 1024} KiB a link holds. Save… the project and share the file instead.`);
        return null;
      }
      const link = `${location.origin}${location.pathname}#lunar=${data}`;
      let copied = false;
      try { await navigator.clipboard.writeText(link); copied = true; } catch (err) { /* shown below */ }
      notice('info', copied ? `Link copied: ${Math.ceil(data.length / 1024)} KiB of the ${LINK_CAP / 1024} KiB a link holds. ` +
        'Anyone who opens it gets this project, in their own browser.'
        : 'The browser would not copy the link; it is selected below to copy by hand.');
      if (!copied) {
        const input = document.createElement('input');
        input.className = 'link-out';
        input.readOnly = true;
        input.value = link;
        input.setAttribute('aria-label', 'Link to this project');
        noticeEl.insertBefore(input, noticeEl.querySelector('.notice-actions'));
        input.select();
      }
      f.link = link;
      return link;
    } catch (err) {
      notice('refused', `No link: ${err.message}`);
      return null;
    }
  }

  // ---- the library: saved, Recent, examples ----
  const libEl = $('library-lists');
  async function renderLibrary() {
    if (!libEl) return;
    const [saved, recent] = await Promise.all([store.all('files'), store.all('recent')]);
    const section = (title, items, actions, empty) => {
      const s = document.createElement('div');
      s.className = 'lib-section';
      const h = document.createElement('h3');
      h.textContent = title;
      s.append(h);
      if (!items.length) {
        const p = document.createElement('p');
        p.className = 'lib-empty';
        p.textContent = empty;
        s.append(p);
      }
      const ul = document.createElement('ul');
      for (const it of items) {
        const li = document.createElement('li');
        const name = document.createElement('span');
        name.className = 'lib-name';
        name.textContent = it.name;
        const meta = document.createElement('span');
        meta.className = 'lib-meta';
        meta.textContent = it.meta;
        const btns = document.createElement('span');
        btns.className = 'lib-actions';
        for (const [label, fn] of actions(it)) {
          const b = document.createElement('button');
          b.type = 'button';
          b.textContent = label;
          b.disabled = !sim.node && label !== 'Delete' && !it.path;
          b.addEventListener('click', () => { b.blur(); fn(); });
          btns.append(b);
        }
        li.append(name, meta, btns);
        ul.append(li);
      }
      s.append(ul);
      return s;
    };
    const asItems = (list) => list.sort((a, b) => b.modified - a.modified)
      .map((x) => ({ ...x, meta: `${when(x.modified)}, ${Math.ceil(x.size / 1024)} KB` }));
    const binActions = (it, del) => [
      ['Load', () => load(it.bin, { d: { enc: 1, kind: 'project', title: it.name.replace(/^Before /, '') }, ui: true })],
      ['Download', async () => {
        try { download(await saveText('project', 0, it.bin), `${slug(it.name)}.lunar`, 'application/json'); } catch (err) {
          notice('refused', `Not saved: ${err.message}`);
        }
      }],
      ...(del ? [['Delete', async () => { await store.del('files', it.id); renderLibrary(); }]] : []),
    ];
    libEl.textContent = '';
    libEl.append(
      section('Saved in this browser', asItems(saved), (it) => binActions(it, true), 'Nothing yet: SAVE on the panel keeps the project here.'),
      section('Recent', asItems(recent), (it) => binActions(it, false), 'The state a load replaces is kept here, the last five.'),
      section('Examples', EXAMPLES.map((x) => ({ ...x, name: x.title, meta: `${KIND_WORD[x.kind]}, MIT` })),
        (it) => [['Load', () => openExample(it.path)]], ''),
    );
    for (const li of libEl.querySelectorAll('.lib-section:last-child li')) {
      const x = EXAMPLES.find((e) => e.title === li.querySelector('.lib-name').textContent);
      const a = document.createElement('a');
      a.href = `?load=${x.path}`;
      a.textContent = x.title;
      a.addEventListener('click', (e) => { e.preventDefault(); openExample(x.path); });
      li.querySelector('.lib-name').replaceChildren(a);
    }
  }

  // ---- arrival: a link's file, or files opened before the power is on ----
  const arrivalEl = $('arrival');
  function showArrival() {
    const p = f.pending[0];
    const powerHint = $('power-hint');
    $('arrival-cancel').hidden = !p;
    if (!p) {
      arrivalEl.hidden = true;
      $('power-on').textContent = 'Power on';
      powerHint.hidden = false;
      return;
    }
    arrivalEl.hidden = false;
    powerHint.hidden = true;
    $('arrival-kind').textContent = p.d.kind ? `A ${KIND_WORD[p.d.kind]}${f.pending.length > 1 ? `, and ${plural(f.pending.length - 1, 'more file', 'more files')}` : ''}` : 'A file';
    $('arrival-title').textContent = p.d.title;
    $('arrival-about').textContent = p.d.about;
    $('arrival-about').hidden = !p.d.about;
    $('power-on').textContent = 'Power on and load';
    store.get('autosave', 'project').then((saved) => {
      const replaces = p.d.kind === 'project' || !p.d.kind ? 'It replaces what is on the FM-1' : 'It loads into what is on the FM-1';
      $('arrival-replace').textContent = saved
        ? `${replaces} now, your work from ${when(saved.modified)}, which stays in Recent as “Before ${p.d.title}”.`
        : '';
      $('arrival-replace').hidden = !saved;
    });
  }
  $('arrival-cancel').addEventListener('click', () => {
    for (const p of f.pending) if (p.reply) p.reply({ ok: false, error: 'The person chose not to load it.' });
    f.pending = [];
    showArrival();
  });

  async function arrive(bytes, name, hints = {}, reply = null) {
    f.pending.push({ bytes, name, hints, reply, d: describe(bytes, name) });
    if (f.powered) await loadPending(); else showArrival();
  }
  async function loadPending() {
    while (f.pending.length) {
      const p = f.pending.shift();
      const target = p.hints.into && p.d.kind ? parseInto(p.hints.into, p.d.kind) : null;
      const r = await openBytes(p.bytes, p.name, { target, d: p.d, ask: p.reply ? false : undefined });
      if (r && r.ok) await applyHints(p.hints);
      if (p.reply) p.reply({ ok: !!(r && r.ok), report: r && r.report });
      f.skipBefore = null;
    }
    showArrival();
  }

  // After POWER: the shadow Worker, the store's answer for SAVE, then the
  // arrivals, or else the autosave.
  async function afterPowerOn() {
    const ok = await store.available();
    sim.node.port.postMessage({ type: 'store-ready', on: true });
    if (!ok) f.memoryOnly = true;
    const pending = f.pending;
    f.pending = [];
    showArrival();
    const saved = await store.get('autosave', 'project');
    if (pending.length) {
      // A link over the user's work (ST14): a project replaces it, so the
      // autosave goes to Recent unloaded; anything else loads into it.
      const first = pending[0];
      if (saved && first.d.kind === 'project') {
        await addRecent(`Before ${first.d.title}`, saved.bin);
        f.skipBefore = saved.bin;
      } else if (saved) {
        await restore(saved, true);
      }
    } else if (saved) {
      await restore(saved, false);
    }
    f.powered = true;
    f.pending = pending.concat(f.pending);
    await loadPending();
    if (pending.length) clearLinkFromAddress();
    renderLibrary();
    if (embed) post({ event: 'power', on: true });
  }
  async function restore(saved, quietly) {
    const r = await load(saved.bin, { d: { enc: 1, kind: 'project', title: saved.name }, before: false, quiet: true });
    if (r.ok) {
      setTitle(saved.name);
      f.dirty = false;
      lastBytes = saved.bin;
      if (!quietly) {
        notice('info', `Restored “${saved.name}”, autosaved in this browser ${when(saved.modified)}.`, '',
          [{ label: 'Start fresh', fn: startFresh }]);
      }
    } else {
      await addRecent(`Autosave not restored (${saved.name})`, saved.bin);
      notice('refused', `Your autosaved project was not restored: ${r.report.message} It is kept in Recent.`);
    }
  }
  async function startFresh() {
    const s = await shadow('start');
    if (!s.ok) return;
    const r = await load(s.bin, { d: { enc: 1, kind: 'project', title: 'a fresh start' }, quiet: true });
    if (r.ok) {
      setTitle('Untitled');
      notice('info', 'A fresh start: the start chain and its demo pattern. Your work is in Recent.', '',
        [{ label: 'Undo', fn: undoLoad }]);
    }
  }
  async function beforePowerOff() {
    await Promise.race([autosave(), new Promise((r) => setTimeout(r, 800))]);
    f.powered = false;
    if (embed) post({ event: 'power', on: false });
  }

  // ---- Open… and drop ----
  async function openBytes(bytes, name, o = {}) {
    const d = o.d || describe(bytes, name);
    if (d.enc === 4 || (d.enc === 0 && /\.syx$/i.test(name || ''))) {
      loadDx7Files([new File([bytes], name || 'patches.syx')]);
      return { ok: true, dx7: true };
    }
    if (!f.powered) {
      arrive(bytes, name, o.hints || {});
      return null;
    }
    return load(bytes, { ...o, d, name, ui: o.ui !== false });
  }
  async function openFiles(files) {
    for (const file of files) {
      const cap = /\.syx$/i.test(file.name) ? SYX_CAP : TEXT_CAP;
      if (file.size > cap) {
        notice('refused', `“${file.name}” was not loaded: at ${Math.ceil(file.size / 1024)} KiB it is larger than the ` +
          `${cap / 1024} KiB the simulator reads.`);
        continue;
      }
      let bytes;
      try { bytes = new Uint8Array(await file.arrayBuffer()); } catch (err) {
        notice('refused', `“${file.name}” could not be read: ${err.message || err}`);
        continue;
      }
      await openBytes(bytes, file.name);
      pref('last-file', file.name);
    }
  }
  const openInput = $('open-file');
  $('open').addEventListener('click', () => openInput.click());
  openInput.addEventListener('change', () => {
    const files = [...openInput.files];
    openInput.value = '';
    $('open').blur();
    openFiles(files);
  });
  $('save').addEventListener('click', () => { $('save').blur(); saveAs($('save-kind').value); });
  $('copy-link').addEventListener('click', () => { $('copy-link').blur(); copyLink(); });
  async function openExample(path) {
    const r = await fetchAllowed(path);
    if (r.ok) openBytes(r.bytes, path.split('/').pop());
    else notice('refused', r.message);
  }

  // The Save… choices follow the current sound.
  let kindsFor = -1;
  function fillSaveKinds() {
    const sel = $('save-kind');
    const n = (sim.state ? sim.state.sound : 0) + 1;
    if (n === kindsFor) return;
    kindsFor = n;
    const keep = sel.value;
    sel.innerHTML = [
      ['project', 'Project (.lunar)'], ['sound:current', `Sound ${n} (.sound.lunar)`],
      ['fx:-1', 'Master effects (.fx.lunar)'], ['fx:current', `Sound ${n}'s effects (.fx.lunar)`],
      ['mods', 'Mod rack (.mods.lunar)'], ['set', 'Set, for Movy (.movy1)'],
    ].map(([v, t]) => `<option value="${v}">${t}</option>`).join('');
    if (keep) sel.value = keep;
    if (!sel.value) sel.value = 'project';
  }

  // ---- links: ?load= and #lunar= ----
  async function fetchAllowed(path) {
    const u = loadUrl(path);
    if (!u) return { ok: false, message: `The link's file “${String(path).slice(0, 80)}” is not one this page loads: only files under ${LOAD_PREFIXES.join(', ')} on this site are.` };
    try {
      const res = await fetch(u, { credentials: 'omit', redirect: 'error', cache: 'no-cache' });
      if (!res.ok) return { ok: false, message: `The link's file could not be fetched (HTTP ${res.status}).` };
      const bytes = await readCapped(res.body, /\.syx$/.test(path) ? SYX_CAP : TEXT_CAP);
      return { ok: true, bytes };
    } catch (err) {
      return { ok: false, message: `The link's file could not be read: ${err.message || err}.` };
    }
  }
  function clearLinkFromAddress() {
    try {
      const u = new URL(location.href);
      for (const k of ['load', 'into', 'view', 'hl', 'play', 'entry']) u.searchParams.delete(k);
      if (/^#lunar=/.test(u.hash)) u.hash = '';
      history.replaceState(null, '', u.href);
    } catch (err) { /* the address keeps the link */ }
  }
  async function readLink() {
    const hash = new URLSearchParams(location.hash.slice(1));
    const hints = { ...readHints(params), ...readHints(hash) };
    if (params.has('load')) {
      const path = params.get('load');
      const r = await fetchAllowed(path);
      if (r.ok) arrive(r.bytes, path.split('/').pop(), hints);
      else notice('refused', r.message);
    } else if (hash.has('lunar')) {
      try {
        const bytes = await inflateLink(hash.get('lunar'));
        arrive(bytes, 'the link', hints);
      } catch (err) {
        notice('refused', `The link's project could not be read: ${err.message || err}.`);
      }
    }
  }

  // Hints, after the load and the POWER press.
  async function applyHints(h) {
    if (h.view) {
      const v = parseView(h.view);
      if (!v || !(await setView(v))) notice('refused', `The link's view “${h.view}” was not applied.`);
    }
    if (h.hl) highlight(h.hl);
    if (h.entry) seqLine(`sgjump ${h.entry - 1}`);
    if (h.play || h.entry) seqLine('play');
  }
  async function setView(v) {
    try {
      const live = await liveBin();
      const doc = JSON.parse(await saveText('project', 0, live));
      doc.view = v;
      const p = await shadow('pack', { text: JSON.stringify(doc) });
      if (!p.ok) return false;
      const l = await worklet({ type: 'state-load', bytes: p.bin, kind: 1, into: 0, slot: 0, flags: FLAG_QUIET }, [p.bin.buffer]);
      f.workletLoads.push({ binary: l.binary === true, ok: l.ok === true });
      return l.ok;
    } catch (err) {
      return false;
    }
  }
  function seqLine(text) {
    if (sim.node) sim.node.port.postMessage({ type: 'seq-line', bytes: encoder.encode(text) });
  }
  function highlight(names) {
    for (const g of document.querySelectorAll('#panel .hl-ring')) g.remove();
    const done = [];
    for (const name of names.slice(0, 16)) {
      const g = controlEl(name);
      if (!g) continue;
      const b = g.getBBox();
      const pad = 0.8;
      const ring = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      ring.setAttribute('class', 'hl-ring');
      const t = g.getAttribute('transform') || '';
      const m = /translate\(([-\d.]+) ([-\d.]+)\)/.exec(t);
      const dx = m ? Number(m[1]) : 0, dy = m ? Number(m[2]) : 0;
      ring.setAttribute('x', b.x + dx - pad);
      ring.setAttribute('y', b.y + dy - pad);
      ring.setAttribute('width', b.width + 2 * pad);
      ring.setAttribute('height', b.height + 2 * pad);
      ring.setAttribute('rx', Math.min(b.width, b.height) / 2 + pad);
      $('panel').append(ring);
      done.push(name);
    }
    f.highlighted = done;
    return done;
  }

  // ---- ?embed=1: the guide's postMessage API, same origin only ----
  let changedTimer = null, busy = false;
  function post(m) { if (embed) window.parent.postMessage({ lunar: 1, ...m }, location.origin); }
  function changedSoon() {
    if (changedTimer) return;
    changedTimer = setTimeout(() => { changedTimer = null; post({ event: 'changed', gen: f.gen }); }, CHANGED_MS);
  }
  async function embedOp(m) {
    const kindArg = (k, into) => (k === 'sound' ? into | 0 : k === 'fx' ? (into === undefined ? -1 : into | 0) : 0);
    switch (m.op) {
      case 'load': {
        if (typeof m.text !== 'string' || m.text.length > TEXT_CAP) return { ok: false, error: 'text: a .lunar file of up to 256 KiB' };
        const bytes = encoder.encode(m.text);
        const d = describe(bytes, 'the page');
        if (m.kind && d.kind && m.kind !== d.kind) return { ok: false, error: `the text is a ${d.kind}, not a ${m.kind}` };
        const target = m.into !== undefined && d.kind ? parseInto(String(m.into), d.kind) : null;
        if (!f.powered) {
          return new Promise((resolve) => arrive(bytes, 'the page', { into: m.into === undefined ? undefined : String(m.into) }, resolve));
        }
        const r = await load(bytes, { d, target, ask: false, ui: true });
        return { ok: r.ok, report: r.report };
      }
      case 'save':
      case 'query': {
        if (!KIND[m.kind]) return { ok: false, error: `kind: one of ${Object.keys(KIND).join(', ')}` };
        if (!sim.node) return { ok: false, error: 'Power is off.' };
        const text = await saveText(m.kind, kindArg(m.kind, m.into));
        if (m.op === 'save') return { ok: true, text };
        return { ok: true, json: m.kind === 'set' ? text : JSON.parse(text) };
      }
      case 'view': {
        const v = typeof m.view === 'string' ? parseView(m.view) : null;
        if (!v) return { ok: false, error: 'view: as the link hint, e.g. "seq.track=2"' };
        if (!sim.node) return { ok: false, error: 'Power is off.' };
        return { ok: await setView(v) };
      }
      case 'highlight': {
        if (!Array.isArray(m.controls)) return { ok: false, error: 'controls: an array of control names' };
        return { ok: true, controls: highlight(m.controls.map((c) => String(c).toUpperCase())) };
      }
      case 'transport': {
        if (!sim.node) return { ok: false, error: 'Power is off: the person presses POWER first.' };
        if (m.play) {
          if (Number.isInteger(m.entry) && m.entry >= 1 && m.entry <= 64) seqLine(`sgjump ${m.entry - 1}`);
          seqLine('play');
        } else {
          seqLine('stop');
        }
        return { ok: true };
      }
      default:
        return { ok: false, error: `no such operation: ${String(m.op).slice(0, 40)}` };
    }
  }
  if (embed) {
    document.body.classList.add('embed');
    window.addEventListener('message', async (e) => {
      if (e.source !== window.parent || e.origin !== location.origin) return;
      const m = e.data;
      if (!m || typeof m !== 'object' || m.lunar !== 1 || typeof m.op !== 'string') return;
      if (busy) { post({ re: m.id, ok: false, error: 'busy: one operation at a time' }); return; }
      busy = true;
      let r;
      try { r = await embedOp(m); } catch (err) { r = { ok: false, error: String(err.message || err) }; }
      busy = false;
      post({ re: m.id, ...r });
    });
    post({ event: 'ready', formats: ['lunar', 'movy1'], version: '1.0' });
  }

  // ---- drop, wired by app.js ----
  readLink();
  fillSaveKinds();
  renderLibrary();
  // window.fm1.files: this state and these calls, for the console and the
  // headless page check.
  return Object.assign(f, {
    openFiles, afterPowerOn, beforePowerOff, touched, fillSaveKinds, renderLibrary, autosave, copyLink, highlight,
    saveText, undoLoad, store,
    onWorklet(m) {
      if (m.type === 'state-saved' || m.type === 'state-loaded') {
        const w = waiting.get(m.id);
        if (w) { waiting.delete(m.id); w(m); }
        return true;
      }
      if (m.type === 'save-pressed') { savePressed(); return true; }
      return false;
    },
  });
}
