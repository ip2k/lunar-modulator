// Sequencer workspace. Canonical projects are loaded by the host, never patched
// optimistically in the audio engine. MIT licence, like the rest of Lunar.
import { parseSet, writeSet, validateSet, arrangementEntries } from './sequence-model.js';
import { parseMidi, planMidiImport, applyMidiImport, checkMidiFiles, checkMidiParts } from './midi-import.js';
import { toPos } from './model.js';
import { clipPlayback, automationSteps } from './sequence-playback.js';
import { positionText, timeText, songDuration, barLimit, transportNavigation } from './sequence-transport.js';
import { makeSongShortcuts, noteNudge, duplicateNote } from './song-shortcuts.js';

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
function editableName(label, value, commit, attrs = {}) {
  const input = el('input', 'sq-name', { type: 'text', 'aria-label': label,
    title: 'Double-click to rename; Enter or F2 also edits. Enter or leaving the field saves; Escape cancels.',
    'aria-description': 'Double-click, Enter or F2 edits this name. Enter or leaving the field saves; Escape cancels.', ...attrs });
  input.value = value; input.readOnly = true;
  let editing = false, pointerDown = false, pendingBlur = false, blurTimer = null;
  function cleanup() {
    document.removeEventListener('pointerdown', pointerStart, true);
    document.removeEventListener('mousedown', pointerStart, true);
    document.removeEventListener('mouseup', pointerEnd, true);
    document.removeEventListener('pointerup', pointerEnd, true);
    document.removeEventListener('pointercancel', pointerEnd, true);
    document.removeEventListener('click', pointerClick, true);
    clearTimeout(blurTimer); blurTimer = null; pointerDown = pendingBlur = false;
  }
  function pointerStart() { pointerDown = true; }
  function pointerEnd(e) {
    pointerDown = false;
    if (e.type === 'pointercancel' && pendingBlur) pointerClick();
  }
  function pointerClick() {
    // Wait for the destination's click, including touch's compatibility click,
    // before a native commit disables/redraws the workspace. Keyboard focus
    // changes have no pointer and save directly.
    if (pendingBlur) { pendingBlur = false; blurTimer = setTimeout(() => finish(), 0); }
  }
  function begin() {
    cleanup(); editing = true; input.readOnly = false;
    document.addEventListener('pointerdown', pointerStart, true);
    // Touch focus may happen in compatibility mousedown after pointerup.
    document.addEventListener('mousedown', pointerStart, true);
    document.addEventListener('mouseup', pointerEnd, true);
    document.addEventListener('pointerup', pointerEnd, true);
    document.addEventListener('pointercancel', pointerEnd, true);
    document.addEventListener('click', pointerClick, true);
    input.focus(); input.select();
  }
  function finish(cancel = false) {
    if (!editing) return;
    if (!cancel && !input.checkValidity()) { input.reportValidity(); return; }
    cleanup(); editing = false; input.readOnly = true;
    if (cancel) input.value = value;
    else if (input.value !== value) commit(input.value);
  }
  input.addEventListener('dblclick', begin);
  input.addEventListener('keydown', e => {
    if (!editing && ['Enter', 'F2'].includes(e.key)) { e.preventDefault(); begin(); }
    else if (editing && e.key === 'Enter') { e.preventDefault(); finish(); }
    else if (editing && e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); finish(true); }
  });
  input.addEventListener('blur', () => { if (pointerDown) pendingBlur = true; else finish(); });
  input.beginNameEdit = begin;
  return input;
}

export function makeSequencer(ctx) {
  if (!document.querySelector('link[data-sequencer-style]')) document.head.append(el('link', '', {
    rel: 'stylesheet', href: new URL('sequencer.css', import.meta.url).href, 'data-sequencer-style': true,
  }));
  const root = el('section', 'sq', { 'aria-label': 'Sequencer workspace', 'data-testid': 'sequencer', tabindex: 0, 'aria-description': 'Song shortcuts: Space play or pause; Shift+Space restart; E Clip; A Automation; D device; I sidebar; Tab Arrangement or Mixer when the canvas has focus. F2 rename; 0 mute selected track.' });
  const status = el('p', 'sq-status', { role: 'status', 'aria-live': 'polite' });
  const content = el('fieldset', 'sq-content');
  const rotate = el('section', 'sq-rotate', { 'data-testid': 'song-rotate-prompt', 'aria-label': 'Rotate phone' }, [
    el('h3', '', { text: 'Turn your phone sideways' }),
    el('p', '', { text: 'Song editing needs landscape on a small phone. Rotate to use scenes, clips and the mixer. Playback keeps its current state.' }),
  ]);
  const deviceDialog = el('dialog', 'sq-device-dialog', { id: 'sq-device-controls', 'aria-label': 'Device controls' });
  const transportMount = ctx.transportHost || el('div', 'sq-transport-mount');
  transportMount.classList.add('sq-transport-mount');
  transportMount.classList.toggle('is-external', !!ctx.transportHost);
  if (!ctx.transportHost) root.append(transportMount);
  root.append(status, rotate, content, deviceDialog);
  const contains = target => root.contains(target) || transportMount.contains(target);
  const workspaceAll = selector => [...root.querySelectorAll(selector), ...(ctx.transportHost ? transportMount.querySelectorAll(selector) : [])];
  const state = { doc: null, model: null, busy: false, loading: null, dirty: true, track: 0, scene: 0,
    note: -1, page: 0, pitch: 60, low: 48, song: 0, lane: 0, inspector: null, midi: null, solo: null, mixDetails: null,
    noteAdvancedOpen: false, automationAssignOpen: false, follow: true, view: 'Scenes' };
  let disposed = false, pendingFocus = null, suppressNoteClick = false, cancelDrag = null, readError = false;
  let pendingRollNote = -1;
  let readRevision = 0, readText = null;
  let releaseFader = null;
  const meterHold = new Map();
  // Capacity follows the stable workspace, never a grid being replaced by draw().
  let layout = gridLayout(0), resizeFrame = 0, resizePending = false, pointerActive = false;
  state.scenesPage = 0; state.songPage = 0;
  function gridLayout(width) {
    const available = Math.max(240, width - 28);
    const steps = (label, cell) => Math.max(1, Math.min(32, Math.floor((available - label - 18) / cell)));
    return { columns: Math.max(1, Math.floor((available - 140) / 150)), clip: steps(60, 32), automation: steps(140, 55) };
  }
  const pageSize = () => state.view === 'Automation' ? layout.automation : layout.clip;
  const pageStart = () => state.page * pageSize();
  function changeView(name) {
    const anchor = pageStart(); state.view = name;
    state.page = Math.floor(anchor / pageSize());
  }
  function resizeGrids() {
    resizeFrame = 0;
    if (disposed || !root.isConnected) return;
    const next = gridLayout(content.getBoundingClientRect().width);
    if (JSON.stringify(next) === JSON.stringify(layout)) { resizePending = false; return; }
    // Do not replace a held pointer target or an unsaved field during a resize.
    if (pointerActive || cancelDrag || releaseFader || state.busy || contains(document.activeElement) && document.activeElement.matches('input:not([readonly]), textarea')) {
      resizePending = true; return;
    }
    const anchor = pageStart(), scene = state.scenesPage * layout.columns, song = state.songPage * layout.columns;
    layout = next; state.page = Math.floor(anchor / pageSize());
    state.scenesPage = Math.floor(scene / layout.columns); state.songPage = Math.floor(song / layout.columns);
    resizePending = false; draw();
  }
  function scheduleResize() { if (!resizeFrame) resizeFrame = requestAnimationFrame(resizeGrids); }
  const gridObserver = new ResizeObserver(scheduleResize); gridObserver.observe(root);
  root.addEventListener('pointerdown', () => { pointerActive = true; }, { capture: true });
  const finishPointer = () => { pointerActive = false; if (resizePending) scheduleResize(); };
  window.addEventListener('pointerup', finishPointer); window.addEventListener('pointercancel', finishPointer);
  const finishEdit = () => { if (resizePending) scheduleResize(); };
  root.addEventListener('focusout', finishEdit);
  if (ctx.transportHost) transportMount.addEventListener('focusout', finishEdit);
  function pageControls(key, total, size, noun, change) {
    const index = key === 'steps' ? state.page : state[key], pages = Math.max(1, Math.ceil(total / size));
    const range = `${noun} ${index * size + 1}–${Math.min(total, (index + 1) * size)}`;
    function arrow(previous) {
      const label = `${previous ? 'Previous' : 'Next'} ${noun.toLowerCase()} page`;
      const button = btn('', () => change(index + (previous ? -1 : 1)), {
        disabled: previous ? index <= 0 : index >= pages - 1, 'aria-label': label, title: label,
      });
      const icon = svgNode('svg', { viewBox: '0 0 16 16', 'aria-hidden': 'true', focusable: 'false' });
      icon.append(svgNode('path', { d: previous ? 'M10 3 5 8l5 5' : 'm6 3 5 5-5 5', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
      button.append(icon);
      return button;
    }
    return el('div', 'sq-page-nav is-compact', { 'aria-label': `${noun} pages` }, [
      arrow(true),
      el('span', 'sq-caption', { text: `${range} / ${total}`, 'aria-live': 'polite', 'aria-atomic': 'true' }),
      arrow(false),
    ]);
  }
  function stepPages(c) { return pageControls('steps', c.loopStart + c.length, pageSize(), 'Steps', index => { state.follow = false; state.page = index; draw(); }); }
  const trackName = (t) => state.model?.tracks[t].name || `Track ${t + 1}`;
  const sceneName = (s) => state.model?.sceneNames[s] || `Scene ${s + 1}`;
  const clip = (m = state.model, t = state.track, s = state.scene) => m.tracks[t].clips[s];
  const ensureClip = (m, t, s) => m.tracks[t].clips[s] ||= freshClip();
  function trackTitle(t) {
    const input = editableName(`Track ${t + 1} name`, state.model.tracks[t].name,
      name => edit(`Rename track ${t + 1}`, m => { m.tracks[t].name = name; }),
      { placeholder: `Track ${t + 1}`, pattern: '[\\x20-\\x7e]{0,16}', title: 'Double-click, Enter or F2 to rename. Up to 16 printable ASCII characters; spaces allowed. Clear for the numbered name.' });
    return el('div', 'sq-track-title', {}, [input]);
  }
  function trackHeader(track, t, group) {
    const route = track.route;
    const header = el('div', `sq-track-head sq-track-select ${group}`, { role: 'button', tabindex: 0,
      'aria-label': `Track ${t + 1}`, 'aria-current': t === state.track ? 'true' : 'false', 'aria-pressed': String(t === state.track),
      'data-midi-id': `seq:select-track:${t}`,
      'aria-description': 'Click empty space or press Enter or Space to select this track. Double-click its name to rename.',
      'data-track-header': t, title: 'Click empty space to select track; double-click name to rename.' }, [trackTitle(t),
      choose(`Track ${t + 1} output`, `${route.kind === 1 ? 's' : 'm'}${route.index}`, routeOptions(), v => edit(`Route track ${t + 1}`, m => { m.tracks[t].route = { kind: v[0] === 's' ? 1 : 0, index: Number(v.slice(1)) }; }))]);
    wireHeaderSelection(header, () => selectClip(t, state.scene));
    return header;
  }
  function wireHeaderSelection(header, select) {
    // The parent selection surface is a distinct MIDI target. Child controls
    // keep their own clicks, keyboard actions and MIDI assignments.
    header.addEventListener('click', e => {
      const control = e.target.closest('button, input, select, textarea, label, summary, a, [role=button]');
      if (!state.busy && (!control || control === header)) select();
    });
    header.addEventListener('keydown', e => {
      if (e.target === header && ['Enter', ' '].includes(e.key)) { e.preventDefault(); if (!state.busy) select(); }
    });
  }
  function announce(text, error = false) {
    readError = false;
    status.textContent = text; status.classList.toggle('is-error', error); ctx.say?.(text);
  }
  function lock(on) {
    if (on && contains(document.activeElement)) { const a = document.activeElement; pendingFocus = a.getAttribute('aria-label'); }
    state.busy = on; content.disabled = on; const transport = transportMount.querySelector('fieldset'); if (transport) transport.disabled = on; root.setAttribute('aria-busy', String(on));
    if (!on && resizePending) scheduleResize();
    if (!on && pendingFocus) { const e = workspaceAll('[aria-label]').find(e => e.getAttribute('aria-label') === pendingFocus); e?.focus({ preventScroll: true }); pendingFocus = null; }
  }
  async function refresh(force = false) {
    if (state.busy && !force) { state.dirty = true; return; }
    if (state.loading) return state.loading;
    state.loading = (async () => {
      try {
        for (;;) {
          const revision = readRevision;
          const doc = await ctx.fetchProject();
          if (disposed) return;
          // A native edit can invalidate an older snapshot while it is being
          // read. Consume that invalidation before clearing the dirty flag.
          if (revision !== readRevision) continue;
          const text = JSON.stringify(doc);
          if (readError) announce('');
          // Settlement and content-generation notifications can both request
          // the same snapshot. Replacing unchanged controls loses pointer
          // clicks and number-input selection in the middle of a gesture.
          if (!force && text === readText) { state.dirty = false; return; }
          const selected = state.model && state.note >= 0 ? clip()?.notes[state.note] : null;
          const model = parseSet(doc.set || ['movy1']);
          state.doc = doc; state.model = model; readText = text; state.dirty = false;
          if (selected) state.note = (clip()?.notes || []).findIndex(n => n.tick === selected.tick && n.pitch === selected.pitch);
          draw();
          return;
        }
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
    if (open) changeView('Clip');
    state.track = t; state.scene = s; state.scenesPage = Math.floor(s / layout.columns); ctx.watchTrack?.(t); state.note = -1;
    frameClipNotes();
    draw();
    if (open) root.querySelector('[data-view="Clip"]')?.focus({ preventScroll: true });
  }
  function frameClipNotes() {
    const c = clip();
    state.page = Math.floor((c?.loopStart || 0) / pageSize());
    pendingRollNote = -1;
    // A clip can start with silence, or have a loop starting after bar one.
    // Open the first sounding note's page rather than an empty first page.
    c?.notes.forEach((n, i) => {
      if (n.tick >= (c.loopStart + c.length) * 24 || n.tick + n.gate <= c.loopStart * 24) return;
      if (pendingRollNote < 0 || n.tick < c.notes[pendingRollNote].tick) pendingRollNote = i;
    });
    const n = c?.notes[pendingRollNote];
    if (n) {
      state.page = Math.floor(Math.max(c.loopStart, n.tick / 24) / pageSize());
      state.pitch = n.pitch; state.low = Math.max(0, Math.min(104, n.pitch - 12));
    }
  }
  function soundName(i) { const s = state.doc.sounds?.[i]; return `S${i + 1} · ${s?.engine || 'Empty'}`; }
  const routeOptions = () => [...Array.from({ length: 4 }, (_, i) => [`s${i}`, soundName(i)]),
    ...Array.from({ length: 16 }, (_, i) => [`m${i + 1}`, `MIDI channel ${i + 1}`])];
  function openInspector(key) {
    if (ctx.inspector) { state.inspector = state.inspector === key ? null : key; draw(); }
    else ctx.editSound?.(key);
  }
  function closeInspector() {
    const key = state.inspector;
    state.inspector = null;
    if (deviceDialog.open) deviceDialog.close();
    if (!ctx.fileToolsHost) { const files = deviceDialog.querySelector('.sq-file-tools'); if (files) transportMount.querySelector('.sq-transport')?.append(files); }
    deviceDialog.replaceChildren();
    const trigger = root.querySelector(`[data-inspector="${key}"]`);
    trigger?.setAttribute('aria-expanded', 'false');
    trigger?.focus({ preventScroll: true });
  }
  deviceDialog.addEventListener('cancel', e => { e.preventDefault(); closeInspector(); });
  deviceDialog.addEventListener('click', e => {
    if (e.target !== deviceDialog) return;
    const r = deviceDialog.getBoundingClientRect();
    if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) closeInspector();
  });
  function toolbar() {
    const m = state.model;
    const file = el('input', 'sq-file', { type: 'file', accept: '.mid,.midi', multiple: true, 'aria-label': 'Import MIDI files' });
    file.addEventListener('change', () => importFiles([...file.files]));
    const files = el('details', 'sq-file-tools', {}, [el('summary', '', { text: 'Files & export', 'aria-label': 'Files & export' }), el('div', 'sq-file-menu', {}, [
      btn('Open…', () => action(ctx.openFile)), btn('Save .lunar', () => action(() => ctx.exportFile?.('lunar'))),
      btn('Export .movy1', () => action(() => ctx.exportFile?.('movy1'))),
      btn('Export WAV…', () => action(ctx.exportAudio)), btn('Import MIDI…', () => file.click()), file,
      btn('Refresh', () => refresh()),
    ])]);
    if (ctx.fileToolsHost) ctx.fileToolsHost.replaceChildren(files);
    const jump = (kind, direction) => {
      const counter = transportNavigation(state.model, ctx.getTransport?.() || {}, state.track)[kind];
      const next = counter[direction < 0 ? 'previous' : 'next'];
      if (next === null) return;
      selectClip(state.track, next.scene);
      action(() => kind === 'clip' ? ctx.playClip?.(state.track, next.scene)
        : next.bar !== undefined ? ctx.seekBar?.(next.bar) : ctx.playScene?.(next.scene));
    };
    const nav = (kind, direction) => btn(direction < 0 ? '‹' : '›', () => jump(kind, direction), {
      'aria-label': `${direction < 0 ? 'Previous' : 'Next'} ${kind}`, title: `${direction < 0 ? 'Previous' : 'Next'} ${kind}`,
      'data-slot-kind': kind, 'data-slot-direction': direction,
      'data-midi-id': `seq:transport:${direction < 0 ? 'previous' : 'next'}-${kind}`,
    });
    return el('fieldset', 'sq-toolbar sq-transport', { disabled: state.busy, 'aria-label': 'Song transport' }, [
      btn('▶', () => action(ctx.playPause), { 'data-midi-id': 'seq:transport:play-pause', 'data-testid': 'seq-play', 'aria-label': 'Play', title: 'Play', 'data-transport-play-pause': true }),
      btn('■', () => action(ctx.stop), { 'data-midi-id': 'seq:transport:stop', 'aria-label': 'Stop', title: 'Stop and return to 0:0:0' }),
      el('div', 'sq-transport-readouts', {}, [
        el('span', 'sq-readout', { title: 'Current position in zero-based bars:beats:ticks' }, [
          el('span', 'sq-readout-icon', { text: '▶', 'aria-hidden': 'true' }),
          el('output', 'sq-position', { text: '0:0:0', 'data-play-position': true, 'aria-label': 'Current position in zero-based bars, beats and ticks' })]),
        el('span', 'sq-readout', { title: 'Total arrangement length in bars:beats:ticks' }, [
          el('span', 'sq-readout-icon', { text: '◼', 'aria-hidden': 'true' }),
          el('output', 'sq-position', { text: songDuration(m).position, 'data-play-total-position': true, 'aria-label': 'Total arrangement length in bars, beats and ticks' })]),
        el('span', 'sq-readout', { title: 'Native elapsed playback time' }, [
          el('span', 'sq-readout-icon', { text: '◷', 'aria-hidden': 'true' }),
          el('output', 'sq-time', { text: '0:00.000', 'data-play-time': true, 'aria-label': 'Elapsed playback time' })]),
        el('span', 'sq-readout', { title: 'Estimated remaining time when the song ends with Stop; unavailable while looping, parked, or externally clocked' }, [
          el('span', 'sq-readout-icon', { text: '⌛', 'aria-hidden': 'true' }),
          el('output', 'sq-time', { text: '—', 'data-play-remaining': true, 'aria-label': 'Estimated remaining song time' })]),
        el('span', 'sq-transport-state sq-sr', { text: 'Stopped', 'data-play-state': true, role: 'status' }),
      ]),
      ...['bar', 'clip', 'scene'].map(kind => el('div', 'sq-transport-nav', {}, [
        kind === 'bar' ? btn('‹', () => locateBar(-1), { 'data-midi-id': 'seq:transport:previous-bar', 'aria-label': 'Previous bar', 'data-bar-nav': -1 }) : nav(kind, -1),
        el('span', 'sq-nav-label', {}, [el('span', '', { text: kind }),
          el('output', 'sq-nav-count', { text: '0/0', 'data-nav-count': kind, 'aria-label': `Current ${kind} and total` })]),
        kind === 'bar' ? btn('›', () => locateBar(1), { 'data-midi-id': 'seq:transport:next-bar', 'aria-label': 'Next bar', 'data-bar-nav': 1 }) : nav(kind, 1),
      ])),
      field('BPM', m.bpmX100 / 100, v => edit('Change tempo', m => { m.bpmX100 = Math.round(v * 100); }), { min: 20, max: 300, step: .01 }),
      metronomeButton(),
      choose('Song end', m.songEnd, [[0, 'Loop'], [1, 'Park'], [2, 'Stop']], v => edit('Set song ending', m => { m.songEnd = Number(v); })),
      state.view === 'Mixer' ? btn('Routing & FX', () => { state.mixDetails = !(state.mixDetails ?? !matchMedia('(max-height: 500px) and (orientation: landscape)').matches); draw(); },
        { 'aria-label': 'Routing & FX', 'aria-expanded': String(state.mixDetails ?? !matchMedia('(max-height: 500px) and (orientation: landscape)').matches), 'aria-controls': 'sq-mixer-board' }) : null,
      ctx.fileToolsHost ? null : files,
      el('div', 'sq-transport-master', {}, [el('span', '', { text: 'Master' }), signalMeter('out.post_master', 'Master output', true)]),
    ]);
  }
  function metronomeButton() {
    const button = btn('', () => edit('Toggle metronome', (_m, doc) => { doc.settings ||= {}; doc.settings.metronome = doc.settings.metronome ? 0 : 1; }),
      { 'data-midi-id': 'seq:transport:metronome', 'aria-label': 'Metronome', title: 'Metronome', 'aria-pressed': String(!!state.doc.settings?.metronome), class: 'sq-button sq-metronome' });
    const icon = svgNode('svg', { viewBox: '0 0 24 24', width: 20, height: 20, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.7, 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' });
    icon.append(svgNode('path', { d: 'M9 3h6l4 17H5L9 3Z M8 16h8 M12 16l6-11' }), svgNode('circle', { cx: 18, cy: 5, r: 1.5, fill: 'currentColor' }));
    button.append(icon); return button;
  }
  function locateBar(direction) {
    const transport = ctx.getTransport?.() || {};
    if (transport.following) return;
    action(() => ctx.seekBar?.(Math.max(0, Math.min(barLimit(state.model, transport), Math.floor((transport.master_tick || 0) / 384) + direction))));
  }
  function updateTransport(transport) {
    if (disposed || !transport || !state.model) return;
    // A queued native update can arrive while the external host is empty
    // during an editor remount. Each control is optional until draw finishes.
    const position = transportMount.querySelector('[data-play-position]');
    if (position) position.textContent = positionText(transport.master_tick);
    const time = transportMount.querySelector('[data-play-time]');
    if (time) time.textContent = timeText(transport.playbackFrames, transport.sampleRate);
    const duration = songDuration(state.model, transport);
    const total = transportMount.querySelector('[data-play-total-position]');
    if (total) total.textContent = duration.position;
    const remaining = transportMount.querySelector('[data-play-remaining]');
    if (remaining) remaining.textContent = duration.remaining;
    const status = transportMount.querySelector('[data-play-state]');
    if (status) status.textContent = transport.playing ? 'Playing' : transport.paused ? 'Paused' : 'Stopped';
    const playPause = transportMount.querySelector('[data-transport-play-pause]');
    if (playPause) {
      const label = transport.playing ? 'Pause' : transport.paused ? 'Resume' : 'Play';
      playPause.textContent = transport.playing ? 'Ⅱ' : '▶';
      playPause.setAttribute('aria-label', label);
      playPause.title = label;
      playPause.disabled = state.busy;
    }
    const counters = transportNavigation(state.model, transport, state.track);
    for (const [kind, counter] of Object.entries(counters)) {
      const output = transportMount.querySelector(`[data-nav-count="${kind}"]`);
      if (output) { output.textContent = `${counter.current}/${counter.total}`; output.title = counter.description; }
    }
    for (const button of transportMount.querySelectorAll('[data-slot-kind]')) {
      const counter = counters[button.dataset.slotKind];
      button.disabled = state.busy || counter[Number(button.dataset.slotDirection) < 0 ? 'previous' : 'next'] === null;
    }
    const bar = Math.floor((transport.master_tick || 0) / 384), max = barLimit(state.model, transport);
    for (const button of transportMount.querySelectorAll('[data-bar-nav]')) button.disabled = state.busy || !!transport.following || (Number(button.dataset.barNav) < 0 ? bar <= 0 : bar >= max);
  }

  function syncMixerDisclosure() {
    const button = transportMount.querySelector('[aria-controls="sq-mixer-board"]');
    if (button) button.setAttribute('aria-expanded', String(state.mixDetails ?? !matchMedia('(max-height: 500px) and (orientation: landscape)').matches));
  }
  const compactMixerMedia = matchMedia('(max-height: 500px) and (orientation: landscape)');
  const syncMixerAfterResize = () => { syncMixerDisclosure(); requestAnimationFrame(syncMixerDisclosure); };
  const dbText = gain => gain > 0 ? `${(20 * Math.log10(gain)).toFixed(1)} dB` : '−∞ dB';
  function levelFader(sound) {
    const master = sound === null, label = master ? 'Master output level' : `S${sound + 1} level`;
    const get = () => master ? (ctx.getMaster?.() ?? 1) * 100 : (ctx.getSoundLevel?.(sound) ?? state.doc.sounds?.[sound]?.level ?? 100);
    const range = el('input', 'sq-fader', { type: 'range', min: 0, max: 100, step: 1, orient: 'vertical',
      'aria-label': label, 'aria-orientation': 'vertical', 'data-sound-fader': master ? 'master' : sound });
    const value = el('output', 'sq-fader-value', { 'aria-hidden': 'true' });
    let frame = 0, pending = null, dragging = false;
    const paint = v => { range.value = v; value.textContent = dbText(master ? (v / 100) ** 2 : v / 100); range.setAttribute('aria-valuetext', value.textContent); };
    const send = () => {
      if (frame) cancelAnimationFrame(frame); frame = 0;
      if (pending === null) return;
      const v = pending; pending = null;
      if (master) ctx.setMaster?.(v / 100);
      else if (ctx.setSoundLevel) ctx.setSoundLevel(sound, v, dragging ? 'drag' : 'key');
    };
    const end = () => { send(); if (dragging) ctx.endLevelDrag?.(); dragging = false; range.dataset.dragging = 'false'; if (releaseFader === end) releaseFader = null; };
    range.addEventListener('pointerdown', () => { releaseFader?.(); dragging = true; range.dataset.dragging = 'true'; if (!master) ctx.beginLevelDrag?.(sound); releaseFader = end; });
    range.addEventListener('input', () => {
      pending = Number(range.value); paint(pending);
      if (!frame) frame = requestAnimationFrame(send);
    });
    range.addEventListener('change', () => {
      const v = Number(range.value); pending = v; send(); end();
      if (!master && !ctx.setSoundLevel) edit(`Set S${sound + 1} level`, (_m, d) => { d.sounds[sound].level = v; });
    });
    range.addEventListener('pointerup', end); range.addEventListener('pointercancel', end); range.addEventListener('blur', end);
    range.addEventListener('dblclick', () => { paint(100); pending = 100; send(); });
    paint(get());
    return el('div', 'sq-fader-column', {}, [value, range, el('span', 'sq-fader-label', { text: master ? 'Output' : 'Level' })]);
  }
  function signalMeter(row, label, small = false) {
    return el('div', `sq-signal-meter ${small ? 'is-mini' : ''}`, { role: 'meter', 'aria-label': label,
      'aria-valuemin': -60, 'aria-valuemax': 6, 'aria-valuenow': -60, 'aria-valuetext': 'Silent', 'data-sq-meter': row }, [
      el('span', 'sq-meter-rms', { 'aria-hidden': 'true' }), el('span', 'sq-meter-peak', { 'aria-hidden': 'true' }),
      small ? null : el('span', 'sq-meter-scale', { 'aria-hidden': 'true' }, [0, -12, -24, -48].map(db =>
        el('span', '', { text: String(db).replace('-', '−'), style: `bottom:${(db + 60) / 66 * 100}%` }))),
    ]);
  }
  function deviceSlot(key, title, fx, input, output) {
    return el('div', 'sq-device', {}, [btn(fx?.engine || 'Empty', () => openInspector(key), { 'aria-label': title, 'data-inspector': key,
      'aria-haspopup': 'dialog', 'aria-controls': deviceDialog.id, 'aria-expanded': String(state.inspector === key), title: `${title}: ${fx?.engine || 'Empty'}` }),
      el('div', 'sq-device-meters', {}, [el('span', '', { text: 'In', 'aria-hidden': 'true' }), signalMeter(input, `${title} input`, true),
        el('span', '', { text: 'Out', 'aria-hidden': 'true' }), signalMeter(output, `${title} output`, true)])]);
  }
  function mixer() {
    const strips = Array.from({ length: 4 }, (_, i) => {
      const tracks = state.model.tracks.map((t, n) => t.route.kind === 1 && t.route.index === i ? n : -1).filter(n => n >= 0);
      const muted = tracks.length > 0 && tracks.every(n => state.model.tracks[n].muted);
      const prefix = `snd${i + 1}`, inserts = state.doc.sounds?.[i]?.inserts || [];
      return el('section', `sq-sound sq-channel ed-s${i + 1}`, { 'aria-label': `Sound ${i + 1} channel` }, [
        el('h3', '', { text: `Sound ${i + 1}` }),
        btn(state.doc.sounds?.[i]?.engine || 'Empty instrument', () => openInspector(`s${i + 1}`), { class: 'sq-button sq-instrument', 'aria-label': `S${i + 1} instrument`, 'data-inspector': `s${i + 1}`,
          'aria-haspopup': 'dialog', 'aria-controls': deviceDialog.id, 'aria-expanded': String(state.inspector === `s${i + 1}`) }),
        el('p', 'sq-channel-routes', { text: tracks.length ? `Tracks ${tracks.map(n => n + 1).join(', ')}` : 'No routed tracks' }),
        el('div', 'sq-device-rack', {}, [deviceSlot(`s${i + 1}.in1`, `S${i + 1} insert 1`, inserts[0], prefix, `${prefix}.fx1`),
          deviceSlot(`s${i + 1}.in2`, `S${i + 1} insert 2`, inserts[1], `${prefix}.fx1`, `${prefix}.fx2`)]),
        el('div', 'sq-channel-controls', {}, [btn('Mute', () => edit(`Toggle S${i + 1} track mute`, m => { for (const t of tracks) m.tracks[t].muted = muted ? 0 : 1; }), { 'aria-label': `S${i + 1} mute routed tracks`, 'aria-pressed': String(muted), disabled: !tracks.length }),
          btn('Solo', () => edit(`Solo S${i + 1}`, m => {
            if (state.solo?.sound === i) { m.tracks.forEach((t, n) => { t.muted = state.solo.mutes[n]; }); state.solo = null; }
            else { const mutes = state.solo?.mutes || m.tracks.map(t => t.muted); state.solo = { sound: i, mutes }; m.tracks.forEach((t, n) => { t.muted = tracks.includes(n) ? 0 : 1; }); }
          }), { 'aria-label': `S${i + 1} solo routed tracks`, 'aria-pressed': String(state.solo?.sound === i), disabled: !tracks.length })]),
        el('div', 'sq-channel-level', {}, [levelFader(i), signalMeter(`${prefix}.post_fader`, `S${i + 1} post-fader level`)]),
      ]);
    });
    strips.push(el('section', 'sq-sound sq-channel sq-master', { 'aria-label': 'Master channel' }, [
      el('h3', '', { text: 'Master' }), el('p', 'sq-master-title', { text: 'Stereo output' }), el('p', 'sq-channel-routes', { text: 'All four sounds' }),
      el('div', 'sq-device-rack', {}, [deviceSlot('m1', 'Master FX 1', state.doc.master?.[0], 'mix', 'fx1'),
        deviceSlot('m2', 'Master FX 2', state.doc.master?.[1], 'fx1', 'fx2')]),
      el('p', 'sq-output-note', { text: 'Playback level', title: 'Output preference; not saved in the project. Sound levels and effects are saved.' }),
      el('div', 'sq-channel-level', {}, [levelFader(null), signalMeter('out.post_master', 'Final master output level')]),
    ]));
    const routes = state.model.tracks.map((track, t) => el('div', `sq-mixer-track ${track.route.kind === 1 ? `ed-s${track.route.index + 1}` : ''}`, { 'data-mixer-track': t }, [
      trackTitle(t),
      btn('Mute', () => edit(`Toggle track ${t + 1} mute`, m => { m.tracks[t].muted ^= 1; }), { 'aria-label': `Track ${t + 1} mute`, 'aria-pressed': String(!!track.muted), title: `Track ${t + 1}: ${track.muted ? 'muted' : 'playing when launched'}` }),
      choose(`Track ${t + 1} mixer output`, `${track.route.kind === 1 ? 's' : 'm'}${track.route.index}`, routeOptions(), v => edit(`Route track ${t + 1}`, m => { m.tracks[t].route = { kind: v[0] === 's' ? 1 : 0, index: Number(v.slice(1)) }; })),
    ]));
    return el('section', 'sq-mixer-workspace', {}, [el('div', 'sq-track-routing', { 'aria-label': 'Sequencer track routing and mute' }, routes),
      el('div', 'sq-mixer', { id: 'sq-mixer-board', 'aria-label': 'Four shared sound channels and master' }, strips),
      null]);
  }
  function syncLevels() {
    if (disposed) return;
    for (const input of workspaceAll('[data-sound-fader]')) {
      if (input.dataset.dragging === 'true') continue;
      const master = input.dataset.soundFader === 'master', sound = Number(input.dataset.soundFader);
      const v = master ? (ctx.getMaster?.() ?? 1) * 100 : ctx.getSoundLevel?.(sound);
      if (!Number.isFinite(v)) continue;
      input.value = v;
      const text = dbText(master ? (v / 100) ** 2 : v / 100);
      input.previousElementSibling.textContent = text; input.setAttribute('aria-valuetext', text);
    }
  }
  function onTelemetry(floats) {
    if (disposed) return;
    const sections = ctx.metadata?.doc?.telemetry?.sections || [], now = performance.now();
    for (const meter of workspaceAll('[data-sq-meter]')) {
      const row = meter.dataset.sqMeter;
      const sec = sections.find(s => ['meters', 'levels'].includes(s.name) && s.rows.includes(row));
      if (!sec) continue;
      const offset = sec.offset + sec.rows.indexOf(row) * sec.fields.length;
      const peak = floats[offset], rms = floats[offset + 1];
      if (!Number.isFinite(peak) || !Number.isFinite(rms)) continue;
      const db = peak > 0 ? 20 * Math.log10(peak) : -60;
      let hold = meterHold.get(row);
      if (!hold || peak >= hold.peak || now - hold.at > 1400) { hold = { peak, at: now }; meterHold.set(row, hold); }
      const position = gain => Math.max(0, Math.min(1, ((gain > 0 ? 20 * Math.log10(gain) : -60) + 60) / 66));
      meter.style.setProperty('--rms', position(rms).toFixed(4)); meter.style.setProperty('--peak', position(hold.peak).toFixed(4));
      meter.classList.toggle('is-clipping', peak >= 1);
      meter.setAttribute('aria-valuenow', String(Math.max(-60, Math.min(6, db)).toFixed(1)));
      meter.setAttribute('aria-valuetext', peak > 0 ? `Peak ${dbText(peak)}, RMS ${dbText(rms)}` : 'Silent');
      meter.title = meter.getAttribute('aria-valuetext');
    }
    syncLevels();
  }
  function songView() {
    const entries = arrangementEntries(state.model), selected = entries[state.song];
    function alter(label, fn) { edit(label, m => { const es = arrangementEntries(m); fn(es); m.song = es.flatMap(e => Array(e.presses).fill(e.scene)); }); }
    const add = el('details', 'sq-add-section', {}, [
      el('summary', 'sq-button', { text: '＋ Add section' }),
      el('div', 'sq-add-menu', {}, state.model.sceneNames.map((_, scene) =>
        btn(sceneName(scene), () => { add.open = false; edit('Append scene to song', m => { m.song.push(scene); }); },
          { 'aria-label': `Append scene ${scene + 1}: ${sceneName(scene)}`, disabled: state.model.song.length >= 64 }))),
    ]);
    const tools = el('details', 'sq-section-tools', {}, [el('summary', 'sq-button', { text: 'Section tools' }), el('div', 'sq-toolbar', {}, [
      btn('Copy entry', () => alter('Copy song entry', es => { if (es[state.song]) es.splice(state.song + 1, 0, clone(es[state.song])); }), { disabled: !selected }),
      btn('Move ←', () => alter('Move song entry earlier', es => { if (state.song > 0) { const e = es.splice(state.song, 1)[0]; es.splice(--state.song, 0, e); } }), { disabled: !selected || !state.song }),
      btn('Move →', () => alter('Move song entry later', es => { if (state.song < es.length - 1) { const e = es.splice(state.song, 1)[0]; es.splice(++state.song, 0, e); } }), { disabled: !selected || state.song === entries.length - 1 }),
      btn('Remove entry', () => alter('Remove song entry', es => { es.splice(state.song, 1); state.song = Math.max(0, state.song - 1); }), { disabled: !selected }),
      selected ? field('Repeats', selected.presses, v => alter('Change scene repeats', es => { es[state.song].presses = v; }), { min: 1, max: 64, step: 1 }) : null,
    ])]);
    const ending = choose('Song ending', state.model.songEnd, [[0, 'Loop song'], [1, 'Park tracks'], [2, 'Stop']],
      v => edit('Set song ending', m => { m.songEnd = Number(v); }));
    ending.title = 'At the song end: loop, park tracks while the clock keeps running, or stop.';
    const timeline = el('div', 'sq-song-grid', { 'aria-label': 'Song timeline' });
    const allColumns = entries.length ? entries : [{ scene: state.scene, presses: 1, startBar: 0, bars: Math.max(1, ...state.model.tracks.map(t => Math.ceil((t.clips[state.scene]?.length || 0) / 16))) }];
    state.songPage = Math.min(state.songPage, Math.floor((allColumns.length - 1) / layout.columns));
    const first = state.songPage * layout.columns, columns = allColumns.slice(first, first + layout.columns);
    timeline.style.gridTemplateColumns = `140px repeat(${columns.length}, minmax(0, 1fr))`;
    timeline.append(el('div', 'sq-track-head', { text: entries.length ? 'SONG · bars' : 'SCENE · not in song' }));
    columns.forEach((e, offset) => {
      const i = first + offset;
      const name = editableName(`Scene ${e.scene + 1} name in song entry ${i + 1}`, state.model.sceneNames[e.scene] || '', v => edit('Rename scene', m => { m.sceneNames[e.scene] = v; }), { maxlength: 6, pattern: '[!-~]{0,6}', placeholder: sceneName(e.scene) });
      timeline.append(el('div', `sq-entry ${state.song === i ? 'is-selected' : ''}`, { 'data-song-entry': e.songIndex ?? i, 'data-song-entry-end': (e.songIndex ?? i) + e.presses }, [
      el('div', 'sq-name-header', {}, [name]),
      btn(`×${e.presses} · ${e.bars} ${e.bars === 1 ? 'bar' : 'bars'}`, () => { state.song = i; selectClip(state.track, e.scene); }, {
        title: `Starts at bar ${e.startBar + 1}. Select this section; repeats share its scene clips.`, 'aria-label': `Select song entry ${i + 1}: ${sceneName(e.scene)}`, 'aria-pressed': String(state.song === i),
      }),
    ])); });
    state.model.tracks.forEach((track, t) => {
      const route = track.route, group = route.kind === 1 ? `ed-s${route.index + 1}` : '';
      timeline.append(trackHeader(track, t, group));
      columns.forEach((e, offset) => {
      const i = first + offset;
        const c = track.clips[e.scene];
        const noteCount = c?.notes.length || 0, barCount = c ? c.length / 16 : 0;
        const cell = btn(c ? `${noteCount} ${noteCount === 1 ? 'note' : 'notes'} · ${barCount} ${barCount === 1 ? 'bar' : 'bars'}` : '＋ Empty clip', () => { state.song = i; selectClip(t, e.scene, true); }, {
          class: `sq-button sq-clip ${group} ${t === state.track && e.scene === state.scene ? 'is-selected' : ''}`,
          'aria-label': `Track ${t + 1}, ${sceneName(e.scene)}, ${c ? `${noteCount} ${noteCount === 1 ? 'note' : 'notes'}, ${barCount} ${barCount === 1 ? 'bar' : 'bars'}` : 'empty clip'}`, 'data-track': t, 'data-scene': e.scene,
          'data-preview-track': t, 'data-preview-scene': e.scene, 'data-entry-start': e.songIndex ?? -1, 'data-entry-end': (e.songIndex ?? -1) + e.presses,
        });
        if (c) cell.append(clipPreview(c));
        timeline.append(cell);
      });
    });
    return el('section', 'sq-section sq-arrangement', { 'aria-description': 'Select a section using its repeat and bar header. Repeats share scene clips; copy a scene for a different variation.' }, [timelineHeading('Arrangement', 'songPage', allColumns.length, [add, tools, ending]),
      timelinePage(timeline, 'songPage')]);
  }
  function timelineHeading(title, key, total, controls = []) {
    const noun = key === 'songPage' ? 'Sections' : 'Scenes';
    return el('div', `sq-section-heading${controls.length ? ' sq-arrangement-tools' : ''}`, {}, [el('h3', '', { text: title }),
      pageControls(key, total, layout.columns, noun, index => { state[key] = index; draw(); }), controls]);
  }
  function timelinePage(grid, key) {
    const label = key === 'songPage' ? 'Sections' : 'Scenes';
    return el('div', 'sq-timeline', {}, [
      el('div', 'sq-scroll', { 'data-scroll': key === 'songPage' ? 'song' : 'scenes', tabindex: 0, 'aria-label': `${label} grid` }, [grid]),
    ]);
  }
  function sceneMatrix() {
    const grid = el('div', 'sq-song-grid sq-scene-grid', { 'aria-label': 'Scene matrix', 'data-testid': 'scene-matrix' });
    state.scenesPage = Math.min(state.scenesPage, Math.floor(7 / layout.columns));
    const first = state.scenesPage * layout.columns, last = Math.min(8, first + layout.columns);
    grid.style.gridTemplateColumns = `140px repeat(${last - first}, minmax(0, 1fr))`;
    grid.append(el('div', 'sq-track-head', { text: 'SCENES · performance' }));
    for (let scene = first; scene < last; scene++) {
      const name = editableName(`Scene ${scene + 1} name`, state.model.sceneNames[scene] || '', v => edit('Rename scene', m => { m.sceneNames[scene] = v; }), { maxlength: 6, pattern: '[!-~]{0,6}', placeholder: sceneName(scene) });
      const header = el('div', 'sq-scene-head sq-scene-select', { role: 'button', tabindex: 0,
        'data-scene-header': scene, 'data-midi-id': `seq:select-scene:${scene}`,
        'aria-label': `Scene ${scene + 1}`, 'aria-pressed': String(state.scene === scene),
        'aria-description': 'Click empty space or press Enter or Space to select this scene. Double-click its name to rename.',
        title: 'Click empty space to select scene; double-click name to rename.' }, [
        el('div', 'sq-scene-title', {}, [
          ctx.playScene ? btn('▶', () => action(() => ctx.playScene(scene)), {
            class: 'sq-button sq-scene-launch', 'aria-label': `Launch scene ${scene + 1}`, title: `Launch scene ${scene + 1}`,
          }) : null,
          el('div', 'sq-name-header', {}, [name]),
        ]),
      ]);
      wireHeaderSelection(header, () => selectClip(state.track, scene));
      grid.append(header);
    }
    state.model.tracks.forEach((track, t) => {
      const route = track.route, group = route.kind === 1 ? `ed-s${route.index + 1}` : '';
      grid.append(trackHeader(track, t, group));
      for (let scene = first; scene < last; scene++) {
        const c = track.clips[scene];
        const notes = c?.notes.length || 0, bars = c ? c.length / 16 : 0;
        const summary = c ? `${notes} ${notes === 1 ? 'note' : 'notes'} · ${bars} ${bars === 1 ? 'bar' : 'bars'}` : '＋ Empty clip';
        const editButton = btn('', () => selectClip(t, scene, true), {
          class: 'sq-button sq-scene-edit', 'aria-label': `Edit track ${t + 1} scene ${scene + 1}`,
          'aria-pressed': String(state.track === t && state.scene === scene),
          'data-progress-track': t, 'data-progress-scene': scene,
        });
        editButton.append(el('span', 'sq-clip-progress', { 'aria-hidden': 'true', hidden: true }));
        editButton.append(el('span', 'sq-scene-summary', { text: summary }));
        if (c) editButton.append(clipPreview(c));
        grid.append(el('div', `sq-matrix-cell ${group}`, { 'data-live-track': t, 'data-live-scene': scene }, [
          ctx.playClip ? btn(c ? '▶' : '■', () => action(() => ctx.playClip(t, scene)), {
            class: 'sq-button sq-scene-launch',
            'aria-label': `${c ? 'Launch clip' : 'Stop track'} ${t + 1} scene ${scene + 1}`,
            title: c ? 'Launch this clip at the native bar boundary' : 'Launch the empty slot to stop this track at the native bar boundary',
          }) : null, editButton]));
      }
    });
    return el('section', 'sq-section', {}, [timelineHeading('Scenes', 'scenesPage', 8),
      timelinePage(grid, 'scenesPage')]);
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
    svg.append(svgNode('line', { x1: 0, x2: 0, y1: 0, y2: 32, class: 'sq-preview-playhead', 'data-preview-playhead': true, visibility: 'hidden' }));
    return svg;
  }
  function sceneTools() {
    let target = (state.scene + 1) % 8, track = state.track;
    return el('details', 'sq-scene-tools', {}, [
      el('summary', 'sq-button', { 'aria-label': 'Scene and clip tools', title: 'Scene and clip tools: rename, copy, move or swap' }),
      el('div', 'sq-toolbar sq-compact-fields sq-scene-tool-fields', {}, [
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
      ]),
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
    return edit(label, m => {
      const c = clip(m, t, s), n = c?.notes.find(n => JSON.stringify(n) === JSON.stringify(original));
      if (!n) throw new Error('This note changed elsewhere. Select it again.');
      const previous = { step: n.step, pitch: n.pitch };
      Object.assign(n, patch);
      state.note = c.notes.indexOf(n);
      for (const trig of c.trigs) if (trig.step === previous.step && trig.lane === previous.pitch) { trig.step = n.step; trig.lane = n.pitch; }
    });
  }
  function pianoRoll(c) {
    const start = pageStart(), end = Math.min(start + pageSize(), c.loopStart + c.length), count = Math.max(1, end - start);
    const canvas = el('div', 'sq-roll', { 'aria-label': 'Piano roll', 'data-testid': 'piano-roll', 'aria-description': 'Click an empty cell to add a note; select a note to edit its properties.' });
    canvas.style.setProperty('--steps', count);
    const octaves = el('div', 'sq-octaves', { 'aria-label': 'Pitch range' });
    for (const up of [false, true]) {
      const button = btn('', () => { state.low = Math.max(0, Math.min(104, state.low + (up ? 12 : -12))); draw(); }, {
        disabled: up ? state.low === 104 : state.low === 0, 'aria-label': up ? 'Octave ↑' : 'Octave ↓', title: up ? 'Raise pitch range one octave' : 'Lower pitch range one octave',
      });
      const icon = svgNode('svg', { viewBox: '0 0 24 30', 'aria-hidden': 'true', focusable: 'false' });
      icon.append(svgNode('path', { d: up ? 'M13 26C6 28 4 20 9 17c7-4 12 3 7 7-5 4-12 0-12-6 0-8 13-11 12-18-1-5-7 3-6 8l5 19c1 4-5 5-6 1' : 'M5 11c0-7 12-7 12 0 0 7-6 10-12 12', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }));
      if (!up) { icon.append(svgNode('circle', { cx: 21, cy: 8, r: 1.2, fill: 'currentColor' }), svgNode('circle', { cx: 21, cy: 14, r: 1.2, fill: 'currentColor' })); }
      button.append(icon); octaves.append(button);
    }
    const ruler = el('div', 'sq-ruler', {}, [octaves]);
    for (let step = start; step < end; ++step) ruler.append(el('span', '', { text: step % 4 === 0 ? `${Math.floor(step / 16) + 1}.${step % 16 / 4 + 1}` : '·' }));
    canvas.append(ruler, el('div', 'sq-playhead', { 'aria-hidden': 'true', 'data-roll-playhead': true }));
    for (let pitch = state.low + 23; pitch >= state.low; --pitch) {
      const row = el('div', `sq-pitch-row ${[1,3,6,8,10].includes(pitch % 12) ? 'is-black' : ''}`);
      row.append(btn(pitchName(pitch), () => { state.pitch = pitch; draw(); }, { 'aria-label': `Use ${pitchName(pitch)} for new notes` }));
      const lane = el('div', 'sq-note-lane', { onclick: e => {
        if (e.target !== lane || state.busy) return;
        const step = start + Math.min(count - 1, Math.floor((e.clientX - lane.getBoundingClientRect().left) / (lane.getBoundingClientRect().width / count)));
        if (step >= c.loopStart) addNote(step, pitch);
      } });
      c.notes.forEach((n, i) => {
        if (n.pitch !== pitch || n.tick / 24 >= end || (n.tick + n.gate) / 24 <= start) return;
        const left = Math.max(0, n.tick / 24 - start), right = Math.min(count, (n.tick + n.gate) / 24 - start);
        const b = btn(`${n.vel}`, e => { e.stopPropagation(); if (suppressNoteClick) { suppressNoteClick = false; return; } state.note = i; state.pitch = n.pitch; draw(); }, {
          class: `sq-note ${state.note === i ? 'is-selected' : ''}`, 'aria-label': `${pitchName(pitch)}, step ${n.step + 1}, gate ${n.gate} ticks, velocity ${n.vel}`,
          'data-note': i, title: `${pitchName(pitch)} · velocity ${n.vel} · gate ${n.gate}`,
        });
        b.style.left = `${left / count * 100}%`; b.style.width = `calc(${(right - left) / count * 100}% - 2px)`;
        b.addEventListener('pointerdown', e => beginNoteDrag(e, n, i, c, false));
        b.append(el('span', 'sq-note-resize', { 'aria-hidden': 'true', 'data-resize-note': i, title: 'Drag to resize gate', onpointerdown: e => { e.stopPropagation(); beginNoteDrag(e, n, i, c, true); } }));
        lane.append(b);
      });
      row.append(lane); canvas.append(row);
    }
    const steps = el('div', 'sq-step-grid', { 'aria-label': `Step editor for ${pitchName(state.pitch)}` });
    steps.style.setProperty('--steps', count);
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
    const stepWidth = node.parentElement.getBoundingClientRect().width / Number(node.closest('.sq-roll').style.getPropertyValue('--steps'));
    const pixelWidth = node.getBoundingClientRect().width;
    const abort = new AbortController(); cancelDrag?.(); cancelDrag = () => { abort.abort(); node.style.left = originalLeft; node.style.width = originalWidth; node.style.transform = ''; };
    window.addEventListener('pointermove', ev => {
      dx = Math.round((ev.clientX - x) / stepWidth); dy = Math.round((y - ev.clientY) / 28);
      if (Math.abs(ev.clientX - x) + Math.abs(ev.clientY - y) < 5) return;
      moved = true; ev.preventDefault();
      if (resize) node.style.width = `${Math.max(8, pixelWidth + dx * stepWidth)}px`;
      else node.style.transform = `translate(${dx * stepWidth}px, ${-dy * 28}px)`;
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
    if (!n) return null;
    const trig = c.trigs.find(t => t.step === n.step && t.lane === n.pitch);
    return el('div', 'sq-note-details', { 'aria-label': 'Selected note' }, [
      el('div', 'sq-toolbar sq-compact-fields sq-note-essential', {}, [
      field('MIDI pitch', n.pitch, v => noteEdit({ pitch: v }), { min: 0, max: 127, step: 1 }),
      field('Step', n.step + 1, v => noteEdit({ step: v - 1, tick: (v - 1) * 24 + n.tick - n.step * 24 }), { min: c.loopStart + 1, max: c.loopStart + c.length, step: 1 }),
      field('Gate · ticks', n.gate, v => noteEdit({ gate: v }), { min: 1, max: 65535, step: 1 }),
      field('Velocity', n.vel, v => noteEdit({ vel: v }), { min: 1, max: 127, step: 1 }),
      ]),
      el('details', 'sq-note-advanced', { open: state.noteAdvancedOpen, ontoggle: e => { state.noteAdvancedOpen = e.currentTarget.open; } }, [el('summary', '', { text: 'Advanced note controls', 'aria-label': 'Advanced note controls' }),
        el('div', 'sq-toolbar sq-compact-fields sq-note-advanced-fields', {}, [
      field('Microtiming · ticks', n.tick - n.step * 24, v => noteEdit({ tick: n.step * 24 + v }), { min: Math.max(-23, -n.step * 24), max: 23, step: 1 }),
      field('Probability %', trig?.prob ?? 100, v => edit('Set note probability', m => {
        const c = clip(m);
        if (!c?.notes.some(x => JSON.stringify(x) === JSON.stringify(n))) throw new Error('This note changed elsewhere. Select it again.');
        let t = c.trigs.find(t => t.step === n.step && t.lane === n.pitch);
        if (!t) { t = { step: n.step, lane: n.pitch, prob: v, a: 1, b: 1, invert: 0 }; c.trigs.push(t); } else t.prob = v;
      }), { min: 0, max: 100, step: 1 }),
        ])]),
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
    const start = pageStart(), end = Math.min(start + pageSize(), c.loopStart + c.length);
    const controls = el('details', 'sq-automation-assign', { open: state.automationAssignOpen, ontoggle: e => { state.automationAssignOpen = e.currentTarget.open; } }, [
      el('summary', '', { text: 'Add automation', 'aria-label': 'Add automation', title: 'Assign one of eight native lock lanes to an instrument, insert, sound level or master effect parameter.' }),
      el('div', 'sq-toolbar', {}, [
      choose('Lock lane', lane, Array.from({ length: 8 }, (_, i) => [i, `Lane ${i + 1}${track.lanes[i] ? ' · ' + track.lanes[i].label : ''}`]), v => { state.lane = Number(v); draw(); }),
      targets.some(t => t.params.length) ? choose('Automation target', targetId, targets.filter(t => t.params.length || t.id === targetId).map(t => [t.id,t.name]), v => { const p = targets.find(t => t.id === v)?.params[0]; if (p) assign(p.label); }) : null,
      params.length ? choose('Parameter', assigned?.label || params[0].label, params.map(p => [p.label,p.name]), assign) : null,
      !assigned && params.length ? btn('Assign parameter', () => assign(params[0].label)) : null,
      assigned ? field('Base · 0–127', assigned.base, v => edit('Set lane base', m => { m.tracks[state.track].lanes[lane].base = v; }), { min: 0, max: 127, step: 1 }) : null,
    ])]);
    const points = el('div', 'sq-lock-grid');
    points.style.setProperty('--automation-steps', end - start);
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
    return el('section', 'sq-section', {}, [controls,
      el('div', 'sq-scroll', { 'data-scroll': 'locks' }, [automationRows(c, start, end), points]),
      null]);
  }
  function setVisualLock(lane, step, value) {
    edit(value === null ? 'Remove parameter lock' : 'Edit parameter lock', m => {
      const c = clip(m); c.locks = c.locks.filter(l => l.lane !== lane || l.step !== step);
      if (value !== null) c.locks.push({ lane, step, value });
    });
  }
  function automationRows(c, start, end) {
    const track = state.model.tracks[state.track];
    const rows = el('div', 'sq-automation-rows', { 'aria-label': 'Native parameter lock lanes', 'aria-description': 'Locks use 0–127. Blank steps carry the last value; a note without a lock resets to base. Click a step to set, use up/down to adjust, Delete to clear.' });
    const ruler = el('div', 'sq-automation-row sq-automation-ruler', {}, [el('span', 'sq-automation-label', { text: 'LANE · 0–127' })]);
    for (let step = start; step < end; step++) ruler.append(el('span', '', { text: step + 1 }));
    rows.append(ruler);
    track.lanes.forEach((assigned, lane) => {
      if (!assigned) return;
      const row = el('div', `sq-automation-row ${lane === state.lane ? 'is-selected' : ''}`, { 'data-automation-lane': lane });
      row.append(btn(`Lane ${lane + 1} · ${assigned.label}`, () => { state.lane = lane; draw(); }, {
        class: 'sq-button sq-automation-label', 'aria-label': `Select lock lane ${lane + 1}: ${assigned.label}`,
        'aria-pressed': String(lane === state.lane), title: `${assigned.label} · base ${assigned.base}`,
      }));
      for (const point of automationSteps(c, lane, assigned.base, start, end)) {
        const kind = point.lock !== undefined ? `lock ${point.lock}` : point.reset ? `note resets to base ${point.value}` : `held value ${point.value}`;
        const button = btn('', e => {
          // Keyboard activation uses the held value. Pointer clicks map the
          // lane height to its native 0–127 value; no host-only envelopes.
          const r = e.currentTarget.getBoundingClientRect();
          const value = e.detail ? Math.max(0, Math.min(127, Math.round((r.bottom - 8 - e.clientY) / (r.height - 16) * 127))) : point.value;
          setVisualLock(lane, point.step, value);
        }, { class: `sq-button sq-automation-step ${point.lock !== undefined ? 'has-lock' : ''} ${point.reset ? 'is-reset' : ''}`,
          'aria-label': `Lane ${lane + 1}, step ${point.step + 1} automation`, 'aria-description': kind,
          'data-automation-step': point.step, disabled: !point.inLoop,
          title: `${kind}. Click to set; ↑/↓ changes by 1 (Shift: 8); Delete clears.`,
          onkeydown: e => {
            if (['Delete', 'Backspace'].includes(e.key)) { e.preventDefault(); setVisualLock(lane, point.step, null); }
            else if (['ArrowUp', 'ArrowDown'].includes(e.key)) {
              e.preventDefault(); const delta = (e.shiftKey ? 8 : 1) * (e.key === 'ArrowUp' ? 1 : -1);
              setVisualLock(lane, point.step, Math.max(0, Math.min(127, (point.lock ?? point.value) + delta)));
            }
          },
        });
        button.style.setProperty('--lock-height', `${point.value / 127 * 100}%`);
        button.append(el('span', 'sq-automation-block', { 'aria-hidden': 'true' }),
          el('span', 'sq-automation-value', { text: point.lock ?? '', 'aria-hidden': 'true' }));
        row.append(button);
      }
      row.append(el('span', 'sq-automation-playhead', { 'data-automation-playhead': true, hidden: true, 'aria-hidden': 'true' }));
      rows.append(row);
    });
    if (!track.lanes.some(Boolean)) rows.append(el('p', 'sq-caption', { text: 'Assign a parameter to create a visual lock lane.' }));
    rows.style.setProperty('--automation-steps', Math.max(0, end - start));
    return rows;
  }
  function clipView(selection) {
    const c = clip();
    if (!c) return el('section', 'sq-section', {}, [sceneTools(), btn('Create clip', () => edit('Create clip', m => { ensureClip(m, state.track, state.scene); })), selection]);
    state.page = Math.min(state.page, Math.floor((c.loopStart + c.length - 1) / pageSize()));
    function compactField(label, visible, value, change, attrs) {
      const control = field(label, value, change, attrs);
      control.firstChild.textContent = visible;
      control.title = label;
      return control;
    }
    const controls = el('div', 'sq-clip-controls', {}, [
      el('div', 'sq-toolbar sq-compact-fields sq-clip-params', {}, [
      compactField('Loop start · step', 'Start', c.loopStart + 1, v => edit('Set clip loop start', m => { clip(m).loopStart = v - 1; }), { min: 1, max: 256, step: 1 }),
      compactField('Loop length · steps', 'Length', c.length, v => edit('Set clip loop length', m => { clip(m).length = v; }), { min: 1, max: 256 - c.loopStart, step: 1 }),
      compactField('Quantize %', 'Quantize', c.quant, v => edit('Set clip quantize', m => { clip(m).quant = v; }), { min: 0, max: 100, step: 1 }),
      field('Transpose', c.transpose, v => edit('Transpose clip', m => { clip(m).transpose = v; }), { min: -36, max: 36, step: 1 }),
      ]),
      el('div', 'sq-toolbar sq-compact-fields sq-clip-actions', {}, [
      btn('Add note', () => addNote(Math.max(c.loopStart, pageStart()), state.pitch)),
      compactField('New note pitch', 'Pitch', state.pitch, v => { state.pitch = v; state.low = Math.max(0, Math.min(104, v - 12)); draw(); }, { min: 0, max: 127, step: 1 }),
      btn('Delete clip', () => edit('Delete clip', m => { m.tracks[state.track].clips[state.scene] = null; state.note = -1; })),
      ]),
    ]);
    return el('section', 'sq-section sq-clip-workspace', {}, [el('div', 'sq-toolbar sq-clip-heading', {}, [
      el('h3', '', { text: `${trackName(state.track)} · ${sceneName(state.scene)}` }), sceneTools(), stepPages(c),
      btn('Follow playhead', () => { state.follow = !state.follow; draw(); }, { 'aria-label': 'Follow playhead', 'aria-pressed': String(state.follow) }),
      el('span', 'sq-caption sq-clip-length', { text: `Clip ${c.length} steps · ${c.length / 16} bars · loop ${c.loopStart + 1}–${c.loopStart + c.length}` }),
    ]), controls, pianoRoll(c), selection, noteDetails(c)]);
  }
  async function importFiles(files) {
    if (state.busy || !files.length) return;
    await action(async () => {
      checkMidiFiles(files);
      const parsed = [];
      for (const f of files) {
        parsed.push(parseMidi(new Uint8Array(await f.arrayBuffer()), f.name));
        checkMidiParts(parsed);
      }
      state.midi = { files: parsed, partIndex: parsed.map(f => new Map(f.parts.map(p => [p.id, p]))),
        mode: 'scene', bars: 4, tempoPolicy: 'reject', onlyEmpty: true, mapping: parsed.flatMap((f, fileIndex) => f.parts.map(p => ({ fileIndex, partId: p.id, track: 0, sound: 0 }))) };
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
      const part = m.partIndex[r.fileIndex].get(r.partId);
      return el('div', 'sq-midi-row', {}, [el('span', '', { text: `${m.files[r.fileIndex].name} · ${part.name || 'Part'} · Ch ${part.channel}${part.drums ? ' · Drums' : ''} · ${part.notes.length} notes` }),
        choose(`Part ${i + 1} target track`, r.track, [[-1, 'Skip'], ...Array.from({ length: 8 }, (_, t) => [t, trackName(t)])], v => { r.track = Number(v); draw(); }),
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
  function draw(transport) {
    if (!state.model || disposed) return;
    releaseFader?.();
    const active = contains(document.activeElement) ? document.activeElement : null;
    const focus = active && { label: active.getAttribute('aria-label'), tag: active.tagName, value: active.value, start: active.selectionStart, end: active.selectionEnd };
    const scrolls = new Map([...content.querySelectorAll('[data-scroll]')].map(e => [e.dataset.scroll, [e.scrollLeft, e.scrollTop]]));
    const views = ['Scenes', 'Arrangement', 'Clip', 'Automation', 'Mixer'];
    const navigation = el('div', 'sq-tabs', { role: 'tablist', 'aria-label': 'Song workspace views' }, views.map(name => btn(name, () => {
      const frame = name === 'Clip' && state.view !== name;
      changeView(name); if (frame) frameClipNotes(); state.inspector = null; draw(); root.querySelector(`[data-view="${name}"]`)?.focus({preventScroll:true});
    }, { role: 'tab', id: `sq-tab-${name}`, 'data-view': name, 'aria-selected': String(state.view === name),
      'aria-controls': 'sq-view-panel', tabindex: state.view === name ? 0 : -1,
      onkeydown: e => {
        if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return;
        e.preventDefault(); e.stopPropagation();
        const i = views.indexOf(name), next = e.key === 'Home' ? 0 : e.key === 'End' ? 4 : (i + (e.key === 'ArrowRight' ? 1 : 4)) % 5;
        const frame = views[next] === 'Clip' && state.view !== 'Clip';
        changeView(views[next]); if (frame) frameClipNotes(); state.inspector = null; draw(); root.querySelector(`[data-view="${state.view}"]`)?.focus({preventScroll:true});
      },
    })));
    const selection = el('div', 'sq-toolbar sq-selection', {}, [
      choose('Edit track', state.track, Array.from({length:8}, (_, t) => [t, trackName(t)]), v => selectClip(Number(v), state.scene)),
      trackTitle(state.track),
      choose('Edit scene', state.scene, state.model.sceneNames.map((_, s) => [s, sceneName(s)]), v => selectClip(state.track, Number(v))),
      ctx.playScene ? btn('Launch scene', () => action(() => ctx.playScene(state.scene)), { 'data-testid': 'launch-scene' }) : null,
    ]);
    let body;
    if (state.view === 'Scenes') body = sceneMatrix();
    else if (state.view === 'Arrangement') body = songView();
    else if (state.view === 'Clip') body = clipView(selection);
    else if (state.view === 'Automation') {
      const c = clip();
      if (c) state.page = Math.min(state.page, Math.floor((c.loopStart + c.length - 1) / pageSize()));
      body = c ? el('div', '', {}, [el('div', 'sq-toolbar sq-clip-heading', {}, [
        el('h3', '', { text: `${trackName(state.track)} · ${sceneName(state.scene)}` }), sceneTools(), stepPages(c),
      ]), locksView(c), selection]) : el('div', '', {}, [el('p', 'sq-caption', { text: 'Create a clip in Clip view before editing automation.' }), selection]);
    } else body = mixer();
    root.dataset.songView = state.view;
    if (state.mixDetails !== null) root.dataset.mixerDetails = String(state.mixDetails);
    transportMount.replaceChildren(toolbar());
    content.replaceChildren(midiView() || '',
      el('div', 'sq-view-panel', {id:'sq-view-panel',role:'tabpanel','aria-labelledby':`sq-tab-${state.view}`}, [body]), navigation);
    if (state.inspector && ctx.inspector) {
      const body = ctx.inspector(state.inspector);
      if (body) {
        const footer = el('footer', 'sq-device-dialog-footer', {}, []);
        if (!ctx.fileToolsHost) { const files = transportMount.querySelector('.sq-file-tools'); if (files) footer.append(files); }
        deviceDialog.replaceChildren(el('div', 'sq-device-dialog-header', {}, [el('h3', '', { text: 'Device controls' }), btn('Close inspector', closeInspector)]), body, footer);
        if (!deviceDialog.open && deviceDialog.isConnected) deviceDialog.showModal();
      } else closeInspector();
    } else { if (deviceDialog.open) deviceDialog.close(); deviceDialog.replaceChildren(); }
    for (const e of content.querySelectorAll('[data-scroll]')) { const p = scrolls.get(e.dataset.scroll); if (p) { e.scrollLeft = p[0]; e.scrollTop = p[1]; } }
    const roll = content.querySelector('[data-scroll="piano"]');
    if (roll && pendingRollNote >= 0) {
      const note = roll.querySelector(`[data-note="${pendingRollNote}"]`);
      if (note) {
        const r = roll.getBoundingClientRect(), n = note.getBoundingClientRect();
        roll.scrollTop += n.top - r.top - (roll.clientHeight - n.height) / 2;

      }
      pendingRollNote = -1;
    }
    content.disabled = state.busy;
    if (focus?.label) {
      const next = workspaceAll('[aria-label]').find(e => e.tagName === focus.tag && e.getAttribute('aria-label') === focus.label);
      if (next && !state.busy) { next.focus({ preventScroll: true }); if (focus.start != null && next.setSelectionRange) { next.value = focus.value; next.setSelectionRange(focus.start, focus.end); } }
    }
    update(transport);
    ctx.onMeterSubscription?.();
  }
  function update(transport = ctx.getTransport?.()) {
    if (disposed) return;
    updateTransport(transport);
    for (const e of root.querySelectorAll('[data-song-entry]')) e.classList.toggle('is-playing', !!transport?.playing && transport.songIndex >= Number(e.dataset.songEntry) && transport.songIndex < Number(e.dataset.songEntryEnd));
    for (const e of root.querySelectorAll('[data-live-track]')) {
      const t = transport?.tracks?.[Number(e.dataset.liveTrack)], scene = Number(e.dataset.liveScene);
      e.classList.toggle('is-playing', !!transport?.playing && t?.playing === scene);
    }
    const watched = transport?.tracks?.[state.track];
    const phase = state.model && clipPlayback(clip(), watched, transport?.playing, state.scene);
    const liveScene = phase ? state.scene : -1;
    const livePosition = phase?.step, liveStep = Math.floor(livePosition);
    const nextPage = phase && Math.floor(phase.step / pageSize());
    if (state.view === 'Clip' && state.follow && phase && nextPage !== state.page && !pointerActive && !cancelDrag && !releaseFader && !state.busy && !(contains(document.activeElement) && document.activeElement.matches('input:not([readonly]), textarea'))) {
      state.page = nextPage; draw(transport); return;
    }
    const playhead = root.querySelector('[data-roll-playhead]');
    if (playhead) { playhead.hidden = !transport?.playing || liveScene !== state.scene || livePosition < pageStart() || livePosition >= pageStart() + pageSize(); const count = Number(playhead.parentElement.style.getPropertyValue('--steps')); playhead.style.left = `calc(60px + (100% - 60px) * ${(livePosition - pageStart()) / count})`; }
    for (const e of root.querySelectorAll('[data-step]')) e.classList.toggle('is-playing', !!transport?.playing && liveScene === state.scene && Number(e.dataset.step) === liveStep);
    for (const e of root.querySelectorAll('[data-mixer-track]')) e.classList.toggle('is-playing', !!transport?.playing && transport.tracks?.[Number(e.dataset.mixerTrack)]?.playing >= 0);
    updatePlayback(transport);
  }
  function updatePlayback(transport) {
    if (disposed) return;
    if (!state.model) return;
    for (const e of root.querySelectorAll('[data-progress-track], [data-preview-track]')) {
      const t = Number(e.dataset.progressTrack ?? e.dataset.previewTrack);
      const scene = Number(e.dataset.progressScene ?? e.dataset.previewScene);
      const phase = clipPlayback(clip(state.model, t, scene), transport?.tracks?.[t], transport?.playing, scene);
      const inEntry = e.dataset.entryStart === undefined || (transport?.songIndex >= Number(e.dataset.entryStart) && transport?.songIndex < Number(e.dataset.entryEnd));
      const active = phase && inEntry;
      const fill = e.querySelector('.sq-clip-progress');
      if (fill) { fill.hidden = !active; fill.style.width = `${active ? phase.fraction * 100 : 0}%`; }
      const line = e.querySelector('[data-preview-playhead]');
      if (line) {
        line.setAttribute('visibility', active ? 'visible' : 'hidden');
        line.setAttribute('x1', active ? phase.fraction * 160 : 0); line.setAttribute('x2', active ? phase.fraction * 160 : 0);
      }
      if (e.dataset.previewTrack !== undefined) e.classList.toggle('is-playing', !!active);
    }
    const c = clip(), track = transport?.tracks?.[state.track];
    const phase = clipPlayback(c, track, transport?.playing, state.scene);
    const start = pageStart(), end = Math.min(start + pageSize(), (c?.loopStart || 0) + (c?.length || 0));
    const visible = phase && phase.step >= start && phase.step < end;
    for (const head of root.querySelectorAll('[data-automation-playhead]')) {
      head.hidden = !visible; head.style.left = `calc(140px + (100% - 140px) * ${(visible ? phase.step - start : 0) / Math.max(1, end - start)})`;
    }
    for (const cell of root.querySelectorAll('[data-automation-step]')) cell.classList.toggle('is-playing', !!visible && Number(cell.dataset.automationStep) === Math.floor(phase.step));
  }
  function shortcutEdit(fn) {
    // A note redraw may remove its focused button. Keep subsequent keys in Song.
    Promise.resolve(fn()).finally(() => { if (root.isConnected && !deviceDialog.open) root.focus({ preventScroll: true }); });
  }
  function shortcut(command) {
    // Keep Song ownership while a native transaction is pending, without queuing edits.
    if (state.busy) return true;
    const c = clip(), n = c?.notes[state.note];
    const views = { clip: 'Clip', automation: 'Automation', arrangeMix: state.view === 'Mixer' ? 'Arrangement' : 'Mixer' };
    if (views[command]) {
      const frame = views[command] === 'Clip' && state.view !== 'Clip';
      changeView(views[command]); if (frame) frameClipNotes(); state.inspector = null; draw(); root.focus({ preventScroll: true }); return true;
    }
    if (command === 'transport' || command === 'restart') {
      const fn = command === 'transport' ? ctx.playPause : ctx.restart;
      if (!fn) return false;
      action(fn); return true;
    }
    if (command === 'device') {
      const route = state.model.tracks[state.track].route;
      if (route.kind !== 1) { announce('This track sends MIDI; select a sound-routed track to open its instrument.'); return true; }
      openInspector(`s${route.index + 1}`); return true;
    }
    if (command === 'sidebar') {
      if (!ctx.toggleSidebar) return false;
      ctx.toggleSidebar(); return true;
    }
    if (command === 'mute') {
      shortcutEdit(() => edit(`Toggle track ${state.track + 1} mute`, m => { m.tracks[state.track].muted ^= 1; })); return true;
    }
    if (command === 'rename') {
      const entry = state.view === 'Arrangement' ? root.querySelector('.sq-entry.is-selected') : null;
      const input = entry?.querySelector('.sq-name') || root.querySelector(`[aria-label="Track ${state.track + 1} name"]`);
      if (!input?.beginNameEdit) return false;
      input.beginNameEdit(); return true;
    }
    if (state.view === 'Clip' && n) {
      if (command === 'duplicate') { const original = clone(n); shortcutEdit(() => edit('Duplicate note', m => { state.note = duplicateNote(clip(m), original); })); return true; }
      if (command === 'delete') {
        const original = clone(n);
        shortcutEdit(() => edit('Delete note', m => {
          const c = clip(m), i = c?.notes.findIndex(x => JSON.stringify(x) === JSON.stringify(original));
          if (i == null || i < 0) throw new Error('This note changed elsewhere. Select it again.');
          c.notes.splice(i, 1); c.trigs = c.trigs.filter(t => t.step !== original.step || t.lane !== original.pitch); state.note = -1;
        })); return true;
      }
      const delta = { arrowleft: [-1, 0], arrowright: [1, 0], arrowup: [0, 1], arrowdown: [0, -1] }[command];
      if (delta) { shortcutEdit(() => noteEdit(noteNudge(c, n, ...delta), 'Nudge note')); return true; }
    }
    if (state.view === 'Arrangement' && ['duplicate', 'delete'].includes(command)) {
      const original = [...state.model.song], index = state.song;
      if (!arrangementEntries(state.model)[index]) return false;
      shortcutEdit(() => edit(command === 'duplicate' ? 'Copy song entry' : 'Remove song entry', m => {
        if (JSON.stringify(m.song) !== JSON.stringify(original)) throw new Error('The arrangement changed elsewhere. Select the section again.');
        const entries = arrangementEntries(m);
        if (command === 'duplicate') entries.splice(index + 1, 0, clone(entries[index]));
        else { entries.splice(index, 1); state.song = Math.max(0, index - 1); }
        m.song = entries.flatMap(e => Array(e.presses).fill(e.scene));
      })); return true;
    }
    return false;
  }
  const onKey = makeSongShortcuts(root, { ready: () => !!state.model && !disposed,
    run: shortcut, claimKeys: ctx.claimKeys });
  root.addEventListener('keydown', e => {
    if (onKey(e)) return;
    if ((deviceDialog.open && e.key === 'Escape') || e.target.closest('input, select, textarea')) e.stopPropagation();
  });
  window.addEventListener('resize', syncMixerAfterResize);
  compactMixerMedia.addEventListener('change', syncMixerDisclosure);
  root.addEventListener('dragover', e => { if ([...(e.dataTransfer?.types || [])].includes('Files')) { e.preventDefault(); e.stopPropagation(); } });
  root.addEventListener('drop', e => {
    const files = [...(e.dataTransfer?.files || [])];
    if (!files.length || !files.every(f => /\.midi?$/i.test(f.name))) return;
    e.preventDefault(); e.stopPropagation(); e.lunarInto = true; importFiles(files);
  });
return { render() { if (state.dirty && !state.busy) refresh(); return root; }, refresh, update, onTelemetry, syncLevels, onKey, contains,
    toggleTransport: () => action(ctx.playPause), restartTransport: () => action(ctx.restart),
    wantRows() { return (ctx.metadata?.doc?.telemetry?.sections || []).filter(s => ['meters', 'levels'].includes(s.name)).flatMap(s => s.rows.flatMap((row, r) => state.view === 'Mixer' || row === 'out.post_master' ? [s.mask + r] : [])); },
    invalidate() { state.dirty = true; readRevision++; }, destroy() { gridObserver.disconnect(); cancelAnimationFrame(resizeFrame); if (ctx.transportHost) transportMount.removeEventListener('focusout', finishEdit); window.removeEventListener('pointerup', finishPointer); window.removeEventListener('pointercancel', finishPointer); releaseFader?.(); closeInspector(); disposed = true; cancelDrag?.(); window.removeEventListener('resize', syncMixerAfterResize); compactMixerMedia.removeEventListener('change', syncMixerDisclosure); if (ctx.transportHost) transportMount.replaceChildren(); root.remove(); } };
}
