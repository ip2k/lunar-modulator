import assert from 'node:assert/strict';
import test from 'node:test';
import { observePanelFollow } from './panel-follow.mjs';

// Synthetic message/frame schedules test observation and cleanup, not browser
// performance. In particular, a slow observation must stay slow in the report.
async function fixture(run, tick) {
  const saved = new Map(['window', 'document', 'performance', 'requestAnimationFrame'].map((k) => [k, globalThis[k]]));
  let frame = 0, text = '0.30';
  const listeners = new Set();
  const row = { el: { isConnected: true, querySelector: () => ({ value: text }), classList: { contains: () => true } } };
  const state = { loading: false, gen: 1, pendingChanges: [], inflight: 0,
    panelView: { knobs: [{ kind: 1 }, { kind: 1, role: 1, sound: 1, uid: 2 }] } };
  const original = function (e) {
    assert.equal(this, state.port);
    if (e.data.type === 'changes') {
      if (state.loading) state.pendingChanges.push(e.data);
      else { text = '0.33'; ++state.gen; }
    }
  };
  state.port = { onmessage: original };
  const sim = { ctx: { currentTime: 0, state: 'running' }, editor: { state, rows: new Map([['s2:2', row]]), history: { entries: [] } },
    node: { port: { addEventListener: (_, fn) => listeners.add(fn), removeEventListener: (_, fn) => listeners.delete(fn),
      postMessage: (m) => assert.deepEqual(m, { type: 'encoder', encoder: 4, delta: 3 }) } } };
  globalThis.window = { fm1: sim };
  globalThis.document = { querySelectorAll: () => [], querySelector: () => ({ textContent: 'From the panel' }) };
  globalThis.performance = { now: () => frame * 16 };
  globalThis.requestAnimationFrame = (done) => { ++frame; sim.ctx.currentTime += 0.016; tick({ frame, state, sim,
    change: () => state.port.onmessage({ data: { type: 'changes', bytes: new Uint8Array(32) } }),
    main: () => { for (const fn of listeners) fn({ data: { type: 'screen' } }); },
    applyPending: () => { state.pendingChanges = []; state.loading = false; text = '0.33'; ++state.gen; } }); done(); };
  try { await run(sim); }
  finally {
    assert.equal(state.port.onmessage, original, 'restore the exact handler');
    assert.equal(listeners.size, 0, 'remove diagnostic listeners');
    for (const [k, v] of saved) { if (v === undefined) delete globalThis[k]; else globalThis[k] = v; }
  }
}

test('late delivery remains 24 frames and records immediate editor application', async () => {
  await fixture(async () => {
    const r = await observePanelFollow();
    assert.equal(r.frames, 24); assert.equal(r.ms, 384);
    assert.equal(r.trace.events[0].ms, 384);
    assert.equal(r.trace.events[0].value, '0.30');
    assert.equal(r.trace.events[1].value, '0.33');
    assert.equal(r.trace.events[1].loading, false);
  }, ({ frame, change }) => { if (frame === 24) change(); });
});

test('early delivery deferred by loading is distinguishable from late delivery', async () => {
  await fixture(async (sim) => {
    sim.editor.state.loading = true;
    const r = await observePanelFollow();
    assert.equal(r.frames, 24);
    assert.equal(r.trace.events[0].ms, 16);
    assert.equal(r.trace.events[1].pendingChanges, 1);
    assert.equal(r.trace.events[1].value, '0.30');
    assert.equal(r.trace.frames[23].loading, false);
  }, ({ frame, change, applyPending }) => { if (frame === 1) change(); if (frame === 24) applyPending(); });
});

test('no delivery exhausts the unchanged 60-frame observation with bounded messages', async () => {
  await fixture(async () => {
    const r = await observePanelFollow();
    assert.equal(r.frames, 60); assert.equal(r.trace.frames.length, 60);
    assert.equal(r.trace.events.length, 128); assert.equal(r.trace.droppedEvents, 52);
  }, ({ main }) => { main(); main(); main(); });
});

test('exception restores the page handlers before propagating', async () => {
  await fixture(async (sim) => {
    sim.node.port.postMessage = () => { throw new Error('send failed'); };
    await assert.rejects(observePanelFollow(), /send failed/);
  }, () => {});
});
