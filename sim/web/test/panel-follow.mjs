// Test-only, serializable into Playwright's page. Main-thread observations
// distinguish message delivery from editor deferral; they do not timestamp
// receipt inside the AudioWorklet. Reading clocks/DOM adds diagnostic overhead.
// MIT licence, like the rest of this repository.
export async function observePanelFollow() {
  const sim = window.fm1, ed = sim.editor, v = ed.state.panelView;
  const knob2 = v.knobs[1];
  const key = `${knob2.role === 1 ? `s${knob2.sound + 1}` : '?'}:${knob2.uid}`;
  const row = ed.rows.get(key);
  const value = (r) => r ? r.el.querySelector('.ed-val, [aria-checked="true"], select').value || r.el.textContent : null;
  const before = value(row);
  const chips = [...document.querySelectorAll('.ed-k:not([hidden])')].map((c) => c.textContent);
  const trace = { observer: 'main-thread', perturbsTiming: true, events: [], frames: [], droppedEvents: 0 };
  let t0, frames = 0;
  const state = () => ({ ms: performance.now() - t0, audioTime: sim.ctx ? sim.ctx.currentTime : null,
    audioState: sim.ctx ? sim.ctx.state : null, loading: ed.state.loading, gen: ed.state.gen,
    pendingChanges: ed.state.pendingChanges.length, inflight: ed.state.inflight,
    rowConnected: row ? row.el.isConnected : false, value: value(row), currentRowValue: value(ed.rows.get(key)) });
  const record = (phase, message) => {
    if (trace.events.length >= 128) { ++trace.droppedEvents; return; }
    trace.events.push({ phase, type: message.type, bytes: message.bytes ? message.bytes.byteLength : null, ...state() });
  };
  const onMain = (event) => record('main-port', event.data);
  const port = ed.state.port, onEditor = port.onmessage;
  function observedEditor(event) {
    record('editor-before', event.data);
    try { return onEditor.call(this, event); }
    finally { record('editor-after', event.data); }
  }
  sim.node.port.addEventListener('message', onMain);
  port.onmessage = observedEditor;
  try {
    t0 = performance.now();
    trace.initial = state();
    sim.node.port.postMessage({ type: 'encoder', encoder: 4, delta: 3 });
    while (frames < 60) {
      await new Promise((r) => requestAnimationFrame(r));
      ++frames;
      trace.frames.push({ frame: frames, ...state() });
      if (value(row) !== before) break;
    }
    const ms = performance.now() - t0;
    const h = ed.history.entries[ed.history.entries.length - 1];
    return { key, frames, ms, chips, knobs: v.knobs.filter((k) => k.kind).length,
      entry: h ? { origin: h.origin, how: h.how, label: h.label } : null,
      from: document.querySelector('.ed-from').textContent, flashed: row && row.el.classList.contains('is-flash'), trace };
  } finally {
    sim.node.port.removeEventListener('message', onMain);
    port.onmessage = onEditor;
  }
}
