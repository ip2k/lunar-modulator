// Real browser/native synchronization regression; no mock DSP. MIT.
// Run in the bounded Playwright container: node sequencer-sync.mjs WWW OUT
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { serve } from './serve.mjs';
import { launch } from './launch.mjs';

const [www = 'sim/web/www', out = 'scratch/sequencer-sync'] = process.argv.slice(2);
await mkdir(out, { recursive: true });
const { server, url } = await serve(www, 18875, { prefix: '/lunar-modulator/' });
const { browser, name } = await launch();
const report = { browser: name, wasmSha256: createHash('sha256').update(await readFile(join(www, 'fm1.wasm'))).digest('hex'),
  scope: 'Real AudioWorklet/Wasm and browser history. Native seq-line exercises the panel command path; no physical controls or hardware acceptance.', checks: [], errors: [] };
const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
page.setDefaultTimeout(20000);
page.on('pageerror', e => report.errors.push(e.message));
async function until(fn, label) {
  const deadline = Date.now() + 20000;
  while (Date.now() < deadline) { if (await fn()) return; await page.waitForTimeout(60); }
  throw Error(`Timed out: ${label}`);
}
async function check(label, fn) { await fn(); report.checks.push(label); console.log(`PASS ${label}`); }
async function model() { return page.evaluate(async () => window.syncTest.model()); }
async function idle() { await page.waitForFunction(() => !fm1.editor.state.sequenceBusy); }
async function nativeNote(pitch) {
  await page.evaluate(p => fm1.node.port.postMessage({ type: 'seq-line', bytes: new TextEncoder().encode(`addp 0 1 1 ${p} 96`) }), pitch);
  await until(async () => (await model()).tracks[0].clips[0].notes.some(n => n.pitch === pitch), `native note ${pitch}`);
}
async function reset() {
  await page.evaluate(async () => {
    const { emptySet, emptyClip, writeSet } = window.syncTest.api;
    const doc = await fm1.editor.sequencerHost.fetchProject();
    doc.title = 'Native synchronization regression'; doc.master = [null, null]; doc.mod = { seed: 1, rack: [], cables: [] };
    doc.sounds = Array.from({ length: 4 }, () => ({ engine: 'test-sine', params: { Volume: .2 }, level: 50, inserts: [null, null], midi_fx: [] }));
    const set = emptySet(); set.song = [0]; set.songEnd = 0;
    set.tracks[0].route = { kind: 1, index: 0 }; set.tracks[0].clips[0] = emptyClip(16);
    set.tracks[0].clips[0].notes = [{ tick: 0, gate: 96, pitch: 60, vel: 100, step: 0 }];
    doc.set = writeSet(set); await fm1.editor.sequencerHost.applyProject(doc, 'Synchronization fixture');
    await fm1.editor.sequencer.refresh(); fm1.editor.history.clear();
  });
  await page.getByRole('tab', { name: 'Clip', exact: true }).click();
  await until(async () => await page.locator('.sq-note').count() === 1, 'fixture note');
}
async function velocity(value) {
  await page.locator('.sq-note').first().click();
  const field = page.getByLabel('Velocity', { exact: true });
  await field.fill(String(value)); await field.dispatchEvent('change');
  await until(async () => (await model()).tracks[0].clips[0].notes.find(n => n.pitch === 60)?.vel === value, 'velocity native acknowledgement');
  await idle();
}
try {
  await page.goto(`${url}?view=sequencer`);
  await page.getByRole('button', { name: 'Power on', exact: true }).click();
  await page.waitForFunction(() => window.fm1?.editor?.state.mirror && fm1.editor.sequencerHost);
  await page.waitForFunction(() => Number.isInteger(fm1.seq?.contentGen));
  await page.evaluate(async () => {
    const api = await import('/lunar-modulator/editor/sequence-model.js');
    window.syncTest = { api, model: async () => api.parseSet(JSON.parse((await fm1.files.projectSnapshot()).text).set) };
  });
  await check('clean sequencer undo and redo preserve native project state', async () => {
    await reset(); await velocity(72);
    await page.getByRole('button', { name: 'Undo', exact: true }).click();
    await until(async () => (await model()).tracks[0].clips[0].notes[0].vel === 100, 'clean undo'); await idle();
    await page.getByRole('button', { name: 'Redo', exact: true }).click();
    await until(async () => (await model()).tracks[0].clips[0].notes[0].vel === 72, 'clean redo'); await idle();
  });
  await check('native panel-path edit refreshes the visible clip and rejects stale undo', async () => {
    const generation = await page.evaluate(() => fm1.seq.contentGen);
    await nativeNote(64);
    await until(async () => await page.locator('.sq-note').count() === 2, 'visible native refresh');
    assert.notEqual(await page.evaluate(() => fm1.seq.contentGen), generation);
    const at = await page.evaluate(() => fm1.editor.history.at);
    await page.getByRole('button', { name: 'Undo', exact: true }).click();
    await until(async () => (await page.locator('.ed-sr').allTextContents()).join(' ').includes('overwrite later changes'), 'stale undo refusal');
    await idle(); assert.equal(await page.evaluate(() => fm1.editor.history.at), at);
    assert.deepEqual((await model()).tracks[0].clips[0].notes.map(n => [n.pitch, n.vel]), [[60, 72], [64, 96]]);
  });
  await check('hidden sequencer invalidates without project reads and refreshes on reopen', async () => {
    await page.evaluate(() => fm1.editor.select('s1', { view: 'sound' }));
    assert.equal(await page.locator('.sq').count(), 0);
    await page.evaluate(() => {
      const original = fm1.files.projectSnapshot; window.syncTest.originalSnapshot = original; window.syncTest.hiddenReads = 0;
      fm1.files.projectSnapshot = (...args) => { window.syncTest.hiddenReads++; return original(...args); };
      fm1.node.port.postMessage({ type: 'seq-line', bytes: new TextEncoder().encode('addp 0 2 2 67 96') });
    });
    await page.waitForTimeout(350);
    assert.equal(await page.evaluate(() => window.syncTest.hiddenReads), 0);
    await page.evaluate(() => { fm1.files.projectSnapshot = window.syncTest.originalSnapshot; fm1.editor.select('s1', { view: 'sequencer' }); });
    await until(async () => await page.locator('.sq-note').count() === 3, 'reopened native refresh');
    assert.equal((await model()).tracks[0].clips[0].notes.some(n => n.pitch === 67), true);
  });
  await check('native edit after undo rejects stale redo and preserves its history cursor', async () => {
    await reset(); await velocity(72);
    await page.getByRole('button', { name: 'Undo', exact: true }).click();
    await until(async () => (await model()).tracks[0].clips[0].notes[0].vel === 100, 'undo before stale redo'); await idle();
    await nativeNote(69); await until(async () => await page.locator('.sq-note').count() === 2, 'redo native refresh');
    const at = await page.evaluate(() => fm1.editor.history.at);
    await page.getByRole('button', { name: 'Redo', exact: true }).click();
    await until(async () => (await page.locator('.ed-sr').allTextContents()).join(' ').includes('overwrite later changes'), 'stale redo refusal');
    await idle(); assert.equal(await page.evaluate(() => fm1.editor.history.at), at);
    assert.deepEqual((await model()).tracks[0].clips[0].notes.map(n => [n.pitch, n.vel]), [[60, 100], [69, 96]]);
  });
  assert.deepEqual(report.errors, []);
  report.ok = true;
} catch (err) {
  report.ok = false; report.failure = err.stack; await page.screenshot({ path: join(out, 'sequencer-sync-failure.png'), fullPage: true }); throw err;
} finally {
  await writeFile(join(out, `sequencer-sync-${name.split(' ')[0].toLowerCase()}.json`), JSON.stringify(report, null, 2));
  await browser.close(); await new Promise(resolve => server.close(resolve));
}
