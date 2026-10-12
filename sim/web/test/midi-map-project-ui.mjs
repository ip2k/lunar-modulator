// Combined-source gate: real native module, file codec and editor dispatch.
// Requires a module rebuilt with fm1w_midi_map_set; mocked Web MIDI only.
import assert from 'node:assert/strict';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';
const [www, out = '/tmp/midi-map-project-ui'] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const { server, url } = await serve(www, 8793);
const { browser, name } = await launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = []; page.on('pageerror', (e) => errors.push(e.message));
await page.addInitScript(() => {
  const input = { id: 'native-test-controller', name: 'Mock controller', state: 'connected' };
  Object.defineProperty(navigator, 'requestMIDIAccess', { configurable: true, value: async () => ({ inputs: new Map([[input.id, input]]), onstatechange: null }) });
  window.emitMidi = (data) => input.onmidimessage?.({ data: new Uint8Array(data) });
});
try {
  await page.goto(`${url}?load=examples/first-orbit.lunar`);
  await page.click('[data-layout="workbench"]'); await page.waitForFunction(() => window.fm1?.editor);
  await page.click('#power-on');
  await page.waitForFunction(() => window.fm1.editor.state.mirror?.blocks.size > 6 && window.fm1.files.powered, null, { timeout: 30000 });
  // Workbench moves panel connection controls into the Simulator disclosure.
  const simulator = page.locator('.ed-footer-menu summary').filter({ hasText: /^Simulator$/ });
  async function simulatorControl(selector) {
    if (!await page.locator(selector).isVisible()) await simulator.click();
    await page.click(selector); // A control activation closes its disclosure.
  }
  await simulatorControl('#midi');
  const before = await page.evaluate(() => window.fm1.files.saveText('project'));
  await page.evaluate(async () => { window.cachedSongBeforeLearn = await window.fm1.editor.sequencerHost.fetchProject(); });
  await page.click('#midi-learn'); await page.click('[data-key="0"]');
  await page.evaluate(() => window.emitMidi([0x90, 60, 100])); await page.click('#midi-learn');
  const mapped = await page.evaluate(() => window.fm1.files.projectSnapshot());
  const bindings = JSON.parse(mapped.text).browser.midiMap.bindings;
  assert.deepEqual(bindings, [{ target: 'panel:key:0', source: 'native-test-controller', channel: 0, kind: 'note', number: 60 }]);
  const stale = await page.evaluate(async () => {
    try { await window.fm1.editor.sequencerHost.applyProject(window.cachedSongBeforeLearn); return 'accepted'; }
    catch (e) { return e.message; }
  });
  assert.match(stale, /project changed/i, 'a cached Song document cannot overwrite freshly learned mappings');
  const seqEdited = await page.evaluate(async () => {
    const host = window.fm1.editor.sequencerHost;
    const { parseSet, writeSet } = await import('./editor/sequence-model.js');
    const doc = await host.fetchProject(), set = parseSet(doc.set); set.bpmX100 += 100; doc.set = writeSet(set);
    await host.applyProject(doc, 'MIDI mapping preservation test');
    return JSON.parse((await window.fm1.files.projectSnapshot()).text).browser.midiMap.bindings;
  });
  assert.deepEqual(seqEdited, bindings, 'learn → native Song edit → snapshot/save preserves assignments');
  const afterDoc = JSON.parse(mapped.text); delete afterDoc.browser;
  const beforeDoc = JSON.parse(before); delete beforeDoc.browser;
  assert.deepEqual(afterDoc, beforeDoc, 'assigning a controller must not alter engines, sounds, session or song');
  const result = await page.evaluate(async ({ before, text }) => {
    const f = window.fm1.files, encode = (s) => new TextEncoder().encode(s);
    const old = await f.load(encode(before), { name: 'old.lunar', before: false, quiet: true });
    const cleared = window.fm1.midiLearn.map.export();
    const json = await f.load(encode(text), { name: 'mapped.lunar', before: false, quiet: true });
    const jsonMap = window.fm1.midiLearn.map.export();
    const packed = await f.shadow('check', { bytes: encode(text), kind: 0, into: 0, slot: 0, flags: 0 });
    if (!packed.ok) throw new Error(JSON.stringify(packed.report));
    window.fm1.midiLearn.map.import(null); await f.midiChanged();
    const binary = await f.load(packed.bin, { d: { enc: 1, kind: 'project', title: 'Binary mapping' }, before: false, quiet: true });
    return { old: old.ok, cleared, json: json.ok, jsonMap, binary: binary.ok, binaryMap: window.fm1.midiLearn.map.export(), text: await f.saveText('project') };
  }, { before, text: mapped.text });
  assert.equal(result.old && result.json && result.binary, true);
  assert.deepEqual(result.cleared.bindings, []);
  assert.deepEqual(result.jsonMap.bindings, bindings); assert.deepEqual(result.binaryMap.bindings, bindings);
  assert.deepEqual(JSON.parse(result.text).browser.midiMap.bindings, bindings);

  // Derived caption IDs include whitespace; the native policy must match JS.
  const caption = await page.evaluate(async () => {
    // An isolated scope keeps the workbench's semantic layout attributes from
    // replacing this deliberately caption-derived ID with an ordinal ID.
    const scope = document.createElement('main'); scope.id = 'mapping-caption-test';
    const button = document.createElement('button'); button.textContent = 'Next bar / Song'; scope.append(button); document.body.append(scope);
    const ui = window.fm1.midiLearn; ui.refresh(); const { targetId } = await import('./midi-map.js');
    const id = targetId(button); ui.map.learn(true); ui.map.select(id); window.emitMidi([0x90, 61, 100]); ui.map.learn(false);
    const text = (await window.fm1.files.projectSnapshot()).text; scope.remove(); return { id, bindings: JSON.parse(text).browser.midiMap.bindings };
  });
  assert.ok(caption.id.includes('Next bar / Song'));
  assert.ok(caption.bindings.some((b) => b.target === caption.id));

  // The real editor slider dispatches setValue -> packed native edit and history.
  await page.evaluate(() => { window.fm1.editor.setKeys('edit'); window.fm1.editor.select('s2', { view: 'sound' }); });
  await page.waitForSelector('.ed-slider[data-midi-id]');
  const chosen = await page.evaluate(() => {
    const e = document.querySelector('.ed-slider[data-midi-id]'), id = e.dataset.midiId;
    window.fm1.midiLearn.refresh();
    const map = window.fm1.midiLearn.map;
    map.learn(true); map.select(id); window.emitMidi([0xb0, 20, 64]); map.learn(false);
    const row = window.fm1.editor.rows.get(e.dataset.fk), uid = row.uid, key = row.key;
    const block = window.fm1.editor.state.mirror.blocks.get(key);
    return { id, key, uid, before: uid === 'level' ? window.fm1.editor.state.mirror.levels[Number(key.slice(1)) - 1] : block.values.get(uid), history: window.fm1.editor.history.entries.length };
  });
  await page.evaluate(() => { document.activeElement.blur(); window.emitMidi([0xb0, 20, 127]); });
  await page.waitForFunction(() => window.fm1.editor.state.inflight === 0);
  const edited = await page.evaluate(({ key, uid }) => {
    const ed = window.fm1.editor;
    return { value: uid === 'level' ? ed.state.mirror.levels[Number(key.slice(1)) - 1] : ed.state.mirror.blocks.get(key).values.get(uid), history: ed.history.entries.length };
  }, chosen);
  assert.notEqual(edited.value, chosen.before); assert.ok(edited.history > chosen.history);
  await page.evaluate(() => window.fm1.editor.undo()); await page.waitForFunction(() => window.fm1.editor.state.inflight === 0);
  const undone = await page.evaluate(({ key, uid }) => uid === 'level' ? window.fm1.editor.state.mirror.levels[Number(key.slice(1)) - 1] : window.fm1.editor.state.mirror.blocks.get(key).values.get(uid), chosen);
  assert.equal(undone, chosen.before);
  // Autosave/library records carry the same metadata, not only downloaded JSON.
  await page.evaluate(() => window.fm1.files.autosave());
  const auto = await page.evaluate(async () => {
    const f = window.fm1.files, saved = await f.store.get('autosave', 'project');
    const r = await f.shadow('save', { kind: 1, arg: 0, live: saved.bin }); return JSON.parse(r.text).browser.midiMap;
  });
  assert.ok(auto.bindings.some((b) => b.target === chosen.id));
  assert.deepEqual(errors, []);
  await page.screenshot({ path: join(out, 'native-editor-mapping.png') });
  writeFileSync(join(out, 'report.json'), JSON.stringify({ browser: name, checks: 'metadata-only setter; stale cached Song refusal; learned map preserved by native Song edit/save; caption ID native acknowledgement; JSON+binary canonical roundtrip; old-project clear; native slider and undo; binary autosave', errors }, null, 2));
  console.log(`${name}: native MIDI mapping project checks passed`);
} finally { await browser.close(); server.close(); }
