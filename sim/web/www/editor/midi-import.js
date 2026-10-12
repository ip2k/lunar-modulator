// Standard MIDI File 0/1 importer. Reference: MIDI Association SMF specification
// https://midi.org/standard-midi-files. Bounded reader; no device/vendor commands.
import { emptySet, emptyClip, cloneSet, validateSet, sceneBars } from './sequence-model.js';
export const MIDI_IMPORT_LIMITS = Object.freeze({ files: 16, fileBytes: 16 * 1024 * 1024,
  batchBytes: 32 * 1024 * 1024, parts: 64 });
const MAX_BYTES = MIDI_IMPORT_LIMITS.fileBytes, MAX_EVENTS = 250000, MAX_NOTES = 100000;
const integer = (n, lo, hi) => Number.isSafeInteger(n) && n >= lo && n <= hi;
export function checkMidiFiles(files) {
  if (files.length > MIDI_IMPORT_LIMITS.files) throw new Error('Import at most 16 MIDI files at once; split this batch.');
  let bytes = 0;
  for (const file of files) {
    if (!/\.midi?$/i.test(file.name)) throw new Error('Choose .mid or .midi files.');
    if (!integer(file.size, 0, MAX_BYTES)) throw new Error('Each MIDI file must be at most 16 MiB.');
    bytes += file.size;
    if (bytes > MIDI_IMPORT_LIMITS.batchBytes) throw new Error('MIDI batch exceeds 32 MiB; split this batch.');
  }
}
export function checkMidiParts(files) {
  if (files.length > MIDI_IMPORT_LIMITS.files) throw new Error('Import at most 16 MIDI files at once; split this batch.');
  if (files.reduce((n, file) => n + file.parts.length, 0) > MIDI_IMPORT_LIMITS.parts)
    throw new Error('MIDI batch exceeds 64 instrument parts; export fewer instruments or split this batch.');
}
class Reader {
  constructor(bytes, start = 0, end = bytes.length) { this.b = bytes; this.p = start; this.end = end; }
  need(n) { if (!integer(n, 0, MAX_BYTES) || n > this.end - this.p) throw new Error(`Truncated MIDI data at byte ${this.p}.`); }
  u8() { this.need(1); return this.b[this.p++]; }
  u16() { return this.u8() * 256 + this.u8(); }
  u32() { return this.u16() * 65536 + this.u16(); }
  data(n) { this.need(n); const out = this.b.subarray(this.p, this.p + n); this.p += n; return out; }
  tag() { return String.fromCharCode(...this.data(4)); }
  vlq() { let n = 0; for (let i = 0; i < 4; ++i) { const b = this.u8(); n = n * 128 + (b & 127); if (!(b & 128)) return n; } throw new Error('MIDI variable-length quantity exceeds four bytes.'); }
}
export function parseMidi(input, name = 'Untitled MIDI') {
  const bytes = input instanceof Uint8Array ? input : input instanceof ArrayBuffer ? new Uint8Array(input) : null;
  if (!bytes || bytes.length > MAX_BYTES) throw new Error('MIDI file must be an ArrayBuffer/Uint8Array of at most 16 MiB.');
  const r = new Reader(bytes); if (r.tag() !== 'MThd') throw new Error('Expected Standard MIDI File MThd header.');
  const headLength = r.u32(); if (headLength < 6) throw new Error('MIDI header is shorter than six bytes.'); r.need(headLength);
  const headEnd = r.p + headLength, format = r.u16(), nTracks = r.u16(), ppqn = r.u16(); r.p = headEnd;
  if (format === 2) throw new Error('MIDI type 2 contains asynchronous patterns; export a type 0 or type 1 song.');
  if (format > 1) throw new Error(`Unsupported MIDI format ${format}.`);
  if (!nTracks || nTracks > 256 || (format === 0 && nTracks !== 1)) throw new Error('Invalid MIDI track count (maximum 256).');
  if (ppqn & 0x8000) throw new Error('SMPTE MIDI timing is unsupported; export using PPQN timing.');
  if (!ppqn) throw new Error('MIDI PPQN must be nonzero.');
  const events = [], metadata = [], tempoMap = [], timeSignatures = [], warnings = [], tracks = [];
  let durationTicks = 0, eventCount = 0, sysex = 0;
  for (let t = 0; t < nTracks; ++t) {
    if (r.tag() !== 'MTrk') throw new Error(`Expected MTrk chunk for track ${t + 1}.`);
    const length = r.u32(); r.need(length); const tr = new Reader(bytes, r.p, r.p + length); r.p += length;
    let tick = 0, running = 0, ended = false; tracks.push({ name: '', instrument: '', end: 0 });
    while (tr.p < tr.end) {
      if (++eventCount > MAX_EVENTS) throw new Error('MIDI exceeds 250,000 events.');
      tick += tr.vlq(); if (tick > 0xffffffff) throw new Error('MIDI absolute tick exceeds 32-bit timing.');
      let status = tr.u8(); if (status < 0x80) { if (!running) throw new Error(`Invalid MIDI running status at byte ${tr.p - 1}.`); --tr.p; status = running; }
      if (status >= 0x80 && status <= 0xef) {
        running = status; const kind = status >> 4, a = tr.u8(), b = kind === 0xc || kind === 0xd ? 0 : tr.u8();
        if (a > 127 || b > 127) throw new Error('MIDI channel event contains a status byte where data was required.');
        events.push({ tick, track: t, order: eventCount, kind, channel: status & 15, a, b });
      } else if (status === 0xff) {
        running = 0; const type = tr.u8(), len = tr.vlq(), data = tr.data(len);
        const need = n => { if (len !== n) throw new Error(`Invalid MIDI meta event 0x${type.toString(16)} length.`); };
        if (type === 0x2f) { need(0); ended = true; if (tr.p !== tr.end) throw new Error('MIDI has data after End of Track.'); }
        else if (type === 0x51) { need(3); const usPerQuarter = data[0] * 65536 + data[1] * 256 + data[2]; if (!usPerQuarter) throw new Error('MIDI tempo must be nonzero.'); tempoMap.push({ tick, usPerQuarter, track: t }); }
        else if (type === 0x58) { need(4); if (!data[0] || data[1] > 7) throw new Error('Invalid MIDI time signature.'); timeSignatures.push({ tick, numerator: data[0], denominator: 2 ** data[1], clocks: data[2], thirtySeconds: data[3], track: t }); }
        else {
          const item = { tick, track: t, type, length: len };
          if (type >= 1 && type <= 9) { item.text = new TextDecoder().decode(data.subarray(0, 4096)); if (len > 4096) warnings.push(`Track ${t + 1}: metadata text preview shortened to 4096 bytes.`); if (type === 3) tracks[t].name = item.text; if (type === 4) tracks[t].instrument = item.text; }
          else item.data = Array.from(data);
          // Keep source bytes when a text preview is shortened or decoded as UTF-8.
          if (type >= 1 && type <= 9) item.data = Array.from(data);
          metadata.push(item);
        }
      } else if (status === 0xf0 || status === 0xf7) { running = 0; const data = tr.data(tr.vlq()); metadata.push({ tick, track: t, kind: 'sysex', status, data: Array.from(data) }); ++sysex; }
      else throw new Error(`Unsupported system status 0x${status.toString(16)} in MIDI track.`);
    }
    if (!ended) throw new Error(`Track ${t + 1} is missing End of Track.`);
    tracks[t].end = tick; durationTicks = Math.max(durationTicks, tick);
  }
  if (r.p !== r.end) throw new Error('Trailing chunks/data after declared MIDI tracks.');
  if (sysex) warnings.push(`${sysex} SysEx events are retained as metadata; instrument/system settings are not applied.`);
  events.sort((a, b) => a.tick - b.tick || a.track - b.track || a.order - b.order);
  const state = Array.from({ length: 16 }, () => ({ program: 0, bank: [0, 0], sustain: false, held: new Map(), deferred: [] }));
  const parts = [], byId = new Map(), controllerCounts = new Map(); let noteCount = 0, unmatched = 0, sustained = 0, unfinished = 0, expression = 0;
  const getPart = e => {
    const s = state[e.channel], id = `${e.track}:${e.channel}:${s.program}:${s.bank[0]}:${s.bank[1]}`;
    if (!byId.has(id)) {
      if (parts.length >= MIDI_IMPORT_LIMITS.parts) throw new Error('MIDI file exceeds 64 instrument parts; export fewer instruments or split this file.');
      const p = { id, track: e.track, channel: e.channel + 1, program: s.program, bank: [...s.bank], drums: e.channel === 9,
      name: tracks[e.track].instrument || tracks[e.track].name || `Track ${e.track + 1}`, notes: [] }; byId.set(id, p); parts.push(p); }
    return byId.get(id);
  };
  const finish = (n, tick) => { n.end = Math.max(n.tick + 1, tick); };
  const releaseDeferred = (s, tick) => { s.deferred.forEach(n => finish(n, tick)); s.deferred = []; };
  for (const e of events) {
    const s = state[e.channel];
    if (e.kind === 0x9 && e.b) {
      if (++noteCount > MAX_NOTES) throw new Error('MIDI exceeds 100,000 notes.');
      const note = { tick: e.tick, end: null, pitch: e.a, vel: e.b }; getPart(e).notes.push(note);
      if (!s.held.has(e.a)) s.held.set(e.a, []); s.held.get(e.a).push(note);
    } else if (e.kind === 0x8 || (e.kind === 0x9 && !e.b)) {
      const queue = s.held.get(e.a); if (!queue?.length) { ++unmatched; continue; }
      const note = queue.shift(); if (s.sustain) { s.deferred.push(note); ++sustained; } else finish(note, e.tick);
    } else if (e.kind === 0xc) s.program = e.a;
    else if (e.kind === 0xb) {
      if (e.a === 0) s.bank[0] = e.b; else if (e.a === 32) s.bank[1] = e.b;
      else if (e.a === 64) { const on = e.b >= 64; if (s.sustain && !on) releaseDeferred(s, e.tick); s.sustain = on; }
      else if (e.a === 120 || e.a === 123) {
        s.held.forEach(queue => queue.forEach(n => { if (e.a === 123 && s.sustain) s.deferred.push(n); else finish(n, e.tick); })); s.held.clear(); if (e.a === 120) releaseDeferred(s, e.tick);
      } else if (e.a === 121) { s.sustain = false; releaseDeferred(s, e.tick); controllerCounts.set(121, (controllerCounts.get(121) || 0) + 1); }
      else controllerCounts.set(e.a, (controllerCounts.get(e.a) || 0) + 1);
    } else if (e.kind === 0xa || e.kind === 0xd || e.kind === 0xe) ++expression;
  }
  state.forEach(s => { s.held.forEach(q => q.forEach(n => { finish(n, durationTicks); ++unfinished; })); unfinished += s.deferred.length; releaseDeferred(s, durationTicks); });
  if (sustained) warnings.push(`Sustain pedal baked into ${sustained} note gates.`);
  if (unfinished) warnings.push(`${unfinished} notes without a final release were closed at the song end.`);
  if (unmatched) warnings.push(`${unmatched} unmatched note-off events were ignored.`);
  if (controllerCounts.size) warnings.push(`Unsupported controllers not applied: ${[...controllerCounts].map(([cc, n]) => `CC${cc} (${n})`).join(', ')}. Automation is retained only as import metadata.`);
  if (expression) warnings.push(`${expression} pitch-bend/pressure events are retained as metadata and are not applied.`);
  parts.forEach(p => { p.notes.sort((a, b) => a.tick - b.tick || a.pitch - b.pitch); for (const n of p.notes) durationTicks = Math.max(durationTicks, n.end); });
  tempoMap.sort((a, b) => a.tick - b.tick || a.track - b.track); timeSignatures.sort((a, b) => a.tick - b.tick || a.track - b.track);
  return { name: String(name), format, ppqn, tracks, parts, tempoMap, timeSignatures, metadata, channelEvents: events, warnings, durationTicks,
    unsupported: { controllers: [...controllerCounts].map(([controller, count]) => ({ controller, count })), expression, sysex } };
}
export function planMidiImport(input, options = {}) {
  const files = Array.isArray(input) ? input : [input], errors = [], warnings = [], set = emptySet();
  checkMidiParts(files);
  const parts = files.flatMap((f, fileIndex) => f.parts.map(p => ({ ...p, fileIndex, fileName: f.name })));
  const partIndex = new Map(parts.map(part => [`${part.fileIndex}/${part.id}`, part]));
  const barsPerScene = options.barsPerScene ?? 4, mode = options.mode ?? 'song', targetScene = options.scene ?? 0;
  if (!integer(barsPerScene, 1, 16)) errors.push('Section length must be 1–16 bars.');
  if (!['song', 'scene'].includes(mode)) errors.push('Import mode must be song or scene.');
  if (!integer(targetScene, 0, 7)) errors.push('Target scene must be 0–7.');
  let mapping = options.mapping;
  if (mapping === undefined) { mapping = parts.slice(0, 8).map((p, track) => ({ fileIndex: p.fileIndex, partId: p.id, track, sound: track % 4 })); if (parts.length > 8) errors.push('More than eight instrument parts: choose an explicit mapping/exclusion for every desired part.'); }
  if (!Array.isArray(mapping)) mapping = [];
  const selected = [], seen = new Set(), usedTracks = new Set();
  mapping.forEach(row => {
    const fileIndex = row.fileIndex ?? 0, part = partIndex.get(`${fileIndex}/${row.partId}`);
    if (!part) { errors.push('Mapping refers to a missing MIDI part.'); return; }
    const id = `${fileIndex}/${part.id}`;
    if (seen.has(id)) errors.push(`Part ${part.name} is mapped more than once.`); seen.add(id);
    if (!integer(row.track, 0, 7) || !integer(row.sound, 0, 3)) { errors.push('Mappings require track 0–7 and sound 0–3.'); return; }
    if (usedTracks.has(row.track)) errors.push('Each MIDI part needs its own sequencer track; merge sources before importing.'); usedTracks.add(row.track);
    selected.push({ part, file: files[fileIndex], track: row.track, sound: row.sound });
  });
  if (!selected.length) errors.push('Choose at least one instrument part.');
  const excluded = parts.filter(p => !seen.has(`${p.fileIndex}/${p.id}`)); if (excluded.length) warnings.push(`${excluded.length} unmapped parts are excluded (${excluded.reduce((n, p) => n + p.notes.length, 0)} notes).`);
  const usedFiles = [...new Set(selected.map(s => s.file))];
  const tempos = [];
  usedFiles.forEach(f => {
    warnings.push(...f.warnings.map(w => `${f.name}: ${w}`));
    const map = f.tempoMap.length ? f.tempoMap : [{ tick: 0, usPerQuarter: 500000 }];
    const initial = map.filter(t => t.tick === 0).at(-1)?.usPerQuarter || 500000; tempos.push(initial);
    if (map.some(t => t.usPerQuarter !== initial)) {
      if (options.tempoPolicy === 'first') warnings.push(`${f.name}: tempo changes replaced by the initial tempo; musical tick positions are retained, elapsed timing changes.`);
      else errors.push(`${f.name}: tempo changes cannot be represented by one project tempo. Choose initial tempo explicitly or export a constant-tempo MIDI.`);
    }
    if (f.timeSignatures.some(ts => ts.numerator !== 4 || ts.denominator !== 4)) errors.push(`${f.name}: only constant 4/4 is supported; MIDI meter is not silently reinterpreted.`);
  });
  if (new Set(tempos).size > 1) { if (options.tempoPolicy === 'first') warnings.push('Batch files have different tempos; all use the first file tempo.'); else errors.push('Batch files have different tempos; choose initial-tempo policy explicitly.'); }
  set.bpmX100 = Math.round(6000000000 / (tempos[0] || 500000));
  if (!integer(set.bpmX100, 2000, 30000)) errors.push('MIDI tempo is outside the native 20–300 BPM range.');
  if (errors.length) return { valid: false, errors, warnings, parts, mapping, mode, targetScene, barsPerScene, scenes: [], set, usage: validateSet(set).usage };
  let duration = 0, rounded = 0;
  const converted = selected.map(({ part, file, track, sound }) => {
    duration = Math.max(duration, Math.round(file.durationTicks * 96 / file.ppqn));
    const notes = part.notes.map(n => {
      const a = n.tick * 96 / file.ppqn, b = n.end * 96 / file.ppqn; if (!Number.isInteger(a) || !Number.isInteger(b)) ++rounded;
      const tick = Math.round(a), end = Math.max(tick + 1, Math.round(b)); duration = Math.max(duration, end);
      return { tick, end, pitch: n.pitch, vel: n.vel };
    });
    return { track, sound, notes };
  });
  const bars = Math.max(1, Math.ceil(duration / 384)), sections = Math.ceil(bars / barsPerScene), scenes = [];
  if (rounded) warnings.push(`${rounded} note timings rounded to the nearest 96 PPQN tick (maximum onset rounding: half a tick).`);
  if (mode === 'scene' && sections > 1) errors.push(`Selected MIDI needs ${bars} bars; one scene holds ${barsPerScene}. Choose song import or a longer section.`);
  if (sections > 64) errors.push(`Import requires ${sections} song presses; the native song holds 64. Increase bars per section.`);
  if (errors.length) return { valid: false, errors, warnings, parts, mapping, mode, targetScene, barsPerScene, scenes, set, usage: validateSet(set).usage };
  const hashes = new Map(); let split = 0, overlaps = 0, maxPolyphony = 0;
  converted.forEach(({ track, sound, notes }) => {
    set.tracks[track].route = { kind: 1, index: sound };
    const active = [], lastEnd = new Map();
    for (const n of notes) { while (active.length && active[0] <= n.tick) active.shift(); active.push(n.end); active.sort((a, b) => a - b); maxPolyphony = Math.max(maxPolyphony, active.length); if ((lastEnd.get(n.pitch) || 0) > n.tick) ++overlaps; lastEnd.set(n.pitch, Math.max(n.end, lastEnd.get(n.pitch) || 0)); }
  });
  for (let section = 0; section < sections; ++section) {
    const startBar = section * barsPerScene, nBars = Math.min(barsPerScene, bars - startBar), start = startBar * 384, end = start + nBars * 384;
    const column = converted.map(({ track, notes }) => {
      const clip = emptyClip(nBars * 16);
      for (const n of notes) if (n.tick < end && n.end > start) {
        const tick = Math.max(n.tick, start) - start, gate = Math.min(n.end, end) - Math.max(n.tick, start);
        if (n.tick < start) ++split;
        clip.notes.push({ tick, gate, pitch: n.pitch, vel: n.vel, step: Math.min(clip.length - 1, Math.floor(tick / 24)) });
      }
      return { track, clip };
    });
    const hash = JSON.stringify(column); let slot = mode === 'scene' ? targetScene : hashes.get(hash);
    if (slot === undefined) {
      slot = hashes.size; if (slot >= 8) { errors.push('Import needs more than eight distinct scene columns. Increase bars per section or simplify the arrangement.'); break; }
      hashes.set(hash, slot);
    }
    if (!scenes.some(s => s.slot === slot)) { scenes.push({ slot, bars: nBars, startBar }); set.sceneNames[slot] = `M${slot + 1}`; column.forEach(({ track, clip }) => { set.tracks[track].clips[slot] = clip; }); }
    if (mode === 'song') set.song.push(slot);
  }
  converted.forEach(({ track }) => { set.tracks[track].active = mode === 'scene' ? targetScene : set.song[0] ?? 0; });
  if (mode === 'song') set.songEnd = 2;
  if (split) warnings.push(`${split} notes crossing scene boundaries split and retrigger at the next scene; gate duration is preserved, attack/legato may change.`);
  if (overlaps) warnings.push(`${overlaps} overlapping repeated pitches retained; sound engines may retrigger or release a shared pitch.`);
  if (maxPolyphony > 64) errors.push(`A part needs ${maxPolyphony} simultaneous notes; the native gate pool holds 64 across all tracks.`);
  // The global gate bound applies across every mapped part, not just each part.
  const polyEvents = converted.flatMap(c => c.notes.flatMap(n => [[n.tick, 1], [n.end, -1]])).sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  let sounding = 0; for (const [, delta] of polyEvents) { sounding += delta; if (sounding > 64) { errors.push('Mapped parts exceed the global 64 sounding-note gate pool.'); break; } }
  const validation = validateSet(set); errors.push(...validation.errors); warnings.push(...validation.warnings);
  return { valid: errors.length === 0, errors: [...new Set(errors)], warnings: [...new Set(warnings)], parts, mapping, mode, targetScene, barsPerScene, scenes, set, usage: validation.usage,
    metadata: files.map(f => ({ name: f.name, format: f.format, ppqn: f.ppqn, tracks: f.tracks, channelEvents: f.channelEvents, tempoMap: f.tempoMap, timeSignatures: f.timeSignatures, metadata: f.metadata, unsupported: f.unsupported })) };
}
// Capacity, not synthesizer voice count. All probability/condition outcomes are
// treated as firing: this may conservatively refuse a safe probabilistic set.
// Import sets swing to 50. Mirror native note_fire (C truncates toward zero),
// pad filtering after transpose, and gate lifetimes measured in *track ticks*.
function importGateCheck(model, scenes) {
  const fail = () => { throw new Error('Combined import may exceed the native 64 sounding-note gate pool and end held notes early. This conservative check assumes every probability/condition fires; shorten gates, reduce overlapping notes, or clear retained clips. Engine voice limits are separate.'); };
  const clips = model.tracks.map(track => track.clips.map(c => {
    if (!c) return null;
    const start = c.loopStart * 24, span = c.length * 24, end = start + span, fires = new Map();
    if (!track.muted) for (const n of c.notes) {
      if (n.step < c.loopStart || n.step >= c.loopStart + c.length) continue;
      const pitch = Math.max(0, Math.min(127, n.pitch + c.transpose));
      if (track.padSolo !== null ? pitch !== track.padSolo : track.padMutes.includes(pitch)) continue;
      const dev = n.tick - n.step * 24;
      let fire = Math.max(start, n.step * 24 + dev - Math.trunc((dev * c.quant + (dev >= 0 ? 50 : -50)) / 100));
      if (fire >= end) fire -= span; // Native folds only once, not modulo.
      if (fire < start || fire >= end) continue;
      if (!fires.has(fire)) fires.set(fire, []);
      fires.get(fire).push(n.gate);
    }
    return { start, span, end, fires, num: c.scaleNum, den: c.scaleDen };
  }));
  // Each selected scene can be launched and loop forever. Sum independent track
  // maxima: speed changes phase, not overlap within a track's own tick clock.
  for (const slot of scenes) {
    let total = 0;
    for (const track of clips) {
      const c = track[slot]; if (!c) continue;
      let base = 0; const events = new Map([[0, 0]]);
      const add = (tick, delta) => events.set(tick, (events.get(tick) || 0) + delta);
      for (const [fire, gates] of c.fires) for (const gate of gates) {
        base += Math.floor(gate / c.span);
        const remainder = gate % c.span, at = fire - c.start;
        if (!remainder) continue;
        add(at, 1); const off = at + remainder;
        if (off >= c.span) { ++base; add(off - c.span, -1); } else add(off, -1);
      }
      let peak = base, live = base;
      for (const [, delta] of [...events].sort((a, b) => a[0] - b[0])) { live += delta; peak = Math.max(peak, live); }
      total += peak;
    }
    if (total > 64) fail();
  }
  // Song boundaries retain held gates, even when the next clip changes speed.
  // Follow native track order: that track's offs precede its ons, while later
  // tracks' old gates still occupy the pool. Equal adjacent presses do not reset.
  if (!model.song.length) return;
  const states = clips.map(() => ({ pos: 0, acc: 0, clock: 0, gates: [] }));
  const seen = new Set(); let count = 0, ticks = 0, previous = -1;
  for (;;) {
    const key = JSON.stringify([previous, states.map(s => [s.pos, s.acc, s.gates.map(g => g - s.clock)])]);
    if (seen.has(key)) return; seen.add(key);
    for (const slot of model.song) {
      if (slot !== previous) states.forEach((s, t) => {
        const c = clips[t][slot]; s.pos = c?.start ?? 0;
        if (!c) { count -= s.gates.length; s.gates = []; }
      });
      previous = slot;
      const duration = sceneBars(model, slot) * 384;
      for (let tick = 0; tick < duration; ++tick) {
        if (++ticks > 1000000) throw new Error('Cannot conservatively prove the merged song fits the 64-gate pool within the bounded import check. Simplify clip speeds or sustained gates before importing.');
        states.forEach((s, t) => {
          const c = clips[t][slot]; if (!c) return;
          s.acc += c.num;
          while (s.acc >= c.den) {
            s.acc -= c.den; ++s.clock;
            while (s.gates.length && s.gates[0] <= s.clock) { s.gates.shift(); --count; }
            for (const gate of c.fires.get(s.pos) || []) {
              if (++count > 64) fail();
              const expiry = s.clock + gate; let i = s.gates.length;
              while (i && s.gates[i - 1] > expiry) --i;
              s.gates.splice(i, 0, expiry);
            }
            if (++s.pos >= c.end) s.pos = c.start;
          }
        });
      }
    }
    if (model.songEnd !== 0) return; // Park and Stop both release every gate.
  }
}
export function applyMidiImport(model, plan, options = {}) {
  if (!plan?.valid) throw new Error(plan?.errors?.join('\n') || 'Invalid MIDI import plan.');
  if (model?.unknown?.length) throw new Error('This set has unknown extension tags; native reload would discard them. Preserve the source before importing.');
  const current = validateSet(model); if (!current.valid) throw new Error(current.errors.join('\n'));
  const out = cloneSet(model), tracks = new Set(plan.mapping.map(m => m.track));
  for (const t of tracks) {
    const target = out.tracks[t], imported = plan.set.tracks[t];
    const slots = plan.mode === 'scene' ? [plan.targetScene] : Array.from({ length: 8 }, (_, s) => s);
    if (options.onlyEmpty && slots.some(s => target.clips[s] !== null)) throw new Error(`Track ${t + 1} target contains a clip; choose an empty target or authorize replacement.`);
    slots.forEach(s => { target.clips[s] = cloneSet(imported.clips[s]); }); target.route = { ...imported.route }; target.active = imported.active; target.muted = 0;
    // Imported tracks are pitched MIDI parts: prior drum pad filters would silently mute them.
    target.padMutes = []; target.padSolo = null;
  }
  out.bpmX100 = plan.set.bpmX100; out.swing = 50;
  plan.scenes.forEach(s => { out.sceneNames[s.slot] = plan.set.sceneNames[s.slot]; });
  if (plan.mode === 'song') { out.song = [...plan.set.song]; out.songEnd = plan.set.songEnd; }
  for (const scene of plan.scenes) if (sceneBars(out, scene.slot) !== scene.bars) throw new Error(`Scene ${scene.slot + 1} contains an unmapped longer clip; its duration would change imported timing. Choose empty targets or clear/resize the existing clip.`);
  const validation = validateSet(out); if (!validation.valid) throw new Error(validation.errors.join('\n'));
  importGateCheck(out, plan.scenes.map(s => s.slot));
  return out;
}
