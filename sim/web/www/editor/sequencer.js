// Sequencer workspace. Canonical projects are loaded by the host, never patched
// optimistically in the audio engine. MIT licence, like the rest of Lunar.
import { parseSet, writeSet, validateSet, arrangementEntries } from './sequence-model.js';
import { parseMidi, planMidiImport, applyMidiImport } from './midi-import.js';
import { toPos } from './model.js';

const clone = (x) => structuredClone(x);
const pitchName = (p) => `${['C','C♯','D','E♭','E','F','F♯','G','A♭','A','B♭','B'][p % 12]}${Math.floor(p / 12) - 1}`;
const freshClip = () => ({ length: 16, loopStart: 0, scaleNum: 1, scaleDen: 1, transpose: 0, quant: 0, notes: [], locks: [], trigs: [] });
function el(tag, cls, attrs = {}, children = []) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else if (k === 'text') e.textContent = v;
    else if (v !== undefined && v !== null && v !== false) e.setAttribute(k, v === true ? '' : v);
  }
  for (const child of children.flat()) if (child != null) e.append(child);
  return e;
}
const btn = (text, fn, attrs = {}) => el('button', 'sq-button', { type: 'button', text, onclick: fn, ...attrs });
function field(label, value, change, attrs = {}) {
  const input = el('input', '', { type: 'number', 'aria-label': label, ...attrs });
  input.value = value;
  input.addEventListener('change', () => {
    if (!input.checkValidity()) { input.reportValidity(); return; }
    change(input.type === 'number' ? Number(input.value) : input.value);
  });
  return el('label', 'sq-field', {}, [el('span', '', { text: label }), input]);
}
function choose(label, value, options, change) {
  const select = el('select', '', { 'aria-label': label });
  for (const [id, text] of options) select.append(el('option', '', { value: id, text }));
  select.value = String(value);
  select.addEventListener('change', () => change(select.value));
  return el('label', 'sq-field', {}, [el('span', '', { text: label }), select]);
}

export function makeSequencer(ctx) {
  if (!document.querySelector('link[data-sequencer-style]')) document.head.append(el('link', '', {
    rel: 'stylesheet', href: new URL('sequencer.css', import.meta.url).href, 'data-sequencer-style': true,
  }));
  const root = el('section', 'sq', { 'aria-label': 'Sequencer workspace', 'data-testid': 'sequencer' });
  const status = el('p', 'sq-status', { role: 'status', 'aria-live': 'polite' });
  const content = el('fieldset', 'sq-content');
  const rotate = el('section', 'sq-rotate', { 'data-testid': 'song-rotate-prompt', 'aria-label': 'Rotate phone' }, [
    el('h3', '', { text: 'Turn your phone sideways' }),
    el('p', '', { text: 'Song editing needs landscape on a small phone. Rotate to use scenes, clips and the mixer. Playback keeps its current state.' }),
  ]);
  root.append(status, rotate, content);
  const state = { doc: null, model: null, busy: false, loading: null, dirty: true, track: 0, scene: 0,
    note: -1, page: 0, pitch: 60, low: 48, song: 0, lane: 0, inspector: null, midi: null, solo: null, view: 'Scenes' };
  let disposed = false, pendingFocus = null, suppressNoteClick = false, cancelDrag = null, readError = false;
  const sceneName = (s) => state.model?.sceneNames[s] || `Scene ${s + 1}`;
  const clip = (m = state.model, t = state.track, s = state.scene) => m.tracks[t].clips[s];
  const ensureClip = (m, t, s) => m.tracks[t].clips[s] ||= freshClip();
  function announce(text, error = false) {
    readError = false;
    status.textContent = text; status.classList.toggle('is-error', error); ctx.say?.(text);
  }
  function lock(on) {
    if (on && content.contains(document.activeElement)) { const a = document.activeElement; pendingFocus = a.getAttribute('aria-label'); }
    state.busy = on; content.disabled = on; root.setAttribute('aria-busy', String(on));
    if (!on && pendingFocus) { const e = [...content.querySelectorAll('[aria-label]')].find(e => e.getAttribute('aria-label') === pendingFocus); e?.focus({ preventScroll: true }); pendingFocus = null; }
  }
  async function refresh(force = false) {
    if (state.busy && !force) { state.dirty = true; return; }
    if (state.loading) return state.loading;
    state.loading = (async () => {
      try {
        const doc = await ctx.fetchProject();
        if (disposed) return;
        const selected = state.model && state.note >= 0 ? clip()?.notes[state.note] : null;
        state.doc = doc; state.model = parseSet(doc.set || ['movy1']); state.dirty = false;
        if (selected) state.note = (clip()?.notes || []).findIndex(n => n.tick === selected.tick && n.pitch === selected.pitch);
        if (readError) announce('');
        draw();
      } catch (e) { announce(`Cannot read the sequence: ${e.message}`, true); readError = true; }
      finally { state.loading = null; }
    })();
    return state.loading;
  }
  async function edit(label, change) {
    if (state.busy) return;
    lock(true);
    const before = { solo: clone(state.solo), note: state.note, midi: state.midi, song: state.song };
    try {
      if (state.loading) await state.loading;
      const doc = await ctx.fetchProject();
      const model = parseSet(doc.set || ['movy1']);
      if (model.unknown.length) throw new Error('This set has extension lines the native editor cannot preserve. Export a backup and remove those extensions before editing.');
      await change(model, doc);
      const verdict = validateSet(model);
      if (!verdict.valid) throw new Error(verdict.errors.join('; '));
      doc.set = writeSet(model);
      await ctx.applyProject(doc, label);
      state.model = model;
      await refresh(true); announce(label);
    } catch (e) { Object.assign(state, before); announce(`Not changed: ${e.message}`, true); await refresh(true); }
    finally { lock(false); }
  }
  async function action(fn) {
    if (state.busy || !fn) return;
    lock(true);
    try { await fn(); } catch (e) { announce(e.message, true); } finally { lock(false); }
  }
  function selectClip(t, s, open = false) {
    if (open) state.view = 'Clip';
    state.track = t; state.scene = s; ctx.watchTrack?.(t); state.note = -1; state.page = 0;
    const notes = clip()?.notes || [];
    if (notes.length) { state.pitch = notes[0].pitch; state.low = Math.max(0, Math.min(104, state.pitch - 12)); }
    draw();
  }
  function soundName(i) { const s = state.doc.sounds?.[i]; return `S${i + 1} · ${s?.engine || 'Empty'}`; }
  const routeOptions = () => [...Array.from({ length: 4 }, (_, i) => [`s${i}`, soundName(i)]),
    ...Array.from({ length: 16 }, (_, i) => [`m${i + 1}`, `MIDI channel ${i + 1}`])];
  function openInspector(key) {
    if (ctx.inspector) { state.inspector = state.inspector === key ? null : key; draw(); }
    else ctx.editSound?.(key);
  }
  function toolbar() {
    const m = state.model;
    const file = el('input', 'sq-file', { type: 'file', accept: '.mid,.midi', multiple: true, 'aria-label': 'Import MIDI files' });
    file.addEventListener('change', () => importFiles([...file.files]));
    return el('div', 'sq-toolbar', {}, [
      btn('Play', () => action(ctx.play), { 'data-testid': 'seq-play' }), btn('Stop', () => action(ctx.stop)),
      el('output', 'sq-position', { text: 'Stopped', 'data-play-position': true, 'aria-label': 'Transport position' }),
      field('BPM', m.bpmX100 / 100, v => edit('Change tempo', m => { m.bpmX100 = Math.round(v * 100); }), { min: 20, max: 300, step: .01 }),
      field('Swing %', m.swing, v => edit('Change swing', m => { m.swing = v; }), { min: 50, max: 80, step: 1 }),
      btn('Open…', () => action(ctx.openFile)), btn('Save .lunar', () => action(() => ctx.exportFile?.('lunar'))),
      btn('Export .movy1', () => action(() => ctx.exportFile?.('movy1'))),
      btn('Export WAV…', () => action(ctx.exportAudio)), btn('Import MIDI…', () => file.click()), file,
      btn('Refresh', () => refresh()),
    ]);
  }
  function mixer() {
    return el('div', 'sq-mixer', { 'aria-label': 'Four sound groups' }, Array.from({ length: 4 }, (_, i) => {
      const tracks = state.model.tracks.map((t, n) => t.route.kind === 1 && t.route.index === i ? n : -1).filter(n => n >= 0);
      const muted = tracks.length > 0 && tracks.every(n => state.model.tracks[n].muted);
      return el('section', `sq-sound ed-s${i + 1}`, {}, [
        el('h3', '', { text: soundName(i) }), el('p', 'sq-caption', { text: tracks.length ? `Tracks ${tracks.map(n => n + 1).join(', ')}` : 'No sequencer tracks routed here' }),
        field(`S${i + 1} level %`, state.doc.sounds?.[i]?.level ?? 100, v => edit(`Set S${i + 1} level`, (_m, d) => { d.sounds[i].level = v; }), { min: 0, max: 100, step: 1 }),
        el('div', 'sq-actions', {}, [btn('Mute', () => edit(`Toggle S${i + 1} track mute`, m => { for (const t of tracks) m.tracks[t].muted = muted ? 0 : 1; }), { 'aria-pressed': String(muted), disabled: !tracks.length }),
          btn('Solo', () => edit(`Solo S${i + 1}`, m => {
            if (state.solo?.sound === i) { m.tracks.forEach((t, n) => { t.muted = state.solo.mutes[n]; }); state.solo = null; }
            else { const mutes = state.solo?.mutes || m.tracks.map(t => t.muted); state.solo = { sound: i, mutes }; m.tracks.forEach((t, n) => { t.muted = tracks.includes(n) ? 0 : 1; }); }
          }), { 'aria-pressed': String(state.solo?.sound === i), disabled: !tracks.length }),
          btn('Instrument', () => openInspector(`s${i + 1}`)),
          ...(state.doc.sounds?.[i]?.inserts || []).map((fx, slot) => btn(`Insert ${slot + 1}${fx?.engine ? ' · ' + fx.engine : ' · Empty'}`, () => openInspector(`s${i + 1}.in${slot + 1}`)))]),
      ]);
    }));
  }
  function songView() {
    const entries = arrangementEntries(state.model), selected = entries[state.song];
    const select = choose('Add scene', state.scene, state.model.sceneNames.map((_, s) => [s, sceneName(s)]), v => { state.scene = Number(v); draw(); });
    function alter(label, fn) { edit(label, m => { const es = arrangementEntries(m); fn(es); m.song = es.flatMap(e => Array(e.presses).fill(e.scene)); }); }
    const controls = el('div', 'sq-toolbar', {}, [select,
      btn('Append', () => edit('Append scene to song', m => { m.song.push(state.scene); })),
      btn('Copy entry', () => alter('Copy song entry', es => { if (es[state.song]) es.splice(state.song + 1, 0, clone(es[state.song])); }), { disabled: !selected }),
      btn('Move ←', () => alter('Move song entry earlier', es => { if (state.song > 0) { const e = es.splice(state.song, 1)[0]; es.splice(--state.song, 0, e); } }), { disabled: !selected || !state.song }),
      btn('Move →', () => alter('Move song entry later', es => { if (state.song < es.length - 1) { const e = es.splice(state.song, 1)[0]; es.splice(++state.song, 0, e); } }), { disabled: !selected || state.song === entries.length - 1 }),
      btn('Remove entry', () => alter('Remove song entry', es => { es.splice(state.song, 1); state.song = Math.max(0, state.song - 1); }), { disabled: !selected }),
      selected ? field('Repeats', selected.presses, v => alter('Change scene repeats', es => { es[state.song].presses = v; }), { min: 1, max: 64, step: 1 }) : null,
      choose('Song end', state.model.songEnd, [[0, 'Loop song'], [1, 'Park tracks; keep clock running'], [2, 'Stop']], v => edit('Set song ending', m => { m.songEnd = Number(v); })),
    ]);
    const timeline = el('div', 'sq-song-grid', { 'aria-label': 'Song timeline' });
    const columns = entries.length ? entries : [{ scene: state.scene, presses: 1, startBar: 0, bars: Math.max(1, ...state.model.tracks.map(t => Math.ceil((t.clips[state.scene]?.length || 0) / 16))) }];
    timeline.style.gridTemplateColumns = `170px ${columns.map(e => `${Math.max(100, Math.min(340, e.bars * 22))}px`).join(' ')}`;
    timeline.append(el('div', 'sq-track-head', { text: entries.length ? 'SONG · bars' : 'SCENE · not in song' }));
    columns.forEach((e, i) => timeline.append(btn(`${sceneName(e.scene)} ×${e.presses} · ${e.bars} bars`, () => { state.song = i; selectClip(state.track, e.scene); }, {
      class: `sq-button sq-entry ${state.song === i ? 'is-selected' : ''}`, 'data-song-entry': e.songIndex ?? i, title: `Starts at bar ${e.startBar + 1}`, 'aria-pressed': String(state.song === i),
    })));
    state.model.tracks.forEach((track, t) => {
      const route = track.route, group = route.kind === 1 ? `ed-s${route.index + 1}` : '';
      timeline.append(el('div', `sq-track-head ${group}`, {}, [btn(`Track ${t + 1}`, () => selectClip(t, state.scene)),
        choose(`Track ${t + 1} output`, `${route.kind === 1 ? 's' : 'm'}${route.index}`, routeOptions(), v => edit(`Route track ${t + 1}`, m => { m.tracks[t].route = { kind: v[0] === 's' ? 1 : 0, index: Number(v.slice(1)) }; }))]));
      columns.forEach((e, i) => {
        const c = track.clips[e.scene];
        const cell = btn(c ? `${c.notes.length} notes · ${c.length / 16} bars` : '＋ Empty clip', () => { state.song = i; selectClip(t, e.scene, true); }, {
          class: `sq-button sq-clip ${group} ${t === state.track && e.scene === state.scene ? 'is-selected' : ''}`,
          'aria-label': `Track ${t + 1}, ${sceneName(e.scene)}, ${c ? c.notes.length + ' notes' : 'empty clip'}`, 'data-track': t, 'data-scene': e.scene,
        });
        if (c?.notes.length) cell.append(clipPreview(c));
        timeline.append(cell);
      });
    });
    return el('section', 'sq-section', {}, [el('h3', '', { text: 'Arrangement' }), controls,
      el('div', 'sq-scroll', { 'data-scroll': 'song' }, [timeline]), el('p', 'sq-caption', { text: 'Columns follow the native scene chain. Repeats share their scene clips; edit a copied scene for a different variation.' })]);
  }
  function sceneMatrix() {
    const grid = el('div', 'sq-song-grid sq-scene-grid', { 'aria-label': 'Scene matrix', 'data-testid': 'scene-matrix' });
    grid.style.gridTemplateColumns = '170px repeat(8, 170px)';
    grid.append(el('div', 'sq-track-head', { text: 'SCENES · performance' }));
    for (let scene = 0; scene < 8; scene++) grid.append(el('div', 'sq-scene-head', {}, [
      btn(sceneName(scene), () => selectClip(state.track, scene), { 'aria-label': `Edit scene ${scene + 1}`, 'aria-pressed': String(state.scene === scene) }),
      ctx.playScene ? btn('▶ Launch scene', () => action(() => ctx.playScene(scene)), { 'aria-label': `Launch scene ${scene + 1}` }) : null,
    ]));
    state.model.tracks.forEach((track, t) => {
      const route = track.route, group = route.kind === 1 ? `ed-s${route.index + 1}` : '';
      grid.append(el('div', `sq-track-head ${group}`, {}, [btn(`Track ${t + 1}`, () => selectClip(t, state.scene)),
        choose(`Track ${t + 1} output`, `${route.kind === 1 ? 's' : 'm'}${route.index}`, routeOptions(), v => edit(`Route track ${t + 1}`, m => { m.tracks[t].route = { kind: v[0] === 's' ? 1 : 0, index: Number(v.slice(1)) }; }))]));
      for (let scene = 0; scene < 8; scene++) {
        const c = track.clips[scene];
        const editButton = btn(c ? `${c.notes.length} notes · ${c.length / 16} bars` : '＋ Empty clip', () => selectClip(t, scene, true), {
          'aria-label': `Edit track ${t + 1} scene ${scene + 1}`, 'aria-pressed': String(state.track === t && state.scene === scene),
        });
        if (c?.notes.length) editButton.append(clipPreview(c));
        grid.append(el('div', `sq-matrix-cell ${group}`, { 'data-live-track': t, 'data-live-scene': scene }, [editButton,
          ctx.playClip ? btn(c ? '▶ Launch clip' : '■ Stop track', () => action(() => ctx.playClip(t, scene)), {
            'aria-label': `${c ? 'Launch clip' : 'Stop track'} ${t + 1} scene ${scene + 1}`,
            title: c ? 'Launch this clip at the native bar boundary' : 'Launch the empty slot to stop this track at the native bar boundary',
          }) : null]));
      }
    });
    return el('section', 'sq-section', {}, [el('h3', '', { text: 'Scenes' }),
      el('p', 'sq-caption', { text: 'Edit a clip or launch it separately. Launch a whole column for a scene; empty slots stop those tracks. Manual launches leave song following and keep the saved chain.' }),
      el('div', 'sq-scroll', { 'data-scroll': 'scenes' }, [grid])]);
  }
  function svgNode(tag, attrs = {}) {
    const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) n.setAttribute(key, value);
    return n;
  }
  function clipPreview(c) {
    const svg = svgNode('svg', { viewBox: '0 0 160 32', preserveAspectRatio: 'none', class: 'sq-clip-preview', 'aria-hidden': 'true' });
    const pitches = c.notes.map(n => n.pitch), lo = Math.min(...pitches), hi = Math.max(lo + 1, ...pitches);
    for (const n of c.notes) {
      const x = (n.tick / 24 - c.loopStart) / c.length * 160;
      if (x < 0 || x >= 160) continue;
      svg.append(svgNode('rect', { x, y: 27 - (n.pitch - lo) / (hi - lo) * 24, width: Math.min(160 - x, Math.max(2, n.gate / 24 / c.length * 160)), height: 3, opacity: .35 + n.vel / 127 * .65 }));
    }
    return svg;
  }
  function sceneTools() {
    let target = (state.scene + 1) % 8, track = state.track;
    return el('div', 'sq-toolbar', {}, [
      field('Scene name', state.model.sceneNames[state.scene] || '', v => edit('Rename scene', m => { m.sceneNames[state.scene] = v; }), { type: 'text', maxlength: 6, pattern: '[!-~]{0,6}', title: 'Up to six characters, without spaces' }),
      choose('Copy to scene', target, state.model.sceneNames.map((_, s) => [s, sceneName(s)]), v => { target = Number(v); }),
      choose('Copy to track', track, Array.from({ length: 8 }, (_, i) => [i, `Track ${i + 1}`]), v => { track = Number(v); }),
      btn('Copy clip', () => transferClip(track, target, false)),
      btn('Move clip', () => transferClip(track, target, true)),
      btn('Copy scene', () => edit('Copy scene', m => { if (target === state.scene) throw new Error('Choose a different destination scene.'); m.tracks.forEach(t => { t.clips[target] = clone(t.clips[state.scene]); }); m.sceneNames[target] = m.sceneNames[state.scene]; })),
      btn('Swap scenes', () => edit('Swap scenes', m => {
        if (target === state.scene) throw new Error('Choose a different destination scene.');
        m.tracks.forEach(t => { [t.clips[target], t.clips[state.scene]] = [t.clips[state.scene], t.clips[target]]; if (t.active === target) t.active = state.scene; else if (t.active === state.scene) t.active = target; });
        [m.sceneNames[target], m.sceneNames[state.scene]] = [m.sceneNames[state.scene], m.sceneNames[target]];
        m.song = m.song.map(s => s === target ? state.scene : s === state.scene ? target : s);
      })),
    ]);
  }
  function transferClip(track, scene, move) {
    const sourceTrack = state.track, sourceScene = state.scene;
    edit(move ? 'Move clip' : 'Copy clip', m => {
      if (track === sourceTrack && scene === sourceScene) throw new Error('Choose a different destination.');
      const source = clip(m, sourceTrack, sourceScene);
      if (!source) throw new Error('Select a clip first.');
      if (source.locks.some(l => JSON.stringify(m.tracks[sourceTrack].lanes[l.lane]) !== JSON.stringify(m.tracks[track].lanes[l.lane]))) throw new Error('Destination lock lanes differ. Assign matching lanes before copying this clip.');
      m.tracks[track].clips[scene] = clone(source);
      if (move) m.tracks[sourceTrack].clips[sourceScene] = null;
    });
  }
  function noteEdit(patch, label = 'Edit note') {
    const original = clone(clip().notes[state.note]), t = state.track, s = state.scene;
    edit(label, m => {
      const c = clip(m, t, s), n = c?.notes.find(n => JSON.stringify(n) === JSON.stringify(original));
      if (!n) throw new Error('This note changed elsewhere. Select it again.');
      const previous = { step: n.step, pitch: n.pitch };
      Object.assign(n, patch);
      state.note = c.notes.indexOf(n);
      for (const trig of c.trigs) if (trig.step === previous.step && trig.lane === previous.pitch) { trig.step = n.step; trig.lane = n.pitch; }
    });
  }
  function pianoRoll(c) {
    const start = state.page * 32, end = Math.min(start + 32, c.loopStart + c.length), count = Math.max(1, end - start);
    const canvas = el('div', 'sq-roll', { 'aria-label': 'Piano roll', 'data-testid': 'piano-roll' });
    canvas.style.setProperty('--steps', count);
    const ruler = el('div', 'sq-ruler', {}, [el('span', '', { text: 'Pitch' })]);
    for (let step = start; step < end; ++step) ruler.append(el('span', '', { text: step % 4 === 0 ? `${Math.floor(step / 16) + 1}.${step % 16 / 4 + 1}` : '·' }));
    canvas.append(ruler, el('div', 'sq-playhead', { 'aria-hidden': 'true', 'data-roll-playhead': true }));
    for (let pitch = state.low + 23; pitch >= state.low; --pitch) {
      const row = el('div', `sq-pitch-row ${[1,3,6,8,10].includes(pitch % 12) ? 'is-black' : ''}`);
      row.append(btn(pitchName(pitch), () => { state.pitch = pitch; draw(); }, { 'aria-label': `Use ${pitchName(pitch)} for new notes` }));
      const lane = el('div', 'sq-note-lane', { onclick: e => {
        if (e.target !== lane || state.busy) return;
        const step = start + Math.min(count - 1, Math.floor((e.clientX - lane.getBoundingClientRect().left) / 28));
        if (step >= c.loopStart) addNote(step, pitch);
      } });
      c.notes.forEach((n, i) => {
        if (n.pitch !== pitch || n.tick / 24 >= end || (n.tick + n.gate) / 24 <= start) return;
        const left = Math.max(0, n.tick / 24 - start), right = Math.min(count, (n.tick + n.gate) / 24 - start);
        const b = btn(`${n.vel}`, e => { e.stopPropagation(); if (suppressNoteClick) { suppressNoteClick = false; return; } state.note = i; state.pitch = n.pitch; draw(); }, {
          class: `sq-note ${state.note === i ? 'is-selected' : ''}`, 'aria-label': `${pitchName(pitch)}, step ${n.step + 1}, gate ${n.gate} ticks, velocity ${n.vel}`,
          'data-note': i, title: `${pitchName(pitch)} · velocity ${n.vel} · gate ${n.gate}`,
        });
        b.style.left = `${left * 28}px`; b.style.width = `${Math.max(8, (right - left) * 28 - 2)}px`;
        b.addEventListener('pointerdown', e => beginNoteDrag(e, n, i, c, false));
        b.append(el('span', 'sq-note-resize', { 'aria-hidden': 'true', 'data-resize-note': i, title: 'Drag to resize gate', onpointerdown: e => { e.stopPropagation(); beginNoteDrag(e, n, i, c, true); } }));
        lane.append(b);
      });
      row.append(lane); canvas.append(row);
    }
    const steps = el('div', 'sq-step-grid', { 'aria-label': `Step editor for ${pitchName(state.pitch)}` });
    for (let s = start; s < end; ++s) {
      const index = c.notes.findIndex(n => n.step === s && n.pitch === state.pitch);
      steps.append(btn(String(s + 1), () => { if (index < 0) addNote(s, state.pitch); else { state.note = index; draw(); } }, {
        class: `sq-button sq-step ${index >= 0 ? 'is-filled' : ''}`, 'aria-label': `Step ${s + 1}, ${pitchName(state.pitch)}${index >= 0 ? ', select note' : ', add note'}`, 'data-step': s, disabled: s < c.loopStart,
      }));
    }
    return el('div', '', {}, [el('div', 'sq-scroll', { 'data-scroll': 'piano' }, [canvas]), el('div', 'sq-scroll', { 'data-scroll': 'steps' }, [steps])]);
  }
  function beginNoteDrag(e, note, index, c, resize) {
    if (state.busy || e.button !== 0) return;
    const x = e.clientX, y = e.clientY, node = e.currentTarget.closest('.sq-note');
    let moved = false, dx = 0, dy = 0;
    const originalLeft = node.style.left, originalWidth = node.style.width;
    const abort = new AbortController(); cancelDrag?.(); cancelDrag = () => { abort.abort(); node.style.left = originalLeft; node.style.width = originalWidth; node.style.transform = ''; };
    window.addEventListener('pointermove', ev => {
      dx = Math.round((ev.clientX - x) / 28); dy = Math.round((y - ev.clientY) / 28);
      if (Math.abs(ev.clientX - x) + Math.abs(ev.clientY - y) < 5) return;
      moved = true; ev.preventDefault();
      if (resize) node.style.width = `${Math.max(8, parseFloat(originalWidth) + dx * 28)}px`;
      else node.style.transform = `translate(${dx * 28}px, ${-dy * 28}px)`;
    }, { signal: abort.signal, passive: false });
    window.addEventListener('pointerup', () => {
      cancelDrag?.(); cancelDrag = null;
      if (!moved) return;
      if (JSON.stringify(clip()?.notes[index]) !== JSON.stringify(note)) { announce('This note changed during the drag. Select it again.', true); return; }
      suppressNoteClick = true; state.note = index;
      // Keep explicit native step anchoring and existing microtiming when moving.
      if (resize) noteEdit({ gate: Math.max(1, Math.min(65535, note.gate + dx * 24)) }, 'Resize note gate');
      else {
        const step = Math.max(c.loopStart, Math.min(c.loopStart + c.length - 1, note.step + dx));
        noteEdit({ step, tick: Math.max(0, step * 24 + note.tick - note.step * 24), pitch: Math.max(0, Math.min(127, note.pitch + dy)) }, 'Move note');
      }
      setTimeout(() => { suppressNoteClick = false; }, 0);
    }, { signal: abort.signal, once: true });
    window.addEventListener('pointercancel', () => { cancelDrag?.(); cancelDrag = null; }, {signal:abort.signal,once:true});
  }
  function addNote(step, pitch) {
    const t = state.track, s = state.scene;
    edit('Add note', m => { const c = ensureClip(m, t, s); c.notes.push({ tick: step * 24, gate: 24, pitch, vel: 96, step }); state.note = c.notes.length - 1; });
  }
  function noteDetails(c) {
    const n = c.notes[state.note];
    if (!n) return el('p', 'sq-caption', { text: 'Click an empty piano-roll cell or step to add a note. Select a note to edit its gate, velocity, probability and microtiming.' });
    const trig = c.trigs.find(t => t.step === n.step && t.lane === n.pitch);
    return el('div', 'sq-toolbar sq-note-details', { 'aria-label': 'Selected note' }, [
      field('MIDI pitch', n.pitch, v => noteEdit({ pitch: v }), { min: 0, max: 127, step: 1 }),
      field('Step', n.step + 1, v => noteEdit({ step: v - 1, tick: (v - 1) * 24 + n.tick - n.step * 24 }), { min: c.loopStart + 1, max: c.loopStart + c.length, step: 1 }),
      field('Gate · ticks', n.gate, v => noteEdit({ gate: v }), { min: 1, max: 65535, step: 1 }),
      field('Velocity', n.vel, v => noteEdit({ vel: v }), { min: 1, max: 127, step: 1 }),
      field('Microtiming · ticks', n.tick - n.step * 24, v => noteEdit({ tick: n.step * 24 + v }), { min: Math.max(-23, -n.step * 24), max: 23, step: 1 }),
      field('Probability %', trig?.prob ?? 100, v => edit('Set note probability', m => {
        const c = clip(m);
        if (!c?.notes.some(x => JSON.stringify(x) === JSON.stringify(n))) throw new Error('This note changed elsewhere. Select it again.');
        let t = c.trigs.find(t => t.step === n.step && t.lane === n.pitch);
        if (!t) { t = { step: n.step, lane: n.pitch, prob: v, a: 1, b: 1, invert: 0 }; c.trigs.push(t); } else t.prob = v;
      }), { min: 0, max: 100, step: 1 }),
      btn('Delete note', () => edit('Delete note', m => { const c = clip(m), i = c.notes.findIndex(x => JSON.stringify(x) === JSON.stringify(n)); if (i < 0) throw new Error('Note changed elsewhere.'); c.notes.splice(i, 1); c.trigs = c.trigs.filter(t => t.step !== n.step || t.lane !== n.pitch); state.note = -1; })),
    ]);
  }
  function locksView(c) {
    const track = state.model.tracks[state.track], lane = state.lane;
    const assigned = track.lanes[lane], sound = track.route.kind === 1 ? state.doc.sounds[track.route.index] : null;
    const meta = ctx.getMetadata?.() || ctx.metadata;
    const parameterOptions = (block, prefix) => (meta?.engine?.(block?.engine)?.params || [])
      .filter(p => !(p.flags || []).some(f => ['nolock', 'per_focus', 'focus'].includes(f)))
      .map(p => {
        const raw = block.params?.[p.name] ?? p.def;
        const entry = p.type === 'enum' ? (p.entries || []).indexOf(String(raw)) : -1;
        const value = entry >= 0 ? entry : Number.isFinite(Number(raw)) ? Number(raw) : p.def;
        const base = p.type === 'enum'
          ? Math.ceil(Math.max(0, Math.min(p.max - p.min, Math.round(value - p.min))) * 128 / (p.max - p.min + 1))
          : Math.round(toPos(p, value) * 127);
        return { label: `${prefix}:${p.name.replaceAll(' ', '_')}`, name: p.name, base: Math.min(127, base) };
      })
      .filter(p => /^[!-~]{1,23}$/.test(p.label));
    const targets = [];
    if (sound) {
      targets.push({ id: 'synth', name: 'Instrument', params: parameterOptions(sound, 'synth') });
      (sound.inserts || []).forEach((fx, i) => targets.push({ id: `in${i + 1}`, name: `Sound insert ${i + 1}`, params: parameterOptions(fx, `in${i + 1}`) }));
      targets.push({ id: 'mix', name: 'Sound level', params: [{label:'mix:Level',name:'Level',base:Math.round((sound.level ?? 100) * 127 / 100)}] });
    }
    (state.doc.master || []).forEach((fx, i) => targets.push({ id: `m${i + 1}`, name: `Master effect ${i + 1}`, params: parameterOptions(fx, `m${i + 1}`) }));
    const targetId = assigned ? (assigned.label.includes(':') ? assigned.label.split(':')[0] : 'synth') : targets.find(t => t.params.length)?.id;
    if (assigned && !targets.some(t => t.id === targetId)) targets.push({id:targetId,name:`Existing ${targetId}`,params:[]});
    const target = targets.find(t => t.id === targetId);
    const params = [...(target?.params || [])];
    if (assigned && !params.some(p => p.label === assigned.label)) params.unshift({label:assigned.label,name:`Existing · ${assigned.label}`});
    const assign = label => edit('Assign lock parameter', m => {
      const param = targets.flatMap(t => t.params).find(p => p.label === label);
      m.tracks[state.track].lanes[lane] = { label, base: assigned?.label === label ? assigned.base : param?.base ?? 64 };
    });
    const start = state.page * 32, end = Math.min(start + 32, c.loopStart + c.length);
    const controls = el('div', 'sq-toolbar', {}, [
      choose('Lock lane', lane, Array.from({ length: 8 }, (_, i) => [i, `Lane ${i + 1}${track.lanes[i] ? ' · ' + track.lanes[i].label : ''}`]), v => { state.lane = Number(v); draw(); }),
      targets.some(t => t.params.length) ? choose('Automation target', targetId, targets.filter(t => t.params.length || t.id === targetId).map(t => [t.id,t.name]), v => { const p = targets.find(t => t.id === v)?.params[0]; if (p) assign(p.label); }) : null,
      params.length ? choose('Parameter', assigned?.label || params[0].label, params.map(p => [p.label,p.name]), assign) : null,
      !assigned && params.length ? btn('Assign parameter', () => assign(params[0].label)) : null,
      assigned ? field('Base · 0–127', assigned.base, v => edit('Set lane base', m => { m.tracks[state.track].lanes[lane].base = v; }), { min: 0, max: 127, step: 1 }) : null,
    ]);
    const points = el('div', 'sq-lock-grid');
    if (assigned) for (let step = start; step < end; step++) {
      const found = c.locks.find(l => l.lane === lane && l.step === step);
      const input = el('input', '', { type: 'number', min: 0, max: 127, step: 1, placeholder: '—', 'aria-label': `Lane ${lane + 1}, step ${step + 1} lock`, title: 'Clear the field to remove this lock' });
      input.value = found?.value ?? '';
      input.addEventListener('change', () => { if (!input.checkValidity()) return input.reportValidity(); edit('Edit parameter lock', m => {
        const c = clip(m); c.locks = c.locks.filter(l => l.lane !== lane || l.step !== step);
        if (input.value !== '') c.locks.push({ lane, step, value: Number(input.value) });
      }); });
      points.append(el('label', 'sq-lock', {}, [el('span', '', { text: step + 1 }), input]));
    }
    return el('section', 'sq-section', {}, [el('h3', '', { text: 'Parameter locks' }), controls,
      el('div', 'sq-scroll', { 'data-scroll': 'locks' }, [assigned ? lockPlot(c, lane, assigned.base, start, end) : '', points]),
      el('p', 'sq-caption', { text: 'Locks use a 0–127 scale across the target’s parameter range. Blank steps use the last value. Inserts and level follow this track’s sound route; master-effect lanes control the shared master effects.' })]);
  }
  function lockPlot(c, lane, base, start, end) {
    const width = Math.max(1, end - start) * 55 + 12;
    const svg = svgNode('svg', { viewBox: `0 0 ${width} 80`, width, height: 80, class: 'sq-lock-plot', role: 'img', 'aria-label': 'Held automation values; changes occur at step boundaries' });
    const locks = c.locks.filter(l => l.lane === lane).sort((a,b) => a.step - b.step);
    let value = base;
    for (const l of locks) if (l.step < start) value = l.value;
    const y = v => 72 - v / 127 * 64;
    let path = `M 8 ${y(value)}`;
    for (let step = start; step < end; step++) {
      const point = locks.find(l => l.step === step), x = 8 + (step - start) * 55;
      if (point) { value = point.value; path += ` H ${x} V ${y(value)}`; }
      path += ` H ${x + 55}`;
      svg.append(svgNode('path', {d:`M ${x} 8 V 72`,class:'sq-lock-guide'}));
    }
    svg.append(svgNode('path', { d:path, class:'sq-lock-line' }));
    return svg;
  }
  function clipView() {
    const c = clip();
    if (!c) return el('section', 'sq-section', {}, [sceneTools(), btn('Create clip', () => edit('Create clip', m => { ensureClip(m, state.track, state.scene); }))]);
    state.page = Math.min(state.page, Math.floor((c.loopStart + c.length - 1) / 32));
    const controls = el('div', 'sq-toolbar', {}, [
      el('h3', '', { text: `Track ${state.track + 1} · ${sceneName(state.scene)}` }),
      field('Loop start · step', c.loopStart + 1, v => edit('Set clip loop start', m => { clip(m).loopStart = v - 1; }), { min: 1, max: 256, step: 1 }),
      field('Loop length · steps', c.length, v => edit('Set clip loop length', m => { clip(m).length = v; }), { min: 1, max: 256 - c.loopStart, step: 1 }),
      field('Quantize %', c.quant, v => edit('Set clip quantize', m => { clip(m).quant = v; }), { min: 0, max: 100, step: 1 }),
      field('Transpose', c.transpose, v => edit('Transpose clip', m => { clip(m).transpose = v; }), { min: -36, max: 36, step: 1 }),
      field('New note pitch', state.pitch, v => { state.pitch = v; state.low = Math.max(0, Math.min(104, v - 12)); draw(); }, { min: 0, max: 127, step: 1 }),
      btn('Add note', () => addNote(Math.max(c.loopStart, state.page * 32), state.pitch)),
      btn('Delete clip', () => edit('Delete clip', m => { m.tracks[state.track].clips[state.scene] = null; state.note = -1; })),
      btn('◀ 2 bars', () => { state.page--; draw(); }, { disabled: state.page === 0 }),
      el('span', 'sq-caption', { text: `Steps ${state.page * 32 + 1}–${Math.min((state.page + 1) * 32, c.loopStart + c.length)}` }),
      btn('2 bars ▶', () => { state.page++; draw(); }, { disabled: (state.page + 1) * 32 >= c.loopStart + c.length }),
      btn('Octave ↓', () => { state.low = Math.max(0, state.low - 12); draw(); }, { disabled: state.low === 0 }),
      btn('Octave ↑', () => { state.low = Math.min(104, state.low + 12); draw(); }, { disabled: state.low === 104 }),
    ]);
    return el('section', 'sq-section', {}, [sceneTools(), controls, noteDetails(c), pianoRoll(c)]);
  }
  async function importFiles(files) {
    if (state.busy || !files.length) return;
    await action(async () => {
      const parsed = [];
      for (const f of files) { if (!/\.midi?$/i.test(f.name)) throw new Error('Choose .mid or .midi files.'); if (f.size > 8 * 1024 * 1024) throw new Error('MIDI file exceeds 8 MB.'); parsed.push(parseMidi(new Uint8Array(await f.arrayBuffer()), f.name)); }
      state.midi = { files: parsed, mode: 'scene', bars: 4, tempoPolicy: 'reject', onlyEmpty: true, mapping: parsed.flatMap((f, fileIndex) => f.parts.map(p => ({ fileIndex, partId: p.id, track: 0, sound: 0 }))) };
      state.midi.mapping.forEach((m, i) => { m.track = i < 8 ? i : -1; m.sound = i % 4; }); draw();
    });
  }
  function midiView() {
    const m = state.midi;
    if (!m) return null;
    const mapping = m.mapping.filter(x => x.track >= 0);
    let plan;
    try { plan = planMidiImport(m.files, { barsPerScene: m.bars, mode: m.mode, scene: state.scene, tempoPolicy: m.tempoPolicy, mapping }); }
    catch (e) { plan = { valid: false, errors: [e.message], warnings: [] }; }
    const rows = m.mapping.map((r, i) => {
      const part = m.files[r.fileIndex].parts.find(p => p.id === r.partId);
      return el('div', 'sq-midi-row', {}, [el('span', '', { text: `${m.files[r.fileIndex].name} · ${part.name || 'Part'} · Ch ${part.channel}${part.drums ? ' · Drums' : ''} · ${part.notes.length} notes` }),
        choose(`Part ${i + 1} target track`, r.track, [[-1, 'Skip'], ...Array.from({ length: 8 }, (_, t) => [t, `Track ${t + 1}`])], v => { r.track = Number(v); draw(); }),
        choose(`Part ${i + 1} sound`, r.sound, Array.from({ length: 4 }, (_, s) => [s, soundName(s)]), v => { r.sound = Number(v); draw(); })]);
    });
    return el('section', 'sq-section sq-import', { 'aria-label': 'MIDI import preview', 'data-testid': 'midi-import-preview' }, [
      el('h3', '', { text: 'MIDI import · review mapping' }),
      el('div', 'sq-toolbar', {}, [choose('Import into', m.mode, [['scene', `Selected scene · ${sceneName(state.scene)}`], ['song', 'New song chain on mapped tracks']], v => { m.mode = v; draw(); }),
        field('Bars per scene', m.bars, v => { m.bars = v; draw(); }, { min: 1, max: 16, step: 1 }),
        choose('Existing clips', m.onlyEmpty ? 'empty' : 'replace', [['empty', 'Merge into empty slots only'], ['replace', 'Replace mapped clips']], v => { m.onlyEmpty = v === 'empty'; draw(); }),
        choose('Tempo changes', m.tempoPolicy, [['reject', 'Reject tempo changes'], ['first', 'Use first tempo']], v => { m.tempoPolicy = v; draw(); })]),
      ...rows, el('p', 'sq-caption', { text: [...(plan.errors || []), ...(plan.warnings || [])].join(' · ') || 'Mapping fits the import plan. Unmapped tracks and sound patches are kept.' }),
      el('div', 'sq-actions', {}, [btn('Apply MIDI import', () => edit('Import MIDI', model => {
        const next = applyMidiImport(model, plan, { onlyEmpty: m.onlyEmpty }); Object.assign(model, next); state.midi = null; state.note = -1;
      }), { disabled: !plan.valid || !mapping.length, 'data-testid': 'apply-midi-import' }), btn('Cancel import', () => { state.midi = null; draw(); })]),
    ]);
  }
  function draw() {
    if (!state.model || disposed) return;
    const active = content.contains(document.activeElement) ? document.activeElement : null;
    const focus = active && { label: active.getAttribute('aria-label'), tag: active.tagName, value: active.value, start: active.selectionStart, end: active.selectionEnd };
    const scrolls = new Map([...content.querySelectorAll('[data-scroll]')].map(e => [e.dataset.scroll, [e.scrollLeft, e.scrollTop]]));
    const views = ['Scenes', 'Arrangement', 'Clip', 'Automation', 'Mixer'];
    const navigation = el('div', 'sq-tabs', { role: 'tablist', 'aria-label': 'Song workspace views' }, views.map(name => btn(name, () => {
      state.view = name; state.inspector = null; draw(); root.querySelector(`[data-view="${name}"]`)?.focus({preventScroll:true});
    }, { role: 'tab', id: `sq-tab-${name}`, 'data-view': name, 'aria-selected': String(state.view === name),
      'aria-controls': 'sq-view-panel', tabindex: state.view === name ? 0 : -1,
      onkeydown: e => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
        e.preventDefault(); e.stopPropagation();
        const i = views.indexOf(name), next = e.key === 'Home' ? 0 : e.key === 'End' ? 4 : (i + (e.key === 'ArrowRight' ? 1 : 4)) % 5;
        state.view = views[next]; state.inspector = null; draw(); root.querySelector(`[data-view="${state.view}"]`)?.focus({preventScroll:true});
      },
    })));
    const selection = el('div', 'sq-toolbar sq-selection', {}, [
      choose('Edit track', state.track, Array.from({length:8}, (_, t) => [t, `Track ${t + 1}`]), v => selectClip(Number(v), state.scene)),
      choose('Edit scene', state.scene, state.model.sceneNames.map((_, s) => [s, sceneName(s)]), v => selectClip(state.track, Number(v))),
      ctx.playScene ? btn('Launch scene', () => action(() => ctx.playScene(state.scene)), { 'data-testid': 'launch-scene' }) : null,
    ]);
    let body;
    if (state.view === 'Scenes') body = sceneMatrix();
    else if (state.view === 'Arrangement') body = songView();
    else if (state.view === 'Clip') body = clipView();
    else if (state.view === 'Automation') {
      const c = clip();
      body = c ? el('div', '', {}, [el('div', 'sq-toolbar', {}, [
        btn('◀ 2 bars', () => { state.page--; draw(); }, { disabled: state.page === 0 }),
        el('span', 'sq-caption', { text: `Steps ${state.page * 32 + 1}–${Math.min((state.page + 1) * 32, c.loopStart + c.length)}` }),
        btn('2 bars ▶', () => { state.page++; draw(); }, { disabled: (state.page + 1) * 32 >= c.loopStart + c.length }),
      ]), locksView(c)]) : el('p', 'sq-caption', { text: 'Create a clip in Clip view before editing automation.' });
    } else body = el('div', '', {}, [mixer(), el('div', 'sq-toolbar', {}, [
      ctx.getMaster && ctx.setMaster ? field('Output level %', Math.round(ctx.getMaster() * 100), v => action(() => ctx.setMaster(v / 100)), { min:0, max:100, step:1, title:'Playback preference; not saved in the project' }) : null,
      btn('Master FX 1', () => openInspector('m1')), btn('Master FX 2', () => openInspector('m2'))])]);
    content.replaceChildren(toolbar(), navigation, selection, midiView() || '',
      el('div', 'sq-view-panel', {id:'sq-view-panel',role:'tabpanel','aria-labelledby':`sq-tab-${state.view}`}, [body]));
    if (state.inspector && ctx.inspector) {
      const body = ctx.inspector(state.inspector);
      if (body) content.append(el('section', 'sq-inspector', {}, [btn('Close inspector', () => { state.inspector = null; draw(); }), body]));
    }
    for (const e of content.querySelectorAll('[data-scroll]')) { const p = scrolls.get(e.dataset.scroll); if (p) { e.scrollLeft = p[0]; e.scrollTop = p[1]; } }
    content.disabled = state.busy;
    if (focus?.label) {
      const next = [...content.querySelectorAll('[aria-label]')].find(e => e.tagName === focus.tag && e.getAttribute('aria-label') === focus.label);
      if (next && !state.busy) { next.focus({ preventScroll: true }); if (focus.start != null && next.setSelectionRange) { next.value = focus.value; next.setSelectionRange(focus.start, focus.end); } }
    }
    update();
  }
  function update(transport = ctx.getTransport?.()) {
    const pos = root.querySelector('[data-play-position]');
    for (const e of root.querySelectorAll('[data-song-entry]')) e.classList.toggle('is-playing', !!transport?.playing && Number(e.dataset.songEntry) === transport.songIndex);
    for (const e of root.querySelectorAll('[data-live-track]')) {
      const t = transport?.tracks?.[Number(e.dataset.liveTrack)], scene = Number(e.dataset.liveScene);
      e.classList.toggle('is-playing', !!transport?.playing && t?.playing === scene);
    }
    const watched = transport?.tracks?.[state.track];
    const liveScene = (transport?.playing ? watched?.playing : watched?.active) ?? transport?.scene;
    const liveStep = watched ? Math.floor(watched.posTick / 24) : transport?.step;
    if (pos && transport) pos.textContent = transport.playing ? `Playing · Scene ${(liveScene ?? 0) + 1} · Step ${(liveStep ?? 0) + 1}` : 'Stopped';
    const playhead = root.querySelector('[data-roll-playhead]');
    if (playhead) { playhead.hidden = !transport?.playing || liveScene !== state.scene || liveStep < state.page * 32 || liveStep >= (state.page + 1) * 32; playhead.style.left = `${60 + (liveStep - state.page * 32) * 28}px`; }
    for (const e of root.querySelectorAll('[data-step]')) e.classList.toggle('is-playing', !!transport?.playing && liveScene === state.scene && Number(e.dataset.step) === liveStep);
  }
  root.addEventListener('keydown', e => { if (e.target.closest('input, select, textarea')) e.stopPropagation(); });
  root.addEventListener('dragover', e => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { e.preventDefault(); e.stopPropagation(); } });
  root.addEventListener('drop', e => {
    const files = [...(e.dataTransfer?.files || [])];
    if (!files.length || !files.every(f => /\.midi?$/i.test(f.name))) return;
    e.preventDefault(); e.stopPropagation(); e.lunarInto = true; importFiles(files);
  });
  return { render() { if (state.dirty && !state.busy) refresh(); return root; }, refresh, update,
    invalidate() { state.dirty = true; }, destroy() { disposed = true; cancelDrag?.(); root.remove(); } };
}
