// The browser's lossless editable movy1 model. Native bounds: fm1_seq.h and
// seq_persist.c. Unknown extension lines survive saving and are reported.
export const SEQ_LIMITS = Object.freeze({ tracks: 8, slots: 8, steps: 256, notes: 1536, locks: 1536,
  trigs: 256, clipNotes: 512, clipLocks: 1024, clipTrigs: 1024, song: 64, gates: 64 });
export const cloneSet = (m) => JSON.parse(JSON.stringify(m));
export function emptyClip(length = 16) {
  return { length, loopStart: 0, scaleNum: 1, scaleDen: 1, transpose: 0, quant: 0, notes: [], locks: [], trigs: [] };
}
export function emptySet() {
  return { bpmX100: 12000, swing: 50, link: 0, key: [0, 0], defaultQuant: 0, song: [], songEnd: 0,
    sceneNames: Array(8).fill(''), unknown: [], tracks: Array.from({ length: 8 }, (_, t) => ({
      active: 0, muted: 0, padMutes: [], padSolo: null, lanes: Array(8).fill(null), route: { kind: 0, index: t + 1 }, clips: Array(8).fill(null) })) };
}
const int = (x, lo, hi) => Number.isSafeInteger(x) && x >= lo && x <= hi;
const token = (s, max) => typeof s === 'string' && new TextEncoder().encode(s).length <= max && !/[\s\x00-\x1f\x7f]/u.test(s);
export function validateSet(m) {
  const errors = [], warnings = [], usage = { notes: 0, locks: 0, trigs: 0, clips: 0, song: 0 };
  const ck = (yes, why) => { if (!yes) errors.push(why); };
  if (!m || !Array.isArray(m.tracks) || m.tracks.length !== 8) return { valid: false, errors: ['A set must contain eight tracks.'], warnings, usage };
  ck(int(m.bpmX100, 2000, 30000), 'Tempo must be 20–300 BPM.'); ck(int(m.swing, 50, 80), 'Swing must be 50–80%.');
  ck(int(m.link, 0, 1), 'Link must be 0 or 1.'); ck(Array.isArray(m.key) && int(m.key[0], 0, 11) && int(m.key[1], 0, 7), 'Invalid project key.');
  ck(int(m.defaultQuant, 0, 100), 'Invalid default quantize.'); ck(int(m.songEnd, 0, 2), 'Invalid song ending.');
  ck(Array.isArray(m.song) && m.song.length <= 64 && m.song.every(s => int(s, 0, 7)), 'Song exceeds 64 presses or has an invalid scene.');
  usage.song = m.song?.length || 0;
  ck(Array.isArray(m.sceneNames) && m.sceneNames.length === 8 && m.sceneNames.every(s => token(s, 6) && /^[\x21-\x7e]*$/.test(s)), 'Scene names must be up to six printable non-space ASCII characters.');
  ck(Array.isArray(m.unknown) && m.unknown.every(s => typeof s === 'string' && !/[\r\n\x00]/.test(s) && !/^(?:movy1|bpm|swing|link|dq|se|key|sg|sn|tk|rt|pm|ps|au|cl|cp|lk|tg)(?:\s|$)/.test(s.trim())), 'Invalid extension lines.');
  if (m.unknown?.length) warnings.push(`${m.unknown.length} unknown extension lines are preserved; the native sequencer ignores them.`);
  m.tracks.forEach((tr, t) => {
    const prefix = `Track ${t + 1}`;
    if (!tr || !Array.isArray(tr.clips) || tr.clips.length !== 8) { errors.push(`${prefix}: expected eight clip slots.`); return; }
    ck(int(tr.active, 0, 7) && int(tr.muted, 0, 1), `${prefix}: invalid active clip or mute.`);
    ck(Array.isArray(tr.padMutes) && tr.padMutes.length <= 16 && tr.padMutes.every(p => int(p, 0, 127)) && new Set(tr.padMutes).size === tr.padMutes.length, `${prefix}: invalid pad mutes.`);
    ck(tr.padSolo === null || int(tr.padSolo, 0, 127), `${prefix}: invalid pad solo.`);
    ck(tr.route && (tr.route.kind === 0 ? int(tr.route.index, 1, 16) : tr.route.kind === 1 && int(tr.route.index, 0, 3)), `${prefix}: invalid MIDI/sound route.`);
    ck(Array.isArray(tr.lanes) && tr.lanes.length === 8 && tr.lanes.every(l => l === null || (l && int(l.base, 0, 127) && token(l.label, 23))), `${prefix}: invalid automation lane.`);
    tr.clips.forEach((c, s) => {
      if (c === null) return;
      const p = `${prefix}, clip ${s + 1}`; ++usage.clips;
      if (!c || !Array.isArray(c.notes) || !Array.isArray(c.locks) || !Array.isArray(c.trigs)) { errors.push(`${p}: invalid clip.`); return; }
      ck(int(c.length, 1, 256) && int(c.loopStart, 0, 255) && c.length + c.loopStart <= 256, `${p}: clip window exceeds 256 steps.`);
      ck(int(c.scaleNum, 1, 255) && int(c.scaleDen, 1, 255) && c.scaleNum <= 4 * c.scaleDen && c.scaleDen <= 8 * c.scaleNum, `${p}: invalid speed ratio.`);
      ck(int(c.transpose, -36, 36) && int(c.quant, 0, 100), `${p}: invalid transpose/quantize.`);
      ck(c.notes.length <= 512, `${p}: exceeds 512 notes.`); ck(c.locks.length <= 1024, `${p}: exceeds 1024 locks.`); ck(c.trigs.length <= 1024, `${p}: exceeds 1024 trig rows.`);
      usage.notes += c.notes.length; usage.locks += c.locks.length; usage.trigs += c.trigs.length;
      const lockKeys = new Set(), trigKeys = new Set();
      c.notes.forEach(n => {
        ck(n && int(n.tick, 0, 65535) && int(n.gate, 1, 65535) && int(n.pitch, 0, 127) && int(n.vel, 1, 127) && int(n.step, 0, 255), `${p}: invalid note.`);
      });
      c.locks.forEach(l => { ck(l && int(l.lane, 0, 7) && int(l.step, 0, 255) && int(l.value, 0, 127), `${p}: invalid lock.`);
        const k = `${l?.lane}:${l?.step}`; ck(!lockKeys.has(k), `${p}: duplicate lane/step lock.`); lockKeys.add(k); });
      c.trigs.forEach(g => { ck(g && int(g.step, 0, 255) && int(g.lane, -1, 127) && int(g.prob, 0, 100) && int(g.a, 1, 255) && int(g.b, 1, 255) && int(g.invert, 0, 1), `${p}: invalid trig.`);
        const k = `${g?.step}:${g?.lane}`; ck(!trigKeys.has(k), `${p}: duplicate step/pitch trig.`); trigKeys.add(k); });
    });
  });
  for (const k of ['notes', 'locks', 'trigs']) ck(usage[k] <= SEQ_LIMITS[k], `Set uses ${usage[k]} ${k}; native pool holds ${SEQ_LIMITS[k]}.`);
  return { valid: errors.length === 0, errors: [...new Set(errors)], warnings, usage };
}
export function parseSet(input) {
  const text = Array.isArray(input) ? input.join('\n') : input;
  if (typeof text !== 'string' || text.length > 4 * 1024 * 1024) throw new Error('Invalid or oversized movy1 set.');
  const lines = text.split(/\r?\n/); if (lines.shift()?.trim() !== 'movy1') throw new Error('Expected movy1 format tag.');
  const m = emptySet();
  const num = x => { if (!/^[+-]?\d+$/.test(x || '')) throw new Error(`Invalid integer: ${x}`); const n = Number(x); if (!Number.isSafeInteger(n)) throw new Error('Integer is too large.'); return n; };
  lines.forEach((raw, i) => {
    const w = raw.trim().split(/\s+/), tag = w.shift(); if (!tag) return;
    const fail = msg => { throw new Error(`movy1 line ${i + 2}: ${msg}`); };
    const exact = n => { if (w.length !== n) fail(`${tag} requires ${n} fields.`); };
    const nums = () => w.map(num);
    const track = () => { const t = num(w[0]); if (!int(t, 0, 7)) fail('Track is outside 0–7.'); return m.tracks[t]; };
    const clip = () => { const tr = track(), s = num(w[1]); if (!int(s, 0, 7)) fail('Clip is outside 0–7.'); return tr.clips[s] || (tr.clips[s] = emptyClip()); };
    const rows = (text, count, fields) => !text ? [] : text.split(';').map(row => {
      const vals = row.split(':').map(num); if (vals.length < count || vals.length > fields.length) fail('Invalid list row.');
      const out = Object.fromEntries(fields.slice(0, vals.length).map((f, j) => [f, vals[j]]));
      if (tag === 'cl' && vals.length === 4) out.step = Math.floor((out.tick + 12) / 24); return out;
    });
    switch (tag) {
      case 'bpm': case 'swing': case 'link': case 'dq': case 'se': exact(1); m[{ bpm: 'bpmX100', swing: 'swing', link: 'link', dq: 'defaultQuant', se: 'songEnd' }[tag]] = num(w[0]); break;
      case 'key': exact(2); m.key = nums(); break;
      case 'sg': m.song = nums(); break;
      case 'sn': exact(2); if (!int(num(w[0]), 0, 7)) fail('Invalid scene.'); m.sceneNames[num(w[0])] = w[1]; break;
      case 'tk': exact(3); { const tr = track(); tr.active = num(w[1]); tr.muted = num(w[2]); } break;
      case 'rt': exact(3); track().route = { kind: num(w[1]), index: num(w[2]) }; break;
      case 'pm': exact(2); track().padMutes.push(num(w[1])); break;
      case 'ps': exact(2); track().padSolo = num(w[1]); break;
      case 'au': if (w.length < 3 || w.length > 4) fail('Invalid au fields.'); { const l = num(w[1]); if (!int(l, 0, 7)) fail('Invalid lane.'); track().lanes[l] = { base: num(w[2]), label: w[3] || '' }; } break;
      case 'cl': if (w.length < 4 || w.length > 5) fail('Invalid cl fields.'); { const c = clip(); c.length = num(w[2]); c.loopStart = num(w[3]); c.notes = rows(w[4], 4, ['tick', 'gate', 'pitch', 'vel', 'step']); } break;
      case 'cp': if (w.length < 5 || w.length > 6) fail('Invalid cp fields.'); { const c = clip(); [c.scaleNum, c.scaleDen, c.transpose] = w.slice(2, 5).map(num); c.quant = w[5] === undefined ? 0 : num(w[5]); } break;
      case 'lk': case 'tg': if (w.length < 2 || w.length > 3) fail('Invalid list fields.'); { const c = clip(); if (tag === 'lk') c.locks = rows(w[2], 3, ['lane', 'step', 'value']); else c.trigs = rows(w[2], 6, ['step', 'lane', 'prob', 'a', 'b', 'invert']); } break;
      default: m.unknown.push(raw); break;
    }
  });
  const v = validateSet(m); if (!v.valid) throw new Error(v.errors.join('\n')); return m;
}
export function writeSet(m) {
  const v = validateSet(m); if (!v.valid) throw new Error(v.errors.join('\n'));
  const out = ['movy1', `bpm ${m.bpmX100}`, `swing ${m.swing}`, `link ${m.link}`];
  if (m.key[0] || m.key[1]) out.push(`key ${m.key.join(' ')}`); if (m.defaultQuant) out.push(`dq ${m.defaultQuant}`);
  if (m.song.length) out.push(`sg ${m.song.join(' ')}`); if (m.songEnd) out.push(`se ${m.songEnd}`);
  m.sceneNames.forEach((n, s) => { if (n) out.push(`sn ${s} ${n}`); });
  m.tracks.forEach((tr, t) => {
    out.push(`tk ${t} ${tr.active} ${tr.muted}`); tr.padMutes.forEach(p => out.push(`pm ${t} ${p}`)); if (tr.padSolo !== null) out.push(`ps ${t} ${tr.padSolo}`);
    tr.lanes.forEach((l, i) => { if (l) out.push(`au ${t} ${i} ${l.base} ${l.label}`); });
    if (tr.route.kind !== 0 || tr.route.index !== t + 1) out.push(`rt ${t} ${tr.route.kind} ${tr.route.index}`);
    tr.clips.forEach((c, s) => { if (!c) return;
      out.push(`cl ${t} ${s} ${c.length} ${c.loopStart} ${c.notes.map(n => [n.tick, n.gate, n.pitch, n.vel, n.step].join(':')).join(';')}`);
      out.push(`cp ${t} ${s} ${c.scaleNum} ${c.scaleDen} ${c.transpose} ${c.quant}`);
      if (c.locks.length) out.push(`lk ${t} ${s} ${c.locks.map(l => [l.lane, l.step, l.value].join(':')).join(';')}`);
      if (c.trigs.length) out.push(`tg ${t} ${s} ${c.trigs.map(g => [g.step, g.lane, g.prob, g.a, g.b, g.invert].join(':')).join(';')}`);
    });
  });
  out.push(...m.unknown);
  if (new TextEncoder().encode(out.join('\n')).length > 256 * 1024) throw new Error('Set exceeds the native 256 KiB file buffer.');
  return out;
}
export function sceneBars(m, scene) { return Math.max(1, ...m.tracks.map(t => t.clips[scene] ? Math.ceil(t.clips[scene].length / 16) : 1)); }
export function arrangementEntries(m) {
  const entries = []; let startBar = 0;
  m.song.forEach((scene, i) => {
    const last = entries.at(-1); if (last && last.scene === scene) { ++last.presses; last.bars += sceneBars(m, scene); }
    else entries.push({ scene, presses: 1, index: entries.length, songIndex: i, startBar, bars: sceneBars(m, scene) });
    startBar += sceneBars(m, scene);
  }); return entries;
}
