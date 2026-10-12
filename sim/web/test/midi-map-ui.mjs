// Real app controls with mocked Web MIDI. No controller/hardware acceptance.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
const [www, out = '/tmp/midi-map-ui'] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8792);
const { browser, name } = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.addInitScript(() => {
  const inputs = new Map(['A', 'B'].map((id) => [id, { id, name: `Controller ${id}`, state: 'connected', onmidimessage: null }]));
  window.midiAccess = { inputs, onstatechange: null };
  Object.defineProperty(navigator, 'requestMIDIAccess', { configurable: true, value: async () => window.midiAccess });
  window.emitMidi = (id, data) => inputs.get(id)?.onmidimessage?.({ data: new Uint8Array(data) });
});
try {
  await page.goto(url); await page.waitForFunction(() => window.fm1?.midiLearn);
  await page.click('[data-layout="workbench"]'); await page.waitForFunction(() => window.fm1.editor);
  await page.click('[data-layout="panel"]');
  await page.evaluate(() => {
    document.querySelector('#power-overlay').hidden = true;
    window.trace = [];
    window.midiAcks = []; window.delayMidiAck = false;
    window.fm1.node = { port: { postMessage: (m) => { window.trace.push(m); if (m.type === 'midi-map') {
      const ack = () => window.fm1.files.onWorklet({ type: 'midi-map-set', id: m.id, ok: true });
      if (window.delayMidiAck) window.midiAcks.push(ack); else queueMicrotask(ack);
    } else if (m.type === 'state-save') queueMicrotask(() => window.fm1.files.onWorklet({ type: 'state-saved', id: m.id, ok: false })); } } };
    window.fm1.midiLearn.refresh();
  });
  await page.click('#midi');
  const registered = await page.evaluate(() => [...window.fm1.midiLearn.map.targets.keys()]);
  assert.equal(registered.filter((s) => s.startsWith('panel:key:')).length, 27);
  assert.equal(registered.filter((s) => s.startsWith('panel:button:')).length, 14);
  assert.equal(registered.filter((s) => s.startsWith('panel:encoder:')).length, 7);
  assert.ok(registered.includes('panel:master') && registered.includes('panel:power'));
  await page.click('#midi-learn'); await page.click('[data-key="0"]');
  await page.evaluate(() => { window.trace = []; window.emitMidi('A', [0x90, 60, 100]); window.emitMidi('A', [0xe0, 0, 64]); });
  assert.deepEqual(await page.evaluate(() => window.trace.filter((m) => ['key', 'note-on', 'bend'].includes(m.type))), []);
  await page.screenshot({ path: join(out, 'panel-learn.png') });
  await page.click('#midi-learn');
  await page.evaluate(() => { window.trace = []; window.emitMidi('A', [0x90, 60, 90]); window.emitMidi('A', [0x90, 60, 100]); window.emitMidi('A', [0x80, 60, 0]); });
  assert.deepEqual(await page.evaluate(() => window.trace.filter((m) => m.type === 'key').map((m) => [m.key, m.down])), [[0, true], [0, false]]);
  await page.evaluate(() => { window.trace = []; window.emitMidi('B', [0x90, 60, 100]); window.emitMidi('A', [0x91, 60, 100]); window.emitMidi('A', [0xe0, 0, 64]); window.emitMidi('A', [0xb0, 7, 127]); window.emitMidi('A', [0xb0, 123, 0]); });
  assert.deepEqual(await page.evaluate(() => window.trace.filter((m) => ['note-on', 'bend', 'master', 'panic'].includes(m.type)).map((m) => m.type)), ['note-on', 'note-on', 'bend', 'master', 'panic']);
  await page.evaluate(() => { window.trace = []; window.emitMidi('A', [0x90, 60, 100]); window.midiAccess.inputs.get('A').state = 'disconnected'; window.midiAccess.onstatechange(); });
  assert.deepEqual(await page.evaluate(() => window.trace.filter((m) => m.type === 'key').map((m) => m.down)), [true, false]);

  // Export cannot snapshot a browser-only map while either queued native
  // update is unacknowledged. Acknowledgement invalidates cached Song state.
  await page.evaluate(async () => {
    await window.fm1.files.midiSettled(); window.trace = []; window.delayMidiAck = true;
    window.invalidations = 0;
    const changed = window.fm1.editor.midiMapChanged;
    window.fm1.editor.midiMapChanged = () => { window.invalidations++; changed(); };
    window.fm1.files.midiChanged(); window.fm1.files.midiChanged();
    window.pendingExport = window.fm1.files.projectSnapshot().catch((e) => e.message);
  });
  await page.waitForFunction(() => window.midiAcks.length === 1);
  assert.equal(await page.evaluate(() => window.trace.some((m) => m.type === 'state-save')), false);
  await page.evaluate(() => window.midiAcks.shift()());
  await page.waitForFunction(() => window.midiAcks.length === 1);
  assert.equal(await page.evaluate(() => window.trace.some((m) => m.type === 'state-save')), false);
  await page.evaluate(() => { window.delayMidiAck = false; window.midiAcks.shift()(); });
  await page.waitForFunction(() => window.trace.some((m) => m.type === 'state-save'));
  assert.equal(await page.evaluate(() => window.invalidations), 2);
  assert.match(await page.evaluate(() => window.pendingExport), /could not be saved/);

  // An explicit refusal remains a save error until a later successful update.
  const refused = await page.evaluate(async () => {
    const node = window.fm1.node;
    window.fm1.node = { port: { postMessage(m) { queueMicrotask(() => window.fm1.files.onWorklet({ type: 'midi-map-set', id: m.id, ok: false, error: 'Native mapping refused' })); } } };
    await window.fm1.files.midiChanged();
    const error = await window.fm1.files.projectSnapshot().catch((e) => e.message);
    window.fm1.node = node; await window.fm1.files.midiChanged(); return error;
  });
  assert.equal(refused, 'Native mapping refused');
  const timedOut = await page.evaluate(async () => {
    const node = window.fm1.node; window.fm1.node = { port: { postMessage() {} } };
    await window.fm1.files.midiChanged();
    const error = await window.fm1.files.projectSnapshot().catch((e) => e.message);
    window.fm1.node = node; await window.fm1.files.midiChanged(); return error;
  });
  assert.match(timedOut, /not acknowledged/);
  await page.evaluate(() => { window.midiAccess.inputs.get('A').state = 'connected'; window.midiAccess.onstatechange(); window.trace = []; window.emitMidi('A', [0x90, 60, 100]); window.dispatchEvent(new Event('blur')); });
  assert.deepEqual(await page.evaluate(() => window.trace.filter((m) => m.type === 'key').map((m) => m.down)), [true, false]);

  // Generic DOM controls use their actual click/input/change handlers. A clone
  // replaces each element to exercise semantic IDs through a complete redraw.
  await page.evaluate(async () => {
    const mod = await import('./midi-map.js'); window.mappingModule = mod;
    const fixture = document.createElement('section'); fixture.id = 'mapping-fixture'; fixture.style.cssText = 'position:fixed;left:20px;top:90px;padding:24px;background:#172033;z-index:4';
    fixture.innerHTML = '<button id="mapping-button">Action</button><input id="mapping-range" type="range" min="-10" max="10" step="2"><select id="mapping-select"><option value="a">A</option><option disabled value="b">B</option><option value="c">C</option></select><input id="mapping-toggle" type="checkbox"><input id="mapping-text" type="text"><button id="mapping-disabled" disabled>Read only</button><div id="mapping-slider" role="slider" tabindex="0" aria-label="Custom parameter">Parameter</div>';
    document.body.append(fixture); window.fixtureCalls = [];
    fixture.querySelector('#mapping-button').onclick = () => window.fixtureCalls.push('click');
    fixture.querySelector('#mapping-range').oninput = (e) => window.fixtureCalls.push(['range', e.target.value]);
    fixture.querySelector('#mapping-select').onchange = (e) => window.fixtureCalls.push(['select', e.target.value]);
    fixture.querySelector('#mapping-toggle').onchange = (e) => window.fixtureCalls.push(['toggle', e.target.checked]);
    window.fm1.midiLearn.register(fixture.querySelector('#mapping-slider'), 'editor:param:test:1', { kind: 'value', value: (u) => window.fixtureCalls.push(['parameter', u]) });
    window.fm1.midiLearn.refresh();
    const map = window.fm1.midiLearn.map;
    const targets = ['mapping-button', 'mapping-range', 'mapping-select', 'mapping-toggle', 'mapping-slider'];
    const bindings = targets.map((id, i) => ({ target: mod.targetId(document.getElementById(id)), source: 'A', channel: 0, kind: 'cc', number: i + 20 }));
    map.import({ version: 1, bindings });
    // A disabled control never invokes its callback; arbitrary text is absent.
    window.disabledClicked = false; document.getElementById('mapping-disabled').onclick = () => { window.disabledClicked = true; };
    const disabledId = mod.targetId(document.getElementById('mapping-disabled'));
    map.import({ version: 1, bindings: [...bindings, { target: disabledId, source: 'A', channel: 0, kind: 'note', number: 61 }] });
    window.emitMidi('A', [0x90, 61, 100]);
    window.textMapped = map.targets.has(mod.targetId(document.getElementById('mapping-text')));
    for (let i = 20; i < 25; i++) window.emitMidi('A', [0xb0, i, 127]);
  });
  assert.deepEqual(await page.evaluate(() => window.fixtureCalls), ['click', ['range', '10'], ['select', 'c'], ['toggle', true], ['parameter', 1]]);
  assert.equal(await page.evaluate(() => window.disabledClicked || window.textMapped), false);
  await page.evaluate(() => { document.querySelector('#mapping-text').focus(); window.fixtureCalls = []; window.emitMidi('A', [0xb0, 21, 0]); });
  assert.deepEqual(await page.evaluate(() => window.fixtureCalls), []);
  await page.evaluate(() => {
    document.querySelector('#mapping-text').blur();
    const old = document.querySelector('#mapping-button'), clone = old.cloneNode(true); clone.textContent = 'Action changed'; clone.onclick = () => window.fixtureCalls.push('redraw'); old.replaceWith(clone);
    window.fm1.midiLearn.refresh(); window.emitMidi('A', [0xb0, 20, 0]); window.emitMidi('A', [0xb0, 20, 127]);
  });
  assert.deepEqual(await page.evaluate(() => window.fixtureCalls), ['redraw']);
  await page.click('#midi-learn');
  await page.screenshot({ path: join(out, 'control-learn.png') });
  await page.getByRole('button', { name: 'Clear MIDI assignment for Action changed', exact: true }).click();
  assert.equal(await page.evaluate(() => [...window.fm1.midiLearn.map.bindings.values()].some((b) => b.target === 'ui:mapping-button')), false);
  await page.click('#midi-learn');
  await page.evaluate(() => { window.fm1.node = null; }); // stop the fake node before reload
  await page.reload(); await page.waitForFunction(() => window.fm1?.midiLearn);
  assert.equal(await page.evaluate(() => window.fm1.midiLearn.map.export().bindings.length), 5);
  await page.evaluate(() => { Object.defineProperty(navigator, 'requestMIDIAccess', { value: undefined }); });
  await page.click('#midi-learn');
  await page.getByRole('status').filter({ hasText: 'Web MIDI is unavailable' }).waitFor();
  assert.equal(await page.locator('.midi-learn-help button').first().isDisabled(), true);
  assert.deepEqual(errors, []);
  writeFileSync(join(out, 'report.json'), JSON.stringify({ browser: name, checks: 'panel registration; silent learning; held native keys; source/channel pass-through; disconnect/blur release; queued ACK export barrier; cache invalidation; refusal and timeout save errors; buttons/range/select/toggle/custom adapter; disabled/text/typing; redraw; clear; reload; unavailable Web MIDI', errors }, null, 2));
  console.log(`${name}: MIDI learn checks passed`);
} finally { await browser.close(); server.close(); }
